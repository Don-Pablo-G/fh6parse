"""Machine travel vs programmed work: allowed work-offset origin box in G53 mm."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import tempfile

from .machtime import MachineProfile, to_mm


@dataclass
class WorkBBox:
    """Programmed work-coordinate extents (program units)."""

    min_x: float | None = None
    max_x: float | None = None
    min_y: float | None = None
    max_y: float | None = None
    min_z: float | None = None
    max_z: float | None = None

    def add(
        self,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
    ) -> None:
        if x is not None:
            self.min_x = x if self.min_x is None else min(self.min_x, x)
            self.max_x = x if self.max_x is None else max(self.max_x, x)
        if y is not None:
            self.min_y = y if self.min_y is None else min(self.min_y, y)
            self.max_y = y if self.max_y is None else max(self.max_y, y)
        if z is not None:
            self.min_z = z if self.min_z is None else min(self.min_z, z)
            self.max_z = z if self.max_z is None else max(self.max_z, z)

    def has_xy(self) -> bool:
        return None not in (self.min_x, self.max_x, self.min_y, self.max_y)

    def union(self, other: WorkBBox) -> WorkBBox:
        out = WorkBBox(
            self.min_x, self.max_x, self.min_y, self.max_y, self.min_z, self.max_z
        )
        out.add(other.min_x, other.min_y, other.min_z)
        out.add(other.max_x, other.max_y, other.max_z)
        return out


@dataclass(frozen=True)
class G54Window:
    """Where work offset origin may sit in G53 mm so the work AABB stays in travel."""

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float | None = None
    z_max: float | None = None
    fits: bool = True
    g54_inside: bool | None = None
    leftover_x: float = 0.0
    leftover_y: float = 0.0

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x_min + self.x_max) / 2.0, (self.y_min + self.y_max) / 2.0)

    @property
    def max_tool_dia_mm(self) -> float | None:
        """Largest Ø whose tool axis still fits if the work AABB is centred.

        Outside G41/G42: leftover on +X and −X is one diameter. Skip when the
        uncompensated box already exceeds travel.
        """
        if self.leftover_x < -1e-9 or self.leftover_y < -1e-9:
            return None
        return min(self.leftover_x, self.leftover_y)

    @property
    def corners(self) -> tuple[tuple[float, float], ...]:
        """SW, SE, NE, NW in G53 (Y up)."""
        return (
            (self.x_min, self.y_min),
            (self.x_max, self.y_min),
            (self.x_max, self.y_max),
            (self.x_min, self.y_max),
        )


def _ordered(a: float, b: float) -> tuple[float, float]:
    return (a, b) if a <= b else (b, a)


def g54_window(
    mill: MachineProfile,
    bbox: WorkBBox,
    *,
    inch: bool = False,
) -> G54Window | None:
    if not mill.has_xy_travel() or not bbox.has_xy():
        return None
    wx0 = to_mm(bbox.min_x or 0.0, inch=inch)
    wx1 = to_mm(bbox.max_x or 0.0, inch=inch)
    wy0 = to_mm(bbox.min_y or 0.0, inch=inch)
    wy1 = to_mm(bbox.max_y or 0.0, inch=inch)
    if wx0 > wx1:
        wx0, wx1 = wx1, wx0
    if wy0 > wy1:
        wy0, wy1 = wy1, wy0
    tx0, tx1 = _ordered(mill.x_min or 0.0, mill.x_max or 0.0)
    ty0, ty1 = _ordered(mill.y_min or 0.0, mill.y_max or 0.0)
    x_min = tx0 - wx0
    x_max = tx1 - wx1
    y_min = ty0 - wy0
    y_max = ty1 - wy1
    leftover_x = x_max - x_min
    leftover_y = y_max - y_min
    fits_x = leftover_x >= -1e-9
    fits_y = leftover_y >= -1e-9
    fits = fits_x and fits_y
    if not fits_x:
        x_min, x_max = x_max, x_min
    if not fits_y:
        y_min, y_max = y_max, y_min
    z_min = z_max = None
    if mill.has_z_travel() and bbox.min_z is not None and bbox.max_z is not None:
        wz0 = to_mm(bbox.min_z, inch=inch)
        wz1 = to_mm(bbox.max_z, inch=inch)
        if wz0 > wz1:
            wz0, wz1 = wz1, wz0
        tz0, tz1 = _ordered(mill.z_min or 0.0, mill.z_max or 0.0)
        length = mill.tool_length_mm
        z_min = tz0 - wz0 - length
        z_max = tz1 - wz1 - length
        if z_min > z_max:
            fits = False
            z_min, z_max = z_max, z_min
    inside: bool | None = None
    if mill.offset_x is not None and mill.offset_y is not None and fits:
        inside = (
            x_min - 1e-6 <= mill.offset_x <= x_max + 1e-6
            and y_min - 1e-6 <= mill.offset_y <= y_max + 1e-6
        )
        if inside and z_min is not None and mill.offset_z is not None:
            inside = z_min - 1e-6 <= mill.offset_z <= (z_max or z_min) + 1e-6
    return G54Window(
        x_min=x_min,
        x_max=x_max,
        y_min=y_min,
        y_max=y_max,
        z_min=z_min,
        z_max=z_max,
        fits=fits,
        g54_inside=inside,
        leftover_x=leftover_x,
        leftover_y=leftover_y,
    )


def fmt_mm(v: float) -> str:
    if abs(v - round(v)) < 0.05:
        return str(int(round(v)))
    return f"{v:.1f}"


def fmt_xy(x: float, y: float) -> str:
    return f"{fmt_mm(x)},{fmt_mm(y)}"


def _fmt_xy(x: float, y: float) -> str:
    return fmt_xy(x, y)


def render_g54_window_png(
    mill: MachineProfile,
    window: G54Window,
    *,
    dest: Path | None = None,
) -> Path | None:
    """Labeled XY rectangle of allowed work-offset origin. Needs Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    width, height = 512, 360
    margin = 56
    img = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    tx0, tx1 = _ordered(mill.x_min or 0.0, mill.x_max or 0.0)
    ty0, ty1 = _ordered(mill.y_min or 0.0, mill.y_max or 0.0)
    span_x = max(tx1 - tx0, abs(window.x_max - window.x_min), 1.0)
    span_y = max(ty1 - ty0, abs(window.y_max - window.y_min), 1.0)
    pad = 0.08
    gx0 = min(tx0, window.x_min) - span_x * pad
    gx1 = max(tx1, window.x_max) + span_x * pad
    gy0 = min(ty0, window.y_min) - span_y * pad
    gy1 = max(ty1, window.y_max) + span_y * pad
    if gx1 - gx0 < 1:
        gx1 = gx0 + 1
    if gy1 - gy0 < 1:
        gy1 = gy0 + 1

    def to_px(x: float, y: float) -> tuple[int, int]:
        px = margin + (x - gx0) / (gx1 - gx0) * (width - 2 * margin)
        py = height - margin - (y - gy0) / (gy1 - gy0) * (height - 2 * margin)
        return int(round(px)), int(round(py))

    draw.rectangle([to_px(tx0, ty1), to_px(tx1, ty0)], outline=80, width=1)
    w0 = to_px(window.x_min, window.y_max)
    w1 = to_px(window.x_max, window.y_min)
    draw.rectangle([w0, w1], outline=0, width=3)
    cx, cy = window.center
    pc = to_px(cx, cy)
    draw.line([(pc[0] - 6, pc[1]), (pc[0] + 6, pc[1])], fill=0, width=2)
    draw.line([(pc[0], pc[1] - 6), (pc[0], pc[1] + 6)], fill=0, width=2)
    labels = [
        (window.corners[0], (0, 12)),
        (window.corners[1], (-48, 12)),
        (window.corners[2], (-48, -14)),
        (window.corners[3], (0, -14)),
    ]
    for (x, y), (dx, dy) in labels:
        px, py = to_px(x, y)
        draw.text((px + dx, py + dy), _fmt_xy(x, y), fill=0, font=font)
    draw.text((pc[0] - 28, pc[1] + 10), _fmt_xy(cx, cy), fill=0, font=font)
    if mill.offset_x is not None and mill.offset_y is not None:
        gx, gy = to_px(mill.offset_x, mill.offset_y)
        r = 4
        draw.ellipse([gx - r, gy - r, gx + r, gy + r], outline=0, width=2)
    title = "Offset origin G53 mm"
    if not window.fits:
        title += "  TOO BIG"
    elif window.g54_inside is False:
        title += "  OFFSET OUT"
    draw.text((8, 6), title, fill=0, font=font)
    dia = window.max_tool_dia_mm
    if dia is not None:
        draw.text(
            (8, height - 18),
            f"Omax {fmt_mm(dia)} mm  centred G41/G42",
            fill=0,
            font=font,
        )
    path = dest or _cache_png_path(mill, window)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    img.save(tmp, format="PNG")
    tmp.replace(path)
    return path


