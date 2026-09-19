"""Keep company STEP / documentation folders read-only.

fh6parse may list and open files under model_roots. It must not create,
overwrite, or delete anything there. Rendered bitmaps go to the temp cache.
"""

from __future__ import annotations

from pathlib import Path

from .modelmatch import is_under


class ProtectedWriteError(PermissionError):
    """Attempt to write or delete inside a company documentation folder."""


def is_protected(path: Path, roots: list[Path] | None) -> bool:
    """True if path is the root or anything inside it."""
    if not roots:
        return False
    try:
        target = Path(path).resolve()
    except OSError:
        return False
    for root in roots:
        try:
            base = Path(root).resolve()
        except OSError:
            continue
        if target == base or is_under(target, base):
            return True
    return False


def refuse_write(path: Path, roots: list[Path] | None, *, action: str = "write") -> None:
    """Raise if dest would land in a company folder."""
    if is_protected(path, roots):
        raise ProtectedWriteError(
            f"refusing to {action} inside company folder: {path}"
        )
