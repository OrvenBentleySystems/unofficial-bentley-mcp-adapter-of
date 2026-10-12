# Runbook

All commands from `C:\mcp-bridge` in PowerShell 7. Nothing here restarts STAAD.Pro, edits the model, or
touches `%USERPROFILE%\.copilot\mcp-config.json`.

## One-time setup (done on this workstation 2026-10-12)
```powershell
npm install -g @microsoft/m365agentstoolkit-cli --allow-scripts=@microsoft/m365agentstoolkit-cli,@azure/msal-node-extensions,keytar
winget install Microsoft.devtunnel --scope user
cd adapter; uv sync --group dev; cd ..
Copy-Item .env.example .env.local        # set STAAD_GW_ALLOWED_OIDS (your Entra object ID) + STAAD_GW_TENANT_ID
atk auth login m365
devtunnel user login -e -w               # integrated Windows auth (device code also works)
devtunnel create staad-assistant-gw -a -e 30d   # persistent; anonymous relay, auth enforced by gateway
devtunnel port create staad-assistant-gw -p 18130 --protocol http
```
The tunnel's public host is `ck8d1ltp-18130.asse.devtunnels.ms` (set in `agent\env\.env.dev` as
`MCP_SERVER_URL`). If the tunnel is deleted/recreated, update that value and re-provision.

## Blocker: Entra app registration
`atk provision` failed at `aadApp/create`:
`Authorization_RequestDenied — Insufficient privileges to complete the operation`
(2026-10-12T14:36:58Z, request-id `d4f3823f-477f-4ee6-91cc-103360a7e5f2`). The tenant does not allow this
user to register applications. Entra SSO for MCP plugins requires one.

* **Required actor:** Bentley Entra administrator (Application Administrator / Cloud Application Administrator).
* **Required action (either):**
  1. Temporarily grant the developer the *Application Developer* role; or
  2. Create a single-tenant app registration "STAAD Assistant MCP Gateway dev" with **no secret**, add the
     developer as **Owner**, and give the developer its *Application (client) ID* and *Object ID*.
  The developer's provisioning then sets (via `agent\aad.manifest.json`): Application ID URI from the SSO
  auth config, scope `access_as_user`, pre-authorized client `ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b`,
  redirect URI `https://teams.microsoft.com/api/platform/v1.0/oAuthConsentRedirect`, access token v2.
  If tenant policy also restricts `identifierUris`, the admin applies that manifest.
* **Success condition:** `pwsh scripts\provision.ps1` completes all 8 actions and records
  `AAD_APP_CLIENT_ID`, `MCP_DA_AUTH_ID_STAADASSIS`, `MCP_DA_APPLICATION_ID_URI_STAADASSIS`, `TEAMS_APP_ID`, `M365_TITLE_ID`.
* **Resume step:** for option 2 first add to `agent\env\.env.dev`:
  `AAD_APP_CLIENT_ID=<client id>` and `AAD_APP_OBJECT_ID=<object id>` (ATK then skips creation). Then
  run `pwsh scripts\provision.ps1`, then continue at "Launch".

## Validate / provision
```powershell
pwsh scripts\preflight.ps1     # read-only; VERIFIED/FAILED/UNVERIFIED per gate
pwsh scripts\validate.ps1      # unit tests, pinned-tool drift check, atk manifest validation (after provision)
pwsh scripts\provision.ps1     # Entra app, SSO auth config, app package validation, dev-user sideload
```
Also confirm **Copilot Access Enabled** in VS Code → Agents Toolkit → Accounts (not exposed by the CLI).

## Launch
```powershell
pwsh scripts\start.ps1
```
Starts the gateway (127.0.0.1:18130, own OpenSTAAD MCP stdio child) and `devtunnel host`, records PIDs in
`.run\state.json`, and checks unauthenticated loopback and HTTPS requests are rejected (401). It refuses to
start if a previous run is alive or the port is taken, and warns if the public URL differs from the
provisioned one. Restart after provisioning so the gateway trusts the new audience.

## Use (browser acceptance test)
1. Open https://m365.cloud.microsoft/chat, select **Agents → STAAD Assistantdev**.
2. Send the acceptance prompt (also a conversation starter):
   > Use the configured STAAD MCP tools to inspect the current runtime. Do not use chat history, screenshots, expected values, or cached answers. Return the live connection state, STAAD.Pro version if available, available instances, selected process identity if available, and current model path. Identify the tool that supplied each result. If a field is unavailable, say unavailable. Do not invent it.
3. Approve the first-use connection/sign-in prompt.
4. Correlate: `Get-Content logs\audit-*.jsonl -Tail 20` must show `tools/call` entries with your `oid` and
   client `ab3be6b7-…` at the matching time; compare values with `adapter\.venv\Scripts\python adapter\tests\live_baseline.py`.
5. Freshness without model mutation: in STAAD.Pro start or close a *second* instance (or the user opens a
   different model, if authorized), re-ask, and confirm `list_instances` (pid/alias/file_path) changed.
6. Failure honesty: `pwsh scripts\stop.ps1`, re-ask, the agent must report the tool/server as unreachable.
7. Desktop: repeat steps 1–3 in the Microsoft 365 Copilot desktop app and record separately.

If a token is rejected, `.run\gateway.log` states the reason (`audience mismatch`, `missing required
scopes (has …)`, `user_not_allowed`, `client_not_allowed`). Adjust `.env.local` overrides only to the
values shown by Entra, never to wildcards.

## Teardown
```powershell
pwsh scripts\stop.ps1                       # stops only recorded gateway/tunnel process trees
devtunnel delete staad-assistant-gw         # optional: remove the public hostname entirely
cd agent; atk uninstall -i false --mode env --env dev --options m365-app,app-registration  # optional: remove sideload + Dev Portal registration
```

## Maintenance
* Tool changes: edit `adapter/src/staad_mcp_gateway/app.py`, then
  `cd adapter; uv run python -m staad_mcp_gateway.export_tools ..\agent\appPackage\mcp-tools.json` and re-provision.
* Upstream upgrade: change the tag in `adapter/pyproject.toml`, `uv lock`, rerun `tests\live_baseline.py`
  and the unit tests; review new upstream tools before exposing anything.
