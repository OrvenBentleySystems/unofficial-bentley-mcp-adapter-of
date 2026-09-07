from __future__ import annotations

import ctypes
import getpass
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import uuid
from ctypes import wintypes
from pathlib import Path
from typing import Any

from core.common import AdapterError, utc_now, write_json

if sys.platform == "win32":
    import winreg


FOLDER_IDS = {
    "user_profile": "5E6C858F-0E22-4760-9AFE-EA3317B67173",
    "local_app_data": "F1B32785-6FBA-4FCF-9D55-7B8E7F157091",
}

APP_PATTERNS = {
    "microstation": (r"^MicroStation \d",),
    "microstation_js_apps": (r"MicroStationJsApps", r"Copilot for MicroStation"),
    "staadpro": (r"^STAAD\.Pro \d",),
    "plaxis2d": (r"^PLAXIS 2D (?!Output Viewer)",),
    "plaxis3d": (r"^PLAXIS 3D (?!Output Viewer)",),
}


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_string(cls, value: str) -> "GUID":
        raw = uuid.UUID(value).bytes_le
        return cls.from_buffer_copy(raw)


def _known_folder(folder_id: str) -> Path:
    shell32 = ctypes.windll.shell32
    ole32 = ctypes.windll.ole32
    output = ctypes.c_wchar_p()
    guid = GUID.from_string(folder_id)
    result = shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(output))
    if result != 0:
        raise AdapterError(f"SHGetKnownFolderPath failed with HRESULT 0x{result & 0xFFFFFFFF:08X}")
    try:
        return Path(output.value).resolve(strict=False)
    finally:
        ole32.CoTaskMemFree(output)


def _registry_views() -> list[tuple[Any, int, str]]:
    return [
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY, "HKLM64"),
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY, "HKLM32"),
        (winreg.HKEY_CURRENT_USER, 0, "HKCU"),
    ]


def _read_value(key: Any, name: str) -> str | None:
    try:
        value, _ = winreg.QueryValueEx(key, name)
    except OSError:
        return None
    return str(value) if value not in (None, "") else None


def _enumerate_installations() -> dict[str, list[dict[str, Any]]]:
    found = {app_id: [] for app_id in APP_PATTERNS}
    uninstall = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    seen: set[tuple[str, str, str]] = set()
    for hive, view, source in _registry_views():
        try:
            root = winreg.OpenKey(hive, uninstall, 0, winreg.KEY_READ | view)
        except OSError:
            continue
        with root:
            for index in range(winreg.QueryInfoKey(root)[0]):
                try:
                    child_name = winreg.EnumKey(root, index)
                    child = winreg.OpenKey(root, child_name)
                except OSError:
                    continue
                with child:
                    display_name = _read_value(child, "DisplayName")
                    if not display_name:
                        continue
                    for app_id, patterns in APP_PATTERNS.items():
                        if not any(
                            re.search(pattern, display_name, re.IGNORECASE)
                            for pattern in patterns
                        ):
                            continue
                        version = _read_value(child, "DisplayVersion") or "unverified"
                        location = _read_value(child, "InstallLocation")
                        signature = (app_id, display_name, version)
                        if signature in seen:
                            continue
                        seen.add(signature)
                        found[app_id].append(
                            {
                                "display_name": display_name,
                                "version": version,
                                "install_location": location,
                                "registry_source": source,
                                "registry_key": child_name,
                            }
                        )
    return found


def _find_microstation_bundle(local_app_data: Path) -> Path | None:
    programs = local_app_data / "Programs" / "Bentley"
    if not programs.is_dir():
        return None
    matches = sorted(programs.glob("MicroStationJsApps *\\bundle.mcp.js"), reverse=True)
    return matches[0].resolve(strict=False) if matches else None


def _find_plaxis_profiles(local_app_data: Path) -> dict[str, str | None]:
    root = local_app_data / "Caros" / "PLAXIS-MCP" / "profiles"
    return {
        "directory": str(root),
        "input": str(root / "input.toml") if (root / "input.toml").is_file() else None,
        "output": str(root / "output.toml") if (root / "output.toml").is_file() else None,
    }


def _command_path(name: str) -> str | None:
    value = shutil.which(name)
    return str(Path(value).resolve(strict=False)) if value else None


def _python_313() -> str | None:
    launcher = shutil.which("py")
    if not launcher:
        launcher = ""
    try:
        result = subprocess.run(
            [launcher, "-3.13", "-c", "import sys;print(sys.executable)"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        uv = shutil.which("uv")
        if not uv:
            return None
        try:
            result = subprocess.run(
                [uv, "python", "find", "3.13"],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            return None
    output = result.stdout.strip()
    return str(Path(output).resolve(strict=False)) if output else None


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def _long_paths_enabled() -> bool:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\FileSystem",
        )
        with key:
            value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
            return int(value) == 1
    except OSError:
        return False


def _sync_roots() -> list[Path]:
    roots: list[Path] = []
    for name, value in os.environ.items():
        if name.casefold().startswith("onedrive") and value:
            roots.append(Path(value).resolve(strict=False))
    return sorted(set(roots), key=lambda path: str(path).casefold())


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_machine(output: Path, working_directory: Path) -> dict[str, Any]:
    if sys.platform != "win32":
        raise AdapterError("Bentley MCP Adapter supports Windows only")
    user_profile = _known_folder(FOLDER_IDS["user_profile"])
    local_app_data = _known_folder(FOLDER_IDS["local_app_data"])
    working_directory = working_directory.resolve(strict=False)
    sync_roots = _sync_roots()
    installations = _enumerate_installations()
    bundle = _find_microstation_bundle(local_app_data)
    data: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "host": {
            "computer_name": socket.gethostname(),
            "account_name": getpass.getuser(),
            "platform": platform.platform(),
            "windows_release": platform.release(),
            "windows_version": platform.version(),
            "python": sys.version.split()[0],
            "python_executable": str(Path(sys.executable).resolve(strict=False)),
            "is_admin": _is_admin(),
            "long_paths_enabled": _long_paths_enabled(),
        },
        "known_folders": {
            "user_profile": str(user_profile),
            "local_app_data": str(local_app_data),
        },
        "working_directory": {
            "path": str(working_directory),
            "inside_synced_folder": any(
                _is_relative_to(working_directory, root) for root in sync_roots
            ),
            "sync_roots": [str(root) for root in sync_roots],
        },
        "executables": {
            "node": _command_path("node"),
            "uv": _command_path("uv"),
            "uvx": _command_path("uvx"),
            "python_313": _python_313(),
        },
        "installations": installations,
        "microstation": {
            "mcp_bundle": str(bundle) if bundle else None,
            "tool_inventory": str(
                local_app_data / "Bentley" / "McpBridge" / "Config" / "microstation-tools.json"
            ),
            "bridge_log": str(
                local_app_data / "Bentley" / "Logs" / "mstn-copilot-mcpb.log"
            ),
        },
        "plaxis": {"profiles": _find_plaxis_profiles(local_app_data)},
    }
    write_json(output, data)
    return data
