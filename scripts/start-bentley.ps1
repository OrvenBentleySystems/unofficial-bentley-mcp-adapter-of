#Requires -Version 7
<#
.SYNOPSIS
  Starts the Bentley MCP server in loopback HTTP mode.
.DESCRIPTION
  Serves http://127.0.0.1:<port>/mcp for MicroStation and OpenBuildings control.
  For stdio, point the agent at adapter\.venv\Scripts\python.exe and skip this
  script (see docs\BENTLEY-MCP.md).

  Reads optional BENTLEY_MCP_PORT and BENTLEY_MCP_TOKEN from the current
  environment first, then from .env.local. The token value is never printed or
  written to the state file.
#>
param([int]$Port)

. "$PSScriptRoot\common.ps1"

$BentleyState = Join-Path $RunDir 'bentley.json'
$EnvFile = Read-EnvFile (Join-Path $Root '.env.local')

if ($Port -le 0) {
    if ($env:BENTLEY_MCP_PORT) {
        $Port = [int]$env:BENTLEY_MCP_PORT
    } elseif ($EnvFile['BENTLEY_MCP_PORT']) {
        $Port = [int]$EnvFile['BENTLEY_MCP_PORT']
    } else {
        $Port = 18131
    }
}
if ($Port -lt 1 -or $Port -gt 65535) { Fail "port must be 1..65535, got $Port" }

if (-not $env:BENTLEY_MCP_TOKEN -and $EnvFile['BENTLEY_MCP_TOKEN']) {
    $env:BENTLEY_MCP_TOKEN = $EnvFile['BENTLEY_MCP_TOKEN']
}

if (-not (Test-Path $GatewayPython)) { Fail "adapter venv not found: $GatewayPython. Run: cd adapter; uv sync --group dev" }
if (Test-PortListening $Port) { Fail "port $Port is already listening" }

$Bentley = @(Get-Process microstation, OpenBuildingsDesigner -ErrorAction SilentlyContinue)
if ($Bentley.Count -eq 0) {
    Warn 'No MicroStation/OpenBuildings process detected. Tools will report unavailable until one opens a DGN.'
}

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$outLog = Join-Path $RunDir 'bentley.out.log'
$errLog = Join-Path $RunDir 'bentley.err.log'

$started = Get-Date
$p = Start-Process -FilePath $GatewayPython `
    -ArgumentList '-m', 'bentley_mcp.server', '--http', '--port', "$Port" `
    -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog

$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 300
    if (Test-PortListening $Port) { $ready = $true; break }
    if ($p.HasExited) { break }
}
if (-not $ready) {
    if (Test-Path $errLog) { Get-Content $errLog -Tail 20 | ForEach-Object { Write-Host $_ } }
    if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    Fail "Bentley MCP did not start on port $Port (see $errLog)"
}

[pscustomobject]@{
    pid     = $p.Id
    port    = $Port
    started = $started.ToString('o')
    auth    = [bool]$env:BENTLEY_MCP_TOKEN
} | ConvertTo-Json | Set-Content -Path $BentleyState -Encoding utf8

Ok "Bentley MCP on http://127.0.0.1:$Port/mcp (pid $($p.Id))"
if ($env:BENTLEY_MCP_TOKEN) {
    Write-Host '     Auth: Authorization: Bearer <BENTLEY_MCP_TOKEN>'
} else {
    Warn 'BENTLEY_MCP_TOKEN is not set; any local process can call the endpoint.'
}
Write-Host "     Logs: $errLog"
Write-Host "     Stop: pwsh scripts\stop-bentley.ps1"
