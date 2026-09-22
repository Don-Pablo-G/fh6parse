"""Programmed-motion time: G0/G1/G2/G3, F#n, canned cycles, and optional G53 ATC.

Approx only: no accel. Per-mill ATC + work-offset tables mix work and G53 in millimetres.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re

# Conservative mill defaults. Overridden by [machine.*] in the kiosk ini.
RAPID_MM_PER_MIN = 20000.0
ROTARY_DEG_PER_MIN = 5400.0  # 90 deg/s B/C


Pose5 = tuple[float | None, float | None, float | None, float | None, float | None]


@dataclass(frozen=True)
class MachineProfile:
    """Shop mill used for programmed-time estimates."""

    id: str = "default"
    name: str = "Default mill"
    rapid_mm_min: float = RAPID_MM_PER_MIN
    rotary_deg_min: float = ROTARY_DEG_PER_MIN
    tool_change_s: float = 0.0
    atc_x: float | None = None
    atc_y: float | None = None
    atc_z: float | None = None
    atc_b: float | None = None
    atc_c: float | None = None
    offset_x: float | None = None
    offset_y: float | None = None
    offset_z: float | None = None
    offset_b: float | None = None
    offset_c: float | None = None
    tool_length_mm: float = 0.0
    x_min: float | None = None
    x_max: float | None = None
    y_min: float | None = None
    y_max: float | None = None
    z_min: float | None = None
    z_max: float | None = None
    mrzp_x: float | None = None
    mrzp_y: float | None = None
    mrzp_z: float | None = None
    max_rpm: float | None = None

    def rapid_m_min_label(self) -> str:
        return f"{self.rapid_mm_min / 1000.0:.0f} m/min"

    def tool_change_label(self) -> str:
        s = self.tool_change_s
        if abs(s - round(s)) < 1e-6:
            return f"{int(round(s))} s"
        return f"{s:g} s"

    def has_g53_frame(self) -> bool:
        """True when this mill has its own ATC and typical work offset in G53 mm."""
        return None not in (
            self.atc_x,
            self.atc_y,
            self.atc_z,
            self.offset_x,
            self.offset_y,
            self.offset_z,
        )

    def atc_pose(self) -> tuple[float, float, float, float, float]:
        return (
            float(self.atc_x or 0.0),
            float(self.atc_y or 0.0),
            float(self.atc_z or 0.0),
            0.0 if self.atc_b is None else self.atc_b,
            0.0 if self.atc_c is None else self.atc_c,
        )

    def has_xy_travel(self) -> bool:
        return None not in (self.x_min, self.x_max, self.y_min, self.y_max)

    def has_z_travel(self) -> bool:
        return None not in (self.z_min, self.z_max)

    def has_mrzp(self) -> bool:
        """True when Haas 255/256/257 (machine rotary zero point) are all set."""
        return None not in (self.mrzp_x, self.mrzp_y, self.mrzp_z)


DEFAULT_MACHINE = MachineProfile()
# Haas G73 chip-break retract (user: 0.2 mm, not Setting 22 0.5 mm).
G73_PULLBACK_MM = 0.2
# Haas Setting 22 default 0.02" ≈ 0.5 mm — G83 re-approach above last peck.
G83_CLEARANCE_MM = 0.5
# Haas G84/G74 J retract multiple when J is omitted.
G84_RETRACT_MULT = 1.0

HASH_ASSIGN_RE = re.compile(
    r"#(\d+)\s*=\s*([+\-]?(?:\d+\.?\d*|\.\d+))", re.IGNORECASE
)
HASH_WORD_RE = re.compile(r"([A-Za-z])\s*#(\d+)\b", re.IGNORECASE)

TIME_INCOMPLETE_WARN = "cut time incomplete (missing F or S)"


def format_machine_time(seconds: float | None, *, incomplete: bool = False) -> str:
    if seconds is None:
        return "n/a"
    s = max(0, int(round(seconds)))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        text = f"{h}:{m:02d}:{sec:02d}"
    else:
        text = f"{m}:{sec:02d}"
    if incomplete:
        text += "+"
    return text


def rapid_per_min(*, inch: bool, profile: MachineProfile | None = None) -> float:
    rate = (profile or DEFAULT_MACHINE).rapid_mm_min
    if rate <= 0:
        rate = RAPID_MM_PER_MIN
    if inch:
        return rate / 25.4
    return rate


def feed_per_min(
    f: float | None, *, per_rev: bool, rpm: float | None
) -> float | None:
    if f is None or f <= 0:
        return None
    if per_rev:
        if rpm is None or rpm <= 0:
            return None
        return f * rpm
    return f


def seconds_for_length(
    length: float,
    feed: float | None,
    *,
    rapid: bool,
    inch: bool,
    profile: MachineProfile | None = None,
) -> float | None:
    if length <= 1e-12:
        return 0.0
    if rapid:
        return 60.0 * length / rapid_per_min(inch=inch, profile=profile)
    if feed is None or feed <= 1e-12:
        return None
    return 60.0 * length / feed


def seconds_for_rotary(
    deg: float,
    *,
    rapid: bool,
    feed: float | None,
    profile: MachineProfile | None = None,
) -> float | None:
    length = abs(deg)
    if length <= 1e-12:
        return 0.0
    if rapid:
        rate = (profile or DEFAULT_MACHINE).rotary_deg_min
        if rate <= 0:
            rate = ROTARY_DEG_PER_MIN
        return 60.0 * length / rate
    if feed is None or feed <= 1e-12:
        return None
    return 60.0 * length / feed


def axis_delta(
    prev: float | None, word: float | None, *, incremental: bool
) -> tuple[float | None, float]:
    """Return (new_position, signed_delta). Unknown start: set position, delta 0."""
    if word is None:
        return prev, 0.0
    if incremental:
        if prev is None:
            return word, 0.0
        return prev + word, word
    if prev is None:
        return word, 0.0
    return word, word - prev


def to_mm(value: float, *, inch: bool) -> float:
    return value * 25.4 if inch else value


def work_to_g53(
    wx: float | None,
    wy: float | None,
    wz: float | None,
    wb: float | None,
    wc: float | None,
    mill: MachineProfile,
    *,
    inch: bool,
) -> Pose5:
    """Work coordinates → G53 mm using this mill's work offset and tool length."""
    if not mill.has_g53_frame():
        return (None, None, None, None, None)
    off_b = 0.0 if mill.offset_b is None else mill.offset_b
    off_c = 0.0 if mill.offset_c is None else mill.offset_c

    def lin(work: float | None, origin: float | None) -> float | None:
        if work is None or origin is None:
            return None
        return origin + to_mm(work, inch=inch)

    mz = lin(wz, mill.offset_z)
    if mz is not None:
        mz = mz + mill.tool_length_mm
    return (
        lin(wx, mill.offset_x),
        lin(wy, mill.offset_y),
        mz,
        lin(wb, off_b),
        lin(wc, off_c),
    )


