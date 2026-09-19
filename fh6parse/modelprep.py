"""Background STEP match + render for the USB file list. Never blocks print."""

from __future__ import annotations

from pathlib import Path
import threading
import time

from .modelmatch import ModelFile, index_models, is_under, pick_model_near
from .modelrender import cache_png_path, ensure_cache_path, render_available, render_step_stack
from .partid import identity_from_nc_path

INDEX_EVERY = 90.0

CAD_READY = "ready"
CAD_SEARCHING = "searching"
CAD_RENDERING = "rendering"
CAD_NO_STEP = "no_step"
CAD_MISSING = "cad_missing"
CAD_SHARE_DOWN = "share_down"
CAD_IDLE = "idle"


def company_share_up(roots: list[Path] | None) -> bool | None:
    """None if no company folder is configured. False if none of them exist."""
    if not roots:
        return None
    for root in roots:
        try:
            if Path(root).is_dir():
                return True
        except OSError:
            continue
    return False


def cad_status(
    path: Path | None,
    *,
    prep: ModelPrep | None,
    model_roots: list[Path] | None = None,
    cad_ok: bool | None = None,
) -> str:
    """Why the 3D cube is missing (or ready). cad_ok defaults to render_available()."""
    if cad_ok is None:
        cad_ok = render_available()
    if path is not None and prep is not None and prep.is_ready(path):
        return CAD_READY
    if not cad_ok:
        return CAD_MISSING
    share = company_share_up(model_roots)
    if path is None:
        if share is False:
            return CAD_SHARE_DOWN
        return CAD_IDLE
    if prep is None:
        return CAD_MISSING
    state = prep.file_cad_state(path)
    if state == CAD_READY:
        return CAD_READY
    if state == CAD_RENDERING:
        return CAD_RENDERING
    if state == CAD_SEARCHING:
        return CAD_SEARCHING
    if share is False:
        return CAD_SHARE_DOWN
    return CAD_NO_STEP


