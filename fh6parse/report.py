"""CNC operator tool reports: A4 and 80 mm thermal (text + print HTML)."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from contextvars import ContextVar
from dataclasses import dataclass
import base64
import re
import textwrap
import webbrowser

from .i18n import GUI_DEFAULT, parse_language, t
from .parser import (
    BangNote,
    G95_END_WARN,
    G95_NEXT_WARN,
    NO_FEED_WARN,
    NO_MOTION_WARN,
    Operation,
    ParseResult,
    TimeSplit,
    ToolSummary,
    ToolUsage,
)
from .machtime import DEFAULT_MACHINE, format_machine_time
from .safepath import refuse_write
from .workarea import append_g54_png, fmt_mm, fmt_xy, window_for_result


_ticket_lang: ContextVar[str] = ContextVar("ticket_lang", default=GUI_DEFAULT)
_MISMATCH_RE = re.compile(r"^([A-Z]#?\d+) does not match (T#?\d+)$")
_OFFSET_LATE_RE = re.compile(r"^(G\d+) after operation started \((L\d+)\)$")
_S_MAX_RE = re.compile(r"^(S[0-9.]+) exceeds mill max ([0-9.]+)$")
_G68_G69_RE = re.compile(r"^G68 (.+) to G69 (.+)$")
_G68_OPEN_RE = re.compile(r"^G68 (.+) without G69$")
_WARN_KEYS = {
    G95_NEXT_WARN: "ticket_warn_g95_next",
    G95_END_WARN: "ticket_warn_g95_end",
    NO_MOTION_WARN: "ticket_warn_no_motion",
    NO_FEED_WARN: "ticket_warn_no_feed",
}


def _set_ticket_lang(lang: str | None) -> str:
    code = parse_language(lang, default=GUI_DEFAULT)
    _ticket_lang.set(code)
    return code


def _tr(key: str, **kwargs: object) -> str:
    return t(_ticket_lang.get(), key, **kwargs)


def _warn_text(warn: str) -> str:
    key = _WARN_KEYS.get(warn)
    if key:
        return _tr(key)
    match = _MISMATCH_RE.match(warn)
    if match:
        return _tr("ticket_warn_mismatch", offset=match.group(1), tool=match.group(2))
    late = _OFFSET_LATE_RE.match(warn)
    if late:
        return _tr(
            "ticket_warn_offset_late", offset=late.group(1), line=late.group(2)
        )
    rpm = _S_MAX_RE.match(warn)
    if rpm:
        return _tr("ticket_warn_s_max", s=rpm.group(1), max=rpm.group(2))
    g68g69 = _G68_G69_RE.match(warn)
    if g68g69:
        return _tr(
            "ticket_warn_g68_g69", start=g68g69.group(1), end=g68g69.group(2)
        )
    g68open = _G68_OPEN_RE.match(warn)
    if g68open:
        return _tr("ticket_warn_g68_open", start=g68open.group(1))
    return warn


def _warn_line(warn: str, *, prefix: str | None = None) -> str:
    head = prefix if prefix is not None else f"{_tr('ticket_warning')} "
    return f"{head}{_warn_text(warn)}"


def _bang_label(note: BangNote) -> str:
    return f"L{note.line}  ({note.text})"

# A4 portrait ~78 cols at 10 pt Courier with 12 mm margins.
A4_WIDTH = 78
# ESC/POS 80 mm Font A is 48 columns on 72 mm printable width.
THERMAL_WIDTH = 48
# Solid block (CP852 0xDB) — prints as a black bar on Font A / Courier / Consolas.
BAR_FILL = "\u2588"
# "T15     0:24  50% " — bars start on the same column so they read as a chart.
CHART_PREFIX = 19
A4_BAR_WIDTH = 40
THERMAL_BAR_WIDTH = THERMAL_WIDTH - CHART_PREFIX

PAPER_A4 = "a4"
PAPER_80MM = "80mm"
PAPER_80MM_RUN = "80mm-run"
PAPER_80MM_LOAD = "80mm-load"
PAPER_80MM_SET = "80mm-set"
PAPER_80MM_MIN = PAPER_80MM_LOAD

SECTION_ORDER = (
    "header",
    "notes",
    "step",
    "g54",
    "cycle",
    "chart",
    "timesplit",
    "tools",
    "changes",
    "warnings",
    "sign",
)
GUI_SECTION_KEYS = (
    "header",
    "notes",
    "step",
    "g54",
    "cycle",
    "timesplit",
    "tools",
    "changes",
    "warnings",
    "sign",
)


@dataclass(frozen=True)
class ReportSections:
    header: bool = True
    notes: bool = True
    step: bool = True
    g54: bool = True
    cycle: bool = True
    chart: bool = True
    timesplit: bool = False
    tools: bool = True
    changes: bool = True
    warnings: bool = True
    sign: bool = True

    def to_csv(self) -> str:
        return ",".join(name for name in SECTION_ORDER if getattr(self, name))


SECTIONS_ALL = ReportSections()
SECTIONS_LOAD = ReportSections(
    notes=False,
    step=False,
    g54=False,
    cycle=False,
    chart=False,
    timesplit=False,
    changes=False,
)
SECTIONS_SET = ReportSections(
    chart=False,
    timesplit=False,
    tools=False,
    changes=False,
)
SECTIONS_RUN = ReportSections(timesplit=True)


def normalize_paper(paper: str | None) -> str:
    raw = (paper or "").strip().lower().replace(" ", "").replace("_", "-")
    if raw in {PAPER_80MM_LOAD, "80mm-min", "80mmmin", "load", "min"}:
        return PAPER_80MM_LOAD
    if raw in {PAPER_80MM_SET, "set"}:
        return PAPER_80MM_SET
    if raw in {PAPER_80MM, PAPER_80MM_RUN, "80mmrun", "run", "80", "thermal", "80mmthermal"}:
        return PAPER_80MM_RUN
    return PAPER_A4


def sections_for_paper(paper: str | None) -> ReportSections:
    kind = normalize_paper(paper)
    if kind == PAPER_80MM_LOAD:
        return SECTIONS_LOAD
    if kind == PAPER_80MM_SET:
        return SECTIONS_SET
    if kind == PAPER_80MM_RUN:
        return SECTIONS_RUN
    return SECTIONS_ALL


def parse_report_sections(raw: str | None) -> ReportSections:
    text = (raw or "").strip().lower().replace(" ", "")
    if not text:
        return SECTIONS_ALL
    wanted = {part for part in text.split(",") if part}
    if "cycle" in wanted and "chart" not in wanted:
        wanted.add("chart")
    kwargs = {name: name in wanted for name in SECTION_ORDER}
    return ReportSections(**kwargs)


def ticket_image_paths(
    result: ParseResult,
    image_paths: list[Path] | None,
    sections: ReportSections,
) -> list[Path]:
    extra = list(image_paths or [])
    out: list[Path] = []
    if sections.step:
        out.extend(p for p in extra if not Path(p).name.startswith("g54-"))
    if sections.g54:
        out = append_g54_png(result, out)
    return out


def _fmt_time(seconds: float, *, incomplete: bool = False) -> str:
    return format_machine_time(seconds, incomplete=incomplete)


def _time_of(obj: object) -> str:
    return _fmt_time(
        getattr(obj, "time_s", 0.0),
        incomplete=bool(getattr(obj, "time_incomplete", False)),
    )


def _time_assumptions(result: ParseResult, *, compact: bool = False) -> str:
    mill = result.machine
    rapid = mill.rapid_m_min_label()
    tchg = mill.tool_change_s
    named = mill.id != "default" or mill.name != DEFAULT_MACHINE.name
    if compact:
        bits: list[str] = []
        if named:
            bits.append(mill.name)
        bits.append(rapid.replace(" ", ""))
        if tchg > 0:
            bits.append(
                _tr(
                    "ticket_tchg_compact",
                    tchg=mill.tool_change_label().replace(" ", ""),
                )
            )
        if mill.has_g53_frame():
            bits.append(_tr("ticket_g53_compact"))
        return " ".join(bits)
    bits = [_tr("ticket_rapids", rapid=rapid)]
    if tchg > 0:
        bits.append(_tr("ticket_tchg", tchg=mill.tool_change_label()))
    if mill.has_g53_frame():
        bits.append(_tr("ticket_g53_frame"))
    bits.append(_tr("ticket_no_accel"))
    head = f"{mill.name}, " if named else ""
    return f"{head}{', '.join(bits)}"


def _seconds_of(obj: object) -> float:
    return float(getattr(obj, "time_s", 0.0) or 0.0)


def _op_cycle(op: Operation) -> tuple[float, bool]:
    total = sum(u.time_s for u in op.usages)
    incomplete = any(u.time_incomplete for u in op.usages)
    return total, incomplete


def _cycle_label(op: Operation) -> str:
    seconds, incomplete = _op_cycle(op)
    return _tr("ticket_cycle", time=_fmt_time(seconds, incomplete=incomplete))


def _pct(part: float, total: float) -> int:
    if total <= 0 or part <= 0:
        return 0
    return max(0, min(100, int(round(100.0 * part / total))))


def _pct_of(obj: object, total: float) -> int:
    return _pct(_seconds_of(obj), total)


def _bar_fill(pct: int, width: int) -> str:
    """Left-aligned solid marks. No trailing pad — thermal printers drop it."""
    pct = max(0, min(100, int(pct)))
    filled = int(round(width * pct / 100.0))
    if pct > 0:
        filled = max(1, filled)
    return BAR_FILL * max(0, min(width, filled))


def _chart_line(tool: int, obj: object, total: float, bar_width: int) -> str:
    share = _pct_of(obj, total)
    prefix = f"T{tool:<3} {_time_of(obj):>8} {share:3d}% "
    room = max(0, CHART_PREFIX + bar_width - len(prefix))
    return prefix + _bar_fill(share, room)


def _share_chart_text(
    op: Operation, bar_width: int, *, short: bool = True
) -> list[str]:
    if not op.summaries:
        return []
    total, _ = _op_cycle(op)
    rows = [_chart_line(s.tool, s, total, bar_width) for s in op.summaries]
    heading = _tr("ticket_share_short" if short else "ticket_share")
    return [heading, *rows]


def _share_chart_html(op: Operation) -> str:
    """A4: aligned CSS tracks. Same order as the tool list."""
    if not op.summaries:
        return ""
    total, _ = _op_cycle(op)
    rows: list[str] = []
    for s in op.summaries:
        share = _pct_of(s, total)
        rows.append(
            "<tr>"
            f'<td class="t">T{s.tool}</td>'
            f'<td class="n">{escape(_time_of(s))}</td>'
            f'<td class="n">{share}%</td>'
            '<td class="bar"><div class="track">'
            f'<span style="width:{share}%"></span></div></td>'
            "</tr>"
        )
    return (
        f'<p class="cycle-sub">{escape(_tr("ticket_share"))}</p>'
        '<table class="chart"><tbody>'
        + "".join(rows)
        + "</tbody></table>"
    )


def _share_chart_pre(op: Operation, bar_width: int) -> str:
    """80 mm HTML: same block chart as the kiosk ticket."""
    lines = _share_chart_text(op, bar_width)
    if not lines:
        return ""
    head, *rows = lines
    body = "\n".join(escape(p) for p in rows)
    return (
        f'<div class="tline">{escape(head)}</div>'
        f'<pre class="chart">{body}</pre>'
    )


SPLIT_MARK = {
    "rapid": "G",
    "feed": "F",
    "rotary": "R",
    "canned": "C",
    "probe": "P",
    "atc": "A",
}


def _split_of(obj: object) -> TimeSplit:
    split = getattr(obj, "split", None)
    return split if isinstance(split, TimeSplit) else TimeSplit()


def _feeds_of(obj: object) -> list[float]:
    feeds = getattr(obj, "feeds", None)
    return list(feeds) if feeds else []


def _op_split(op: Operation) -> TimeSplit:
    out = TimeSplit()
    for s in op.summaries:
        out = out.plus(_split_of(s))
    return out


def _fmt_feed_list(feeds: list[float]) -> str:
    if not feeds:
        return ""
    bits: list[str] = []
    for fpm in feeds:
        if abs(fpm - round(fpm)) < 1e-9:
            bits.append(str(int(round(fpm))))
        else:
            bits.append(f"{fpm:g}")
    return _tr("ticket_split_feeds", feeds=" ".join(bits))


def _split_kind_label(kind: str) -> str:
    return _tr(f"ticket_split_{kind}")


def _split_table_line(split: TimeSplit, *, feeds: list[float] | None = None) -> str:
    parts = [
        f"{_split_kind_label(kind)} {_fmt_time(sec)}"
        for kind, sec in split.nonzero()
    ]
    feed_txt = _fmt_feed_list(feeds or [])
    if feed_txt:
        parts.append(feed_txt)
    return "  ".join(parts)


def _stack_marks(split: TimeSplit, filled: int) -> str:
    parts = split.nonzero()
    if not parts or filled <= 0:
        return ""
    tot = split.total()
    if tot <= 0:
        return ""
    raw: list[list[object]] = []
    used = 0
    fracs: list[tuple[float, int]] = []
    for i, (kind, sec) in enumerate(parts):
        exact = filled * sec / tot
        n = int(exact)
        raw.append([kind, n])
        fracs.append((exact - n, i))
        used += n
    need = filled - used
    for _, i in sorted(fracs, reverse=True):
        if need <= 0:
            break
        raw[i][1] = int(raw[i][1]) + 1
        need -= 1
    return "".join(
        SPLIT_MARK[str(kind)] * int(n) for kind, n in raw if int(n) > 0
    )


def _split_bar_line(
    label: str, obj: object, cycle_s: float, bar_width: int
) -> str:
    split = _split_of(obj)
    share = _pct(split.total() or _seconds_of(obj), cycle_s)
    prefix = f"{label:<4} {_time_of(obj):>8} {share:3d}% "
    room = max(0, CHART_PREFIX + bar_width - len(prefix))
    filled = int(round(room * share / 100.0))
    if share > 0:
        filled = max(1, min(room, filled))
    else:
        filled = 0
    marks = _stack_marks(split, filled)
    if not marks and filled:
        marks = BAR_FILL * filled
    return (prefix + marks)[: CHART_PREFIX + bar_width]


def _split_chart_text(
    op: Operation, bar_width: int, *, short: bool = True, width: int = THERMAL_WIDTH
) -> list[str]:
    if not op.summaries:
        return []
    cycle_s, _ = _op_cycle(op)
    whole = _op_split(op)
    heading = _tr("ticket_split_short" if short else "ticket_split")
    lines = [heading]
    lines.extend(_wrap(_tr("ticket_split_legend"), width))
    all_label = _tr("ticket_split_all")
    dummy = ToolSummary(
        tool=0,
        descriptions=[],
        min_z=None,
        min_z_line=None,
        called=True,
        usages=[],
        time_s=whole.total(),
        split=whole,
    )
    lines.append(_split_bar_line(all_label, dummy, cycle_s, bar_width))
    detail = _split_table_line(whole)
    if detail:
        lines.extend(_wrap(detail, width))
    for s in op.summaries:
        lines.append(_split_bar_line(f"T{s.tool}", s, cycle_s, bar_width))
        row = _split_table_line(_split_of(s), feeds=_feeds_of(s))
        if row:
            lines.extend(_wrap(row, width))
    return lines


def _split_chart_html(op: Operation) -> str:
    if not op.summaries:
        return ""
    cycle_s, _ = _op_cycle(op)
    rows: list[str] = []

    def row_html(label: str, obj: object, feeds: list[float] | None = None) -> str:
        split = _split_of(obj)
        share = _pct(split.total() or _seconds_of(obj), cycle_s)
        tot = split.total()
        segs = ""
        if tot > 0:
            segs = "".join(
                f'<span class="k-{kind}" style="width:{100.0 * sec / tot:.2f}%"></span>'
                for kind, sec in split.nonzero()
            )
        detail = escape(_split_table_line(split, feeds=feeds))
        return (
            "<tr>"
            f'<td class="t">{escape(label)}</td>'
            f'<td class="n">{escape(_time_of(obj))}</td>'
            f'<td class="n">{share}%</td>'
            '<td class="bar"><div class="track">'
            f'<div class="fill" style="width:{share}%">{segs}</div>'
            "</div>"
            f'<div class="split-d">{detail}</div></td>'
            "</tr>"
        )

    whole = _op_split(op)
    dummy = ToolSummary(
        tool=0,
        descriptions=[],
        min_z=None,
        min_z_line=None,
        called=True,
        usages=[],
        time_s=whole.total(),
        split=whole,
    )
    rows.append(row_html(_tr("ticket_split_all"), dummy))
    for s in op.summaries:
        rows.append(row_html(f"T{s.tool}", s, _feeds_of(s)))
    return (
        f'<p class="cycle-sub">{escape(_tr("ticket_split"))}</p>'
        f'<p class="fine">{escape(_tr("ticket_split_legend"))}</p>'
        '<table class="chart"><tbody>'
        + "".join(rows)
        + "</tbody></table>"
    )


def _split_chart_pre(op: Operation, bar_width: int) -> str:
    lines = _split_chart_text(op, bar_width)
    if not lines:
        return ""
    head, *rows = lines
    body = "\n".join(escape(p) for p in rows)
    return (
        f'<div class="tline">{escape(head)}</div>'
        f'<pre class="chart">{body}</pre>'
    )


def _op_time_chart_text(
    op: Operation, bar_width: int, *, short: bool, width: int, sections: ReportSections
) -> list[str]:
    if sections.timesplit:
        return _split_chart_text(op, bar_width, short=short, width=width)
    if sections.chart:
        return _share_chart_text(op, bar_width, short=short)
    return []


def _op_time_chart_html(op: Operation, sections: ReportSections) -> str:
    if sections.timesplit:
        return _split_chart_html(op)
    if sections.chart:
        return _share_chart_html(op)
    return ""


def _op_time_chart_pre(
    op: Operation, bar_width: int, sections: ReportSections
) -> str:
    if sections.timesplit:
        return _split_chart_pre(op, bar_width)
    if sections.chart:
        return _share_chart_pre(op, bar_width)
    return ""


def _fmt_z(z: float | None) -> str:
    if z is None:
        return _tr("ticket_na")
    return f"{z:.3f}"


def _fmt_axis(letter: str, value: float | None) -> str:
    if value is None:
        return ""
    if abs(value - round(value)) < 1e-9:
        return f"{letter}{int(round(value))}"
    return f"{letter}{value:g}"


def _fmt_s(s: float | None) -> str:
    if s is None:
        return ""
    if abs(s - round(s)) < 1e-9:
        return f"S{int(round(s))}"
    return f"S{s:g}"


def _fmt_t(tool: int, tool_hash: int | None = None) -> str:
    if tool_hash is not None:
        if tool:
            return f"T{tool} (#{tool_hash})"
        return f"T#{tool_hash}"
    return f"T{tool}"


def _is_stop_usage(u: ToolUsage) -> bool:
    return getattr(u, "event", "tool") == "stop"


def _t_of_usage(u: ToolUsage) -> str:
    if _is_stop_usage(u):
        return "M00"
    return _fmt_t(u.tool, u.tool_hash)


def _t_of_summary(s: ToolSummary) -> str:
    hashes: list[int] = []
    for u in s.usages:
        if u.tool_hash is not None and u.tool_hash not in hashes:
            hashes.append(u.tool_hash)
    if len(hashes) == 1:
        return _fmt_t(s.tool, hashes[0])
    if hashes:
        extra = ", ".join(f"#{n}" for n in hashes)
        if s.tool:
            return f"T{s.tool} ({extra})"
        return " ".join(f"T#{n}" for n in hashes)
    return _fmt_t(s.tool)


def _fmt_hd(letter: str, offset: int | None, param: int | None) -> str:
    if offset is None and param is None:
        return ""
    if param is not None and offset is not None:
        return f"{letter}{offset} (#{param})"
    if param is not None:
        return f"{letter}#{param}"
    return f"{letter}{offset}"


def _summary_hds(s: ToolSummary) -> str:
    """H/D/S to load for this T (unique values across its Txx M6 uses)."""
    hs: list[str] = []
    ds: list[str] = []
    speeds: list[str] = []
    for u in s.usages:
        h = _fmt_hd("H", u.h_offset, u.h_hash)
        if h and h not in hs:
            hs.append(h)
        d = _fmt_hd("D", u.d_offset, u.d_hash)
        if d and d not in ds:
            ds.append(d)
        sp = _fmt_s(u.s_rpm)
        if sp and sp not in speeds:
            speeds.append(sp)
    return "  ".join(hs + ds + speeds)


def _summary_warnings(s: ToolSummary) -> list[str]:
    seen: list[str] = []
    for u in s.usages:
        for warn in u.warnings:
            if warn not in seen:
                seen.append(warn)
    return seen


def _units_label(units: str) -> str:
    if units == "mm":
        return _tr("ticket_units_mm")
    if units == "inch":
        return _tr("ticket_units_inch")
    return units


def _program_line(result: ParseResult) -> str:
    prog = result.program_number or _tr("ticket_no_onumber")
    if result.program_title:
        return f"{prog} ({result.program_title})"
    return prog


def _wrap(text: str, width: int) -> list[str]:
    text = (text or "").rstrip()
    if not text:
        return [""]
    if len(text) <= width:
        return [text]
    return textwrap.wrap(
        " ".join(text.split()),
        width=width,
        break_long_words=True,
        break_on_hyphens=True,
    ) or [""]


def _op_heading(op: Operation) -> str:
    if op.n is None:
        return f"{op.title}  ({op.call})"
    return f"{op.title}  (N{op.n})  {op.call}"


def _usage_meta(u: ToolUsage, *, include_lines: bool = True) -> str:
    parts = [u.subprogram]
    if u.subprogram_comment:
        parts[0] = f"{u.subprogram} ({u.subprogram_comment})"
    if not _is_stop_usage(u):
        bc = " ".join(
            p for p in (_fmt_axis("B", u.b), _fmt_axis("C", u.c)) if p
        )
        if bc:
            parts.append(bc)
        h = _fmt_hd("H", u.h_offset, u.h_hash)
        if h:
            parts.append(h)
        d = _fmt_hd("D", u.d_offset, u.d_hash)
        if d:
            parts.append(d)
        s = _fmt_s(u.s_rpm)
        if s:
            parts.append(s)
    if include_lines:
        if _is_stop_usage(u):
            parts.append(f"L{u.line_start}")
        else:
            parts.append(f"L{u.line_start}-{u.line_end}")
    return "  ".join(parts)


def format_report(
    result: ParseResult,
    *,
    paper: str = PAPER_A4,
    generated: datetime | None = None,
    lang: str | None = None,
    sections: ReportSections | None = None,
) -> str:
    _set_ticket_lang(lang)
    kind = normalize_paper(paper)
    secs = sections or sections_for_paper(kind)
    if kind != PAPER_A4:
        return _format_text_80mm(
            result, generated=generated, sections=secs, paper=kind
        )
    return _format_text_a4(result, generated=generated, sections=secs)


def _80mm_title(paper: str) -> str:
    kind = normalize_paper(paper)
    if kind == PAPER_80MM_LOAD:
        return _tr("ticket_title_load")
    if kind == PAPER_80MM_SET:
        return _tr("ticket_title_set")
    return _tr("ticket_title_80")


def _named_mill(result: ParseResult) -> str:
    mill = result.machine
    if mill.id != "default" or mill.name != DEFAULT_MACHINE.name:
        return mill.name
    return ""


def _g54_ticket_lines(result: ParseResult, width: int) -> list[str]:
    window = window_for_result(result)
    if window is None:
        return []
    sw, se, ne, nw = window.corners
    cx, cy = window.center
    raw = [
        _tr("ticket_g54_heading"),
        _tr("ticket_g54_sw", xy=fmt_xy(*sw)),
        _tr("ticket_g54_se", xy=fmt_xy(*se)),
        _tr("ticket_g54_ne", xy=fmt_xy(*ne)),
        _tr("ticket_g54_nw", xy=fmt_xy(*nw)),
        _tr("ticket_g54_center", xy=fmt_xy(cx, cy)),
    ]
    dia = window.max_tool_dia_mm
    if dia is not None:
        raw.append(_tr("ticket_g54_dia", d=fmt_mm(dia)))
    if window.z_min is not None and window.z_max is not None:
        raw.append(
            _tr("ticket_g54_z", z0=fmt_mm(window.z_min), z1=fmt_mm(window.z_max))
        )
    if not window.fits:
        raw.append(_tr("ticket_g54_too_big"))
    elif window.g54_inside is False:
        raw.append(_tr("ticket_g54_out"))
    elif window.g54_inside is True:
        raw.append(_tr("ticket_g54_ok"))
    lines: list[str] = []
    for text in raw:
        lines.extend(_wrap(text, width))
    return lines


def _a4_field(label: str, value: str) -> str:
    return f"{label:<14}{value}"


def _format_text_a4(
    result: ParseResult,
    *,
    generated: datetime | None,
    sections: ReportSections = SECTIONS_ALL,
) -> str:
    now = generated or datetime.now()
    w78 = A4_WIDTH
    lines: list[str] = []
    w = lines.append
    w(_tr("ticket_title_a4"))
    w("=" * w78)
    if sections.header:
        w(_a4_field(_tr("ticket_file"), result.filename or result.path))
        prog = _program_line(result)
        label = f"{_tr('ticket_program'):<14}"
        wrapped = _wrap(prog, w78 - len(label))
        w(label + wrapped[0])
        for part in wrapped[1:]:
            w(" " * len(label) + part)
        w(_a4_field(_tr("ticket_units"), _units_label(result.units)))
        w(_a4_field(_tr("ticket_generated"), now.strftime("%Y-%m-%d %H:%M")))
    if sections.notes:
        if result.header_comments:
            w("")
            w(_tr("ticket_header_notes"))
            for c in result.header_comments:
                for part in _wrap(f"({c})", w78 - 2):
                    w(f"  {part}")
        if result.bang_notes:
            w("")
            w(_tr("ticket_programmer_notes"))
            for note in result.bang_notes:
                for part in _wrap(_bang_label(note), w78 - 2):
                    w(f"  {part}")

    if sections.tools or sections.cycle or sections.changes:
        w("")
        if sections.tools:
            w(_tr("ticket_minz_legend"))
        if sections.cycle:
            w(_tr("ticket_time_legend", assumptions=_time_assumptions(result)))
            w(_tr("ticket_cycle_legend"))
            w(_tr("ticket_sim_legend"))
        if sections.changes:
            w(_tr("ticket_m97_legend"))
        if sections.tools:
            w(_tr("ticket_loaded_legend"))
    if sections.g54:
        for part in _g54_ticket_lines(result, w78):
            w(part)
    show_ops = sections.tools or sections.changes or sections.cycle
    ops = result.operations or []
    if show_ops:
        if not ops:
            w("")
            w(_tr("ticket_no_ops"))
        for op in ops:
            w("")
            w("=" * w78)
            for part in _wrap(_op_heading(op), w78):
                w(part)
            w("=" * w78)
            if sections.warnings:
                for warn in op.warnings:
                    for part in _wrap(_warn_line(warn), w78):
                        w(part)
            cycle_s, _ = _op_cycle(op)
            if sections.cycle:
                w(_cycle_label(op))
            for line in _op_time_chart_text(
                op, A4_BAR_WIDTH, short=False, width=w78, sections=sections
            ):
                w(line)
            none = _tr("ticket_no_comment")
            minz = _tr("ticket_minz")
            time_lbl = _tr("ticket_time")
            if sections.tools:
                if not op.summaries:
                    w(_tr("ticket_no_tool_changes"))
                else:
                    w(_tr("ticket_tool_list"))
                    w("-" * w78)
                    for s in op.summaries:
                        desc = " / ".join(s.descriptions) if s.descriptions else none
                        w(
                            f"[ ] {_t_of_summary(s):<12}  {minz} {_fmt_z(s.min_z):>9}  "
                            f"{time_lbl} {_time_of(s):>7}"
                        )
                        for part in _wrap(desc, w78 - 4):
                            w(f"    {part}")
                        if sections.warnings:
                            for u in s.usages:
                                for warn in u.warnings:
                                    for part in _wrap(_warn_line(warn), w78 - 6):
                                        w(f"      {part}")
            if sections.changes:
                w("")
                w(_tr("ticket_each_change"))
                w("-" * w78)
                for u in op.usages:
                    w("")
                    for part in _wrap(
                        f"[ ] {_t_of_usage(u)}  {u.description or none}", w78
                    ):
                        w(part)
                    for part in _wrap(_usage_meta(u), w78 - 4):
                        w(f"    {part}")
                    if not _is_stop_usage(u):
                        share = _pct_of(u, cycle_s)
                        bits = f"{minz} {_fmt_z(u.min_z)}"
                        if u.min_z_line:
                            bits += f"  L{u.min_z_line}"
                        bits += f"  {time_lbl} {_time_of(u)}  {share:3d}%"
                        for part in _wrap(bits, w78 - 4):
                            w(f"    {part}")
                    if sections.warnings:
                        for warn in u.warnings:
                            for part in _wrap(_warn_line(warn), w78 - 4):
                                w(f"    {part}")

    if sections.sign:
        w("")
        w("=" * w78)
        w(_tr("ticket_sign_a4"))
        w("")
    return "\n".join(lines)


def _format_text_80mm(
    result: ParseResult,
    *,
    generated: datetime | None,
    sections: ReportSections = SECTIONS_ALL,
    paper: str = PAPER_80MM_RUN,
) -> str:
    """48-column receipt text for 80 mm ESC/POS / generic text driver."""
    now = generated or datetime.now()
    n = THERMAL_WIDTH
    bar = "=" * n
    dash = "-" * n
    lines: list[str] = []
    w = lines.append
    none = _tr("ticket_no_comment")
    minz_lbl = _tr("ticket_minz_compact")
    time_lbl = _tr("ticket_time")
    load = sections.tools and not sections.changes

    def block(text: str, width: int = n) -> None:
        for part in _wrap(text, width):
            w(part)

    w(bar)
    w(_80mm_title(paper))
    w(_tr("ticket_80mm"))
    w(bar)
    if sections.header:
        block(result.filename or Path(result.path).name or _tr("ticket_file_fallback"))
        block(_program_line(result))
        mill = _named_mill(result)
        if mill and not sections.tools:
            block(mill)
        w(_units_label(result.units))
        w(now.strftime("%Y-%m-%d %H:%M"))
    if sections.notes:
        for c in result.header_comments[:8]:
            block(f"({c})")
        if result.bang_notes:
            w(_tr("ticket_notes_short"))
            for note in result.bang_notes:
                block(f"! {_bang_label(note)}")
    if sections.tools or sections.cycle:
        w(dash)
        if sections.tools:
            w(_tr("ticket_minz_work"))
        if sections.cycle:
            w(
                _tr(
                    "ticket_time_moves",
                    assumptions=_time_assumptions(result, compact=True),
                )
            )
            if sections.changes:
                w(_tr("ticket_until_m30"))
                w(_tr("ticket_op_m97"))
    if sections.g54:
        for part in _g54_ticket_lines(result, n):
            w(part)
    show_ops = sections.tools or sections.changes or sections.cycle
    ops = result.operations or []
    if show_ops:
        if not ops:
            w(_tr("ticket_no_ops_short"))
        for op in ops:
            w(dash)
            block(_op_heading(op))
            w(dash)
            if sections.warnings:
                for warn in op.warnings:
                    block(_warn_line(warn, prefix="! "))
            cycle_s, _ = _op_cycle(op)
            if sections.cycle:
                w(_cycle_label(op))
            for line in _op_time_chart_text(
                op, THERMAL_BAR_WIDTH, short=True, width=n, sections=sections
            ):
                w(line)
            if sections.tools:
                if not op.summaries:
                    w(_tr("ticket_no_tools"))
                    continue
                for s in op.summaries:
                    desc = " / ".join(s.descriptions) if s.descriptions else none
                    if load:
                        w(f"[ ] {_t_of_summary(s)}")
                    else:
                        w(f"[ ] {_t_of_summary(s)}")
                    block(desc)
                    if load:
                        hds = _summary_hds(s)
                        if hds:
                            block(hds)
                        w(f"{minz_lbl} {_fmt_z(s.min_z)}")
                    else:
                        w(f"{minz_lbl} {_fmt_z(s.min_z)}  {time_lbl} {_time_of(s)}")
                    if sections.warnings:
                        warns = (
                            _summary_warnings(s)
                            if load
                            else [warn for u in s.usages for warn in u.warnings]
                        )
                        for warn in warns:
                            block(_warn_line(warn, prefix="! "))
                    w(dash)
            if sections.changes:
                w(_tr("ticket_each_change_short"))
                w(dash)
                for u in op.usages:
                    w(f"[ ] {_t_of_usage(u)}")
                    block(u.description or none)
                    block(_usage_meta(u, include_lines=False))
                    if not _is_stop_usage(u):
                        share = _pct_of(u, cycle_s)
                        minz = f"{minz_lbl} {_fmt_z(u.min_z)}"
                        if u.min_z_line:
                            minz += f" L{u.min_z_line}"
                        w(f"{minz}  {time_lbl} {_time_of(u)}  {share:3d}%")
                    if sections.warnings:
                        for warn in u.warnings:
                            block(_warn_line(warn, prefix="! "))
                    w(dash)

    if sections.sign:
        w(_tr("ticket_sign_op"))
        w(_tr("ticket_sign_date"))
        w(_tr("ticket_sign_loaded"))
        w(bar)
        w("")
    return "\n".join(lines)


def format_print_html(
    result: ParseResult,
    *,
    paper: str = PAPER_A4,
    generated: datetime | None = None,
    auto_print: bool = False,
    image_paths: list[Path] | None = None,
    lang: str | None = None,
    sections: ReportSections | None = None,
) -> str:
    _set_ticket_lang(lang)
    kind = normalize_paper(paper)
    secs = sections or sections_for_paper(kind)
    image_paths = ticket_image_paths(result, image_paths, secs)
    if kind != PAPER_A4:
        return _html_80mm(
            result,
            generated=generated,
            auto_print=auto_print,
            image_paths=image_paths,
            sections=secs,
            paper=kind,
        )
    return _html_a4(
        result,
        generated=generated,
        auto_print=auto_print,
        image_paths=image_paths,
        sections=secs,
    )


def _step_views_html(image_paths: list[Path] | None) -> str:
    """Stacked isometric PNGs as data URIs so a browser print needs no extra files."""
    parts: list[str] = []
    for raw in image_paths or []:
        path = Path(raw)
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        if not blob:
            continue
        b64 = base64.b64encode(blob).decode("ascii")
        alt_key = "ticket_g54_alt" if path.name.startswith("g54-") else "ticket_step_alt"
        parts.append(
            f'<img class="step-view" alt="{escape(_tr(alt_key))}" '
            f'src="data:image/png;base64,{b64}">'
        )
    if not parts:
        return ""
    return '<div class="step-views">' + "".join(parts) + "</div>"


def _g54_html(result: ParseResult) -> str:
    lines = _g54_ticket_lines(result, A4_WIDTH)
    if not lines:
        return ""
    return '<p class="fine">' + "<br>".join(escape(x) for x in lines) + "</p>"


def _html_shell(title: str, css: str, body: str, *, auto_print: bool, hint: str) -> str:
    script = ""
    if auto_print:
        script = """
