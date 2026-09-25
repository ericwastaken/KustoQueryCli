@echo off
setlocal DisableDelayedExpansion
rem Build locally. Only the resulting image reference is written to stdout.
if defined KQC_IMAGE (
    >&2 echo Error: docker/build.bat builds locally. Unset KQC_IMAGE first, or use a Docker launcher to run the selected image.
    exit /b 1
)
pushd "%~dp0.." >nul
if errorlevel 1 exit /b 1
set "FORCE="
:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--force" set "FORCE=1"
shift
goto parse_args
:args_done
if not defined KUSTO_QUERY_CLI_VERSION if exist "%~dp0..\kusto_query_cli\assets\mcp-wrapper-version" set /p KUSTO_QUERY_CLI_VERSION=<"%~dp0..\kusto_query_cli\assets\mcp-wrapper-version"
if not defined KUSTO_QUERY_CLI_VERSION set "KUSTO_QUERY_CLI_VERSION=dev"
set "IMAGE_TAG=kusto-query-cli:%KUSTO_QUERY_CLI_VERSION%"
if not exist "docker\Dockerfile" (
    >&2 echo Error: Dockerfile not found in the project directory.
    goto failed
)
if defined FORCE goto build_image
docker image inspect "%IMAGE_TAG%" >nul 2>&1
if not errorlevel 1 goto image_ready
:build_image
>&2 echo Building local image %IMAGE_TAG%...
docker build -f docker/Dockerfile -t "%IMAGE_TAG%" . 1>&2
if errorlevel 1 goto failed
:image_ready
echo %IMAGE_TAG%
popd >nul
endlocal & set "KQC_BUILT_IMAGE=%IMAGE_TAG%" & exit /b 0
:failed
>&2 echo Error: local Docker image preparation failed.
popd >nul
exit /b 1
