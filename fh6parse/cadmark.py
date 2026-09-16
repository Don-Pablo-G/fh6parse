"""Isometric-cube mark: the STEP / 3D ticket view is ready to print."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tkinter as tk

LEGEND = "3D view ready to print"
TAG_READY = "cad"


def cube_pixels(
    size: int,
    *,
    bg: tuple[int, int, int],
    edge: tuple[int, int, int],
    width: int = 2,
) -> list[list[tuple[int, int, int]]]:
    """Visible-edge isometric cube (ticket-style line art, not a filled square)."""
    size = max(18, int(size))
    grid = [[bg for _ in range(size)] for _ in range(size)]
    cx = size // 2
    pad = 2
    hw = max(5, cx - pad)
    hh = max(3, (size * 3) // 16)
    top = pad + 1
    body = max(5, size - pad - 1 - (top + 2 * hh))
    north = (cx, top)
    east = (cx + hw, top + hh)
    south = (cx, top + 2 * hh)
    west = (cx - hw, top + hh)
    east_b = (east[0], east[1] + body)
    south_b = (south[0], south[1] + body)
    west_b = (west[0], west[1] + body)
    for a, b in (
        (north, east),
        (east, south),
        (south, west),
        (west, north),
        (east, east_b),
        (south, south_b),
        (west, west_b),
        (east_b, south_b),
        (south_b, west_b),
    ):
        _thick_line(grid, a, b, edge, width)
    return grid


def cube_photo(
    master: tk.Misc,
    *,
    size: int,
    dark: bool,
) -> tuple[tk.PhotoImage, tk.PhotoImage]:
    """(ready cube, empty spacer) — keep both on the widget so Tk does not GC them."""
    if dark:
        bg = (0x1A, 0x1A, 0x1A)
        edge = (0xFF, 0xD5, 0x4A)
    else:
        bg = (0xF0, 0xF0, 0xF0)
        edge = (0x1A, 0x1A, 0x1A)
    ready = _photo(master, cube_pixels(size, bg=bg, edge=edge, width=2))
    empty = _photo(master, [[bg for _ in range(size)] for _ in range(size)])
    return ready, empty


def _photo(master: tk.Misc, grid: list[list[tuple[int, int, int]]]) -> tk.PhotoImage:
    import tkinter as tk

    h = len(grid)
    w = len(grid[0])
    img = tk.PhotoImage(master=master, width=w, height=h)
    rows = [
        "{" + " ".join(f"#{r:02x}{g:02x}{b:02x}" for r, g, b in row) + "}"
        for row in grid
    ]
    img.put(" ".join(rows))
    return img


def make_file_tree(
    parent: tk.Misc,
    *,
    dark: bool,
    font: object | None = None,
    rowheight: int = 28,
) -> tk.Widget:
    """Treeview that can show the cube PhotoImage (Listbox cannot)."""
    import tkinter as tk
    from tkinter import ttk

    style = ttk.Style(parent)
    name = "KioskCad.Treeview" if dark else "GuiCad.Treeview"
    if dark:
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        kwargs: dict = {
            "background": "#1a1a1a",
            "fieldbackground": "#1a1a1a",
            "foreground": "#eeeeee",
            "rowheight": rowheight,
            "borderwidth": 0,
            "relief": "flat",
            "indent": 0,
        }
        if font is not None:
            kwargs["font"] = font
        style.configure(name, **kwargs)
        style.map(
            name,
            background=[("selected", "#e6b800")],
            foreground=[("selected", "#111111")],
        )
    else:
        kwargs = {
            "rowheight": rowheight,
            "indent": 0,
            "background": "#f0f0f0",
            "fieldbackground": "#f0f0f0",
        }
        if font is not None:
            kwargs["font"] = font
        style.configure(name, **kwargs)
    try:
        style.layout(name, [("Treeview.treearea", {"sticky": "nswe"})])
    except tk.TclError:
        pass
    tree = ttk.Treeview(
        parent,
        style=name,
        show="tree",
        selectmode="browse",
        takefocus=True,
    )
    tree.column("#0", stretch=True, anchor="w")
    return tree


def clear_file_tree(tree: tk.Widget) -> None:
    rows = tree.get_children()
    if rows:
        tree.delete(*rows)


def apply_file_row(
    tree: tk.Widget,
    iid: str,
    text: str,
    *,
    ready: bool,
    ready_img: tk.PhotoImage,
    empty_img: tk.PhotoImage,
) -> None:
    tree.item(
        iid,
        text=text,
        image=ready_img if ready else empty_img,
        tags=(TAG_READY,) if ready else (),
    )


def insert_file_row(
    tree: tk.Widget,
    text: str,
    *,
    ready: bool,
    ready_img: tk.PhotoImage,
    empty_img: tk.PhotoImage,
) -> str:
    return tree.insert(
        "",
        "end",
        text=text,
        image=ready_img if ready else empty_img,
        tags=(TAG_READY,) if ready else (),
    )


def row_is_ready(tree: tk.Widget, iid: str) -> bool:
    tags = tree.item(iid, "tags") or ()
    return TAG_READY in tags


def _thick_line(grid, a, b, rgb, width: int) -> None:
    _line(grid, a, b, rgb)
    if width < 2:
        return
    ax, ay = int(a[0]), int(a[1])
    bx, by = int(b[0]), int(b[1])
    if abs(bx - ax) >= abs(by - ay):
        _line(grid, (ax, ay - 1), (bx, by - 1), rgb)
        _line(grid, (ax, ay + 1), (bx, by + 1), rgb)
    else:
        _line(grid, (ax - 1, ay), (bx - 1, by), rgb)
        _line(grid, (ax + 1, ay), (bx + 1, by), rgb)


def _line(grid, a, b, rgb) -> None:
    x0, y0 = int(a[0]), int(a[1])
    x1, y1 = int(b[0]), int(b[1])
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    h, w = len(grid), len(grid[0])
    while True:
        if 0 <= x0 < w and 0 <= y0 < h:
            grid[y0][x0] = rgb
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
