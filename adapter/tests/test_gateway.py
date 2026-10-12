"""Unit tests for gateway authentication, tool policy and forwarding.

MOCKED: the upstream OpenSTAAD server is replaced by an in-memory FastMCP
server and tokens are signed by a local test key. These tests prove gateway
logic only and are NOT live integration evidence.
"""

from __future__ import annotations

import asyncio
import socket

import httpx
import pytest
import uvicorn
from fastmcp import Client, FastMCP
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server.auth.providers.jwt import RSAKeyPair

from staad_mcp_gateway.app import ALLOWED_TOOLS, MODEL_SUMMARY_CODE, Upstream, build_app
from staad_mcp_gateway.auth import EntraUserVerifier
from staad_mcp_gateway.config import ConfigError, GatewayConfig

TENANT = "11111111-1111-1111-1111-111111111111"
OTHER_TENANT = "22222222-2222-2222-2222-222222222222"
APP_ID = "33333333-3333-3333-3333-333333333333"
USER_OID = "44444444-4444-4444-4444-444444444444"
OTHER_OID = "55555555-5555-5555-5555-555555555555"
ISS = f"https://login.microsoftonline.com/{TENANT}/v2.0"

KEY = RSAKeyPair.generate()
WRONG_KEY = RSAKeyPair.generate()


def make_cfg() -> GatewayConfig:
    return GatewayConfig.from_env({
        "STAAD_GW_TENANT_ID": TENANT,
        "STAAD_GW_AUDIENCES": f"{APP_ID},api://staad-test/{APP_ID}",
        "STAAD_GW_ALLOWED_OIDS": USER_OID,
        "STAAD_GW_MAX_BODY_BYTES": "4096",
    })


def token(key=KEY, *, iss=ISS, aud=APP_ID, tid=TENANT, oid=USER_OID, scp="access_as_user", exp=3600,
          azp="ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b", extra=None):
    claims = {"tid": tid, "oid": oid, "preferred_username": "dev@example.test", "azp": azp}
    if scp is not None:
        claims["scp"] = scp
    claims.update(extra or {})
    return key.create_token(subject=oid, issuer=iss, audience=aud, expires_in_seconds=exp, additional_claims=claims)