def merge_pose(prev: Pose5, target: Pose5) -> Pose5:
    return tuple(
        t if t is not None else p for t, p in zip(target, prev)
    )  # type: ignore[return-value]


def pose_linear_delta(prev: Pose5, new: Pose5) -> float:
    total = 0.0
    for i in range(3):
        a, b = prev[i], new[i]
        if a is None or b is None:
            continue
        total += (b - a) ** 2
    return math.sqrt(total)


def pose_rotary_delta(prev: Pose5, new: Pose5) -> float:
    db = 0.0
    dc = 0.0
    if prev[3] is not None and new[3] is not None:
        db = new[3] - prev[3]
    if prev[4] is not None and new[4] is not None:
        dc = new[4] - prev[4]
    return math.hypot(db, dc)


def rapid_seconds_mm(
    length: float, mill: MachineProfile | None = None
) -> float:
    timed = seconds_for_length(
        length, None, rapid=True, inch=False, profile=mill
    )
    return 0.0 if timed is None else timed


def rapid_z_then_xy(
    prev: Pose5,
    dest: tuple[float, float, float, float, float],
    mill: MachineProfile,
) -> float:
    """Tool-change path: Z retract, then XY and B/C, at mill rapids (mm)."""
    px, py, pz, pb, pc = prev
    dx, dy, dz, db, dc = dest
    z_move = 0.0 if pz is None else abs(dz - pz)
    x_move = 0.0 if px is None else dx - px
    y_move = 0.0 if py is None else dy - py
    b_move = 0.0 if pb is None else db - pb
    c_move = 0.0 if pc is None else dc - pc
    rot = seconds_for_rotary(
        math.hypot(b_move, c_move), rapid=True, feed=None, profile=mill
    )
    return (
        rapid_seconds_mm(z_move, mill)
        + rapid_seconds_mm(math.hypot(x_move, y_move), mill)
        + (0.0 if rot is None else rot)
    )


