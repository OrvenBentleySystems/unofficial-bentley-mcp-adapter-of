"""COM access for the Bentley app that owns MicroStationDGN.Application.

MicroStation and OpenBuildings Designer both expose the same automation object.
OpenBuildings' own ``Bentley.OpenBuildingsDesigner.Application`` ProgID is
registered but is not externally attachable in the tested build; the
``MicroStationDGN.Application`` object is the supported path.

The module keeps COM imports lazy so the MCP server can be constructed and
unit-tested without Bentley installed.
"""

from __future__ import annotations

import itertools
import logging
import os
import tempfile
import time
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


_run_seq = itertools.count(1)


def _collect(collection: Any, limit: int) -> list[Any]:
    """Materialize a COM collection, preferring native enumeration over Item()."""
    items: list[Any] = []
    try:
        for item in collection:
            items.append(item)
            if len(items) >= limit:
                return items
        return items
    except (TypeError, AttributeError):
        items = []
    count = int(collection.Count)
    base = 0
    try:
        collection.Item(0)
    except Exception:
        base = 1
    for index in range(base, min(base + count, base + limit)):
        items.append(collection.Item(index))
    return items


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

    def list_models(self, target: Target = "auto") -> dict[str, Any]:
        app, kind, name = self._for_target(target)
        try:
            models = []
            for model in _collect(app.ActiveDesignFile.Models, 500):
                entry: dict[str, Any] = {}
                try:
                    entry["name"] = str(model.Name)
                except Exception:
                    entry["name"] = None
                for attribute, cast in (("Is3D", bool), ("IsReadOnly", bool)):
                    try:
                        entry[attribute[2:].lower()] = cast(getattr(model, attribute))
                    except Exception:
                        continue
                models.append(entry)
        except Exception as exc:
            raise BentleyError(f"list_models failed: {exc}") from exc
        out = self._info(app, kind, name)
        out["models"] = models
        out["model_count"] = len(models)
        return out

    def list_levels(self, target: Target = "auto") -> dict[str, Any]:
        app, kind, name = self._for_target(target)
        try:
            levels = []
            for level in _collect(app.ActiveDesignFile.Levels, 64):
                entry: dict[str, Any] = {}
                try:
                    entry["name"] = str(level.Name)
                except Exception:
                    entry["name"] = None
                for attribute in ("IsDisplayed", "IsLevelUsed"):
                    try:
                        entry[attribute[2:].lower()] = bool(getattr(level, attribute))
                    except Exception:
                        continue
                levels.append(entry)
        except Exception as exc:
            raise BentleyError(f"list_levels failed: {exc}") from exc
        out = self._info(app, kind, name)
        out["levels"] = levels
        out["level_count"] = len(levels)
        return out

    def set_active_model(self, name: str, target: Target = "auto") -> dict[str, Any]:
        wanted = name.strip()
        if not wanted or len(wanted) > 255:
            raise BentleyError("model name must be 1..255 characters")
        app, kind, app_name = self._for_target(target)
        try:
            match = next(
                (
                    model
                    for model in _collect(app.ActiveDesignFile.Models, 500)
                    if str(model.Name).lower() == wanted.lower()
                ),
                None,
            )
            if match is None:
                raise BentleyError(f"model not found: {wanted!r}; call list_models first")
            match.Activate()
        except BentleyError:
            raise
        except Exception as exc:
            raise BentleyError(f"model Activate failed: {exc}") from exc
        out = self._info(app, kind, app_name)
        out["requested_model"] = wanted
        return out

    @staticmethod
    def _id_of(element: Any) -> int | None:
        try:
            return int(element.ID64)
        except Exception:
            pass
        try:
            dlong = element.ID64
            return (int(dlong.High) << 32) | int(dlong.Low)
        except Exception:
            return None

    def _graphical_cache(self, app: Any) -> Any:
        try:
            return app.ActiveModelReference.GraphicalElementCache
        except Exception as exc:
            raise BentleyError(f"GraphicalElementCache unavailable: {exc}") from exc

    def list_elements(
        self, limit: int = 100, level: str | None = None, target: Target = "auto"
    ) -> dict[str, Any]:
        if not 1 <= int(limit) <= 1000:
            raise BentleyError("limit must be 1..1000")
        app, kind, name = self._for_target(target)
        cache = self._graphical_cache(app)
        try:
            total = int(cache.Count)
        except Exception as exc:
            raise BentleyError(f"cache Count failed: {exc}") from exc
        elements: list[dict[str, Any]] = []
        index = 0
        while len(elements) < int(limit) and index < total:
            index += 1
            try:
                element = cache.GetElement(index)
            except Exception:
                continue
            if element is None:
                continue
            try:
                if bool(element.IsDeleted):
                    continue
            except Exception:
                pass
            element_id = self._id_of(element)
            if element_id is None:
                continue
            level_name: str | None = None
            try:
                level_name = str(element.Level.Name)
            except Exception:
                pass
            if level and (level_name or "").lower() != level.lower():
                continue
            entry: dict[str, Any] = {"element_id": element_id}
            if level_name is not None:
                entry["level"] = level_name
            try:
                entry["type"] = int(element.Type)
            except Exception:
                pass
            elements.append(entry)
        out = self._info(app, kind, name)
        out["elements"] = elements
        out["returned"] = len(elements)
        out["total_in_model"] = total
        out["truncated"] = len(elements) >= int(limit) and index < total
        return out

    def delete_element(
        self, element_id: int, confirm: bool = False, target: Target = "auto"
    ) -> dict[str, Any]:
        if not confirm:
            raise BentleyError("confirm=true is required for delete_element")
        if not isinstance(element_id, int) or element_id <= 0:
            raise BentleyError("element_id must be a positive integer")
        app, kind, name = self._for_target(target)
        cache = self._graphical_cache(app)
        try:
            total = int(cache.Count)
            model = app.ActiveModelReference
            for index in range(1, total + 1):
                try:
                    element = cache.GetElement(index)
                except Exception:
                    continue
                if element is None:
                    continue
                try:
                    if bool(element.IsDeleted):
                        continue
                except Exception:
                    pass
                if self._id_of(element) != element_id:
                    continue
                model.RemoveElement(element)
                out = self._info(app, kind, name)
                out["deleted"] = element_id
                return out
        except Exception as exc:
            raise BentleyError(f"delete_element failed: {exc}") from exc
        raise BentleyError(
            f"element {element_id} not found in the active model's graphical cache; "
            "call list_elements first (ids are per-model)"
        )

    def create_text(
        self,
        origin: Point,
        text: str,
        height: float | None = None,
        target: Target = "auto",
    ) -> dict[str, Any]:
        if not text.strip():
            raise BentleyError("text is empty")
        if len(text) > 4096:
            raise BentleyError("text is limited to 4096 characters")
        if height is not None and not 0.0 < float(height) <= 1e6:
            raise BentleyError("height must be greater than 0")

        app, kind, name = self._for_target(target)
        height_applied = height is None
        try:
            if height is not None:
                try:
                    app.ActiveSettings.TextStyle.Height = float(height)
                    height_applied = True
                except Exception:
                    pass
            # comtypes returns [Point3d, Matrix3d, TextElement]; the element is last.
            element = app.CreateTextElement1(None, text, _point(origin))
            if isinstance(element, (list, tuple)):
                element = element[-1]
            app.ActiveModelReference.AddElement(element)
        except BentleyError:
            raise
        except Exception as exc:
            raise BentleyError(f"CreateTextElement1 failed: {exc}") from exc
        out = self._info(app, kind, name)
        out["created"] = "text"
        out["height_applied"] = height_applied
        return out

    def run_python(
        self, code: str, confirm: bool = False, target: Target = "auto"
    ) -> dict[str, Any]:
        if not confirm:
            raise BentleyError("confirm=true is required for run_python")
        if not code.strip():
            raise BentleyError("code is empty")
        if len(code) > 20000:
            raise BentleyError("code is limited to 20000 characters")

        directory = Path(tempfile.gettempdir()) / "bentley_mcp"
        directory.mkdir(parents=True, exist_ok=True)
        script = directory / (
            f"exec_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}_{next(_run_seq)}.py"
        )
        script.write_text(code, encoding="utf-8")

        app, kind, name = self._for_target(target)
        keyin = f'python execute "{script}"'
        try:
            app.CadInputQueue.SendKeyin(keyin)
        except Exception as exc:
            raise BentleyError(f"SendKeyin failed: {exc}") from exc
        out = self._info(app, kind, name)
        out["script"] = str(script)
        out["keyin"] = keyin
        out["note"] = (
            "Queued to MicroStation's Python engine; results appear in its "
            "Python window, not in this tool result."
        )
        return out
