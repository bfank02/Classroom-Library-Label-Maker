#!/usr/bin/env bash
# Build a native macOS .app bundle for Classroom Library Label Maker.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

python scripts/generate_app_icons.py
python scripts/build_release.py "$@"

echo
echo "macOS app: dist/Classroom Library Label Maker.app"
echo "Launch from Finder, or:"
echo "  open \"dist/Classroom Library Label Maker.app\""
