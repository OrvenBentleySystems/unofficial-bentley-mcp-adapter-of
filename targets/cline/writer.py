import json

from core.emit.writer_api import (
    RenderedArtifact,
    TargetContext,
    generated_metadata,
    server_entries,
)


def render(context: TargetContext):
    servers, _ = server_entries(context)
    for entry in servers.values():
        entry["disabled"] = False
        entry["autoApprove"] = []
    document = {
        "_generated": generated_metadata(context),
        str(context.descriptor["root_key"]): servers,
    }
    content = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    paths = [context.output_path()]
    if context.settings.get("cli_output"):
        cli_path = context.output_path("cli_output")
        if cli_path not in paths:
            paths.append(cli_path)
    return [
        RenderedArtifact(
            path=path,
            content=content,
            post_write_note=str(context.descriptor["restart_note"]),
            merge_kind="json_object",
            merge_root=str(context.descriptor["root_key"]),
        )
        for path in paths
    ]
