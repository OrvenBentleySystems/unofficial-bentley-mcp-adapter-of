"""Unit tests for the Bentley MCP tool surface.

COM is replaced by a fake adapter. These tests prove argument policy and
forwarding only; they are not live Bentley evidence.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastmcp import Client

from bentley_mcp.com import BentleyCom, BentleyError, _kind
from bentley_mcp.server import build_server

TOOLS = {
    "list_apps",
    "get_status",
    "open_design",
    "save_design",
    "create_line",
    "create_polyline",
    "run_keyin",
    "fit_view",
}


class FakeCom:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def list_apps(self) -> dict[str, Any]:
        self.calls.append(("list_apps",))
        return {"apps": [{"kind": "openbuildings"}], "note": "one at a time"}

    def get_status(self, target: str = "auto") -> dict[str, Any]:
        self.calls.append(("get_status", target))
        return {"kind": "openbuildings", "design_file": "C:\\scratch\\test.dgn"}

    def open_design(
        self, path: str, target: str = "auto", read_only: bool = False
    ) -> dict[str, Any]:
        self.calls.append(("open_design", path, target, read_only))
        return {"design_file": path}

    def save_design(self, target: str = "auto") -> dict[str, Any]:
        self.calls.append(("save_design", target))
        return {"saved": True}

    def create_line(
        self, start: Any, end: Any, target: str = "auto"
    ) -> dict[str, Any]:
        self.calls.append(("create_line", start, end, target))
        return {"created": "line"}

    def create_polyline(self, points: Any, target: str = "auto") -> dict[str, Any]:
        self.calls.append(("create_polyline", points, target))
        return {"created": "polyline", "segments": len(points) - 1}

    def run_keyin(
        self, command: str, confirm: bool = False, target: str = "auto"
    ) -> dict[str, Any]:
        self.calls.append(("run_keyin", command, confirm, target))
        return {"keyin": command}

    def fit_view(self, target: str = "auto") -> dict[str, Any]:
        self.calls.append(("fit_view", target))
        return {"views": 8}


def fake_server() -> tuple[FakeCom, Any]:
    fake = FakeCom()
    return fake, build_server(com=fake)  # type: ignore[arg-type]


async def test_tool_surface_and_annotations() -> None:
    _, server = fake_server()
    async with Client(server) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    assert set(tools) == TOOLS
    for name in ("list_apps", "get_status", "fit_view"):
        assert tools[name].annotations.readOnlyHint is True
    assert tools["run_keyin"].annotations.destructiveHint is True
    assert tools["create_line"].annotations.readOnlyHint is False


async def test_discovery_and_status_forward() -> None:
    fake, server = fake_server()
    async with Client(server) as client:
        apps = (await client.call_tool("list_apps", {})).structured_content
        status = (
            await client.call_tool("get_status", {"target": "openbuildings"})
        ).structured_content

    assert apps["apps"][0]["kind"] == "openbuildings"
    assert status["design_file"].endswith("test.dgn")
    assert fake.calls == [("list_apps",), ("get_status", "openbuildings")]


async def test_file_and_geometry_forward() -> None:
    fake, server = fake_server()
    async with Client(server) as client:
        await client.call_tool(
            "open_design",
            {"path": "C:\\scratch\\test.dgn", "target": "auto", "read_only": True},
        )
        await client.call_tool("save_design", {})
        await client.call_tool(
            "create_line", {"start": [0, 0, 0], "end": [25, 0, 0]}
        )
        result = await client.call_tool(
            "create_polyline", {"points": [[0, 0, 0], [1, 0, 0], [1, 1, 0]]}
        )
        await client.call_tool("fit_view", {})

    assert result.structured_content["segments"] == 2
    assert fake.calls == [
        ("open_design", "C:\\scratch\\test.dgn", "auto", True),
        ("save_design", "auto"),
        ("create_line", (0, 0, 0), (25, 0, 0), "auto"),
        ("create_polyline", [(0, 0, 0), (1, 0, 0), (1, 1, 0)], "auto"),
        ("fit_view", "auto"),
    ]


async def test_run_keyin_requires_confirm() -> None:
    fake, server = fake_server()
    async with Client(server) as client:
        refused = await client.call_tool(
            "run_keyin", {"command": "DELETE ELEMENT"}, raise_on_error=False
        )
        sent = await client.call_tool(
            "run_keyin",
            {"command": "DELETE ELEMENT", "confirm": True, "target": "microstation"},
        )

    assert refused.is_error
    assert sent.structured_content["keyin"] == "DELETE ELEMENT"
    assert fake.calls == [("run_keyin", "DELETE ELEMENT", True, "microstation")]


def test_com_validation_before_attach() -> None:
    com = BentleyCom()
    with pytest.raises(BentleyError, match="absolute"):
        com.open_design("relative.dgn")
    with pytest.raises(BentleyError, match="\\.dgn"):
        com.open_design("C:\\scratch\\not-a-design.txt")


def test_product_name_classification() -> None:
    assert _kind("OpenBuildingsDesigner") == "openbuildings"
    assert _kind("MicroStation") == "microstation"
    assert _kind("") == "bentley"


def test_http_token_controls_auth() -> None:
    assert build_server(token=None).auth is None
    assert build_server(token="local-secret").auth is not None
