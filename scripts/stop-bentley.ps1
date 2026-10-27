#Requires -Version 7
<#
.SYNOPSIS
  Stops the Bentley MCP server started by start-bentley.ps1.
.DESCRIPTION
  Uses the PID recorded in .run\bentley.json and only stops the process if its
  command line still matches bentley_mcp.server. Does not touch MicroStation,
  OpenBuildings, the STAAD gateway, or its tunnel.
#>
. "$PSScriptRoot\common.ps1"

$BentleyState = Join-Path $RunDir 'bentley.json'
if (-not (Test-Path $BentleyState)) {
    Ok 'Bentley MCP is not running (no state file).'
    exit 0
}

$state = Get-Content $BentleyState -Raw | ConvertFrom-Json
$result = Stop-OwnedTree -rootPid ([int]$state.pid) -startedAt ([datetime]$state.started) -expectPattern 'bentley_mcp\.server'
Ok "Bentley MCP: $result"

if ([bool](Get-NetTCPConnection -LocalPort ([int]$state.port) -State Listen -ErrorAction SilentlyContinue)) {
    Warn "port $($state.port) is still listening; another process may own it."
}
Remove-Item $BentleyState -Force
