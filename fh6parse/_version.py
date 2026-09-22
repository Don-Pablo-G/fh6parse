"""Single source of truth for the package version and visible build id."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

__version__ = "1.4.1"

try:
    from ._build import __build__
except ImportError:
    __build__ = ""


def _git_root(start: Path) -> Path | None:
    path = start.resolve()
    if path.is_file():
        path = path.parent
    for candidate in [path, *path.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def local_build() -> str:
    """Short git SHA, frozen bake, or empty if unknown."""
    frozen = bool(getattr(sys, "frozen", False))
    if frozen and __build__:
        return str(__build__)
    root = _git_root(Path(__file__))
    if root is not None:
        try:
            proc = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--short=7", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            proc = None
        if proc is not None and proc.returncode == 0:
            sha = (proc.stdout or "").strip()
            if sha:
                return sha
    return str(__build__ or "")


def display_version() -> str:
    """Label shown in kiosk, office GUI, and ``--version``."""
    return package_stamp()


def package_stamp() -> str:
    """Version plus short SHA for dist filenames, e.g. ``1.4.1+0e7f077``."""
    build = local_build()
    if build:
        return f"{__version__}+{build}"
    return __version__


def dist_basename(kind: str, *, stamped: bool = True) -> str:
    """``fh6parse-1.4.1+0e7f077-windows-x64`` (or without the SHA if unstamped)."""
    ver = package_stamp() if stamped else __version__
    return f"fh6parse-{ver}-{kind}"
