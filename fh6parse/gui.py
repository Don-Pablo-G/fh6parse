"""Tkinter GUI: pick CNC files, preview and print A4 / 80 mm reports."""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ._version import __version__, display_version
from .cadmark import (
    apply_file_row,
    clear_file_tree,
    cube_photo,
    insert_file_row,
    make_file_tree,
    row_is_ready,
    step_photo,
)
from .i18n import GUI_DEFAULT, cad_status_label, file_count, parse_language, t, update_button_label
from .kiosk import (
    MILL_FORM_ATC,
    MILL_FORM_OFFSET,
    MILL_FORM_SCALARS,
    MILL_FORM_TRAVEL,
    FileStamp,
    file_stamp,
    load_kiosk_config,
    machine_display_name,
    mill_from_form_entries,
    parse_gui_paper,
    persist_machine_profile,
    preview_cache_stale,
    save_kiosk_values,
    save_model_roots,
    ui_overlay_path,
)
from .modelprep import ModelPrep, cad_status
from .modelrender import render_available
from .parser import ParseResult, parse_nc_file
from .report import (
    GUI_SECTION_KEYS,
    PAPER_80MM,
    PAPER_A4,
    SECTIONS_LOAD,
    SECTIONS_RUN,
    SECTIONS_SET,
    format_report,
    open_print_html,
    parse_report_sections,
    ReportSections,
    ticket_image_paths,
    write_report,
)
from .safepath import ProtectedWriteError, is_protected
from .update import UpdateCheck


def nc_keys_to_reload(
    stamps: dict[str, FileStamp | None],
    disk: dict[str, FileStamp | None],
) -> list[str]:
    """Open NC keys whose mtime/size no longer match the last parse."""
    return [
        key
        for key, cached in stamps.items()
        if preview_cache_stale(cached, disk.get(key))
    ]


class ToolReportApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"CNC Tool Report {display_version()}")
        self.geometry("1000x700")
        self.minsize(760, 500)

        self._results: dict[str, tuple[Path, ParseResult]] = {}
        self._stamps: dict[str, FileStamp | None] = {}
        self._order: list[str] = []
        self._reload_gen = 0
        self._reload_inflight: set[str] = set()
        self._out_dir: Path | None = None
        cfg = load_kiosk_config()
        self._cfg_source = cfg.source
        self._lang = parse_language(cfg.language, default=GUI_DEFAULT)
        self._lang_var = tk.StringVar(value=self._lang)
        self._machines = list(cfg.machines)
        self._machine_id = cfg.machine_id
        self._machine_var = tk.StringVar()
        self._model_roots = list(cfg.model_roots)
        self._last_nc_dir = cfg.last_nc_dir
        self._paper = tk.StringVar(value=parse_gui_paper(cfg.last_paper))
        self._section_seed = parse_report_sections(cfg.report_sections)
        if cfg.last_out_dir:
            out = Path(cfg.last_out_dir)
            if out.is_dir():
                self._out_dir = out
        self._models: ModelPrep | None = None
        self._model_job: str | None = None
        self._pending_update: UpdateCheck | None = None
        self._updating = False
        self._update_check_inflight = False
        self._iso_photo = None
        self._iso_path: Path | None = None

        self._build()
        self._apply_language()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._start_models()
        self.after(400, self._poll_models)
        self.after(400, self._start_update_check)
        self.bind("<FocusIn>", self._on_window_focus)

    def _tr(self, key: str, **kwargs) -> str:
        return t(self._lang, key, **kwargs)

    def _build(self) -> None:
        top = ttk.Frame(self, padding=8)
        top.pack(fill=tk.X)

        self.btn_open = ttk.Button(top, command=self.open_files)
        self.btn_open.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_save_fmt = ttk.Button(top, command=self.save_current)
        self.btn_save_fmt.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_save_all = ttk.Button(top, command=self.save_all)
        self.btn_save_all.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_out = ttk.Button(top, command=self.choose_out_dir)
        self.btn_out.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_step = ttk.Button(top, command=self.choose_model_roots)
        self.btn_step.pack(side=tk.LEFT, padx=(0, 6))
        self.out_label = ttk.Label(top, text="")
        self.out_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.rb_lang_pl = ttk.Radiobutton(
            top,
            value="pl",
            variable=self._lang_var,
            command=self._on_language,
        )
        self.rb_lang_en = ttk.Radiobutton(
            top,
            value="en",
            variable=self._lang_var,
            command=self._on_language,
        )
        self.rb_lang_en.pack(side=tk.RIGHT)
        self.rb_lang_pl.pack(side=tk.RIGHT, padx=(0, 8))
        self.version_lbl = ttk.Label(top, text=f"v{display_version()}")
        self.version_lbl.pack(side=tk.RIGHT, padx=(0, 12))

        paper_row = ttk.Frame(self, padding=(8, 0, 8, 8))
        paper_row.pack(fill=tk.X)
        self.lbl_preview = ttk.Label(paper_row)
        self.lbl_preview.pack(side=tk.LEFT, padx=(0, 8))
        self.rb_a4 = ttk.Radiobutton(
            paper_row,
            text="A4",
            value=PAPER_A4,
            variable=self._paper,
            command=self._on_paper,
        )
        self.rb_a4.pack(side=tk.LEFT, padx=(0, 8))
        self.rb_80 = ttk.Radiobutton(
            paper_row,
            value=PAPER_80MM,
            variable=self._paper,
            command=self._on_paper,
        )
        self.rb_80.pack(side=tk.LEFT, padx=(0, 12))
        self.lbl_machine = ttk.Label(paper_row)
        self.lbl_machine.pack(side=tk.LEFT, padx=(0, 6))
        self.machine_combo = ttk.Combobox(
            paper_row,
            textvariable=self._machine_var,
            state="readonly",
            width=22,
        )
        self.machine_combo.pack(side=tk.LEFT, padx=(0, 12))
        self.machine_combo.bind("<<ComboboxSelected>>", self._on_machine)
        self.btn_machine_add = ttk.Button(paper_row, command=self._add_machine)
        self.btn_machine_add.pack(side=tk.LEFT, padx=(0, 12))
        self._sync_machine_combo()
        self.btn_print_a4 = ttk.Button(
            paper_row, command=lambda: self.print_paper(PAPER_A4)
        )
        self.btn_print_a4.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_print_80 = ttk.Button(
            paper_row, command=lambda: self.print_paper(PAPER_80MM)
        )
        self.btn_print_80.pack(side=tk.LEFT)

        self._update_bar = tk.Frame(self, bg="#e6b800")
        self.btn_update = tk.Button(
            self._update_bar,
            text=self._tr("update"),
            command=self._on_update,
            bg="#e6b800",
            fg="#111",
            activebackground="#f0c420",
            activeforeground="#111",
            disabledforeground="#555555",
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            padx=10,
            pady=8,
            cursor="hand2",
            font=("Segoe UI", 12, "bold"),
        )
        self.btn_update.pack(fill=tk.X)

        body = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        self._body = body
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        left = ttk.Frame(body)
        self._cad_ready, self._cad_empty = cube_photo(self, size=24, dark=False)
        legend = ttk.Frame(left)
        legend.pack(anchor=tk.W, fill=tk.X)
        tk.Label(legend, image=self._cad_ready).pack(side=tk.LEFT)
        self.cad_legend_lbl = ttk.Label(legend)
        self.cad_legend_lbl.pack(side=tk.LEFT)
        self.file_list = make_file_tree(left, dark=False, rowheight=28)
        self.file_list.pack(fill=tk.BOTH, expand=True)
        self.file_list.bind("<<TreeviewSelect>>", self._on_select)
        body.add(left, weight=1)

        right = ttk.Frame(body)
        self.iso_label = ttk.Label(right)
        self._preview_row = ttk.Frame(right)
        self._preview_row.pack(fill=tk.BOTH, expand=True)
        self.section_frame = ttk.LabelFrame(self._preview_row)
        self.section_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        self._section_vars: dict[str, tk.BooleanVar] = {}
        self._section_checks: dict[str, ttk.Checkbutton] = {}
        seed = self._section_seed
        ticks = ttk.Frame(self.section_frame)
        ticks.pack(fill=tk.BOTH, expand=True)
        for key in GUI_SECTION_KEYS:
            var = tk.BooleanVar(value=getattr(seed, key))
            self._section_vars[key] = var
            cb = ttk.Checkbutton(
                ticks, variable=var, command=self._on_sections
            )
            cb.pack(anchor=tk.W)
            self._section_checks[key] = cb
        self._section_safety = ttk.Label(self.section_frame, wraplength=220)
        self._section_safety.pack(anchor=tk.W, pady=(6, 4))
        packs = ttk.Frame(self.section_frame)
        packs.pack(fill=tk.X, pady=(0, 4))
        self._btn_pack_load = ttk.Button(
            packs, command=lambda: self._apply_pack(SECTIONS_LOAD)
        )
        self._btn_pack_set = ttk.Button(
            packs, command=lambda: self._apply_pack(SECTIONS_SET)
        )
        self._btn_pack_run = ttk.Button(
            packs, command=lambda: self._apply_pack(SECTIONS_RUN)
        )
        self._btn_pack_load.pack(fill=tk.X, pady=1)
        self._btn_pack_set.pack(fill=tk.X, pady=1)
        self._btn_pack_run.pack(fill=tk.X, pady=1)
        preview_col = ttk.Frame(self._preview_row)
        preview_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.lbl_report = ttk.Label(preview_col)
        self.lbl_report.pack(anchor=tk.W)
        text_frame = ttk.Frame(preview_col)
        text_frame.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(text_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            undo=False,
            width=82,
        )
        xscroll = ttk.Scrollbar(
            preview_col, orient=tk.HORIZONTAL, command=self.preview.xview
        )
        self.preview.configure(yscrollcommand=scroll.set, xscrollcommand=xscroll.set)
        self.preview.pack(in_=text_frame, side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=self.preview.yview)
        xscroll.pack(fill=tk.X)
        body.add(right, weight=3)

        self.status = ttk.Label(self, padding=8)
        self.status.pack(fill=tk.X)

    def _apply_language(self) -> None:
        self.title(self._tr("app_title_gui", version=display_version()))
        self.version_lbl.config(text=f"v{display_version()}")
        self.btn_open.config(text=self._tr("open_nc"))
        self.btn_save_fmt.config(text=self._tr("save_formats"))
        self.btn_save_all.config(text=self._tr("save_all"))
        self.btn_out.config(text=self._tr("output_folder"))
        self.btn_step.config(text=self._tr("step_folders"))
        if self._out_dir is None:
            self.out_label.config(text=self._tr("save_next_to_nc"))
        else:
            self.out_label.config(text=str(self._out_dir))
        self.rb_lang_pl.config(text=self._tr("lang_pl"))
        self.rb_lang_en.config(text=self._tr("lang_en"))
        self.lbl_preview.config(text=self._tr("preview_print"))
        self.lbl_machine.config(text=self._tr("machine"))
        self.btn_machine_add.config(text=self._tr("machine_add"))
        self._sync_machine_combo()
        self.rb_80.config(text=self._tr("paper_thermal"))
        self.btn_print_a4.config(text=self._tr("print_a4"))
        self.btn_print_80.config(text=self._tr("print_80"))
        if self._pending_update is not None and not self._updating:
            self.btn_update.config(text=update_button_label(self._lang, self._pending_update))
        else:
            self.btn_update.config(text=self._tr("update"))
        self.cad_legend_lbl.config(text=f"  {self._tr('cad_legend')}")
        self.section_frame.config(text=self._tr("report_sections"))
        for key, cb in self._section_checks.items():
            cb.config(text=self._tr(f"section_{key}"))
        self._section_safety.config(text=self._tr("section_safety"))
        self._btn_pack_load.config(text=self._tr("section_use_load"))
        self._btn_pack_set.config(text=self._tr("section_use_set"))
        self._btn_pack_run.config(text=self._tr("section_use_run"))
        self.lbl_report.config(text=self._tr("report_preview"))
        if not self._results:
            self.status.config(text=self._tr("gui_idle"))
        else:
            self._status_loaded()
        self._on_select()

    def _on_language(self) -> None:
        self._lang = parse_language(self._lang_var.get(), default=GUI_DEFAULT)
        self._apply_language()
        try:
            saved = save_kiosk_values(
                {"language": self._lang}, source=self._cfg_source
            )
            self._cfg_source = saved
            save_kiosk_values({"language": self._lang}, dest=ui_overlay_path())
        except OSError:
            pass

    def _machine_labels(self) -> list[str]:
        names = [machine_display_name(m, self._lang) for m in self._machines]
        if len(names) != len(set(names)):
            return [
                f"{machine_display_name(m, self._lang)} ({m.id})"
                for m in self._machines
            ]
        return names

    def _label_for_machine(self, mill) -> str:
        labels = self._machine_labels()
        for i, m in enumerate(self._machines):
            if m.id == mill.id:
                return labels[i]
        return labels[0] if labels else mill.name

    def _sync_machine_combo(self) -> None:
        labels = self._machine_labels()
        self.machine_combo["values"] = labels
        mill = next(
            (m for m in self._machines if m.id == self._machine_id),
            self._machines[0],
        )
        self._machine_id = mill.id
        self._machine_var.set(self._label_for_machine(mill))

    def _active_machine(self):
        return next(
            (m for m in self._machines if m.id == self._machine_id),
            self._machines[0],
        )

    def _persist_gui_prefs(self) -> None:
        updates = {
            "last_paper": parse_gui_paper(self._paper.get()),
            "report_sections": self._gui_sections().to_csv(),
        }
        if self._last_nc_dir:
            updates["last_nc_dir"] = self._last_nc_dir
        if self._out_dir is not None:
            updates["last_out_dir"] = str(self._out_dir)
        try:
            saved = save_kiosk_values(updates, source=self._cfg_source)
            self._cfg_source = saved
            save_kiosk_values(updates, dest=ui_overlay_path())
        except OSError:
            pass

    def _on_paper(self) -> None:
        self._paper.set(parse_gui_paper(self._paper.get()))
        self._persist_gui_prefs()
        self._on_select()

    def _gui_sections(self) -> ReportSections:
        ticks = {key: var.get() for key, var in self._section_vars.items()}
        return ReportSections(
            **{key: bool(ticks.get(key, False)) for key in GUI_SECTION_KEYS}
        )

    def _apply_pack(self, pack: ReportSections) -> None:
        for key, var in self._section_vars.items():
            var.set(bool(getattr(pack, key)))
        self._on_sections()

    def _on_sections(self) -> None:
        self._persist_gui_prefs()
        self._on_select()

    def _persist_machine(self) -> None:
        try:
            saved = save_kiosk_values(
                {"machine": self._machine_id}, source=self._cfg_source
            )
            self._cfg_source = saved
            save_kiosk_values({"machine": self._machine_id}, dest=ui_overlay_path())
        except OSError:
            pass

    def _reparse_open(self) -> None:
        self._reload_gen += 1
        self._reload_inflight.clear()
        mill = self._active_machine()
        for key, (path, _) in list(self._results.items()):
            try:
                self._results[key] = (path, parse_nc_file(path, machine=mill))
                self._stamps[key] = file_stamp(path)
            except Exception:
                continue
        if self._results:
            self._on_select()

    def _on_machine(self, _event=None) -> None:
        label = self._machine_var.get()
        labels = self._machine_labels()
        try:
            i = labels.index(label)
        except ValueError:
            return
        mid = self._machines[i].id
        if mid == self._machine_id:
            return
        self._machine_id = mid
        self._persist_machine()
        self._reparse_open()

    def _add_machine(self) -> None:
        win = tk.Toplevel(self)
        win.title(self._tr("machine_add_title"))
        win.transient(self)
        win.resizable(False, False)
        body = ttk.Frame(win, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        entries: dict[str, ttk.Entry] = {}
        row = 0
        for key, default in MILL_FORM_SCALARS:
            ttk.Label(body, text=self._tr(key)).grid(
                row=row, column=0, columnspan=2, sticky=tk.W, pady=(6, 0)
            )
            ent = ttk.Entry(body, width=36)
            ent.insert(0, default)
            ent.grid(row=row + 1, column=0, columnspan=6, sticky=tk.EW, pady=(0, 4))
            entries[key] = ent
            row += 2

        def add_triplet(heading: str, keys: tuple[str, ...]) -> None:
            nonlocal row
            ttk.Label(body, text=self._tr(heading)).grid(
                row=row, column=0, columnspan=6, sticky=tk.W, pady=(8, 2)
            )
            row += 1
            for i, (key, ax) in enumerate(
                zip(keys, ("machine_ax_x", "machine_ax_y", "machine_ax_z"))
            ):
                ttk.Label(body, text=self._tr(ax)).grid(
                    row=row, column=i * 2, sticky=tk.W, padx=(0 if i == 0 else 8, 4)
                )
                ent = ttk.Entry(body, width=10)
                ent.grid(row=row, column=i * 2 + 1, sticky=tk.EW)
                entries[key] = ent
            row += 1

        add_triplet("machine_atc_group", MILL_FORM_ATC)
        add_triplet("machine_offset_group", MILL_FORM_OFFSET)
        ttk.Label(body, text=self._tr("machine_travel_group")).grid(
            row=row, column=0, columnspan=6, sticky=tk.W, pady=(8, 2)
        )
        row += 1
        for pair in MILL_FORM_TRAVEL:
            for i, key in enumerate(pair):
                ttk.Label(body, text=self._tr(key)).grid(
                    row=row, column=i * 2, sticky=tk.W, padx=(0 if i == 0 else 8, 4)
                )
                ent = ttk.Entry(body, width=10)
                ent.grid(row=row, column=i * 2 + 1, sticky=tk.EW)
                entries[key] = ent
            row += 1
        for col in range(6):
            body.columnconfigure(col, weight=1)

        err = ttk.Label(body, foreground="#a40000")
        err.grid(row=row, column=0, columnspan=6, sticky=tk.W, pady=(8, 8))
        btns = ttk.Frame(body)
        btns.grid(row=row + 1, column=0, columnspan=6, sticky=tk.E)

        def submit() -> None:
            try:
                mill = mill_from_form_entries(
                    entries,
                    existing_ids={m.id for m in self._machines},
                )
            except ValueError as exc:
                err.config(text=self._tr(str(exc)))
                return
            try:
                persist_machine_profile(mill, extra=self._cfg_source)
            except OSError as exc:
                err.config(text=self._tr("settings_save_fail", detail=exc))
                return
            self._apply_saved_machine(mill)
            win.destroy()
            self.status.config(text=self._tr("machine_saved", name=mill.name))

        ttk.Button(btns, text=self._tr("machine_cancel"), command=win.destroy).pack(
            side=tk.RIGHT
        )
        ttk.Button(btns, text=self._tr("machine_save"), command=submit).pack(
            side=tk.RIGHT, padx=(0, 8)
        )
        entries["machine_name"].focus_set()
        win.bind("<Return>", lambda _e: submit())
        win.bind("<Escape>", lambda _e: win.destroy())
        win.grab_set()

    def _apply_saved_machine(self, mill) -> None:
        cfg = load_kiosk_config(self._cfg_source)
        self._machines = list(cfg.machines)
        self._machine_id = mill.id
        self._sync_machine_combo()
        self._persist_machine()
        self._reparse_open()

    def _status_loaded(self, extra: str = "") -> None:
        ready = sum(
            1
            for key in self._order
            if self._models is not None and self._models.is_ready(Path(key))
        )
        text = self._tr("files_loaded", files=file_count(self._lang, len(self._results)))
        if self._order:
            text = f"{text}  ·  {self._tr('step_ready', ready=ready, total=len(self._order))}"
        if extra:
            text = f"{text}{extra}"
        self.status.config(text=text)

    def _file_label(self, path: Path) -> str:
        return path.name

    def _cad_ready_for(self, path: Path) -> bool:
        return self._models is not None and self._models.is_ready(path)

    def _cad_status_extra(self) -> str:
        selected = self._selected_result()
        path = selected[0] if selected is not None else None
        if path is None and self._order:
            path = Path(self._order[0])
        reason = cad_status(
            path, prep=self._models, model_roots=self._model_roots
        )
        if reason == "ready":
            return ""
        if reason == "idle" and not self._model_roots:
            return f"  ·  {self._tr('step_hint')}"
        if reason == "idle":
            return ""
        return f"  ·  {cad_status_label(self._lang, reason)}"

    def _images_for(self, path: Path) -> list[Path]:
        if self._models is None:
            return []
        return self._models.ready_images(path)

    def _hide_iso(self) -> None:
        self._iso_photo = None
        self._iso_path = None
        self.iso_label.configure(image="")
        self.iso_label.pack_forget()

    def _refresh_iso(self) -> None:
        selected = self._selected_result()
        if selected is None:
            self._hide_iso()
            return
        path, _ = selected
        images = self._images_for(path)
        if not images:
            self._hide_iso()
            return
        png = images[0]
        if self._iso_path == png and self._iso_photo is not None:
            return
        photo = step_photo(self, png, max_width=480, max_height=360)
        if photo is None:
            self._hide_iso()
            return
        self._iso_photo = photo
        self._iso_path = png
        self.iso_label.configure(image=photo)
        if not self.iso_label.winfo_ismapped():
            self.iso_label.pack(anchor=tk.N, pady=(0, 8), before=self._preview_row)

    def _start_models(self) -> None:
        if self._models is not None:
            self._models.close()
        self._models = ModelPrep(self._model_roots)
        self._enqueue_open_files()

    def _enqueue_open_files(self) -> None:
        if self._models is None:
            return
        self._models.set_files([path for path, _result in self._results.values()])

    def _poll_models(self) -> None:
        self._model_job = self.after(500, self._poll_models)
        self._reload_stale_nc()
        if self._models is None or not self._order:
            return
        changed = False
        children = self.file_list.get_children()
        if len(children) != len(self._order):
            return
        for i, key in enumerate(self._order):
            path = Path(key)
            iid = children[i]
            label = self._file_label(path)
            ready = self._cad_ready_for(path)
            try:
                current = self.file_list.item(iid, "text")
            except tk.TclError:
                return
            if current != label or row_is_ready(self.file_list, iid) != ready:
                apply_file_row(
                    self.file_list,
                    iid,
                    label,
                    ready=ready,
                    ready_img=self._cad_ready,
                    empty_img=self._cad_empty,
                )
                changed = True
        if changed:
            extra = self._cad_status_extra()
            self._status_loaded(extra)
            self._refresh_iso()

    def _reload_stale_nc(self) -> None:
        """Re-parse open files when CAM overwrites them (mtime and size)."""
        if not self._results or self._updating:
            return
        disk = {key: file_stamp(path) for key, (path, _) in self._results.items()}
        for key in nc_keys_to_reload(self._stamps, disk):
            if key in self._reload_inflight:
                continue
            path = self._results[key][0]
            if self._selected_key() == key:
                self.status.config(text=self._tr("preview_reading"))
            self._reload_inflight.add(key)
            mill = self._active_machine()
            gen = self._reload_gen
            threading.Thread(
                target=self._reload_nc_worker,
                args=(key, path, mill, gen),
                daemon=True,
            ).start()

    def _reload_nc_worker(self, key: str, path: Path, mill, gen: int) -> None:
        stamp = file_stamp(path)
        result = None
        try:
            result = parse_nc_file(path, machine=mill)
        except Exception:
            result = None

        def done() -> None:
            self._reload_inflight.discard(key)
            if gen != self._reload_gen or key not in self._results:
                return
            now = file_stamp(path)
            if preview_cache_stale(stamp, now):
                return
            if result is None:
                return
            self._results[key] = (path, result)
            self._stamps[key] = now
            if self._models is not None:
                self._models.invalidate(path)
            extra = self._cad_status_extra()
            if self._selected_key() == key:
                self._on_select()
                self._status_loaded(f"  ·  {self._tr('gui_reloaded', name=path.name)}{extra}")
            else:
                self._status_loaded(extra)

        try:
            self.after(0, done)
        except tk.TclError:
            pass

    def choose_model_roots(self) -> None:
        chosen = filedialog.askdirectory(title=self._tr("choose_step"))
        if not chosen:
            return
        path = Path(chosen)
        add = False
        if self._model_roots:
            add = messagebox.askyesno(
                self._tr("step_add_title"),
                self._tr("step_add_body"),
            )
        roots = list(self._model_roots) if add else []
        if path not in roots:
            roots.append(path)
        saved = save_model_roots(roots, dest=self._cfg_source)
        self._cfg_source = saved
        self._model_roots = roots
        self._start_models()
        cad = self._tr("cad_ok") if render_available() else self._tr("cad_missing")
        self.status.config(
            text=self._tr(
                "step_folders_status", n=len(roots), cad=cad, name=saved.name
            )
        )

    def open_files(self) -> None:
        kwargs: dict[str, str] = {}
        start = Path(self._last_nc_dir) if self._last_nc_dir else None
        if start is not None and start.is_dir():
            kwargs["initialdir"] = str(start)
        paths = filedialog.askopenfilenames(
            title=self._tr("select_cnc"),
            filetypes=[
                (self._tr("ft_cnc"), "*.nc *.NC *.tap *.TAP *.txt *.TXT"),
                (self._tr("ft_all"), "*.*"),
            ],
            **kwargs,
        )
        if not paths:
            return
        self._last_nc_dir = str(Path(paths[0]).parent)
        self._persist_gui_prefs()
        errors: list[str] = []
        for raw in paths:
            path = Path(raw)
            try:
                self._results[str(path)] = (
                    path,
                    parse_nc_file(path, machine=self._active_machine()),
                )
                self._stamps[str(path)] = file_stamp(path)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{path.name}: {exc}")
        self._refresh_list()
        self._enqueue_open_files()
        children = self.file_list.get_children()
        if children:
            self.file_list.selection_set(children[0])
            self.file_list.focus(children[0])
            self._on_select()
        if errors:
            messagebox.showerror(self._tr("parse_error"), "\n".join(errors))
        extra = self._cad_status_extra()
        self._status_loaded(extra)

    def _refresh_list(self) -> None:
        clear_file_tree(self.file_list)
        self._order = list(self._results)
        for key in self._order:
            path = Path(key)
            insert_file_row(
                self.file_list,
                self._file_label(path),
                ready=self._cad_ready_for(path),
                ready_img=self._cad_ready,
                empty_img=self._cad_empty,
            )

    def _selected_key(self) -> str | None:
        sel = self.file_list.selection()
        if not sel:
            return None
        return self._order[int(self.file_list.index(sel[0]))]

    def _selected_result(self) -> tuple[Path, ParseResult] | None:
        key = self._selected_key()
        if key is None:
            return None
        return self._results[key]

    def _on_select(self, _event: object | None = None) -> None:
        self.preview.delete("1.0", tk.END)
        selected = self._selected_result()
        if selected is None:
            self._refresh_iso()
            return
        _path, result = selected
        paper = self._paper.get()
        sections = self._gui_sections()
        text = format_report(result, paper=paper, lang=self._lang, sections=sections)
        self.preview.insert("1.0", text)
        if paper == PAPER_80MM:
            self.preview.configure(width=50, font=("Consolas", 11), wrap=tk.NONE)
        else:
            self.preview.configure(width=82, font=("Consolas", 10), wrap=tk.WORD)
        self._refresh_iso()

    def choose_out_dir(self) -> None:
        kwargs: dict[str, str] = {}
        if self._out_dir is not None and self._out_dir.is_dir():
            kwargs["initialdir"] = str(self._out_dir)
        chosen = filedialog.askdirectory(title=self._tr("out_folder_title"), **kwargs)
        if not chosen:
            return
        folder = Path(chosen)
        if is_protected(folder, self._model_roots):
            messagebox.showerror(
                self._tr("out_folder_title"), self._tr("company_folder_readonly")
            )
            return
        self._out_dir = folder
        self.out_label.config(text=str(self._out_dir))
        self._persist_gui_prefs()

    def save_current(self) -> None:
        selected = self._selected_result()
        if selected is None:
            messagebox.showinfo(self._tr("save_title"), self._tr("select_first"))
            return
        path, result = selected
        try:
            dests = write_report(
                result,
                out_dir=self._out_dir,
                image_paths=ticket_image_paths(
                    result, self._images_for(path), self._gui_sections()
                ),
                lang=self._lang,
                protected_roots=self._model_roots,
                sections=self._gui_sections(),
            )
        except ProtectedWriteError:
            messagebox.showerror(
                self._tr("save_title"), self._tr("company_folder_readonly")
            )
            return
        self.status.config(
            text=self._tr("wrote_files", n=len(dests), folder=dests[0].parent)
        )

    def save_all(self) -> None:
        if not self._results:
            messagebox.showinfo(self._tr("save_all_title"), self._tr("open_first"))
            return
        written = 0
        for path, result in self._results.values():
            try:
                write_report(
                    result,
                    out_dir=self._out_dir,
                    image_paths=ticket_image_paths(
                        result, self._images_for(path), self._gui_sections()
                    ),
                    lang=self._lang,
                    protected_roots=self._model_roots,
                    sections=self._gui_sections(),
                )
            except ProtectedWriteError:
                messagebox.showerror(
                    self._tr("save_all_title"), self._tr("company_folder_readonly")
                )
                return
            written += 1
        self.status.config(text=self._tr("wrote_all", n=written))

    def print_paper(self, paper: str) -> None:
        self._paper.set(parse_gui_paper(paper))
        self._persist_gui_prefs()
        self._on_select()
        selected = self._selected_result()
        if selected is None:
            messagebox.showinfo(self._tr("print_title"), self._tr("select_first"))
            return
        path, result = selected
        sections = self._gui_sections()
        html = open_print_html(
            result,
            paper=paper,
            auto_print=True,
            image_paths=ticket_image_paths(
                result, self._images_for(path), sections
            ),
            lang=self._lang,
            sections=sections,
        )
        label = "A4" if paper == PAPER_A4 else "80 mm"
        self.status.config(
            text=self._tr("opened_print", label=label, name=html.name)
        )

    def _start_update_check(self) -> None:
        if self._update_check_inflight or self._updating or self._pending_update is not None:
            return
        self._update_check_inflight = True
        threading.Thread(target=self._check_update_worker, daemon=True).start()

    def _on_window_focus(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        self._start_update_check()
        self._reload_stale_nc()

    def _check_update_worker(self) -> None:
        from .update import check_for_update, check_github_windows_exe

        status = None
        try:
            if getattr(sys, "frozen", False):
                status = check_github_windows_exe()
            else:
                status = check_for_update()
        except Exception:
            status = None

        def done() -> None:
            self._update_check_inflight = False
            if status is not None:
                self._apply_update_status(status)

        self.after(0, done)

    def _show_update_bar(self) -> None:
        try:
            mapped = bool(self._update_bar.winfo_ismapped())
        except tk.TclError:
            return
        if mapped:
            return
        self._update_bar.pack(fill=tk.X, padx=8, pady=(0, 8), before=self._body)

    def _hide_update_bar(self) -> None:
        self._update_bar.pack_forget()

    def _apply_update_status(self, status: UpdateCheck) -> None:
        if self._updating or not status.available:
            return
        self._pending_update = status
        self.btn_update.config(text=update_button_label(self._lang, status))
        self._show_update_bar()
        if status.new_version:
            self.status.config(
                text=self._tr(
                    "update_status_gui",
                    current=status.current_version or __version__,
                    new=status.new_version,
                )
            )
        else:
            self.status.config(text=self._tr("update_available_gui"))

    def _on_update(self) -> None:
        if self._updating or self._pending_update is None:
            return
        self._updating = True
        self.btn_update.config(state=tk.DISABLED, text=self._tr("updating"))
        self.status.config(text=self._tr("update_progress_gui"))
        threading.Thread(target=self._update_worker, daemon=True).start()

    def _update_worker(self) -> None:
        from .update import perform_frozen_exe_update, perform_update

        if getattr(sys, "frozen", False):
            code = perform_frozen_exe_update()
        else:
            code = perform_update(restart_kiosk=False)
        self.after(0, lambda: self._update_done(code))

    def _update_done(self, code: int) -> None:
        if code == 0:
            self.status.config(text=self._tr("update_restarting_gui"))
            self.update_idletasks()
            if getattr(sys, "frozen", False):
                self.destroy()
                return
            from .update import relaunch_gui

            relaunch_gui()
            return
        self._updating = False
        if code == 2:
            self._pending_update = None
            self._hide_update_bar()
            self.btn_update.config(state=tk.NORMAL, text=self._tr("update"))
            self.status.config(text=self._tr("update_frozen"))
            return
        if self._pending_update is not None:
            self.btn_update.config(
                state=tk.NORMAL,
                text=update_button_label(self._lang, self._pending_update),
            )
        else:
            self.btn_update.config(state=tk.NORMAL, text=self._tr("update"))
        self.status.config(text=self._tr("update_failed_gui"))

    def _on_close(self) -> None:
        if self._model_job is not None:
            try:
                self.after_cancel(self._model_job)
            except tk.TclError:
                pass
        if self._models is not None:
            try:
                self._models.close()
            except Exception:
                pass
        self.destroy()


def run_gui() -> None:
    app = ToolReportApp()
    app.mainloop()
