from __future__ import annotations

import getpass
import json
import socket
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import yaml

from core.budget import calculate_budget
from core.common import AdapterError, discover_provider_ids
from core.provider import emit_provider_configs, run_provider_preflight
from core.emit.emitter import emit_configs


class _ProviderHandler(BaseHTTPRequestHandler):
    alias = "test-alias"

    def log_message(self, *_: object) -> None:
        return

    def _json(self, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/props":
            self._json(
                {
                    "build_info": "test-build",
                    "chat_template": "tool-aware-template",
                }
            )
            return
        if self.path == "/v1/models":
            self._json({"data": [{"id": self.alias}]})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self._json(
            {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "adapter_readiness",
                                        "arguments": '{"ready":true}',
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        )


class ProviderTests(unittest.TestCase):
    def _machine(self, root: Path) -> dict:
        return {
            "host": {
                "computer_name": socket.gethostname(),
                "account_name": getpass.getuser(),
            },
            "known_folders": {
                "user_profile": str(root),
                "local_app_data": str(root / "AppData" / "Local"),
            },
        }

    def _profile(self, root: Path, tier: str = "read") -> dict:
        modules = {}
        for module_id in (
            "microstation",
            "staadpro",
            "plaxis2d-input",
            "plaxis2d-output",
        ):
            modules[module_id] = {
                "tier": tier,
                "launch": {
                    "command": f"{module_id}.exe",
                    "args": ["serve"],
                },
            }
        return {
            "allowed_directory": str(root / "work"),
            "workspace_root": str(root / "workspace"),
            "modules": modules,
            "targets": {
                "codex": {"output": str(root / ".codex" / "config.toml")},
                "cline": {"output": str(root / ".cline" / "mcp.json")},
            },
        }

    def test_llamacpp_provider_is_discovered(self) -> None:
        self.assertIn("llamacpp", discover_provider_ids())

    def test_provider_emits_launch_codex_and_cline_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "work").mkdir()
            (root / ".codex").mkdir()
            (root / ".cline").mkdir()
            profile = self._profile(root)
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(yaml.safe_dump(profile), encoding="utf-8")
            machine_path.write_text(
                json.dumps(self._machine(root)), encoding="utf-8"
            )
            self.assertEqual(
                0,
                emit_provider_configs(
                    profile_path,
                    machine_path,
                    "llamacpp",
                    8080,
                    "test-alias",
                    False,
                ),
            )
            launch = root / "work" / "llamacpp-provider.generated.txt"
            codex = root / ".codex" / "llamacpp.bentley.generated.toml"
            cline = root / ".cline" / "llamacpp-setup.generated.txt"
            self.assertIn("--jinja", launch.read_text(encoding="utf-8"))
            self.assertIn(
                'wire_api = "responses"', codex.read_text(encoding="utf-8")
            )
            self.assertIn(
                "OpenAI Compatible", cline.read_text(encoding="utf-8")
            )

    def test_full_tier_is_rejected_for_local_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "work").mkdir()
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(
                yaml.safe_dump(self._profile(root, "full")), encoding="utf-8"
            )
            machine_path.write_text(
                json.dumps(self._machine(root)), encoding="utf-8"
            )
            with self.assertRaises(AdapterError):
                emit_provider_configs(
                    profile_path,
                    machine_path,
                    "llamacpp",
                    8080,
                    "test-alias",
                    True,
                )

    def test_remote_or_injected_provider_host_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "work").mkdir()
            profile = self._profile(root)
            profile["local_provider"] = {
                "id": "llamacpp",
                "host": 'attacker.invalid"\nenv_key="TOKEN',
                "port": 8080,
                "alias": "test-alias",
            }
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(yaml.safe_dump(profile), encoding="utf-8")
            machine_path.write_text(
                json.dumps(self._machine(root)), encoding="utf-8"
            )
            with self.assertRaises(AdapterError):
                emit_provider_configs(
                    profile_path,
                    machine_path,
                    "llamacpp",
                    None,
                    None,
                    True,
                )

    def test_provider_alias_is_toml_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "work").mkdir()
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(
                yaml.safe_dump(self._profile(root)), encoding="utf-8"
            )
            machine_path.write_text(
                json.dumps(self._machine(root)), encoding="utf-8"
            )
            with self.assertRaises(AdapterError):
                emit_provider_configs(
                    profile_path,
                    machine_path,
                    "llamacpp",
                    8080,
                    'bad"\nenv_key="TOKEN',
                    True,
                )

    def test_mcp_config_emit_rejects_full_tier_with_local_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = self._profile(root, "full")
            profile["local_provider"] = {
                "id": "llamacpp",
                "port": 8080,
                "alias": "test-alias",
            }
            profile["targets"] = {"cursor": {"output": "cursor.json"}}
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(yaml.safe_dump(profile), encoding="utf-8")
            machine_path.write_text(
                json.dumps(self._machine(root)), encoding="utf-8"
            )
            with self.assertRaises(AdapterError):
                emit_configs(
                    profile_path,
                    machine_path,
                    ["cursor"],
                    True,
                )

    def test_budget_reports_expected_catalogue_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = root / "site.yaml"
            profile_path.write_text(
                yaml.safe_dump(self._profile(root)), encoding="utf-8"
            )
            self.assertEqual(
                37,
                calculate_budget(profile_path, "read", "codex")["tool_count"],
            )
            self.assertEqual(
                75,
                calculate_budget(profile_path, "read", "cline")[
                    "exposed_tool_count"
                ],
            )
            self.assertEqual(
                75,
                calculate_budget(profile_path, "full", "codex")["tool_count"],
            )

    def test_provider_preflight_checks_build_alias_and_tool_call(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _ProviderHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = run_provider_preflight(
                {
                    "modules": {
                        "microstation": {
                            "tier": "read",
                            "launch": {
                                "command": "node",
                                "args": ["bundle.mcp.js"],
                            },
                        }
                    },
                    "local_provider": {
                        "id": "llamacpp",
                        "host": "127.0.0.1",
                        "port": server.server_port,
                        "alias": "test-alias",
                    }
                }
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertTrue(result["tool_call"])
        self.assertEqual("test-build", result["build"])


if __name__ == "__main__":
    unittest.main()
