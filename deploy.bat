@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "MODE=deploy"
set "EMIT_MODE=--auto"
set "CONTEXT_MODE=--auto"
if /I "%~1"=="--check" set "MODE=check"
if /I "%~1"=="--client" (
  if "%~2"=="" (
    echo ERROR: --client requires a target id.
    exit /b 2
  )
  set "EMIT_MODE=--target %~2"
  set "CONTEXT_MODE=--target %~2"
)

where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python launcher not found. Install CPython 3.13 and put py.exe on PATH.
  exit /b 2
)
call py -3.13 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,13) else 1)" >nul 2>nul
if errorlevel 1 (
  echo ERROR: CPython 3.13 is required.
  exit /b 2
)
if not exist "profiles\site.yaml" (
  echo ERROR: profiles\site.yaml is missing. Copy and complete profiles\site.example.yaml.
  exit /b 2
)

if /I "%MODE%"=="check" (
  set "CHECK_DIR=%TEMP%\bentley-adapter-check-%RANDOM%"
  mkdir "!CHECK_DIR!" >nul
  bentley-adapter resolve --output "!CHECK_DIR!\machine.json"
  if errorlevel 1 exit /b !errorlevel!
  bentley-adapter detect --profile profiles\site.yaml --machine "!CHECK_DIR!\machine.json" --output "!CHECK_DIR!\detected.json"
  if errorlevel 1 exit /b !errorlevel!
  bentley-adapter preflight --profile profiles\site.yaml --machine "!CHECK_DIR!\machine.json"
  set "RESULT=!ERRORLEVEL!"
  rmdir /s /q "!CHECK_DIR!"
  exit /b !RESULT!
)

for %%F in ("dist\bentley_mcp_adapter-*.whl") do set "WHEEL=%%~fF"
if not defined WHEEL (
  echo ERROR: No adapter wheel found in dist\. Build the release wheel before deployment.
  exit /b 2
)
call py -3.13 -m pip install --upgrade --force-reinstall --no-deps "%WHEEL%"
if errorlevel 1 exit /b %errorlevel%

bentley-adapter resolve --output machine.json
if errorlevel 1 exit /b %errorlevel%
bentley-adapter detect --profile profiles\site.yaml --machine machine.json --output detected.json
if errorlevel 1 exit /b %errorlevel%
echo NOTE: Cline local-provider selection is a manual UI step. See docs\LOCAL-MODELS.md.

bentley-adapter emit-context --profile profiles\site.yaml --detected detected.json %CONTEXT_MODE%
if errorlevel 1 exit /b %errorlevel%

bentley-adapter emit --profile profiles\site.yaml --machine machine.json --detected detected.json %EMIT_MODE% --dry-run
if errorlevel 1 exit /b %errorlevel%
set /p "CONFIRM=Apply the displayed client configuration changes? Type YES: "
if /I not "%CONFIRM%"=="YES" (
  echo Deployment cancelled. No client config was written.
  exit /b 3
)
bentley-adapter emit --profile profiles\site.yaml --machine machine.json --detected detected.json %EMIT_MODE%
if errorlevel 1 exit /b %errorlevel%
bentley-adapter preflight --profile profiles\site.yaml --machine machine.json
if errorlevel 1 exit /b %errorlevel%

echo Deployment complete.
echo Review detected.json for client restart notes and the PLAXIS port map.
exit /b 0
