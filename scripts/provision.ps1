#Requires -Version 7
<#
.SYNOPSIS
  Provisions STAAD Assistant for the signed-in development user only (sideload; no tenant publish).
  Creates/updates: Entra app registration, Entra SSO auth config, Teams/M365 app, personal sideload.
#>
param([string]$EnvName = 'dev')
. "$PSScriptRoot\common.ps1"

if (-not (Get-Command atk -ErrorAction SilentlyContinue)) { Fail 'Agents Toolkit CLI missing: npm install -g @microsoft/m365agentstoolkit-cli' }
$who = atk auth list --telemetry false 2>&1 | Out-String
if ($who -notmatch 'Microsoft 365 account is') { Fail 'Not signed in. Run: atk auth login m365' }

& (Join-Path $PSScriptRoot 'validate.ps1') -SkipTests -EnvName $EnvName
Push-Location $Agent
try {
    $log = [System.Collections.Generic.List[string]]::new()
    atk provision --env $EnvName --interactive false --telemetry false 2>&1 | ForEach-Object { $log.Add("$_"); $_ }
    if ($LASTEXITCODE) {
        if (($log -join "`n") -match 'aadApp/create[\s\S]*Authorization_RequestDenied') {
            Write-Host ''
            Warn 'BLOCKED: this account may not create Entra app registrations in this tenant. Re-running will not help.'
            Warn 'Needs a tenant Entra admin: grant the Application Developer role, OR create the app registration (no secret),'
            Warn 'add you as Owner, then put AAD_APP_CLIENT_ID and AAD_APP_OBJECT_ID in agent\env\.env.dev and re-run.'
            Warn 'Details: docs\RUNBOOK.md "Blocker: Entra app registration".'
        }
        Fail "atk provision failed (exit $LASTEXITCODE)."
    }
} finally { Pop-Location }

$e = Get-AgentEnv $EnvName
foreach ($k in 'AAD_APP_CLIENT_ID', 'MCP_DA_AUTH_ID_STAADASSIS', 'MCP_DA_APPLICATION_ID_URI_STAADASSIS', 'TEAMS_APP_ID', 'M365_TITLE_ID') {
    if ($e[$k]) { Ok "$k recorded" } else { Warn "$k missing after provision" }
}
Ok 'Restart the gateway (scripts\stop.ps1; scripts\start.ps1) so it trusts the new Application ID URI audience.'
