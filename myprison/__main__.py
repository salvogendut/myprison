"""Entry point: python3 -m myprison [SITE_DIR]"""

from __future__ import annotations

import argparse
import curses
import locale
import sys
from pathlib import Path

from . import __version__
from .app import curses_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="myprison",
        description="Curses-based static blog manager producing Hugo-compatible sites.",
    )
    parser.add_argument(
        "site_dir", nargs="?", default=".",
        help="Hugo site directory (default: current directory)",
    )
    parser.add_argument("--version", action="version", version="myprison %s" % __version__)
    args = parser.parse_args(argv)

    locale.setlocale(locale.LC_ALL, "")
    start_dir = Path(args.site_dir).expanduser()
    try:
        curses.wrapper(curses_main, start_dir)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
