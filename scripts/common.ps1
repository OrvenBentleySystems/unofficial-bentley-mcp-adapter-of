#Requires -Version 7
# Shared helpers for STAAD Assistant scripts. Dot-source only.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:Root      = Split-Path -Parent $PSScriptRoot
$script:Adapter   = Join-Path $Root 'adapter'
$script:Agent     = Join-Path $Root 'agent'
$script:RunDir    = Join-Path $Root '.run'
$script:StateFile = Join-Path $RunDir 'state.json'
$script:TunnelId  = 'staad-assistant-gw'
$script:GatewayPython = Join-Path $Adapter '.venv\Scripts\python.exe'

function Fail([string]$msg) { Write-Host "FAIL: $msg" -ForegroundColor Red; exit 1 }
function Ok([string]$msg)   { Write-Host "OK:   $msg" -ForegroundColor Green }
function Warn([string]$msg) { Write-Host "WARN: $msg" -ForegroundColor Yellow }

function Get-DevTunnelExe {
    $c = Get-Command devtunnel -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    $p = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Microsoft.devtunnel_*\devtunnel.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($p) { return $p.FullName }
    Fail 'devtunnel CLI not found. Install: winget install Microsoft.devtunnel --scope user'
}

# Parse KEY=VALUE files (ATK env files, .env.local). Never echoes values.
function Read-EnvFile([string]$path) {
    $h = @{}
    if (-not (Test-Path $path)) { return $h }
    foreach ($line in Get-Content $path) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') { $h[$Matches[1]] = $Matches[2].Trim('"') }
    }
    return $h
}

function Get-AgentEnv([string]$envName = 'dev') {
    $h = Read-EnvFile (Join-Path $Agent "env\.env.$envName")
    foreach ($kv in (Read-EnvFile (Join-Path $Agent "env\.env.$envName.user")).GetEnumerator()) { $h[$kv.Key] = $kv.Value }
    return $h
}

function Get-State {
    if (Test-Path $StateFile) { return Get-Content $StateFile -Raw | ConvertFrom-Json }
    return $null
}

function Get-Descendants([int]$rootPid) {
    $all = Get-CimInstance Win32_Process -Property ProcessId, ParentProcessId, Name, CommandLine, CreationDate
    $result = [System.Collections.Generic.List[object]]::new()
    $queue = [System.Collections.Generic.Queue[int]]::new(); $queue.Enqueue($rootPid)
    while ($queue.Count) {
        $p = $queue.Dequeue()
        foreach ($c in $all | Where-Object { $_.ParentProcessId -eq $p -and $_.ProcessId -ne $p }) {
            $result.Add($c); $queue.Enqueue([int]$c.ProcessId)
        }
    }
    return $result
}

# Stops a recorded process tree only if the root still matches what we started.
function Stop-OwnedTree([int]$rootPid, [datetime]$startedAt, [string]$expectPattern) {
    $root = Get-CimInstance Win32_Process -Filter "ProcessId=$rootPid" -ErrorAction SilentlyContinue
    if (-not $root) { return 'not-running' }
    $created = $root.CreationDate
    if ([math]::Abs(($created - $startedAt).TotalSeconds) -gt 5 -or ($root.CommandLine -notmatch $expectPattern)) {
        Warn "PID $rootPid no longer matches the process this project started; not touching it."
        return 'skipped-mismatch'
    }
    $tree = @(Get-Descendants $rootPid)
    [array]::Reverse($tree)
    foreach ($c in $tree) { Stop-Process -Id $c.ProcessId -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $rootPid -Force -ErrorAction SilentlyContinue
    return "stopped ($($tree.Count + 1) processes)"
}

function Test-PortListening([int]$port) {
    return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}
