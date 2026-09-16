"""Portrait USB kiosk for Raspberry Pi 5: encoder, two print buttons, screensaver."""

from __future__ import annotations

import configparser
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
import tkinter as tk
from tkinter import font as tkfont

from . import usbwatch
from ._version import __version__
from .idle import ScreensaverGate
from .modelprep import ModelPrep
from .parser import parse_nc_file
from .printer import print_ticket
from .report import PAPER_80MM, PAPER_80MM_MIN, format_report
from .update import UpdateCheck

BG = "#111111"
FG = "#eeeeee"
ACCENT = "#e6b800"
MUTED = "#888888"
ERR = "#ff6b6b"
OK = "#8fd19e"


@dataclass
class KioskConfig:
    width: int = 600
    height: int = 800
    fullscreen: bool = True
    idle_seconds: float = 60.0
    encoder_clk: int = 17
    encoder_dt: int = 27
    encoder_swap: bool = False
    button_full: int = 22
    button_min: int = 23
    printer_queue: str = ""
    printer_device: str = "/dev/usb/lp0"
    usb_poll_ms: int = 500
    scan_depth: int = 1
    extensions: tuple[str, ...] = (".nc", ".tap")
    extra_roots: list[Path] = field(default_factory=list)
    model_roots: list[Path] = field(default_factory=list)


def _ini_paths(raw: str) -> list[Path]:
    chunks = raw.replace(",", os.pathsep).split(os.pathsep)
    return [Path(p.strip()) for p in chunks if p.strip()]


def default_config_paths() -> list[Path]:
    paths: list[Path] = []
    env = os.environ.get("FH6PARSE_KIOSK_INI")
    if env:
        paths.append(Path(env))
    paths.append(Path.cwd() / "fh6parse-kiosk.ini")
    if getattr(sys, "frozen", False):
        paths.append(Path(sys.executable).resolve().parent / "fh6parse-kiosk.ini")
    else:
        paths.append(Path(__file__).resolve().parent.parent / "fh6parse-kiosk.ini")
    paths.append(Path("/etc/fh6parse-kiosk.ini"))
    return paths


def kiosk_config_write_path() -> Path:
    """Ini the GUI writes when the operator picks STEP folders."""
    env = os.environ.get("FH6PARSE_KIOSK_INI")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "fh6parse-kiosk.ini"
    return Path.cwd() / "fh6parse-kiosk.ini"


def save_model_roots(roots: list[Path], dest: Path | None = None) -> Path:
    path = dest or kiosk_config_write_path()
    parser = configparser.ConfigParser()
    if path.is_file():
        parser.read(path, encoding="utf-8")
    if not parser.has_section("kiosk"):
        parser.add_section("kiosk")
    parser.set("kiosk", "model_roots", ",".join(str(p) for p in roots))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        parser.write(fh)
    return path


def load_kiosk_config(explicit: Path | None = None) -> KioskConfig:
    cfg = KioskConfig()
    if explicit is not None:
        if not explicit.is_file():
            raise FileNotFoundError(f"kiosk config not found: {explicit}")
        chosen = explicit
    else:
        chosen = next((p for p in default_config_paths() if p.is_file()), None)
    if chosen is None:
        return cfg
    parser = configparser.ConfigParser()
    parser.read(chosen, encoding="utf-8")
    if not parser.has_section("kiosk"):
        return cfg
    src = parser["kiosk"]
    cfg.width = src.getint("width", fallback=cfg.width)
    cfg.height = src.getint("height", fallback=cfg.height)
    cfg.fullscreen = src.getboolean("fullscreen", fallback=cfg.fullscreen)
    cfg.idle_seconds = src.getfloat("idle_seconds", fallback=cfg.idle_seconds)
    cfg.encoder_clk = src.getint("encoder_clk", fallback=cfg.encoder_clk)
    cfg.encoder_dt = src.getint("encoder_dt", fallback=cfg.encoder_dt)
    cfg.encoder_swap = src.getboolean("encoder_swap", fallback=cfg.encoder_swap)
    cfg.button_full = src.getint("button_full", fallback=cfg.button_full)
    cfg.button_min = src.getint("button_min", fallback=cfg.button_min)
    cfg.printer_queue = src.get("printer_queue", fallback=cfg.printer_queue).strip()
    cfg.printer_device = src.get("printer_device", fallback=cfg.printer_device)
    cfg.usb_poll_ms = src.getint("usb_poll_ms", fallback=cfg.usb_poll_ms)
    cfg.scan_depth = src.getint("scan_depth", fallback=cfg.scan_depth)
    ext_raw = src.get("extensions", fallback=",".join(cfg.extensions))
    cfg.extensions = tuple(
        e.strip() if e.strip().startswith(".") else f".{e.strip()}"
        for e in ext_raw.split(",")
        if e.strip()
    )
    extra = src.get("extra_roots", fallback="")
    cfg.extra_roots = _ini_paths(extra)
    models = src.get("model_roots", fallback="")
    cfg.model_roots = _ini_paths(models)
    return cfg


