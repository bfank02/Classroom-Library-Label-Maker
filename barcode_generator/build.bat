@echo off
setlocal
cd /d "%~dp0"

set "PYTHONPATH=src"

REM Shared cross-platform packaging entry point (Windows EXE).
REM Prefer an active venv Python when available.
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo Generating application icons...
%PY% scripts\generate_app_icons.py
if errorlevel 1 (
    echo Icon generation failed.
    exit /b 1
)

echo Building desktop release with PyInstaller...
%PY% scripts\build_release.py %*
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo Build complete. Output is under dist\
endlocal