def arc_xy_length(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    r: float | None,
    i: float | None,
    j: float | None,
    clockwise: bool,
) -> float:
    """Planar G2/G3 length. Negative R is the long way (>180°)."""
    dx = x1 - x0
    dy = y1 - y0
    chord = math.hypot(dx, dy)
    if r is not None:
        if chord < 1e-9:
            return abs(2.0 * math.pi * r)
        rabs = abs(r)
        half = chord / 2.0
        if rabs < half:
            rabs = half
        # sweep of the shorter arc
        sweep = 2.0 * math.asin(min(1.0, half / rabs))
        if r < 0:
            sweep = 2.0 * math.pi - sweep
        return rabs * sweep
    if i is None and j is None:
        return chord
    cx = x0 + (i or 0.0)
    cy = y0 + (j or 0.0)
    rabs = math.hypot(x0 - cx, y0 - cy)
    if rabs < 1e-9:
        return chord
    a0 = math.atan2(y0 - cy, x0 - cx)
    a1 = math.atan2(y1 - cy, x1 - cx)
    sweep = a1 - a0
    if clockwise:
        if sweep >= 0:
            sweep -= 2.0 * math.pi
    else:
        if sweep <= 0:
            sweep += 2.0 * math.pi
    if abs(sweep) < 1e-12 and chord < 1e-9:
        sweep = -2.0 * math.pi if clockwise else 2.0 * math.pi
    return abs(sweep) * rabs


def helical_length(xy_arc: float, dz: float) -> float:
    return math.hypot(xy_arc, dz)


def _unit_mm(mm: float, *, inch: bool) -> float:
    return mm / 25.4 if inch else mm


def peck_depths(
    depth: float,
    *,
    q: float | None,
    i: float | None,
    j: float | None,
    k: float | None,
) -> list[float]:
    """Haas G73/G83 pecks: Q equal, or I/J/K reducing (do not mix Q with IJK)."""
    if depth <= 1e-12:
        return []
    if i is not None and i > 0:
        reduce = j if j is not None and j > 0 else 0.0
        min_p = k if k is not None and k > 0 else i
        pecks: list[float] = []
        remaining = depth
        current = i
        while remaining > 1e-9 and len(pecks) < 10_000:
            this = min(max(current, min_p) if reduce else current, remaining)
            this = min(max(this, 1e-9), remaining)
            pecks.append(this)
            remaining -= this
            current = current - reduce if reduce else current
            if reduce:
                current = max(min_p, current)
        return pecks
    peck = q if q is not None and q > 0 else depth
    pecks = []
    remaining = depth
    while remaining > 1e-9 and len(pecks) < 10_000:
        this = min(peck, remaining)
        pecks.append(this)
        remaining -= this
    return pecks


