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
from .cadmark import (
    apply_file_row,
    clear_file_tree,
    cube_photo,
    insert_file_row,
    make_file_tree,
    row_is_ready,
)
from .i18n import (
    KIOSK_DEFAULT,
    file_count,
    parse_language,
    t,
    update_button_label,
    usb_count,
)
from .idle import ScreensaverGate
from .modelprep import ModelPrep
from .parser import parse_nc_file
from .printer import print_ticket
from .report import PAPER_80MM, PAPER_80MM_MIN, format_report
from .update import UpdateCheck

BG = "#111111"
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
    language: str = ""
    source: Path | None = None


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


def ui_overlay_path() -> Path:
    """Writable per-user file for language (kiosk cannot write /etc)."""
    return Path.home() / ".config" / "fh6parse" / "ui.ini"


def save_kiosk_values(
    updates: dict[str, str],
    dest: Path | None = None,
    *,
    source: Path | None = None,
) -> Path:
    """Merge keys into [kiosk] without dropping the rest of the ini."""
    path = dest or source or kiosk_config_write_path()
    parser = configparser.ConfigParser()
    read_from = None
    if source is not None and source.is_file():
        read_from = source
    elif path.is_file():
        read_from = path
    if read_from is not None:
        parser.read(read_from, encoding="utf-8")
    if not parser.has_section("kiosk"):
        parser.add_section("kiosk")
    for key, value in updates.items():
        parser.set("kiosk", key, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        parser.write(fh)
    return path


def save_model_roots(roots: list[Path], dest: Path | None = None) -> Path:
    return save_kiosk_values(
        {"model_roots": ",".join(str(p) for p in roots)}, dest
    )


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
    cfg.source = chosen
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
    lang_raw = src.get("language", fallback="").strip()
    cfg.language = parse_language(lang_raw, default=KIOSK_DEFAULT) if lang_raw else ""
    overlay = ui_overlay_path()
    if overlay.is_file():
        extra = configparser.ConfigParser()
        extra.read(overlay, encoding="utf-8")
        if extra.has_section("kiosk"):
            over = extra["kiosk"].get("language", "").strip()
            if over:
                cfg.language = parse_language(over, default=KIOSK_DEFAULT)
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
        self._models = ModelPrep(cfg.model_roots)
        self._update_available = False
        self._updating = False
        self._pending_update: UpdateCheck | None = None
        self._lang = parse_language(cfg.language, default=KIOSK_DEFAULT)
        self._config_open = False

        self.title(t(self._lang, "app_title_kiosk", version=__version__))
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
        self._font_title = title_font
        self._font_small = small
        self._font_update = update_font

        head = tk.Frame(self, bg=BG)
        head.pack(fill=tk.X, padx=16, pady=(18, 8))
        title_row = tk.Frame(head, bg=BG)
        title_row.pack(fill=tk.X)
        self.brand_lbl = tk.Label(
            title_row, text=t(self._lang, "brand"), font=title_font, bg=BG, fg=ACCENT
        )
        self.brand_lbl.pack(side=tk.LEFT)
        self.lang_chip = tk.Label(
            title_row,
            text=t(self._lang, "lang_chip"),
            font=small,
            bg="#2a2a2a",
            fg=ACCENT,
            padx=8,
            pady=2,
            cursor="hand2",
        )
        self.lang_chip.pack(side=tk.RIGHT, pady=(6, 0), padx=(8, 0))
        self.lang_chip.bind("<Button-1>", self._on_config_pointer)
        self.version_lbl = tk.Label(
            title_row,
            text=f"v{__version__}",
            font=small,
            bg=BG,
            fg=MUTED,
        )
        self.version_lbl.pack(side=tk.RIGHT, pady=(6, 0))
        self.hint = tk.Label(
            head,
            text=t(self._lang, "insert_usb"),
            font=small,
            bg=BG,
            fg=MUTED,
            wraplength=self.cfg.width - 40,
            justify="left",
        )
        self.hint.pack(anchor="w", pady=(4, 0))
        self._cad_ready, self._cad_empty = cube_photo(self, size=32, dark=True)
        self._cad_legend, _unused_empty = cube_photo(self, size=26, dark=True)
        legend = tk.Frame(head, bg=BG)
        legend.pack(anchor="w", pady=(6, 0))
        tk.Label(legend, image=self._cad_legend, bg=BG).pack(side=tk.LEFT)
        self.cad_legend_lbl = tk.Label(
            legend,
            text=f"  {t(self._lang, 'cad_legend')}",
            font=small,
            bg=BG,
            fg=MUTED,
        )
        self.cad_legend_lbl.pack(side=tk.LEFT)

        mid = tk.Frame(self, bg=BG)
        mid.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self.listbox = make_file_tree(mid, dark=True, font=list_font, rowheight=40)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind("<Button-1>", self._on_list_click)
        self.listbox.bind("<MouseWheel>", self._on_wheel)
        self.listbox.bind("<Button-4>", lambda e: self._on_wheel_button(-1))
        self.listbox.bind("<Button-5>", lambda e: self._on_wheel_button(1))

        foot = tk.Frame(self, bg=BG)
        foot.pack(fill=tk.X, padx=16, pady=(4, 16))
        self.update_btn = tk.Button(
            foot,
            text=t(self._lang, "update"),
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
            text=t(self._lang, "keys_hint"),
            font=small,
            bg=BG,
            fg=MUTED,
            wraplength=self.cfg.width - 40,
            justify="left",
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

        self._build_config_panel(small, update_font)

        self.saver = tk.Frame(self, bg="#000000", takefocus=True, cursor="arrow")
        self.saver.bind("<Button-1>", self._on_saver_pointer)
        self.saver.bind("<Button-2>", self._on_saver_pointer)
        self.saver.bind("<Button-3>", self._on_saver_pointer)
        self.saver.bind("<MouseWheel>", self._on_wheel)
        self.saver.bind("<Button-4>", lambda e: self._on_wheel_button(-1))
        self.saver.bind("<Button-5>", lambda e: self._on_wheel_button(1))

    def _build_config_panel(self, small, update_font) -> None:
        panel = tk.Frame(
            self,
            bg="#1a1a1a",
            highlightbackground=ACCENT,
            highlightthickness=2,
            padx=18,
            pady=16,
        )
        self._config = panel
        self._config_title = tk.Label(
            panel,
            text=t(self._lang, "settings"),
            font=update_font,
            bg="#1a1a1a",
            fg=ACCENT,
        )
        self._config_title.pack(anchor="w")
        self._config_blurb = tk.Label(
            panel,
            text=t(self._lang, "settings_blurb"),
            font=small,
            bg="#1a1a1a",
            fg=MUTED,
            wraplength=self.cfg.width - 80,
            justify="left",
        )
        self._config_blurb.pack(anchor="w", pady=(8, 12))
        self._config_lang_lbl = tk.Label(
            panel,
            text=t(self._lang, "language"),
            font=small,
            bg="#1a1a1a",
            fg="#eeeeee",
        )
        self._config_lang_lbl.pack(anchor="w", pady=(0, 8))
        row = tk.Frame(panel, bg="#1a1a1a")
        row.pack(fill=tk.X, pady=(0, 12))
        self._btn_pl = tk.Button(
            row,
            text=t(self._lang, "lang_pl"),
            font=update_font,
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: self._set_language("pl"),
        )
        self._btn_pl.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6), ipady=10)
        self._btn_en = tk.Button(
            row,
            text=t(self._lang, "lang_en"),
            font=update_font,
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: self._set_language("en"),
        )
        self._btn_en.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(6, 0), ipady=10)
        self._config_saved = tk.Label(
            panel,
            text="",
            font=small,
            bg="#1a1a1a",
            fg=OK,
            wraplength=self.cfg.width - 80,
            justify="left",
        )
        self._config_saved.pack(anchor="w")
        self._config_keys = tk.Label(
            panel,
            text=t(self._lang, "settings_keys"),
            font=small,
            bg="#1a1a1a",
            fg=MUTED,
            wraplength=self.cfg.width - 80,
            justify="left",
        )
        self._config_keys.pack(anchor="w", pady=(10, 0))
        self._style_lang_buttons()

    def _tr(self, key: str, **kwargs) -> str:
        return t(self._lang, key, **kwargs)

    def _style_lang_buttons(self) -> None:
        for code, btn in (("pl", self._btn_pl), ("en", self._btn_en)):
            if code == self._lang:
                btn.config(bg=ACCENT, fg="#111111", activebackground="#ffd54a")
            else:
                btn.config(bg="#333333", fg="#eeeeee", activebackground="#444444")

    def _apply_language(self) -> None:
        self.title(self._tr("app_title_kiosk", version=__version__))
        self.brand_lbl.config(text=self._tr("brand"))
        self.lang_chip.config(text=self._tr("lang_chip"))
        self.cad_legend_lbl.config(text=f"  {self._tr('cad_legend')}")
        self._keys_hint.config(text=self._tr("keys_hint"))
        self._config_title.config(text=self._tr("settings"))
        self._config_blurb.config(text=self._tr("settings_blurb"))
        self._config_lang_lbl.config(text=self._tr("language"))
        self._btn_pl.config(text=self._tr("lang_pl"))
        self._btn_en.config(text=self._tr("lang_en"))
        self._config_keys.config(text=self._tr("settings_keys"))
        self._style_lang_buttons()
        self._refresh_hint()
        if self._update_available and self._pending_update is not None and not self._updating:
            self.update_btn.config(text=update_button_label(self._lang, self._pending_update))
        elif not self._updating:
            self.update_btn.config(text=self._tr("update"))

    def _refresh_hint(self) -> None:
        if not self._files:
            self.hint.config(text=self._tr("insert_usb"))
            return
        n = len(self._files)
        usb_n = len(self._mounts)
        extra = (
            f"  {self._tr('local_extra', n=len(self.cfg.extra_roots))}"
            if self.cfg.extra_roots
            else ""
        )
        self.hint.config(
            text=f"{file_count(self._lang, n)}   {usb_count(usb_n)}{extra}"
        )

    def _set_language(self, lang: str) -> None:
        self._lang = parse_language(lang, default=KIOSK_DEFAULT)
        self.cfg.language = self._lang
        self._apply_language()
        self._persist_language()

    def _persist_language(self) -> None:
        overlay = ui_overlay_path()
        try:
            saved = save_kiosk_values({"language": self._lang}, dest=overlay)
        except OSError as exc:
            self._config_saved.config(
                text=self._tr("settings_save_fail", detail=exc), fg=ERR
            )
            return
        if self.cfg.source is not None:
            try:
                save_kiosk_values(
                    {"language": self._lang},
                    dest=self.cfg.source,
                    source=self.cfg.source,
                )
            except OSError:
                pass
        self._config_saved.config(
            text=self._tr("settings_saved", path=str(saved)), fg=OK
        )

    def _show_config(self) -> None:
        self._config_open = True
        self._config.place(relx=0.05, rely=0.18, relwidth=0.90, relheight=0.52)
        self._config.lift()
        self._style_lang_buttons()
        self._arm_idle()

    def _hide_config(self) -> None:
        if not self._config_open:
            return
        self._config_open = False
        self._config.place_forget()
        self._claim_input()

    def _toggle_config(self) -> None:
        if self._config_open:
            self._hide_config()
        else:
            self._show_config()

    def _on_config_pointer(self, _event: tk.Event | None = None) -> str:
        if self._wake_hid():
            return "break"
        self._toggle_config()
        self._arm_idle()
        return "break"

    def _on_config_key(self) -> str:
        if self._wake_hid():
            return "break"
        self._toggle_config()
        self._arm_idle()
        return "break"

    def _dismiss_config(self) -> bool:
        """Close settings without changing the file list. True if it was open."""
        if not self._config_open:
            return False
        self._hide_config()
        return True

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
            ("<F2>", lambda e: self._on_config_key()),
            ("<Key-c>", lambda e: self._on_config_key()),
            ("<Key-C>", lambda e: self._on_config_key()),
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
        if self._wake_hid():
            return "break"
        if self._config_open:
            self._set_language("en" if self._lang == "pl" else "pl")
            self._arm_idle()
            return "break"
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
        if self._wake_hid():
            return "break"
        if self._config_open:
            self._set_language("en" if self._lang == "pl" else "pl")
            self._arm_idle()
            return "break"
        self._on_encoder(delta)
        return "break"

    def _on_wheel_button(self, delta: int) -> str:
        if self._wake_hid():
            return "break"
        if self._config_open:
            self._set_language("en" if self._lang == "pl" else "pl")
            self._arm_idle()
            return "break"
        self._on_encoder(delta)
        return "break"

    def _on_escape(self, _event: tk.Event | None = None) -> str:
        if self._wake_hid():
            return "break"
        if self._dismiss_config():
            self._arm_idle()
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
            self._set_status(self._tr("gpio_off", detail=_gpio_fail_hint(exc)), error=True)

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
        return label

    def _cad_ready_for(self, path: Path) -> bool:
        return self._models is not None and self._models.is_ready(path)

    def _set_files(self, files: list[Path], *, keep_highlight: bool) -> None:
        current = self._selected()
        self._files = files
        if self._models is not None:
            self._models.set_files(files)
        clear_file_tree(self.listbox)
        names = [p.name for p in files]
        for path in files:
            insert_file_row(
                self.listbox,
                self._label_for(path, names),
                ready=self._cad_ready_for(path),
                ready_img=self._cad_ready,
                empty_img=self._cad_empty,
            )
        self._refresh_hint()
        if not files:
            self._index = 0
            return
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
        children = self.listbox.get_children()
        if len(children) != len(self._files):
            return
        for i, path in enumerate(self._files):
            iid = children[i]
            label = self._label_for(path, names)
            ready = self._cad_ready_for(path)
            try:
                current = self.listbox.item(iid, "text")
            except tk.TclError:
                return
            if current != label or row_is_ready(self.listbox, iid) != ready:
                apply_file_row(
                    self.listbox,
                    iid,
                    label,
                    ready=ready,
                    ready_img=self._cad_ready,
                    empty_img=self._cad_empty,
                )
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
        children = self.listbox.get_children()
        if not children:
            return
        iid = children[self._index]
        self.listbox.selection_set(iid)
        self.listbox.focus(iid)
        self.listbox.see(iid)

    def _on_encoder(self, delta: int) -> None:
        action = self.gate.encoder()
        if action == "wake":
            self._hide_saver()
            self._arm_idle()
            self._claim_input()
            return
        if self._dismiss_config():
            self._arm_idle()
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
        if self._dismiss_config():
            self._arm_idle()
            return "break"
        iid = self.listbox.identify_row(event.y)
        if iid:
            self._index = int(self.listbox.index(iid))
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
        self._pending_update = status
        label = update_button_label(self._lang, status)
        try:
            mapped = self.update_btn.winfo_ismapped()
        except tk.TclError:
            return
        self.update_btn.config(text=label)
        if not mapped:
            self.update_btn.pack(fill=tk.X, pady=(0, 10), before=self._keys_hint)
        if status.new_version and status.new_version != status.current_version:
            self._set_status(
                self._tr(
                    "update_status",
                    current=status.current_version,
                    new=status.new_version,
                )
            )
        else:
            self._set_status(self._tr("update_available"))

    def _on_update(self, _event: tk.Event | None = None) -> str | None:
        if self._wake_hid():
            return "break"
        if self._dismiss_config():
            self._arm_idle()
            return "break"
        if not self._update_available or self._updating:
            return "break"
        self._arm_idle()
        self._updating = True
        self.update_btn.config(state=tk.DISABLED, text=self._tr("updating"))
        self._set_status(self._tr("update_progress"))
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
                self._pending_update = None
                self.update_btn.pack_forget()
                self.update_btn.config(state=tk.NORMAL, text=self._tr("update"))
                self._updating = False
                self._set_status(self._tr("update_restarting"))
                return
            self._updating = False
            retry = (
                update_button_label(self._lang, self._pending_update)
                if self._pending_update is not None
                else self._tr("update")
            )
            self.update_btn.config(state=tk.NORMAL, text=retry)
            if code == 2:
                self._update_available = False
                self._pending_update = None
                self.update_btn.pack_forget()
                self._set_status(self._tr("update_frozen"), error=True)
                return
            self._set_status(
                self._tr("update_failed"),
                error=True,
            )
        except tk.TclError:
            pass

    def _on_print(self, paper: str) -> str | None:
        if self._updating:
            self._set_status(self._tr("busy_update"), error=True)
            return "break"
        if self._dismiss_config():
            self._arm_idle()
            return "break"
        if not self.gate.allow_print():
            return None
        self._arm_idle()
        path = self._selected()
        if path is None:
            self._set_status(self._tr("no_file"), error=True)
            return "break"
        kind = self._tr("print_kind_full" if paper == PAPER_80MM else "print_kind_min")
        self._set_status(self._tr("printing", kind=kind, name=path.name))
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
            self._set_status(self._tr("printed", name=path.name, route=route))
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
        if self._config_open:
            self._config_open = False
            self._config.place_forget()
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
