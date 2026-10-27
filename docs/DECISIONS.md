# Decisions and source verification

Access date for all sources: **2026-10-12**.

## Sources

| Source | Verified requirement | Consequence |
|---|---|---|
| [Build a plugin for a declarative agent from an MCP server](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/build-mcp-plugins) (updated 2026-09-30) | DA + MCP plugin via Agents Toolkit ("Start with an MCP Server"); test in browser at `m365.cloud.microsoft/chat`; needs Custom App Upload + Copilot Access | Used ATK template `declarative-agent-with-action-from-mcp`; browser is the acceptance host |
| [Plugin manifest v2.4](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/plugin-manifest-2.4) | `runtimes[].type = RemoteMCPServer`, `spec.url`, optional `spec.mcp_tool_description` (`file` or `tools`, same format as `tools/list`) | `agent/appPackage/ai-plugin.json` |
| [Dynamic tool discovery](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/plugin-dynamic-tool-discovery) | Pinned tools = `functions` + `run_for_functions` + `mcp_tool_description`; ATK default is dynamic | Pinned the 3 gateway tools (`mcp-tools.json`, exported from the gateway; `validate.ps1` checks they match) |
| [Plugin authentication](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/plugin-authentication) | MCP plugins: Entra SSO, DCR, OAuth 2.0 auth code, None. **API key not supported** | Upstream static bearer token cannot be used by Copilot → gateway required |
| [Entra SSO auth](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/plugin-authentication-entra-sso) (updated 2026-07-16) | Entra app secures server; auth config yields Application ID URI; add it to `identifierUris`; redirect `https://teams.microsoft.com/api/platform/v1.0/oAuthConsentRedirect`; pre-authorize token store `ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b`; API must accept the new audience | `agent/aad.manifest.json`, `oauth/register` writes `MCP_DA_APPLICATION_ID_URI_STAADASSIS`, gateway trusts that audience and that client |
| [Confirmation prompts](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/plugin-confirmation-prompts) | After first-use consent, MCP tools with `readOnlyHint: true` skip per-call confirmation | All 3 gateway tools are genuinely read-only and annotated so |
| [Dev tunnels CLI](https://learn.microsoft.com/en-us/azure/developer/dev-tunnels/cli-commands) | Preview; `--allow-anonymous`; anonymous means anyone with the URL can connect | Tunnel is anonymous at the relay; **authorization is enforced by the gateway**. `devtunnel host --help` (CLI 1.0.2094) shows Host header rewritten to `localhost` by default (verified live) |
| ATK CLI 1.1.18 (`atk new --help`, live) | `--mcp-da-auth-type` ∈ `oauth, oauth-dynamic, entra-sso, none`; `--mcp-tools-file-path` did not populate `functions` in non-interactive mode | Pinned tools written manually in the documented schema |
| [BentleySystems/openstaad-mcp](https://github.com/BentleySystems/openstaad-mcp) tag v1.3.0 (`1b12202f`) | stdio default; HTTP mode = 127.0.0.1 only, static token, TrustedHost 127.0.0.1, stateless; tools `discover_api, read_skills, list_instances, get_status, execute_code` (general Python, `destructiveHint`) | Upstream pinned unmodified; `execute_code` never exposed |
| [MCP 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) | Streamable HTTP | Negotiated `2025-11-25` end to end (evidence 01, 02) |

Discrepancies: Microsoft Learn does not state a transport/protocol-version matrix or payload/timeout
limits for MCP plugins, nor desktop-client parity. A research summary claimed `--host-header` is
undocumented; the installed CLI's own help documents it.

## Decisions

1. **Gateway is justified** (requirement 7C): Copilot cannot send the upstream static token (API key
   unsupported for MCP plugins), and upstream exposes `execute_code`. The gateway validates Entra
   tokens with FastMCP's `JWTVerifier` (authlib) and adds tenant/user/client checks.
2. **Upstream over stdio as a gateway child**, not upstream HTTP mode: no second listening port, no
   local token to manage, process dies with the gateway, aliases stay stable in one session.
3. **Explicit allowlist, not filtering**: the gateway only registers `list_instances`, `get_status`
   (pass-through, same names and semantics) and `get_model_summary` (adapter tool). Anything else is
   "Unknown tool" server-side, regardless of discovery.
4. **`get_model_summary` is a gateway adapter tool**, not a Bentley tool: it sends one fixed
   getter-only snippet (`GetSTAADFile, GetBaseUnit, GetNodeCount, GetMemberCount, GetPlateCount,
   GetPrimaryLoadCaseCount, GetLoadCombinationCaseCount, AreResultsAvailable`) through upstream
   `execute_code`. Only an alias matching `^staadPro[0-9]{1,4}$` is accepted; extra arguments are rejected.
5. **Entra SSO** chosen over OAuth/DCR: corporate identity, no client secret, documented for MCP.
   DCR is documented as unavailable for Entra-protected servers.
6. **Pinned tools**, so the tool surface cannot grow without republishing.
7. **No tenant publish**: the Toolkit's `publish` stage (tenant catalog) was removed; provision sideloads for the developer only.
8. **Persistent named tunnel** so the URL in the manifest/auth config is stable across restarts.
9. **Not switched** to `none` auth or a non-Entra IdP after the tenant blocked app registration
   (see RUNBOOK blocker) — that would bypass the tenant's identity governance.

## Amendments (2026-10-27)

| Change | Why |
|---|---|
| openstaad-mcp pin v1.3.0 → v26.0.0.107 | upstream keeps the `openstaad_mcp.main` entry module and the same `fastmcp>=3.2.3,<4` range; gateway code unchanged; 32/32 tests pass |
| COM-first routing ([ROUTING.md](ROUTING.md)) | live verification on MicroStation 26.00.02.39 showed direct COM covers agent authoring needs without Copilot or its Feature Token (expires 2027-05-01); Copilot MCP demoted to documented gap-filler |
| Element enumeration via `DesignFile.GetElementByID(DLong)` id-scan; `ModelReference.Activate()`; `CreateTextElement1(None, text, origin)` taking the element from the last list item | the v10.1 typelib exposes no `ModelReference.Elements`, no `SetModelActive`, and no reachable `TextElementTemplate` (live probes, 2026-10-27) |
