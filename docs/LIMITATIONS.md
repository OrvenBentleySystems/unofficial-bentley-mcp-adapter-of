# Limitations and open production decisions

## Current limitations
* **Not provisioned**: blocked on Entra app registration permission (RUNBOOK). No hosted call has happened.
* **Copilot Access Enabled** for the account is unverified (CLI does not expose it). Custom App Upload is verified.
* **Browser vs desktop**: only the browser host is documented for the acceptance test; desktop app support for MCP-plugin agents is unverified and untested.
* **Required scope** `access_as_user`: the Entra SSO auth config was registered without an explicit scope
  (as the Toolkit generates it). If Copilot's token carries a different `scp`, the gateway logs
  `missing required scopes (has …)`; set `STAAD_GW_REQUIRED_SCOPES` to the observed delegated scope.
* **Dev tunnel** is a preview service, user-scoped, 30-day expiry, relay is anonymous; gateway must be running on this PC with STAAD open.
* **Read-only only**: no write, analysis, design or save tools. `get_model_summary` returns counts in model
  terms, not engineering quantities; `base_unit` is the model's base unit system.
* **Instance aliases** are stable only while the gateway runs; restarting renumbers them.
* Upstream `get_status` returns `allowed_dirs` (empty here); passed through unchanged.
* `agent/appPackage/manifest.json` `privacyUrl`/`termsOfUseUrl` are **placeholders** (example.com) acceptable
  for a personal sideload only; replace before any wider distribution.
* COM calls that hang are abandoned by upstream after its timeout; gateway upstream timeout 30 s.

## Production decisions (not implemented in this milestone)
Stable hosting/connectivity (replace dev tunnel); user-to-device/session binding (which workstation serves
which user); authorization model beyond a single allowlisted OID; audit retention and central logging;
secret/key rotation and certificate policy; tenant-wide deployment and admin approval; support ownership;
version compatibility across STAAD/openstaad-mcp/Copilot manifest schemas; long-running operations
(analysis) and progress; controlled model writes with confirmation and rollback.
