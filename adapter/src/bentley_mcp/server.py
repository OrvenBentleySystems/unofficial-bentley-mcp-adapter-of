"""Bentley MCP server: typed local control of MicroStation and OpenBuildings.

Default transport is stdio, for an agent to launch this process directly.
``--http`` serves streamable HTTP on 127.0.0.1 only; set ``BENTLEY_MCP_TOKEN``
to require ``Authorization: Bearer <token>``.

The typed tools cover the DGN object model through COM. Arbitrary execution
exists only behind ``run_keyin`` and ``run_python``, both requiring
``confirm=true``. No Bentley Copilot dependency: any MCP client can drive the
design directly. See docs/ROUTING.md for the COM-vs-MCP routing policy.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Callable, Sequence
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from pydantic import Field

from .com import BentleyCom, BentleyError, Point, Target

log = logging.getLogger("bentley_mcp.server")

DEFAULT_PORT = 18131
LOOPBACK = "127.0.0.1"

_READ = {"readOnlyHint": True, "openWorldHint": False}
_WRITE = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}
_RAW = {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": False}

_INSTRUCTIONS = (
    "Controls the Bentley desktop app that currently owns the MicroStation "
    "automation object: MicroStation or OpenBuildings Designer, one at a time. "
    "A design file must already be open. OpenBuildings must be running with a "
    "DGN from its active workset. Coordinates are [x, y, z] in the active "
    "model's working units. Use list_apps or get_status first. Prefer the typed "
    "tools; use run_python or run_keyin (both gated on confirm=true) for "
    "anything the typed surface does not cover."
)


def _call(
    operation: Callable[..., dict[str, Any]], *args: Any, **kwargs: Any
) -> dict[str, Any]:
    try:
        return operation(*args, **kwargs)
    except BentleyError as exc:
        raise ToolError(str(exc)) from exc


def build_server(com: BentleyCom | None = None, token: str | None = None) -> FastMCP:
    """Build the MCP server. ``com`` is injectable for tests."""
    app = com if com is not None else BentleyCom()
    auth = (
        StaticTokenVerifier({token: {"client_id": "bentley-mcp"}}) if token else None
    )
    mcp = FastMCP("Bentley", instructions=_INSTRUCTIONS, auth=auth)

    @mcp.tool(annotations=_READ)
    async def list_apps() -> dict[str, Any]:
        """List the Bentley application currently attached, or an empty list."""
        return _call(app.list_apps)

    @mcp.tool(annotations=_READ)
    async def get_status(target: Target = "auto") -> dict[str, Any]:
        """Return the attached app, active design file, model, and extents.

        target: auto follows the attached app; microstation or openbuildings
        refuses a mismatch instead of acting on the other product.
        """
        return _call(app.get_status, target)

    @mcp.tool(annotations=_WRITE)
    async def open_design(
        path: str, target: Target = "auto", read_only: bool = False
    ) -> dict[str, Any]:
        """Open an absolute .dgn path in the attached application."""
        return _call(app.open_design, path, target, read_only)

    @mcp.tool(annotations=_WRITE)
    async def save_design(target: Target = "auto") -> dict[str, Any]:
        """Save the active design file."""
        return _call(app.save_design, target)

    @mcp.tool(annotations=_WRITE)
    async def create_line(
        start: Point, end: Point, target: Target = "auto"
    ) -> dict[str, Any]:
        """Add a line element to the active model. Points are [x, y, z]."""
        return _call(app.create_line, start, end, target)

    @mcp.tool(annotations=_WRITE)
    async def create_polyline(
        points: Annotated[list[Point], Field(min_length=2, max_length=1000)],
        target: Target = "auto",
    ) -> dict[str, Any]:
        """Add connected line segments to the active model.

        points: two to 1000 [x, y, z] points, in order.
        """
        return _call(app.create_polyline, points, target)

    @mcp.tool(annotations=_RAW)
    async def run_keyin(
        command: Annotated[str, Field(min_length=1, max_length=1024)],
        confirm: bool = False,
        target: Target = "auto",
    ) -> dict[str, Any]:
        """Send one MicroStation key-in. Requires confirm=true.

        This is raw application input: it can change or delete model content.
        Keep the command to one line (1024 characters maximum).
        """
        if not confirm:
            raise ToolError("confirm=true is required for run_keyin")
        return _call(app.run_keyin, command, True, target)

    @mcp.tool(annotations=_READ)
    async def fit_view(target: Target = "auto") -> dict[str, Any]:
        """Fit and redraw the open views in the active design file."""
        return _call(app.fit_view, target)

    @mcp.tool(annotations=_READ)
    async def list_models(target: Target = "auto") -> dict[str, Any]:
        """List models in the active design file (name, 3D, read-only flags)."""
        return _call(app.list_models, target)

    @mcp.tool(annotations=_READ)
    async def list_levels(target: Target = "auto") -> dict[str, Any]:
        """List levels in the active design file, with display state when readable."""
        return _call(app.list_levels, target)

    @mcp.tool(annotations=_WRITE)
    async def set_active_model(name: str, target: Target = "auto") -> dict[str, Any]:
        """Activate the named model (case-insensitive) in the active design file."""
        return _call(app.set_active_model, name, target)

    @mcp.tool(annotations=_READ)
    async def list_elements(
        limit: int = 100, level: str | None = None, target: Target = "auto"
    ) -> dict[str, Any]:
        """List elements in the active model: id, level, type.

        limit: 1..1000 returned. Scans at most the first 5000 elements, so
        filtered results on large models may be partial; check scanned_limit.
        """
        return _call(app.list_elements, limit, level, target)

    @mcp.tool(annotations=_RAW)
    async def delete_element(
        element_id: Annotated[int, Field(gt=0)],
        confirm: bool = False,
        target: Target = "auto",
    ) -> dict[str, Any]:
        """Remove one element (by element_id from list_elements) from the active model.

        Destructive: requires confirm=true. Searches only the first 5000
        elements of the active model.
        """
        if not confirm:
            raise ToolError("confirm=true is required for delete_element")
        return _call(app.delete_element, element_id, True, target)

    @mcp.tool(annotations=_WRITE)
    async def create_text(
        origin: Point,
        text: Annotated[str, Field(min_length=1, max_length=4096)],
        height: float | None = None,
        target: Target = "auto",
    ) -> dict[str, Any]:
        """Place a text element at [x, y, z] using the active text template.

        height: optional text height in working units; the result reports
        whether the template accepted it.
        """
        return _call(app.create_text, origin, text, height, target)

    @mcp.tool(annotations=_RAW)
    async def run_python(
        code: Annotated[str, Field(min_length=1, max_length=20000)],
        confirm: bool = False,
        target: Target = "auto",
    ) -> dict[str, Any]:
        """Run MicroStation Python code by writing it to a temp script and
        queueing the 'python execute' key-in. Requires confirm=true.

        Output appears in MicroStation's Python window, not in the tool
        result. Prefer typed tools; this is the escape hatch for anything
        they do not cover.
        """
        if not confirm:
            raise ToolError("confirm=true is required for run_python")
        return _call(app.run_python, code, True, target)

    return mcp


def _env_port() -> int:
    raw = os.environ.get("BENTLEY_MCP_PORT", str(DEFAULT_PORT))
    try:
        port = int(raw)
    except ValueError as exc:
        raise SystemExit(f"BENTLEY_MCP_PORT must be an integer, got {raw!r}") from exc
    if not 1 <= port <= 65535:
        raise SystemExit(f"BENTLEY_MCP_PORT must be 1..65535, got {port}")
    return port


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bentley-mcp",
        description="Typed local MCP control of MicroStation and OpenBuildings.",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="serve streamable HTTP on 127.0.0.1 instead of stdio",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"HTTP port (default {DEFAULT_PORT}; env BENTLEY_MCP_PORT)",
    )
    args = parser.parse_args(argv)
    if args.port is not None and not 1 <= args.port <= 65535:
        parser.error("--port must be 1..65535")
    return args


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    logging.basicConfig(
        level=os.environ.get("BENTLEY_MCP_LOG_LEVEL", "INFO").upper(),
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )

    token = os.environ.get("BENTLEY_MCP_TOKEN") or None
    server = build_server(token=token)

    if args.http:
        if not token:
            log.warning(
                "BENTLEY_MCP_TOKEN is not set; loopback HTTP has no bearer authentication"
            )
        server.run(
            transport="http",
            host=LOOPBACK,
            port=args.port if args.port is not None else _env_port(),
        )
    else:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
