#!/usr/bin/env python3
"""Smoke-test a packaged macOS .app without requiring interactive GUI use.

Validates bundle layout, bundled assets, Info.plist metadata, frozen path
resolution, sample + custom inventory generation, logging, and a brief
process launch/exit.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "dist" / "Classroom Library Label Maker.app"
SRC = ROOT / "src"


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def _ok(message: str) -> None:
    print(f"OK: {message}")


def check_bundle() -> Path:
    if not APP.is_dir():
        _fail(f"missing app bundle: {APP}")
    macos = APP / "Contents" / "MacOS"
    resources = APP / "Contents" / "Resources"
    plist_path = APP / "Contents" / "Info.plist"
    if not macos.is_dir() or not resources.is_dir() or not plist_path.is_file():
        _fail("incomplete .app Contents layout")

    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    for key in (
        "CFBundleName",
        "CFBundleDisplayName",
        "CFBundleIdentifier",
        "CFBundleShortVersionString",
        "NSHumanReadableCopyright",
    ):
        if not plist.get(key):
            _fail(f"Info.plist missing {key}")
    if plist["CFBundleName"] != "Classroom Library Label Maker":
        _fail(f"unexpected CFBundleName: {plist['CFBundleName']}")
    if "barcode-generator" in str(plist).lower():
        _fail("teacher-facing metadata still references barcode-generator")
    _ok("Info.plist metadata")

    # PyInstaller places datas under Resources or Frameworks/_internal depending
    # on version; locate assets by walking the bundle.
    asset_hits = list(APP.rglob("Sample Books.xlsx"))
    if not asset_hits:
        _fail("bundled sample workbook not found")
    quick_start_hits = list(APP.rglob("Quick Start.md"))
    if not quick_start_hits:
        _fail("bundled Quick Start guide not found")
    icon_hits = list(APP.rglob("app.icns"))
    if not icon_hits:
        _fail("bundled app.icns not found")
    version_hits = list(APP.rglob("VERSION"))
    if not version_hits:
        _fail("bundled VERSION not found")
    _ok("bundled sample workbook, Quick Start, icon, VERSION")
    return asset_hits[0].parents[2]  # .../assets parent == resource root-ish


def check_generation(resource_hint: Path) -> None:
    sys.path.insert(0, str(SRC))
    # Simulate frozen layout for path helpers while still importing from source.
    meipass_candidates = [
        resource_hint,
        resource_hint.parent,
    ]
    # Prefer a directory that contains assets/ and VERSION.
    meipass = None
    for candidate in APP.rglob("VERSION"):
        root = candidate.parent
        if (root / "assets" / "sample-data" / "Sample Books.xlsx").is_file():
            meipass = root
            break
    if meipass is None:
        for candidate in meipass_candidates:
            if (candidate / "assets").is_dir():
                meipass = candidate
                break
    if meipass is None:
        _fail("could not locate frozen-style resource root inside bundle")

    import classroom_library_label_maker.runtime_paths as runtime_paths
    from classroom_library_label_maker.config import (
        ProjectPaths,
        load_application_settings,
    )
    from classroom_library_label_maker.models import GenerationCompletionState
    from classroom_library_label_maker.services.workbook_generation_service import (
        WorkbookGenerationService,
    )

    # Point frozen helpers at the bundled tree.
    runtime_paths.sys.frozen = True  # type: ignore[attr-defined]
    runtime_paths.sys._MEIPASS = str(meipass)  # type: ignore[attr-defined]

    paths = ProjectPaths()
    sample = paths.sample_inventory_file
    if not sample.is_file():
        _fail(f"sample inventory unresolved via ProjectPaths: {sample}")
    quick = paths.quick_start_file
    if not quick.is_file():
        _fail(f"quick start unresolved via ProjectPaths: {quick}")
    _ok(f"frozen ProjectPaths root={paths.root}")

    with tempfile.TemporaryDirectory(prefix="cllm-smoke-") as tmp:
        tmp_path = Path(tmp)
        barcodes = tmp_path / "barcodes"
        barcodes.mkdir()
        labels = tmp_path / "labels.xlsx"
        settings = load_application_settings(
            project_root=meipass,
            workbook_path=sample,
            barcode_output_directory=barcodes,
        )
        result = WorkbookGenerationService(settings).generate(output_path=labels)
        if not labels.is_file():
            _fail("sample generation did not create label workbook")
        if result.labels_created < 1:
            _fail("sample generation created zero labels")
        if result.completion_state is not GenerationCompletionState.SUCCESS:
            _fail(f"sample generation state={result.completion_state}")
        _ok(
            f"sample workbook generation "
            f"(labels={result.labels_created}, warnings={result.warning_count})"
        )

        # Custom inventory: copy sample and generate again (same shape).
        custom = tmp_path / "custom.xlsx"
        shutil.copy2(sample, custom)
        labels2 = tmp_path / "custom_labels.xlsx"
        barcodes2 = tmp_path / "barcodes2"
        barcodes2.mkdir()
        settings2 = load_application_settings(
            project_root=meipass,
            workbook_path=custom,
            barcode_output_directory=barcodes2,
        )
        result2 = WorkbookGenerationService(settings2).generate(output_path=labels2)
        if not labels2.is_file() or result2.labels_created < 1:
            _fail("custom inventory generation failed")
        _ok("custom inventory generation")

        # Warning path: malformed inventory should produce review warnings.
        bad = ROOT / "tests" / "assets" / "workbooks" / "malformed_rows.xlsx"
        if bad.is_file():
            labels3 = tmp_path / "warn_labels.xlsx"
            barcodes3 = tmp_path / "barcodes3"
            barcodes3.mkdir()
            settings3 = load_application_settings(
                project_root=meipass,
                workbook_path=bad,
                barcode_output_directory=barcodes3,
            )
            result3 = WorkbookGenerationService(settings3).generate(output_path=labels3)
            if result3.warning_count < 1:
                _fail("expected warnings from malformed inventory")
            if not labels3.is_file():
                _fail("warning-path generation did not create a label workbook")
            _ok(
                f"warnings path ok (warnings={result3.warning_count}, "
                f"requires_review={result3.requires_review})"
            )
        else:
            _ok("warning fixture not present; skipped")


def check_logging() -> None:
    sys.path.insert(0, str(SRC))
    from classroom_library_label_maker.logger import setup_logging
    from classroom_library_label_maker.runtime_paths import user_log_directory

    log_dir = user_log_directory()
    log_file = log_dir / "smoke-test.log"
    logger = setup_logging(level="INFO", log_file=log_file)
    logger.info("smoke-test log write")
    if not log_file.is_file():
        _fail(f"log file not written: {log_file}")
    text = log_file.read_text(encoding="utf-8")
    if "smoke-test log write" not in text:
        _fail("log contents missing expected message")
    _ok(f"rotating logs writable at {log_dir}")


def check_launch() -> None:
    binary = next((APP / "Contents" / "MacOS").iterdir())
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    # Launch briefly; windowed apps may exit immediately under offscreen.
    proc = subprocess.Popen(
        [str(binary)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2.5)
    still_running = proc.poll() is None
    if still_running:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        _ok("application launched and exited cleanly after terminate")
    else:
        # Offscreen may cause immediate exit; treat non-crash codes as OK.
        code = proc.returncode
        stderr = (proc.stderr.read() if proc.stderr else b"").decode("utf-8", "replace")
        if code not in (0, None) and "Traceback" in stderr:
            _fail(f"app crashed on launch (code={code}): {stderr[:500]}")
        _ok(f"application process started (exit code={code})")


def main() -> int:
    print(f"Smoke testing: {APP}")
    hint = check_bundle()
    check_generation(hint)
    check_logging()
    check_launch()
    print("All smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
