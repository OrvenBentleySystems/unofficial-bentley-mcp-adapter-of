from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType
from typing import Any

from core.common import (
    AdapterError,
    enabled_modules,
    enforce_local_provider_tier,
    load_json,
    load_provider,
    load_yaml,
    output_roots,
    utc_now,
    validate_machine_identity,
    validate_safe_profile,
)
from core.emit.emitter import _write_artifact
from core.emit.writer_api import RenderedArtifact
from core.provider_api import ProviderContext


def _load_provider_plugin(provider: dict[str, Any]) -> ModuleType:
    provider_id = str(provider["id"])
    path = Path(str(provider["_directory"])) / "writer.py"
    module_name = "_bentley_adapter_provider_" + "".join(
        character if character.isalnum() else "_"
        for character in provider_id
    )
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AdapterError(f"Cannot load provider plugin: {path}")
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)
    return plugin


def emit_provider_configs(
    profile_path: Path,
    machine_path: Path,
    provider_id: str,
    port: int | None,
    alias: str | None,
    dry_run: bool,
) -> int:
    profile_path = profile_path.resolve()
    profile = load_yaml(profile_path)
    validate_safe_profile(profile)
    machine = load_json(machine_path.resolve())
    validate_machine_identity(machine)
    descriptor = load_provider(provider_id)
    configured = profile.get("local_provider")
    configured = configured if isinstance(configured, dict) else {}
    if configured.get("id") not in (None, provider_id):
        raise AdapterError("Configured local provider id does not match --provider")
    configured_port = configured.get("port")
    configured_alias = configured.get("alias")
    if port is not None and configured_port is not None and int(port) != int(configured_port):
        raise AdapterError("--port does not match local_provider.port")
    if alias and configured_alias and alias != configured_alias:
        raise AdapterError("--alias does not match local_provider.alias")
    effective_port = int(
        port
        if port is not None
        else configured_port
        if configured_port is not None
        else descriptor["default_port"]
    )
    effective_alias = str(alias or configured_alias or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", effective_alias):
        raise AdapterError(
            "Provider alias must use 1-128 letters, digits, dot, underscore, colon, or hyphen"
        )
    effective_host = str(
        configured.get("host", descriptor["default_host"])
    ).casefold()
    if effective_host not in {"127.0.0.1", "::1", "localhost"}:
        raise AdapterError("Local provider host must be loopback")
    modules = enabled_modules(profile)
    provider_profile = dict(profile)
    provider_profile["local_provider"] = {
        "id": provider_id,
        "port": effective_port,
        "alias": effective_alias,
    }
    enforce_local_provider_tier(provider_profile, modules)
    plugin = _load_provider_plugin(descriptor)
    if not callable(getattr(plugin, "render", None)):
        raise AdapterError(
            f"Provider plugin {provider_id} has no render(context) function"
        )
    context = ProviderContext(
        provider_id=provider_id,
        descriptor=descriptor,
        profile_path=profile_path,
        profile=profile,
        machine=machine,
        settings={
            "host": effective_host,
            "port": effective_port,
            "alias": effective_alias,
        },
        generated_at=utc_now(),
    )
    artifacts = plugin.render(context)
    if not isinstance(artifacts, list) or not all(
        isinstance(artifact, RenderedArtifact) for artifact in artifacts
    ):
        raise AdapterError(
            f"Provider plugin {provider_id} must return list[RenderedArtifact]"
        )
    if not artifacts:
        raise AdapterError(f"Provider plugin {provider_id} returned no artifacts")
    roots = output_roots(profile, machine, profile_path)
    for artifact in artifacts:
        _write_artifact(artifact, dry_run, allowed_roots=roots)
    return 0


def run_provider_preflight(profile: dict[str, Any]) -> dict[str, Any] | None:
    settings = profile.get("local_provider")
    if not isinstance(settings, dict):
        return None
    provider_id = str(settings.get("id") or "")
    if not provider_id:
        raise AdapterError("local_provider.id is required")
    descriptor = load_provider(provider_id)
    enforce_local_provider_tier(profile, enabled_modules(profile))
    plugin = _load_provider_plugin(descriptor)
    if not callable(getattr(plugin, "preflight", None)):
        raise AdapterError(
            f"Provider plugin {provider_id} has no preflight(settings) function"
        )
    return plugin.preflight(settings, descriptor)
