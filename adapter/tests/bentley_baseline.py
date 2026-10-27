"""Live Bentley COM probe: attaches through the real server (no fakes).

Run from the adapter directory with MicroStation (or OpenBuildings with a DGN
from its active workset) running:

    uv run python tests\\bentley_baseline.py

Prints JSON. Exit code 0 only when the probe attached and a design file is
active. This is live evidence, unlike tests\\test_bentley_mcp.py.
"""

from __future__ import annotations

import asyncio
import json
import sys

from fastmcp import Client

from bentley_mcp.server import build_server


async def probe() -> dict:
    out: dict = {"ok": False}
    server = build_server()
    async with Client(server) as client:
        apps = (await client.call_tool("list_apps", {})).structured_content
        out["apps"] = apps["apps"]
        if apps["apps"]:
            status = (await client.call_tool("get_status", {})).structured_content
            out["status"] = status
            out["ok"] = bool(status.get("design_file"))
    return out


def main() -> int:
    try:
        result = asyncio.run(probe())
    except Exception as exc:  # report, never crash silently
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