class ModelPrep:
    """Walk NC folders + configured model roots, match, render in the background."""

    def __init__(self, roots: list[Path] | None = None) -> None:
        self.roots = [Path(p) for p in (roots or [])]
        self._lock = threading.Lock()
        self._nc: list[Path] = []
        self._local_roots: list[Path] = []
        self._index: list[ModelFile] = []
        self._index_dirty = True
        self._ready: dict[str, Path] = {}
        self._tried: set[str] = set()
        self._usb_reads = 0
        self._work_key: str | None = None
        self._work_phase: str = CAD_SEARCHING
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="fh6parse-models", daemon=True
        )
        self._thread.start()

    def set_files(self, files: list[Path]) -> None:
        parents = _unique_parents(files)
        with self._lock:
            self._nc = list(files)
            live = {str(p.resolve()) for p in files}
            self._ready = {k: v for k, v in self._ready.items() if k in live}
            if parents != self._local_roots:
                self._local_roots = parents
                self._index_dirty = True
                self._tried = set(self._ready)
            else:
                self._tried &= live
        self._wake.set()

    def is_ready(self, path: Path) -> bool:
        png = self.ready_png(path)
        return png is not None and png.is_file()

    def file_cad_state(self, path: Path) -> str:
        """ready, searching (index/match), rendering (drawing a hit), or no_step."""
        if self.is_ready(path):
            return CAD_READY
        try:
            key = str(path.resolve())
        except OSError:
            return CAD_SEARCHING
        with self._lock:
            if key in self._tried:
                return CAD_NO_STEP
            if self._work_key == key and self._work_phase == CAD_RENDERING:
                return CAD_RENDERING
            return CAD_SEARCHING

    def ready_png(self, path: Path) -> Path | None:
        try:
            key = str(path.resolve())
        except OSError:
            return None
        with self._lock:
            png = self._ready.get(key)
        if png is None or not png.is_file():
            return None
        return png

    def ready_images(self, path: Path) -> list[Path]:
        png = self.ready_png(path)
        if png is None:
            return []
        return [png]

    def close(self) -> None:
        self._stop.set()
        self._wake.set()

    def usb_busy(self) -> bool:
        """True while listing or copying STEP/NC on a USB stick (not the NAS)."""
        with self._lock:
            return self._usb_reads > 0

    def invalidate(self, path: Path) -> None:
        """Drop a cached bitmap so an overwritten .nc can rematch."""
        try:
            key = str(path.resolve())
        except OSError:
            return
        with self._lock:
            self._ready.pop(key, None)
            self._tried.discard(key)
            if self._work_key == key:
                self._work_key = None
        self._wake.set()

    def _set_work(self, key: str | None, phase: str = CAD_SEARCHING) -> None:
        with self._lock:
            self._work_key = key
            self._work_phase = phase

    def _begin_usb(self) -> None:
        with self._lock:
            self._usb_reads += 1

    def _end_usb(self) -> None:
        with self._lock:
            self._usb_reads = max(0, self._usb_reads - 1)

    def _path_is_local(self, path: Path) -> bool:
        try:
            target = path.resolve()
        except OSError:
            return False
        with self._lock:
            roots = list(self._local_roots)
        return any(is_under(target, root) for root in roots)

    def _run(self) -> None:
        last_index = 0.0
        while not self._stop.is_set():
            now = time.monotonic()
            if now - last_index >= INDEX_EVERY or self._index_dirty:
                with self._lock:
                    company = list(self.roots)
                    local = list(self._local_roots)
                    self._index_dirty = False
                models: list[ModelFile] = []
                try:
                    models.extend(index_models(company))
                except Exception:
                    pass
                if local:
                    self._begin_usb()
                    try:
                        models.extend(index_models(local))
                    except Exception:
                        pass
                    finally:
                        self._end_usb()
                with self._lock:
                    self._index = models
                    self._tried = set(self._ready)
                last_index = now
            with self._lock:
                pending = list(self._nc)
                models = list(self._index)
            for nc in pending:
                if self._stop.is_set():
                    return
                self._prep_one(nc, models)
            self._wake.wait(timeout=1.0)
            self._wake.clear()

    def _prep_one(self, nc: Path, models: list[ModelFile]) -> None:
        try:
            key = str(nc.resolve())
        except OSError:
            return
        with self._lock:
            if key in self._ready and self._ready[key].is_file():
                return
            if key in self._tried:
                return
        local = self._path_is_local(nc)
        if local:
            self._begin_usb()
        self._set_work(key, CAD_SEARCHING)
        try:
            self._prep_one_body(nc, models, key)
        finally:
            self._set_work(None)
            if local:
                self._end_usb()

    def _prep_one_body(self, nc: Path, models: list[ModelFile], key: str) -> None:
        if not nc.is_file():
            return
        try:
            ident = identity_from_nc_path(nc)
        except OSError:
            return
        if not ident.base:
            self._mark_tried(key)
            return
        chosen = pick_model_near(ident, nc, models)
        if chosen is None:
            self._mark_tried(key)
            return
        if not render_available():
            return
        try:
            st = chosen.path.stat()
        except OSError:
            self._mark_tried(key)
            return
        dest = ensure_cache_path(cache_png_path(chosen.path, st.st_mtime, st.st_size))
        if not dest.is_file():
            self._set_work(key, CAD_RENDERING)
            if render_step_stack(chosen.path, dest) is None:
                self._mark_tried(key)
                return
        if not dest.is_file():
            self._mark_tried(key)
            return
        with self._lock:
            self._ready[key] = dest
            self._tried.add(key)

    def _mark_tried(self, key: str) -> None:
        with self._lock:
            self._tried.add(key)


def _unique_parents(files: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for path in files:
        try:
            parent = path.resolve().parent
        except OSError:
            continue
        if parent in seen or not parent.is_dir():
            continue
        seen.add(parent)
        out.append(parent)
    return out
