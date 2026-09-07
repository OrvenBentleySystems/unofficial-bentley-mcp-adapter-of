import json

import yaml

from core.emit.writer_api import (
    RenderedArtifact,
    TargetContext,
    generated_metadata,
    server_entries,
)


def render(context: TargetContext):
    servers, _ = server_entries(context)
    metadata = generated_metadata(context)
    yaml_servers = []
    fallback_servers = {}
    for module_id, entry in servers.items():
        yaml_entry = {
            "name": module_id,
            "type": "stdio",
            "command": entry["command"],
            "args": entry.get("args", []),
        }
        if entry.get("env"):
            yaml_entry["env"] = entry["env"]
        yaml_servers.append(yaml_entry)
        fallback_entry = {
            "type": "stdio",
            "command": entry["command"],
            "args": entry.get("args", []),
            "disabled": False,
            "autoApprove": [],
        }
        if entry.get("env"):
            fallback_entry["env"] = entry["env"]
        fallback_servers[module_id] = fallback_entry
    yaml_document = {
        "name": "Bentley MCP Servers",
        "version": "0.1.0",
        "schema": "v1",
        "mcpServers": yaml_servers,
        "x-bentley-adapter": metadata,
    }
    yaml_header = (
        "# Generated artifact. Hand edits are overwritten.\n"
        f"# Source profile: {metadata['source_profile']}\n"
        f"# Generated at: {metadata['generated_at']}\n"
    )
    yaml_content = yaml_header + yaml.safe_dump(
        yaml_document,
        sort_keys=False,
        allow_unicode=True,
    )
    fallback_document = {
        "_generated": metadata,
        "mcpServers": fallback_servers,
    }
    fallback_content = (
        json.dumps(fallback_document, indent=2, ensure_ascii=False) + "\n"
    )
    artifacts = [
        RenderedArtifact(
            path=context.output_path(),
            content=yaml_content,
            post_write_note=str(context.descriptor["restart_note"]),
        )
    ]
    if context.settings.get("fallback_output"):
        artifacts.append(
            RenderedArtifact(
                path=context.output_path("fallback_output"),
                content=fallback_content,
                post_write_note=(
                    "The JSON fallback is not auto-loaded. Move it into "
                    ".continue/mcpServers only if the YAML block is rejected."
                ),
            )
        )
    return artifacts
