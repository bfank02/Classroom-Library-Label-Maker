@echo off
setlocal
cd /d "%~dp0"

REM Optional EXE icon once assets\icons\app.ico contains real icon data.
set "ICON_ARGS="
if exist "assets\icons\app.ico" (
    for %%A in ("assets\icons\app.ico") do (
        if %%~zA GTR 0 set "ICON_ARGS=--icon assets\icons\app.ico"
    )
)

echo Building Classroom Library Barcode Generator with PyInstaller...
python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --name barcode-generator ^
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
