#Requires -Version 7
<#
.SYNOPSIS
  Starts the project-owned STAAD MCP gateway (loopback) and hosts the persistent dev tunnel.
.DESCRIPTION
  * Gateway: adapter venv python -m staad_mcp_gateway.app on 127.0.0.1:<port>. It spawns its own
    OpenSTAAD MCP child over stdio. The user's CLI OpenSTAAD MCP servers are not touched.
  * Tunnel: devtunnel host staad-assistant-gw (anonymous connect; Entra auth is enforced by the gateway).
  * Records PIDs/start times in .run\state.json for scripts\stop.ps1.
#>
param([string]$EnvName = 'dev', [switch]$NoTunnel)
. "$PSScriptRoot\common.ps1"

if (-not (Test-Path $GatewayPython)) { Fail "Gateway venv missing. Run: cd adapter; uv sync" }
$state = Get-State
if ($state) {
    $alive = @($state.gateway_pid, $state.tunnel_pid) | Where-Object { $_ -and (Get-Process -Id $_ -ErrorAction SilentlyContinue) }
    if ($alive) { Fail "Already running (PIDs $($alive -join ', ')); endpoint $($state.public_url). To restart: pwsh scripts\stop.ps1; pwsh scripts\start.ps1" }
}

$agentEnv = Get-AgentEnv $EnvName
$local = Read-EnvFile (Join-Path $Root '.env.local')
$port = if ($local['STAAD_GW_PORT']) { [int]$local['STAAD_GW_PORT'] } else { 18130 }
if (Test-PortListening $port) { Fail "Port $port is already in use by another process. Free it or set STAAD_GW_PORT (and re-create the tunnel port)." }

$tenant = if ($agentEnv['AAD_APP_TENANT_ID']) { $agentEnv['AAD_APP_TENANT_ID'] } else { $local['STAAD_GW_TENANT_ID'] }
if (-not $tenant) { Fail 'Tenant ID unknown: set STAAD_GW_TENANT_ID in .env.local (or provision first).' }
if (-not $local['STAAD_GW_ALLOWED_OIDS']) { Fail 'Set STAAD_GW_ALLOWED_OIDS (your Entra user object ID) in .env.local. See .env.example.' }

$audiences = @($agentEnv['MCP_DA_APPLICATION_ID_URI_STAADASSIS'], $agentEnv['AAD_APP_CLIENT_ID']) | Where-Object { $_ }
if (-not $audiences) {
    Warn 'Agent not provisioned yet: no Entra audience known. Gateway will start but reject every token (fail-closed).'
    $audiences = @('api://staad-assistant-not-provisioned')
}

New-Item -ItemType Directory -Force $RunDir | Out-Null
$env:STAAD_GW_TENANT_ID = $tenant
$env:STAAD_GW_AUDIENCES = ($audiences -join ',')
$env:STAAD_GW_ALLOWED_OIDS = $local['STAAD_GW_ALLOWED_OIDS']
$env:STAAD_GW_PORT = "$port"
$env:STAAD_GW_LOG_DIR = (Join-Path $Root 'logs')
foreach ($k in 'STAAD_GW_REQUIRED_SCOPES', 'STAAD_GW_ALLOWED_CLIENT_IDS', 'STAAD_GW_UPSTREAM_TIMEOUT_S', 'STAAD_GW_MAX_BODY_BYTES') {
    if ($local[$k]) { Set-Item "env:$k" $local[$k] }
}

$gw = Start-Process -FilePath $GatewayPython -ArgumentList '-m', 'staad_mcp_gateway.app' -WorkingDirectory $Root `
    -RedirectStandardError (Join-Path $RunDir 'gateway.log') -RedirectStandardOutput (Join-Path $RunDir 'gateway.out.log') `
    -WindowStyle Hidden -PassThru
$deadline = (Get-Date).AddSeconds(60)
while (-not (Test-PortListening $port)) {
    if ($gw.HasExited) { Get-Content (Join-Path $RunDir 'gateway.log') -Tail 20; Fail "Gateway exited (code $($gw.ExitCode))." }
    if ((Get-Date) -gt $deadline) { Fail 'Gateway did not start listening within 60s. See .run\gateway.log' }
    Start-Sleep -Milliseconds 500
}
$listen = Get-NetTCPConnection -LocalPort $port -State Listen | Select-Object -First 1
if ($listen.LocalAddress -notin @('127.0.0.1')) { Fail "Gateway is listening on $($listen.LocalAddress), expected 127.0.0.1 only." }
Ok "Gateway PID $($gw.Id) listening on 127.0.0.1:$port"

$st = [ordered]@{ env = $EnvName; port = $port; gateway_pid = $gw.Id; gateway_started = $gw.StartTime.ToString('o'); tunnel_pid = $null; tunnel_started = $null; public_url = $null }
$st | ConvertTo-Json | Set-Content $StateFile

$r = Invoke-WebRequest "http://127.0.0.1:$port/mcp" -Method Post -Body '{}' -ContentType 'application/json' -SkipHttpErrorCheck
if ($r.StatusCode -ne 401) { Fail "Loopback unauthenticated request returned $($r.StatusCode), expected 401." }
Ok 'Loopback request without token rejected (401)'

if ($NoTunnel) { return }

$dt = Get-DevTunnelExe
$tunnelLog = Join-Path $RunDir 'tunnel.log'
$tn = Start-Process -FilePath $dt -ArgumentList 'host', $TunnelId -RedirectStandardOutput $tunnelLog `
    -RedirectStandardError (Join-Path $RunDir 'tunnel.err.log') -WindowStyle Hidden -PassThru
$url = $null; $deadline = (Get-Date).AddSeconds(60)
while (-not $url) {
    if ($tn.HasExited) { Get-Content (Join-Path $RunDir 'tunnel.err.log') -Tail 20; Fail 'devtunnel host exited. Is `devtunnel user login` done and the tunnel created? See docs\RUNBOOK.md' }
    if ((Get-Date) -gt $deadline) { Fail 'Tunnel URL not reported within 60s. See .run\tunnel.log' }
    Start-Sleep -Milliseconds 500
    $m = Select-String -Path $tunnelLog -Pattern "https://[a-z0-9\-]+-$port\.[a-z0-9]+\.devtunnels\.ms" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($m) { $url = $m.Matches[0].Value.TrimEnd('/') + '/mcp' }
}
$st.tunnel_pid = $tn.Id; $st.tunnel_started = $tn.StartTime.ToString('o'); $st.public_url = $url
$st | ConvertTo-Json | Set-Content $StateFile
Ok "Tunnel PID $($tn.Id) public endpoint: $url"

if ($agentEnv['MCP_SERVER_URL'] -and $agentEnv['MCP_SERVER_URL'] -ne $url) {
    Warn "Endpoint differs from agent\env\.env.$EnvName MCP_SERVER_URL ($($agentEnv['MCP_SERVER_URL'])). Update it and re-run scripts\provision.ps1."
}

$r = $null
for ($i = 0; $i -lt 10 -and -not $r; $i++) {
    try { $r = Invoke-WebRequest $url -Method Post -Body '{}' -ContentType 'application/json' -SkipHttpErrorCheck -TimeoutSec 20 } catch { Start-Sleep 2 }
}
if (-not $r -or $r.StatusCode -ne 401) { Warn "HTTPS unauthenticated probe returned $($r.StatusCode); expected 401. Run scripts\test-https.ps1." }
else { Ok 'HTTPS request without token rejected (401)' }
