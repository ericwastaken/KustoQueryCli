@echo off
setlocal enabledelayedexpansion

:: docker-run.bat: A wrapper for docker compose run --rm kusto-query-cli
:: Ensures the image is built before running the container.

set SERVICE_NAME=kusto-query-cli

:: Ensure we are in the directory where docker-compose.yml resides
if not exist "docker-compose.yml" (
    echo Error: docker-compose.yml not found in the current directory. >&2
    exit /b 1
)

:: Special case for 'down' command
if "%~1"=="down" (
    set "ARGS=%*"
    set "ARGS=!ARGS:*down =!"
    if "!ARGS!"=="%*" set "ARGS="
    
    echo Running: docker compose down !ARGS!
    docker compose down !ARGS!
    exit /b %ERRORLEVEL%
)

:: Extract image tag from docker-compose.yml
:: Using PowerShell to parse the YAML file for the image tag
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "$content = Get-Content docker-compose.yml -Raw; if ($content -match 'kusto-query-cli:[\s\S]*?image:\s*(\S+)') { $matches[1] }"`) do set IMAGE_TAG=%%i

if "%IMAGE_TAG%"=="" (
    echo Warning: Could not determine image tag from docker-compose.yml. Forcing build check.
    goto BUILD_CHECK
)

:: Check if image exists
docker images -q %IMAGE_TAG% >nul 2>&1
if %ERRORLEVEL% equ 0 (
    :: Image exists
    goto RUN_COMMAND
)

:BUILD_CHECK
echo Image for %SERVICE_NAME% not found. Building now...
docker compose build %SERVICE_NAME%
if %ERRORLEVEL% neq 0 (
    echo Error: Failed to build %SERVICE_NAME%. >&2
    exit /b 1
)

:RUN_COMMAND
:: Run the command
echo Running: docker compose run --rm %SERVICE_NAME% %*
docker compose run --rm %SERVICE_NAME% %*
exit /b %ERRORLEVEL%
