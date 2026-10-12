"""STAAD MCP gateway: authenticated, allowlisted front for the upstream OpenSTAAD MCP.

Only these tools exist on the gateway (anything else is "unknown tool"):
  * list_instances     - pass-through to upstream ``list_instances``
  * get_status         - pass-through to upstream ``get_status``
  * get_model_summary  - ADAPTER tool: runs one fixed, getter-only OpenSTAAD
                         snippet through upstream ``execute_code``. It accepts
                         no code, paths or file arguments from the caller.

Upstream ``execute_code``, ``discover_api`` and ``read_skills`` are never exposed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated, Any

import uvicorn
from fastmcp import Client, FastMCP
from fastmcp.client.transports import StdioTransport
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import Middleware, MiddlewareContext
from mcp.types import ToolAnnotations
from pydantic import Field

from .auth import EntraUserVerifier
from .config import ConfigError, GatewayConfig

log = logging.getLogger("staad_mcp_gateway")

ALLOWED_TOOLS = ("list_instances", "get_status", "get_model_summary")

# Fixed, getter-only OpenSTAAD calls (verified against upstream staad-core,
# staad-geometry, staad-loading and staad-results skills). Never parameterised.
MODEL_SUMMARY_CODE = """\
geo = staad.Geometry
load = staad.Load
result = {
    "model_path": staad.GetSTAADFile(),
    "base_unit": staad.GetBaseUnit(),
    "node_count": geo.GetNodeCount(),
    "member_count": geo.GetMemberCount(),
    "plate_count": geo.GetPlateCount(),
    "primary_load_case_count": load.GetPrimaryLoadCaseCount(),
    "load_combination_count": load.GetLoadCombinationCaseCount(),
    "results_available": staad.Output.AreResultsAvailable(),
}
"""

InstanceAlias = Annotated[
    str | None,
    Field(
        default=None,
        pattern=r"^staadPro[0-9]{1,4}$",
        description="Instance alias returned by list_instances (e.g. staadPro1). Omit only when exactly one instance is running.",
    ),
]

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=False, openWorldHint=False)


class Upstream:
    """Persistent MCP client session to a project-owned upstream stdio child.

    A single long-lived session keeps upstream instance aliases stable.
    """

    def __init__(self, timeout_s: float, client_factory=None):
        self._timeout_s = timeout_s
        self._client: Client | None = None
        self._lock = asyncio.Lock()
        self._factory = client_factory or self._stdio_client

    def _stdio_client(self) -> Client:
        # Fixed command: the upstream from this project's pinned environment. No configurable URL.
        transport = StdioTransport(command=sys.executable, args=["-m", "openstaad_mcp.main"], keep_alive=True)
        return Client(transport, timeout=self._timeout_s, init_timeout=60)

    def _new_client(self) -> Client:
        return self._factory()

    async def start(self) -> None:
        async with self._lock:
            if self._client is None or not self._client.is_connected():
                self._client = self._new_client()
                await self._client.__aenter__()
                tools = {t.name for t in await self._client.list_tools()}
                missing = {"list_instances", "get_status", "execute_code"} - tools
                if missing:
                    raise RuntimeError(f"Upstream OpenSTAAD MCP is missing required tools: {sorted(missing)}")
                log.info("upstream_ready protocol=%s tools=%s", self._client.initialize_result.protocolVersion, sorted(tools))

    async def stop(self) -> None:
        async with self._lock:
            if self._client is not None:
                try:
                    await self._client.__aexit__(None, None, None)
                finally:
                    self._client = None

    async def call(self, name: str, args: dict[str, Any]) -> Any:
        for attempt in (1, 2):
            try:
                await self.start()
                res = await self._client.call_tool(name, args, raise_on_error=False)
                break
            except Exception as exc:  # transport failure: restart child once
                log.warning("upstream_call_failed tool=%s attempt=%d error=%s", name, attempt, type(exc).__name__)
                await self.stop()
                if attempt == 2:
                    raise ToolError(f"OpenSTAAD MCP upstream unavailable: {type(exc).__name__}") from exc
        if res.is_error:
            text = " ".join(getattr(c, "text", "") for c in res.content).strip()
            raise ToolError(f"Upstream {name} error: {text or 'unknown error'}")
        if res.structured_content is not None:
            sc = res.structured_content
            # FastMCP wraps non-object results as {"result": ...}
            return sc["result"] if set(sc) == {"result"} else sc
        text = " ".join(getattr(c, "text", "") for c in res.content)
        return json.loads(text)


class AuditMiddleware(Middleware):
    """One JSON line per MCP request: who, what, outcome. Never logs tokens or arguments' values."""

    def __init__(self, sink):
        self._sink = sink

    async def on_request(self, context: MiddlewareContext, call_next):
        rid = uuid.uuid4().hex[:12]
        start = time.perf_counter()
        token = get_access_token()
        claims = (token.claims or {}) if token else {}
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "rid": rid,
            "method": context.method,
            "oid": claims.get("oid"),
            "upn": claims.get("preferred_username") or claims.get("upn"),
            "appid": claims.get("azp") or claims.get("appid"),
        }
        if context.method == "tools/call":
            entry["tool"] = getattr(context.message, "name", None)
            entry["arg_keys"] = sorted((getattr(context.message, "arguments", None) or {}).keys())
        try:
            result = await call_next(context)
            entry["outcome"] = "ok"
            if context.method == "tools/call" and getattr(result, "is_error", False):
                entry["outcome"] = "tool_error"
            return result
        except Exception as exc:
            entry["outcome"] = f"error:{type(exc).__name__}"
            raise
        finally:
            entry["ms"] = round((time.perf_counter() - start) * 1000, 1)
            self._sink(entry)


