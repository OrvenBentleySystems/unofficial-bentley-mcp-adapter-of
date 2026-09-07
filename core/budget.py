from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from core.common import AdapterError, enabled_modules, load_target, load_yaml
from core.tiers import resolve_tier


def _tool_count(module: dict[str, Any], tier: str) -> int:
    tools = resolve_tier(module, tier)
    if tools != ["*"]:
        return len(tools)
    inventory = module.get("inventory") or {}
    count = inventory.get("verified_count")
    if not isinstance(count, int) or count < 1:
        raise AdapterError(
            f"Module {module['id']} has no verified full-tier tool count"
        )
    return count


def calculate_budget(
    profile_path: Path, tier: str, client_id: str
) -> dict[str, Any]:
    profile = load_yaml(profile_path.resolve())
    target = load_target(client_id)
    modules = enabled_modules(profile)
    counts = {
        module["id"]: _tool_count(module, tier)
        for module in modules
    }
    tool_count = sum(counts.values())
    allowlist_enforced = bool(target.get("supports_tool_allowlist"))
    exposed_tool_count = (
        tool_count
        if allowlist_enforced
        else sum(_tool_count(module, "full") for module in modules)
    )
    estimated_characters = sum(
        count * (200 + len(module_id))
        for module_id, count in counts.items()
    )
    return {
        "client": client_id,
        "tier": tier,
        "modules": counts,
        "tool_count": tool_count,
        "exposed_tool_count": exposed_tool_count,
        "estimated_schema_tokens": math.ceil(estimated_characters / 4),
        "estimate_method": (
            "200 schema characters plus module-id length per declared tool, "
            "divided by four"
        ),
        "client_allowlist_enforced": allowlist_enforced,
    }
