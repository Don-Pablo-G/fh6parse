"""Tkinter GUI: pick CNC files, preview and print A4 / 80 mm reports."""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ._version import __version__
from .cadmark import (
    apply_file_row,
    clear_file_tree,
    cube_photo,
    insert_file_row,
    make_file_tree,
    row_is_ready,
    step_photo,
)
from .i18n import GUI_DEFAULT, file_count, parse_language, t, update_button_label
from .kiosk import load_kiosk_config, parse_gui_paper, save_kiosk_values, save_model_roots, ui_overlay_path
from .modelprep import ModelPrep
from .modelrender import render_available
from .parser import ParseResult, parse_nc_file
from .report import (
    PAPER_80MM,
    PAPER_A4,
    format_report,
    open_print_html,
    write_report,
)
from .update import UpdateCheck


class ToolReportApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"CNC Tool Report {__version__}")
        self.geometry("1000x700")
        self.minsize(760, 500)

        self._results: dict[str, tuple[Path, ParseResult]] = {}
        self._order: list[str] = []
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
        if cfg.last_out_dir:
            out = Path(cfg.last_out_dir)
            if out.is_dir():
                self._out_dir = out
        self._models: ModelPrep | None = None
        self._model_job: str | None = None
        self._pending_update: UpdateCheck | None = None
        self._updating = False
        self._iso_photo = None
        self._iso_path: Path | None = None

        self._build()
        self._apply_language()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._start_models()
        self.after(400, self._poll_models)
        self.after(400, self._start_update_check)

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
            text="Polski",
            value="pl",
            variable=self._lang_var,
            command=self._on_language,
        )
        self.rb_lang_en = ttk.Radiobutton(
            top,
            text="English",
            value="en",
            variable=self._lang_var,
            command=self._on_language,
        )
        self.rb_lang_en.pack(side=tk.RIGHT)
        self.rb_lang_pl.pack(side=tk.RIGHT, padx=(0, 8))

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
        self._sync_machine_combo()
        self.btn_print_a4 = ttk.Button(
            paper_row, command=lambda: self.print_paper(PAPER_A4)
        )
        self.btn_print_a4.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_print_80 = ttk.Button(
            paper_row, command=lambda: self.print_paper(PAPER_80MM)
        )
        self.btn_print_80.pack(side=tk.LEFT)
        self.btn_update = tk.Button(
            paper_row,
            text=self._tr("update"),
            command=self._on_update,
            bg="#e6b800",
            fg="#111",
            activebackground="#f0c420",
            activeforeground="#111",
            relief=tk.FLAT,
            padx=10,
            font=("Segoe UI", 10, "bold"),
        )

        body = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
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
        self.lbl_report = ttk.Label(right)
        self.lbl_report.pack(anchor=tk.W)
        text_frame = ttk.Frame(right)
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
        xscroll = ttk.Scrollbar(right, orient=tk.HORIZONTAL, command=self.preview.xview)
        self.preview.configure(yscrollcommand=scroll.set, xscrollcommand=xscroll.set)
        self.preview.pack(in_=text_frame, side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=self.preview.yview)
        xscroll.pack(fill=tk.X)
        body.add(right, weight=3)

        self.status = ttk.Label(self, padding=8)
        self.status.pack(fill=tk.X)

    def _apply_language(self) -> None:
        self.title(self._tr("app_title_gui", version=__version__))
        self.btn_open.config(text=self._tr("open_nc"))
        self.btn_save_fmt.config(text=self._tr("save_formats"))
        self.btn_save_all.config(text=self._tr("save_all"))
        self.btn_out.config(text=self._tr("output_folder"))
        self.btn_step.config(text=self._tr("step_folders"))
        if self._out_dir is None:
            self.out_label.config(text=self._tr("save_next_to_nc"))
        else:
            self.out_label.config(text=str(self._out_dir))
        self.lbl_preview.config(text=self._tr("preview_print"))
        self.lbl_machine.config(text=self._tr("machine"))
        self.rb_80.config(text=self._tr("paper_thermal"))
        self.btn_print_a4.config(text=self._tr("print_a4"))
        self.btn_print_80.config(text=self._tr("print_80"))
        if self._pending_update is not None and not self._updating:
            self.btn_update.config(text=update_button_label(self._lang, self._pending_update))
        else:
            self.btn_update.config(text=self._tr("update"))
        self.cad_legend_lbl.config(text=f"  {self._tr('cad_legend')}")
        self.lbl_report.config(text=self._tr("report_preview"))
        if not self._results:
            self.status.config(text=self._tr("gui_idle"))
        else:
            self._status_loaded()

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
        names = [m.name for m in self._machines]
        if len(names) != len(set(names)):
            return [f"{m.name} ({m.id})" for m in self._machines]
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
        updates = {"last_paper": parse_gui_paper(self._paper.get())}
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
        mill = self._active_machine()
        for key, (path, _) in list(self._results.items()):
            try:
                self._results[key] = (path, parse_nc_file(path, machine=mill))
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
            self.iso_label.pack(anchor=tk.N, pady=(0, 8), before=self.lbl_report)

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
            extra = ""
            if not render_available():
                extra = f"  ·  {self._tr('cad_not_in_build')}"
            elif not self._model_roots:
                extra = f"  ·  {self._tr('step_hint')}"
            self._status_loaded(extra)
            self._refresh_iso()

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
        extra = ""
        if not render_available():
            extra = f"  ·  {self._tr('cad_not_in_build')}"
        elif not self._model_roots:
            extra = f"  ·  {self._tr('step_hint')}"
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
        text = format_report(result, paper=paper)
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
        self._out_dir = Path(chosen)
        self.out_label.config(text=str(self._out_dir))
        self._persist_gui_prefs()

    def save_current(self) -> None:
        selected = self._selected_result()
        if selected is None:
            messagebox.showinfo(self._tr("save_title"), self._tr("select_first"))
            return
        path, result = selected
        dests = write_report(
            result, out_dir=self._out_dir, image_paths=self._images_for(path)
        )
        self.status.config(
            text=self._tr("wrote_files", n=len(dests), folder=dests[0].parent)
        )

    def save_all(self) -> None:
        if not self._results:
            messagebox.showinfo(self._tr("save_all_title"), self._tr("open_first"))
            return
        written = 0
        for path, result in self._results.values():
            write_report(
                result, out_dir=self._out_dir, image_paths=self._images_for(path)
            )
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
        html = open_print_html(
            result,
            paper=paper,
            auto_print=True,
            image_paths=self._images_for(path),
        )
        label = "A4" if paper == PAPER_A4 else "80 mm"
        self.status.config(
            text=self._tr("opened_print", label=label, name=html.name)
        )

    def _start_update_check(self) -> None:
        threading.Thread(target=self._check_update_worker, daemon=True).start()

    def _check_update_worker(self) -> None:
        from .update import check_for_update, check_github_windows_exe

        if getattr(sys, "frozen", False):
            status = check_github_windows_exe()
        else:
            status = check_for_update()
        self.after(0, lambda: self._apply_update_status(status))

    def _apply_update_status(self, status: UpdateCheck) -> None:
        if self._updating or not status.available:
            return
        self._pending_update = status
        self.btn_update.config(text=update_button_label(self._lang, status))
        if not self.btn_update.winfo_ismapped():
            self.btn_update.pack(side=tk.LEFT, padx=(12, 0))
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
