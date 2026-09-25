@echo off
setlocal DisableDelayedExpansion
rem Return KQC_RESOLVED_IMAGE to the caller. Status/errors go to stderr.
if not defined KQC_IMAGE goto local_image
if /I "%~1"=="--force" (
    >&2 echo Error: --force rebuilds local images and cannot be used with KQC_IMAGE. Unset KQC_IMAGE to build locally.
    exit /b 1
)
docker image inspect "%KQC_IMAGE%" >nul 2>&1
if not errorlevel 1 goto external_ready
>&2 echo Pulling selected image %KQC_IMAGE%...
docker pull "%KQC_IMAGE%" 1>&2
if errorlevel 1 (
    >&2 echo Error: cannot pull KQC_IMAGE. No local build was attempted.
    exit /b 1
)
:external_ready
endlocal & set "KQC_RESOLVED_IMAGE=%KQC_IMAGE%" & exit /b 0

:local_image
set "KQC_BUILT_IMAGE="
call "%~dp0..\build.bat" %~1 >nul
if errorlevel 1 exit /b 1
if not defined KQC_BUILT_IMAGE exit /b 1
endlocal & set "KQC_RESOLVED_IMAGE=%KQC_BUILT_IMAGE%" & exit /b 0
