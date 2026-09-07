from __future__ import annotations

from typing import Any

from core.common import AdapterError


TIERS = ("read", "guided", "full")


def _expand_guided(tiers: dict[str, Any]) -> list[str]:
    read = list(tiers.get("read") or [])
    guided = list(tiers.get("guided") or [])
    combined = read[:]
    for name in guided:
        clean = name[1:] if isinstance(name, str) and name.startswith("+") else name
        if clean not in combined:
            combined.append(clean)
    return combined


def resolve_tier(module: dict[str, Any], tier: str) -> list[str]:
    if tier not in TIERS:
        raise AdapterError(f"Unsupported capability tier '{tier}'")
    tiers = module.get("tiers")
    if not isinstance(tiers, dict):
        raise AdapterError(f"Module {module['id']} has no tier policy")
    if tier == "guided":
        tools = _expand_guided(tiers)
    else:
        tools = list(tiers.get(tier) or [])
    if tier == "full" and tools == ["*"]:
        return tools
    never = set(module.get("never_auto_approve") or [])
    if tier == "read" and never.intersection(tools):
        unsafe = ", ".join(sorted(never.intersection(tools)))
        raise AdapterError(f"Read tier for {module['id']} includes mutating tools: {unsafe}")
    return tools

