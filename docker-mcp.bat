@echo off
setlocal enabledelayedexpansion

:::: docker-mcp.bat: A wrapper for running the MCP wrapper inside Docker.
:::: This script reads from stdin and pipes it to 'python mcp.py' inside the container.

set IMAGE_TAG=kusto-query-cli:1.1.0
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
docker exec -i %MCP_CONTAINER_NAME% python mcp.py %*
exit /b %ERRORLEVEL%
