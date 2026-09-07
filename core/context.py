from __future__ import annotations

from pathlib import Path
from typing import Any

from core.common import (
    AdapterError,
    INSTALLED_DATA_ROOT,
    ROOT,
    expand_path,
    load_json,
    load_target,
    load_yaml,
    output_roots,
    resolve_tokens,
    utc_now,
)
from core.detect import select_auto_targets
from core.emit.emitter import _write_artifact
from core.emit.writer_api import RenderedArtifact


DOCS_DIR = (
    ROOT / "docs"
    if (ROOT / "docs").is_dir()
    else INSTALLED_DATA_ROOT / "docs"
)


def _context_content(profile_path: Path) -> str:
    harness_path = DOCS_DIR / "harness.md"
    skill_path = DOCS_DIR / "skill.md"
    try:
        harness = harness_path.read_text(encoding="utf-8").rstrip()
        skill = skill_path.read_text(encoding="utf-8").rstrip()
    except FileNotFoundError as exc:
        raise AdapterError(f"Context source file missing: {exc.filename}") from exc
    return (
        "<!-- Generated artifact. Hand edits are overwritten. -->\n"
        f"<!-- Source profile: {profile_path.resolve()} -->\n"
        f"<!-- Generated at: {utc_now()} -->\n\n"
        f"{harness}\n\n---\n\n{skill}\n"
    )


def emit_context(
    profile_path: Path,
    detected_path: Path,
    auto: bool,
    target_id: str | None = None,
    dry_run: bool = False,
) -> list[Path]:
    if auto == bool(target_id):
        raise AdapterError("Choose exactly one of --auto or --target")
    profile_path = profile_path.resolve()
    profile = load_yaml(profile_path)
    detected = load_json(detected_path.resolve())
    machine_path = detected.get("machine_path")
    if not machine_path:
        raise AdapterError("detected.json has no machine_path")
    machine = load_json(Path(str(machine_path)))
    roots = output_roots(profile, machine, profile_path)
    if auto:
        selected, skipped = select_auto_targets(detected)
        for item in skipped:
            print(f"SKIP {item['id']}: {item['reason']}")
    else:
        selected = [str(target_id)]
    content = _context_content(profile_path)
    written: list[Path] = []
    seen: set[Path] = set()
    for selected_id in selected:
        descriptor = load_target(selected_id)
        raw_paths = descriptor.get("instruction_paths") or []
        if not raw_paths:
            print(f"SKIP {selected_id}: no instruction path is declared")
            continue
        for raw_path in raw_paths:
            resolved = expand_path(
                resolve_tokens(str(raw_path), detected, profile)
            )
            if resolved in seen:
                continue
            seen.add(resolved)
            _write_artifact(
                RenderedArtifact(path=resolved, content=content),
                dry_run,
                allowed_roots=roots,
            )
            written.append(resolved)
    return written
