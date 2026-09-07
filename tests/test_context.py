from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from core.context import emit_context


class ContextTests(unittest.TestCase):
    def _detected(self) -> dict:
        return {
            "clients": [
                {
                    "id": "copilot-cli",
                    "present": True,
                    "auto_eligible": True,
                    "writable": True,
                },
                {
                    "id": "vscode-copilot",
                    "present": True,
                    "auto_eligible": True,
                    "writable": True,
                },
                {
                    "id": "cline",
                    "present": True,
                    "auto_eligible": True,
                    "writable": True,
                },
            ]
        }

    def test_auto_deduplicates_shared_instruction_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = root / "site.yaml"
            detected_path = root / "detected.json"
            machine_path = root / "machine.json"
            profile_path.write_text(
                yaml.safe_dump({"workspace_root": str(root)}),
                encoding="utf-8",
            )
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
            detected = self._detected()
            detected["machine_path"] = str(machine_path)
            detected_path.write_text(
                json.dumps(detected), encoding="utf-8"
            )
            written = emit_context(
                profile_path, detected_path, auto=True
            )
            self.assertEqual(2, len(written))
            copilot = root / ".github" / "copilot-instructions.md"
            cline = root / ".clinerules" / "bentley-mcp.md"
            self.assertTrue(copilot.is_file())
            self.assertTrue(cline.is_file())
            self.assertEqual(
                copilot.read_text(encoding="utf-8"),
                cline.read_text(encoding="utf-8"),
            )

    def test_handwritten_instruction_file_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile_path = root / "site.yaml"
            detected_path = root / "detected.json"
            machine_path = root / "machine.json"
            existing = root / ".github" / "copilot-instructions.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("hand written\n", encoding="utf-8")
            profile_path.write_text(
                yaml.safe_dump({"workspace_root": str(root)}),
                encoding="utf-8",
            )
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
            detected_path.write_text(
                json.dumps(
                    {
                        "machine_path": str(machine_path),
                        "clients": [
                            {
                                "id": "copilot-cli",
                                "present": True,
                                "auto_eligible": True,
                                "writable": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            emit_context(profile_path, detected_path, auto=True)
            self.assertEqual("hand written\n", existing.read_text(encoding="utf-8"))
            sibling = (
                root
                / ".github"
                / "copilot-instructions.bentley.generated.md"
            )
            self.assertTrue(sibling.is_file())


if __name__ == "__main__":
    unittest.main()
