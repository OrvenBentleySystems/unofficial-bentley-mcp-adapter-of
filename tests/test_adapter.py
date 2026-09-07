from __future__ import annotations

import json
import getpass
import socket
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from core.common import (
    AdapterError,
    discover_target_ids,
    load_module,
    validate_safe_profile,
)
from core.emit.emitter import emit_configs
from core.preflight.checks import (
    CheckFailure,
    EXIT_APPLICATION,
    EXIT_DIRECTORY,
    EXIT_MACHINE,
    EXIT_MODEL,
    EXIT_PORT,
    EXIT_TOOL,
    EXIT_VERSION,
    EXIT_VERSION_RECORD,
    _check_models,
    _check_allowed_directory,
    _application_version_status,
    _machine_current,
    _version_matches,
    _version_record_complete,
    classify_port,
)
from core.tiers import resolve_tier


class TierTests(unittest.TestCase):
    def test_read_tier_excludes_never_auto_approve(self) -> None:
        for module_id in (
            "microstation",
            "staadpro",
            "plaxis2d-input",
            "plaxis2d-output",
        ):
            module = load_module(module_id)
            tools = set(resolve_tier(module, "read"))
            self.assertFalse(tools.intersection(module["never_auto_approve"]))

    def test_guided_tier_extends_read_tier(self) -> None:
        module = load_module("plaxis2d-input")
        self.assertTrue(
            set(resolve_tier(module, "read")).issubset(resolve_tier(module, "guided"))
        )


class PortTests(unittest.TestCase):
    def test_collision_wins_over_credential_diagnosis(self) -> None:
        rows = [
            {"pid": 10, "process": "Plaxis2DXInput.exe"},
            {"pid": 11, "process": "Plaxis3DInput.exe"},
        ]
        code, _ = classify_port(rows, "Plaxis2DXInput.exe")
        self.assertEqual("PORT_COLLISION", code)

    def test_wrong_single_owner_is_identity_mismatch(self) -> None:
        rows = [{"pid": 11, "process": "Plaxis3DInput.exe"}]
        code, _ = classify_port(rows, "Plaxis2DXInput.exe")
        self.assertEqual("PORT_IDENTITY_MISMATCH", code)

    def test_duplicate_listener_rows_for_same_pid_are_not_collision(self) -> None:
        rows = [
            {"pid": 10, "process": "Plaxis2DXInput.exe", "address": "0.0.0.0"},
            {"pid": 10, "process": "Plaxis2DXInput.exe", "address": "::"},
        ]
        code, _ = classify_port(rows, "Plaxis2DXInput.exe")
        self.assertEqual("PASS", code)

    def test_preflight_stage_exit_codes_are_distinct(self) -> None:
        codes = {
            EXIT_MACHINE,
            EXIT_VERSION_RECORD,
            EXIT_APPLICATION,
            EXIT_MODEL,
            EXIT_PORT,
            EXIT_VERSION,
            EXIT_DIRECTORY,
            EXIT_TOOL,
        }
        self.assertEqual(8, len(codes))


class ModelTests(unittest.TestCase):
    def test_plaxis_untitled_project_is_named_failure(self) -> None:
        module = load_module("plaxis2d-input")
        processes = [
            {
                "name": "Plaxis2DXInput.exe",
                "title": "PLAXIS 2D Advanced: [(Untitled)]",
            }
        ]
        with self.assertRaises(CheckFailure) as context:
            _check_models([module], processes)
        self.assertEqual("MODEL_NOT_OPEN", context.exception.code)

    @patch("core.preflight.checks._com_probe", return_value={})
    def test_staad_running_without_model_is_named_failure(self, _: object) -> None:
        module = load_module("staadpro")
        processes = [{"name": "Bentley.Staad.exe", "title": "STAAD.Pro 2026"}]
        with self.assertRaises(CheckFailure) as context:
            _check_models([module], processes)
        self.assertEqual("MODEL_NOT_OPEN", context.exception.code)


