#!/usr/bin/env python3
"""Install a Google Books API key for the packaged desktop app.

Finder / Dock launches do not inherit shell ``export`` variables. This writes
the key to the per-user application support file that
``load_google_books_auth_config()`` reads at startup.

Usage (from ``barcode_generator``)::

    # From the current shell environment:
    export GOOGLE_BOOKS_API_KEY="your-key"
    python scripts/install_google_books_api_key.py

    # Or pass the key explicitly (avoid leaving it in shell history if possible):
    python scripts/install_google_books_api_key.py --key "your-key"

Never commit the key file. Restrict file permissions to the current user.
"""

from __future__ import annotations

import argparse
import contextlib
import os
from pathlib import Path
import stat
import sys

# Allow running without installing the package.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from classroom_library_label_maker.config import (  # noqa: E402
    google_books_api_key_file_path,
    load_google_books_auth_config,
    log_google_books_authentication_status,
)
from classroom_library_label_maker.constants import (  # noqa: E402
    GOOGLE_BOOKS_API_KEY_ENV,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install Google Books API key for Classroom Library Label Maker"
    )
    parser.add_argument(
        "--key",
        help=f"API key value (default: read {GOOGLE_BOOKS_API_KEY_ENV})",
    )
    parser.add_argument(
        "--path",
        type=Path,
        help="Override key file path (default: per-user application support)",
    )
    args = parser.parse_args(argv)

    raw = args.key if args.key is not None else os.environ.get(GOOGLE_BOOKS_API_KEY_ENV)
    if raw is None or not str(raw).strip():
        print(
            f"error: provide --key or set {GOOGLE_BOOKS_API_KEY_ENV}",
            file=sys.stderr,
        )
        return 1

    key = str(raw).strip().splitlines()[0].strip()
    path = args.path if args.path is not None else google_books_api_key_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{key}\n", encoding="utf-8")
    with contextlib.suppress(OSError):
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)

    auth = load_google_books_auth_config(environ={}, key_file=path)
    log_google_books_authentication_status(auth.status)
    print(f"Wrote API key file: {path}")
    print("Restart Classroom Library Label Maker, then confirm the log shows:")
    print("  Google Books authentication: Enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
