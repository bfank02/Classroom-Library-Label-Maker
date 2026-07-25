"""Command-line interface package.

Public surface for parsing arguments and dispatching commands.
"""

from __future__ import annotations

from classroom_library_label_maker.cli.commands import dispatch
from classroom_library_label_maker.cli.parser import build_parser, parse_args

__all__ = [
    "build_parser",
    "dispatch",
    "parse_args",
]
