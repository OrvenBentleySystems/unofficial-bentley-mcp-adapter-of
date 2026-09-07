# Handover

## Built

- Python 3.13 package with stdlib plus PyYAML.
- `core.resolve`: Windows known-folder, registry, executable, privilege,
  long-path, sync-root, MicroStation bundle, and PLAXIS profile discovery.
- Four independent module descriptors: MicroStation, STAAD.Pro, PLAXIS 2D
  Input, and PLAXIS 2D Output.
- Capability policy with Read, Guided write, and Full tiers.
- `core.emit`: ten discovered client writers, generated metadata, pinned
  versions, secret input references where supported, preservation notices, and
  unified-diff dry-run.
- `core.preflight`: eight required checks plus optional local-provider stage 9,
  with distinct exit codes, process and model separation, listener owner
  identity, collision diagnosis, version checks, allowed-directory controls,
  and stdio MCP read probes.
- Installation, port, troubleshooting, and machine-variance documentation.
- Unit tests for tiers, version records, model-open checks, port identity, port
  collision, generated pins, and secret input references.

No gateway, tunnel, remote transport, WSL, or Docker path is included.

## Evidence status

### Verified on the operator machine

| Item | Result |
|---|---|
| MicroStation | 2026.1 build 26.00.01.65, live MCP read previously passed |
| STAAD.Pro | 2026 version 26.0.0.340, live OpenSTAAD read previously passed |
| PLAXIS 2D | 2023.2.1.1079 with plaxis-mcp 0.3.5, live Input reads previously passed |
| Port map | 2D Input 10000 and 3D Input 10002 |
| Resolver | Passed on the operator machine; dotted username, known folders, non-hardcoded bundle path, registry versions, Node.js, uv, Python 3.13, long paths, and sync root recorded |
| Emitters | Passed dry-run and write for both dialects to session artifacts; pins and generated metadata present; no secret values |
| Unit suite | Passed, 14 frozen baseline tests and 27 additive tests |
| Wheel | Built and installed non-editably in an isolated Python 3.13 environment; module and target data loaded |
| Full adapter preflight | Passed all eight ordered stages with live read-only calls to MicroStation, STAAD.Pro, and PLAXIS 2D Input |
| Skip mode | Passed stages 1 to 7 without launching MCP servers; stage 8 reported skipped |

### Chosen conventions

- PLAXIS ports 10000 through 10003.
- Capability tier definitions and allowlists.
- Generated JSON metadata under `_generated`.
- Exit codes 10 through 17 for ordered preflight failures.
- Twenty-four hour default lifetime for `machine.json`.

### Unverified

- VS Code support for a server-side tool allowlist.
- Second clean-machine resolver behavior.
- PLAXIS 2D Output live connection on this machine.
- A production signed `plaxis-mcp.exe` path on this machine.

## TODOs and closing evidence

| TODO | File or evidence that closes it |
|---|---|
| Identify the two client-local MicroStation tools not present in the 23-name cache | Live `tools/list` output plus `%LOCALAPPDATA%\Bentley\McpBridge\Config\microstation-tools.json` |
| Determine a supported VS Code mechanism for enforcing capability allowlists | VS Code MCP schema or client documentation; until then no automatic approval is emitted, but the server catalogue is not reduced |
| Verify resolver on a clean second Windows machine | That machine's generated `machine.json` and Stage 1 run log |
| Verify PLAXIS 2D Output descriptor and port 10001 | Output application `connection_status`, `project_info`, and `list_result_types` results |
| Confirm OpenSTAAD 1.2.0 is installed or cached for offline launch | `openstaad-mcp --help`, package provenance, and passing preflight |
| Replace the live validation override that points into a uv cache | A stable pinned OpenSTAAD executable or `.mcpb` deployment path |
| Decide whether `list_phases` should accept a project with no staged phases | A target PLAXIS project with staged construction plus recorded tool output |
| Replace example version-record TODO values | Operator-completed `profiles/site.yaml` |

## Stage 0 to 3 exit tests

| Stage | Exit test | Recorded result |
|---|---|---|
| 0 | Complete version record, three passing reads, generated `machine.json` | Passed on the operator machine using the session-scoped live profile. The distributable example intentionally contains TODO values. |
| 1 | Correct resolver output on operator and one clean second machine, no hardcoded paths | Partial. Passed on the operator machine, including the dotted account name. A clean second machine has not been run. |
| 2 | Emit Copilot and VS Code from one profile, register all servers, pass both clients without hand edits, explain Copilot diff | Passed for the three enabled baseline servers. The exact generated VS Code file is installed and each server returned its status/read call. The Copilot diff is explained below. |
| 3 | Reproduce blank STAAD, PLAXIS collision, and path variance diagnostics | Passed in automated fault fixtures, with the prior live collision as corroborating evidence. A destructive live collision was not repeated. |

