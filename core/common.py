from __future__ import annotations

import json
import os
import re
import socket
import getpass
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
INSTALLED_DATA_ROOT = Path(os.sys.prefix) / "share" / "bentley-mcp-adapter"
MODULES_DIR = (
    ROOT / "modules"
    if (ROOT / "modules").is_dir()
    else INSTALLED_DATA_ROOT / "modules"
)
TARGETS_DIR = (
    ROOT / "targets"
    if (ROOT / "targets").is_dir()
    else INSTALLED_DATA_ROOT / "targets"
)
PROVIDERS_DIR = (
    ROOT / "providers"
    if (ROOT / "providers").is_dir()
    else INSTALLED_DATA_ROOT / "providers"
)

FORBIDDEN_APPROVAL_KEYS = {
    "autoapprove",
    "auto_approve",
    "alwaysallow",
    "always_allow",
    "autotoolapproval",
    "auto_tool_approval",
}
SECRET_KEY_MARKERS = ("password", "secret", "token", "credential")


class AdapterError(RuntimeError):
    """An actionable adapter configuration error."""


def _validate_id(value: str, kind: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", value):
        raise AdapterError(f"Invalid {kind} id: {value!r}")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AdapterError(f"File not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise AdapterError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise AdapterError(f"Expected a YAML mapping in {path}")
    return data


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AdapterError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AdapterError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise AdapterError(f"Expected a JSON object in {path}")
    return data


def load_module(module_id: str) -> dict[str, Any]:
    _validate_id(module_id, "module")
    path = MODULES_DIR / module_id / "module.yaml"
    module = load_yaml(path)
    if module.get("id") != module_id:
        raise AdapterError(f"Module id mismatch in {path}")
    module["_descriptor_path"] = str(path)
    return module


def load_target(target_id: str) -> dict[str, Any]:
    _validate_id(target_id, "target")
    path = TARGETS_DIR / target_id / "target.yaml"
    target = load_yaml(path)
    if target.get("id") != target_id:
        raise AdapterError(f"Target id mismatch in {path}")
    target["_directory"] = str(path.parent)
    return target


def discover_target_ids() -> list[str]:
    if not TARGETS_DIR.is_dir():
        raise AdapterError(f"Target directory not found: {TARGETS_DIR}")
    discovered: list[str] = []
    for directory in sorted(TARGETS_DIR.iterdir(), key=lambda path: path.name.casefold()):
        if not directory.is_dir():
            continue
        if not (directory / "target.yaml").is_file():
            continue
        if not (directory / "writer.py").is_file():
            continue
        target = load_target(directory.name)
        discovered.append(str(target["id"]))
    return discovered


def load_provider(provider_id: str) -> dict[str, Any]:
    _validate_id(provider_id, "provider")
    path = PROVIDERS_DIR / provider_id / "provider.yaml"
    provider = load_yaml(path)
    if provider.get("id") != provider_id:
        raise AdapterError(f"Provider id mismatch in {path}")
    provider["_directory"] = str(path.parent)
    return provider


def discover_provider_ids() -> list[str]:
    if not PROVIDERS_DIR.is_dir():
        return []
    discovered: list[str] = []
    for directory in sorted(PROVIDERS_DIR.iterdir(), key=lambda path: path.name.casefold()):
        if not directory.is_dir():
            continue
        if not (directory / "provider.yaml").is_file():
            continue
        if not (directory / "writer.py").is_file():
            continue
        provider = load_provider(directory.name)
        discovered.append(str(provider["id"]))
    return discovered


def validate_safe_profile(value: Any, path: str = "profile") -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            validate_safe_profile(item, f"{path}[{index}]")
        return
    if not isinstance(value, dict):
        return
    for key, item in value.items():
        folded = str(key).replace("-", "_").casefold()
        if folded in FORBIDDEN_APPROVAL_KEYS:
            raise AdapterError(f"Automatic approval setting is forbidden: {path}.{key}")
        if (
            any(marker in folded for marker in SECRET_KEY_MARKERS)
            and item not in (None, "")
            and not (isinstance(item, dict) and set(item) == {"secret"})
        ):
            raise AdapterError(
                f"Possible secret at {path}.{key}; use a {{secret: input-id}} reference"
            )
        if isinstance(item, dict) and set(item) == {"secret"}:
            continue
        validate_safe_profile(item, f"{path}.{key}")


def validate_machine_identity(machine: dict[str, Any]) -> None:
    host = machine.get("host")
    if not isinstance(host, dict):
        raise AdapterError("machine.json has no host record")
    recorded_host = str(host.get("computer_name") or "")
    recorded_account = str(host.get("account_name") or "")
    if recorded_host.casefold() != socket.gethostname().casefold():
        raise AdapterError(
            f"machine.json belongs to host '{recorded_host}', not '{socket.gethostname()}'"
        )
    if recorded_account.casefold() != getpass.getuser().casefold():
        raise AdapterError(
            f"machine.json belongs to account '{recorded_account}', not '{getpass.getuser()}'"
        )


def enabled_modules(profile: dict[str, Any]) -> list[dict[str, Any]]:
    selected = profile.get("modules")
    if not isinstance(selected, dict) or not selected:
        raise AdapterError("profiles/site.yaml must enable at least one module")
    modules: list[dict[str, Any]] = []
    for module_id, settings in selected.items():
        if settings is False:
            continue
        module = load_module(module_id)
        module["_site"] = settings if isinstance(settings, dict) else {}
        modules.append(module)
    if not modules:
        raise AdapterError("No modules are enabled")
    return modules


def enforce_local_provider_tier(
    profile: dict[str, Any], modules: list[dict[str, Any]]
) -> None:
    if not profile.get("local_provider"):
        return
    full_modules = [
        module["id"]
        for module in modules
        if str(module["_site"].get("tier", "read")) == "full"
    ]
    if full_modules:
        raise AdapterError(
            "Full tier cannot be used with a local provider because the tool "
            "catalogue exceeds the supported local-model posture: "
            + ", ".join(full_modules)
        )


def expand_path(value: str, base: Path | None = None) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(value))
    path = Path(expanded)
    if not path.is_absolute() and base is not None:
        path = base / path
    return path.resolve(strict=False)


def lexical_path(value: str, base: Path | None = None) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(value))
    path = Path(expanded)
    if not path.is_absolute() and base is not None:
        path = base / path
    return Path(os.path.abspath(path))


