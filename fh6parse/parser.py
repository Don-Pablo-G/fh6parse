"""Fanuc/Haas G-code parser: tools (Txx M6) and lowest work-coordinate Z."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import math
import re

from .machtime import (
    DEFAULT_MACHINE,
    HASH_ASSIGN_RE,
    HASH_WORD_RE,
    MachineProfile,
    apply_hash_assigns,
    arc_xy_length,
    axis_delta,
    canned_cycle_seconds,
    feed_per_min,
    helical_length,
    resolve_hash_letter,
    seconds_for_length,
    seconds_for_rotary,
)


COMMENT_RE = re.compile(r"\([^()]*\)")
WORD_RE = re.compile(r"([A-Za-z])\s*([+\-]?(?:\d+\.?\d*|\.\d+))", re.IGNORECASE)
GOTO_RE = re.compile(r"GOTO\s*(\d+)", re.IGNORECASE)
N_LABEL_RE = re.compile(r"^N(\d+)\b", re.IGNORECASE)
O_WORD_RE = re.compile(r"\bO(\d+)\b", re.IGNORECASE)
# Header ops: "(N10 - OP1)", "(N60 - KONTROLA OSI ...)" — N number may be any value.
HEADER_OP_RE = re.compile(r"N(\d+)\s*[-–]\s*(.*)$", re.IGNORECASE)

CYCLE_START = {73, 74, 76, 77, 81, 82, 83, 84, 85, 86, 87, 88, 89}
G95_NEXT_WARN = "G95 still active (feed per rev); set G94"
G95_END_WARN = "G95 still active at M30; set G94"


def _parse_number(raw: str) -> float:
    return float(raw)


def extract_comments(text: str) -> list[str]:
    return [m.group(0)[1:-1].strip() for m in COMMENT_RE.finditer(text)]


def strip_comments(text: str) -> str:
    return COMMENT_RE.sub(" ", text)


@dataclass
class Word:
    letter: str
    value: float
    raw: str


@dataclass
class Line:
    number: int  # 1-based
    raw: str
    comments: list[str]
    code: str
    words: list[Word]
    n_label: int | None = None
    goto_target: int | None = None
    hash_assigns: list[tuple[int, float]] = field(default_factory=list)
    hash_words: list[tuple[str, int]] = field(default_factory=list)

    def letters(self, letter: str) -> list[Word]:
        L = letter.upper()
        return [w for w in self.words if w.letter == L]

    def first(self, letter: str) -> Word | None:
        found = self.letters(letter)
        return found[0] if found else None

    def g_ints(self) -> list[int]:
        out: list[int] = []
        for w in self.letters("G"):
            if abs(w.value - round(w.value)) < 1e-9:
                out.append(int(round(w.value)))
        return out

    def m_ints(self) -> list[int]:
        out: list[int] = []
        for w in self.letters("M"):
            if abs(w.value - round(w.value)) < 1e-9:
                out.append(int(round(w.value)))
        return out

    def has_g(self, *codes: int) -> bool:
        gs = set(self.g_ints())
        return any(c in gs for c in codes)

    def has_m(self, *codes: int) -> bool:
        ms = set(self.m_ints())
        return any(c in ms for c in codes)


@dataclass
class ToolUsage:
    tool: int
    description: str
    line_start: int
    line_end: int = 0
    h_offset: int | None = None
    d_offset: int | None = None
    s_rpm: float | None = None
    b: float | None = None
    c: float | None = None
    subprogram: str = "main"
    subprogram_comment: str = ""
    min_z: float | None = None
    min_z_line: int | None = None
    g43_z: float | None = None
    cycle_r: float | None = None
    called_from_main: bool = False
    warnings: list[str] = field(default_factory=list)
    time_s: float = 0.0
    time_incomplete: bool = False

    def consider_z(self, z: float, line_no: int) -> None:
        if self.min_z is None or z < self.min_z:
            self.min_z = z
            self.min_z_line = line_no

    def add_time(self, seconds: float | None) -> None:
        if seconds is None:
            self.time_incomplete = True
            return
        self.time_s += seconds


@dataclass
class ToolSummary:
    tool: int
    descriptions: list[str]
    min_z: float | None
    min_z_line: int | None
    called: bool
    usages: list[ToolUsage]
    time_s: float = 0.0
    time_incomplete: bool = False


@dataclass
class Operation:
    """One selectable setup: tools that run if this path is taken until M30."""

    n: int | None
    title: str
    call: str
    executed_lines: set[int]
    summaries: list[ToolSummary]
    usages: list[ToolUsage]


@dataclass
class BangNote:
    """Parenthesis comment that contains '!' — programmer → operator."""

    line: int
    text: str


@dataclass
class ParseResult:
    path: str
    filename: str
    program_number: str
    program_title: str
    header_comments: list[str]
    bang_notes: list[BangNote]
    units: str
    usages: list[ToolUsage]
    called_summaries: list[ToolSummary]
    all_summaries: list[ToolSummary]
    operations: list[Operation]
    executed_lines: set[int]
    source_lines: list[str]
    machine: MachineProfile = field(default_factory=lambda: DEFAULT_MACHINE)


def _tokenize_line(raw: str, number: int) -> Line:
    comments = extract_comments(raw)
    code = strip_comments(raw)
    code = code.split(";", 1)[0]
    goto_target = None
    goto_match = GOTO_RE.search(code)
    if goto_match:
        goto_target = int(goto_match.group(1))
        code = GOTO_RE.sub(" ", code)

    words: list[Word] = []
    for m in WORD_RE.finditer(code):
        letter = m.group(1).upper()
        raw_val = m.group(2)
        try:
            value = _parse_number(raw_val)
        except ValueError:
            continue
        words.append(Word(letter=letter, value=value, raw=raw_val))

    hash_assigns: list[tuple[int, float]] = []
    for m in HASH_ASSIGN_RE.finditer(code):
        try:
            hash_assigns.append((int(m.group(1)), float(m.group(2))))
        except ValueError:
            continue
    hash_words: list[tuple[str, int]] = []
    for m in HASH_WORD_RE.finditer(code):
        hash_words.append((m.group(1).upper(), int(m.group(2))))

    n_label = None
    n_match = N_LABEL_RE.search(code.strip())
    if n_match:
        n_label = int(n_match.group(1))

    return Line(
        number=number,
        raw=raw.rstrip("\n\r"),
        comments=comments,
        code=code,
        words=words,
        n_label=n_label,
        goto_target=goto_target,
        hash_assigns=hash_assigns,
        hash_words=hash_words,
    )


def _is_pad_line(line: Line) -> bool:
    if not line.raw.strip() or line.raw.strip() == "%":
        return True
    if (
        set(line.m_ints()) <= {0, 1}
        and not ({w.letter for w in line.words} - {"M"})
        and not line.comments
    ):
        return True
    return False


def _is_tool_change(line: Line) -> bool:
    return bool(line.has_m(6) and line.first("T"))


def _last_comment(line: Line) -> str:
    for c in reversed(line.comments):
        if c:
            return c
    return ""


def _description_for(lines: list[Line], idx: int) -> str:
    parts: list[str] = []
    same = [c for c in lines[idx].comments if c]
    if same:
        parts.extend(same)
    else:
        for j in range(idx - 1, -1, -1):
            prev = lines[j]
            if _is_pad_line(prev):
                continue
            if prev.comments and not _is_tool_change(prev):
                comment = _last_comment(prev)
                if comment:
                    parts.append(comment)
            break
    for j in range(idx + 1, len(lines)):
        nxt = lines[j]
        if _is_pad_line(nxt):
            continue
        if nxt.comments and not _is_tool_change(nxt):
            comment = _last_comment(nxt)
            if comment and comment not in parts:
                parts.append(comment)
        break
    return " / ".join(parts)


def _collect_bang_notes(lines: list[Line]) -> list[BangNote]:
    notes: list[BangNote] = []
    seen: set[tuple[int, str]] = set()
    for line in lines:
        for c in line.comments:
            if "!" not in c:
                continue
            key = (line.number, c)
            if key in seen:
                continue
            seen.add(key)
            notes.append(BangNote(line=line.number, text=c))
    return notes


def _int_or_none(word: Word | None) -> int | None:
    if word is None:
        return None
    if abs(word.value - round(word.value)) < 1e-9:
        return int(round(word.value))
    return int(word.value)


def _build_n_index(lines: list[Line]) -> dict[int, int]:
    index: dict[int, int] = {}
    for i, line in enumerate(lines):
        if line.n_label is not None and line.n_label not in index:
            index[line.n_label] = i
    return index


def _execute(
    lines: list[Line],
    n_index: dict[int, int],
    *,
    p_overrides: dict[int, int] | None = None,
    start_at: int | None = None,
) -> set[int]:
    """Walk until M30/M02. M97/M98 call a sub; M99 returns. GOTO jumps.

    p_overrides maps 0-based line index -> P number for operator M97 P# selection.
    start_at, if set, begins at that 0-based index (declared op not reached by M97).
    """
    executed: set[int] = set()
    i = 0 if start_at is None else start_at
    stack: list[int] = []
    steps = 0
    max_steps = 2_000_000
    n = len(lines)
    overrides = p_overrides or {}

    while 0 <= i < n and steps < max_steps:
        steps += 1
        executed.add(i)
        line = lines[i]

        if line.goto_target is not None:
            target = n_index.get(line.goto_target)
            if target is not None:
                i = target
                continue
            i += 1
            continue

        if line.has_m(30, 2):
            break

        if line.has_m(99):
            if stack:
                i = stack.pop()
                continue
            break

        if line.has_m(97, 98):
            p_val: int | None = None
            if i in overrides:
                p_val = overrides[i]
            else:
                p = line.first("P")
                if p is not None:
                    p_val = int(round(p.value))
            if p_val is not None:
                target = n_index.get(p_val)
                if target is not None:
                    stack.append(i + 1)
                    i = target
                    continue

        i += 1

    return executed


def _declared_ops(header_comments: list[str]) -> list[tuple[int, str]]:
    """Ops advertised near the header, e.g. (N10 - OP1). N# may be any number."""
    seen: set[int] = set()
    ops: list[tuple[int, str]] = []
    for c in header_comments:
        m = HEADER_OP_RE.search(c.strip())
        if not m:
            continue
        n = int(m.group(1))
        title = (m.group(2) or "").strip() or f"N{n}"
        if n in seen:
            continue
        seen.add(n)
        ops.append((n, title))
    return ops


