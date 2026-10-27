#Requires -Version 7
<#
.SYNOPSIS
  Read-only preflight. Prints VERIFIED / FAILED / UNVERIFIED per gate. Changes nothing.
#>
param([string]$EnvName = 'dev', [switch]$SkipLiveMcp)
. "$PSScriptRoot\common.ps1"
$ErrorActionPreference = 'Continue'
$results = [System.Collections.Generic.List[object]]::new()
function Gate($name, $status, $detail) { $results.Add([pscustomobject]@{ Gate = $name; Status = $status; Detail = $detail }) }

Gate 'Windows' ($(if ($IsWindows) { 'VERIFIED' } else { 'FAILED' })) ([Environment]::OSVersion.VersionString)
$uv = Get-Command uv -ErrorAction SilentlyContinue
Gate 'uv' ($(if ($uv) { 'VERIFIED' } else { 'FAILED' })) ($(if ($uv) { (uv --version) } else { 'install uv' }))
Gate 'Gateway venv' ($(if (Test-Path $GatewayPython) { 'VERIFIED' } else { 'FAILED' })) 'adapter\.venv (cd adapter; uv sync)'

$staad = @(Get-Process -Name 'Bentley.Staad' -ErrorAction SilentlyContinue)
Gate 'STAAD.Pro running' ($(if ($staad) { 'VERIFIED' } else { 'FAILED' })) "$($staad.Count) process(es)"

$progid = Test-Path 'Registry::HKEY_CLASSES_ROOT\MicroStationDGN.Application'
Gate 'Bentley COM ProgID' ($(if ($progid) { 'VERIFIED' } else { 'FAILED' })) 'HKCR\MicroStationDGN.Application (Bentley bridge dependency)'
$bentley = @(Get-Process microstation, OpenBuildingsDesigner -ErrorAction SilentlyContinue)
Gate 'Bentley app running' ($(if ($bentley) { 'VERIFIED' } else { 'UNVERIFIED' })) "$($bentley.Count) process(es); a DGN must be open for tools to attach"

if (-not $SkipLiveMcp -and (Test-Path $GatewayPython)) {
    Push-Location $Adapter
    $j = & $GatewayPython tests\live_baseline.py 2>$null | Out-String
    Pop-Location
    try {
        $b = $j | ConvertFrom-Json
        $tools = ($b.tools.name -join ',')
        $ok = $b.get_status.structured.connected -eq $true
        Gate 'Upstream MCP init/tools/status' ($(if ($ok) { 'VERIFIED' } else { 'FAILED' })) "protocol=$($b.protocol_version) tools=$tools connected=$($b.get_status.structured.connected)"
    } catch { Gate 'Upstream MCP init/tools/status' 'FAILED' 'baseline probe did not return JSON' }
}

if (-not $SkipLiveMcp -and $bentley -and (Test-Path $GatewayPython)) {
    Push-Location $Adapter
    $bj = & $GatewayPython tests\bentley_baseline.py 2>$null | Out-String
    Pop-Location
    try {
        $bb = $bj | ConvertFrom-Json
        Gate 'Bentley COM attach/status' ($(if ($bb.ok) { 'VERIFIED' } else { 'FAILED' })) "design=$($bb.status.design_file) model=$($bb.status.model)"
    } catch { Gate 'Bentley COM attach/status' 'FAILED' 'bentley_baseline.py did not return JSON' }
}

$local = Read-EnvFile (Join-Path $Root '.env.local')
Gate '.env.local allowed OID' ($(if ($local['STAAD_GW_ALLOWED_OIDS']) { 'VERIFIED' } else { 'FAILED' })) 'STAAD_GW_ALLOWED_OIDS set'

$dt = Get-DevTunnelExe
$who = & $dt user show 2>&1 | Out-String
Gate 'devtunnel login' ($(if ($who -match 'Logged in') { 'VERIFIED' } else { 'FAILED' })) 'devtunnel user login -e -w'
$show = & $dt show $TunnelId 2>&1 | Out-String
Gate 'Tunnel exists' ($(if ($show -match 'Tunnel ID') { 'VERIFIED' } else { 'FAILED' })) ($(if ($show -match 'Ports\s*:\s*(\d+)') { "ports=$($Matches[1])" } else { $TunnelId }))

$atk = Get-Command atk -ErrorAction SilentlyContinue
Gate 'Agents Toolkit CLI' ($(if ($atk) { 'VERIFIED' } else { 'FAILED' })) ($(if ($atk) { "atk $(atk --version)" } else { 'npm i -g @microsoft/m365agentstoolkit-cli' }))
if ($atk) {
    $doc = atk doctor --telemetry false 2>&1 | Out-String
    Gate 'M365 sign-in + Custom App Upload' ($(if ($doc -match 'custom app upload permission is enabled') { 'VERIFIED' } else { 'FAILED' })) 'atk doctor'
}
Gate 'Copilot Access Enabled' 'UNVERIFIED' 'Not exposed by atk CLI; check Agents Toolkit Accounts pane in VS Code'

$e = Get-AgentEnv $EnvName
Gate 'Entra app registration' ($(if ($e['AAD_APP_CLIENT_ID']) { 'VERIFIED' } else { 'FAILED' })) ($(if ($e['AAD_APP_CLIENT_ID']) { 'AAD_APP_CLIENT_ID recorded' } else { 'missing - see docs\RUNBOOK.md "Blocker"' }))
Gate 'Entra SSO auth config' ($(if ($e['MCP_DA_AUTH_ID_STAADASSIS']) { 'VERIFIED' } else { 'FAILED' })) 'MCP_DA_AUTH_ID_STAADASSIS'
Gate 'Sideloaded title' ($(if ($e['M365_TITLE_ID']) { 'VERIFIED' } else { 'FAILED' })) 'M365_TITLE_ID'

$results | Format-Table -AutoSize -Wrap
if ($results.Status -contains 'FAILED') { exit 1 }
