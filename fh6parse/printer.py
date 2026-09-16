"""Raw ESC/POS output for the 80 mm MUNBYN P047 / ITPP047."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .report import THERMAL_WIDTH, _wrap

ESC = b"\x1b"
GS = b"\x1d"
INIT = ESC + b"@"
FONT_A = ESC + b"!\x00"
# PC852 (Latin-2) — Polish shop comments on typical ESC/POS tables.
CODEPAGE_PC852 = ESC + b"t\x12"
# GS V 66 0: feed then full cut.
CUT = GS + b"V\x42\x00"
# Raster width for 80 mm (multiple of 8). ~72 mm printable at 203 dpi is 576.
RASTER_MAX_WIDTH = 512


def bitmap_to_escpos(width: int, height: int, packed: bytes) -> bytes:
    """GS v 0 raster: 1 = black dot, MSB is the leftmost pixel of each byte."""
    if width <= 0 or height <= 0 or width % 8:
        raise ValueError("raster width must be a positive multiple of 8")
    row_bytes = width // 8
    expected = row_bytes * height
    if len(packed) != expected:
        raise ValueError("raster payload size does not match width*height")
    xL, xH = row_bytes & 0xFF, (row_bytes >> 8) & 0xFF
    yL, yH = height & 0xFF, (height >> 8) & 0xFF
    return GS + b"v0\x00" + bytes((xL, xH, yL, yH)) + packed


def png_to_escpos(path: Path, *, max_width: int = RASTER_MAX_WIDTH) -> bytes:
    from PIL import Image

    image = Image.open(path)
    if image.mode not in ("1", "L"):
        image = image.convert("L")
    if image.width > max_width:
        height = max(1, round(image.height * max_width / image.width))
        image = image.resize((max_width, height), Image.Resampling.LANCZOS)
    pad = (8 - (image.width % 8)) % 8
    if pad:
        canvas = Image.new("L", (image.width + pad, image.height), 255)
        canvas.paste(image, (0, 0))
        image = canvas
    bw = image.convert("1", dither=Image.Dither.NONE)
    width, height = bw.size
    pixels = bw.load()
    packed = bytearray()
    for y in range(height):
        for x0 in range(0, width, 8):
            byte = 0
            for bit in range(8):
                if pixels[x0 + bit, y] == 0:
                    byte |= 0x80 >> bit
            packed.append(byte)
    return bitmap_to_escpos(width, height, bytes(packed))


def encode_ticket(text: str, rasters: list[bytes] | None = None) -> bytes:
    """Initialize printer, optional bitmaps at the top, 48-col text, feed, cut."""
    lines: list[bytes] = []
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for raw in normalized.split("\n"):
        wrapped = _wrap(raw, THERMAL_WIDTH) if len(raw) > THERMAL_WIDTH else [raw]
        for part in wrapped:
            lines.append(part.encode("cp852", "replace"))
    body = b"\r\n".join(lines)
    if not body.endswith(b"\r\n"):
        body += b"\r\n"
    pictures = b""
    for blob in rasters or []:
        if blob:
            pictures += blob + b"\n"
    return INIT + FONT_A + CODEPAGE_PC852 + pictures + body + b"\n\n\n" + CUT


def print_ticket(
    text: str,
    *,
    queue: str = "",
    device: str = "/dev/usb/lp0",
    image_paths: list[Path] | None = None,
) -> str:
    """Send a ticket. USB device first; CUPS only if that node fails.

    Returns a short route label. Raises on total failure.
    """
    rasters: list[bytes] = []
    for path in image_paths or []:
        try:
            rasters.append(png_to_escpos(path))
        except Exception:
            continue
    data = encode_ticket(text, rasters=rasters)
    errors: list[str] = []

    node = Path(device) if device else None
    if node is not None:
        try:
            if node.exists():
                with node.open("wb") as fh:
                    fh.write(data)
                    fh.flush()
                return f"device:{node}"
            errors.append(f"missing {node}")
        except OSError as exc:
            errors.append(str(exc))

    lp = shutil.which("lp")
    if lp and queue:
        try:
            proc = subprocess.run(
                [lp, "-d", queue, "-o", "raw"],
                input=data,
                check=False,
                capture_output=True,
                timeout=30,
            )
            if proc.returncode == 0:
                return f"lp:{queue}"
            err = (proc.stderr or b"").decode("utf-8", "replace").strip()
            errors.append(err or f"lp -d {queue} exit {proc.returncode}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(str(exc))

    detail = "; ".join(errors) if errors else "no printer route"
    raise RuntimeError(f"printer failed: {detail}")
