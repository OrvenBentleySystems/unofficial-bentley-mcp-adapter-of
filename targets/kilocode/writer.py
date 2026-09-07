import json

from core.emit.writer_api import (
    RenderedArtifact,
    TargetContext,
    generated_metadata,
    server_entries,
)


def render(context: TargetContext):
    servers, _ = server_entries(context)
    kilo_servers = {}
    for module_id, entry in servers.items():
        server = {
            "type": "local",
            "command": [entry["command"], *entry.get("args", [])],
            "enabled": True,
        }
        if entry.get("env"):
            server["environment"] = entry["env"]
        kilo_servers[module_id] = server
    document = {
        "_generated": generated_metadata(context),
        str(context.descriptor["root_key"]): kilo_servers,
    }
    content = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    paths = [context.output_path()]
    if context.settings.get("global_output"):
        global_path = context.output_path("global_output")
        if global_path not in paths:
            paths.append(global_path)
    return [
        RenderedArtifact(
            path=path,
            content=content,
            post_write_note=str(context.descriptor["restart_note"]),
        )
        for path in paths
    ]

