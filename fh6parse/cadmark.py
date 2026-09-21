"""Isometric-cube mark: the STEP / 3D ticket view is ready to print."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tkinter as tk

LEGEND = "3D view ready to print"
TAG_READY = "cad"
# Same gold as the kiosk legend / UPDATE button.
CUBE_YELLOW = (0xFF, 0xD5, 0x4A)
# Chroma key — GIF transparency. Must not match the cube ink.
CUBE_CLEAR = (0x00, 0x01, 0x02)
KIOSK_BG = "#111111"


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
    dark: bool = True,
) -> tuple[tk.PhotoImage, tk.PhotoImage]:
    """Yellow cube like the legend. Empty spacer matches the list background."""
    if dark:
        bg = (0x11, 0x11, 0x11)
        trans = None
    else:
        bg = CUBE_CLEAR
        trans = CUBE_CLEAR
    ready = _photo_gif(
        master,
        cube_pixels(size, bg=bg, edge=CUBE_YELLOW, width=2),
        trans=trans,
    )
    empty = _photo_gif(
        master,
        [[bg for _ in range(size)] for _ in range(size)],
        trans=trans,
    )
    return ready, empty


def step_zoom_factor(
    width: int, height: int, max_width: int, max_height: int
) -> int:
    """Integer subsample so the ticket PNG fits a screen pane."""
    max_width = max(1, int(max_width))
    max_height = max(1, int(max_height))
    width = max(1, int(width))
    height = max(1, int(height))
    factor = 1
    while (width // factor > max_width or height // factor > max_height) and factor < 16:
        factor += 1
    return factor


def step_photo(
    master: tk.Misc,
    path: Path,
    *,
    max_width: int,
    max_height: int,
) -> tk.PhotoImage | None:
    """Load a stacked isometric PNG and shrink it to the preview pane."""
    import tkinter as tk

    max_width = max(1, int(max_width))
    max_height = max(1, int(max_height))
    try:
        from PIL import Image, ImageTk

        img = Image.open(path)
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS
        img.thumbnail((max_width, max_height), resample)
        return ImageTk.PhotoImage(img, master=master)
    except Exception:
        pass
    try:
        photo = tk.PhotoImage(file=str(path), master=master)
    except (tk.TclError, OSError):
        return None
    w, h = photo.width(), photo.height()
    if w < 1 or h < 1:
        return None
    factor = step_zoom_factor(w, h, max_width, max_height)
    if factor > 1:
        photo = photo.subsample(factor, factor)
    return photo


def _photo_gif(
    master: tk.Misc,
    grid: list[list[tuple[int, int, int]]],
    *,
    trans: tuple[int, int, int] | None,
) -> tk.PhotoImage:
    """GIF in one shot. Treeview paints an empty PhotoImage+put() as a black square."""
    import tkinter as tk

    raw = gif89a(grid, trans=trans)
    return tk.PhotoImage(master=master, data=base64.b64encode(raw), format="gif")


def gif89a(
    grid: list[list[tuple[int, int, int]]],
    *,
    trans: tuple[int, int, int] | None = None,
) -> bytes:
    """GIF89a, 256-colour table. Index 0 is transparent when trans is set."""
    h = len(grid)
    w = len(grid[0])
    palette: list[tuple[int, int, int]] = []
    index: dict[tuple[int, int, int], int] = {}
    if trans is not None:
        palette.append(trans)
        index[trans] = 0
    pixels: list[int] = []
    for row in grid:
        for px in row:
            if px not in index:
                if len(palette) >= 256:
                    px = palette[0]
                else:
                    index[px] = len(palette)
                    palette.append(px)
            pixels.append(index[px])
    if not palette:
        palette.append((0, 0, 0))
    while len(palette) < 256:
        palette.append((0, 0, 0))
    lzw = _gif_lzw_uncompressed(pixels)
    out = bytearray()
    out += b"GIF89a"
    out += int(w).to_bytes(2, "little")
    out += int(h).to_bytes(2, "little")
    out += bytes([0xF7, 0x00, 0x00])
    for r, g, b in palette:
        out += bytes((r, g, b))
    if trans is not None:
        out += bytes([0x21, 0xF9, 0x04, 0x01, 0x00, 0x00, 0x00, 0x00])
    out += bytes([0x2C, 0x00, 0x00, 0x00, 0x00])
    out += int(w).to_bytes(2, "little")
    out += int(h).to_bytes(2, "little")
    out += bytes([0x00, 0x08])
    for i in range(0, len(lzw), 255):
        chunk = lzw[i : i + 255]
        out.append(len(chunk))
        out += chunk
    out += bytes([0x00, 0x3B])
    return bytes(out)


def _gif_lzw_uncompressed(indices: list[int]) -> bytes:
    """GIF LZW, min code size 8, CLEAR every 100 literals so width stays 9 bits."""
    clear, eoi = 256, 257
    width = 9
    codes: list[tuple[int, int]] = [(clear, width)]
    nlit = 0
    for idx in indices:
        codes.append((idx & 0xFF, width))
        nlit += 1
        if nlit >= 100:
            codes.append((clear, width))
            nlit = 0
    codes.append((eoi, width))
    acc = 0
    nbits = 0
    out = bytearray()
    for val, n in codes:
        acc |= (val & ((1 << n) - 1)) << nbits
        nbits += n
        while nbits >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            nbits -= 8
    if nbits:
        out.append(acc & 0xFF)
    return bytes(out)


def make_file_tree(
    parent: tk.Misc,
    *,
    dark: bool,
    font: object | None = None,
    rowheight: int = 28,
    style_name: str | None = None,
) -> tk.Widget:
    """Treeview that can show the cube PhotoImage (Listbox cannot)."""
    import tkinter as tk
    from tkinter import ttk

    style = ttk.Style(parent)
    name = style_name or ("KioskCad.Treeview" if dark else "GuiCad.Treeview")
    if dark:
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        kwargs: dict = {
            "background": KIOSK_BG,
            "fieldbackground": KIOSK_BG,
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
        }
        if font is not None:
            kwargs["font"] = font
        style.configure(name, **kwargs)
    try:
        style.layout(
            f"{name}.Item",
            [
                (
                    "Treeitem.padding",
                    {
                        "sticky": "nswe",
                        "children": [
                            ("Treeitem.image", {"side": "left", "sticky": ""}),
                            ("Treeitem.text", {"side": "left", "sticky": ""}),
                        ],
                    },
                )
            ],
        )
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