class FakeUpstream:
    """In-memory stand-in for OpenSTAAD MCP exposing the same tool names."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        srv = FastMCP("fake-openstaad")

        @srv.tool
        def list_instances() -> list[dict]:
            self.calls.append(("list_instances", {}))
            return [{"alias": "staadPro1", "pid": 1, "file_path": "c:\\m.std", "version": "x"}]

        @srv.tool
        def get_status(instance: str | None = None) -> dict:
            self.calls.append(("get_status", {"instance": instance}))
            return {"connected": True, "alias": instance or "staadPro1"}

        @srv.tool
        def execute_code(code: str, instance: str | None = None) -> dict:
            self.calls.append(("execute_code", {"code": code, "instance": instance}))
            return {"success": True, "result": {"node_count": 3}, "error": None}

        @srv.tool
        def discover_api() -> str:
            self.calls.append(("discover_api", {}))
            return "skills"

        self.server = srv


@pytest.fixture
async def gateway():
    cfg = make_cfg()
    fake = FakeUpstream()
    audit: list[dict] = []
    verifier = EntraUserVerifier(cfg, public_key=KEY.public_key)
    app, _ = build_app(cfg, Upstream(5, client_factory=lambda: Client(fake.server)), audit.append, verifier)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp", fake, audit
    server.should_exit = True
    await task


def client(url, tok):
    return Client(StreamableHttpTransport(url, headers={"Authorization": f"Bearer {tok}"}))


INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
HDRS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


@pytest.mark.parametrize("auth", [
    None,
    "Bearer not-a-jwt",
    "Bearer " + token(WRONG_KEY),
    "Bearer " + token(aud="api://someone-else"),
    "Bearer " + token(iss=f"https://login.microsoftonline.com/{OTHER_TENANT}/v2.0"),
    "Bearer " + token(tid=OTHER_TENANT),
    "Bearer " + token(oid=OTHER_OID),
    "Bearer " + token(scp="User.Read"),
    "Bearer " + token(scp=None),
    "Bearer " + token(exp=-600),
    "Bearer " + token(azp="66666666-6666-6666-6666-666666666666"),
])
async def test_rejects_missing_or_invalid_credentials(gateway, auth):
    url, fake, _ = gateway
    headers = dict(HDRS)
    if auth:
        headers["Authorization"] = auth
    async with httpx.AsyncClient() as http:
        r = await http.post(url, json=INIT, headers=headers)
    assert r.status_code == 401
    assert "www-authenticate" in r.headers
    assert fake.calls == []


async def test_valid_token_lists_only_allowlisted_tools(gateway):
    url, _, audit = gateway
    async with client(url, token()) as c:
        names = sorted(t.name for t in await c.list_tools())
        tools = {t.name: t for t in await c.list_tools()}
    assert names == sorted(ALLOWED_TOOLS)
    assert all(t.annotations.readOnlyHint for t in tools.values())
    assert any(e["method"] == "tools/list" and e["oid"] == USER_OID for e in audit)


async def test_accepts_v1_issuer_and_app_id_uri_audience(gateway):
    url, _, _ = gateway
    tok = token(iss=f"https://sts.windows.net/{TENANT}/", aud=f"api://staad-test/{APP_ID}")
    async with client(url, tok) as c:
        assert await c.call_tool("get_status", {})


@pytest.mark.parametrize("tool,args", [
    ("execute_code", {"code": "staad.Quit()"}),
    ("discover_api", {}),
    ("read_skills", {"skills": ["staad-core"]}),
])
async def test_disallowed_tool_invocation_rejected(gateway, tool, args):
    url, fake, audit = gateway
    async with client(url, token()) as c:
        res = await c.call_tool(tool, args, raise_on_error=False)
    assert res.is_error
    assert fake.calls == []
    assert audit[-1]["tool"] == tool and audit[-1]["outcome"] != "ok"


async def test_status_and_list_forward_to_upstream(gateway):
    url, fake, _ = gateway
    async with client(url, token()) as c:
        inst = (await c.call_tool("list_instances", {})).structured_content
        st = (await c.call_tool("get_status", {"instance": "staadPro1"})).structured_content
    assert inst["result"][0]["alias"] == "staadPro1"
    assert st == {"connected": True, "alias": "staadPro1"}
    assert fake.calls == [("list_instances", {}), ("get_status", {"instance": "staadPro1"})]


async def test_model_summary_sends_only_fixed_code(gateway):
    url, fake, _ = gateway
    async with client(url, token()) as c:
        injected = await c.call_tool("get_model_summary", {"instance": "staadPro1", "code": "staad.Quit()"},
                                     raise_on_error=False)
        bad = await c.call_tool("get_model_summary", {"instance": "x'); staad.Quit() #"}, raise_on_error=False)
        ok = await c.call_tool("get_model_summary", {"instance": "staadPro1"})
    # Caller-supplied code and malformed aliases are rejected before anything reaches upstream.
    assert injected.is_error and bad.is_error
    assert fake.calls == [("execute_code", {"code": MODEL_SUMMARY_CODE, "instance": "staadPro1"})]
    assert ok.structured_content["node_count"] == 3


async def test_oversized_body_rejected(gateway):
    url, fake, _ = gateway
    headers = dict(HDRS, Authorization=f"Bearer {token()}")
    async with httpx.AsyncClient() as http:
        r = await http.post(url, content=b"{" + b" " * 8000 + b"}", headers=headers)
    assert r.status_code == 413
    assert fake.calls == []


@pytest.mark.parametrize("env", [
    {},
    {"STAAD_GW_TENANT_ID": "common", "STAAD_GW_AUDIENCES": APP_ID, "STAAD_GW_ALLOWED_OIDS": USER_OID},
    {"STAAD_GW_TENANT_ID": TENANT, "STAAD_GW_AUDIENCES": "", "STAAD_GW_ALLOWED_OIDS": USER_OID},
    {"STAAD_GW_TENANT_ID": TENANT, "STAAD_GW_AUDIENCES": APP_ID, "STAAD_GW_ALLOWED_OIDS": "*"},
])
def test_config_fails_closed(env):
    with pytest.raises(ConfigError):
        GatewayConfig.from_env(env)
