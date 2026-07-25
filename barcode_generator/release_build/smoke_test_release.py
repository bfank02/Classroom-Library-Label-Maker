"""Post-build smoke checks for the Windows GUI release folder.

Validates release layout, PE subsystem (no console), barcode font bundling,
sample generation, warning workflow, and clean EXE launch/shutdown.

Run after ``python release_build/build_windows_release.py``::

    python release_build/smoke_test_release.py
"""

from __future__ import annotations

import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from classroom_library_label_maker.config import load_application_settings
from classroom_library_label_maker.metadata import APP_GUI_EXE_NAME, APP_VERSION
from classroom_library_label_maker.models import GenerationCompletionState
from classroom_library_label_maker.services.workbook_generation_service import (
    WorkbookGenerationService,
)

FOLDER = (
    ROOT
    / "dist"
    / f"Classroom-Library-Label-Maker-{APP_VERSION}-windows"
)
ZIP = (
    REPO_ROOT
    / "releases"
    / f"Classroom-Library-Label-Maker-{APP_VERSION}-windows.zip"
)


def _pe_is_gui(exe: Path) -> bool:
    """Return True when the EXE subsystem is WINDOWS_GUI (2), not console (3)."""
    data = exe.read_bytes()
    if data[:2] != b"MZ":
        raise AssertionError(f"Not a PE file: {exe}")
    (pe_offset,) = struct.unpack_from("<I", data, 0x3C)
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise AssertionError(f"Missing PE header: {exe}")
    optional = pe_offset + 24
    (magic,) = struct.unpack_from("<H", data, optional)
    if magic not in (0x10B, 0x20B):
        raise AssertionError(f"Unexpected optional magic {magic:#x}")
    (subsystem,) = struct.unpack_from("<H", data, optional + 68)
    return subsystem == 2  # IMAGE_SUBSYSTEM_WINDOWS_GUI


def check_layout() -> Path:
    assert FOLDER.is_dir(), f"Missing release folder: {FOLDER}"
    exe = FOLDER / f"{APP_GUI_EXE_NAME}.exe"
    required = [
        exe,
        FOLDER / "Sample Books.xlsx",
        FOLDER / "Quick Start.md",
        FOLDER / "README.md",
        FOLDER / "LICENSE",
        FOLDER / "VERSION.txt",
    ]
    for path in required:
        assert path.is_file(), f"Missing {path}"
        assert path.stat().st_size > 0, f"Empty {path}"
    assert ZIP.is_file(), f"Missing ZIP: {ZIP}"
    assert _pe_is_gui(exe), "EXE is not a windowed GUI binary"
    print(f"OK layout + GUI subsystem: {exe.name}")
    return exe


def check_barcode_font_bundled(exe: Path) -> None:
    """Fail the release if python-barcode's TTF is missing from the EXE archive."""
    from PyInstaller.archive.readers import CArchiveReader

    reader = CArchiveReader(str(exe))
    key = "barcode\\fonts\\DejaVuSansMono.ttf"
    assert key in reader.toc, (
        f"{key} not embedded in {exe.name} — barcode ImageWriter will fail"
    )
    data = reader.extract(key)
    assert data and len(data) > 1000
    print(f"OK barcode font embedded in EXE ({len(data)} bytes)")


def check_barcode_pngs_written(tmp: Path) -> None:
    from classroom_library_label_maker.rendering.barcode_renderer import (
        PythonBarcodeRenderer,
        _resolve_barcode_font_path,
    )

    font = _resolve_barcode_font_path()
    assert font is not None, "python-barcode font missing from environment"
    out = tmp / "font-check.png"
    PythonBarcodeRenderer().render_to_file("9780064400558", out)
    assert out.is_file() and out.stat().st_size > 0
    print(f"OK barcode font + PNG write ({out.stat().st_size} bytes)")


def check_sample_generation(tmp: Path) -> None:
    sample = FOLDER / "Sample Books.xlsx"
    barcodes = tmp / "barcodes"
    barcodes.mkdir()
    output = tmp / "labels.xlsx"
    settings = load_application_settings(
        workbook_path=sample,
        barcode_output_directory=barcodes,
    )
    result = WorkbookGenerationService(settings).generate(output_path=output)
    assert result.warning_count == 0
    assert result.completion_state is GenerationCompletionState.SUCCESS
    assert output.is_file()
    pngs = list(barcodes.glob("*.png"))
    assert len(pngs) >= 15
    print(f"OK sample generation: {result.labels_created} labels, {len(pngs)} PNGs")


def check_warning_path(tmp: Path) -> None:
    from openpyxl import Workbook

    inventory = tmp / "bad.xlsx"
    wb = Workbook()
    sheet = wb.active
    assert sheet is not None
    sheet.title = "Books"
    sheet.append(["ISBN", "Title", "Author", "Copies"])
    sheet.append(["123", "Broken ISBN", "Author", 1])
    sheet.append(["9780064400558", "Charlotte's Web", "E. B. White", 1])
    wb.save(inventory)

    barcodes = tmp / "warn-barcodes"
    barcodes.mkdir()
    output = tmp / "warn-labels.xlsx"
    settings = load_application_settings(
        workbook_path=inventory,
        barcode_output_directory=barcodes,
    )
    result = WorkbookGenerationService(settings).generate(output_path=output)
    assert result.requires_review
    assert result.warning_count >= 1
    assert output.is_file()
    print(f"OK warning workflow: {result.warning_count} warnings")


def check_launch_and_shutdown(exe: Path) -> None:
    proc = subprocess.Popen(
        [str(exe)],
        cwd=str(FOLDER),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    still_running = proc.poll() is None
    if still_running:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    assert still_running, "EXE exited immediately (launch failure?)"
    print("OK clean launch + shutdown")


def main() -> int:
    print(f"Smoke testing release {APP_VERSION}...")
    exe = check_layout()
    check_barcode_font_bundled(exe)
    tmp = ROOT / "temp" / "release-smoke"
    if tmp.exists():
        import shutil

        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    check_barcode_pngs_written(tmp)
    check_sample_generation(tmp)
    check_warning_path(tmp)
    check_launch_and_shutdown(exe)
    print("All smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
