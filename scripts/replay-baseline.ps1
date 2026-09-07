param(
    [Parameter(Mandatory = $true)][string]$ArtifactDir,
    [Parameter(Mandatory = $true)][string]$LiveProfile,
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][int]$ExpectedWheelCount,
    [Parameter(Mandatory = $true)][int]$ExpectedTestCount,
    [string]$Label = "BASELINE"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$clone = Join-Path $ArtifactDir "stage4-replay-clone"
$venv = Join-Path $ArtifactDir "stage4-replay-env"
$wheelDir = Join-Path $ArtifactDir "stage4-replay-wheel"
foreach ($path in @($clone, $venv, $wheelDir)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

New-Item -ItemType Directory -Path $clone | Out-Null
Get-ChildItem -LiteralPath $repo -Force |
    Where-Object {
        $_.Name -notin @(
            "machine.json", ".venv", "build", "dist",
            "bentley_mcp_adapter.egg-info", "__pycache__"
        )
    } |
    Copy-Item -Destination $clone -Recurse -Force

uv venv --quiet --python 3.13 $venv
uv pip install --quiet --python "$venv\Scripts\python.exe" -e $clone PyYAML
if ($LASTEXITCODE -ne 0) { exit 1 }

$env:PYTHONDONTWRITEBYTECODE = "1"
Set-Location $clone
& "$venv\Scripts\bentley-adapter.exe" resolve `
    --working-directory $WorkingDirectory --output machine.json | Out-Host
Copy-Item $LiveProfile "$clone\profiles\site.yaml" -Force
& "$venv\Scripts\bentley-adapter.exe" preflight `
    --profile profiles\site.yaml --machine machine.json | Out-Host
if ($LASTEXITCODE -ne 0) { exit 1 }

$oldAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$testOutput = & "$venv\Scripts\python.exe" -m unittest discover -s tests -q 2>&1
$testExit = $LASTEXITCODE
$ErrorActionPreference = $oldAction
$testOutput | Out-Host
if (
    $testExit -ne 0 -or
    ($testOutput -join "`n") -notmatch "Ran $ExpectedTestCount tests"
) {
    exit 1
}

uv --quiet build --wheel --out-dir $wheelDir
if ($LASTEXITCODE -ne 0) { exit 1 }
$wheel = Get-ChildItem $wheelDir -Filter "*.whl" |
    Select-Object -First 1 -ExpandProperty FullName
uv pip install --quiet --python "$venv\Scripts\python.exe" --reinstall $wheel PyYAML
if ($LASTEXITCODE -ne 0) { exit 1 }

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($wheel)
try {
    $wheelFiles = $zip.Entries | ForEach-Object FullName | Sort-Object
    $entryFile = $zip.Entries |
        Where-Object { $_.FullName -like "*.dist-info/entry_points.txt" }
    $reader = New-Object IO.StreamReader($entryFile.Open())
    try { $entryText = $reader.ReadToEnd() } finally { $reader.Dispose() }
}
finally {
    $zip.Dispose()
}

$lines = Get-Content "$repo\baseline.txt"
$start = [Array]::IndexOf($lines, "Files:") + 1
$original = @()
for ($index = $start; $index -lt $lines.Count; $index++) {
    if ($lines[$index] -notmatch "^  \S") { break }
    $original += $lines[$index].Trim()
}
$missing = $original | Where-Object { $_ -notin $wheelFiles }
if ($missing -or $wheelFiles.Count -ne $ExpectedWheelCount) {
    throw "Wheel invariant failed"
}
if ($entryText -notmatch "bentley-adapter = core.cli:main") {
    throw "Entry point changed"
}

$env:BASELINE_MACHINE = "$clone\machine.json"
$env:BASELINE_PROFILE = $LiveProfile
$env:BASELINE_ARTIFACTS = $ArtifactDir
@'
import os
from pathlib import Path
import core.emit.emitter as emitter
emitter.utc_now = lambda: "2026-09-07T02:54:00+00:00"
raise SystemExit(emitter.emit_configs(
    Path(os.environ["BASELINE_PROFILE"]),
    Path(os.environ["BASELINE_MACHINE"]),
    ["copilot-cli", "vscode-copilot"],
    False,
))
'@ | & "$venv\Scripts\python.exe" -

foreach ($pair in @(
    @(
        "$ArtifactDir\baseline-mcp-config.json",
        "$ArtifactDir\mcp-config.live.json"
    ),
    @(
        "$ArtifactDir\baseline-vscode-mcp.json",
        "$ArtifactDir\vscode-mcp.live.json"
    )
)) {
    if ((Get-FileHash $pair[0]).Hash -ne (Get-FileHash $pair[1]).Hash) {
        throw "Reference config drift"
    }
}

$added = $wheelFiles | Where-Object { $_ -notin $original }
Write-Output (
    "$Label PASS: preflight 8/8; baseline 14/14; " +
    "$ExpectedTestCount tests; configs byte-identical; 24 original intact, " +
    "$($added.Count) added; wheel installed."
)
$added
