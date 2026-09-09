"""Tkinter GUI: pick CNC files, preview and print A4 / 80 mm reports."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ._version import __version__
from .parser import ParseResult, parse_nc_file
from .report import (
    PAPER_80MM,
    PAPER_A4,
    format_report,
    open_print_html,
    write_report,
)


class ToolReportApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"CNC Tool Report {__version__}")
        self.geometry("1000x700")
        self.minsize(760, 500)

        self._results: dict[str, tuple[Path, ParseResult]] = {}
        self._order: list[str] = []
        self._out_dir: Path | None = None
        self._paper = tk.StringVar(value=PAPER_A4)

        self._build()

    def _build(self) -> None:
        top = ttk.Frame(self, padding=8)
        top.pack(fill=tk.X)

        ttk.Button(top, text="Open NC files…", command=self.open_files).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(top, text="Save all formats", command=self.save_current).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(top, text="Save all files", command=self.save_all).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(top, text="Output folder…", command=self.choose_out_dir).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        self.out_label = ttk.Label(top, text="Save next to each .nc file")
        self.out_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        paper_row = ttk.Frame(self, padding=(8, 0, 8, 8))
        paper_row.pack(fill=tk.X)
        ttk.Label(paper_row, text="Preview / print:").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(
            paper_row,
            text="A4",
            value=PAPER_A4,
            variable=self._paper,
            command=self._on_select,
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(
            paper_row,
            text="80 mm thermal",
            value=PAPER_80MM,
            variable=self._paper,
            command=self._on_select,
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Button(paper_row, text="Print A4…", command=lambda: self.print_paper(PAPER_A4)).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(
            paper_row, text="Print 80 mm…", command=lambda: self.print_paper(PAPER_80MM)
        ).pack(side=tk.LEFT)

        body = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        left = ttk.Frame(body)
        ttk.Label(left, text="Files").pack(anchor=tk.W)
        self.file_list = tk.Listbox(left, width=36, exportselection=False)
        self.file_list.pack(fill=tk.BOTH, expand=True)
        self.file_list.bind("<<ListboxSelect>>", self._on_select)
        body.add(left, weight=1)

        right = ttk.Frame(body)
        ttk.Label(right, text="Report preview").pack(anchor=tk.W)
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

        self.status = ttk.Label(
            self,
            text="Open NC files, then Print A4 or Print 80 mm.",
            padding=8,
        )
        self.status.pack(fill=tk.X)

    def open_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select CNC programs",
            filetypes=[
                ("CNC programs", "*.nc *.NC *.tap *.TAP *.txt *.TXT"),
                ("All files", "*.*"),
            ],
        )
        if not paths:
            return
        errors: list[str] = []
        for raw in paths:
            path = Path(raw)
            try:
                self._results[str(path)] = (path, parse_nc_file(path))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{path.name}: {exc}")
        self._refresh_list()
        if self.file_list.size():
            self.file_list.selection_clear(0, tk.END)
            self.file_list.selection_set(0)
            self._on_select()
        if errors:
            messagebox.showerror("Parse error", "\n".join(errors))
        self.status.config(text=f"{len(self._results)} file(s) loaded")

    def _refresh_list(self) -> None:
        self.file_list.delete(0, tk.END)
        self._order = list(self._results)
        for key in self._order:
            self.file_list.insert(tk.END, Path(key).name)

    def _selected_key(self) -> str | None:
        sel = self.file_list.curselection()
        if not sel:
            return None
        return self._order[sel[0]]

    def _selected_result(self) -> tuple[Path, ParseResult] | None:
        key = self._selected_key()
        if key is None:
            return None
        return self._results[key]

    def _on_select(self, _event: object | None = None) -> None:
        self.preview.delete("1.0", tk.END)
        selected = self._selected_result()
        if selected is None:
            return
        _path, result = selected
        paper = self._paper.get()
        text = format_report(result, paper=paper)
        self.preview.insert("1.0", text)
        if paper == PAPER_80MM:
            self.preview.configure(width=50, font=("Consolas", 11), wrap=tk.NONE)
        else:
            self.preview.configure(width=82, font=("Consolas", 10), wrap=tk.WORD)

    def choose_out_dir(self) -> None:
        chosen = filedialog.askdirectory(title="Report output folder")
        if not chosen:
            return
        self._out_dir = Path(chosen)
        self.out_label.config(text=str(self._out_dir))

    def save_current(self) -> None:
        selected = self._selected_result()
        if selected is None:
            messagebox.showinfo("Save", "Select a file first.")
            return
        _path, result = selected
        dests = write_report(result, out_dir=self._out_dir)
        self.status.config(text=f"Wrote {len(dests)} files in {dests[0].parent}")

    def save_all(self) -> None:
        if not self._results:
            messagebox.showinfo("Save all", "Open NC files first.")
            return
        written = 0
        for _path, result in self._results.values():
            write_report(result, out_dir=self._out_dir)
            written += 1
        self.status.config(text=f"Wrote A4 + 80 mm reports for {written} file(s)")

    def print_paper(self, paper: str) -> None:
        selected = self._selected_result()
        if selected is None:
            messagebox.showinfo("Print", "Select a file first.")
            return
        _path, result = selected
        path = open_print_html(result, paper=paper, auto_print=True)
        label = "A4" if paper == PAPER_A4 else "80 mm"
        self.status.config(text=f"Opened {label} print preview ({path.name})")


def run_gui() -> None:
    app = ToolReportApp()
    app.mainloop()
