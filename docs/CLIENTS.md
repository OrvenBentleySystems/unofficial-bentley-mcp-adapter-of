# Client targets

Verification levels:

- **verified**: the generated config is installed and one status call returned
  for every configured server.
- **detected, not installed**: the client or its config location exists, but
  the generated config is not registered.
- **shape-only**: the writer follows current vendor documentation, but the
  client is not present for a live check.

## Status before Stage 4 registration

| Target | Config shape | Status before registration |
|---|---|---|
| GitHub Copilot CLI/app | `mcpServers` JSON | verified |
| VS Code Copilot | `servers` JSON | detected, not installed |
| Codex | TOML `[mcp_servers.<name>]` | detected, not installed |
| Claude Code | `mcpServers` JSON | detected, not installed |
| Cline | `mcpServers` JSON, explicit stdio, empty `autoApprove` | detected, not installed |
| Claude Desktop | `mcpServers` JSON | shape-only |
| Kilo Code | `mcp` JSONC with local command arrays | shape-only |
| Cursor | `mcpServers` JSON | shape-only |
| OpenCode | `mcp` JSON/JSONC with local command arrays | shape-only |
| Continue | YAML `mcpServers` array plus opt-in JSON fallback | shape-only |

## Current status

| Target | Current status | Evidence |
|---|---|---|
| GitHub Copilot CLI/app | verified | Baseline generated configuration and live MicroStation, STAAD.Pro, and PLAXIS 2D Input reads |
| VS Code Copilot | verified | Generated project config installed; 25-tool MicroStation read, 5-tool STAAD status, and 34-tool PLAXIS status returned |
| Codex | verified | Generated TOML merged with unrelated settings preserved; the same three server checks returned |
| Claude Code | verified | Generated project `.mcp.json` installed; the same three server checks returned |
| Cline | verified | Generated entries merged with `autoApprove: []`; the same three server checks returned |
| Claude Desktop | shape-only | Client not detected |
| Kilo Code | shape-only | Client not detected |
| Cursor | shape-only | Client not detected |
| OpenCode | shape-only | Client not detected |
| Continue | shape-only | Client not detected |

Shape-only targets are excluded from future `emit --auto` behavior until the
same installation and per-server status evidence exists.

Local provider output is separate from MCP registration. Codex supports an
adapter-owned custom-provider fragment. Cline requires UI configuration, so the
adapter writes instructions rather than editing Cline's internal provider
state. Kilo Code and Continue have documented file-based provider formats but
remain shape-only while absent.

Claude Cowork and ChatGPT web are out of scope. Their connector traffic starts
from vendor cloud infrastructure, which cannot reach these Windows-local stdio
servers.
