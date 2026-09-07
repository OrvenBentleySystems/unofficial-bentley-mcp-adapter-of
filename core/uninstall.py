from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.common import (
    AdapterError,
    atomic_write_text,
    enabled_modules,
    load_json,
    load_target,
    load_yaml,
    output_roots,
    validate_output_path,
)
from core.detect import config_paths_for_target


MARKER = "Generated artifact. Hand edits are overwritten."
MERGED_MARKER = "Bentley MCP Adapter generated entries. Surrounding settings are preserved."


def _uninstall_toml(
    path: Path, module_ids: set[str], profile_path: Path
) -> str:
    text = path.read_text(encoding="utf-8")
    source = f"# Source profile: {profile_path.resolve()}"
    if source not in text:
        return "skipped: generated source profile does not match"
    if MERGED_MARKER in text:
        atomic_write_text(
            path,
            text.split(f"# {MERGED_MARKER}", 1)[0].rstrip() + "\n",
        )
        return "removed merged generated MCP tables"
    if MARKER not in text:
        return "skipped: no generated-artifact header"
    for module_id in module_ids:
        pattern = (
            rf'(?ms)^\[mcp_servers\."{re.escape(module_id)}"\]\s*\n'
            r".*?(?=^\[|\Z)"
        )
        text = re.sub(pattern, "", text)
    text = re.sub(
        rf"(?m)^# (?:{re.escape(MARKER)}|Source profile:.*|Generated at:.*|Pin .*?)\r?\n",
        "",
        text,
    )
    atomic_write_text(path, text.rstrip() + "\n")
    return "removed generated MCP tables"


def _uninstall_json(
    path: Path, module_ids: set[str], profile_path: Path
) -> str:
    text = path.read_text(encoding="utf-8")
    if MARKER not in text and MERGED_MARKER not in text:
        return "skipped: no generated-artifact header"
    json_text = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )
    data = json.loads(json_text)
    metadata = data.get("_generated")
    if (
        not isinstance(metadata, dict)
        or metadata.get("source_profile") != str(profile_path.resolve())
    ):
        return "skipped: generated source profile does not match"
    for root_key in ("mcpServers", "servers", "mcp"):
        servers = data.get(root_key)
        if isinstance(servers, dict):
            for module_id in module_ids:
                servers.pop(module_id, None)
    data.pop("_generated", None)
    if set(data).issubset({"mcpServers", "servers", "mcp"}) and all(
        not value for value in data.values()
    ):
        path.unlink()
        return "deleted generated-only config"
    atomic_write_text(
        path,
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
    )
    return "removed generated MCP entries"


def uninstall_generated(
    profile_path: Path,
    detected_path: Path,
) -> list[dict[str, str]]:
    profile = load_yaml(profile_path.resolve())
    detected = load_json(detected_path.resolve())
    machine_path = detected.get("machine_path")
    if not machine_path:
        raise AdapterError("detected.json has no machine_path")
    machine = load_json(Path(str(machine_path)))
    roots = output_roots(profile, machine, profile_path)
    module_ids = {module["id"] for module in enabled_modules(profile)}
    results = []
    for client in detected.get("clients") or []:
        raw_path = client.get("config_path")
        if not raw_path:
            continue
        path = Path(str(raw_path))
        if not path.is_file():
            continue
        descriptor = load_target(str(client.get("id")))
        known_paths = config_paths_for_target(descriptor, profile, machine)
        if path.resolve(strict=False) not in {
            known.resolve(strict=False) for known in known_paths
        }:
            raise AdapterError(
                f"Detected config path is not declared by target "
                f"{descriptor['id']}: {path}"
            )
        path = validate_output_path(path, roots)
        try:
            if path.suffix.casefold() == ".toml":
                action = _uninstall_toml(path, module_ids, profile_path)
            elif path.suffix.casefold() in {".json", ".jsonc"}:
                action = _uninstall_json(path, module_ids, profile_path)
            elif path.suffix.casefold() in {".yaml", ".yml"}:
                text = path.read_text(encoding="utf-8")
                source = f"# Source profile: {profile_path.resolve()}"
                if text.startswith(f"# {MARKER}") and source in text:
                    path.unlink()
                    action = "deleted generated YAML block"
                else:
                    action = "skipped: no generated-artifact header"
            else:
                action = "skipped: unsupported file type"
        except (OSError, json.JSONDecodeError) as exc:
            raise AdapterError(f"Could not uninstall {path}: {exc}") from exc
        results.append({"client": str(client.get("id")), "path": str(path), "action": action})
    return results
