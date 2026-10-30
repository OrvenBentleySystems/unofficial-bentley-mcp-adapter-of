# SYNCHRO 4D access (synchro-mcp)

Status: **v0, working, scoped honestly.** SYNCHRO 4D Pro 6.5 exposes no COM
automation and no CLI. Reverse-engineering the install (all findings verified
live on this machine, 2026-10-30) found two real doors and this server ships
both.

```
agent ── MCP stdio ──> synchro-mcp (Node, zero deps)
                        ├─ synchro_script  ──> phrase .txt ──> user Preview/Run in app (undoable)
                        └─ synchro_status  ──> bundled headless SDK (synchrojs native addon)
```

## The script channel (full control of the open project)

SYNCHRO's own **SYNCHRO Script** tool executes phrase files with bulk
set/condition operations over the live project — tasks, resources,
assignments, links, user fields, 3D. `synchro_script` writes those files;
loading + Preview + Run is one human interaction per batch, and the app's
Undo reverses it. Grammar (from the product help, `Synchro4DPro.chm`):

- Phrase: `<OBJECT>[(condition)] <COMMAND>` per line; `//` and `/* */` comments.
- Objects: `TASK RESOURCE 3D ASSIGNMENT PARENT LINK TO_LINK LINKED_TO_TASK LINKED_FROM_TASK`,
  chained with `.` (`TASK.RESOURCE`, `TASK.TASK`, `TASK.SUCCESSOR`, `3D.TASK`, `TASK.ASSIGNMENT`, …).
- Conditions: `== != < > <= >= <>`, `AND/OR/NOT`, states `STARTED FINISHED LEAF HAS_PARENT`.
- Commands: `SET <property> = <value>`, `PROPERTY("user field")`, `SUM(...)`, `COUNT(...)`.

Example agent flow — shift a phase two weeks, tag status:

```
TASK(NAME >= "excavation" AND STARTED) SET START = 15.11.2026
TASK(NAME == "Foundation") SET STATUS = "Delayed"
RESOURCE(NAME >= "crew") SET PROPERTY("Notes") = "rescheduled 2026-11"
```

## The headless SDK (what it can and cannot do)

The install ships Bentley's own Node bindings (`synchrojs-node.node`, loads in
plain Node) over the full C++ object model (`SynchroAPI.dll`, 8,728 exports:
Task/Resource/Calendar/Link/Importer/Exporter classes, `ActiveProject`,
`Transaction`). Verified facts:

- **Works headless:** build `.sp` files from scratch (`Importer` →
  `OpenEntity/OpenTask/OpenResource` → `WriteSPFile`); SYNCHRO opens the
  result. The app's own iModel bridge runs this path in a separate process.
- **Does not work headless:** `ActiveProject()` is null outside the app, so
  reading an existing `.sp` or producing schedule-visible WBS edits needs the
  app context — that is what the script channel covers.
- Not present: COM ProgIDs, TCP/Thrift server on the running app, script
  auto-run CLI, standalone IFC→`.sp` converter (the Importer is a geometry
  feed API; conversion is driven by app-internal readers).

## Run it

```json
{
  "mcpServers": {
    "synchro": {
      "command": "node",
      "args": ["C:\\mcp-bridge\\synchro-mcp\\server.js"]
    }
  }
}
```

Requires SYNCHRO 4D Pro installed at the default path (override with
`SYNCHRO_APP_ROOT` pointing at `...\\node_modules\\synchrojs\\src\\index.js`).
`synchro_status` reports SDK load state; the script channel works regardless.

## Roadmap (each step needs the same RE probing that got v0)

1. Read-back: script phrases cannot emit data; a C# script template that
   dumps schedule state to CSV would close the loop (editor-paste, not TXT).
2. Headless `.sp` builder tool wrapping `Importer` (entity trees + user
   fields; task stubs are not schedule-visible — proven 2026-10-30).
3. Re-check on the next SYNCHRO release for a hosted Thrift/Messenger port
   (service constants already exist in the addon: STATELESS/TRANSACTIONAL/
   MESSENGER/INTEGRATION/ADMIN).
