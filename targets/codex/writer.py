import json

from core.emit.writer_api import (
    RenderedArtifact,
    TargetContext,
    generated_metadata,
    server_entries,
)


def _toml_string(value):
    return json.dumps(str(value), ensure_ascii=False)


def _toml_array(values):
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def render(context: TargetContext):
    servers, inputs = server_entries(context)
    metadata = generated_metadata(context)
    lines = [
        "# Generated artifact. Hand edits are overwritten.",
        f"# Source profile: {metadata['source_profile']}",
        f"# Generated at: {metadata['generated_at']}",
    ]
    for module_id, pins in metadata["pins"].items():
        lines.append(
            f"# Pin {module_id}: descriptor={pins['descriptor']}, "
            f"server={pins['server']}, application={pins['application']}"
        )
    lines.append("")
    for module_id, entry in servers.items():
        lines.extend(
            (
                f'[mcp_servers.{_toml_string(module_id)}]',
                f"command = {_toml_string(entry['command'])}",
                f"args = {_toml_array(entry.get('args', []))}",
                'default_tools_approval_mode = "writes"',
            )
        )
        tools = entry.get("tools")
        if tools:
            lines.append(f"enabled_tools = {_toml_array(tools)}")
        env = entry.get("env")
        if env:
            lines.append("")
            lines.append(f'[mcp_servers.{_toml_string(module_id)}.env]')
            for key, value in env.items():
                lines.append(f"{_toml_string(key)} = {_toml_string(value)}")
        lines.append("")
    return [
        RenderedArtifact(
            path=context.output_path(),
            content="\n".join(lines).rstrip() + "\n",
            post_write_note=str(context.descriptor["restart_note"]),
            merge_kind="toml_mcp",
            merge_root="mcp_servers",
        )
    ]
