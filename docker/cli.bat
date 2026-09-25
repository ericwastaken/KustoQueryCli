@echo off
setlocal DisableDelayedExpansion
rem Launch the CLI runtime using a local build or explicit KQC_IMAGE.
pushd "%~dp0.." >nul
if errorlevel 1 exit /b 1
set "MODE=run"
set "FORCE_FLAG="
set "PASSTHRU_ARGS="
if /I "%~1"=="down" (
    set "MODE=down"
    shift
    goto collect_args
)
if /I "%~1"=="--force" (
    set "FORCE_FLAG=--force"
    shift
)
:collect_args
if "%~1"=="" goto args_done
set PASSTHRU_ARGS=%PASSTHRU_ARGS% "%~1"
shift
goto collect_args
:args_done
if "%MODE%"=="down" goto compose_down
set "KQC_RESOLVED_IMAGE="
call "%~dp0lib\acquire-image.bat" %FORCE_FLAG%
if errorlevel 1 goto failed
set "KQC_RUNTIME_IMAGE=%KQC_RESOLVED_IMAGE%"
docker compose --project-directory "%~dp0.." --env-file "%~dp0.env" -f "%~dp0compose.yaml" run --rm --pull never kusto-query-cli %PASSTHRU_ARGS%
goto finish
:compose_down
docker compose --project-directory "%~dp0.." --env-file "%~dp0.env" -f "%~dp0compose.yaml" down %PASSTHRU_ARGS%
:finish
set "EXITCODE=%ERRORLEVEL%"
popd >nul
exit /b %EXITCODE%
:failed
popd >nul
exit /b 1
