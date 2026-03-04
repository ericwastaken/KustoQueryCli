@echo off
setlocal enabledelayedexpansion

rem Always execute from the directory where this script resides so relative paths work.
pushd %~dp0 >nul

:::: docker-mcp.bat: Launch the MCP stdio server inside Docker on Windows.
:::: Runs 'python mcp-stdio-server.py' with stdio attached for MCP clients.

set ENV_FILE=%~dp0.env

rem Resolve version tag from env var or .env file
if "%KUSTO_QUERY_CLI_VERSION%"=="" (
  if exist "%ENV_FILE%" (
    for /f "tokens=2 delims==" %%a in ('findstr /R "^KUSTO_QUERY_CLI_VERSION=" "%ENV_FILE%"') do set KUSTO_QUERY_CLI_VERSION=%%a
  )
)

if "%KUSTO_QUERY_CLI_VERSION%"=="" (
  rem Fall back to dev if not provided
  set KUSTO_QUERY_CLI_VERSION=dev
)

set IMAGE_TAG=kusto-query-cli:%KUSTO_QUERY_CLI_VERSION%

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

:::: Ensure we are in the project root
if not exist "Dockerfile" (
    echo Error: Dockerfile not found in the current directory. >&2
    popd >nul
    exit /b 1
)

:::: Check if image exists, build if missing
docker image inspect %IMAGE_TAG% >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Image %IMAGE_TAG% not found. Building now...
    docker build -t %IMAGE_TAG% .
    if !ERRORLEVEL! neq 0 (
        echo Error: Failed to build %IMAGE_TAG%. >&2
        popd >nul
        exit /b 1
    )
)

:::: Run the MCP stdio server in a fresh, auto-removed container (stdin attached)
docker run --rm -i %NAME_FLAG% %ENV_FLAGS% ^
  -v "%AZURE_STATE_VOLUME%:/root/.azure" ^
  %IMAGE_TAG% ^
  python mcp-stdio-server.py %*
set EXITCODE=%ERRORLEVEL%
popd >nul
exit /b %EXITCODE%
