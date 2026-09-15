"""Background STEP match + render for the USB file list. Never blocks print."""

from __future__ import annotations

from pathlib import Path
import threading
import time

from .modelmatch import ModelFile, index_models, pick_model
from .modelrender import cache_png_path, render_available, render_step_stack
from .partid import identity_from_nc_path

INDEX_EVERY = 90.0


class ModelPrep:
    """Walk configured model folders, match NC files, render when a CAD stack exists."""

    def __init__(self, roots: list[Path]) -> None:
        self.roots = [Path(p) for p in roots]
        self._lock = threading.Lock()
        self._nc: list[Path] = []
        self._index: list[ModelFile] = []
        self._ready: dict[str, Path] = {}
        self._tried: set[str] = set()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        if self.roots:
            self._thread = threading.Thread(
                target=self._run, name="fh6parse-models", daemon=True
            )
            self._thread.start()

    def set_files(self, files: list[Path]) -> None:
        with self._lock:
            self._nc = list(files)
            live = {str(p.resolve()) for p in files}
            self._ready = {k: v for k, v in self._ready.items() if k in live}
            self._tried &= live
        self._wake.set()

    def is_ready(self, path: Path) -> bool:
        png = self.ready_png(path)
        return png is not None and png.is_file()

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

    def _run(self) -> None:
        last_index = 0.0
        while not self._stop.is_set():
            now = time.monotonic()
            if now - last_index >= INDEX_EVERY or not self._index:
                try:
                    models = index_models(self.roots)
                except Exception:
                    models = []
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
        if not nc.is_file():
            return
        try:
            ident = identity_from_nc_path(nc)
        except OSError:
            return
        if not ident.base:
            self._mark_tried(key)
            return
        chosen = pick_model(ident, models)
        if chosen is None or not render_available():
            self._mark_tried(key)
            return
        try:
            st = chosen.path.stat()
        except OSError:
            self._mark_tried(key)
            return
        dest = cache_png_path(chosen.path, st.st_mtime, st.st_size)
        if not dest.is_file():
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
