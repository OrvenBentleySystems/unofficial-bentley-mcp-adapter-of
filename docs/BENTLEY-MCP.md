# Bentley MCP bridge (MicroStation / OpenBuildings)

A local MCP server in `adapter/src/bentley_mcp` that controls the running Bentley desktop app
through direct COM. It does not use Bentley Copilot, an MCP proxy, or REA, and it does not affect
the STAAD gateway.

```
MCP client ─► stdio (default)  or  http://127.0.0.1:18131/mcp
           ─► bentley_mcp ─► MicroStationDGN.Application ─► MicroStation or OpenBuildings
```

**Status: live-verified on this workstation** with MicroStation 2026 (26.00.02.39) and
OpenBuildings Designer 2024 (24.00.03.14). Full 15-tool pass on 2026-10-27 against a scratch DGN:
attach, status, open, models, levels, model activation, line, polyline, text, element query,
element delete (confirm-gated), python execute, save, fit, stdio, and loopback HTTP with bearer
auth. Re-verified 2026-10-28 after the element-tool rewrite (unique ids, exact delete targeting).
Live COM facts: `ModelReference` has no `Elements` collection — enumerate
`ModelReference.GraphicalElementCache` with `GetElement(1..Count)` and read `Element.ID64`
(do **not** id-scan: `GetElementByID64` resolves missing ids to a *different* element);
models activate with `ModelReference.Activate()`; `CreateTextElement1(None, text, origin)`
returns `[Point3d, Matrix3d, TextElement]` (element is last); `cache.Count` keeps deleted
elements until the model is rewritten — filter with `Element.IsDeleted`.

## Prerequisites

* Windows with MicroStation or OpenBuildings Designer installed and licensed.
* The application is already running with a **DGN open**.
* OpenBuildings must be started with a DGN from its active workset. A start page with no design
  file does not register the automation object.
* Run **one product at a time**. MicroStation and OpenBuildings both expose
  `MicroStationDGN.Application`; the bridge attaches to whichever process currently owns it.
* OpenBuildings' own `Bentley.OpenBuildingsDesigner.Application` ProgID is registered but is not
  externally attachable in the tested 2024 build. The bridge uses `MicroStationDGN.Application`.

## Agent configuration (stdio)

Point any MCP client at the adapter venv:

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

The console script `C:\mcp-bridge\adapter\.venv\Scripts\bentley-mcp.exe` works the same way.
No token or port is needed for stdio. Any MCP client works; only the config key differs. VS Code
uses `servers` with `"type": "stdio"`; Claude Desktop, Cursor, and most others use `mcpServers`.

## HTTP mode (optional)

HTTP is loopback-only. It is useful for clients that cannot launch stdio processes.

```powershell
pwsh scripts\start-bentley.ps1          # default port 18131
pwsh scripts\stop-bentley.ps1
```

Endpoint: `http://127.0.0.1:18131/mcp`.

Set `BENTLEY_MCP_TOKEN` in the environment or `.env.local` to require a bearer token:

```json
{
  "mcpServers": {
    "bentley": {
      "type": "http",
      "url": "http://127.0.0.1:18131/mcp",
      "headers": { "Authorization": "Bearer <BENTLEY_MCP_TOKEN>" }
    }
  }
}
```

Without the token the endpoint is still loopback-only, but any local process can call it.
`BENTLEY_MCP_PORT` changes the default port.

## Tools

| Tool | Effect | Notes |
|---|---|---|
| `list_apps` | Show the attached app, or an empty list | Safe discovery call |
| `get_status` | Attached app, design file, model, extents | Safe discovery call |
| `open_design` | Open an absolute `.dgn` path | `read_only` defaults to false |
| `save_design` | Save the active design file | Writes the file |
| `create_line` | Add a line element | `start` and `end` are `[x, y, z]` |
| `create_polyline` | Add connected line segments | 2–1000 points |
| `create_text` | Place a text element | Uses the active text template; reports if `height` was applied |
| `list_models` / `list_levels` | Enumerate models / levels | Read-only |
| `set_active_model` | Activate a model by name | Case-insensitive |
| `list_elements` | List active model's graphical elements: id, level, type | `limit` 1–1000, optional `level` filter; `total_in_model`/`truncated` report the rest |
| `delete_element` | Remove one element by id | Destructive; requires `confirm=true` |
| `run_keyin` | Send one MicroStation key-in | Requires `confirm=true` |
| `run_python` | Queue MicroStation Python via temp script + `python execute` | Requires `confirm=true`; output goes to the Python window |
| `fit_view` | Fit and redraw open views | View state only |

