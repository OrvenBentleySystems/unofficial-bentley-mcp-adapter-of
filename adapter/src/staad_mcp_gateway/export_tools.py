"""Write the gateway's exact tools/list result for pinning in the plugin manifest.

Usage: python -m staad_mcp_gateway.export_tools <output.json>
Uses an in-memory session; does not start the upstream or contact STAAD.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from fastmcp import Client

from .app import ALLOWED_TOOLS, Upstream, build_server
from .config import GatewayConfig

_DUMMY = "00000000-0000-0000-0000-000000000000"


class _NoUpstream(Upstream):
    async def start(self) -> None:  # never spawn upstream while exporting schemas
        return None


async def export(path: Path) -> None:
    cfg = GatewayConfig.from_env({"STAAD_GW_TENANT_ID": _DUMMY, "STAAD_GW_AUDIENCES": _DUMMY, "STAAD_GW_ALLOWED_OIDS": _DUMMY})
    server = build_server(cfg, _NoUpstream(1), lambda _e: None, verifier=None)
    server.auth = None  # in-memory export only; HTTP serving always uses the Entra verifier
    async with Client(server) as c:
        tools = await c.list_tools()
    names = [t.name for t in tools]
    assert sorted(names) == sorted(ALLOWED_TOOLS), names
    doc = {"tools": [t.model_dump(mode="json", exclude_none=True, by_alias=True) for t in tools]}
    for t in doc["tools"]:
        t.pop("_meta", None)
        t.pop("meta", None)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(tools)} tools to {path}: {', '.join(names)}")


if __name__ == "__main__":
    asyncio.run(export(Path(sys.argv[1])))
