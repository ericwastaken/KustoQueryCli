@echo off
setlocal enabledelayedexpansion

rem docker-mcp-build.bat: Build the Docker image for the MCP stdio server only.
rem Writes IMAGE_TAG to stdout on success. Status/errors are written to stderr.

rem Always execute from the directory where this script resides so relative paths work.
pushd %~dp0 >nul

set ENV_FILE=%~dp0.env

rem Parse args (support --force)
set FORCE=
:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--force" (
  set FORCE=1
  shift
  goto parse_args
)
shift
goto parse_args
:args_done

rem Resolve version: env var > mcp-wrapper-version > dev
if "%KUSTO_QUERY_CLI_VERSION%"=="" (
  if exist "%~dp0mcp-wrapper-version" (
    set /p KUSTO_QUERY_CLI_VERSION=<"%~dp0mcp-wrapper-version"
  ) else (
    set KUSTO_QUERY_CLI_VERSION=dev
  )
)

set IMAGE_TAG=kusto-query-cli:%KUSTO_QUERY_CLI_VERSION%

rem Ensure we are in the project root
if not exist "Dockerfile" (
    >&2 echo Error: Dockerfile not found in the current directory.
    popd >nul
    exit /b 1
)

rem If forced, attempt to remove existing image first
if defined FORCE (
    docker image inspect %IMAGE_TAG% >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        >&2 echo --force specified: removing existing image %IMAGE_TAG% before rebuild...
        docker rmi -f %IMAGE_TAG% >nul 2>&1
    )
)

rem Check if image exists, build if missing
docker image inspect %IMAGE_TAG% >nul 2>&1
if %ERRORLEVEL% neq 0 (
    >&2 echo Image %IMAGE_TAG% not found. Building now...
) else if defined FORCE (
    >&2 echo Building image %IMAGE_TAG% (forced rebuild)...
) else (
    goto echo_tag
)

docker build -t %IMAGE_TAG% .
if !ERRORLEVEL! neq 0 (
    >&2 echo Error: Failed to build %IMAGE_TAG%.
    popd >nul
    exit /b 1
)

rem Output the image tag to stdout for callers to consume
:echo_tag
echo %IMAGE_TAG%

popd >nul
exit /b 0
