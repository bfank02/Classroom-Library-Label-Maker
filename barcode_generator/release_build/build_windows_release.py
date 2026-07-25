"""Assemble the Windows GUI release ZIP for GitHub Releases.

Builds a windowed one-file EXE with PyInstaller, then packs:

* Classroom Library Label Maker.exe
* README.md
* LICENSE
* Quick Start.md
* Sample Books.xlsx

Run from ``barcode_generator/``::

    python release_build/build_windows_release.py
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from classroom_library_label_maker.metadata import (  # noqa: E402
    APP_GUI_EXE_NAME,
    APP_NAME,
    APP_VERSION,
)

_VERSION_MOD = ROOT / "release_build" / "write_version_info.py"
_spec = importlib.util.spec_from_file_location("write_version_info", _VERSION_MOD)
assert _spec and _spec.loader
_write_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_write_mod)
write_version_info = _write_mod.write_version_info

DIST = ROOT / "dist"
RELEASES = REPO_ROOT / "releases"
ASSETS = ROOT / "assets"
ICON = ASSETS / "icons" / "app.ico"
SPEC = ROOT / "release_build" / "label-maker-gui.spec"
VERSION_INFO = ROOT / "release_build" / "version_info.txt"

FOLDER_NAME = f"Classroom-Library-Label-Maker-{APP_VERSION}-windows"
ZIP_NAME = f"{FOLDER_NAME}.zip"


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def build_exe() -> Path:
    if not ICON.is_file() or ICON.stat().st_size == 0:
        raise SystemExit(f"Missing branding icon: {ICON}")

    write_version_info(VERSION_INFO)

    _run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(SPEC),
        ]
    )
    exe = DIST / f"{APP_GUI_EXE_NAME}.exe"
    if not exe.is_file():
        raise SystemExit(f"Expected EXE not found: {exe}")
    return exe


def assemble_release(exe: Path) -> Path:
    stage = DIST / FOLDER_NAME
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    shutil.copy2(exe, stage / f"{APP_GUI_EXE_NAME}.exe")

    sample = ASSETS / "sample-data" / "Sample Books.xlsx"
    if not sample.is_file() or sample.stat().st_size == 0:
        raise SystemExit(f"Missing sample workbook: {sample}")
    shutil.copy2(sample, stage / "Sample Books.xlsx")

    quick_start = REPO_ROOT / "docs" / "Quick Start.md"
    shutil.copy2(quick_start, stage / "Quick Start.md")

    readme = REPO_ROOT / "README.md"
    shutil.copy2(readme, stage / "README.md")

    license_file = REPO_ROOT / "LICENSE"
    if license_file.is_file():
        shutil.copy2(license_file, stage / "LICENSE")

    (stage / "VERSION.txt").write_text(
        f"{APP_NAME}\nVersion {APP_VERSION}\n",
        encoding="utf-8",
    )
    return stage


def write_zip(stage: Path) -> Path:
    RELEASES.mkdir(parents=True, exist_ok=True)
    zip_path = RELEASES / ZIP_NAME
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                archive.write(
                    path,
                    arcname=str(Path(FOLDER_NAME) / path.relative_to(stage)),
                )
    return zip_path


def main() -> int:
    print(f"Building {APP_NAME} {APP_VERSION} Windows release...")
    exe = build_exe()
    stage = assemble_release(exe)
    zip_path = write_zip(stage)
    print(f"Release folder: {stage}")
    print(f"Release ZIP:    {zip_path}")
    print(f"ZIP size:       {zip_path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
