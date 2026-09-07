# Bentley MCP Adapter

Bentley MCP Adapter discovers local Bentley application installations, emits
MCP client configuration, and runs ordered connectivity checks for
MicroStation, STAAD.Pro, and PLAXIS without replacing their MCP servers.

> [!WARNING]
> This is an unofficial personal community project. It is not a Bentley
> product and is not affiliated with, endorsed by, or sponsored by Bentley
> Systems or Seequent. It has no vendor support. `plaxis-mcp` is an independent
> third-party project. MicroStation MCP is early access and proprietary.
> Licensing and entitlement for agent-driven use are unresolved and are the
> deploying organisation's responsibility. No component validates engineering
> correctness. A qualified engineer must review all analysis output.

## Status

Verified on 2026-09-07:

| Component | Verified version and result |
|---|---|
| MicroStation | 2026.1 build 26.00.01.65; 25 tools; file-info read passed |
| STAAD.Pro | 2026 version 26.0.0.340; OpenSTAAD read passed |
| PLAXIS 2D | 2023.2.1.1079; `plaxis-mcp` 0.3.5; Input read passed |
| Client | GitHub Copilot app 1.0.83-5 |
| Adapter | 0.1.0; eight preflight stages and 14 tests passed |

Not yet verified: a clean second machine, PLAXIS Output, stable provenance for
the OpenSTAAD executable used during live validation, and a local llama.cpp
model chain. See [HANDOVER.md](HANDOVER.md).

Client verification uses three levels: verified, detected but not installed,
and shape-only. GitHub Copilot, VS Code, Codex, Claude Code, and Cline are now
verified with installed generated configurations and status calls from every
enabled server. Claude Desktop, Kilo Code, Cursor, OpenCode, and Continue
remain shape-only. Evidence is in [docs/CLIENTS.md](docs/CLIENTS.md).

The adapter is client-neutral and model-neutral. Client targets and model
providers are separate plugins. The local-provider path targets
`llama-server`; no local provider was detected during verification.

## Requirements

- Bring an MCP client. The adapter detects and configures supported clients; it
  does not install one.
- Bring a model provider. A hosted provider requires no adapter model setup.
  The optional local path uses an existing llama.cpp `llama-server`; the
  adapter does not install it or choose weights.
- Windows 11
- Python 3.13
- PyYAML 6
- MicroStation 2026.1 build 26.00.01.65 with Bentley Copilot MCP installed
- Node.js for the MicroStation stdio launcher
- STAAD.Pro 2026 version 26.0.0.340
- OpenSTAAD MCP 1.2.0, installed or cached before offline launch
- PLAXIS 2D 2023.2.1.1079
- `plaxis-mcp` 0.3.5; use its signed executable for production
- `uv` and `uvx` when using the declared evaluation launchers
- Elevation for the MicroStation MCP MSI installation
- A local writable working directory outside profile roots, shares, and synced folders

## Install and first run

```powershell
New-Item -ItemType Directory -Force C:\mcp-work
Copy-Item profiles\site.example.yaml profiles\site.yaml
uv build --wheel --out-dir dist
deploy.bat
```

Edit `profiles\site.yaml`. Complete every version-record field, set
`workspace_root`, select modules and tiers, and confirm the port map.

Start each application with a disposable model open. In MicroStation, load
Copilot and run `copilot mcpstart`. In PLAXIS, enable the role server on the
assigned port and run `plaxis-mcp setup` after any port change.

`deploy.bat` installs the wheel, resolves the machine, detects clients,
delivers the harness, previews diffs, pauses for confirmation, emits only to
verified detected clients, and runs preflight. `deploy.bat --check` performs a
read-only drift check. Do not continue unless all required stages pass. Full
instructions are in [docs/INSTALL.md](docs/INSTALL.md); agent behavior is
governed by [docs/harness.md](docs/harness.md).

## Supported clients

| Client target | Generated config | Status |
|---|---|---|
| GitHub Copilot CLI and app | `%USERPROFILE%\.copilot\mcp-config.json` | verified |
| VS Code with Copilot | `<workspace>\.vscode\mcp.json` | verified |
| Codex CLI, IDE, ChatGPT desktop | `%USERPROFILE%\.codex\config.toml` | verified |
| Claude Code | `<workspace>\.mcp.json` | verified |
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` | Writer tested; client not detected |
| Cline extension and CLI | Extension settings and `%USERPROFILE%\.cline\mcp.json` | verified extension configuration |
| Kilo Code | `kilo.jsonc` or `.kilo\kilo.jsonc` | Current-shape writer tested; client not detected |
| Cursor | `.cursor\mcp.json` | Writer tested; client not detected |
| OpenCode | `opencode.json` | Current-shape writer tested; client not detected |
| Continue | `.continue\mcpServers\bentley.yaml` | YAML and fallback writers tested; client not detected |

Hand-written whole-application configs are not overwritten. The adapter writes
a `.bentley.generated` sibling for review and merge.

## Port map

| Application | Role | Port |
|---|---|---:|
| PLAXIS 2D | Input | 10000 |
| PLAXIS 2D | Output | 10001 |
| PLAXIS 3D | Input | 10002 |
| PLAXIS 3D | Output | 10003 |
| Reserved | Future use | 10004 to 10009 |

The application owns the port. Change it in the PLAXIS dialog, then run
`plaxis-mcp setup`. Never redirect an endpoint with a `PLAXIS_*` environment
variable. See [docs/PORTS.md](docs/PORTS.md).

## Limits

- Windows only. No WSL, Docker, gateway, tunnel, or remote transport is shipped.
- MicroStation MCP is early access; verification does not transfer to another build.
- PLAXIS Output has not been verified on the operator machine.
- No clean second-machine run has been completed.
- The live OpenSTAAD executable did not have stable release provenance.
- Read tiers reduce the Copilot tool surface. The generated VS Code file
  contains no tool allowlist, so it does not enforce tier restriction.
- Local MCP traffic does not make cloud-model prompts local.
- The adapter checks configuration and connectivity, not engineering results.
- The llama.cpp path is shape- and test-verified only. No local model chain has
  completed on the operator machine.

## Attribution

The adapter uses Bentley's MCP interfaces, the independent
[`yixuanzhong/PLAXIS-MCP`](https://github.com/yixuanzhong/PLAXIS-MCP) profile
and credential pattern, and the protocol-neutral core and adapter pattern from
[`gaopengbin/cesium-mcp`](https://github.com/gaopengbin/cesium-mcp).
[`SeequentEvo/evo-mcp`](https://github.com/SeequentEvo/evo-mcp) is cited as
prior art for tool catalogue filtering. Protocol behavior follows the
[Model Context Protocol specification](https://modelcontextprotocol.io/specification/2025-06-18).
Licence details and all consulted projects are in [CREDITS.md](CREDITS.md).

## Licence

Bentley MCP Adapter is licensed under the [MIT License](LICENSE).
Third-party projects and Bentley applications retain their own licences and
terms.
