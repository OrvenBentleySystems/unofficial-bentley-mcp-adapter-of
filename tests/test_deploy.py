from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import yaml

from core.detect import select_auto_targets
from core.emit.emitter import emit_configs
from core.common import AdapterError, load_target, validate_output_path
from core.uninstall import uninstall_generated


class DetectionTests(unittest.TestCase):
    def test_target_path_traversal_is_rejected(self) -> None:
        with self.assertRaises(AdapterError):
            load_target("../outside")

    def test_output_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            allowed = root / "allowed"
            allowed.mkdir()
            outside = root / "outside.json"
            outside.write_text("outside", encoding="utf-8")
            link = allowed / "config.json"
            try:
                os.symlink(outside, link)
            except OSError:
                self.skipTest("Symlink creation is unavailable")
            with self.assertRaises(AdapterError):
                validate_output_path(link, [allowed])

    def test_auto_selects_only_verified_present_writable_targets(self) -> None:
        detected = {
            "clients": [
                {
                    "id": "verified-client",
                    "present": True,
                    "auto_eligible": True,
                    "writable": True,
                    "skip_reason": None,
                },
                {
                    "id": "shape-client",
                    "present": True,
                    "auto_eligible": False,
                    "writable": True,
                    "skip_reason": "shape-only target is excluded",
                },
                {
                    "id": "absent-client",
                    "present": False,
                    "auto_eligible": True,
                    "writable": True,
                    "skip_reason": "client was not detected",
                },
            ]
        }
        selected, skipped = select_auto_targets(detected)
        self.assertEqual(["verified-client"], selected)
        self.assertEqual({"shape-client", "absent-client"}, {item["id"] for item in skipped})


class UninstallTests(unittest.TestCase):
    def test_uninstall_removes_only_generated_json_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "mcp.json"
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            config.write_text(
                json.dumps(
                    {
                        "_generated": {
                            "notice": "Generated artifact. Hand edits are overwritten.",
                            "source_profile": str(profile_path.resolve()),
                        },
                        "mcpServers": {
                            "microstation": {"command": "node"},
                            "hand-added": {"command": "python"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            profile = {
                "workspace_root": str(root),
                "allowed_directory": str(root),
                "modules": {
                    "microstation": {
                        "launch": {"command": "node", "args": []}
                    }
                },
                "targets": {"cursor": {"output": str(config)}},
            }
            detected = {
                "machine_path": str(machine_path),
                "clients": [
                    {"id": "cursor", "config_path": str(config)}
                ]
            }
            detected_path = root / "detected.json"
            profile_path.write_text(yaml.safe_dump(profile), encoding="utf-8")
            machine_path.write_text(
                json.dumps(
                    {
                        "known_folders": {
                            "user_profile": str(root),
                            "local_app_data": str(root),
                        }
                    }
                ),
                encoding="utf-8",
            )
            detected_path.write_text(json.dumps(detected), encoding="utf-8")
            uninstall_generated(profile_path, detected_path)
            remaining = json.loads(config.read_text(encoding="utf-8"))
            self.assertIn("hand-added", remaining["mcpServers"])
            self.assertNotIn("microstation", remaining["mcpServers"])


class MergeTests(unittest.TestCase):
    def _machine(self) -> dict:
        import getpass
        import socket

        return {
            "host": {
                "computer_name": socket.gethostname(),
                "account_name": getpass.getuser(),
            }
        }

    def _profile(self, target: str, output: str) -> dict:
        return {
            "allowed_directory": r"C:\mcp-work",
            "modules": {
                "microstation": {
                    "tier": "read",
                    "launch": {"command": "node", "args": ["bundle.mcp.js"]},
                }
            },
            "targets": {target: {"output": output}},
        }

    def test_auto_merge_preserves_cline_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "cline.json"
            output.write_text(
                json.dumps(
                    {"mcpServers": {"hand-added": {"command": "python"}}}
                ),
                encoding="utf-8",
            )
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(
                yaml.safe_dump(self._profile("cline", str(output))),
                encoding="utf-8",
            )
            machine_path.write_text(
                json.dumps(self._machine()), encoding="utf-8"
            )
            emit_configs(
                profile_path,
                machine_path,
                ["cline"],
                False,
                merge_existing=True,
            )
            merged = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("hand-added", merged["mcpServers"])
            self.assertIn("microstation", merged["mcpServers"])
            self.assertEqual("entries", merged["_generated"]["merge_mode"])

    def test_auto_merge_preserves_codex_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "config.toml"
            output.write_text('model = "existing-model"\n', encoding="utf-8")
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(
                yaml.safe_dump(self._profile("codex", str(output))),
                encoding="utf-8",
            )
            machine_path.write_text(
                json.dumps(self._machine()), encoding="utf-8"
            )
            emit_configs(
                profile_path,
                machine_path,
                ["codex"],
                False,
                merge_existing=True,
            )
            text = output.read_text(encoding="utf-8")
            self.assertIn('model = "existing-model"', text)
            self.assertIn('[mcp_servers."microstation"]', text)
            self.assertIn("Surrounding settings are preserved", text)


if __name__ == "__main__":
    unittest.main()
