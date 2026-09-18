"""Command-line interface for CNC tool reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._version import __version__
from .parser import parse_nc_file
from .report import PAPER_80MM, PAPER_80MM_MIN, PAPER_A4, format_report, write_report


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _prog_name() -> str:
    if _frozen():
        return Path(sys.executable).name
    return "fh6parse"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=_prog_name(),
        description=(
            "Extract CNC tool list and lowest work Z per operation. "
            "Writes A4 and 80 mm (thermal) text + HTML print sheets."
        ),
    )
    p.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="One or more .nc / G-code files",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Folder for reports (default: same folder as each .nc file)",
    )
    p.add_argument(
        "--gui",
        action="store_true",
        help="Open the graphical operator tool",
    )
    p.add_argument(
        "--kiosk",
        action="store_true",
        help="Raspberry Pi kiosk: USB list, encoder, 80 mm print, screensaver",
    )
    p.add_argument(
        "--update",
        action="store_true",
        help=(
            "Update this install (same as the UPDATE button): git pull on a "
            "checkout, or replace the Windows exe from GitHub Releases"
        ),
    )
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Kiosk ini file (default: fh6parse-kiosk.ini or /etc/fh6parse-kiosk.ini)",
    )
    p.add_argument(
        "--stdout",
        action="store_true",
        help="Print a text report to stdout instead of writing files",
    )
    p.add_argument(
        "--format",
        choices=(PAPER_A4, PAPER_80MM, PAPER_80MM_MIN, "both"),
        default="both",
        dest="paper_format",
        help="A4, 80mm thermal, 80mm-min, or both (default both when writing files)",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return p


def run_cli(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # Double-click / bare binary opens the operator GUI.
    if not argv and _frozen():
        from .gui import run_gui

        run_gui()
        return 0

    args = build_parser().parse_args(argv)
    if args.update:
        from .update import perform_frozen_exe_update, perform_update

        if _frozen() and sys.platform.startswith("win"):
            return perform_frozen_exe_update()
        return perform_update(restart_kiosk=sys.platform.startswith("linux"))
    if args.kiosk:
        from .kiosk import run_kiosk

        run_kiosk(args.config)
        return 0
    if args.gui:
        from .gui import run_gui

        run_gui()
        return 0

    if not args.files:
        build_parser().print_help()
        return 2

    errors = 0
    for path in args.files:
        if not path.is_file():
            print(f"error: file not found: {path}", file=sys.stderr)
            errors += 1
            continue
        try:
            result = parse_nc_file(path)
            if args.stdout:
                paper = PAPER_A4 if args.paper_format == "both" else args.paper_format
                print(format_report(result, paper=paper))
            else:
                for dest in write_report(
                    result, out_dir=args.output_dir, papers=args.paper_format
                ):
                    print(f"wrote {dest}")
        except Exception as exc:  # noqa: BLE001 — shop-floor CLI must keep going
            print(f"error: failed to parse {path}: {exc}", file=sys.stderr)
            errors += 1

    return 1 if errors else 0


def main() -> None:
    sys.exit(run_cli())