<script>
window.addEventListener("load", function () {
  setTimeout(function () { window.print(); }, 300);
});
</script>"""
    return f"""<!DOCTYPE html>
<html lang="{escape(_ticket_lang.get())}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
{css}
</style>
</head>
<body>
<div class="no-print toolbar">
  <button type="button" onclick="window.print()">{escape(_tr("ticket_print"))}</button>
  <span class="hint">{escape(hint)}</span>
</div>
{body}
{script}
</body>
</html>
"""


def _html_a4(
    result: ParseResult,
    *,
    generated: datetime | None,
    auto_print: bool,
    image_paths: list[Path] | None = None,
    sections: ReportSections = SECTIONS_ALL,
) -> str:
    now = generated or datetime.now()
    css = """
@page { size: A4 portrait; margin: 12mm; }
* { box-sizing: border-box; }
body {
  margin: 0;
  color: #000;
  background: #fff;
  font: 10.5pt/1.3 "Segoe UI", Arial, sans-serif;
}
h1 { font-size: 16pt; margin: 0 0 6pt; }
h2 { font-size: 11pt; margin: 14pt 0 4pt; border-bottom: 1.5pt solid #000; padding-bottom: 2pt; }
h3 { font-size: 10pt; margin: 10pt 0 6pt; }
.cycle-sub { font-size: 9pt; font-weight: 600; margin: 0 0 4pt; }
.meta { display: grid; grid-template-columns: 18mm 1fr 22mm 1fr; gap: 2pt 8pt; margin-bottom: 8pt; }
.meta b { font-weight: 600; }
.notes { font-size: 9pt; margin: 0 0 8pt; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; }
th, td { border: 1pt solid #000; padding: 3pt 5pt; vertical-align: top; }
th { background: #eee; font-size: 9pt; text-align: left; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; font-family: Consolas, "Courier New", monospace; white-space: nowrap; }
td.c, th.c { text-align: center; width: 9mm; }
table.chart { margin: 0 0 10pt; border: 0; }
table.chart td { border: 0; border-bottom: 0.4pt solid #ccc; padding: 2pt 4pt; vertical-align: middle; }
table.chart td.t { width: 14mm; font-weight: 700; }
table.chart td.n { width: 16mm; }
table.chart td.bar { padding-right: 0; }
.track { height: 8pt; border: 1pt solid #000; background: #fff; }
.track > span { display: block; height: 100%; background: #000; }
.track .fill { display: flex; height: 100%; }
.track .fill > span { display: block; height: 100%; }
.k-rapid { background: #b0b0b0; }
.k-feed { background: #000; }
.k-rotary { background: #666; }
.k-canned { background: #444; }
.k-probe { background: #888; }
.k-atc { background: #d0d0d0; }
.split-d { font-size: 8pt; font-family: Consolas, "Courier New", monospace; margin-top: 2pt; }
.box { display: inline-block; width: 11pt; height: 11pt; border: 1.2pt solid #000; vertical-align: middle; }
.warn { font-size: 8.5pt; }
.sign { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16pt; margin-top: 16pt; }
.sign .line { border-top: 1pt solid #000; padding-top: 3pt; font-size: 9pt; }
.fine { font-size: 8.5pt; color: #222; margin: 0 0 8pt; }
.toolbar { margin: 0 0 12pt; }
.hint { margin-left: 10pt; font-size: 9pt; }
.step-views { text-align: center; margin: 0 0 10pt; }
.step-views img.step-view { width: 80mm; max-width: 100%; height: auto; display: block; margin: 0 auto; }
@media screen {
  body { max-width: 210mm; margin: 12px auto; padding: 12mm; box-shadow: 0 0 8px #bbb; }
}
@media print {
  .no-print { display: none !important; }
  body { padding: 0; box-shadow: none; }
  thead { display: table-header-group; }
  tr { page-break-inside: avoid; }
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
"""
    notes = ""
    none = _tr("ticket_no_comment")
    if sections.notes:
        if result.header_comments:
            items = "".join(f"<li>({escape(c)})</li>" for c in result.header_comments)
            notes = f'<ul class="notes">{items}</ul>'
        if result.bang_notes:
            items = "".join(
                f"<li>{escape(_bang_label(note))}</li>" for note in result.bang_notes
            )
            notes += (
                f'<h2>{escape(_tr("ticket_programmer_notes"))}</h2>'
                f'<ul class="notes">{items}</ul>'
            )

    op_html: list[str] = []
    show_ops = sections.tools or sections.changes or sections.cycle
    if show_ops:
        if not result.operations:
            op_html.append(f"<p>{escape(_tr('ticket_no_ops'))}</p>")
        for op in result.operations:
            cycle_s, _ = _op_cycle(op)
            setup_rows = []
            if not op.summaries:
                setup_rows.append(
                    f'<tr><td colspan="6">{escape(_tr("ticket_no_tool_changes"))}</td></tr>'
                )
            for s in op.summaries:
                desc = escape(" / ".join(s.descriptions) if s.descriptions else none)
                warns = ""
                if sections.warnings:
                    warns = "".join(
                        f'<div class="warn">{escape(_warn_line(w))}</div>'
                        for u in s.usages
                        for w in u.warnings
                    )
                setup_rows.append(
                    "<tr>"
                    f'<td class="c"><span class="box"></span></td>'
                    f"<td>{escape(_t_of_summary(s))}</td>"
                    f"<td>{desc}{warns}</td>"
                    f'<td class="n">{escape(_fmt_z(s.min_z))}</td>'
                    f'<td class="n">{escape(_time_of(s))}</td>'
                    f'<td class="c"><span class="box"></span></td>'
                    "</tr>"
                )
            change_rows = []
            if not op.usages:
                change_rows.append(
                    f'<tr><td colspan="8">{escape(_tr("ticket_no_txx"))}</td></tr>'
                )
            for u in op.usages:
                extra = ""
                if sections.warnings:
                    extra = "".join(
                        f'<div class="warn">{escape(_warn_line(warn))}</div>'
                        for warn in u.warnings
                    )
                if _is_stop_usage(u):
                    change_rows.append(
                        "<tr>"
                        f'<td class="c"><span class="box"></span></td>'
                        f"<td>{escape(_t_of_usage(u))}</td>"
                        f"<td>{escape(u.description or none)}{extra}</td>"
                        f"<td>{escape(u.subprogram)}</td>"
                        "<td>—</td><td>—</td>"
                        f'<td class="n">—</td>'
                        f'<td class="n">—</td>'
                        "</tr>"
                    )
                    continue
                bc = " ".join(p for p in (_fmt_axis("B", u.b), _fmt_axis("C", u.c)) if p) or "—"
                share = _pct_of(u, cycle_s)
                change_rows.append(
                    "<tr>"
                    f'<td class="c"><span class="box"></span></td>'
                    f"<td>{escape(_t_of_usage(u))}</td>"
                    f"<td>{escape(u.description or none)}{extra}</td>"
                    f"<td>{escape(u.subprogram)}</td>"
                    f"<td>{escape(bc)}</td>"
                    f"<td>{escape(' '.join(p for p in (_fmt_hd('H', u.h_offset, u.h_hash), _fmt_hd('D', u.d_offset, u.d_hash), _fmt_s(u.s_rpm)) if p) or '—')}</td>"
                    f'<td class="n">{escape(_fmt_z(u.min_z))}</td>'
                    f'<td class="n">{escape(_time_of(u))}  {share}%</td>'
                    "</tr>"
                )
            op_html.append(f"<h2>{escape(_op_heading(op))}</h2>")
            if sections.warnings:
                for warn in op.warnings:
                    op_html.append(
                        f'<p class="warn">{escape(_warn_line(warn))}</p>'
                    )
            if sections.cycle:
                op_html.append(f'<p class="cycle">{escape(_cycle_label(op))}</p>')
            chart = _op_time_chart_html(op, sections)
            if chart:
                op_html.append(chart)
            if sections.tools:
                op_html.append(
                    "<table><thead><tr>"
                    f'<th class="c">{escape(_tr("ticket_load"))}</th><th>T</th>'
                    f'<th>{escape(_tr("ticket_desc"))}</th>'
                    f'<th class="n">{escape(_tr("ticket_minz"))}</th>'
                    f'<th class="n">{escape(_tr("ticket_time"))}</th>'
                    f'<th class="c">{escape(_tr("ticket_ok"))}</th>'
                    "</tr></thead><tbody>"
                    + "".join(setup_rows)
                    + "</tbody></table>"
                )
            if sections.changes:
                op_html.append(f'<h3>{escape(_tr("ticket_each_change_html"))}</h3>')
                op_html.append(
                    "<table><thead><tr>"
                    f'<th class="c">{escape(_tr("ticket_load"))}</th><th>T</th>'
                    f'<th>{escape(_tr("ticket_desc"))}</th>'
                    f'<th>{escape(_tr("ticket_sub"))}</th>'
                    '<th>B/C</th><th>H / D / S</th>'
                    f'<th class="n">{escape(_tr("ticket_minz"))}</th>'
                    f'<th class="n">{escape(_tr("ticket_time"))}</th>'
                    "</tr></thead><tbody>"
                    + "".join(change_rows)
                    + "</tbody></table>"
                )

    title = _tr("ticket_title_html_doc", prog=_program_line(result))
    meta = ""
    if sections.header:
        meta = f"""
<div class="meta">
  <b>{escape(_tr("ticket_file_html"))}</b><span>{escape(result.filename or result.path)}</span>
  <b>{escape(_tr("ticket_units_html"))}</b><span>{escape(_units_label(result.units))}</span>
  <b>{escape(_tr("ticket_program_html"))}</b><span>{escape(_program_line(result))}</span>
  <b>{escape(_tr("ticket_printed_html"))}</b><span>{escape(now.strftime("%Y-%m-%d %H:%M"))}</span>
</div>
"""
    fine = ""
    if sections.cycle:
        fine = (
            f'<p class="fine">{escape(_tr("ticket_html_fine", assumptions=_time_assumptions(result)))}</p>'
        )
    g54 = _g54_html(result) if sections.g54 else ""
    sign = ""
    if sections.sign:
        sign = f"""
<div class="sign">
  <div class="line">{escape(_tr("ticket_operator"))}</div>
  <div class="line">{escape(_tr("ticket_date"))}</div>
  <div class="line">{escape(_tr("ticket_tools_loaded"))}</div>
</div>
"""
    body = f"""
<h1>{escape(_tr("ticket_title_html"))}</h1>
{_step_views_html(image_paths)}
{meta}
{notes}
{fine}
{g54}
{"".join(op_html)}
{sign}
"""
    hint = _tr("ticket_print_hint_a4")
    return _html_shell(title, css, body, auto_print=auto_print, hint=hint)


def _html_80mm(
    result: ParseResult,
    *,
    generated: datetime | None,
    auto_print: bool,
    image_paths: list[Path] | None = None,
    sections: ReportSections = SECTIONS_ALL,
    paper: str = PAPER_80MM_RUN,
) -> str:
    now = generated or datetime.now()
    kind = normalize_paper(paper)
    load = sections.tools and not sections.changes
    title = f"{kind} {_program_line(result)}"
    css = """
@page { size: 80mm auto; margin: 2mm; }
* { box-sizing: border-box; }
html, body {
  width: 76mm;
  margin: 0;
  padding: 0;
  color: #000;
  background: #fff;
}
body {
  font: 10.5pt/1.25 Consolas, "Courier New", monospace;
}
h1 { font-size: 13pt; margin: 0 0 4pt; text-align: center; letter-spacing: 0.04em; }
.center { text-align: center; }
.rule { border: 0; border-top: 1.5pt dashed #000; margin: 6pt 0; }
.tool { page-break-inside: avoid; margin: 0 0 6pt; }
.tline { font-weight: 700; font-size: 12pt; }
.box {
  display: inline-block; width: 10pt; height: 10pt;
  border: 1.3pt solid #000; vertical-align: -1pt; margin-right: 3pt;
}
.kv { display: flex; justify-content: space-between; gap: 6pt; }
.d { word-wrap: break-word; overflow-wrap: anywhere; }
.warn { font-weight: 700; }
.cycle { font-weight: 700; margin: 2pt 0 4pt; }
pre.chart {
  font: inherit;
  margin: 2pt 0 6pt;
  white-space: pre;
}
.toolbar { margin: 0 0 8pt; font-family: "Segoe UI", Arial, sans-serif; }
.hint { display: block; margin-top: 4pt; font-size: 8pt; }
.step-views { margin: 0 0 6pt; }
.step-views img.step-view { width: 76mm; max-width: 100%; height: auto; display: block; }
@media screen {
  body { margin: 12px auto; padding: 6px; border: 1px dashed #999; }
}
@media print {
  .no-print { display: none !important; }
  html, body { width: 76mm; }
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
"""
    chunks: list[str] = []
    a = chunks.append
    none = _tr("ticket_no_comment")
    minz = _tr("ticket_minz")
    time_lbl = _tr("ticket_time")
    a(f"<h1>{escape(_80mm_title(kind))}</h1>")
    a(f'<div class="center">{escape(_tr("ticket_80mm"))}</div>')
    views = _step_views_html(image_paths)
    if views:
        a(views)
    if sections.header:
        a(f'<div class="d">{escape(result.filename or result.path)}</div>')
        a(f'<div class="d">{escape(_program_line(result))}</div>')
        mill = _named_mill(result)
        if mill and not sections.tools:
            a(f'<div class="d">{escape(mill)}</div>')
        a(f"<div>{escape(_units_label(result.units))} · {escape(now.strftime('%Y-%m-%d %H:%M'))}</div>")
    if sections.notes:
        for c in result.header_comments[:8]:
            a(f'<div class="d">({escape(c)})</div>')
        if result.bang_notes:
            a(f'<div class="warn">{escape(_tr("ticket_notes_short"))}</div>')
            for note in result.bang_notes:
                a(f'<div class="warn d">! {escape(_bang_label(note))}</div>')
    if sections.tools or sections.cycle:
        a('<hr class="rule">')
        if sections.tools:
            a(f"<div>{escape(_tr('ticket_minz_work_html'))}</div>")
        if sections.cycle:
            a(
                f"<div>{escape(_tr('ticket_time_moves_html', assumptions=_time_assumptions(result, compact=True)))}</div>"
            )
            if sections.changes:
                a(f"<div>{escape(_tr('ticket_until_m30'))}</div>")
                a(f"<div>{escape(_tr('ticket_op_m97'))}</div>")
    if sections.g54:
        g54 = _g54_html(result)
        if g54:
            a(g54)
    show_ops = sections.tools or sections.changes or sections.cycle
    ops = result.operations or []
    if show_ops:
        if not ops:
            a(f"<div>{escape(_tr('ticket_no_ops_short'))}</div>")
        for op in ops:
            cycle_s, _ = _op_cycle(op)
            a('<hr class="rule">')
            a(f'<div class="tline d">{escape(_op_heading(op))}</div>')
            if sections.warnings:
                for warn in op.warnings:
                    a(f'<div class="warn">{escape(_warn_line(warn, prefix="! "))}</div>')
            if sections.cycle:
                a(f'<div class="cycle">{escape(_cycle_label(op))}</div>')
            chart = _op_time_chart_pre(op, THERMAL_BAR_WIDTH, sections)
            if chart:
                a(chart)
            if sections.tools:
                if not op.summaries:
                    a(f"<div>{escape(_tr('ticket_no_tools'))}</div>")
                    continue
                for s in op.summaries:
                    desc = " / ".join(s.descriptions) if s.descriptions else none
                    a('<div class="tool">')
                    a(
                        f'<div class="tline"><span class="box"></span>'
                        f"{escape(_t_of_summary(s))}</div>"
                    )
                    a(f'<div class="d">{escape(desc)}</div>')
                    if load:
                        hds = _summary_hds(s)
                        if hds:
                            a(f'<div class="d">{escape(hds)}</div>')
                    a(f'<div class="kv"><span>{escape(minz)}</span><span>{escape(_fmt_z(s.min_z))}</span></div>')
                    if not load:
                        a(f'<div class="kv"><span>{escape(time_lbl)}</span><span>{escape(_time_of(s))}</span></div>')
                    if sections.warnings:
                        for warn in _summary_warnings(s):
                            a(f'<div class="warn">{escape(_warn_line(warn, prefix="! "))}</div>')
                    a("</div>")
            if sections.changes:
                a(f'<div class="tline">{escape(_tr("ticket_each_change_short"))}</div>')
                for u in op.usages:
                    a('<div class="tool">')
                    a(f'<div class="tline"><span class="box"></span>{escape(_t_of_usage(u))}</div>')
                    a(f'<div class="d">{escape(u.description or none)}</div>')
                    a(f'<div class="d">{escape(_usage_meta(u, include_lines=False))}</div>')
                    if not _is_stop_usage(u):
                        share = _pct_of(u, cycle_s)
                        a(f'<div class="kv"><span>{escape(minz)}</span><span>{escape(_fmt_z(u.min_z))}</span></div>')
                        a(
                            f'<div class="kv"><span>{escape(time_lbl)}</span>'
                            f'<span>{escape(_time_of(u))}  {share}%</span></div>'
                        )
                    if sections.warnings:
                        for warn in u.warnings:
                            a(f'<div class="warn">{escape(_warn_line(warn, prefix="! "))}</div>')
                    a("</div>")
    if sections.sign:
        a('<hr class="rule">')
        a(f"<div>{escape(_tr('ticket_sign_op'))}</div>")
        a(f"<div>{escape(_tr('ticket_sign_date'))}</div>")
        a(
            f'<div><span class="box"></span>{escape(_tr("ticket_sign_loaded_html"))}</div>'
        )

    hint = _tr("ticket_print_hint_80")
    return _html_shell(title, css, "\n".join(chunks), auto_print=auto_print, hint=hint)


def report_path_for(
    nc_path: str | Path,
    out_dir: str | Path | None = None,
    *,
    paper: str = PAPER_A4,
    kind: str = "txt",
) -> Path:
    src = Path(nc_path)
    directory = Path(out_dir) if out_dir else src.parent
    paper = normalize_paper(paper)
    if kind == "html":
        suffix = {
            PAPER_A4: "A4.html",
            PAPER_80MM_LOAD: "80mm_load.html",
            PAPER_80MM_SET: "80mm_set.html",
        }.get(paper, "80mm.html")
        return directory / f"{src.stem}_tool_report_{suffix}"
    if paper == PAPER_80MM_LOAD:
        return directory / f"{src.stem}_tool_report_80mm_load.txt"
    if paper == PAPER_80MM_SET:
        return directory / f"{src.stem}_tool_report_80mm_set.txt"
    if paper in {PAPER_80MM, PAPER_80MM_RUN}:
        return directory / f"{src.stem}_tool_report_80mm.txt"
    return directory / f"{src.stem}_tool_report.txt"


def write_report(
    result: ParseResult,
    dest: str | Path | None = None,
    *,
    out_dir: str | Path | None = None,
    papers: str = "both",
    image_paths: list[Path] | None = None,
    lang: str | None = None,
    protected_roots: list[Path] | None = None,
    sections: ReportSections | None = None,
) -> list[Path]:
    """Write text + HTML for A4, 80 mm, or both. Returns paths written."""
    if dest:
        base = Path(dest)
        directory = base.parent
        stem = (
            base.stem.replace("_tool_report_80mm_load", "")
            .replace("_tool_report_80mm_min", "")
            .replace("_tool_report_80mm_set", "")
            .replace("_tool_report_80mm", "")
            .replace("_tool_report", "")
        )
    else:
        directory = Path(out_dir) if out_dir else Path(result.path).parent
        stem = Path(result.path).stem
    refuse_write(directory, protected_roots)
    directory.mkdir(parents=True, exist_ok=True)

    if papers == "both":
        want = {PAPER_A4, PAPER_80MM_RUN}
    else:
        want = {normalize_paper(papers)}
    written: list[Path] = []

    def _write(paper: str) -> None:
        txt = report_path_for(f"{stem}.nc", directory, paper=paper, kind="txt")
        txt.write_text(
            format_report(result, paper=paper, lang=lang, sections=sections),
            encoding="utf-8",
        )
        written.append(txt)
        html = report_path_for(f"{stem}.nc", directory, paper=paper, kind="html")
        html.write_text(
            format_print_html(
                result,
                paper=paper,
                image_paths=image_paths,
                lang=lang,
                sections=sections,
            ),
            encoding="utf-8",
        )
        written.append(html)

    if PAPER_A4 in want:
        _write(PAPER_A4)
    if PAPER_80MM_RUN in want or PAPER_80MM in want:
        _write(PAPER_80MM_RUN)
    if PAPER_80MM_LOAD in want:
        _write(PAPER_80MM_LOAD)
    if PAPER_80MM_SET in want:
        _write(PAPER_80MM_SET)
    return written


def open_print_html(
    result: ParseResult,
    *,
    paper: str = PAPER_A4,
    auto_print: bool = True,
    image_paths: list[Path] | None = None,
    lang: str | None = None,
    sections: ReportSections | None = None,
) -> Path:
    """Write a temp HTML file and open it in the default browser for printing."""
    import tempfile

    kind = normalize_paper(paper)
    stem = Path(result.path).stem or "report"
    tag = {
        PAPER_A4: "A4",
        PAPER_80MM_LOAD: "80mm_load",
        PAPER_80MM_SET: "80mm_set",
    }.get(kind, "80mm")
    path = Path(tempfile.gettempdir()) / f"fh6parse_{stem}_{tag}.html"
    path.write_text(
        format_print_html(
            result,
            paper=paper,
            auto_print=auto_print,
            image_paths=image_paths,
            lang=lang,
            sections=sections,
        ),
        encoding="utf-8",
    )
    webbrowser.open(path.resolve().as_uri())
    return path