def prefer_lgpio_factory() -> str:
    """Use lgpio when present (Pi 5 RP1). RPi.GPIO does not work on Pi 5.

    Honours GPIOZERO_PIN_FACTORY if already set. Returns the factory name, or
    an empty string when gpiozero should keep its default (Pi 3/4, or PC).
    """
    existing = os.environ.get("GPIOZERO_PIN_FACTORY", "").strip()
    if existing:
        return existing
    try:
        from gpiozero import Device
        from gpiozero.pins.lgpio import LGPIOFactory
    except ImportError:
        return ""
    try:
        Device.pin_factory = LGPIOFactory()
    except Exception:
        return ""
    return "lgpio"


def _gpio_fail_hint(exc: BaseException) -> str:
    text = str(exc)
    lowered = text.lower()
    if (
        "rpigpio" in lowered
        or "rpi.gpio" in lowered
        or "pin factory" in lowered
        or "lgpio" in lowered
    ):
        return f"{text}  (Pi 5 needs python3-lgpio; RPi.GPIO is not supported)"
    return text


def _dpms(force: str) -> None:
    """Blank or wake the panel via xset when running under X11."""
    try:
        subprocess.run(
            ["xset", "+dpms"],
            check=False,
            capture_output=True,
            timeout=2,
        )
        subprocess.run(
            ["xset", "dpms", "force", force],
            check=False,
            capture_output=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


class KioskApp(tk.Tk):
    def __init__(self, cfg: KioskConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.gate = ScreensaverGate(cfg.idle_seconds)
        self._files: list[Path] = []
        self._mounts: set[Path] = set()
        self._index = 0
        self._idle_job: str | None = None
        self._poll_job: str | None = None
        self._gpio: list[object] = []
        self._status_job: str | None = None
        self._bound_all: list[str] = []
        self._models = ModelPrep(cfg.model_roots) if cfg.model_roots else None
        self._update_available = False
        self._updating = False

        self.title(f"CNC kiosk {__version__}")
        self.configure(bg=BG)
        self.geometry(f"{cfg.width}x{cfg.height}")
        self.minsize(480, 640)
        if cfg.fullscreen:
            self.attributes("-fullscreen", True)
        self.bind("<Escape>", self._on_escape)
        self.bind("<Map>", lambda _e: self._claim_input())

        self._build()
        self._bind_keys()
        self._setup_gpio()
        self._poll_usb()
        self._arm_idle()
        self.after(200, self._claim_input)
        self.after(400, self._start_update_check)

    def _build(self) -> None:
        family = "DejaVu Sans" if sys.platform.startswith("linux") else "Segoe UI"
        title_font = tkfont.Font(family=family, size=22, weight="bold")
        list_font = tkfont.Font(family=family, size=20)
        small = tkfont.Font(family=family, size=13)
        update_font = tkfont.Font(family=family, size=18, weight="bold")

        head = tk.Frame(self, bg=BG)
        head.pack(fill=tk.X, padx=16, pady=(18, 8))
        tk.Label(
            head, text="CNC TOOLS", font=title_font, bg=BG, fg=ACCENT
        ).pack(anchor="w")
        self.hint = tk.Label(
            head,
            text="Insert USB",
            font=small,
            bg=BG,
            fg=MUTED,
            wraplength=self.cfg.width - 40,
            justify="left",
        )
        self.hint.pack(anchor="w", pady=(4, 0))

        mid = tk.Frame(self, bg=BG)
        mid.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self.listbox = tk.Listbox(
            mid,
            font=list_font,
            bg="#1a1a1a",
            fg=FG,
            selectbackground=ACCENT,
            selectforeground="#111111",
            activestyle="none",
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
            selectmode=tk.SINGLE,
            exportselection=False,
            takefocus=True,
        )
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind("<Button-1>", self._on_list_click)
        self.listbox.bind("<MouseWheel>", self._on_wheel)
        self.listbox.bind("<Button-4>", lambda e: self._on_wheel_button(-1))
        self.listbox.bind("<Button-5>", lambda e: self._on_wheel_button(1))

        foot = tk.Frame(self, bg=BG)
        foot.pack(fill=tk.X, padx=16, pady=(4, 16))
        self.update_btn = tk.Button(
            foot,
            text="UPDATE",
            font=update_font,
            bg=ACCENT,
            fg="#111111",
            activebackground="#ffd54a",
            activeforeground="#111111",
            disabledforeground="#555555",
            relief="flat",
            bd=0,
            highlightthickness=0,
            height=2,
            cursor="hand2",
            command=self._on_update,
        )
        self._keys_hint = tk.Label(
            foot,
            text="FULL / F  full ticket     MIN / M  short ticket     Esc  window",
            font=small,
            bg=BG,
            fg=MUTED,
        )
        self._keys_hint.pack(anchor="w")
        self.status = tk.Label(
            foot,
            text="",
            font=small,
            bg=BG,
            fg=OK,
            wraplength=self.cfg.width - 40,
            justify="left",
        )
        self.status.pack(anchor="w", pady=(6, 0))

        self.saver = tk.Frame(self, bg="#000000", takefocus=True, cursor="arrow")
        self.saver.bind("<Button-1>", self._on_saver_pointer)
        self.saver.bind("<Button-2>", self._on_saver_pointer)
        self.saver.bind("<Button-3>", self._on_saver_pointer)
        self.saver.bind("<MouseWheel>", self._on_wheel)
        self.saver.bind("<Button-4>", lambda e: self._on_wheel_button(-1))
        self.saver.bind("<Button-5>", lambda e: self._on_wheel_button(1))

    def _bind_keys(self) -> None:
        # bind_all: a plugged-in keyboard works even if the listbox has focus.
        handlers = (
            ("<Up>", lambda e: self._on_nav(-1)),
            ("<Down>", lambda e: self._on_nav(1)),
            ("<Left>", lambda e: self._on_nav(-1)),
            ("<Right>", lambda e: self._on_nav(1)),
            ("<Prior>", lambda e: self._on_nav(-1)),
            ("<Next>", lambda e: self._on_nav(1)),
            ("<Key-f>", lambda e: self._on_print(PAPER_80MM)),
            ("<Key-F>", lambda e: self._on_print(PAPER_80MM)),
            ("<Key-m>", lambda e: self._on_print(PAPER_80MM_MIN)),
            ("<Key-M>", lambda e: self._on_print(PAPER_80MM_MIN)),
            ("<Key-u>", lambda e: self._on_update()),
            ("<Key-U>", lambda e: self._on_update()),
            ("<Escape>", self._on_escape),
            ("<KeyPress>", self._on_keypress),
        )
        self._bound_all = [seq for seq, _ in handlers]
        for seq, fn in handlers:
            self.bind_all(seq, fn)
            for widget in (self, self.listbox, self.saver):
                widget.bind(seq, fn)

    def _claim_input(self) -> None:
        try:
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass

    def _wake_hid(self) -> bool:
        """True if a keyboard/mouse event was used only to turn the screen on."""
        if self.gate.hid() != "wake":
            return False
        self._hide_saver()
        self._arm_idle()
        self._claim_input()
        return True

    def _on_keypress(self, event: tk.Event) -> str | None:
        if self._wake_hid():
            return "break"
        if event.keysym not in {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"}:
            self._arm_idle()
        return None

    def _on_nav(self, delta: int) -> str:
        self._on_encoder(delta)
        return "break"

    def _on_saver_pointer(self, _event: tk.Event) -> str:
        self._wake_hid()
        return "break"

    def _on_wheel(self, event: tk.Event) -> str:
        if event.delta:
            delta = -1 if event.delta > 0 else 1
        else:
            delta = 1
        self._on_encoder(delta)
        return "break"

    def _on_wheel_button(self, delta: int) -> str:
        self._on_encoder(delta)
        return "break"

    def _on_escape(self, _event: tk.Event | None = None) -> str:
        if self._wake_hid():
            return "break"
        if self.cfg.fullscreen:
            self.attributes("-fullscreen", False)
            self.cfg.fullscreen = False
            self._claim_input()
        else:
            self.destroy()
        return "break"

    def _queue(self, fn) -> None:
        try:
            self.after(0, fn)
        except tk.TclError:
            pass

    def _setup_gpio(self) -> None:
        try:
            from gpiozero import Button, RotaryEncoder
        except ImportError:
            return
        prefer_lgpio_factory()
        try:
            try:
                enc = RotaryEncoder(
                    self.cfg.encoder_clk,
                    self.cfg.encoder_dt,
                    bounce_time=0.005,
                )
            except TypeError:
                enc = RotaryEncoder(self.cfg.encoder_clk, self.cfg.encoder_dt)
            step = -1 if self.cfg.encoder_swap else 1
            enc.when_rotated_clockwise = lambda: self._queue(
                lambda: self._on_encoder(step)
            )
            enc.when_rotated_counter_clockwise = lambda: self._queue(
                lambda: self._on_encoder(-step)
            )
            full = Button(self.cfg.button_full, pull_up=True, bounce_time=0.08)
            mini = Button(self.cfg.button_min, pull_up=True, bounce_time=0.08)
            full.when_pressed = lambda: self._queue(
                lambda: self._on_print(PAPER_80MM)
            )
            mini.when_pressed = lambda: self._queue(
                lambda: self._on_print(PAPER_80MM_MIN)
            )
            self._gpio.extend([enc, full, mini])
        except Exception as exc:  # GPIO missing or pin busy
            self._set_status(f"GPIO off: {_gpio_fail_hint(exc)}", error=True)

    def _roots(self) -> list[Path]:
        return list(self._mounts) + list(self.cfg.extra_roots)

    def _poll_usb(self) -> None:
        mounts = set(usbwatch.removable_mounts())
        added = mounts - self._mounts
        self._mounts = mounts
        files = usbwatch.list_nc_files(
            self._roots(),
            max_depth=self.cfg.scan_depth,
            extensions=self.cfg.extensions,
        )
        if added:
            action = self.gate.usb_insert()
            if action == "wake":
                self._hide_saver()
            self._set_files(files, keep_highlight=True)
            self._arm_idle()
            self._claim_input()
        elif files != self._files:
            self._set_files(files, keep_highlight=True)
        else:
            self._sync_model_labels()
        self._poll_job = self.after(max(200, self.cfg.usb_poll_ms), self._poll_usb)

    def _label_for(self, path: Path, names: list[str]) -> str:
        label = path.name
        if names.count(path.name) > 1:
            label = f"{path.parent.name}/{path.name}"
        if self._models is not None and self._models.is_ready(path):
            return f"■ {label}"
        return label

    def _set_files(self, files: list[Path], *, keep_highlight: bool) -> None:
        current = self._selected()
        self._files = files
        if self._models is not None:
            self._models.set_files(files)
        self.listbox.delete(0, tk.END)
        names = [p.name for p in files]
        for path in files:
            self.listbox.insert(tk.END, self._label_for(path, names))
        if not files:
            self.hint.config(text="Insert USB")
            self._index = 0
            return
        n = len(files)
        usb_n = len(self._mounts)
        extra = f"  +{len(self.cfg.extra_roots)} local" if self.cfg.extra_roots else ""
        self.hint.config(
            text=f"{n} file{'s' if n != 1 else ''}   {usb_n} USB{extra}"
        )
        if keep_highlight and current in files:
            self._index = files.index(current)
        else:
            self._index = min(self._index, n - 1)
        self._paint_highlight()

    def _sync_model_labels(self) -> None:
        if self._models is None or not self._files:
            return
        names = [p.name for p in self._files]
        changed = False
        for i, path in enumerate(self._files):
            label = self._label_for(path, names)
            try:
                current = self.listbox.get(i)
            except tk.TclError:
                return
            if current != label:
                self.listbox.delete(i)
                self.listbox.insert(i, label)
                changed = True
        if changed:
            self._paint_highlight()

    def _selected(self) -> Path | None:
        if not self._files:
            return None
        if not (0 <= self._index < len(self._files)):
            return None
        return self._files[self._index]

    def _paint_highlight(self) -> None:
        if not self._files:
            return
        self._index %= len(self._files)
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(self._index)
        self.listbox.activate(self._index)
        self.listbox.see(self._index)

    def _on_encoder(self, delta: int) -> None:
        action = self.gate.encoder()
        if action == "wake":
            self._hide_saver()
            self._arm_idle()
            self._claim_input()
            return
        if not self._files:
            self._arm_idle()
            return
        self._index = (self._index + delta) % len(self._files)
        self._paint_highlight()
        self._arm_idle()

    def _on_list_click(self, event: tk.Event) -> str | None:
        if self._wake_hid() or self.gate.asleep:
            return "break"
        idx = self.listbox.nearest(event.y)
        if 0 <= idx < len(self._files):
            self._index = idx
            self._paint_highlight()
            self._arm_idle()
        self.listbox.focus_set()
        return "break"

    def _start_update_check(self) -> None:
        threading.Thread(target=self._check_update_worker, daemon=True).start()

    def _check_update_worker(self) -> None:
        from .update import check_for_update

        status = check_for_update()
        self._queue(lambda: self._apply_update_status(status))

    def _apply_update_status(self, status: UpdateCheck) -> None:
        if not status.available or self._updating:
            return
        self._update_available = True
        try:
            mapped = self.update_btn.winfo_ismapped()
        except tk.TclError:
            return
        if not mapped:
            self.update_btn.pack(fill=tk.X, pady=(0, 10), before=self._keys_hint)
        self._set_status("Update available")

    def _on_update(self, _event: tk.Event | None = None) -> str | None:
        if self._wake_hid():
            return "break"
        if not self._update_available or self._updating:
            return "break"
        self._arm_idle()
        self._updating = True
        self.update_btn.config(state=tk.DISABLED, text="UPDATING…")
        self._set_status("Updating…")
        threading.Thread(target=self._update_worker, daemon=True).start()
        return "break"

    def _update_worker(self) -> None:
        from .update import perform_update

        code = perform_update()
        self._queue(lambda: self._update_done(code))

    def _update_done(self, code: int) -> None:
        try:
            if code == 0:
                self._update_available = False
                self.update_btn.pack_forget()
                self.update_btn.config(state=tk.NORMAL, text="UPDATE")
                self._updating = False
                self._set_status("Updated — restarting kiosk")
                return
            self._updating = False
            self.update_btn.config(state=tk.NORMAL, text="UPDATE")
            if code == 2:
                self._update_available = False
                self.update_btn.pack_forget()
                self._set_status("This install cannot auto-update", error=True)
                return
            self._set_status("Update failed — try again or use --update", error=True)
        except tk.TclError:
            pass

    def _on_print(self, paper: str) -> str | None:
        if self._updating:
            self._set_status("Updating…", error=True)
            return "break"
        if not self.gate.allow_print():
            return None
        self._arm_idle()
        path = self._selected()
        if path is None:
            self._set_status("No file", error=True)
            return "break"
        kind = "full" if paper == PAPER_80MM else "min"
        self._set_status(f"Printing {kind}: {path.name}…")
        self.update_idletasks()
        try:
            result = parse_nc_file(path)
            text = format_report(result, paper=paper)
            images: list[Path] = []
            if self._models is not None:
                images = self._models.ready_images(path)
            route = print_ticket(
                text,
                queue=self.cfg.printer_queue,
                device=self.cfg.printer_device,
                image_paths=images,
            )
            self._set_status(f"Printed {path.name}  ({route})")
        except Exception as exc:  # shop-floor: stay up
            self._set_status(str(exc), error=True)
        return "break"

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self.status.config(text=text, fg=ERR if error else OK)
        if self._status_job:
            self.after_cancel(self._status_job)
            self._status_job = None
        if self._updating:
            return
        self._status_job = self.after(8000, lambda: self.status.config(text=""))

    def _arm_idle(self) -> None:
        if self._idle_job:
            self.after_cancel(self._idle_job)
            self._idle_job = None
        if not self.gate.enabled or self.gate.asleep:
            return
        delay = max(1, int(self.cfg.idle_seconds * 1000))
        self._idle_job = self.after(delay, self._idle_timeout)

    def _idle_timeout(self) -> None:
        self._idle_job = None
        if self.gate.sleep():
            self._show_saver()

    def _show_saver(self) -> None:
        self.saver.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.saver.lift()
        try:
            self.saver.focus_set()
            self.saver.focus_force()
        except tk.TclError:
            pass
        _dpms("off")

    def _hide_saver(self) -> None:
        _dpms("on")
        self.saver.place_forget()
        self._claim_input()

    def destroy(self) -> None:
        for seq in self._bound_all:
            try:
                self.unbind_all(seq)
            except tk.TclError:
                pass
        if self._idle_job:
            try:
                self.after_cancel(self._idle_job)
            except tk.TclError:
                pass
        if self._poll_job:
            try:
                self.after_cancel(self._poll_job)
            except tk.TclError:
                pass
        for obj in self._gpio:
            close = getattr(obj, "close", None)
            if close:
                try:
                    close()
                except Exception:
                    pass
        if self._models is not None:
            try:
                self._models.close()
            except Exception:
                pass
        super().destroy()


def run_kiosk(config_path: Path | None = None) -> None:
    cfg = load_kiosk_config(config_path)
    app = KioskApp(cfg)
    app.mainloop()
