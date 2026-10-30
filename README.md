# Unofficial Bentley MCP Adapter

Let any AI agent control Bentley desktop software. `bentley_mcp` is a local MCP server that drives
a running MicroStation or OpenBuildings Designer through direct Windows COM — no Bentley Copilot,
no Feature Token, no cloud round-trip.

```
agent (VS Code · Claude · Cursor · any MCP client)
  └─ stdio (default)  ·  http://127.0.0.1:18131/mcp (optional, loopback only)
      └─ bentley_mcp
          └─ COM: MicroStationDGN.Application
              └─ MicroStation 2026 · OpenBuildings Designer 2024
```

## Try it (5 minutes)

```powershell
cd adapter
uv sync                          # needs uv; Python 3.11–3.13
```

Open MicroStation with a DGN, then point your client at the bridge:

```json
{
  "mcpServers": {
    "bentley": {
      "command": "C:\\mcp-bridge\\adapter\\.venv\\Scripts\\python.exe",
      "args": ["-m", "bentley_mcp.server"]
    }
  }
}
```

Ask the agent: *list the models, draw a line from [0,0,0] to [10,0,0], add text, save the file.*

Other clients: [docs/clients/](docs/clients). HTTP mode: `pwsh scripts\start-bentley.ps1`
(stop: `stop-bentley.ps1`).

## Tools (19)

| Group | Tools |
|---|---|
| Discover | `list_apps` `get_status` `com_get` |
| Session | `launch_app` |
| Design files | `open_design` `save_design` |
| Structure | `list_models` `list_levels` `set_active_model` |
| Geometry | `create_line` `create_polyline` `create_text` `create_batch` |
| Elements | `list_elements` `delete_element` † |
| Escape hatches | `run_keyin` † `run_python` † `python_result` |
| Views | `fit_view` |

† require `confirm=true`. Full reference: [docs/BENTLEY-MCP.md](docs/BENTLEY-MCP.md) ·
Routing policy (COM-first; Copilot MCP as documented gap-filler): [docs/ROUTING.md](docs/ROUTING.md).

Resource-capable clients can also read live state without tool calls: `bentley://status`,
`bentley://models`, `bentley://levels` (JSON; report `{"error": …}` instead of failing when no
app is running).

## SYNCHRO 4D (second server)

Scheduling-side access via `synchro-mcp/` (Node, zero dependencies): `synchro_script` emits
SYNCHRO's documented phrase-script files for bulk operations on the open project (user
Preview/Run in-app, undoable), and `synchro_status` reports the bundled headless SDK
(`synchrojs` native addon — loads in plain Node; builds `.sp` files without the GUI).
Honest capability map and grammar: [docs/SYNCHRO-MCP.md](docs/SYNCHRO-MCP.md).

```json
{ "mcpServers": { "synchro": { "command": "node", "args": ["C:\\mcp-bridge\\synchro-mcp\\server.js"] } } }
```

## Why COM instead of Copilot's MCP server?

Works with any agent, needs no Evergreen update, has no Feature Token dependency (Copilot MCP,
its Python execution and Display Rules stop working after 1 May 2027), gives deterministic typed
tools with confirm-gates on destructive calls, and stays on localhost. Where the Copilot-bundled
MCP server genuinely adds capability, mount it alongside per [docs/ROUTING.md](docs/ROUTING.md).

## Verified

- MicroStation 2026 (26.00.02.39): all 16 tools; live smoke 2026-10-27, capture re-verified 2026-10-28
- OpenBuildings Designer 2024 (24.00.03.14): DGN element scope only (no parametric objects)
- Unit tests: `uv run pytest -q` (32 pass) · live probe: `uv run python tests\bentley_baseline.py`
- Gotchas: one Bentley instance at a time (shared COM ProgID; a second is invisible to COM);
  MicroStation must be running with a DGN open — start it yourself, COM auto-launch would cold-start
  OpenBuildings; **startup can ignore the file argument and restore the last design — check
  `get_status` before writing anywhere**; non-workset files raise a modal WorkSet prompt (and can
  open Read-Only) until dismissed;
  MicroStation's embedded Python runs only the **first** `python execute` per app session
  (26.00.02.39) — batch whole jobs into one `run_python` call

## Repository layout

| Path | What |
|---|---|
| `adapter/src/bentley_mcp/` | the COM bridge — primary component |
| `synchro-mcp/` | SYNCHRO 4D server (script channel + headless SDK status) |
| `adapter/src/staad_mcp_gateway/` | secondary: authenticated read-only STAAD gateway |
| `adapter/tests/` | unit tests and live probes |
| `scripts/` | PowerShell 7: start/stop, preflight, validate, provision |
| `docs/` | bridge reference, routing, security, runbook, decisions, evidence, client samples |

## STAAD gateway (secondary component)

An authenticated, read-only MCP gateway in front of Bentley's unmodified
[openstaad-mcp](https://github.com/BentleySystems/openstaad-mcp) (pinned v26.0.0.107), plus a
Microsoft 365 Copilot declarative agent ("STAAD Assistant"). Status: partially proven —
provisioning is blocked on Entra app registration in this tenant
([docs/RUNBOOK.md](docs/RUNBOOK.md#blocker-entra-app-registration)). Independent of the Bentley
bridge; `pwsh scripts\preflight.ps1` gates both.

## Disclaimer

Unofficial. Not a Bentley product and not endorsed by Bentley Systems. Bentley, MicroStation,
OpenBuildings and STAAD.Pro are trademarks of Bentley Systems.
