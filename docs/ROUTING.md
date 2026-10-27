# Routing policy: COM-first, plain MCP only as gap filler

Every agent talks to `bentley_mcp` (COM). Nothing on the core path depends on
Bentley Copilot. This page records why, and when the Copilot-bundled MCP
server may still be worth using.

## Default: COM via bentley_mcp

Use the typed COM tools for everything the `MicroStationDGN` object model
covers, and the two gated escape hatches (`run_python`, `run_keyin`) for
anything it does not:

| Need | Route |
|---|---|
| Open/save designs, models, levels | typed tools (`open_design`, `list_models`, `list_levels`, `set_active_model`) |
| Query/inspect elements | `list_elements` (+ `get_status` for extents) |
| Create line/polyline/text | `create_line`, `create_polyline`, `create_text` |
| Delete/modify elements | `delete_element`, or `run_python` for bulk/complex edits |
| Arbitrary scripting | `run_python` (writes a temp script, queues `python execute`) |
| Native MicroStation behavior | `run_keyin` |
| View control | `fit_view` |

Reasons COM is the primary route:

* **No Copilot, no token clock.** The Copilot Feature Aspect Token (expires
  1 May 2027) gates Copilot MCP, its Python execution, and Display Rules in
  2026.2. COM works without it, now and after expiry.
* **Agent-neutral.** Any MCP client connects over stdio or loopback HTTP —
  VS Code, Claude, Cursor, or a custom harness. No dependency on which AI
  product Bentley ships.
* **Deterministic and auditable.** Typed tools, explicit `confirm=true` on
  destructive calls, all local, no cloud hop.
* **No version lag.** Evergreen Copilot updates are not required to keep the
  bridge working; it rides the COM object model, which is stable across the
  2026.x releases tested.

## Optional: the Copilot-bundled MCP server (26.02.49+)

Worth using only when it clearly adds capability COM cannot reach cheaply:

* Display Rules authoring (Copilot feature).
* Copilot's in-process planning/explanation context.

If used, treat it as a side channel for one task. Do not put it on the core
path: it is bound to MicroStation 2026.2 + Copilot 26.02.49, to the token
expiry, and to a model choice controlled by the add-in (stays `gpt-5.6-terra`
until the 2027 release).

## Decision rule

1. Try typed COM tools.
2. Gap → `run_python` (preferred) or `run_keyin`, both confirm-gated.
3. Still a gap → check whether the Copilot MCP offers it; if yes, use it ad
   hoc and record the capability in this doc.
4. Unknown COM surface → reverse-engineer the need case-by-case; REA
   (`github.com/morluto/rea`) is the designated diagnostic for that, not a
   runtime dependency.
