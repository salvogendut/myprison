"""Entry point for the optional Textual UI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="myprison-textual",
        description="Textual-based static blog manager for Hugo-compatible sites.",
    )
    parser.add_argument(
        "site_dir", nargs="?", default=".",
        help="Hugo site directory (default: current directory)",
    )
    parser.add_argument("--version", action="version", version="myprison %s" % __version__)
    args = parser.parse_args(argv)

    try:
        from .textual_app import MyprisonTextualApp
    except ImportError as exc:
        print(
            "The Textual UI requires the optional 'textual' dependency.\n"
            "Install it with:\n\n"
            "  python3 -m pip install --user -e '.[textual]'\n",
            file=sys.stderr,
        )
        print("Import error: %s" % exc, file=sys.stderr)
        return 2

    app = MyprisonTextualApp(Path(args.site_dir).expanduser())
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
