import json

from core.emit.writer_api import (
    RenderedArtifact,
    TargetContext,
    generated_metadata,
    server_entries,
)


def render(context: TargetContext):
    servers, _ = server_entries(context)
    opencode_servers = {}
    for module_id, entry in servers.items():
        server = {
            "type": "local",
            "command": [entry["command"], *entry.get("args", [])],
            "enabled": True,
        }
        if entry.get("env"):
            server["environment"] = entry["env"]
        opencode_servers[module_id] = server
    metadata = generated_metadata(context)
    document = {
        "$schema": "https://opencode.ai/config.json",
        str(context.descriptor["root_key"]): opencode_servers,
    }
    header = (
        "// Generated artifact. Hand edits are overwritten.\n"
        f"// Source profile: {metadata['source_profile']}\n"
        f"// Generated at: {metadata['generated_at']}\n"
    )
    for module_id, pins in metadata["pins"].items():
        header += (
            f"// Pin {module_id}: descriptor={pins['descriptor']}, "
            f"server={pins['server']}, application={pins['application']}\n"
        )
    content = header + json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    return [
        RenderedArtifact(
            path=context.output_path(),
            content=content,
            post_write_note=str(context.descriptor["restart_note"]),
        )
    ]
