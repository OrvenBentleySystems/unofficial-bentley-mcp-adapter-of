from core.emit.writer_api import TargetContext, render_standard_json


def render(context: TargetContext):
    artifacts = render_standard_json(context)
    artifact = artifacts[0]
    return [
        type(artifact)(
            path=artifact.path,
            content=artifact.content,
            post_write_note=str(context.descriptor["restart_note"]),
        )
    ]

