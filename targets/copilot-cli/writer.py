from core.emit.writer_api import (
    RenderedArtifact,
    TargetContext,
    render_standard_json,
)


def render(context: TargetContext):
    artifact = render_standard_json(context)[0]
    return [
        RenderedArtifact(
            path=artifact.path,
            content=artifact.content,
            post_write_note=artifact.post_write_note,
            merge_kind="json_object",
            merge_root="mcpServers",
        )
    ]
