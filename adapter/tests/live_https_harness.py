"""HTTPS path harness: real gateway code + REAL upstream OpenSTAAD MCP + real dev tunnel.

AUTH SUBSTITUTED: tokens are signed by an ephemeral in-memory RSA key instead of
Microsoft Entra (the Enterprise token store is only reachable from Copilot). Every
other layer is production code. Proves HTTPS transport, MCP negotiation,
discovery, forwarding, allowlist and identity checks. It is NOT hosted-agent evidence.

Usage (env STAAD_GW_TENANT_ID, STAAD_GW_ALLOWED_OIDS set; gateway stopped; tunnel hosted):
    python tests/live_https_harness.py <public_https_mcp_url> <port>
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

import httpx
import uvicorn
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server.auth.providers.jwt import RSAKeyPair

from staad_mcp_gateway.app import Upstream, build_app
from staad_mcp_gateway.auth import EntraUserVerifier
from staad_mcp_gateway.config import GatewayConfig

# Read from the environment (.env.local values); never hardcode tenant/user identifiers.
TENANT = os.environ["STAAD_GW_TENANT_ID"]
AUD = "api://staad-assistant-harness"
OID = os.environ["STAAD_GW_ALLOWED_OIDS"].split(",")[0].strip()
STORE = "ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b"


def tok(key, oid=OID):
    return key.create_token(subject=oid, issuer=f"https://login.microsoftonline.com/{TENANT}/v2.0", audience=AUD,
                            additional_claims={"tid": TENANT, "oid": oid, "scp": "access_as_user", "azp": STORE,
                                               "preferred_username": "harness"})


async def main(url: str, port: int) -> None:
    key = RSAKeyPair.generate()
    cfg = GatewayConfig.from_env({"STAAD_GW_TENANT_ID": TENANT, "STAAD_GW_AUDIENCES": AUD,
                                  "STAAD_GW_ALLOWED_OIDS": OID, "STAAD_GW_PORT": str(port)})
    audit: list[dict] = []
    app, _ = build_app(cfg, Upstream(30), audit.append, EntraUserVerifier(cfg, public_key=key.public_key))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.1)
    out: dict = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "url": url,
                 "auth": "SUBSTITUTED (ephemeral test key)", "upstream": "REAL OpenSTAAD MCP v1.3.0 stdio"}
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25",
                    "capabilities": {}, "clientInfo": {"name": "harness", "version": "0"}}}
            h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
            for label, extra in [("no_token", {}), ("garbage_token", {"Authorization": "Bearer abc.def.ghi"}),
                                 ("other_key", {"Authorization": f"Bearer {tok(RSAKeyPair.generate())}"}),
                                 ("other_user", {"Authorization": "Bearer " + tok(key, "00000000-0000-0000-0000-000000000001")})]:
                r = await http.post(url, json=init, headers={**h, **extra})
                out[f"https_{label}"] = r.status_code
            r = await http.get(url.rsplit("/mcp", 1)[0] + "/", headers=h)
            out["https_root_path"] = r.status_code
        async with Client(StreamableHttpTransport(url, headers={"Authorization": f"Bearer {tok(key)}"})) as c:
            out["protocol_version"] = c.initialize_result.protocolVersion
            out["server_info"] = c.initialize_result.serverInfo.name
            out["tools"] = [t.name for t in await c.list_tools()]
            for name, args in [("list_instances", {}), ("get_status", {}), ("get_model_summary", {}),
                               ("execute_code", {"code": "staad.GetBaseUnit()"}), ("discover_api", {})]:
                res = await c.call_tool(name, args, raise_on_error=False)
                out[f"call_{name}"] = {"is_error": res.is_error,
                                        "data": res.structured_content if not res.is_error else
                                        " ".join(getattr(x, "text", "") for x in res.content)[:200]}
    finally:
        server.should_exit = True
        await task
    out["audit"] = audit
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], int(sys.argv[2])))