class VersionTests(unittest.TestCase):
    def test_plaxis_year_version_alias(self) -> None:
        self.assertTrue(_version_matches("23.02.01.1079", "2023.2.1.1079"))

    def test_verified_plaxis_build_is_accepted(self) -> None:
        requires = load_module("plaxis2d-input")["requires"]
        supported, verified, _ = _application_version_status(
            requires, "23.02.01.1079"
        )
        self.assertTrue(supported)
        self.assertTrue(verified)

    def test_upstream_current_plaxis_generation_reaches_live_probes(self) -> None:
        requires = load_module("plaxis2d-input")["requires"]
        supported, verified, reason = _application_version_status(
            requires, "25.01.03.005"
        )
        self.assertTrue(supported)
        self.assertFalse(verified)
        self.assertIn("not live-verified", reason)

    def test_unsupported_intermediate_plaxis_build_is_rejected(self) -> None:
        requires = load_module("plaxis2d-input")["requires"]
        supported, verified, _ = _application_version_status(
            requires, "2024.1.0"
        )
        self.assertFalse(supported)
        self.assertFalse(verified)

    def test_todo_is_incomplete(self) -> None:
        record = {
            field: "value"
            for field in (
                "date",
                "operator",
                "machine",
                "os build",
                "MicroStation build",
                "STAAD.Pro version",
                "PLAXIS version",
                "openstaad-mcp tag",
                "plaxis-mcp version",
                "AI client + version",
                "model identifier",
                "temperature",
                "allowed directory",
            )
        }
        record["operator"] = "TODO"
        with self.assertRaises(CheckFailure) as context:
            _version_record_complete({"version_record": record})
        self.assertEqual(EXIT_VERSION_RECORD, context.exception.exit_code)

    def test_foreign_machine_is_rejected(self) -> None:
        machine = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "host": {
                "computer_name": "not-this-machine",
                "account_name": getpass.getuser(),
            },
        }
        with self.assertRaises(CheckFailure) as context:
            _machine_current(machine, {"machine_max_age_hours": 24})
        self.assertEqual("MACHINE_FOREIGN", context.exception.code)


class DirectoryTests(unittest.TestCase):
    def test_synced_allowed_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            machine = {
                "known_folders": {
                    "user_profile": str(root.parent / "profile"),
                    "local_app_data": str(root.parent / "local"),
                },
                "working_directory": {"sync_roots": [str(root)]},
            }
            with self.assertRaises(CheckFailure) as context:
                _check_allowed_directory(
                    {"allowed_directory": str(root), "project_share_paths": []},
                    machine,
                )
            self.assertEqual("SYNCED_DIRECTORY_FORBIDDEN", context.exception.code)