def output_roots(
    profile: dict[str, Any],
    machine: dict[str, Any],
    profile_path: Path,
) -> list[Path]:
    candidates: list[Path] = [profile_path.resolve().parent]
    for key in ("user_profile", "local_app_data"):
        value = (machine.get("known_folders") or {}).get(key)
        if value:
            candidates.append(Path(str(value)).resolve(strict=False))
    for key in ("workspace_root", "allowed_directory"):
        value = profile.get(key)
        if value:
            resolved = resolve_tokens(str(value), machine, profile)
            candidates.append(expand_path(resolved))
    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def _is_reparse_point(path: Path) -> bool:
    try:
        stat = path.lstat()
    except OSError:
        return False
    return bool(getattr(stat, "st_file_attributes", 0) & 0x400)


def validate_output_path(path: Path, roots: list[Path]) -> Path:
    lexical = lexical_path(str(path))
    for component in (lexical, *lexical.parents):
        if component.exists() and _is_reparse_point(component):
            raise AdapterError(f"Output path contains a reparse point: {component}")
    resolved = lexical.resolve(strict=False)
    for root in roots:
        try:
            resolved.relative_to(root.resolve(strict=False))
            return lexical
        except ValueError:
            continue
    raise AdapterError(f"Output path is outside approved roots: {lexical}")


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if _is_reparse_point(path.parent) or _is_reparse_point(temporary):
            raise AdapterError(f"Refusing reparse-point write: {path}")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def get_nested(data: dict[str, Any], dotted: str) -> Any:
    current: Any = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise AdapterError(f"machine.json does not contain '{dotted}'")
        current = current[part]
    return current


def resolve_tokens(value: Any, machine: dict[str, Any], profile: dict[str, Any]) -> Any:
    if isinstance(value, list):
        return [resolve_tokens(item, machine, profile) for item in value]
    if isinstance(value, dict):
        return {key: resolve_tokens(item, machine, profile) for key, item in value.items()}
    if not isinstance(value, str):
        return value
    output = value
    while "${machine." in output:
        start = output.index("${machine.")
        end = output.find("}", start)
        if end < 0:
            raise AdapterError(f"Unclosed machine token in '{value}'")
        key = output[start + len("${machine.") : end]
        resolved = get_nested(machine, key)
        if resolved is None:
            raise AdapterError(f"machine.json value '{key}' is not available")
        replacement = str(resolved)
        output = output[:start] + replacement + output[end + 1 :]
    while "${profile." in output:
        start = output.index("${profile.")
        end = output.find("}", start)
        if end < 0:
            raise AdapterError(f"Unclosed profile token in '{value}'")
        key = output[start + len("${profile.") : end]
        replacement = str(get_nested(profile, key))
        output = output[:start] + replacement + output[end + 1 :]
    return output


def write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_write_text(
        path,
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
    )
