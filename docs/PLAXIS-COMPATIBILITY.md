# PLAXIS compatibility

Product availability and MCP compatibility are separate. A build can be the
latest offered to an account while still using a runtime that differs from the
stock MCP profiles.

Stock `plaxis-mcp` 0.3.5 matches the bundled Python ABI exactly:

| Upstream profile | Product generation named upstream | Required bundled Python | Status in this adapter |
|---|---|---:|---|
| `current-312` | PLAXIS 2024.2 and newer | 3.12.3 | Allowed to proceed to runtime attestation and live reads; no newer build is live-verified here |
| `legacy-38` | V22 through early 2024 | 3.8.10 | Stock upstream profile |
| `legacy-37` | V20 and V21 | 3.7.4 | Requires explicit legacy security acceptance |
| `legacy-38-2023` | PLAXIS 2D 2023.2 | 3.8.17 | Local patch used for the operator-machine proof; absent from stock 0.3.5 and uncertified upstream |

**Tested 2026-09-07:** PLAXIS 2D 2025.1.3.5 on this machine uses
`PLAXIS Python Distribution V3` with Python 3.12.12. Stock `plaxis-mcp` 0.3.5
does not search Distribution V3 and rejects the installation as
`The requested PLAXIS installation is not a certified discovery result.`
An isolated local V3/3.12.12 validation profile reached
`PLAXIS 2D Input/2025.1.3.5`, but the vendor scripting client could not
authenticate. This build is therefore **known incompatible with pinned
plaxis-mcp 0.3.5**, not merely unverified.

The product generation label is not enough. If a newer PLAXIS release bundles
a Python patch other than an exact upstream profile, stock `plaxis-mcp` fails
closed until that ABI is added and certified.

## Adapter behavior

- The locally verified 2023.2 build is accepted, but the preflight and docs
  disclose that its server distribution was patched.
- A recorded 2024.2+ build is not rejected solely because it differs from
  2023.2, unless it is listed as known incompatible with the pinned server.
- A 2024.2+ build remains **unverified** and receives a stage 6 warning.
- Stock worker attestation and the module's stage 8 read calls must then pass.
- Builds outside the verified 2023.2 case and below 2024.2 still fail the
  version policy.
- PLAXIS 2025.1.3.5 fails stage 6 with the pinned 0.3.5 server because its V3
  Python 3.12.12 runtime is not supported.

## How to close support for a newer build

1. Run stock `plaxis-mcp setup` against that installation.
2. Confirm the generated profile reports `current-312`.
3. Confirm worker Python is exactly 3.12.3.
4. Run preflight through stage 8 for Input.
5. Start Output on port 10001 and verify `connection_status`,
   `project_info`, and `list_result_types`.
6. Record the exact PLAXIS build and promote it to `verified_versions` only
   after those reads pass.

For 2025.1, upstream `plaxis-mcp` must first add and certify Distribution V3
with Python 3.12.12. Removing the adapter's known-incompatible entry before
that would only move the failure from stage 6 to server startup or stage 8.
