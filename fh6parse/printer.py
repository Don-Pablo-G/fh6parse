"""Raw ESC/POS output for the 80 mm MUNBYN P047 / ITPP047."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
import select
import shutil
import subprocess
import time
from pathlib import Path

from .report import THERMAL_WIDTH, _wrap

ESC = b"\x1b"
GS = b"\x1d"
DLE = b"\x10"
# DLE EOT n — real-time status (not printed). n=2 offline, 3 error, 4 paper.
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


@dataclass(frozen=True)
class PrinterStatus:
    """P047 paper / cover / cutter from DLE EOT. queried=False means allow print."""

    queried: bool = False
    cover_open: bool = False
    paper_out: bool = False
    cutter: bool = False
    error: bool = False

    @property
    def blocked(self) -> bool:
        return self.queried and (
            self.cover_open or self.paper_out or self.cutter or self.error
        )


def printer_block_key(status: PrinterStatus) -> str | None:
    """i18n key when FULL/MIN must not fire. None = send the ticket."""
    if not status.blocked:
        return None
    if status.cover_open:
        return "print_cover"
    if status.paper_out:
        return "print_paper"
    if status.cutter:
        return "print_cutter"
    if status.error:
        return "print_error"
    return None


def _valid_dle(byte: int) -> bool:
    """Epson real-time status: bit0=0, bit1=1, bit4=1, bit7=0."""
    return (byte & 0b10010011) == 0b00010010


def decode_printer_status(
    offline: int | None,
    *,
    error: int | None = None,
    paper: int | None = None,
) -> PrinterStatus:
    if offline is None or not _valid_dle(offline):
        return PrinterStatus()
    cover_open = bool(offline & 0x04)
    paper_out = bool(offline & 0x20)
    err_flag = bool(offline & 0x40)
    cutter = False
    error_now = err_flag
    if error is not None and _valid_dle(error):
        cutter = bool(error & 0x08)
        # bit2 mechanical, bit5 unrecoverable, bit6 auto-recoverable
        error_now = bool(error & 0x64)
        if not cutter and not error_now:
            error_now = err_flag
    if paper is not None and _valid_dle(paper) and (paper & 0x60):
        paper_out = True
    return PrinterStatus(
        queried=True,
        cover_open=cover_open,
        paper_out=paper_out,
        cutter=cutter,
        error=error_now,
    )


def _drain(fd: int) -> None:
    while True:
        try:
            chunk = os.read(fd, 64)
            if not chunk:
                return
        except (BlockingIOError, OSError):
            return


def _wait_readable(fd: int, timeout_s: float) -> bool:
    if timeout_s <= 0:
        return False
    if os.name == "nt":
        time.sleep(min(0.02, timeout_s))
        return True
    try:
        ready, _, _ = select.select([fd], [], [], timeout_s)
        return bool(ready)
    except (OSError, ValueError, TypeError):
        time.sleep(min(0.02, timeout_s))
        return True


def _first_dle_status(data: bytes) -> int | None:
    for byte in data:
        if _valid_dle(byte):
            return byte
    return None


def _dle_eot_once(fd: int, n: int, timeout_s: float) -> int | None:
    _drain(fd)
    try:
        os.write(fd, DLE + b"\x04" + bytes((n,)))
    except OSError:
        return None
    deadline = time.monotonic() + timeout_s
    buf = b""
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if not _wait_readable(fd, remaining):
            break
        try:
            chunk = os.read(fd, 16)
        except BlockingIOError:
            continue
        except OSError:
            return None
        if not chunk:
            continue
        buf += chunk
        found = _first_dle_status(buf)
        if found is not None:
            return found
    return _first_dle_status(buf)


def _collect_status(transact: Callable[[int], int | None]) -> PrinterStatus:
    offline = transact(2)
    error = None
    paper = None
    if offline is not None and _valid_dle(offline):
        if offline & 0x40:
            error = transact(3)
        paper = transact(4)
    return decode_printer_status(offline, error=error, paper=paper)


def query_printer_status(
    device: str = "",
    *,
    timeout_s: float = 0.2,
    transact: Callable[[int], int | None] | None = None,
) -> PrinterStatus:
    """Read paper/cover/cutter. No reply or a bad byte → not blocked (print anyway)."""
    if transact is not None:
        return _collect_status(transact)
    node = Path(device) if device else None
    if node is None or not device or not node.exists():
        return PrinterStatus()
    try:
        fd = os.open(str(node), os.O_RDWR | os.O_NONBLOCK)
    except OSError:
        return PrinterStatus()
    try:
        return _collect_status(lambda n: _dle_eot_once(fd, n, timeout_s))
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


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
