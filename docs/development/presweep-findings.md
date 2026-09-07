# Presweep findings

Full-tree scan date: 2026-09-07.

## Findings

| File | Line | Category | Decision |
|---|---:|---|---|
| `.mcp.json` | 34 | Absolute user-profile path | Delete generated client config from publication tree. |
| `.mcp.json` | 38 | Absolute user-profile path | Delete generated client config from publication tree. |
| `.mcp.json` | 45 | Absolute user-profile path | Delete generated client config from publication tree. |
| `.vscode/mcp.json` | 34 | Absolute user-profile path | Delete generated client config from publication tree. |
| `.vscode/mcp.json` | 39 | Absolute user-profile path | Delete generated client config from publication tree. |
| `.vscode/mcp.json` | 47 | Absolute user-profile path | Delete generated client config from publication tree. |
| `AGENTS.md` | 162, 284 | Generic `.std` and `.p2dx` extension references | Not sensitive. Delete generated context copy during inventory cleanup; source remains in `docs/`. |
| `CLAUDE.md` | 162, 284 | Generic `.std` and `.p2dx` extension references | Not sensitive. Delete generated context copy during inventory cleanup; source remains in `docs/`. |
| `.clinerules/bentley-mcp.md` | 162, 284 | Generic `.std` and `.p2dx` extension references | Not sensitive. Delete generated context copy during inventory cleanup; source remains in `docs/`. |
| `.github/copilot-instructions.md` | 162, 284 | Generic `.std` and `.p2dx` extension references | Not sensitive. Delete generated context copy during inventory cleanup; source remains in `docs/`. |
| `core/preflight/checks.py` | 232 | Generic `.std` extension check | Keep. Required model-open detection. |
| `docs/harness.md` | 158, 280 | Generic `.std` extension and exact observed error | Keep. No project filename. |
| `docs/INSTALL.md` | 118 | Generic `.std` extension instruction | Keep. No project filename. |
| `docs/TROUBLESHOOTING.md` | 11, 16 | Generic `.std` extension and exact observed error | Keep. No project filename. |

## Negative results

- No operator username or machine name was found outside generated client
  configs.
- No real DGN, STD, or P2DX filename was found.
- No PLAXIS password or other credential value was found. No rotation is
  required from repository contents.
- No API key, bearer value, licence identifier, internal URL, SharePoint link,
  or email address was found.
- No log, screenshot, transcript, `.env`, or generated sibling belongs in the
  publication tree.
- No `.git` directory exists. There is no history to inspect or rewrite, so
  the first commit is clean by construction.
