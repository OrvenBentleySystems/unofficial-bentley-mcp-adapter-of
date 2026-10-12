#Requires -Version 7
<#
.SYNOPSIS
  Stops only the gateway/tunnel processes recorded by scripts\start.ps1 (and their children).
  Never touches the user's CLI OpenSTAAD MCP servers or STAAD.Pro.
#>
. "$PSScriptRoot\common.ps1"

$st = Get-State
if (-not $st) { Ok 'Nothing to stop (no .run\state.json).'; return }
if ($st.tunnel_pid) {
    $r = Stop-OwnedTree ([int]$st.tunnel_pid) ([datetime]$st.tunnel_started) "devtunnel.*host.*$TunnelId"
    Ok "Tunnel: $r"
}
if ($st.gateway_pid) {
    $r = Stop-OwnedTree ([int]$st.gateway_pid) ([datetime]$st.gateway_started) 'staad_mcp_gateway\.app'
    Ok "Gateway: $r"
}
Start-Sleep -Seconds 1
if (Test-PortListening ([int]$st.port)) { Warn "Port $($st.port) is still listening." } else { Ok "Port $($st.port) closed" }
Remove-Item $StateFile -Force
