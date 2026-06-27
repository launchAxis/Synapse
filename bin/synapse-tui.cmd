@echo off
setlocal
set "ROOT=%~dp0.."
set "CLI=%ROOT%\terminal-ui\source\cli.js"
if /I "%~1"=="--where" (
  echo Synapse command: %~f0
  echo Synapse root: %ROOT%
  echo Synapse CLI: %CLI%
  exit /b 0
)
cd /d "%ROOT%"
node "%CLI%" %*
endlocal