def _selector_m97_indices(
    lines: list[Line],
    n_index: dict[int, int],
    declared: set[int],
) -> list[int]:
    """M97/M98 in main whose P is a declared op. Do not enter subs; stop at M30."""
    if not declared:
        return []
    found: list[int] = []
    i = 0
    n = len(lines)
    steps = 0
    while 0 <= i < n and steps < 2_000_000:
        steps += 1
        line = lines[i]
        if line.goto_target is not None:
            target = n_index.get(line.goto_target)
            i = target if target is not None else i + 1
            continue
        if line.has_m(30, 2, 99):
            break
        if line.has_m(97, 98):
            p = line.first("P")
            if p is not None and int(round(p.value)) in declared:
                found.append(i)
            i += 1
            continue
        i += 1
    return found


def _usages_on_path(usages: list[ToolUsage], executed: set[int]) -> list[ToolUsage]:
    return [u for u in usages if (u.line_start - 1) in executed]


def _make_operation(
    usages: list[ToolUsage],
    executed: set[int],
    *,
    n: int | None,
    title: str,
    call: str,
) -> Operation:
    path_usages = _usages_on_path(usages, executed)
    return Operation(
        n=n,
        title=title,
        call=call,
        executed_lines=executed,
        summaries=_summarize(path_usages, called_only=False),
        usages=path_usages,
    )


