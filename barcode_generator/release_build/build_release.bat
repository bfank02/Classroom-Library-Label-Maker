@echo off
setlocal
cd /d "%~dp0.."

set "PYTHONPATH=src"

echo Building Classroom Library Label Maker Windows release...
python release_build\build_windows_release.py
if errorlevel 1 (
    echo Release build failed.
    exit /b 1
)

echo Done.
endlocal