class BodyLimitMiddleware:
    """Pure-ASGI request body cap (applies before auth parsing)."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        cl = headers.get(b"content-length")
        if cl is not None and (not cl.isdigit() or int(cl) > self.max_bytes):
            return await _plain(send, 413, b"Request body too large")
        seen = 0

        async def limited_receive():
            nonlocal seen
            msg = await receive()
            if msg["type"] == "http.request":
                seen += len(msg.get("body", b""))
                if seen > self.max_bytes:
                    raise _BodyTooLarge()
            return msg

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await _plain(send, 413, b"Request body too large")


class _BodyTooLarge(Exception):
    pass


async def _plain(send, status: int, body: bytes) -> None:
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"text/plain"), (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})


def build_server(cfg: GatewayConfig, upstream: Upstream, audit_sink, verifier=None) -> FastMCP:
    @asynccontextmanager
    async def lifespan(_server):
        try:
            await upstream.start()
        except Exception as exc:  # keep serving; calls retry and report the failure honestly
            log.error("upstream_start_failed error=%s: %s", type(exc).__name__, exc)
        try:
            yield
        finally:
            await upstream.stop()

    mcp = FastMCP(
        "STAAD MCP Gateway",
        instructions="Read-only STAAD.Pro runtime status via the OpenSTAAD MCP server.",
        auth=verifier if verifier is not None else EntraUserVerifier(cfg),
        lifespan=lifespan,
    )
    mcp.add_middleware(AuditMiddleware(audit_sink))

    @mcp.tool(annotations=READ_ONLY)
    async def list_instances() -> list[dict[str, Any]]:
        """List all running STAAD.Pro instances (upstream OpenSTAAD tool).

        Returns alias, process ID, currently open file path and STAAD version
        for each instance. Aliases (e.g. staadPro1) are stable while the gateway runs.
        """
        return await upstream.call("list_instances", {})

    @mcp.tool(annotations=READ_ONLY)
    async def get_status(instance: InstanceAlias = None) -> dict[str, Any]:
        """Check the live connection to a STAAD.Pro instance (upstream OpenSTAAD tool).

        Returns connected flag, STAAD version, model path, alias and whether an
        analysis is running. Pass ``instance`` (alias from list_instances) when
        more than one instance is running.
        """
        args = {} if instance is None else {"instance": instance}
        return await upstream.call("get_status", args)

    @mcp.tool(annotations=READ_ONLY)
    async def get_model_summary(instance: InstanceAlias = None) -> dict[str, Any]:
        """Read a fixed, read-only summary of the open STAAD.Pro model (gateway adapter tool).

        Returns model path, base unit system, node/member/plate counts, primary
        load case and load combination counts, and whether analysis results are
        available. Implemented by the gateway via a fixed getter-only OpenSTAAD
        snippet; it is not an upstream Bentley tool and accepts no code.
        """
        args: dict[str, Any] = {"code": MODEL_SUMMARY_CODE}
        if instance is not None:
            args["instance"] = instance
        res = await upstream.call("execute_code", args)
        if not isinstance(res, dict) or not res.get("success"):
            err = res.get("error") if isinstance(res, dict) else "unexpected upstream response"
            raise ToolError(f"Model summary failed: {err}")
        out = dict(res["result"])
        out["instance"] = instance
        if res.get("warning"):
            out["warning"] = res["warning"]
        return out

    return mcp


def build_app(cfg: GatewayConfig, upstream: Upstream, audit_sink, verifier=None):
    mcp = build_server(cfg, upstream, audit_sink, verifier)
    app = mcp.http_app(path="/mcp", stateless_http=True)
    return BodyLimitMiddleware(app, cfg.max_body_bytes), app


def _file_sink(cfg: GatewayConfig):
    cfg.log_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.log_dir / f"audit-{datetime.now(timezone.utc):%Y%m%d}.jsonl"

    def sink(entry: dict[str, Any]) -> None:
        line = json.dumps(entry, separators=(",", ":"))
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        log.info("audit %s", line)

    return sink


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s - %(message)s", stream=sys.stderr)
    try:
        cfg = GatewayConfig.from_env()
    except (ConfigError, ValueError) as exc:
        log.error("configuration error: %s", exc)
        sys.exit(2)
    upstream = Upstream(cfg.upstream_timeout_s)
    app, _ = build_app(cfg, upstream, _file_sink(cfg))
    log.info("gateway listening on http://127.0.0.1:%d/mcp tools=%s", cfg.port, ",".join(ALLOWED_TOOLS))
    uvicorn.run(app, host="127.0.0.1", port=cfg.port, log_level="warning", timeout_keep_alive=15,
                limit_concurrency=32, proxy_headers=False, server_header=False)


if __name__ == "__main__":
    main()