def _current_n_context(lines: list[Line], idx: int) -> tuple[str, str]:
    for j in range(idx, -1, -1):
        if lines[j].n_label is not None:
            comment = lines[j].comments[0] if lines[j].comments else ""
            return f"N{lines[j].n_label}", comment
    return "main", ""


def _apply_line_to_usage(usage: ToolUsage, line: Line, cycle_active: bool) -> None:
    s_word = line.first("S")
    if s_word is not None and usage.s_rpm is None:
        usage.s_rpm = s_word.value

    b_word = line.first("B")
    if b_word is not None and usage.b is None:
        usage.b = b_word.value
    c_word = line.first("C")
    if c_word is not None and usage.c is None:
        usage.c = c_word.value

    if line.has_g(43):
        h_word = line.first("H")
        h = _int_or_none(h_word)
        if h is not None:
            usage.h_offset = h
            if h != usage.tool:
                msg = f"H{h} does not match T{usage.tool}"
                if msg not in usage.warnings:
                    usage.warnings.append(msg)
        z_word = line.first("Z")
        if z_word is not None:
            usage.g43_z = z_word.value

    d_word = line.first("D")
    d = _int_or_none(d_word)
    if d is not None:
        usage.d_offset = d
        if d != usage.tool:
            msg = f"D{d} does not match T{usage.tool}"
            if msg not in usage.warnings:
                usage.warnings.append(msg)

    r_word = line.first("R")
    if r_word is not None and (cycle_active or any(g in CYCLE_START for g in line.g_ints())):
        usage.cycle_r = r_word.value


