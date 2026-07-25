#!/usr/bin/env python3
"""Cross-platform PyInstaller packaging for the desktop GUI.

Produces a native Windows EXE or macOS ``.app`` from the shared codebase.
Does not require platform-specific application source trees.

Usage (from ``barcode_generator/``)::

    python scripts/build_release.py
    python scripts/build_release.py --clean-only
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
ASSETS = ROOT / "assets"
RESOURCES = ASSETS / "resources"
REPO_DOCS = ROOT.parent / "docs"
QUICK_START_SOURCE = REPO_DOCS / "Quick Start.md"
QUICK_START_STAGED = RESOURCES / "Quick Start.md"
VERSION_FILE = ROOT / "VERSION"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def _ensure_import_path() -> None:
    sys.path.insert(0, str(SRC))


def _load_metadata() -> tuple[str, str, str, str]:
    _ensure_import_path()
    from classroom_library_label_maker.metadata import (
        APP_BUNDLE_IDENTIFIER,
        APP_COPYRIGHT,
        APP_EXECUTABLE_NAME,
        APP_VERSION,
    )

    return APP_EXECUTABLE_NAME, APP_BUNDLE_IDENTIFIER, APP_COPYRIGHT, APP_VERSION


def _pyinstaller_separator() -> str:
    # PyInstaller --add-data uses ";" on Windows and ":" elsewhere.
    return ";" if sys.platform == "win32" else ":"


def _stage_quick_start() -> None:
    """Copy the repo Quick Start into assets for a single bundled location."""
    if not QUICK_START_SOURCE.is_file():
        raise FileNotFoundError(f"Missing Quick Start guide: {QUICK_START_SOURCE}")
    RESOURCES.mkdir(parents=True, exist_ok=True)
    shutil.copy2(QUICK_START_SOURCE, QUICK_START_STAGED)


def _icon_args() -> list[str]:
    if sys.platform == "darwin":
        icns = ASSETS / "icons" / "app.icns"
        if icns.is_file() and icns.stat().st_size > 0:
            return ["--icon", str(icns)]
    ico = ASSETS / "icons" / "app.ico"
    if ico.is_file() and ico.stat().st_size > 0:
        return ["--icon", str(ico)]
    return []


def _data_args() -> list[str]:
    sep = _pyinstaller_separator()
    return [
        "--add-data",
        f"{ASSETS}{sep}assets",
        "--add-data",
        f"{VERSION_FILE}{sep}.",
    ]


def _write_info_plist_metadata(
    app_path: Path,
    name: str,
    bundle_id: str,
    copyright_text: str,
    version: str,
) -> None:
    """Ensure Finder-facing Info.plist keys match product metadata."""
    import plistlib

    plist_path = app_path / "Contents" / "Info.plist"
    if not plist_path.is_file():
        return

    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)

    plist["CFBundleName"] = name
    plist["CFBundleDisplayName"] = name
    plist["CFBundleIdentifier"] = bundle_id
    plist["CFBundleShortVersionString"] = version
    plist["CFBundleVersion"] = version
    plist["NSHumanReadableCopyright"] = copyright_text
    plist["CFBundleGetInfoString"] = f"{name} {version}"

    with plist_path.open("wb") as handle:
        plistlib.dump(plist, handle)


def build(*, clean: bool = True) -> int:
    try:
        import PyInstaller.__main__ as pyinstaller_main
    except ImportError as exc:  # pragma: no cover - packaging environment
        raise SystemExit(
            "PyInstaller is required. Install with: pip install -e '.[build]'"
        ) from exc

    name, bundle_id, copyright_text, version = _load_metadata()
    _stage_quick_start()

    if clean:
        for path in (DIST, BUILD):
            if path.exists():
                shutil.rmtree(path)

    entry = SRC / "classroom_library_label_maker" / "gui" / "__main__.py"
    args: list[str] = [
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        name,
        "--paths",
        str(SRC),
        "--hidden-import",
        "classroom_library_label_maker",
        "--hidden-import",
        "classroom_library_label_maker.gui",
        "--hidden-import",
        "classroom_library_label_maker.services",
        "--hidden-import",
        "classroom_library_label_maker.utils",
        *_data_args(),
        *_icon_args(),
    ]

    if sys.platform == "darwin":
        # Native .app bundle (onedir). Onefile is not used because macOS
        # Finder launches expect a proper bundle layout with Resources.
        args.extend(["--osx-bundle-identifier", bundle_id])
    else:
        # Preserve the existing Windows one-file distribution shape.
        args.append("--onefile")

    args.append(str(entry))

    print(f"Building {name} v{version} ({sys.platform})…")
    print(f"Copyright: {copyright_text}")
    pyinstaller_main.run(args)

    if sys.platform == "darwin":
        app_path = DIST / f"{name}.app"
        if not app_path.is_dir():
            raise SystemExit(f"Expected macOS app bundle missing: {app_path}")
        _write_info_plist_metadata(app_path, name, bundle_id, copyright_text, version)
        print(f"Build complete: {app_path}")
    else:
        exe = DIST / f"{name}.exe"
        print(f"Build complete: {exe if exe.exists() else DIST}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clean-only",
        action="store_true",
        help="Only remove dist/ and build/, then exit.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not delete prior dist/build before packaging.",
    )
    ns = parser.parse_args(argv)

    if ns.clean_only:
        for path in (DIST, BUILD):
            if path.exists():
                shutil.rmtree(path)
                print(f"Removed {path}")
        return 0

    return build(clean=not ns.no_clean)


if __name__ == "__main__":
    raise SystemExit(main())
