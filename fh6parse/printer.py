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


def encode_ticket(text: str) -> bytes:
    """Initialize printer, send 48-col text, feed, and cut."""
    lines: list[bytes] = []
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for raw in normalized.split("\n"):
        wrapped = _wrap(raw, THERMAL_WIDTH) if len(raw) > THERMAL_WIDTH else [raw]
        for part in wrapped:
            lines.append(part.encode("cp852", "replace"))
    body = b"\r\n".join(lines)
    if not body.endswith(b"\r\n"):
        body += b"\r\n"
    return INIT + FONT_A + CODEPAGE_PC852 + body + b"\n\n\n" + CUT


def print_ticket(
    text: str,
    *,
    queue: str = "munbyn",
    device: str = "/dev/usb/lp0",
) -> str:
    """Send a ticket. Returns a short route label. Raises on total failure."""
    data = encode_ticket(text)
    errors: list[str] = []

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

    if lp:
        try:
            proc = subprocess.run(
                [lp, "-o", "raw"],
                input=data,
                check=False,
                capture_output=True,
                timeout=30,
            )
            if proc.returncode == 0:
                return "lp:default"
            err = (proc.stderr or b"").decode("utf-8", "replace").strip()
            errors.append(err or f"lp exit {proc.returncode}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(str(exc))

    path = Path(device) if device else None
    if path is not None:
        try:
            if path.exists():
                with path.open("wb") as fh:
                    fh.write(data)
                    fh.flush()
                return f"device:{path}"
            errors.append(f"missing {path}")
        except OSError as exc:
            errors.append(str(exc))

    detail = "; ".join(errors) if errors else "no printer route"
    raise RuntimeError(f"printer failed: {detail}")
