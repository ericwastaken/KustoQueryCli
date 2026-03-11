@echo off
setlocal enabledelayedexpansion

rem Always execute from the directory where this script resides so relative paths work.
pushd %~dp0 >nul

:::: docker-mcp.bat: Launch the MCP stdio server inside Docker on Windows.
:::: Runs 'python mcp-stdio-server.py' with stdio attached for MCP clients.

set ENV_FILE=%~dp0.env

rem Parse args: support --force for rebuild; pass all others to the server
set FORCE=
set PASSTHRU_ARGS=
:parse_loop
if "%~1"=="" goto parse_done
if /I "%~1"=="--force" (
  set FORCE=1
  shift
  goto parse_loop
)
set PASSTHRU_ARGS=%PASSTHRU_ARGS% "%~1"
shift
goto parse_loop
:parse_done

rem Build (if needed) and retrieve IMAGE_TAG from the build helper to avoid duplication
set FORCE_FLAG=
if defined FORCE set FORCE_FLAG=--force
for /f "usebackq delims=" %%i in (`call "%~dp0docker-mcp-build.bat" %FORCE_FLAG%`) do set IMAGE_TAG=%%i

rem Optional explicit container name provided by caller environment
rem If not set, we omit --name so multiple instances can run concurrently
set NAME_FLAG=
if defined MCP_CONTAINER_NAME (
  set NAME_FLAG=--name %MCP_CONTAINER_NAME%
)

rem Optional: allow overriding logging controls via .env if not set in the environment
if not defined MCP_LOG_LEVEL if exist "%ENV_FILE%" (
  for /f "tokens=2 delims==" %%a in ('findstr /R "^MCP_LOG_LEVEL=" "%ENV_FILE%"') do set MCP_LOG_LEVEL=%%a
)
if not defined MCP_LOG_PAYLOADS if exist "%ENV_FILE%" (
  for /f "tokens=2 delims==" %%a in ('findstr /R "^MCP_LOG_PAYLOADS=" "%ENV_FILE%"') do set MCP_LOG_PAYLOADS=%%a
)

rem Optional env passthrough for logging controls
set ENV_FLAGS=
if defined MCP_LOG_LEVEL (
  set ENV_FLAGS=%ENV_FLAGS% -e MCP_LOG_LEVEL=%MCP_LOG_LEVEL%
)
if defined MCP_LOG_PAYLOADS (
  set ENV_FLAGS=%ENV_FLAGS% -e MCP_LOG_PAYLOADS=%MCP_LOG_PAYLOADS%
)

rem Use a stable/shared Azure CLI state volume by default (overridable)
if not defined AZURE_STATE_VOLUME set AZURE_STATE_VOLUME=kusto-query-cli-mcp-azure-state
rem docker-mcp-build.bat performed Dockerfile check and build if required.

:::: Run the MCP stdio server in a fresh, auto-removed container (stdin attached)
docker run --rm -i %NAME_FLAG% %ENV_FLAGS% ^
  -v "%AZURE_STATE_VOLUME%:/root/.azure" ^
  %IMAGE_TAG% ^
  python mcp-stdio-server.py %PASSTHRU_ARGS%
set EXITCODE=%ERRORLEVEL%
popd >nul
exit /b %EXITCODE%
