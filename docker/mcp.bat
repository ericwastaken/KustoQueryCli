@echo off
setlocal DisableDelayedExpansion

rem Execute from the project root so image acquisition and paths are stable.
pushd "%~dp0.." >nul
if errorlevel 1 exit /b 1

:::: docker/mcp.bat: Launch the MCP stdio server inside Docker on Windows.
:::: Runs 'python mcp-stdio-server.py' with stdio attached for MCP clients.

set ENV_FILE=%~dp0.env

rem Parse args: support --force for rebuild, --share-host-azure-state for a
rem host bind mount; pass all others to the server
set FORCE=
set SHARE_HOST_AZURE_STATE=
set PASSTHRU_ARGS=
:parse_loop
if "%~1"=="" goto parse_done
if /I "%~1"=="--force" (
  set FORCE=1
  shift
  goto parse_loop
)
if /I "%~1"=="--share-host-azure-state" (
  set SHARE_HOST_AZURE_STATE=1
  shift
  goto parse_loop
)
set PASSTHRU_ARGS=%PASSTHRU_ARGS% "%~1"
shift
goto parse_loop
:parse_done

rem Acquire the image independently of MCP execution and auth state.
set FORCE_FLAG=
if defined FORCE set FORCE_FLAG=--force
set "KQC_RESOLVED_IMAGE="
call "%~dp0lib\acquire-image.bat" %FORCE_FLAG%
if errorlevel 1 (
  popd >nul
  exit /b 1
)
set "IMAGE_TAG=%KQC_RESOLVED_IMAGE%"

rem Optional explicit container name provided by caller environment
rem If not set, we omit --name so multiple instances can run concurrently
set NAME_FLAG=
if defined MCP_CONTAINER_NAME (
  set NAME_FLAG=--name "%MCP_CONTAINER_NAME%"
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
  set ENV_FLAGS=%ENV_FLAGS% -e "MCP_LOG_LEVEL=%MCP_LOG_LEVEL%"
)
if defined MCP_LOG_PAYLOADS (
  set ENV_FLAGS=%ENV_FLAGS% -e "MCP_LOG_PAYLOADS=%MCP_LOG_PAYLOADS%"
)

rem Use a stable/shared Azure CLI state volume by default (overridable)
if not defined AZURE_STATE_VOLUME set AZURE_STATE_VOLUME=kusto-query-cli-mcp-azure-state
set AZURE_MOUNT_SOURCE=%AZURE_STATE_VOLUME%
set MCP_AZURE_AUTH_MODE=container_managed
if defined SHARE_HOST_AZURE_STATE set AZURE_MOUNT_SOURCE=%USERPROFILE%\.azure
if defined SHARE_HOST_AZURE_STATE set MCP_AZURE_AUTH_MODE=host_shared
rem Image acquisition succeeded; use the selected image without fallback.

:::: Run the MCP stdio server in a fresh, auto-removed container (stdin attached)
docker run --rm -i %NAME_FLAG% %ENV_FLAGS% ^
  -e "MCP_AZURE_AUTH_MODE=%MCP_AZURE_AUTH_MODE%" ^
  -v "%AZURE_MOUNT_SOURCE%:/root/.azure" ^
  "%IMAGE_TAG%" ^
  python mcp-stdio-server.py %PASSTHRU_ARGS%
set EXITCODE=%ERRORLEVEL%
popd >nul
exit /b %EXITCODE%
