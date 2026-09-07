from __future__ import annotations

import os
import shutil
import socket
from pathlib import Path
from typing import Any

from core.common import (
    AdapterError,
    discover_target_ids,
    expand_path,
    load_json,
    load_target,
    load_yaml,
    resolve_tokens,
    utc_now,
    validate_machine_identity,
    write_json,
)


def _writable(path: Path) -> bool:
    if path.exists():
        return os.access(path, os.W_OK)
    parent = path.parent
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    return parent.is_dir() and os.access(parent, os.W_OK)


def config_paths_for_target(
    descriptor: dict[str, Any],
    profile: dict[str, Any],
    machine: dict[str, Any],
) -> list[Path]:
    paths: list[Path] = []
    settings = (profile.get("targets") or {}).get(descriptor["id"])
    if isinstance(settings, dict):
        for key, value in settings.items():
            if key == "output" or key.endswith("_output"):
                paths.append(
                    expand_path(resolve_tokens(str(value), machine, profile))
                )
    for value in (descriptor.get("config_paths") or {}).values():
        try:
            resolved = expand_path(
                resolve_tokens(str(value), machine, profile)
            )
        except AdapterError:
            continue
        if resolved not in paths:
            paths.append(resolved)
    return paths


def _provider_state(paths: list[Path]) -> str | list[str]:
    readable = False
    providers: set[str] = set()
    for path in paths:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        readable = True
        if "llamacpp" in text.casefold() or "127.0.0.1:8080" in text:
            providers.add("llamacpp")
    return sorted(providers) if readable else "unknown"


def _loopback_reachable(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.5):
            return True
    except OSError:
        return False


def detect_environment(
    profile_path: Path,
    machine_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    profile = load_yaml(profile_path.resolve())
    machine = load_json(machine_path.resolve())
    validate_machine_identity(machine)
    applications = {
        app_id: {
            "present": bool(records),
            "versions": sorted(
                {
                    str(record.get("version"))
                    for record in records
                    if record.get("version")
                }
            ),
        }
        for app_id, records in (machine.get("installations") or {}).items()
    }
    clients = []
    for target_id in discover_target_ids():
        descriptor = load_target(target_id)
        paths = config_paths_for_target(descriptor, profile, machine)
        commands = [
            command
            for command in descriptor.get("detect_commands") or []
            if shutil.which(str(command))
        ]
        present = any(path.exists() for path in paths) or bool(commands)
        preferred = next(
            (path for path in paths if path.exists()),
            paths[0] if paths else None,
        )
        status = str(
            descriptor.get("verification_status")
            or ("verified" if descriptor.get("verified") else "shape-only")
        )
        auto_eligible = bool(descriptor.get("auto_eligible")) and status == "verified"
        reason = None
        if status == "shape-only":
            reason = "shape-only target is excluded from --auto until live verification"
        elif not present:
            reason = "client was not detected"
        elif preferred is None or not _writable(preferred):
            reason = f"config path is not writable: {preferred}"
        clients.append(
            {
                "id": target_id,
                "status": status,
                "present": present,
                "auto_eligible": auto_eligible,
                "config_path": str(preferred) if preferred else None,
                "writable": bool(preferred and _writable(preferred)),
                "commands": commands,
                "providers": _provider_state(paths),
                "skip_reason": reason,
            }
        )
    local = profile.get("local_provider")
    provider_port = (
        int(local.get("port", 8080))
        if isinstance(local, dict)
        else 8080
    )
    result = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "machine_path": str(machine_path.resolve()),
        "applications": applications,
        "clients": clients,
        "local_provider": {
            "id": local.get("id") if isinstance(local, dict) else None,
            "port": provider_port,
            "reachable": _loopback_reachable(provider_port),
        },
    }
    write_json(output_path, result)
    return result


def select_auto_targets(
    detected: dict[str, Any],
    requested: str | None = None,
) -> tuple[list[str], list[dict[str, str]]]:
    selected: list[str] = []
    skipped: list[dict[str, str]] = []
    for client in detected.get("clients") or []:
        target_id = str(client.get("id"))
        if requested and target_id != requested:
            continue
        reason = client.get("skip_reason")
        if not client.get("present"):
            reason = reason or "client was not detected"
        elif not client.get("auto_eligible"):
            reason = reason or "target is not eligible for automatic emission"
        elif not client.get("writable"):
            reason = reason or f"config path is not writable: {client.get('config_path')}"
        else:
            selected.append(target_id)
            continue
        skipped.append({"id": target_id, "reason": str(reason)})
    if requested and not selected and not skipped:
        skipped.append({"id": requested, "reason": "target is absent from detected.json"})
    return selected, skipped
