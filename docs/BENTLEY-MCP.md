# Bentley MCP bridge (MicroStation / OpenBuildings)

A local MCP server in `adapter/src/bentley_mcp` that controls the running Bentley desktop app
through direct COM. It does not use Bentley Copilot, an MCP proxy, or REA, and it does not affect
the STAAD gateway.

```
MCP client ─► stdio (default)  or  http://127.0.0.1:18131/mcp
           ─► bentley_mcp ─► MicroStationDGN.Application ─► MicroStation or OpenBuildings
```

**Status: live-verified on this workstation** with MicroStation 2026 (26.00.02.39) and
OpenBuildings Designer 2024 (24.00.03.14): attach, status, line, polyline, save, fit, stdio,
and loopback HTTP with bearer auth.

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
| `run_keyin` | Send one MicroStation key-in | Requires `confirm=true` |
| `fit_view` | Fit and redraw open views | View state only |

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
* **No arbitrary code.** There is no `execute_code`-style tool. `run_keyin` is raw application
  input and can change or delete model content; it requires explicit confirmation.
* **No tunnel.** HTTP binds to `127.0.0.1` only. Do not expose it through a dev tunnel or reverse
  proxy.

## Troubleshooting

| Symptom | Check |
|---|---|
| `No Bentley automation object is registered` | Open a DGN. For OpenBuildings, use a DGN inside the active workset. |
| `Active Bentley app is X; requested Y` | Close the other product, or call with `target: "auto"`. |
| `401 Unauthorized` over HTTP | Send `Authorization: Bearer` with the same `BENTLEY_MCP_TOKEN` the server has. |
| `port ... already listening` | Choose another port: `pwsh scripts\start-bentley.ps1 -Port 18132`. |

## Tests

```powershell
cd adapter
.\.venv\Scripts\python.exe -m pytest tests\test_bentley_mcp.py -q
```

The unit tests use a fake COM adapter. A live check needs MicroStation or OpenBuildings running
with a scratch DGN, then call `list_apps`, `get_status`, `create_line`, `save_design`, and
`fit_view` from the MCP client. `run_keyin` is not part of the smoke test because it can mutate
the model; its `confirm` gate is unit-tested.