## Copilot configuration differences

The generated Copilot file differs deliberately from the previously working
hand-written file:

- It uses the module id `staadpro`; the hand-written entry used `openstaad`.
- It emits Read-tier allowlists instead of `tools: ["*"]`.
- It records descriptor, server, and application pins plus the source profile
  and generation time.
- The distributable OpenSTAAD descriptor pins release 1.2.0 and uses offline
  `uvx`. The live validation profile temporarily used the already running
  executable from the uv cache because release provenance for that cache entry
  is not established.
- It targets the actual client filename
  `%USERPROFILE%\.copilot\mcp-config.json`. The live proof wrote to a
  session-scoped artifact so the operator's active config was not replaced.

## Limits

The adapter verifies configuration and connectivity. It does not validate
engineering correctness. Results require review by a qualified engineer.

MicroStation MCP is early access. Verification applies only to the recorded
build and client. PLAXIS-MCP is independent software without Bentley or
Seequent support. OpenSTAAD executes code through a guarded sandbox whose own
documentation describes further hardening as work in progress.

The llama.cpp provider is not live-verified. No `llama-server` executable or
process was detected. Stage 9 and provider outputs are covered by deterministic
tests only.

Provider guidance was emitted for the detected Codex and Cline locations.
Codex received an adapter-owned custom-provider fragment. Cline received UI
instructions only because its internal provider state is not a documented
external configuration contract. Full-tier provider emission was refused, and
an actual local-provider preflight stopped at stage 9 with
`LOCAL_MODEL_UNREACHABLE` because no process listened on port 8080.

## Publication cleanup

- `baseline.txt` records the frozen preflight, test, config, wheel, entry-point,
  and installation contract.
- `cleanup-inventory.md` records every pre-cleanup file and its disposition.
- Live `machine.json`, generated distributions, local environments, and Python
  caches were removed. `machine.example.json` is the public schema example.
- The final clean-copy replay passed all eight required preflight stages, all
  14 baseline tests plus additive tests, byte-identical deterministic configs,
  all 24 original wheel entries plus recorded additions, the original console
  entry point, MIT package metadata, and wheel install.
- The source folder had no `.git` directory. No commit history existed to
  inspect, and no history was rewritten.

## Stage 4 target discovery

- Runtime discovery now scans `targets/` for folders containing `target.yaml`
  and `writer.py`.
- The two existing target writers moved behind that interface with
  byte-identical output.
- No target id remains in `core/`.
- A temporary third target was discovered and emitted in the test suite
  without editing `core/`.
- The wheel retains all 24 original entries and adds 29 files for target
  writers, provider support, detection, uninstall, context delivery, and
  packaged documentation. The exact additions are recorded in `baseline.txt`.

## Stage 4 client writers

| Target | Output shape | Machine status |
|---|---|---|
| GitHub Copilot CLI/app | `mcpServers` JSON | Verified client family from the baseline |
| VS Code Copilot | `servers` JSON | Verified |
| Codex | TOML `[mcp_servers.<name>]` | Verified |
| Claude Code | `mcpServers` JSON | Verified |
| Claude Desktop | `mcpServers` JSON | Not detected |
| Cline | `mcpServers` JSON with empty `autoApprove` | Verified |
| Kilo Code | Current `mcp` JSONC with command arrays | Not detected |
| Cursor | `mcpServers` JSON | Not detected |
| OpenCode | Current `mcp` JSON/JSONC with command arrays | Not detected |
| Continue | YAML `mcpServers` array plus opt-in JSON fallback | Not detected |

All eight new writer shapes have automated tests. None is marked live-verified
merely because its file format passed. Hand-written whole-application configs
are preserved; generated content is written to a `.bentley.generated` sibling.
Continue's JSON fallback is outside `.continue/mcpServers` so it cannot
double-register the same servers.

Generated configurations for VS Code, Codex, Claude Code, and Cline were
installed with unrelated settings preserved. Each configuration launched
MicroStation, STAAD.Pro, and PLAXIS 2D Input and returned the expected
read/status call. The recorded tool counts were 25, 5, and 34 respectively.