Routing rules for choosing between these tools and the Copilot-bundled MCP
server live in [ROUTING.md](ROUTING.md).

`target` accepts `auto`, `microstation`, or `openbuildings`. `auto` follows the attached app;
an explicit target refuses a mismatch instead of acting on the other product.

Coordinates are in the active model's working units.

## Typical sequence

```text
list_apps
get_status
open_design  { "path": "C:\\scratch\\test.dgn" }
create_line  { "start": [0, 0, 0], "end": [25, 0, 0] }
create_polyline { "points": [[0, 5, 0], [5, 5, 0], [5, 10, 0]] }
save_design
fit_view
```

Use scratch DGN files for tests. The bridge saves whatever design file is active; it does not
choose or protect project files.

## Boundaries

* **MicroStation element model only.** The shared automation object exposes DGN elements, not
  OpenBuildings parametric building objects such as walls, doors, slabs, or MEP components. Use
  key-ins or an OpenBuildings add-in for those workflows.
* **One owner at a time.** Starting the other product does not give the bridge two independent
  control channels.
* **Gated execution.** `run_keyin` and `run_python` are the escape hatches; both require
  `confirm=true` and both can change or delete model content. `run_python` writes the code to
  `%TEMP%\bentley_mcp\` and queues it to MicroStation's Python engine; its output appears in the
  Python window, not in the tool result.
* **No tunnel.** HTTP binds to `127.0.0.1` only. Do not expose it through a dev tunnel or reverse
  proxy.
* **No undo.** COM exposes no undo or dirty flag anywhere. Snapshot with `save_design` (or a file
  copy) before bulk or destructive agent edits.
* **COM auto-launch starts the wrong product.** The shared CLSID's `LocalServer32` points at
  OpenBuildingsDesigner.exe on this machine. Never let COM cold-start the app — start MicroStation
  yourself, then attach.
* **Shadow instances.** A second MicroStation process registers its automation object but is not
  attachable (ROT entries carry no PID); it stays invisible to the bridge. One instance per session.
* **Typelib provenance.** The pinned GUID resolves through OpenBuildings' exe here; the generated
  interfaces matched MicroStation 2026 live in every probe. Identical object model, but the source
  is shared — noted, not changed.

## Troubleshooting

| Symptom | Check |
|---|---|
| `No Bentley automation object is registered` | Open a DGN. For OpenBuildings, use a DGN inside the active workset. |
| `Active Bentley app is X; requested Y` | Close the other product, or call with `target: "auto"`. |
| `401 Unauthorized` over HTTP | Send `Authorization: Bearer` with the same `BENTLEY_MCP_TOKEN` the server has. |
| `port ... already listening` | Choose another port: `pwsh scripts\start-bentley.ps1 -Port 18132`. |
| Title shows `[... Read-Only]` or "File is read-only" | A fresh non-workset DGN copy opened degraded: dismiss the "No WorkSet Alert" once, then `open_design` with `read_only: false`. |

## Tests

```powershell
cd adapter
.\.venv\Scripts\python.exe -m pytest tests\test_bentley_mcp.py -q
```

The unit tests use a fake COM adapter. A live check needs MicroStation or OpenBuildings running
with a scratch DGN, then:

```powershell
uv run python tests\bentley_baseline.py          # JSON attach/status probe, exit 0 on success
pwsh scripts\preflight.ps1                       # gates: COM ProgID, app running, live attach
pwsh scripts\validate.ps1 -BentleyLive           # unit tests + live COM gate together
```

For deeper round-trips call `create_line`, `list_elements`, `create_text`, `delete_element`,
`save_design`, and `fit_view` from the MCP client. `run_keyin` and `run_python` are not part of
the automated smoke because they can mutate the model; their `confirm` gates are unit-tested.
