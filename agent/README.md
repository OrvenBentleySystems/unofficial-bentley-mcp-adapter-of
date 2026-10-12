# STAAD Assistant — Agents Toolkit project

Generated with `atk new -c declarative-agent-with-action-from-mcp` (ATK CLI 1.1.18), then edited:

* `aad.manifest.json` + `aadApp/create`/`aadApp/update` steps for the Entra SSO app registration.
* `appPackage/ai-plugin.json`: plugin v2.4 `RemoteMCPServer`, pinned tools from `appPackage/mcp-tools.json`, `OAuthPluginVault` (Entra SSO).
* `appPackage/instruction.txt`: runtime instructions using the real tool names.
* Tenant-wide `publish` stage and the template's Azure OpenAI eval scaffolding removed.

See the repository [README](../README.md) and [docs/RUNBOOK.md](../docs/RUNBOOK.md).
