@echo off
setlocal EnableExtensions
cd /d "%~dp0"

where bentley-adapter >nul 2>nul
if errorlevel 1 (
  echo ERROR: bentley-adapter is not installed.
  exit /b 2
)
if not exist "profiles\site.yaml" (
  echo ERROR: profiles\site.yaml is missing.
  exit /b 2
)
if not exist "detected.json" (
  echo ERROR: detected.json is missing. Run deploy.bat first.
  exit /b 2
)

bentley-adapter uninstall --profile profiles\site.yaml --detected detected.json
exit /b %ERRORLEVEL%

