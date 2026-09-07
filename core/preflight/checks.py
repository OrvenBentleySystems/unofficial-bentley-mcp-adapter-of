from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.common import (
    AdapterError,
    enabled_modules,
    expand_path,
    load_json,
    load_yaml,
    resolve_tokens,
    validate_machine_identity,
    validate_safe_profile,
)
from core.preflight.mcp_client import McpError, StdioMcpClient
from core.provider import run_provider_preflight
from core.provider_api import ProviderPreflightError


EXIT_MACHINE = 10
EXIT_VERSION_RECORD = 11
EXIT_APPLICATION = 12
EXIT_MODEL = 13
EXIT_PORT = 14
EXIT_VERSION = 15
EXIT_DIRECTORY = 16
EXIT_TOOL = 17
EXIT_LOCAL_PROVIDER = 18

REQUIRED_VERSION_FIELDS = (
    "date",
    "operator",
    "machine",
    "os build",
    "MicroStation build",
    "STAAD.Pro version",
    "PLAXIS version",
    "openstaad-mcp tag",
    "plaxis-mcp version",
    "AI client + version",
    "model identifier",
    "temperature",
    "allowed directory",
)


class CheckFailure(RuntimeError):
    def __init__(self, exit_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.code = code


def _run_powershell(script: str, timeout: int = 30) -> str:
    powershell = shutil.which("powershell.exe")
    if not powershell:
        raise AdapterError("powershell.exe is not available")
    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise AdapterError(f"PowerShell probe timed out after {timeout}s") from exc
    except OSError as exc:
        raise AdapterError(f"PowerShell probe could not start: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise AdapterError(f"PowerShell probe failed: {detail}")
    return result.stdout.strip()


def _powershell_json(script: str) -> Any:
    output = _run_powershell(
        f"& {{\n{script}\n}} | ConvertTo-Json -Depth 6 -Compress"
    )
    if not output:
        return []
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"PowerShell probe returned invalid JSON: {output[:200]}") from exc


def _machine_current(machine: dict[str, Any], profile: dict[str, Any]) -> None:
    try:
        validate_machine_identity(machine)
    except AdapterError as exc:
        raise CheckFailure(EXIT_MACHINE, "MACHINE_FOREIGN", str(exc)) from exc
    generated = machine.get("generated_at")
    if not isinstance(generated, str):
        raise CheckFailure(EXIT_MACHINE, "MACHINE_INVALID", "machine.json has no generated_at")
    try:
        timestamp = datetime.fromisoformat(generated.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CheckFailure(
            EXIT_MACHINE, "MACHINE_INVALID", "machine.json generated_at is invalid"
        ) from exc
    max_age = float(profile.get("machine_max_age_hours", 24))
    age_hours = (datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds() / 3600
    if age_hours < 0 or age_hours > max_age:
        raise CheckFailure(
            EXIT_MACHINE,
            "MACHINE_STALE",
            f"machine.json is {age_hours:.1f} hours old; run resolve again",
        )


def _version_record_complete(profile: dict[str, Any]) -> None:
    record = profile.get("version_record")
    if not isinstance(record, dict):
        raise CheckFailure(EXIT_VERSION_RECORD, "VERSION_RECORD_MISSING", "version_record is missing")
    missing = []
    for field in REQUIRED_VERSION_FIELDS:
        value = record.get(field)
        if value is None or str(value).strip() == "" or "TODO" in str(value).upper():
            missing.append(field)
    if missing:
        raise CheckFailure(
            EXIT_VERSION_RECORD,
            "VERSION_RECORD_INCOMPLETE",
            "Incomplete version record fields: " + ", ".join(missing),
        )


def _process_snapshot() -> list[dict[str, Any]]:
    script = r"""
$rows = foreach ($p in Get-CimInstance Win32_Process) {
  $gp = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
  $version = $null
  if ($p.ExecutablePath -and (Test-Path -LiteralPath $p.ExecutablePath)) {
    $version = [Diagnostics.FileVersionInfo]::GetVersionInfo($p.ExecutablePath).FileVersion
  }
  [PSCustomObject]@{
    pid = [int]$p.ProcessId
    name = [string]$p.Name
    path = [string]$p.ExecutablePath
    title = [string]$gp.MainWindowTitle
    version = [string]$version
  }
}
$rows
"""
    result = _powershell_json(script)
    if isinstance(result, dict):
        return [result]
    return result if isinstance(result, list) else []


def _module_processes(
    module: dict[str, Any], processes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    names = {str(name).casefold() for name in module["requires"].get("process_names", [])}
    return [
        process
        for process in processes
        if str(process.get("name", "")).casefold() in names
    ]


def _check_processes(
    modules: list[dict[str, Any]], processes: list[dict[str, Any]]
) -> None:
    for module in modules:
        if not _module_processes(module, processes):
            raise CheckFailure(
                EXIT_APPLICATION,
                "APPLICATION_NOT_RUNNING",
                f"{module['display']} process is not running",
            )


def _com_probe(kind: str) -> dict[str, Any]:
    if kind == "microstation_com":
        script = r"""
$app = [Runtime.InteropServices.Marshal]::GetActiveObject('MicroStationDGN.Application')
[PSCustomObject]@{
  file = [string]$app.ActiveDesignFile.FullName
  version = [string]$app.Version
}
"""
    else:
        script = r"""
$app = [Runtime.InteropServices.Marshal]::GetActiveObject('StaadPro.OpenSTAAD')
[PSCustomObject]@{
  file = [string]$app.GetSTAADFile()
  version = [string]$app.GetApplicationVersion()
}
"""
    result = _powershell_json(script)
    return result if isinstance(result, dict) else {}


def _check_models(
    modules: list[dict[str, Any]], processes: list[dict[str, Any]]
) -> None:
    for module in modules:
        check = module["requires"].get("model_check")
        candidates = _module_processes(module, processes)
        if check == "window_title":
            rejected = [
                token.casefold()
                for token in module["requires"].get("model_title_reject", [])
            ]
            titles = [str(item.get("title") or "") for item in candidates]
            open_titles = [
                title
                for title in titles
                if title and not any(token in title.casefold() for token in rejected)
            ]
            if not open_titles:
                raise CheckFailure(
                    EXIT_MODEL,
                    "MODEL_NOT_OPEN",
                    f"{module['display']} is running without an open project",
                )
            continue
        try:
            result = _com_probe(str(check))
        except (AdapterError, subprocess.SubprocessError):
            result = {}
        if result.get("file"):
            continue
        if check == "staad_com" and any(
            re.search(r"\.std(?:\s|$)", str(item.get("title") or ""), re.IGNORECASE)
            for item in candidates
        ):
            continue
        raise CheckFailure(
            EXIT_MODEL,
            "MODEL_NOT_OPEN",
            f"{module['display']} is running without an open model",
        )


def _port_rows(port: int) -> list[dict[str, Any]]:
    script = f"""
$rows = foreach ($c in Get-NetTCPConnection -State Listen -LocalPort {int(port)} -ErrorAction SilentlyContinue) {{
  $p = Get-CimInstance Win32_Process -Filter "ProcessId=$($c.OwningProcess)" -ErrorAction SilentlyContinue
  [PSCustomObject]@{{
    address = [string]$c.LocalAddress
    port = [int]$c.LocalPort
    pid = [int]$c.OwningProcess
    process = [string]$p.Name
    path = [string]$p.ExecutablePath
  }}
}}
$rows
"""
    result = _powershell_json(script)
    rows = [result] if isinstance(result, dict) else result
    return rows if isinstance(rows, list) else []


def classify_port(rows: list[dict[str, Any]], expected_process: str) -> tuple[str, str]:
    unique = {int(row["pid"]): row for row in rows if row.get("pid") is not None}
    if not unique:
        return "PORT_NOT_LISTENING", "No process is listening"
    names = {str(row.get("process", "")).casefold() for row in unique.values()}
    expected = expected_process.casefold()
    if len(unique) > 1:
        detail = ", ".join(
            f"{row.get('process')} (PID {pid})" for pid, row in sorted(unique.items())
        )
        return "PORT_COLLISION", f"Multiple processes own the port: {detail}"
    if expected not in names:
        row = next(iter(unique.values()))
        return (
            "PORT_IDENTITY_MISMATCH",
            f"Expected {expected_process}, found {row.get('process')} (PID {row.get('pid')})",
        )
    return "PASS", f"{expected_process} owns the port"


def _check_ports(modules: list[dict[str, Any]], profile: dict[str, Any]) -> None:
    port_map = profile.get("port_map") or {}
    for module in modules:
        network = module.get("network") or {}
        if not network.get("uses_port"):
            continue
        port = int(port_map.get(module["id"], network["default_port"]))
        try:
            rows = _port_rows(port)
        except AdapterError as exc:
            raise CheckFailure(
                EXIT_PORT, "PORT_PROBE_FAILED", f"Could not inspect port {port}: {exc}"
            ) from exc
        code, message = classify_port(rows, str(network["expected_process"]))
        if code != "PASS":
            raise CheckFailure(
                EXIT_PORT,
                code,
                f"{module['display']} port {port}: {message}",
            )


def _numeric_version(value: Any) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", str(value)))


def _version_matches(actual: Any, expected: Any) -> bool:
    left = _numeric_version(actual)
    right = _numeric_version(expected)
    if not left or not right:
        return str(actual).strip().casefold() == str(expected).strip().casefold()
    width = max(len(left), len(right))
    padded_left = left + (0,) * (width - len(left))
    padded_right = right + (0,) * (width - len(right))
    if padded_left == padded_right:
        return True
    return (
        len(left) == len(right)
        and left[1:] == right[1:]
        and abs(left[0] - right[0]) == 2000
    )


def _year_version(value: Any) -> tuple[int, ...]:
    version = _numeric_version(value)
    if version and version[0] < 100:
        return (version[0] + 2000, *version[1:])
    return version


def _version_at_least(actual: Any, minimum: Any) -> bool:
    left = _year_version(actual)
    right = _year_version(minimum)
    if not left or not right:
        return False
    width = max(len(left), len(right))
    return left + (0,) * (width - len(left)) >= right + (0,) * (width - len(right))


def _application_version_status(
    requires: dict[str, Any],
    version: Any,
) -> tuple[bool, bool, str]:
    policy = requires.get("version_policy")
    if not isinstance(policy, dict):
        expected = requires.get("verified_version")
        matched = _version_matches(version, expected)
        return matched, matched, f"exact verified version {expected}"
    for incompatible in policy.get("known_incompatible") or []:
        if (
            isinstance(incompatible, dict)
            and _version_matches(version, incompatible.get("version"))
        ):
            return (
                False,
                False,
                "known incompatible with the pinned server: "
                + str(incompatible.get("reason") or "no compatible runtime profile"),
            )
    verified_versions = list(policy.get("verified_versions") or [])
    for verified in verified_versions:
        if _version_matches(version, verified):
            return True, True, f"verified version {verified}"
    minimum = policy.get("upstream_generation_from")
    if minimum and _version_at_least(version, minimum):
        return (
            True,
            False,
            f"upstream generation {minimum}+; build is not live-verified",
        )
    return (
        False,
        False,
        "outside verified versions and declared upstream generation",
    )


def _check_versions(
    modules: list[dict[str, Any]],
    profile: dict[str, Any],
    processes: list[dict[str, Any]],
) -> list[str]:
    record = profile["version_record"]
    warnings: list[str] = []
    for module in modules:
        requires = module["requires"]
        record_key = requires.get("version_record_key")
        recorded = record.get(record_key)
        supported, verified, reason = _application_version_status(
            requires, recorded
        )
        if not supported:
            raise CheckFailure(
                EXIT_VERSION,
                "APPLICATION_VERSION_MISMATCH",
                f"{module['display']} record '{recorded}' is {reason}",
            )
        process_versions = [
            process.get("version")
            for process in _module_processes(module, processes)
            if process.get("version")
        ]
        if process_versions and not any(
            _version_matches(version, recorded) for version in process_versions
        ):
            raise CheckFailure(
                EXIT_VERSION,
                "RUNNING_VERSION_MISMATCH",
                f"{module['display']} running version(s) {process_versions} "
                f"do not match version record {recorded}",
            )
        if not verified:
            warnings.append(
                f"{module['display']} {recorded}: {reason}. "
                "Upstream runtime attestation and stage 8 reads must pass."
            )
        server_key = requires.get("server_version_record_key")
        if server_key and not _version_matches(
            record.get(server_key), module["server"]["pinned"]
        ):
            raise CheckFailure(
                EXIT_VERSION,
                "SERVER_VERSION_MISMATCH",
                f"{module['display']} server pin does not match version record",
            )
    return warnings


def _check_runtime_version_warning(
    modules: list[dict[str, Any]], machine: dict[str, Any], profile: dict[str, Any]
) -> None:
    def collect_warnings(value: Any) -> list[Any]:
        found: list[Any] = []
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).casefold() in {"warning", "warnings"} and item:
                    found.append(item)
                found.extend(collect_warnings(item))
        elif isinstance(value, list):
            for item in value:
                found.extend(collect_warnings(item))
        return found

    for module in modules:
        if module["server"].get("package") != "openstaad-mcp":
            continue
        launch = _launch(module, machine, profile)
        try:
            with StdioMcpClient(
                str(launch["command"]),
                [str(value) for value in launch.get("args") or []],
                {
                    str(key): str(value)
                    for key, value in (launch.get("env") or {}).items()
                },
                timeout=float(module["_site"].get("tool_timeout_seconds", 30)),
            ) as client:
                client.initialize()
                payload = client.call_tool("list_instances", {})
        except (McpError, OSError, subprocess.SubprocessError) as exc:
            raise CheckFailure(
                EXIT_VERSION,
                "SERVER_VERSION_PROBE_FAILED",
                f"{module['display']} version probe failed: {exc}",
            ) from exc
        warnings = collect_warnings(payload)
        if warnings:
            text = json.dumps(warnings, ensure_ascii=False)
            if "mismatch" in text.casefold():
                raise CheckFailure(
                    EXIT_VERSION,
                    "SERVER_VERSION_MISMATCH_WARNING",
                    f"{module['display']} reported: {text}",
                )
        instances = payload.get("result") or payload.get("instances")
        if isinstance(instances, list) and len(instances) > 1:
            raise CheckFailure(
                EXIT_MODEL,
                "STAAD_INSTANCE_AMBIGUOUS",
                "More than one STAAD.Pro instance is available; select and record one before continuing",
            )


def _path_is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _check_allowed_directory(
    profile: dict[str, Any], machine: dict[str, Any]
) -> None:
    raw = str(profile.get("allowed_directory") or "")
    if not raw:
        raise CheckFailure(EXIT_DIRECTORY, "ALLOWED_DIRECTORY_MISSING", "No allowed_directory")
    if raw.startswith("\\\\"):
        raise CheckFailure(EXIT_DIRECTORY, "UNC_DIRECTORY", "Allowed directory must not be UNC")
    path = expand_path(raw)
    if not path.is_dir():
        raise CheckFailure(
            EXIT_DIRECTORY, "ALLOWED_DIRECTORY_MISSING", f"Directory does not exist: {path}"
        )
    roots = [
        Path(machine["known_folders"]["user_profile"]).resolve(strict=False),
        Path(machine["known_folders"]["local_app_data"]).resolve(strict=False),
    ]
    if any(path == root for root in roots):
        raise CheckFailure(
            EXIT_DIRECTORY,
            "PROFILE_ROOT_FORBIDDEN",
            f"Allowed directory must not be a profile root: {path}",
        )
    for share in profile.get("project_share_paths") or []:
        if _path_is_under(path, expand_path(str(share))):
            raise CheckFailure(
                EXIT_DIRECTORY,
                "PROJECT_SHARE_FORBIDDEN",
                f"Allowed directory is inside a declared project share: {path}",
            )
    for sync_root in machine.get("working_directory", {}).get("sync_roots", []):
        if _path_is_under(path, Path(sync_root).resolve(strict=False)):
            raise CheckFailure(
                EXIT_DIRECTORY,
                "SYNCED_DIRECTORY_FORBIDDEN",
                f"Allowed directory is inside a synced folder: {path}",
            )
    drive_type = 0
    if path.drive:
        try:
            probe = _run_powershell(
                f"[int](Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='{path.drive}'\").DriveType"
            )
        except AdapterError as exc:
            raise CheckFailure(
                EXIT_DIRECTORY,
                "DIRECTORY_PROBE_FAILED",
                f"Could not inspect allowed directory drive: {exc}",
            ) from exc
        drive_type = int(probe or 0)
    if drive_type == 4:
        raise CheckFailure(
            EXIT_DIRECTORY,
            "NETWORK_DRIVE_FORBIDDEN",
            f"Allowed directory is on a network drive: {path}",
        )
    try:
        with tempfile.NamedTemporaryFile(dir=path, prefix=".bentley-adapter-", delete=True):
            pass
    except OSError as exc:
        raise CheckFailure(
            EXIT_DIRECTORY,
            "ALLOWED_DIRECTORY_NOT_WRITABLE",
            f"Allowed directory is not writable: {path}",
        ) from exc


def _launch(module: dict[str, Any], machine: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    override = module["_site"].get("launch")
    source = override if isinstance(override, dict) else module["server"]["launch"]
    launch = resolve_tokens(source, machine, profile)
    if launch.get("command") in (None, "", "None"):
        raise CheckFailure(
            EXIT_TOOL, "SERVER_COMMAND_MISSING", f"No launch command for {module['display']}"
        )
    return launch


def _get_path(payload: dict[str, Any], dotted: str) -> Any:
    current: Any = payload
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _compare_expectations(
    module: dict[str, Any], call: dict[str, Any], payload: dict[str, Any]
) -> None:
    for key, expected in (call.get("expect") or {}).items():
        actual = _get_path(payload, key)
        if actual != expected:
            raise CheckFailure(
                EXIT_TOOL,
                "READ_PROBE_MISMATCH",
                f"{module['display']} {call['tool']}: expected {key}={expected!r}, got {actual!r}",
            )
    for key in call.get("expect_non_empty") or []:
        if _get_path(payload, key) in (None, "", [], {}):
            raise CheckFailure(
                EXIT_TOOL,
                "READ_PROBE_EMPTY",
                f"{module['display']} {call['tool']} returned empty {key}",
            )


def _check_tools(
    modules: list[dict[str, Any]], machine: dict[str, Any], profile: dict[str, Any]
) -> None:
    for module in modules:
        launch = _launch(module, machine, profile)
        try:
            with StdioMcpClient(
                str(launch["command"]),
                [str(value) for value in launch.get("args") or []],
                {str(key): str(value) for key, value in (launch.get("env") or {}).items()},
                timeout=float(module["_site"].get("tool_timeout_seconds", 30)),
            ) as client:
                client.initialize()
                tools = client.list_tools()
                for call in module.get("preflight") or []:
                    name = str(call["tool"])
                    if name not in tools:
                        raise CheckFailure(
                            EXIT_TOOL,
                            "TOOL_NOT_EXPOSED",
                            f"{module['display']} does not expose {name}",
                        )
                    payload = client.call_tool(name, call.get("arguments"))
                    _compare_expectations(module, call, payload)
        except CheckFailure:
            raise
        except (McpError, OSError, subprocess.SubprocessError) as exc:
            raise CheckFailure(
                EXIT_TOOL,
                "READ_PROBE_FAILED",
                f"{module['display']} read-only probe failed: {exc}",
            ) from exc


def _pass(stage: int, message: str) -> None:
    print(f"PASS {stage}: {message}")


def run_preflight(
    profile_path: Path,
    machine_path: Path,
    selected_module: str | None = None,
    skip_tool_calls: bool = False,
) -> int:
    try:
        profile = load_yaml(profile_path.resolve())
        validate_safe_profile(profile)
        machine = load_json(machine_path.resolve())
        modules = enabled_modules(profile)
        if selected_module:
            modules = [module for module in modules if module["id"] == selected_module]
            if not modules:
                raise AdapterError(f"Module is not enabled: {selected_module}")

        _machine_current(machine, profile)
        _pass(1, "machine.json present and current")
        _version_record_complete(profile)
        _pass(2, "version record complete")
        try:
            processes = _process_snapshot()
        except AdapterError as exc:
            raise CheckFailure(
                EXIT_APPLICATION,
                "PROCESS_PROBE_FAILED",
                f"Could not enumerate application processes: {exc}",
            ) from exc
        _check_processes(modules, processes)
        _pass(3, "required application processes running")
        _check_models(modules, processes)
        _pass(4, "models or projects open")
        _check_ports(modules, profile)
        _pass(5, "ports listening with expected process identity")
        version_warnings = _check_versions(modules, profile, processes)
        for warning in version_warnings:
            print(f"WARN 6: {warning}")
        if not skip_tool_calls:
            _check_runtime_version_warning(modules, machine, profile)
        if skip_tool_calls:
            _pass(6, "application and server pins match the version record; runtime warning probe skipped")
        else:
            _pass(6, "application and server pins match the version record")
        _check_allowed_directory(profile, machine)
        _pass(7, "allowed directory accepted")
        if skip_tool_calls:
            print("SKIP 8: read-only MCP calls explicitly skipped")
        else:
            _check_tools(modules, machine, profile)
            _pass(8, "read-only MCP calls matched expectations")
        if profile.get("local_provider"):
            if skip_tool_calls:
                print("SKIP 9: local-provider tool call explicitly skipped")
            else:
                try:
                    run_provider_preflight(profile)
                except ProviderPreflightError as exc:
                    raise CheckFailure(
                        EXIT_LOCAL_PROVIDER,
                        exc.code,
                        str(exc),
                    ) from exc
                except AdapterError as exc:
                    raise CheckFailure(
                        EXIT_LOCAL_PROVIDER,
                        "LOCAL_PROVIDER_INVALID",
                        str(exc),
                    ) from exc
                _pass(9, "local provider build, alias, and tool call verified")
        return 0
    except CheckFailure as exc:
        print(f"FAIL {exc.code}: {exc}")
        return exc.exit_code