def _feed_on_line(line: Line, hash_vars: dict[int, float]) -> float | None:
    w = line.first("F")
    if w is not None:
        return w.value
    return resolve_hash_letter("F", line.hash_words, hash_vars)


def parse_nc_text(
    text: str, path: str | Path = "", *, machine: MachineProfile | None = None
) -> ParseResult:
    mill = machine or DEFAULT_MACHINE
    path_obj = Path(path) if path else Path("")
    raw_lines = text.splitlines()
    lines = [_tokenize_line(raw, i + 1) for i, raw in enumerate(raw_lines)]

    program_number = ""
    program_title = ""
    header_comments: list[str] = []
    units = "unknown"
    first_tool_idx: int | None = None

    for i, line in enumerate(lines):
        o_match = O_WORD_RE.search(strip_comments(line.raw))
        if o_match and not program_number:
            program_number = f"O{o_match.group(1)}"
            if line.comments:
                program_title = line.comments[0]
        if line.has_g(21):
            units = "mm"
        elif line.has_g(20):
            units = "inch"
        if line.has_m(6) and line.first("T") is not None and first_tool_idx is None:
            first_tool_idx = i
        if first_tool_idx is None:
            for c in line.comments:
                if c and c not in header_comments:
                    if program_title and c == program_title:
                        continue
                    header_comments.append(c)

    n_index = _build_n_index(lines)
    executed = _execute(lines, n_index)

    usages: list[ToolUsage] = []
    current: ToolUsage | None = None

    incremental = False
    abs_x: float | None = None
    abs_y: float | None = None
    abs_z: float | None = None
    g53_x: float | None = None
    g53_y: float | None = None
    g53_z: float | None = None
    abs_b: float | None = None
    abs_c: float | None = None
    cycle_active = False
    cycle_z: float | None = None
    cycle_r: float | None = None
    cycle_q: float | None = None
    cycle_k: float | None = None
    cycle_i: float | None = None
    cycle_j: float | None = None
    cycle_p: float | None = None
    cycle_retract_j: float = 1.0
    cycle_code: int | None = None
    g98 = True
    feed_per_rev = False
    feed_val: float | None = None
    s_rpm: float | None = None
    motion = 0
    hash_vars: dict[int, float] = {}
    inch = units == "inch"

    for i, line in enumerate(lines):
        apply_hash_assigns(hash_vars, line.hash_assigns)
        f_now = _feed_on_line(line, hash_vars)
        if f_now is not None:
            feed_val = f_now
        s_now = line.first("S")
        if s_now is not None:
            s_rpm = s_now.value

        gs = line.g_ints()
        if 90 in gs:
            incremental = False
        if 91 in gs:
            incremental = True
        if 20 in gs:
            inch = True
        if 21 in gs:
            inch = False
        for g in gs:
            if g == 94:
                feed_per_rev = False
            elif g == 95:
                feed_per_rev = True
            elif g in (0, 1, 2, 3):
                motion = g
            elif g == 98:
                g98 = True
            elif g == 99:
                g98 = False

        g53 = line.has_g(53, 28)
        if 80 in gs:
            cycle_active = False
            cycle_z = None
            cycle_code = None
        starting_cycle = any(g in CYCLE_START for g in gs)
        if starting_cycle:
            cycle_active = True
            cycle_i = None
            cycle_j = None
            cycle_k = None
            cycle_q = None
            cycle_p = None
            cycle_retract_j = 1.0
            for g in gs:
                if g in CYCLE_START:
                    cycle_code = g
            r_word = line.first("R")
            if r_word is not None:
                cycle_r = r_word.value
            q_word = line.first("Q")
            if q_word is not None:
                cycle_q = q_word.value
            k_word = line.first("K")
            if k_word is not None:
                cycle_k = k_word.value
            i_word = line.first("I")
            if i_word is not None:
                cycle_i = i_word.value
            j_word = line.first("J")
            if j_word is not None:
                if cycle_code in {74, 84}:
                    cycle_retract_j = j_word.value
                else:
                    cycle_j = j_word.value
            p_word = line.first("P")
            if p_word is not None:
                cycle_p = p_word.value

        t_word = line.first("T")
        if t_word is not None and line.has_m(6):
            if current is not None:
                current.line_end = line.number - 1
            tool = int(round(t_word.value))
            sub, sub_c = _current_n_context(lines, i)
            desc = _description_for(lines, i)
            current = ToolUsage(
                tool=tool,
                description=desc,
                line_start=line.number,
                line_end=line.number,
                subprogram=sub,
                subprogram_comment=sub_c,
                called_from_main=i in executed,
            )
            if feed_per_rev:
                current.warnings.append(G95_NEXT_WARN)
            usages.append(current)
            if mill.tool_change_s > 0:
                current.add_time(mill.tool_change_s)
            cycle_active = False
            cycle_z = None
            cycle_code = None

        x_word = line.first("X")
        y_word = line.first("Y")
        z_word = line.first("Z")
        b_word = line.first("B")
        c_word = line.first("C")
        x_raw = x_word.value if x_word else None
        y_raw = y_word.value if y_word else None
        z_raw = z_word.value if z_word else None
        b_raw = b_word.value if b_word else None
        c_raw = c_word.value if c_word else None

        z_before = abs_z
        fpm = feed_per_min(feed_val, per_rev=feed_per_rev, rpm=s_rpm)
        timed: float | None = 0.0

        if g53:
            g53_x, dx = axis_delta(g53_x, x_raw, incremental=False)
            g53_y, dy = axis_delta(g53_y, y_raw, incremental=False)
            g53_z, dz = axis_delta(g53_z, z_raw, incremental=False)
            move = math.hypot(dx, dy, dz)
            timed = seconds_for_length(
                move, None, rapid=True, inch=inch, profile=mill
            )
        else:
            abs_x, dx = axis_delta(abs_x, x_raw, incremental=incremental)
            abs_y, dy = axis_delta(abs_y, y_raw, incremental=incremental)
            in_cycle = cycle_active and cycle_code is not None
            cycle_line = in_cycle and (
                starting_cycle
                or x_word is not None
                or y_word is not None
                or z_word is not None
            )
            if cycle_line:
                if z_raw is not None:
                    if incremental:
                        if z_before is not None:
                            cycle_z = z_before + z_raw
                    else:
                        cycle_z = z_raw
                xy = math.hypot(dx, dy)
                xy_t = seconds_for_length(
                    xy, None, rapid=True, inch=inch, profile=mill
                )
                z_t: float | None = 0.0
                if cycle_r is not None and cycle_z is not None:
                    z_t = canned_cycle_seconds(
                        cycle_code or 81,
                        z_initial=z_before,
                        r=cycle_r,
                        z=cycle_z,
                        q=cycle_q,
                        k=cycle_k,
                        feed=fpm,
                        g98=g98,
                        inch=inch,
                        i=cycle_i,
                        j=cycle_j,
                        p=cycle_p,
                        retract_mult=cycle_retract_j,
                        profile=mill,
                    )
                    if g98 and z_before is not None:
                        abs_z = z_before
                    else:
                        abs_z = cycle_r
                if xy_t is None or z_t is None:
                    timed = None
                else:
                    timed = xy_t + z_t
            else:
                abs_z, dz = axis_delta(abs_z, z_raw, incremental=incremental)
                if motion in (2, 3):
                    x0 = (abs_x or 0.0) - dx
                    y0 = (abs_y or 0.0) - dy
                    x1 = abs_x if abs_x is not None else x0
                    y1 = abs_y if abs_y is not None else y0
                    r_arc = line.first("R")
                    i_word = line.first("I")
                    j_word = line.first("J")
                    r_val = r_arc.value if r_arc is not None and not in_cycle else None
                    xy_len = arc_xy_length(
                        x0,
                        y0,
                        x1,
                        y1,
                        r=r_val,
                        i=i_word.value if i_word else None,
                        j=j_word.value if j_word else None,
                        clockwise=motion == 2,
                    )
                    length = helical_length(xy_len, dz)
                else:
                    length = math.hypot(dx, dy, dz)
                timed = seconds_for_length(
                    length, fpm, rapid=motion == 0, inch=inch, profile=mill
                )

        abs_b, db = axis_delta(abs_b, b_raw, incremental=incremental)
        abs_c, dc = axis_delta(abs_c, c_raw, incremental=incremental)
        rot = seconds_for_rotary(
            math.hypot(db, dc),
            rapid=motion == 0 or g53,
            feed=fpm,
            profile=mill,
        )
        if current is not None:
            current.add_time(timed)
            current.add_time(rot)

        if current is None:
            continue

        _apply_line_to_usage(current, line, cycle_active)

        work_z: float | None = None
        if not g53 and cycle_active and cycle_code is not None and (
            starting_cycle or x_word is not None or y_word is not None or z_word is not None
        ):
            work_z = cycle_z
        elif z_word is not None and not g53:
            work_z = abs_z

        if work_z is not None:
            current.consider_z(work_z, line.number)
        elif cycle_active and cycle_z is not None and not g53:
            if line.first("X") is not None or line.first("Y") is not None:
                current.consider_z(cycle_z, line.number)

    if current is not None:
        current.line_end = lines[-1].number if lines else current.line_start
        if feed_per_rev and G95_NEXT_WARN not in current.warnings:
            current.warnings.append(G95_END_WARN)

    # Called only if the Txx M6 line itself ran (avoids marking a skipped
    # tool as called when GOTO later lands inside its linear line range).
    for usage in usages:
        start_i = usage.line_start - 1
        usage.called_from_main = start_i in executed

    called_summaries = _summarize(usages, called_only=True)
    all_summaries = _summarize(usages, called_only=False)

    if usages and header_comments:
        first_desc = usages[0].description
        header_comments = [c for c in header_comments if c != first_desc]

    declared = _declared_ops(header_comments)
    declared_ns = {n for n, _ in declared}
    selectors = _selector_m97_indices(lines, n_index, declared_ns)
    operations: list[Operation] = []

    if declared and selectors:
        for n_num, title in declared:
            overrides = {idx: n_num for idx in selectors}
            op_exec = _execute(lines, n_index, p_overrides=overrides)
            n_line = n_index.get(n_num)
            if n_line is not None and n_line not in op_exec:
                op_exec = _execute(lines, n_index, start_at=n_line)
                call = f"start N{n_num} until M30"
            else:
                call = f"M97 P{n_num}"
            operations.append(
                _make_operation(
                    usages,
                    op_exec,
                    n=n_num,
                    title=title,
                    call=call,
                )
            )
    else:
        operations.append(
            _make_operation(
                usages,
                executed,
                n=None,
                title="MAIN",
                call="as written until M30",
            )
        )
        for n_num, title in declared:
            n_line = n_index.get(n_num)
            if n_line is None:
                continue
            op_exec = _execute(lines, n_index, start_at=n_line)
            operations.append(
                _make_operation(
                    usages,
                    op_exec,
                    n=n_num,
                    title=title,
                    call=f"start N{n_num} until M30",
                )
            )

    return ParseResult(
        path=str(path_obj),
        filename=path_obj.name or "",
        program_number=program_number,
        program_title=program_title,
        header_comments=header_comments,
        bang_notes=_collect_bang_notes(lines),
        units=units,
        usages=usages,
        called_summaries=called_summaries,
        all_summaries=all_summaries,
        operations=operations,
        executed_lines={i + 1 for i in executed},
        source_lines=raw_lines,
        machine=mill,
    )


