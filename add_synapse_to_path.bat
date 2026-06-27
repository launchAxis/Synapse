@echo off
setlocal
set "ROOT=%~dp0"
set "BIN=%ROOT%bin"
set "DRY_RUN="
if /I "%~1"=="--dry-run" set "DRY_RUN=1"

where node.exe >nul 2>nul
if errorlevel 1 (
  echo node.exe was not found. Install Node.js first, then run this again.
  exit /b 1
)

if not exist "%BIN%" mkdir "%BIN%"

> "%BIN%\synapse.cmd" echo @echo off
>> "%BIN%\synapse.cmd" echo setlocal
>> "%BIN%\synapse.cmd" echo set "ROOT=%%~dp0.."
>> "%BIN%\synapse.cmd" echo set "CLI=%%ROOT%%\terminal-ui\source\cli.js"
>> "%BIN%\synapse.cmd" echo if /I "%%~1"=="--where" ^(
>> "%BIN%\synapse.cmd" echo   echo Synapse command: %%~f0
>> "%BIN%\synapse.cmd" echo   echo Synapse root: %%ROOT%%
>> "%BIN%\synapse.cmd" echo   echo Synapse CLI: %%CLI%%
>> "%BIN%\synapse.cmd" echo   exit /b 0
>> "%BIN%\synapse.cmd" echo ^)
>> "%BIN%\synapse.cmd" echo cd /d "%%ROOT%%"
>> "%BIN%\synapse.cmd" echo node "%%CLI%%" %%*
>> "%BIN%\synapse.cmd" echo endlocal

copy /Y "%BIN%\synapse.cmd" "%BIN%\synapse-tui.cmd" >nul

if defined DRY_RUN (
  echo Dry run: would place this folder first on your user PATH and remove stale Synapse package bin paths:
  echo   %BIN%
  echo No PATH changes were made.
  exit /b 0
)

set "SYNAPSE_BIN=%BIN%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$bin=(Resolve-Path -LiteralPath $env:SYNAPSE_BIN).Path.TrimEnd('\'); $userPath=[Environment]::GetEnvironmentVariable('Path','User'); $items=if ([string]::IsNullOrWhiteSpace($userPath)) { @() } else { @($userPath -split ';' | Where-Object { $_ }) }; $filtered=@(); foreach ($item in $items) { $trim=$item.Trim().TrimEnd('\'); $lower=$trim.ToLowerInvariant(); if (($lower -like '*\synapse 0.3 staging\synapse 0.3.0 windows\bin') -or ($lower -like '*\synapse 0.3.0 windows\bin')) { continue }; if ($filtered -notcontains $trim) { $filtered += $trim } }; $new=@($bin) + @($filtered | Where-Object { $_ -ne $bin }); [Environment]::SetEnvironmentVariable('Path', ($new -join ';'), 'User'); Write-Host 'Placed first on user PATH:' $bin"
if errorlevel 1 exit /b 1

echo.
echo Synapse terminal commands are ready:
echo   synapse
echo   synapse-tui
echo.
echo Open a new terminal before using them.
echo Check the active launcher with: synapse --where
endlocal
