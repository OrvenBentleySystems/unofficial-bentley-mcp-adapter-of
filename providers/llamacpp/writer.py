from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import yaml

from core.common import AdapterError, expand_path, resolve_tokens
from core.emit.writer_api import RenderedArtifact
from core.provider_api import ProviderContext, ProviderPreflightError


def _header(context: ProviderContext, prefix: str = "#") -> str:
    return (
        f"{prefix} Generated artifact. Hand edits are overwritten.\n"
        f"{prefix} Source profile: {context.profile_path.resolve()}\n"
        f"{prefix} Generated at: {context.generated_at}\n"
    )


def _output(
    context: ProviderContext,
    key: str,
    default: Path,
) -> Path:
    configured = (context.profile.get("provider_outputs") or {}).get(key)
    if configured:
        resolved = resolve_tokens(
            str(configured), context.machine, context.profile
        )
        return expand_path(resolved)
    return default.resolve()


def render(context: ProviderContext):
    port = int(context.settings["port"])
    alias = str(context.settings["alias"])
    try:
        user_profile = Path(context.machine["known_folders"]["user_profile"])
    except (KeyError, TypeError) as exc:
        raise AdapterError(
            "machine.json has no known_folders.user_profile"
        ) from exc
    allowed_value = context.profile.get("allowed_directory")
    if not allowed_value:
        raise AdapterError("Profile has no allowed_directory")
    allowed = expand_path(
        resolve_tokens(str(allowed_value), context.machine, context.profile)
    )
    workspace_value = context.profile.get("workspace_root")
    workspace = (
        expand_path(
            resolve_tokens(
                str(workspace_value), context.machine, context.profile
            )
        )
        if workspace_value
        else Path.cwd().resolve()
    )
    host = str(context.settings.get("host") or context.descriptor["default_host"])
    base_url = f"http://{host}:{port}/v1"
    artifacts = []
    configured_targets = set(context.profile.get("targets") or {})
    supported_targets = set(context.descriptor.get("supported_targets") or {})
    skipped = sorted(configured_targets.intersection(supported_targets))

    jinja_flag = " --jinja" if context.descriptor.get("requires_jinja") else ""
    launch = (
        "llama-server --model <path-to-gguf> "
        f"--alias {alias} --n-gpu-layers 999 --ctx-size <n> "
        f"--port {port}{jinja_flag}"
    )
    artifacts.append(
        RenderedArtifact(
            path=_output(
                context,
                "launch",
                allowed / "llamacpp-provider.generated.txt",
            ),
            content=_header(context) + launch + "\n",
        )
    )

    targets = context.profile.get("targets") or {}
    if "codex" in targets and (user_profile / ".codex").is_dir():
        skipped.remove("codex")
        codex = (
            _header(context)
            + f'model = "{alias}"\n'
            + 'model_provider = "llamacpp"\n\n'
            + "[model_providers.llamacpp]\n"
            + 'name = "Local llama.cpp"\n'
            + f'base_url = "{base_url}"\n'
            + 'wire_api = "responses"\n'
        )
        artifacts.append(
            RenderedArtifact(
                path=_output(
                    context,
                    "codex",
                    user_profile
                    / ".codex"
                    / "llamacpp.bentley.generated.toml",
                ),
                content=codex,
                post_write_note=(
                    "Merge this fragment into user-level config.toml. Codex "
                    "llama.cpp uses a custom provider; the built-in --oss "
                    "endpoint override remains unverified."
                ),
            )
        )

    if "cline" in targets and (user_profile / ".cline").is_dir():
        skipped.remove("cline")
        instructions = (
            _header(context)
            + "Configure Cline through Settings > OpenAI Compatible.\n"
            + f"Base URL: {base_url}\n"
            + f"Model ID: {alias}\n"
            + "API key: <local-placeholder>\n"
            + "Do not select the Ollama provider.\n"
        )
        artifacts.append(
            RenderedArtifact(
                path=_output(
                    context,
                    "cline",
                    user_profile / ".cline" / "llamacpp-setup.generated.txt",
                ),
                content=instructions,
                post_write_note=(
                    "Cline provider state is UI-managed; no internal state "
                    "file was modified."
                ),
            )
        )

    if "kilocode" in targets and (user_profile / ".config" / "kilo").is_dir():
        skipped.remove("kilocode")
        kilo = {
            "$schema": "https://app.kilo.ai/config.json",
            "model": f"llamacpp/{alias}",
            "provider": {
                "llamacpp": {
                    "npm": "@ai-sdk/openai-compatible",
                    "models": {
                        alias: {
                            "name": alias,
                            "tool_call": True,
                        }
                    },
                    "options": {"baseURL": base_url},
                }
            },
        }
        content = _header(context, "//") + json.dumps(
            kilo, indent=2, ensure_ascii=False
        ) + "\n"
        artifacts.append(
            RenderedArtifact(
                path=_output(
                    context,
                    "kilocode",
                    user_profile
                    / ".config"
                    / "kilo"
                    / "llamacpp.bentley.generated.jsonc",
                ),
                content=content,
                post_write_note=(
                    "Merge this generated provider fragment into Kilo's "
                    "global config."
                ),
            )
        )

    if "continue" in targets and (workspace / ".continue").is_dir():
        skipped.remove("continue")
        block = {
            "name": "Bentley Local llama.cpp",
            "version": "0.0.1",
            "schema": "v1",
            "models": [
                {
                    "name": alias,
                    "provider": "openai",
                    "model": alias,
                    "apiBase": base_url,
                    "apiKey": "<local-placeholder>",
                    "capabilities": ["tool_use"],
                }
            ],
        }
        content = _header(context) + yaml.safe_dump(
            block, sort_keys=False, allow_unicode=True
        )
        artifacts.append(
            RenderedArtifact(
                path=_output(
                    context,
                    "continue",
                    workspace
                    / ".continue"
                    / "models"
                    / "llamacpp.bentley.generated.yaml",
                ),
                content=content,
            )
        )
    if artifacts and skipped:
        first = artifacts[0]
        artifacts[0] = RenderedArtifact(
            path=first.path,
            content=first.content,
            post_write_note=(
                "Skipped provider output for configured but undetected "
                "targets: " + ", ".join(skipped)
            ),
        )
    return artifacts