def _summarize(usages: list[ToolUsage], called_only: bool) -> list[ToolSummary]:
    grouped: dict[int, list[ToolUsage]] = {}
    order: list[int] = []
    for u in usages:
        if called_only and not u.called_from_main:
            continue
        if u.tool not in grouped:
            grouped[u.tool] = []
            order.append(u.tool)
        grouped[u.tool].append(u)

    summaries: list[ToolSummary] = []
    for tool in order:
        group = grouped[tool]
        descriptions: list[str] = []
        for u in group:
            if u.description and u.description not in descriptions:
                descriptions.append(u.description)
        min_u = None
        time_s = 0.0
        time_incomplete = False
        for u in group:
            time_s += u.time_s
            time_incomplete = time_incomplete or u.time_incomplete
            if u.min_z is None:
                continue
            if min_u is None or u.min_z < min_u.min_z:  # type: ignore[operator]
                min_u = u
        summaries.append(
            ToolSummary(
                tool=tool,
                descriptions=descriptions,
                min_z=min_u.min_z if min_u else None,
                min_z_line=min_u.min_z_line if min_u else None,
                called=any(u.called_from_main for u in group),
                usages=group,
                time_s=time_s,
                time_incomplete=time_incomplete,
            )
        )
    return summaries


def parse_nc_file(
    path: str | Path, *, machine: MachineProfile | None = None
) -> ParseResult:
    path_obj = Path(path)
    data = path_obj.read_bytes()
    text: str
    for enc in ("utf-8-sig", "utf-8", "cp1250", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("latin-1", errors="replace")
    return parse_nc_text(text, path_obj, machine=machine)
