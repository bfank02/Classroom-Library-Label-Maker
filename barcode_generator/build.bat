@echo off
setlocal
cd /d "%~dp0"

set "PYTHONPATH=src"

REM Resolve product identifiers from metadata.py (single source of truth).
for /f "usebackq delims=" %%A in (`python -c "from classroom_library_label_maker.metadata import APP_CLI_NAME; print(APP_CLI_NAME)"`) do set "CLI_NAME=%%A"
for /f "usebackq delims=" %%A in (`python -c "from classroom_library_label_maker.metadata import APP_NAME, APP_COMPONENT_NAME; print(f'{APP_NAME} — {APP_COMPONENT_NAME}')"`) do set "PRODUCT_LABEL=%%A"

REM Optional EXE icon once assets\icons\app.ico contains real icon data.
set "ICON_ARGS="
if exist "assets\icons\app.ico" (
    for %%A in ("assets\icons\app.ico") do (
        if %%~zA GTR 0 set "ICON_ARGS=--icon assets\icons\app.ico"
    )
)

echo Building %PRODUCT_LABEL% with PyInstaller...
python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --name "%CLI_NAME%" ^
    --paths src ^
    --hidden-import classroom_library_label_maker ^
    --hidden-import classroom_library_label_maker.services ^
    --hidden-import classroom_library_label_maker.utils ^
    --add-data "assets;assets" ^
    %ICON_ARGS% ^
    src\classroom_library_label_maker\__main__.py

if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo Build complete. Output is under dist\
endlocal
