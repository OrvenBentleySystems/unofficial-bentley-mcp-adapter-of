from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.common import AdapterError, ROOT, lexical_path, resolve_tokens
from core.tiers import resolve_tier


@dataclass(frozen=True)
class RenderedArtifact:
    path: Path
    content: str
    post_write_note: str | None = None
    merge_kind: str | None = None
    merge_root: str | None = None


@dataclass(frozen=True)
class TargetContext:
    target_id: str
    descriptor: dict[str, Any]
    settings: dict[str, Any]
    profile_path: Path
    profile: dict[str, Any]
    machine: dict[str, Any]
    modules: list[dict[str, Any]]
    generated_at: str

    def output_path(self, setting: str = "output") -> Path:
        value = self.settings.get(setting)
        if not value:
            raise AdapterError(
                f"Profile has no {setting} path for target {self.target_id}"
            )
        resolved = resolve_tokens(str(value), self.machine, self.profile)
        return lexical_path(resolved, base=ROOT)


def _site_launch(module: dict[str, Any]) -> dict[str, Any]:
    override = module["_site"].get("launch")
    launch = override if isinstance(override, dict) else module["server"]["launch"]
    if not isinstance(launch, dict) or not launch.get("command"):
        raise AdapterError(f"Module {module['id']} has no launch command")
    return launch


def _secret_reference(value: Any, inputs: dict[str, dict[str, Any]]) -> Any:
    if isinstance(value, list):
        return [_secret_reference(item, inputs) for item in value]
    if isinstance(value, dict):
        if set(value) == {"secret"}:
            secret_id = str(value["secret"])
            inputs.setdefault(
                secret_id,
                {
                    "type": "promptString",
                    "description": f"Secret for {secret_id}",
                    "password": True,
                },
            )
            return f"${{input:{secret_id}}}"
        return {key: _secret_reference(item, inputs) for key, item in value.items()}
    return value


def server_entries(
    context: TargetContext,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    inputs: dict[str, dict[str, Any]] = {}
    servers: dict[str, dict[str, Any]] = {}
    for module in context.modules:
        launch = resolve_tokens(_site_launch(module), context.machine, context.profile)
        command = launch.get("command")
        if command in (None, "", "None"):
            raise AdapterError(f"Cannot resolve launch command for {module['id']}")
        entry: dict[str, Any] = {
            "command": command,
            "args": launch.get("args") or [],
        }
        if context.descriptor.get("requires_type"):
            entry["type"] = str(context.descriptor["type_value"])
        env = _secret_reference(launch.get("env") or {}, inputs)
        if env:
            entry["env"] = env
        if context.descriptor.get("supports_tool_allowlist"):
            tier = str(module["_site"].get("tier", "read"))
            entry["tools"] = resolve_tier(module, tier)
        servers[module["id"]] = entry
    if inputs and not context.descriptor.get("supports_inputs"):
        raise AdapterError(
            f"Target {context.target_id} cannot express secret input references; "
            "remove them or use a supported target"
        )
    return servers, inputs


def generated_metadata(context: TargetContext) -> dict[str, Any]:
    return {
        "notice": "Generated artifact. Hand edits are overwritten.",
        "source_profile": str(context.profile_path.resolve()),
        "generated_at": context.generated_at,
        "pins": {
            module["id"]: {
                "descriptor": module["version"],
                "server": module["server"]["pinned"],
                "application": module["requires"]["verified_version"],
            }
            for module in context.modules
        },
        "capability_tiers": {
            module["id"]: module["_site"].get("tier", "read")
            for module in context.modules
        },
        "target_verified": bool(
            context.descriptor.get(
                "legacy_target_verified",
                context.descriptor.get("verified"),
            )
        ),
    }


def render_standard_json(context: TargetContext) -> list[RenderedArtifact]:
    servers, inputs = server_entries(context)
    output: dict[str, Any] = {
        "_generated": generated_metadata(context),
        str(context.descriptor["root_key"]): servers,
    }
    if context.descriptor.get("supports_inputs") and inputs:
        output["inputs"] = [
            {"id": key, **value} for key, value in sorted(inputs.items())
        ]
    content = json.dumps(output, indent=2, ensure_ascii=False) + "\n"
    return [RenderedArtifact(path=context.output_path(), content=content)]
