"""Find a STEP model whose name matches an NC part id and revision."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from .partid import PartIdentity, parse_model_stem
from .usbwatch import SKIP_DIR_NAMES

STEP_EXTENSIONS = {".stp", ".step"}
MIN_PREFIX = 6


@dataclass(frozen=True)
class ModelFile:
    path: Path
    identity: PartIdentity
    mtime: float = 0.0


def iter_step_files(roots: list[Path]) -> list[Path]:
    """All .stp / .step files under each root, including subfolders."""
    found: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            current = Path(dirpath)
            dirnames[:] = [
                d
                for d in dirnames
                if not d.startswith(".") and d.lower() not in SKIP_DIR_NAMES
            ]
            for name in filenames:
                suffix = Path(name).suffix.lower()
                if suffix not in STEP_EXTENSIONS:
                    continue
                path = current / name
                try:
                    resolved = path.resolve()
                except OSError:
                    continue
                if resolved in seen:
                    continue
                seen.add(resolved)
                found.append(path)
    return found


def index_models(roots: list[Path]) -> list[ModelFile]:
    out: list[ModelFile] = []
    for path in iter_step_files(roots):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        ident = parse_model_stem(path.stem)
        if not ident.base:
            continue
        out.append(ModelFile(path=path, identity=ident, mtime=mtime))
    return out


def _prefix_ok(nc_base: str, stp_base: str) -> tuple[int, int] | None:
    """STP must start with the NC id (or vice versa if the STP id is shorter)."""
    a, b = nc_base.upper(), stp_base.upper()
    if not a or not b:
        return None
    if b.startswith(a):
        return (len(a), len(b) - len(a))
    if a.startswith(b) and len(b) >= MIN_PREFIX:
        return (len(b), len(a) - len(b))
    return None


def match_score(nc: PartIdentity, model: ModelFile) -> tuple | None:
    """Higher is better. None = not a candidate."""
    prefix = _prefix_ok(nc.base, model.identity.base)
    if prefix is None:
        return None
    prefix_len, extra_base = prefix
    if prefix_len < min(MIN_PREFIX, len(nc.base)):
        return None
    extra = max(len(model.path.stem) - prefix_len, extra_base)
    if nc.rev is not None:
        if model.identity.rev is None or not nc.rev.matches(model.identity.rev):
            return None
        return (1, prefix_len, -extra)
    rev_key = (
        model.identity.rev.sort_key() if model.identity.rev is not None else (-1, -1)
    )
    return (0, rev_key, prefix_len, -extra)


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def pick_model(nc: PartIdentity, models: list[ModelFile]) -> ModelFile | None:
    """Closest prefix match. Same G-code rev if present, else latest STP rev."""
    scored: list[tuple[tuple, ModelFile]] = []
    for model in models:
        score = match_score(nc, model)
        if score is None:
            continue
        scored.append((score, model))
    if not scored:
        return None
    scored.sort(key=lambda item: (item[0], item[1].mtime), reverse=True)
    return scored[0][1]


def pick_model_near(
    nc: PartIdentity,
    nc_path: Path,
    models: list[ModelFile],
) -> ModelFile | None:
    """Prefer a match on the same volume/folder as the NC (USB stick), else any."""
    try:
        local_root = nc_path.resolve().parent
    except OSError:
        return pick_model(nc, models)
    local = [m for m in models if is_under(m.path, local_root)]
    return pick_model(nc, local) or pick_model(nc, models)
