# Installation

This pack supports Windows only. It configures existing MCP servers. It does
not install or modify Bentley applications.

Bring your own client and model provider. The adapter detects and configures
supported clients that are already installed. It does not install a client,
llama.cpp, or model weights.

## Prerequisites, before step one

1. Use an administrator account for the MicroStation MCP MSI installation.
   The adapter itself should run as a normal user after installation.
2. Install the exact verified MicroStation build recorded in the selected
   module and its compatible MicroStation JS Apps build. A newer application
   build resets verification and requires a new preflight record.
3. Install Node.js for the MicroStation stdio launcher. `resolve` records the
   absolute executable path and reports a missing installation.
4. Install the exact STAAD.Pro build recorded in the selected module. Install
   the pinned OpenSTAAD MCP release. This pack pins 1.2.0. A newer build is not
   treated as verified automatically.
5. Install `uv` and `uvx` if OpenSTAAD is not deployed from its `.mcpb`
   bundle.
6. Install a PLAXIS 2D release whose bundled Python matches an exact upstream
   `plaxis-mcp` runtime profile. Stock 0.3.5 declares `current-312` for PLAXIS
   2024.2 and newer, but accepts only bundled Python 3.12.3. A later product
   release with a different Python patch fails closed until certified.
7. Install the signed `plaxis-mcp` 0.3.5 Windows package for production. The
   PyPI path is suitable for local evaluation but has no Authenticode or
   package manifest assurance.
   The operator-machine PLAXIS 2023.2 proof used a local `legacy-38-2023`
   patch for Python 3.8.17. That patch is absent from stock 0.3.5 and must not
   be presented as upstream support.
8. Install CPython 3.13 for this adapter and the `plaxis-mcp` host. Do not
   install `plxscripting` into that environment.
9. Enable Windows long paths, or use a shallow dedicated working directory.
10. Create a local working directory such as `C:\mcp-work`. Do not use a user
    profile root, network share, UNC path, live project share, or synced folder.

## 1. Install the adapter

From `bentley-adapter`:

```powershell
py -3.13 -m pip install -e .
```

The only runtime package dependency is PyYAML. The adapter makes no network
calls. Server launch descriptors use pinned, offline commands. Install or cache
those server packages before preflight.

For the guided deployment path, build the release wheel and run:

```powershell
uv build --wheel --out-dir dist
deploy.bat
```

The script prints detection results and diffs, then waits for `YES` before
writing client configuration. `deploy.bat --check` uses temporary detection
files and changes no repository or client config.

`machine.json`, `profiles\site.yaml`, generated client configs, logs, and
environment files are ignored by Git. Do not force-add them.

## 2. Configure application ports

Apply the allocation in `PORTS.md` in each PLAXIS Configure remote scripting
server dialog. PLAXIS 2D Input uses 10000. PLAXIS 3D Input uses 10002.

Run `plaxis-mcp setup` after any port change. Store passwords only through its
hidden terminal prompts in Windows Credential Manager.

## 3. Generate machine inventory

```powershell
bentley-adapter resolve `
  --working-directory C:\mcp-work `
  --output machine.json
```

Inspect `machine.json`. It is generated evidence, not a template. It records
known folders, application versions, launch prerequisites, PLAXIS profile
locations, privilege state, long-path state, and sync-folder risk.

Every later command reads `machine.json`. It performs no independent discovery.
Regenerate it after application, runtime, path, or account changes.

## 4. Create the site profile

```powershell
Copy-Item profiles\site.example.yaml profiles\site.yaml
```

Complete every value in `version_record`. A value containing `TODO` is treated
as incomplete. Set `allowed_directory`, the port map, enabled modules,
capability tiers, `workspace_root`, and output paths. The example outputs are
the real filenames read by the clients: `~\.copilot\mcp-config.json` and
`<workspace>\.vscode\mcp.json`.

Do not put passwords, bearer tokens, or other secret values in this file. A
client input reference has this shape:

```yaml
env:
  EXAMPLE_TOKEN: {secret: example-token}
```

The emitter rejects likely secret values and all automatic approval settings.
Secret input references are supported by the VS Code writer. The Copilot CLI
writer rejects them because that target has no matching `inputs` block in this
stage. The shipped PLAXIS flow needs no client secret because it reads Windows
Credential Manager.

For production PLAXIS use, override each PLAXIS module launch with the absolute
path to the signed `plaxis-mcp.exe`. The descriptor's pinned offline `uvx` path
is the verified evaluation path, not the signed production artifact.

## 5. Start applications

1. Open the intended DGN in MicroStation.
2. Load Copilot and run `copilot mcpstart`.
3. Open a `.std` model in STAAD.Pro. A blank STAAD window fails preflight.
4. Open the intended PLAXIS project.
5. Enable the PLAXIS remote scripting servers on their assigned ports.

Use disposable project copies for any later write-tier testing.

## 6. Preview client configurations

```powershell
bentley-adapter emit `
  --profile profiles\site.yaml `
  --machine machine.json `
  --all `
  --dry-run
```

Dry-run output is a unified diff. Review every command, absolute path, version
pin, capability tier, and output location.

## 7. Write client configurations

```powershell
bentley-adapter emit `
  --profile profiles\site.yaml `
  --machine machine.json `
  --all
```

Generated files identify their source profile, timestamp, pins, and capability
tiers. Existing generated files are overwritten. Hand edits are not preserved.

The Copilot writer emits `mcpServers` and requires `type`. The VS Code writer
emits `servers`. Secret references become `inputs` entries with
`type: promptString` and `password: true`. No automatic approval setting is
emitted.

## 8. Run preflight

```powershell
bentley-adapter preflight `
  --profile profiles\site.yaml `
  --machine machine.json
```

Checks run in the fixed order documented in `HANDOVER.md`. A failure has a
stable diagnostic code and exit code. Do not proceed after a failure.

## 9. Register and restart

Restart GitHub Copilot after changing its MCP configuration. VS Code does not
normally need a full application restart, but its MCP server list must be
refreshed.

Keep default approval prompts. Never approve `execute_code`, `run_keyin`,
`run_python`, `call_method`, project file operations, or calculation tools
automatically.
