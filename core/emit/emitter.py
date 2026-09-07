from __future__ import annotations

import difflib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

from core.common import (
    AdapterError,
    atomic_write_text,
    discover_target_ids,
    enabled_modules,
    enforce_local_provider_tier,
    load_json,
    load_target,
    load_yaml,
    output_roots,
    utc_now,
    validate_machine_identity,
    validate_output_path,
    validate_safe_profile,
)
from core.emit.writer_api import RenderedArtifact, TargetContext


def _load_writer(target: dict[str, object]) -> ModuleType:
    target_id = str(target["id"])
    path = Path(str(target["_directory"])) / "writer.py"
    module_name = "_bentley_adapter_target_" + "".join(
        character if character.isalnum() else "_"
        for character in target_id
    )
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AdapterError(f"Cannot load target writer: {path}")
    writer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(writer)
    if not callable(getattr(writer, "render", None)):
        raise AdapterError(f"Target writer has no render(context) function: {path}")
    return writer


def _diff(path: Path, generated: str) -> str:
    current = path.read_text(encoding="utf-8") if path.is_file() else ""
    return "".join(
        difflib.unified_diff(
            current.splitlines(keepends=True),
            generated.splitlines(keepends=True),
            fromfile=str(path),
            tofile=f"{path} (generated)",
        )
    )


def _managed_output_path(path: Path) -> Path:
    if not path.is_file():
        return path
    try:
        existing = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        existing = ""
    if "Generated artifact. Hand edits are overwritten." in existing:
        return path
    suffix = "".join(path.suffixes)
    stem = path.name[: -len(suffix)] if suffix else path.name
    return path.with_name(f"{stem}.bentley.generated{suffix}")


def _merge_json_object(artifact: RenderedArtifact, current: str) -> str:
    existing = json.loads(current)
    generated = json.loads(artifact.content)
    root = artifact.merge_root
    if not root or not isinstance(existing, dict) or not isinstance(generated, dict):
        raise AdapterError("JSON merge requires object documents and merge_root")
    existing_servers = existing.setdefault(root, {})
    generated_servers = generated.get(root)
    if not isinstance(existing_servers, dict) or not isinstance(generated_servers, dict):
        raise AdapterError(f"Cannot merge non-object key '{root}'")
    existing_servers.update(generated_servers)
    metadata = dict(generated.get("_generated") or {})
    metadata["notice"] = (
        "Bentley MCP Adapter generated entries. Surrounding settings are preserved."
    )
    metadata["merge_mode"] = "entries"
    existing["_generated"] = metadata
    return json.dumps(existing, indent=2, ensure_ascii=False) + "\n"


def _merge_toml_mcp(artifact: RenderedArtifact, current: str) -> str:
    marker = "# Bentley MCP Adapter generated entries. Surrounding settings are preserved."
    generated_only_marker = "# Generated artifact. Hand edits are overwritten."
    for owned_marker in (marker, generated_only_marker):
        if owned_marker in current:
            current = current.split(owned_marker, 1)[0].rstrip()
    generated = artifact.content.replace(
        "# Generated artifact. Hand edits are overwritten.",
        marker,
        1,
    )
    return current.rstrip() + "\n\n" + generated.lstrip()


def _merged_content(artifact: RenderedArtifact) -> str:
    current = artifact.path.read_text(encoding="utf-8")
    if artifact.merge_kind == "json_object":
        return _merge_json_object(artifact, current)
    if artifact.merge_kind == "toml_mcp":
        return _merge_toml_mcp(artifact, current)
    raise AdapterError(f"Unsupported merge kind: {artifact.merge_kind}")


def _write_artifact(
    artifact: RenderedArtifact,
    dry_run: bool,
    merge_existing: bool = False,
    allowed_roots: list[Path] | None = None,
) -> None:
    if allowed_roots is not None:
        validated = validate_output_path(artifact.path, allowed_roots)
        artifact = RenderedArtifact(
            path=validated,
            content=artifact.content,
            post_write_note=artifact.post_write_note,
            merge_kind=artifact.merge_kind,
            merge_root=artifact.merge_root,
        )
    content = artifact.content
    if merge_existing and artifact.path.is_file() and artifact.merge_kind:
        output_path = artifact.path
        content = _merged_content(artifact)
    else:
        output_path = _managed_output_path(artifact.path)
    if allowed_roots is not None:
        output_path = validate_output_path(output_path, allowed_roots)
    if output_path != artifact.path:
        print(
            f"Preserving hand-written file {artifact.path}; "
            f"writing generated content to {output_path}.",
            file=sys.stderr,
        )
    if dry_run:
        difference = _diff(output_path, content)
        print(difference or f"No changes for {output_path}")
        return
    if output_path.exists():
        print(
            f"Overwriting generated artifact {output_path}; "
            "hand edits are not preserved.",
            file=sys.stderr,
        )
    else:
        print(
            f"Writing generated artifact {output_path}; "
            "future runs replace hand edits.",
            file=sys.stderr,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output_path, content)
    print(f"Wrote {output_path}")
    if artifact.post_write_note:
        print(artifact.post_write_note)


def emit_configs(
    profile_path: Path,
    machine_path: Path,
    targets: list[str] | None,
    dry_run: bool,
    merge_existing: bool = False,
) -> int:
    profile_path = profile_path.resolve()
    profile = load_yaml(profile_path)
    validate_safe_profile(profile)
    machine = load_json(machine_path.resolve())
    validate_machine_identity(machine)
    modules = enabled_modules(profile)
    enforce_local_provider_tier(profile, modules)
    roots = output_roots(profile, machine, profile_path)
    target_settings = profile.get("targets")
    if not isinstance(target_settings, dict):
        raise AdapterError("Profile has no targets mapping")
    discovered = set(discover_target_ids())
    selected = list(target_settings) if targets is None else targets
    for target_id in selected:
        if target_id not in discovered:
            raise AdapterError(f"Target is not installed: {target_id}")
        settings = target_settings.get(target_id)
        if not isinstance(settings, dict):
            raise AdapterError(f"Profile has no settings for target {target_id}")
        descriptor = load_target(target_id)
        writer = _load_writer(descriptor)
        context = TargetContext(
            target_id=target_id,
            descriptor=descriptor,
            settings=settings,
            profile_path=profile_path,
            profile=profile,
            machine=machine,
            modules=modules,
            generated_at=utc_now(),
        )
        artifacts = writer.render(context)
        if not isinstance(artifacts, list) or not all(
            isinstance(artifact, RenderedArtifact) for artifact in artifacts
        ):
            raise AdapterError(
                f"Target writer {target_id} must return list[RenderedArtifact]"
            )
        if not artifacts:
            raise AdapterError(f"Target writer {target_id} returned no artifacts")
        for artifact in artifacts:
            _write_artifact(
                artifact,
                dry_run,
                merge_existing=merge_existing,
                allowed_roots=roots,
            )
    return 0