def canned_cycle_seconds(
    code: int,
    *,
    z_initial: float | None,
    r: float,
    z: float,
    q: float | None,
    k: float | None,
    feed: float | None,
    g98: bool,
    inch: bool,
    i: float | None = None,
    j: float | None = None,
    p: float | None = None,
    retract_mult: float | None = None,
    profile: MachineProfile | None = None,
) -> float | None:
    """Z motion of a Haas mill Group 09 cycle after the XY rapid to the hole.

    G73 chip-break retract is 0.2 mm (not Setting 22). G83 retracts to R, then
    rapids back to last peck + Setting 22 (0.5 mm). G84/G74 leave at J×feed
    (default J=1.0). P dwell is seconds (Haas).
    """
    depth = abs(z - r)

    def t_feed(dist: float, *, rate: float | None = None) -> float | None:
        return seconds_for_length(
            dist,
            rate if rate is not None else feed,
            rapid=False,
            inch=inch,
            profile=profile,
        )

    def t_rapid(dist: float) -> float:
        return seconds_for_length(
            dist, None, rapid=True, inch=inch, profile=profile
        ) or 0.0

    total = 0.0
    if z_initial is not None:
        total += t_rapid(abs(z_initial - r))

    dwell = p if p is not None and p > 0 else 0.0
    j_out = retract_mult if retract_mult is not None and retract_mult > 0 else G84_RETRACT_MULT
    chip = _unit_mm(G73_PULLBACK_MM, inch=inch)
    clear = _unit_mm(G83_CLEARANCE_MM, inch=inch)

    # Haas NGC mill: 73, 74, 76, 77, 81–86, 89. Fanuc extras 87/88 mapped.
    if code in {81}:
        one = t_feed(depth)
        if one is None:
            return None
        total += one
        total += _retract_after_bottom(z, r, z_initial, g98, t_rapid)
    elif code in {82}:
        one = t_feed(depth)
        if one is None:
            return None
        total += one + dwell
        total += _retract_after_bottom(z, r, z_initial, g98, t_rapid)
    elif code == 73:
        pecks = peck_depths(depth, q=q, i=i, j=j, k=k if i is not None else None)
        k_clear = k if i is None and q is not None and k is not None and k > 0 else None
        body = _g73_seconds(
            pecks,
            feed,
            inch=inch,
            chip=chip,
            k_clear=k_clear,
            clear=clear,
            profile=profile,
        )
        if body is None:
            return None
        total += body + dwell
        total += _retract_after_bottom(z, r, z_initial, g98, t_rapid)
    elif code == 83:
        pecks = peck_depths(depth, q=q, i=i, j=j, k=k)
        body = _g83_seconds(pecks, feed, inch=inch, clear=clear, profile=profile)
        if body is None:
            return None
        total += body + dwell
        total += _retract_after_bottom(z, r, z_initial, g98, t_rapid)
    elif code in {74, 84}:
        out_rate = feed * j_out if feed is not None else None
        pecks = peck_depths(depth, q=q, i=None, j=None, k=None) if q else [depth]
        body = _g84_seconds(
            pecks, feed, out_rate, inch=inch, depth=depth, clear=clear, profile=profile
        )
        if body is None:
            return None
        total += body
        if g98 and z_initial is not None:
            total += t_rapid(abs(z_initial - r))
    elif code in {85, 89}:
        one = t_feed(depth)
        if one is None:
            return None
        total += one
        if code == 89:
            total += dwell
        out = t_feed(depth)
        if out is None:
            return None
        total += out
        if g98 and z_initial is not None:
            total += t_rapid(abs(z_initial - r))
    elif code in {86, 88}:
        one = t_feed(depth)
        if one is None:
            return None
        total += one
        if code == 88:
            total += dwell
        total += _retract_after_bottom(z, r, z_initial, g98, t_rapid)
    elif code in {76, 77, 87}:
        # Fine / back bore: feed the hole, rapid clear-out (shift ignored).
        one = t_feed(depth)
        if one is None:
            return None
        total += one + dwell
        if code in {77, 87}:
            total += t_rapid(depth)
        total += _retract_after_bottom(z, r, z_initial, g98, t_rapid)
    else:
        one = t_feed(depth)
        if one is None:
            return None
        total += one
        total += _retract_after_bottom(z, r, z_initial, g98, t_rapid)
    return total


