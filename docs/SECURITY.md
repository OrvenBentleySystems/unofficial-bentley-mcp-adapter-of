# Security

This is a **single-workstation development integration**, not an enterprise production deployment.

## Who can call the endpoint
* Network: anyone who knows `https://ck8d1ltp-18130.asse.devtunnels.ms` can reach the gateway while
  `scripts\start.ps1` is running (the relay is anonymous because the Copilot cloud caller cannot complete
  a dev-tunnel login). The URL is **not** treated as a secret.
* Authorization (gateway, every HTTP request including `initialize` and `tools/list`): bearer JWT must
  * verify against the tenant's published signing keys (`login.microsoftonline.com/<tenant>/discovery/v2.0/keys`, RS256);
  * have issuer `https://login.microsoftonline.com/<tenant>/v2.0` or `https://sts.windows.net/<tenant>/`;
  * have audience = provisioned Application ID URI or Entra app client ID;
  * have `exp` (required, not expired) and acceptable `nbf`;
  * have `tid` = configured tenant;
  * have `scp` containing `access_as_user` (configurable);
  * have `azp`/`appid` = Microsoft Enterprise token store `ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b`;
  * have `oid` in `STAAD_GW_ALLOWED_OIDS` (the developer only).
  Otherwise HTTP 401 with `WWW-Authenticate`. Config fails closed (no wildcard users, tenant must be a GUID).
* Before provisioning, no audience exists, so the gateway rejects every token.

## Tools allowed
`list_instances`, `get_status` (upstream pass-through) and `get_model_summary` (fixed read-only adapter
tool). Upstream `execute_code`, `discover_api`, `read_skills` are not registered → rejected even if a
client bypasses discovery. No code, file paths or upstream URLs are accepted from callers.

## Instance selection
Upstream ROT discovery, unchanged. Upstream refuses to guess when several instances run
(`Multiple instances running — specify one`). Agent instructions require showing real choices and never
choosing by a file name mentioned in chat.

## Secrets
None are required. The gateway holds no client secret; the Entra app is created without one. The
upstream runs over stdio (no token). `.env.local` holds only the allowed OID and tenant ID and is git-ignored.
ATK and devtunnel credentials remain in their own OS-protected caches.

## Data leaving the workstation
Tool results — STAAD version, process ID, instance alias, full model file path, model counts, analysis
state — travel through the Microsoft dev-tunnel relay to Microsoft 365 Copilot, are processed by the
Copilot service, and may be shown/stored in the user's Copilot conversation under the tenant's
Microsoft 365 policies. This repo makes no retention promise for those services.

## Logs
`logs\audit-YYYYMMDD.jsonl`: timestamp, request id, MCP method, tool name, argument **keys only**,
caller `oid`/`preferred_username`/client id, outcome, duration. No tokens, argument values or results.
`.run\gateway.log` holds process logs (rejection reasons; no tokens). Both are git-ignored and kept
until deleted manually.

## Revocation / removing reachability
* Immediate: `scripts\stop.ps1` (stops tunnel host and gateway; the public URL then returns an error).
* Tunnel: `devtunnel delete staad-assistant-gw`.
* Agent: `atk uninstall` (by title/manifest id) or remove from Microsoft 365 apps.
* Identity: delete the Entra app registration / SSO auth config in Teams Developer Portal, or remove the OID from `.env.local`.

## Residual risks
* While running, the Copilot user can read model metadata of any STAAD instance on this PC.
* Dev tunnels are a preview service; the anonymous relay exposes the gateway to unauthenticated probing (rejected with 401).
* `get_model_summary` relies on upstream `execute_code` sandbox semantics; the code is constant.