def _request_json(url: str, payload=None, timeout: float = 15):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1000]
        raise ProviderPreflightError(
            "LOCAL_MODEL_HTTP_ERROR",
            f"llama-server returned HTTP {exc.code} for {url}: {body}",
        ) from exc
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ProviderPreflightError(
            "LOCAL_MODEL_UNREACHABLE",
            f"llama-server request failed for {url}: {exc}",
        ) from exc


def preflight(settings, descriptor):
    host = str(settings.get("host") or descriptor["default_host"])
    if host not in {"127.0.0.1", "localhost"}:
        raise ProviderPreflightError(
            "LOCAL_MODEL_HOST_FORBIDDEN",
            "llama-server must use a loopback host",
        )
    port = int(settings.get("port") or descriptor["default_port"])
    alias = str(settings.get("alias") or "")
    if not alias:
        raise ProviderPreflightError(
            "LOCAL_MODEL_ALIAS_MISSING",
            "local_provider.alias is required",
        )
    root = f"http://{host}:{port}"
    props = _request_json(root + "/props")
    build = props.get("build_info")
    if not build:
        raise ProviderPreflightError(
            "LOCAL_MODEL_INVALID_PROPS",
            "llama-server /props returned no build_info",
        )
    models = _request_json(root + "/v1/models")
    ids = {
        item.get("id")
        for item in models.get("data", [])
        if isinstance(item, dict)
    }
    if alias not in ids:
        raise ProviderPreflightError(
            "LOCAL_MODEL_ALIAS_MISSING",
            f"llama-server /v1/models does not list alias '{alias}'"
        )
    payload = {
        "model": alias,
        "messages": [{"role": "user", "content": "Call the readiness tool."}],
        "tool_choice": "required",
        "parallel_tool_calls": False,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "adapter_readiness",
                    "description": "Return readiness.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ready": {"type": "boolean", "const": True}
                        },
                        "required": ["ready"],
                    },
                },
            }
        ],
    }
    response = _request_json(
        root + "/v1/chat/completions",
        payload,
        timeout=float(settings.get("request_timeout_seconds") or 120),
    )
    try:
        calls = response["choices"][0]["message"]["tool_calls"]
        function = calls[0]["function"]
        name = function["name"]
        arguments = json.loads(function["arguments"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        calls = []
        name = None
        arguments = {}
    if (
        not calls
        or name != "adapter_readiness"
        or arguments.get("ready") is not True
    ):
        raise ProviderPreflightError(
            "LOCAL_MODEL_NO_TOOL_CALL",
            "LOCAL_MODEL_NO_TOOL_CALL: llama-server returned no forced tool "
            "call. Check that --jinja is present and the GGUF template supports "
            "tool calling."
        )
    return {
        "provider": "llamacpp",
        "build": build,
        "alias": alias,
        "tool_call": True,
    }
