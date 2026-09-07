from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.budget import calculate_budget
from core.common import (
    AdapterError,
    discover_provider_ids,
    discover_target_ids,
    load_json,
)
from core.emit import emit_configs
from core.detect import detect_environment, select_auto_targets
from core.context import emit_context
from core.preflight import run_preflight
from core.provider import emit_provider_configs
from core.resolve import resolve_machine
from core.uninstall import uninstall_generated


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bentley-adapter")
    commands = parser.add_subparsers(dest="command", required=True)

    resolve = commands.add_parser("resolve", help="Discover this Windows machine")
    resolve.add_argument("--output", type=Path, default=Path("machine.json"))
    resolve.add_argument("--working-directory", type=Path, default=Path.cwd())

    emit = commands.add_parser("emit", help="Generate MCP client configurations")
    emit.add_argument("--profile", type=Path, default=Path("profiles/site.yaml"))
    emit.add_argument("--machine", type=Path, default=Path("machine.json"))
    emit.add_argument("--target", choices=tuple(discover_target_ids()))
    emit.add_argument("--all", action="store_true")
    emit.add_argument("--auto", action="store_true")
    emit.add_argument("--detected", type=Path, default=Path("detected.json"))
    emit.add_argument("--dry-run", action="store_true")
    emit.add_argument("--provider", choices=tuple(discover_provider_ids()))
    emit.add_argument("--port", type=int)
    emit.add_argument("--alias")

    budget = commands.add_parser("budget", help="Estimate MCP tool catalogue size")
    budget.add_argument("--profile", type=Path, default=Path("profiles/site.yaml"))
    budget.add_argument("--tier", choices=("read", "guided", "full"), required=True)
    budget.add_argument("--client", choices=tuple(discover_target_ids()), required=True)

    preflight = commands.add_parser("preflight", help="Run ordered deployment checks")
    preflight.add_argument("--profile", type=Path, required=True)
    preflight.add_argument("--machine", type=Path, required=True)
    preflight.add_argument("--module")
    preflight.add_argument("--skip-tool-calls", action="store_true")

    detect = commands.add_parser("detect", help="Detect installed applications and clients")
    detect.add_argument("--profile", type=Path, default=Path("profiles/site.yaml"))
    detect.add_argument("--machine", type=Path, default=Path("machine.json"))
    detect.add_argument("--output", type=Path, default=Path("detected.json"))

    uninstall = commands.add_parser("uninstall", help="Remove generated MCP entries")
    uninstall.add_argument("--profile", type=Path, default=Path("profiles/site.yaml"))
    uninstall.add_argument("--detected", type=Path, default=Path("detected.json"))

    context = commands.add_parser("emit-context", help="Deliver harness instructions")
    context.add_argument("--profile", type=Path, default=Path("profiles/site.yaml"))
    context.add_argument("--detected", type=Path, default=Path("detected.json"))
    context.add_argument("--auto", action="store_true")
    context.add_argument("--target", choices=tuple(discover_target_ids()))
    context.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "resolve":
            result = resolve_machine(args.output, args.working_directory)
            print(f"Wrote {args.output.resolve()} for {result['host']['computer_name']}")
            return 0
        if args.command == "emit":
            has_targets = args.all or args.auto or bool(args.target)
            if sum(bool(value) for value in (args.all, args.auto, args.target)) > 1:
                raise AdapterError("Choose one of --all, --auto, or --target")
            if not has_targets and not args.provider:
                raise AdapterError("Choose --all, --target, or --provider")
            if has_targets:
                if args.auto:
                    detected = load_json(args.detected.resolve())
                    targets, skipped = select_auto_targets(detected)
                    for item in skipped:
                        print(
                            f"SKIP {item['id']}: {item['reason']}",
                            file=sys.stderr,
                        )
                    if not targets:
                        raise AdapterError(
                            "No verified writable client was detected. "
                            "Install a supported client, then rerun detect."
                        )
                else:
                    targets = None if args.all else [args.target]
                result = emit_configs(
                    args.profile,
                    args.machine,
                    targets,
                    args.dry_run,
                    merge_existing=args.auto,
                )
                if result:
                    return result
            if args.provider:
                return emit_provider_configs(
                    args.profile,
                    args.machine,
                    args.provider,
                    args.port,
                    args.alias,
                    args.dry_run,
                )
            return 0
        if args.command == "preflight":
            return run_preflight(
                args.profile,
                args.machine,
                selected_module=args.module,
                skip_tool_calls=args.skip_tool_calls,
            )
        if args.command == "budget":
            import json

            print(
                json.dumps(
                    calculate_budget(args.profile, args.tier, args.client),
                    indent=2,
                )
            )
            return 0
        if args.command == "detect":
            result = detect_environment(args.profile, args.machine, args.output)
            print(f"Wrote {args.output.resolve()}")
            for client in result["clients"]:
                state = "detected" if client["present"] else "absent"
                print(
                    f"{client['id']}: {state}; {client['status']}; "
                    f"writable={client['writable']}"
                )
            return 0
        if args.command == "uninstall":
            for result in uninstall_generated(args.profile, args.detected):
                print(
                    f"{result['client']}: {result['action']} ({result['path']})"
                )
            return 0
        if args.command == "emit-context":
            emit_context(
                args.profile,
                args.detected,
                args.auto,
                args.target,
                args.dry_run,
            )
            return 0
    except AdapterError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2
