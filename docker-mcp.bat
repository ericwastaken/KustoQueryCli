@echo off
setlocal enabledelayedexpansion

rem Always execute from the directory where this script resides so relative paths work.
pushd %~dp0 >nul

:::: docker-mcp.bat: A wrapper for running the MCP wrapper inside Docker.
:::: This script reads from stdin and pipes it to 'python mcp-wrapper.py' inside the container.

set ENV_FILE=%~dp0.env

if not exist "%ENV_FILE%" (
    echo Error: .env file not found at %ENV_FILE% >&2
    echo The .env file must exist and contain KUSTO_QUERY_CLI_VERSION variable. >&2
    exit /b 1
)

set KUSTO_QUERY_CLI_VERSION=
for /f "tokens=2 delims==" %%a in ('findstr /R "^KUSTO_QUERY_CLI_VERSION=" "%ENV_FILE%"') do set KUSTO_QUERY_CLI_VERSION=%%a

if "%KUSTO_QUERY_CLI_VERSION%"=="" (
    echo Error: KUSTO_QUERY_CLI_VERSION not set in %ENV_FILE% >&2
    echo Please add KUSTO_QUERY_CLI_VERSION=^<version^> to your .env file. >&2
    exit /b 1
)

set IMAGE_TAG=kusto-query-cli:%KUSTO_QUERY_CLI_VERSION%
set MCP_CONTAINER_NAME=kusto-query-cli-mcp
set AZURE_STATE_VOLUME=%MCP_CONTAINER_NAME%-azure-state

:::: Ensure we are in the project root
if not exist "Dockerfile" (
    echo Error: Dockerfile not found in the current directory. >&2
    exit /b 1
)

:::: Check if image exists
docker image inspect %IMAGE_TAG% >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Image %IMAGE_TAG% not found. Building now...
    docker build -t %IMAGE_TAG% .
    if !ERRORLEVEL! neq 0 (
        echo Error: Failed to build %IMAGE_TAG%. >&2
        exit /b 1
    )
)

:::: MCP mode behavior:
:::: 1) Use a dedicated container with a fixed name.
:::: 2) If it exists but is not running, remove and re-run to ensure fresh state/volumes.
:::: 3) If it's already running, simply use it via 'docker exec'.

set IS_RUNNING=not_found
for /f "tokens=*" %%i in ('docker inspect -f "{{.State.Running}}" %MCP_CONTAINER_NAME% 2^>nul') do set IS_RUNNING=%%i

if not "%IS_RUNNING%"=="true" (
    if not "%IS_RUNNING%"=="not_found" (
        docker rm %MCP_CONTAINER_NAME% > nul
    )
    
    docker run -d --name %MCP_CONTAINER_NAME% ^
        -v "%AZURE_STATE_VOLUME%:/root/.azure" ^
        %IMAGE_TAG% ^
        tail -f /dev/null > nul
)

:::: Always execute the command via exec. Use -i for stdin.
docker exec -i %MCP_CONTAINER_NAME% python mcp-wrapper.py %*
set EXITCODE=%ERRORLEVEL%
popd >nul
exit /b %EXITCODE%