def _cache_png_path(mill: MachineProfile, window: G54Window) -> Path:
    key = (
        f"{mill.id}|{mill.x_min}|{mill.x_max}|{mill.y_min}|{mill.y_max}|"
        f"{window.x_min}|{window.x_max}|{window.y_min}|{window.y_max}|"
        f"{mill.offset_x}|{mill.offset_y}|{window.fits}|{window.g54_inside}|"
        f"{window.leftover_x}|{window.leftover_y}|v3"
    )
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
    root = Path(tempfile.gettempdir()) / "fh6parse-models"
    return root / f"g54-{digest}.png"


def window_for_result(result: object) -> G54Window | None:
    mill = getattr(result, "machine", None)
    bbox = getattr(result, "work_bbox", None)
    if mill is None or bbox is None:
        return None
    inch = getattr(result, "units", "") == "inch"
    return g54_window(mill, bbox, inch=inch)


def g54_png_for_result(result: object) -> Path | None:
    mill = getattr(result, "machine", None)
    window = window_for_result(result)
    if mill is None or window is None:
        return None
    return render_g54_window_png(mill, window)


def append_g54_png(result: object, images: list[Path] | None = None) -> list[Path]:
    """STEP views first (isometric), then the labeled work-offset origin rectangle."""
    out = list(images or [])
    png = g54_png_for_result(result)
    if png is not None and png not in out:
        out.append(png)
    return out
