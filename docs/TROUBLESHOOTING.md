# Troubleshooting

Start with `machine.json`, then the first failing preflight stage. Do not skip
ahead because later failures can hide the actual cause.

## `No STAAD.Pro instances found`

**Symptom:** OpenSTAAD returned `No STAAD.Pro instances found`. Preflight
reported `MODEL_NOT_OPEN`.

**Cause:** STAAD.Pro was open with no `.std` model. The process existed, but no
model was registered for OpenSTAAD.

**Action:**

1. Open the intended disposable `.std` file in STAAD.Pro.
2. Confirm its filename appears in the STAAD window title.
3. Run `resolve` again if the installation or executable changed.
4. Run preflight again.

A running process is not proof of an open model. The adapter treats these as
separate stages.

## `AUTHENTICATION_FAILED` with a correct PLAXIS password

**Symptom:** `The PLAXIS scripting server rejected the stored password for
this endpoint.`

**Cause:** PLAXIS 2D and PLAXIS 3D both listened on port 10000. The client
reached the wrong secured product, so a port error appeared as authentication
failure.

**Action:**

1. Stop both remote scripting servers.
2. Apply the allocation in `PORTS.md`.
3. Start PLAXIS 2D Input on 10000 and PLAXIS 3D Input on 10002.
4. Run `plaxis-mcp setup` to regenerate profiles.
5. Run preflight.

Preflight must report `PORT_COLLISION` or `PORT_IDENTITY_MISMATCH` before any
credential action. Do not rotate a password until ownership is correct.

## `MACHINE_FOREIGN` or a profile path from another account

**Symptom:** `machine.json belongs to host '<recorded>', not '<current>'`, or
an emitted path points at another account.

**Cause:** A machine record was copied, or a path was hardcoded instead of
resolved. The live variance test included an account name containing a dot.

**Action:**

1. Remove hand-built paths from the site profile where a machine token exists.
2. Run `resolve` under the affected account.
3. Check `known_folders`, `executables`, `installations`, and
   `microstation.mcp_bundle` in `machine.json`.
4. Regenerate client configs.

The resolver uses Windows known-folder APIs and registry discovery. Do not
replace its output with string concatenation.

## `MACHINE_STALE`

`machine.json` is older than `machine_max_age_hours`, or has a future
timestamp. Run `resolve` again.

## `VERSION_RECORD_INCOMPLETE`

At least one required harness field is blank or contains `TODO`. Complete the
record in `profiles/site.yaml`.

## `APPLICATION_NOT_RUNNING`

The required executable is absent. Start the application selected in the site
profile. If several versions are installed, confirm the intended one in
`machine.json`.

## `PORT_NOT_LISTENING`

Enable the remote scripting server in the PLAXIS application. Do not redirect
the MCP process with environment variables.

## `SERVER_VERSION_MISMATCH` or mismatch warning

Stop. Align the server pin, application version, site version record, and
installed package. Do not suppress a warning.

## `ALLOWED_DIRECTORY_*`

Use an existing writable local directory. Do not use UNC, a network drive, a
profile root, a declared project share, or a synced folder.

## `READ_PROBE_FAILED`

Read the complete message. Common causes are an uncached offline package,
MicroStation bridge not started, PLAXIS profile not regenerated, or no model
open. Fix the named earlier stage rather than adding credentials to config.

## `Did not receive done or success response in stream`

**Symptom:** Cline reports this exact message while using llama.cpp through its
Ollama-compatible surface.

**Cause:** llama.cpp does not terminate that compatibility stream exactly like
the native provider expected by Cline.

**Action:** select **OpenAI Compatible** in Cline, use
`http://localhost:8080/v1`, set the model id to the llama-server alias, and use
only a local placeholder key.

## `LOCAL_MODEL_NO_TOOL_CALL`

**Cause:** llama-server answered chat but did not return the forced tool call.

**Action:** confirm `--jinja` is present, inspect `/props` for a tool-aware chat
template, confirm `/v1/models` lists the alias, and increase context if the
catalogue does not fit.

## `LOCAL_MODEL_UNREACHABLE`

**Cause:** no llama-server answered on the configured loopback port.

**Action:** start `llama-server` with the documented launch command, including
`--jinja`, then confirm `GET /props` before rerunning preflight.

## `LOCAL_MODEL_ALIAS_MISSING`

**Cause:** `/v1/models` did not list the configured alias.

**Action:** make `local_provider.alias`, the client model id, and
`llama-server --alias` identical.
