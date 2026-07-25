# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the windowed Classroom Library Label Maker GUI."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).resolve().parent  # barcode_generator/
SRC = ROOT / "src"
ASSETS = ROOT / "assets"
ICON = ASSETS / "icons" / "app.ico"
VERSION_INFO = Path(SPECPATH).resolve() / "version_info.txt"
ENTRY = SRC / "classroom_library_label_maker" / "gui" / "__main__.py"

# Product EXE name (spaces allowed on Windows).
EXE_NAME = "Classroom Library Label Maker"

# python-barcode ships DejaVuSansMono.ttf under barcode/fonts — required by
# ImageWriter or every barcode fails with "cannot open resource".
barcode_datas = collect_data_files("barcode")

a = Analysis(
    [str(ENTRY)],
    pathex=[str(SRC)],
    binaries=[],
    datas=[(str(ASSETS), "assets"), *barcode_datas],
    hiddenimports=[
        "classroom_library_label_maker",
        "classroom_library_label_maker.gui",
        "classroom_library_label_maker.services",
        "classroom_library_label_maker.utils",
        "classroom_library_label_maker.label_templates",
        "classroom_library_label_maker.workbooks",
        "barcode.ean",
        "barcode.writer",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DRender",
        "PySide6.QtBluetooth",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtDesigner",
        "PySide6.QtGraphs",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtPositioning",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=EXE_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.is_file() else None,
    version=str(VERSION_INFO) if VERSION_INFO.is_file() else None,
)
