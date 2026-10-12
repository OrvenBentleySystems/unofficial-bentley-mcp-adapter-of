"""Local baseline: real MCP client -> project-owned upstream OpenSTAAD MCP (stdio).

Prints protocol negotiation, the real tools/list, and harmless status calls.
Writes nothing to STAAD; only get_status and list_instances are invoked.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def main() -> None:
    transport = StdioTransport(command=sys.executable, args=["-m", "openstaad_mcp.main"])
    async with Client(transport) as client:
        init = client.initialize_result
        out = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "protocol_version": init.protocolVersion,
            "server_info": init.serverInfo.model_dump(),
            "tools": [
                {
                    "name": t.name,
                    "annotations": t.annotations.model_dump(exclude_none=True) if t.annotations else None,
                    "input_schema": t.inputSchema,
                }
                for t in await client.list_tools()
            ],
        }
        for name in ("list_instances", "get_status"):
            res = await client.call_tool(name, {}, raise_on_error=False)
            out[name] = {"is_error": res.is_error, "structured": res.structured_content,
                         "text": [c.text for c in res.content if hasattr(c, "text")]}
        print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