def _retract_after_bottom(
    z: float,
    r: float,
    z_initial: float | None,
    g98: bool,
    t_rapid,
) -> float:
    if g98 and z_initial is not None:
        return t_rapid(abs(z - z_initial))
    return t_rapid(abs(z - r))


def _g73_seconds(
    pecks: list[float],
    feed: float | None,
    *,
    inch: bool,
    chip: float,
    k_clear: float | None,
    clear: float,
    profile: MachineProfile | None = None,
) -> float | None:
    """Chip-break pecks; optional Haas K+Q full return to R every K of cut."""
    total = 0.0
    cut = 0.0
    acc = 0.0
    depth = sum(pecks)
    for this in pecks:
        t = seconds_for_length(this, feed, rapid=False, inch=inch, profile=profile)
        if t is None:
            return None
        total += t
        cut += this
        acc += this
        if cut + 1e-9 >= depth:
            break
        full_r = k_clear is not None and acc + 1e-9 >= k_clear
        if full_r:
            total += seconds_for_length(cut, None, rapid=True, inch=inch, profile=profile) or 0.0
            total += seconds_for_length(
                max(0.0, cut - clear), None, rapid=True, inch=inch, profile=profile
            ) or 0.0
            acc = 0.0
        else:
            total += seconds_for_length(chip, None, rapid=True, inch=inch, profile=profile) or 0.0
            total += seconds_for_length(chip, None, rapid=True, inch=inch, profile=profile) or 0.0
    return total


def _g83_seconds(
    pecks: list[float],
    feed: float | None,
    *,
    inch: bool,
    clear: float,
    profile: MachineProfile | None = None,
) -> float | None:
    """Haas G83: peck, rapid to R, rapid to last peck + Setting 22, feed next."""
    total = 0.0
    cut = 0.0
    depth = sum(pecks)
    for n, this in enumerate(pecks):
        extra = min(clear, cut) if n else 0.0
        t = seconds_for_length(this + extra, feed, rapid=False, inch=inch, profile=profile)
        if t is None:
            return None
        total += t
        cut += this
        if cut + 1e-9 >= depth:
            break
        total += seconds_for_length(cut, None, rapid=True, inch=inch, profile=profile) or 0.0
        total += seconds_for_length(
            max(0.0, cut - clear), None, rapid=True, inch=inch, profile=profile
        ) or 0.0
    return total


def _g84_seconds(
    pecks: list[float],
    feed_in: float | None,
    feed_out: float | None,
    *,
    inch: bool,
    depth: float,
    clear: float,
    profile: MachineProfile | None = None,
) -> float | None:
    """Tap in at F, out at J×F (default 1.0). Q pecks retract to R at out feed."""
    if len(pecks) <= 1:
        inn = seconds_for_length(depth, feed_in, rapid=False, inch=inch, profile=profile)
        out = seconds_for_length(depth, feed_out, rapid=False, inch=inch, profile=profile)
        if inn is None or out is None:
            return None
        return inn + out
    total = 0.0
    cut = 0.0
    for n, this in enumerate(pecks):
        extra = min(clear, cut) if n else 0.0
        inn = seconds_for_length(
            this + extra, feed_in, rapid=False, inch=inch, profile=profile
        )
        if inn is None:
            return None
        total += inn
        cut += this
        if cut + 1e-9 >= depth:
            out = seconds_for_length(cut, feed_out, rapid=False, inch=inch, profile=profile)
            if out is None:
                return None
            total += out
            break
        out = seconds_for_length(cut, feed_out, rapid=False, inch=inch, profile=profile)
        inn2 = seconds_for_length(
            max(0.0, cut - clear), feed_in, rapid=False, inch=inch, profile=profile
        )
        if out is None or inn2 is None:
            return None
        total += out + inn2
    return total


def apply_hash_assigns(table: dict[int, float], assigns: list[tuple[int, float]]) -> None:
    for n, value in assigns:
        table[n] = value


def resolve_hash_letter(
    letter: str, words: list[tuple[str, int]], table: dict[int, float]
) -> float | None:
    for L, n in words:
        if L == letter and n in table:
            return table[n]
    return None