class EmitterTests(unittest.TestCase):
    def test_automatic_approval_settings_are_rejected(self) -> None:
        with self.assertRaises(AdapterError):
            validate_safe_profile({"servers": {"plaxis": {"autoApprove": ["calculate"]}}})

    def test_emitted_configs_contain_pins_and_no_secret_values(self) -> None:
        machine = {
            "host": {
                "computer_name": socket.gethostname(),
                "account_name": getpass.getuser(),
            },
            "executables": {
                "node": r"C:\Tools\node.exe",
                "uvx": r"C:\Tools\uvx.exe",
            },
            "microstation": {"mcp_bundle": r"C:\Tools\bundle.mcp.js"},
        }
        profile = {
            "schema_version": 1,
            "allowed_directory": r"C:\mcp-work",
            "modules": {
                "microstation": {
                    "tier": "read",
                    "launch": {
                        "command": r"C:\Tools\node.exe",
                        "args": [r"C:\Tools\bundle.mcp.js"],
                        "env": {"API_TOKEN": {"secret": "microstation-token"}},
                    },
                }
            },
            "targets": {
                "copilot-cli": {"output": "copilot.json"},
                "vscode-copilot": {"output": "vscode.json"},
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(
                __import__("yaml").safe_dump(profile), encoding="utf-8"
            )
            machine_path.write_text(json.dumps(machine), encoding="utf-8")
            with patch("core.emit.writer_api.ROOT", root):
                with self.assertRaises(AdapterError):
                    emit_configs(
                        profile_path,
                        machine_path,
                        ["copilot-cli"],
                        False,
                    )
                self.assertEqual(
                    0,
                    emit_configs(
                        profile_path,
                        machine_path,
                        ["vscode-copilot"],
                        False,
                    ),
                )
            vscode = json.loads((root / "vscode.json").read_text(encoding="utf-8"))
            self.assertIn("pins", vscode["_generated"])
            self.assertEqual("promptString", vscode["inputs"][0]["type"])
            self.assertTrue(vscode["inputs"][0]["password"])

    def test_new_target_is_discovered_without_core_registration(self) -> None:
        machine = {
            "host": {
                "computer_name": socket.gethostname(),
                "account_name": getpass.getuser(),
            }
        }
        profile = {
            "allowed_directory": r"C:\mcp-work",
            "modules": {
                "microstation": {
                    "tier": "read",
                    "launch": {"command": "node", "args": ["bundle.mcp.js"]},
                }
            },
            "targets": {"fixture-client": {"output": "fixture.json"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "targets" / "fixture-client"
            target.mkdir(parents=True)
            (target / "target.yaml").write_text(
                "\n".join(
                    (
                        "id: fixture-client",
                        "format: json",
                        "root_key: mcpServers",
                        "requires_type: true",
                        "type_value: stdio",
                        "supports_inputs: false",
                        "supports_tool_allowlist: false",
                        "verified: false",
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            (target / "writer.py").write_text(
                "from core.emit.writer_api import render_standard_json\n"
                "def render(context):\n"
                "    return render_standard_json(context)\n",
                encoding="utf-8",
            )
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(
                __import__("yaml").safe_dump(profile), encoding="utf-8"
            )
            machine_path.write_text(json.dumps(machine), encoding="utf-8")
            with (
                patch("core.common.TARGETS_DIR", root / "targets"),
                patch("core.emit.writer_api.ROOT", root),
            ):
                self.assertIn("fixture-client", discover_target_ids())
                self.assertEqual(
                    0,
                    emit_configs(
                        profile_path,
                        machine_path,
                        ["fixture-client"],
                        False,
                    ),
                )
            self.assertTrue((root / "fixture.json").is_file())

    def test_codex_writer_emits_toml_with_write_approval(self) -> None:
        machine = {
            "host": {
                "computer_name": socket.gethostname(),
                "account_name": getpass.getuser(),
            }
        }
        profile = {
            "allowed_directory": r"C:\mcp-work",
            "modules": {
                "microstation": {
                    "tier": "read",
                    "launch": {"command": "node", "args": ["bundle.mcp.js"]},
                }
            },
            "targets": {"codex": {"output": "config.toml"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(
                __import__("yaml").safe_dump(profile), encoding="utf-8"
            )
            machine_path.write_text(json.dumps(machine), encoding="utf-8")
            with patch("core.emit.writer_api.ROOT", root):
                self.assertEqual(
                    0,
                    emit_configs(profile_path, machine_path, ["codex"], False),
                )
            rendered = (root / "config.toml").read_text(encoding="utf-8")
            self.assertIn('[mcp_servers."microstation"]', rendered)
            self.assertIn('default_tools_approval_mode = "writes"', rendered)
            self.assertIn("enabled_tools = [", rendered)
            self.assertNotIn("autoApprove", rendered)

    def test_claude_code_writer_emits_mcp_servers_json(self) -> None:
        machine = {
            "host": {
                "computer_name": socket.gethostname(),
                "account_name": getpass.getuser(),
            }
        }
        profile = {
            "allowed_directory": r"C:\mcp-work",
            "modules": {
                "microstation": {
                    "tier": "read",
                    "launch": {"command": "node", "args": ["bundle.mcp.js"]},
                }
            },
            "targets": {"claude-code": {"output": ".mcp.json"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(
                __import__("yaml").safe_dump(profile), encoding="utf-8"
            )
            machine_path.write_text(json.dumps(machine), encoding="utf-8")
            with patch("core.emit.writer_api.ROOT", root):
                self.assertEqual(
                    0,
                    emit_configs(
                        profile_path, machine_path, ["claude-code"], False
                    ),
                )
            rendered = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
            self.assertIn("microstation", rendered["mcpServers"])
            self.assertNotIn("type", rendered["mcpServers"]["microstation"])
            self.assertNotIn("autoApprove", json.dumps(rendered))

    def test_claude_desktop_writer_emits_restart_note(self) -> None:
        machine = {
            "host": {
                "computer_name": socket.gethostname(),
                "account_name": getpass.getuser(),
            }
        }
        profile = {
            "allowed_directory": r"C:\mcp-work",
            "modules": {
                "microstation": {
                    "tier": "read",
                    "launch": {"command": "node", "args": ["bundle.mcp.js"]},
                }
            },
            "targets": {
                "claude-desktop": {"output": "claude_desktop_config.json"}
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(
                __import__("yaml").safe_dump(profile), encoding="utf-8"
            )
            machine_path.write_text(json.dumps(machine), encoding="utf-8")
            with patch("core.emit.writer_api.ROOT", root):
                self.assertEqual(
                    0,
                    emit_configs(
                        profile_path, machine_path, ["claude-desktop"], False
                    ),
                )
            rendered = json.loads(
                (root / "claude_desktop_config.json").read_text(encoding="utf-8")
            )
            self.assertIn("microstation", rendered["mcpServers"])

    def test_cline_writer_emits_stdio_and_empty_autoapprove(self) -> None:
        machine = {
            "host": {
                "computer_name": socket.gethostname(),
                "account_name": getpass.getuser(),
            }
        }
        profile = {
            "allowed_directory": r"C:\mcp-work",
            "modules": {
                "microstation": {
                    "tier": "read",
                    "launch": {"command": "node", "args": ["bundle.mcp.js"]},
                }
            },
            "targets": {
                "cline": {
                    "output": "cline_mcp_settings.json",
                    "cli_output": "cline-cli.json",
                }
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(
                __import__("yaml").safe_dump(profile), encoding="utf-8"
            )
            machine_path.write_text(json.dumps(machine), encoding="utf-8")
            with patch("core.emit.writer_api.ROOT", root):
                self.assertEqual(
                    0,
                    emit_configs(profile_path, machine_path, ["cline"], False),
                )
            for name in ("cline_mcp_settings.json", "cline-cli.json"):
                rendered = json.loads((root / name).read_text(encoding="utf-8"))
                server = rendered["mcpServers"]["microstation"]
                self.assertEqual("stdio", server["type"])
                self.assertFalse(server["disabled"])
                self.assertEqual([], server["autoApprove"])

    def test_kilocode_writer_emits_current_mcp_command_array(self) -> None:
        machine = {
            "host": {
                "computer_name": socket.gethostname(),
                "account_name": getpass.getuser(),
            }
        }
        profile = {
            "allowed_directory": r"C:\mcp-work",
            "modules": {
                "microstation": {
                    "tier": "read",
                    "launch": {"command": "node", "args": ["bundle.mcp.js"]},
                }
            },
            "targets": {"kilocode": {"output": "kilo.jsonc"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(
                __import__("yaml").safe_dump(profile), encoding="utf-8"
            )
            machine_path.write_text(json.dumps(machine), encoding="utf-8")
            with patch("core.emit.writer_api.ROOT", root):
                self.assertEqual(
                    0,
                    emit_configs(profile_path, machine_path, ["kilocode"], False),
                )
            rendered = json.loads((root / "kilo.jsonc").read_text(encoding="utf-8"))
            server = rendered["mcp"]["microstation"]
            self.assertEqual("local", server["type"])
            self.assertEqual(["node", "bundle.mcp.js"], server["command"])
            self.assertTrue(server["enabled"])

    def test_cursor_writer_emits_mcp_servers_json(self) -> None:
        machine = {
            "host": {
                "computer_name": socket.gethostname(),
                "account_name": getpass.getuser(),
            }
        }
        profile = {
            "allowed_directory": r"C:\mcp-work",
            "modules": {
                "microstation": {
                    "tier": "read",
                    "launch": {"command": "node", "args": ["bundle.mcp.js"]},
                }
            },
            "targets": {"cursor": {"output": ".cursor/mcp.json"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(
                __import__("yaml").safe_dump(profile), encoding="utf-8"
            )
            machine_path.write_text(json.dumps(machine), encoding="utf-8")
            with patch("core.emit.writer_api.ROOT", root):
                self.assertEqual(
                    0,
                    emit_configs(profile_path, machine_path, ["cursor"], False),
                )
            rendered = json.loads(
                (root / ".cursor" / "mcp.json").read_text(encoding="utf-8")
            )
            self.assertIn("microstation", rendered["mcpServers"])
            self.assertNotIn("autoApprove", json.dumps(rendered))

    def test_opencode_writer_emits_verified_local_shape(self) -> None:
        machine = {
            "host": {
                "computer_name": socket.gethostname(),
                "account_name": getpass.getuser(),
            }
        }
        profile = {
            "allowed_directory": r"C:\mcp-work",
            "modules": {
                "microstation": {
                    "tier": "read",
                    "launch": {"command": "node", "args": ["bundle.mcp.js"]},
                }
            },
            "targets": {"opencode": {"output": "opencode.json"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(
                __import__("yaml").safe_dump(profile), encoding="utf-8"
            )
            machine_path.write_text(json.dumps(machine), encoding="utf-8")
            with patch("core.emit.writer_api.ROOT", root):
                self.assertEqual(
                    0,
                    emit_configs(profile_path, machine_path, ["opencode"], False),
                )
            rendered_text = (root / "opencode.json").read_text(encoding="utf-8")
            rendered = json.loads(
                "\n".join(
                    line
                    for line in rendered_text.splitlines()
                    if not line.startswith("//")
                )
            )
            self.assertNotIn("_generated", rendered)
            server = rendered["mcp"]["microstation"]
            self.assertEqual("local", server["type"])
            self.assertEqual(["node", "bundle.mcp.js"], server["command"])
            self.assertTrue(server["enabled"])

    def test_continue_writer_emits_yaml_array_and_json_fallback(self) -> None:
        machine = {
            "host": {
                "computer_name": socket.gethostname(),
                "account_name": getpass.getuser(),
            }
        }
        profile = {
            "allowed_directory": r"C:\mcp-work",
            "modules": {
                "microstation": {
                    "tier": "read",
                    "launch": {"command": "node", "args": ["bundle.mcp.js"]},
                }
            },
            "targets": {
                "continue": {
                    "output": ".continue/mcpServers/bentley.yaml",
                    "fallback_output": ".continue/bentley-mcp.fallback.json",
                }
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(
                __import__("yaml").safe_dump(profile), encoding="utf-8"
            )
            machine_path.write_text(json.dumps(machine), encoding="utf-8")
            with patch("core.emit.writer_api.ROOT", root):
                self.assertEqual(
                    0,
                    emit_configs(profile_path, machine_path, ["continue"], False),
                )
            yaml_path = root / ".continue" / "mcpServers" / "bentley.yaml"
            json_path = root / ".continue" / "bentley-mcp.fallback.json"
            yaml_text = yaml_path.read_text(encoding="utf-8")
            yaml_data = __import__("yaml").safe_load(yaml_text)
            self.assertEqual("v1", yaml_data["schema"])
            self.assertIsInstance(yaml_data["mcpServers"], list)
            self.assertEqual("microstation", yaml_data["mcpServers"][0]["name"])
            fallback = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(
                [],
                fallback["mcpServers"]["microstation"]["autoApprove"],
            )

    def test_handwritten_target_file_is_preserved(self) -> None:
        machine = {
            "host": {
                "computer_name": socket.gethostname(),
                "account_name": getpass.getuser(),
            }
        }
        profile = {
            "allowed_directory": r"C:\mcp-work",
            "modules": {
                "microstation": {
                    "tier": "read",
                    "launch": {"command": "node", "args": ["bundle.mcp.js"]},
                }
            },
            "targets": {"cursor": {"output": ".cursor/mcp.json"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / ".cursor" / "mcp.json"
            original.parent.mkdir(parents=True)
            original.write_text('{"handWritten": true}\n', encoding="utf-8")
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(
                __import__("yaml").safe_dump(profile), encoding="utf-8"
            )
            machine_path.write_text(json.dumps(machine), encoding="utf-8")
            with patch("core.emit.writer_api.ROOT", root):
                self.assertEqual(
                    0,
                    emit_configs(profile_path, machine_path, ["cursor"], False),
                )
            self.assertEqual(
                '{"handWritten": true}\n',
                original.read_text(encoding="utf-8"),
            )
            generated = root / ".cursor" / "mcp.bentley.generated.json"
            self.assertTrue(generated.is_file())

    def test_all_discovered_writers_emit_all_four_modules(self) -> None:
        machine = {
            "host": {
                "computer_name": socket.gethostname(),
                "account_name": getpass.getuser(),
            }
        }
        modules = {}
        for module_id in (
            "microstation",
            "staadpro",
            "plaxis2d-input",
            "plaxis2d-output",
        ):
            modules[module_id] = {
                "tier": "read",
                "launch": {
                    "command": f"{module_id}.exe",
                    "args": ["serve"],
                },
            }
        targets = {
            "copilot-cli": {"output": "copilot.json"},
            "vscode-copilot": {"output": "vscode.json"},
            "codex": {"output": "codex.toml"},
            "claude-code": {"output": "claude-code.json"},
            "claude-desktop": {"output": "claude-desktop.json"},
            "cline": {
                "output": "cline.json",
                "cli_output": "cline-cli.json",
            },
            "kilocode": {"output": "kilo.jsonc"},
            "cursor": {"output": "cursor.json"},
            "opencode": {"output": "opencode.json"},
            "continue": {
                "output": "continue.yaml",
                "fallback_output": "continue-fallback.json",
            },
        }
        profile = {
            "allowed_directory": r"C:\mcp-work",
            "modules": modules,
            "targets": targets,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = root / "site.yaml"
            machine_path = root / "machine.json"
            profile_path.write_text(
                __import__("yaml").safe_dump(profile), encoding="utf-8"
            )
            machine_path.write_text(json.dumps(machine), encoding="utf-8")
            with patch("core.emit.writer_api.ROOT", root):
                self.assertEqual(
                    0,
                    emit_configs(profile_path, machine_path, None, False),
                )
            for settings in targets.values():
                self.assertTrue((root / settings["output"]).is_file())
            codex = (root / "codex.toml").read_text(encoding="utf-8")
            for module_id in modules:
                self.assertIn(module_id, codex)


if __name__ == "__main__":
    unittest.main()
