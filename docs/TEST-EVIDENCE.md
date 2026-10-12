# Test evidence

Local raw evidence (git-ignored, contains model paths/user IDs): `evidence\`. Values below are sanitized excerpts.
Components: Windows NT 10.0.26200, STAAD.Pro 26.0.1.491 (`Bentley.Staad.exe`), openstaad-mcp v1.3.0
(`1b12202f`), FastMCP 3.4.8, mcp 1.30.0, Python 3.12.10, uv 0.12.3, ATK CLI 1.1.18, devtunnel CLI 1.0.2094.

| # | Test (2026-10-12, UTC) | Result | Evidence |
|---|---|---|---|
| 1 | Local MCP: real client → upstream stdio; `initialize`, `tools/list`, `list_instances`, `get_status` (14:08:31) | **PASS** — protocol `2025-11-25`; tools `discover_api, read_skills, list_instances, get_status, execute_code`; 1 instance `staadPro1`, connected, model path returned | `evidence\01-local-baseline.json` |
| 2 | Missing/invalid external credentials (unit, mocked upstream, local test key): none, malformed, wrong key, wrong audience, wrong issuer, wrong `tid`, wrong `oid`, wrong scope, no scope, expired, wrong client | **PASS** — all 401, upstream never called | `adapter\tests\test_gateway.py` (23 passed) |
| 2b | Same over real HTTPS tunnel (14:35:53): no token, garbage, other key, other user | **PASS** — 401 ×4; `/` → 404 | `evidence\02-https-harness.json` |
| 3 | Disallowed tool invocation (`execute_code`, `discover_api`, `read_skills`) with a valid token; injected `code` arg and malformed alias on `get_model_summary` | **PASS** — rejected server-side (`Unknown tool` / validation error), nothing forwarded; audit `outcome=error:NotFoundError` | unit tests; `02-https-harness.json` |
| 4 | HTTPS MCP initialize/discovery/status through `https://ck8d1ltp-18130.asse.devtunnels.ms/mcp` with **real upstream and live STAAD**; **auth substituted** by an ephemeral in-memory key | **PASS** — protocol `2025-11-25`; tools = exactly the 3 allowlisted; live `get_status` (connected, 26.0.1.491), `list_instances`, `get_model_summary` (570 nodes, 1107 members, 9 primary load cases) | `02-https-harness.json` |
| 4b | `scripts\start.ps1`: loopback-only bind, 401 without token on loopback and HTTPS; `scripts\stop.ps1` stops only owned trees (tunnel 2, gateway 6 processes), port closed | **PASS** | console output, `.run\` |
| 5 | Package schema validation | **NOT EXECUTED** — `atk validate`/`teamsApp/validateAppPackage` need provision-generated IDs; provisioning blocked | — |
| 5b | Provision | **FAILED (BLOCKED)** — `aadApp/create` → `Authorization_RequestDenied`, request-id `d4f3823f-477f-4ee6-91cc-103360a7e5f2` (14:36:58) | RUNBOOK blocker |
| 6 | Microsoft-hosted agent invokes real tool | **NOT EXECUTED** (blocked by 5b) | — |
| 7 | Freshness without model mutation | **NOT EXECUTED** (blocked by 5b) | — |
| 8 | Disconnection → honest failure in hosted agent | **NOT EXECUTED** (blocked by 5b) | — |
| — | Preflight (14:4x) | Local/network gates VERIFIED; Copilot Access UNVERIFIED; Entra app / auth config / title FAILED | `evidence\03-preflight.txt` |
| — | Existing CLI OpenSTAAD MCP still working after all work | **PASS** — `get_status` connected via GitHub Copilot CLI (does not count as hosted evidence) | — |

Mocked tests (#2, #3 unit) and the auth-substituted harness (#4) are **not** hosted integration evidence.
No hosted transcript or screenshot exists.
