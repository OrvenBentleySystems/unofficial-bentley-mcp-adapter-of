#Requires -Version 7
<#
.SYNOPSIS
  Focused validation: gateway unit tests (mocked; not live evidence) + app package schema/rules validation.
#>
param([string]$EnvName = 'dev', [switch]$SkipTests, [switch]$BentleyLive)
. "$PSScriptRoot\common.ps1"

if (-not $SkipTests) {
    Push-Location $Adapter
    try {
        uv run pytest -q -p no:cacheprovider
        if ($LASTEXITCODE) { Fail 'Gateway unit tests failed.' }
        Ok 'Gateway unit tests passed'
    } finally { Pop-Location }
}

# Pinned tool definitions must match what the gateway actually serves.
$tmp = Join-Path $env:TEMP "staad-tools-$PID.json"
Push-Location $Adapter
try { uv run python -m staad_mcp_gateway.export_tools $tmp | Out-Null } finally { Pop-Location }
$pinned = Get-Content (Join-Path $Agent 'appPackage\mcp-tools.json') -Raw | ConvertFrom-Json | ConvertTo-Json -Depth 20 -Compress
$served = Get-Content $tmp -Raw | ConvertFrom-Json | ConvertTo-Json -Depth 20 -Compress
Remove-Item $tmp
if ($pinned -ne $served) { Fail 'agent\appPackage\mcp-tools.json differs from gateway tools/list. Regenerate: uv run python -m staad_mcp_gateway.export_tools ..\agent\appPackage\mcp-tools.json' }
Ok 'Pinned tools match gateway tools/list'

# Bentley bridge live gate: real COM attach through the unmodified server.
if ($BentleyLive) {
    Push-Location $Adapter
    try {
        $bj = uv run python tests\bentley_baseline.py 2>$null | Out-String
        $bb = $bj | ConvertFrom-Json
        if (-not $bb.ok) { Fail "Bentley live probe failed: $bj" }
        Ok "Bentley live COM attached ($($bb.status.design_file), model $($bb.status.model))"
    } catch {
        Fail 'Bentley live probe did not return JSON. MicroStation running with a DGN open?'
    } finally { Pop-Location }
}

if (-not (Get-AgentEnv $EnvName)['MCP_DA_AUTH_ID_STAADASSIS']) {
    Warn 'Not provisioned yet: package validation runs inside atk provision (teamsApp/validateAppPackage).'
    return
}
Push-Location $Agent
try {
    atk validate --manifest-file ./appPackage/manifest.json --env $EnvName --interactive false --telemetry false
    if ($LASTEXITCODE) { Fail 'atk manifest validation failed.' }
    Ok 'App manifest validated'
} finally { Pop-Location }
