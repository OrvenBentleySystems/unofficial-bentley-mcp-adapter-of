"""COM access for the Bentley app that owns MicroStationDGN.Application.

MicroStation and OpenBuildings Designer both expose the same automation object.
OpenBuildings' own ``Bentley.OpenBuildingsDesigner.Application`` ProgID is
registered but is not externally attachable in the tested build; the
``MicroStationDGN.Application`` object is the supported path.

The module keeps COM imports lazy so the MCP server can be constructed and
unit-tested without Bentley installed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

log = logging.getLogger("bentley_mcp.com")

PROGID = "MicroStationDGN.Application"
_TYPE_LIB = ("{CF9F97BF-39F2-4B8E-835C-8BE9E99DAF5B}", 10, 1)

Target = Literal["auto", "microstation", "openbuildings"]
Point = tuple[float, float, float]

_NO_APP = (
    "No Bentley automation object is registered. Open a DGN in MicroStation "
    "or OpenBuildings. OpenBuildings must be launched with a DGN inside its "
    "active workset, not left on the start page."
)
_ONE_AT_A_TIME = (
    "MicroStation and OpenBuildings share one automation registration; only "
    "the current owner is attachable. Run one at a time."
)

_comtypes_client: Any = None
_microstation: Any = None


class BentleyError(RuntimeError):
    """A Bentley COM operation failed."""


class BentleyUnavailable(BentleyError):
    """No attachable Bentley automation object is running."""


def _client() -> Any:
    global _comtypes_client
    if _comtypes_client is None:
        import comtypes.client as client  # Windows-only, lazy

        _comtypes_client = client
    return _comtypes_client


def _ms() -> Any:
    global _microstation
    if _microstation is None:
        _microstation = _client().GetModule(_TYPE_LIB)
    return _microstation


def _kind(name: str) -> str:
    lowered = name.lower()
    if "openbuildings" in lowered:
        return "openbuildings"
    if "microstation" in lowered:
        return "microstation"
    return "bentley"


def _point(value: Point) -> Any:
    x, y, z = value
    point = _ms().Point3d()
    point.X = float(x)
    point.Y = float(y)
    point.Z = float(z)
    return point


def _xyz(point: Any) -> dict[str, float]:
    return {"x": float(point.X), "y": float(point.Y), "z": float(point.Z)}


class BentleyCom:
    """Thin, synchronous wrapper around the Bentley automation object."""

    def __init__(self, progid: str = PROGID) -> None:
        self._progid = progid

    def _active(self) -> Any:
        try:
            return _client().GetActiveObject(self._progid)
        except Exception as exc:
            raise BentleyUnavailable(_NO_APP) from exc

    def _for_target(self, target: Target) -> tuple[Any, str, str]:
        app = self._active()
        try:
            name = str(app.Name)
        except Exception:
            name = ""
        kind = _kind(name)
        if target != "auto" and kind != target:
            raise BentleyError(
                f"Active Bentley app is {kind} ({name or 'unknown'}); requested "
                f"{target}. Close the other product or start {target} with a DGN open."
            )
        return app, kind, name

    @staticmethod
    def _info(app: Any, kind: str, name: str) -> dict[str, Any]:
        design_file: str | None = None
        model: str | None = None
        is_3d: bool | None = None
        is_read_only: bool | None = None
        extent: dict[str, Any] | None = None

        try:
            if bool(app.HasActiveDesignFile):
                design_file = str(app.ActiveDesignFile.FullName)
        except Exception:
            design_file = None

        try:
            model_ref = app.ActiveModelReference
            model = str(model_ref.Name)
            is_3d = bool(model_ref.Is3D)
            is_read_only = bool(model_ref.IsReadOnly)
            try:
                bounds = model_ref.Range(False)
                extent = {"low": _xyz(bounds.Low), "high": _xyz(bounds.High)}
            except Exception:
                extent = None
        except Exception:
            model_ref = None

        try:
            process_id: int | None = int(app.ProcessID)
        except Exception:
            process_id = None

        try:
            version = str(app.Version)
        except Exception:
            version = "unknown"

        return {
            "kind": kind,
            "name": name or "unknown",
            "version": version,
            "process_id": process_id,
            "design_file": design_file,
            "model": model,
            "is_3d": is_3d,
            "is_read_only": is_read_only,
            "extent": extent,
        }

    def list_apps(self) -> dict[str, Any]:
        """Return the currently attached Bentley app, or an empty list."""
        try:
            app, kind, name = self._for_target("auto")
        except BentleyUnavailable:
            return {"apps": [], "note": _NO_APP}
        return {"apps": [self._info(app, kind, name)], "note": _ONE_AT_A_TIME}

    def get_status(self, target: Target = "auto") -> dict[str, Any]:
        app, kind, name = self._for_target(target)
        return self._info(app, kind, name)

    def open_design(
        self, path: str, target: Target = "auto", read_only: bool = False
    ) -> dict[str, Any]:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            raise BentleyError("path must be absolute")
        if candidate.suffix.lower() != ".dgn":
            raise BentleyError("path must name a .dgn file")
        if not candidate.is_file():
            raise BentleyError(f"design file not found: {candidate}")

        app, kind, name = self._for_target(target)
        try:
            app.OpenDesignFile(str(candidate), bool(read_only))
        except Exception as exc:
            raise BentleyError(f"OpenDesignFile failed: {exc}") from exc
        return self._info(app, kind, name)

    def save_design(self, target: Target = "auto") -> dict[str, Any]:
        app, kind, name = self._for_target(target)
        try:
            app.ActiveDesignFile.Save()
        except Exception as exc:
            raise BentleyError(f"Save failed: {exc}") from exc
        out = self._info(app, kind, name)
        out["saved"] = True
        return out

    def create_line(self, start: Point, end: Point, target: Target = "auto") -> dict[str, Any]:
        app, kind, name = self._for_target(target)
        try:
            result = app.CreateLineElement2(None, _point(start), _point(end))
            app.ActiveModelReference.AddElement(result[2])
        except Exception as exc:
            raise BentleyError(f"CreateLineElement2 failed: {exc}") from exc
        out = self._info(app, kind, name)
        out["created"] = "line"
        return out

    def create_polyline(self, points: list[Point], target: Target = "auto") -> dict[str, Any]:
        if len(points) < 2:
            raise BentleyError("polyline needs at least two points")
        if len(points) > 1000:
            raise BentleyError("polyline is limited to 1000 points")

        app, kind, name = self._for_target(target)
        try:
            model = app.ActiveModelReference
            for start, end in zip(points, points[1:]):
                result = app.CreateLineElement2(None, _point(start), _point(end))
                model.AddElement(result[2])
        except Exception as exc:
            raise BentleyError(f"CreateLineElement2 failed: {exc}") from exc
        out = self._info(app, kind, name)
        out["created"] = "polyline"
        out["segments"] = len(points) - 1
        return out

    def run_keyin(
        self, command: str, confirm: bool = False, target: Target = "auto"
    ) -> dict[str, Any]:
        if not confirm:
            raise BentleyError("confirm=true is required for run_keyin")
        command = command.strip()
        if not command:
            raise BentleyError("key-in command is empty")
        if len(command) > 1024 or "\r" in command or "\n" in command:
            raise BentleyError("key-in command must be one line of at most 1024 characters")

        app, kind, name = self._for_target(target)
        try:
            app.CadInputQueue.SendKeyin(command)
        except Exception as exc:
            raise BentleyError(f"SendKeyin failed: {exc}") from exc
        out = self._info(app, kind, name)
        out["keyin"] = command
        return out

    def fit_view(self, target: Target = "auto") -> dict[str, Any]:
        app, kind, name = self._for_target(target)
        fitted = 0
        try:
            views = app.ActiveDesignFile.Views
            count = int(views.Count)
            for index in range(1, count + 1):
                view = views.Item(index)
                if not bool(view.IsOpen):
                    continue
                view.Fit(False)
                view.Redraw()
                fitted += 1
        except Exception as exc:
            raise BentleyError(f"Fit view failed: {exc}") from exc
        if fitted == 0:
            raise BentleyError("No open views to fit")
        out = self._info(app, kind, name)
        out["views"] = fitted
        out["view_count"] = count
        return out
