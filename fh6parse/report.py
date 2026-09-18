"""CNC operator tool reports: A4 and 80 mm thermal (text + print HTML)."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
import base64
import textwrap
import webbrowser

from .parser import BangNote, Operation, ParseResult, ToolUsage
from .machtime import RAPID_MM_PER_MIN, format_machine_time


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
PAPER_80MM_MIN = "80mm-min"


def _fmt_time(seconds: float, *, incomplete: bool = False) -> str:
    return format_machine_time(seconds, incomplete=incomplete)


def _time_of(obj: object) -> str:
    return _fmt_time(
        float(getattr(obj, "time_s", 0.0) or 0.0),
        incomplete=bool(getattr(obj, "time_incomplete", False)),
    )


def _seconds_of(obj: object) -> float:
    return float(getattr(obj, "time_s", 0.0) or 0.0)


def _op_cycle(op: Operation) -> tuple[float, bool]:
    total = sum(u.time_s for u in op.usages)
    incomplete = any(u.time_incomplete for u in op.usages)
    return total, incomplete


def _cycle_label(op: Operation) -> str:
    seconds, incomplete = _op_cycle(op)
    return f"Cycle {_fmt_time(seconds, incomplete=incomplete)}"


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
    op: Operation, bar_width: int, *, heading: str = "SHARE"
) -> list[str]:
    if not op.summaries:
        return []
    total, _ = _op_cycle(op)
    rows = [_chart_line(s.tool, s, total, bar_width) for s in op.summaries]
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
        '<p class="cycle-sub">Share of cycle</p>'
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


def _fmt_z(z: float | None) -> str:
    if z is None:
        return "n/a"
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


def _fmt_h(h: int | None) -> str:
    return f"H{h}" if h is not None else ""


def _fmt_d(d: int | None) -> str:
    return f"D{d}" if d is not None else ""


def _units_label(units: str) -> str:
    if units == "mm":
        return "mm (G21)"
    if units == "inch":
        return "inch (G20)"
    return units


def _program_line(result: ParseResult) -> str:
    prog = result.program_number or "(no O-number)"
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
    bc = " ".join(
        p for p in (_fmt_axis("B", u.b), _fmt_axis("C", u.c)) if p
    )
    if bc:
        parts.append(bc)
    h = _fmt_h(u.h_offset)
    if h:
        parts.append(h)
    d = _fmt_d(u.d_offset)
    if d:
        parts.append(d)
    s = _fmt_s(u.s_rpm)
    if s:
        parts.append(s)
    if include_lines:
        parts.append(f"L{u.line_start}-{u.line_end}")
    return "  ".join(parts)


def format_report(
    result: ParseResult,
    *,
    paper: str = PAPER_A4,
    generated: datetime | None = None,
) -> str:
    paper = paper.lower()
    if paper == PAPER_80MM_MIN:
        return _format_text_80mm_min(result, generated=generated)
    if paper == PAPER_80MM:
        return _format_text_80mm(result, generated=generated)
    return _format_text_a4(result, generated=generated)


def _format_text_a4(result: ParseResult, *, generated: datetime | None) -> str:
    now = generated or datetime.now()
    w78 = A4_WIDTH
    lines: list[str] = []
    w = lines.append
    w("CNC TOOL REPORT  |  A4")
    w("=" * w78)
    w(f"File:      {result.filename or result.path}")
    prog = _program_line(result)
    label = "Program:   "
    wrapped = _wrap(prog, w78 - len(label))
    w(label + wrapped[0])
    for part in wrapped[1:]:
        w(" " * len(label) + part)
    w(f"Units:     {_units_label(result.units)}")
    w(f"Generated: {now.strftime('%Y-%m-%d %H:%M')}")
    if result.header_comments:
        w("")
        w("Header notes:")
        for c in result.header_comments:
            for part in _wrap(f"({c})", w78 - 2):
                w(f"  {part}")
    if result.bang_notes:
        w("")
        w("Programmer notes (!):")
        for note in result.bang_notes:
            for part in _wrap(_bang_label(note), w78 - 2):
                w(f"  {part}")

    w("")
    w("Min Z = lowest work Z (G53/G28 ignored).")
    w(
        f"Time ≈ programmed moves + cycles (rapids {RAPID_MM_PER_MIN/1000:.0f} m/min, "
        "no accel). + means missing F or S."
    )
    w("Cycle = that op until M30. The chart under Cycle is each T as a share.")
    w("Each operation is simulated until M30. M97 calls a sub; M99 returns.")
    w("Select a header op by changing M97 P# in main.")
    w("[ ] = loaded")
    ops = result.operations or []
    if not ops:
        w("")
        w("(no operations found)")
    for op in ops:
        w("")
        w("=" * w78)
        for part in _wrap(_op_heading(op), w78):
            w(part)
        w("=" * w78)
        cycle_s, _ = _op_cycle(op)
        w(_cycle_label(op))
        for line in _share_chart_text(op, A4_BAR_WIDTH, heading="Share of cycle"):
            w(line)
        if not op.summaries:
            w("(no tool changes until M30)")
            continue
        w("TOOL LIST (deepest Min Z per T)")
        w("-" * w78)
        for s in op.summaries:
            desc = " / ".join(s.descriptions) if s.descriptions else "(no comment)"
            w(f"[ ] T{s.tool:<4}  Min Z {_fmt_z(s.min_z):>9}  Time {_time_of(s):>7}")
            for part in _wrap(desc, w78 - 4):
                w(f"    {part}")
            for u in s.usages:
                for warn in u.warnings:
                    for part in _wrap(f"WARNING: {warn}", w78 - 6):
                        w(f"      {part}")
        w("")
        w("EACH TOOL CHANGE")
        w("-" * w78)
        for u in op.usages:
            w("")
            share = _pct_of(u, cycle_s)
            for part in _wrap(f"[ ] T{u.tool}  {u.description or '(no comment)'}", w78):
                w(part)
            for part in _wrap(_usage_meta(u), w78 - 4):
                w(f"    {part}")
            bits = f"Min Z {_fmt_z(u.min_z)}"
            if u.min_z_line:
                bits += f"  L{u.min_z_line}"
            bits += f"  Time {_time_of(u)}  {share:3d}%"
            for part in _wrap(bits, w78 - 4):
                w(f"    {part}")
            for warn in u.warnings:
                for part in _wrap(f"WARNING: {warn}", w78 - 4):
                    w(f"    {part}")

    w("")
    w("=" * w78)
    w("Operator: ____________________    Date: ________    Loaded: [ ]")
    w("")
    return "\n".join(lines)


def _format_text_80mm(result: ParseResult, *, generated: datetime | None) -> str:
    """48-column receipt text for 80 mm ESC/POS / generic text driver."""
    now = generated or datetime.now()
    n = THERMAL_WIDTH
    bar = "=" * n
    dash = "-" * n
    lines: list[str] = []
    w = lines.append

    def block(text: str, width: int = n) -> None:
        for part in _wrap(text, width):
            w(part)

    w(bar)
    w("CNC TOOL REPORT")
    w("80 mm")
    w(bar)
    block(result.filename or Path(result.path).name or "file")
    block(_program_line(result))
    w(_units_label(result.units))
    w(now.strftime("%Y-%m-%d %H:%M"))
    for c in result.header_comments[:8]:
        block(f"({c})")
    if result.bang_notes:
        w("! NOTES")
        for note in result.bang_notes:
            block(f"! {_bang_label(note)}")
    w(dash)
    w("MinZ=work Z")
    w(f"Time≈moves {RAPID_MM_PER_MIN/1000:.0f}m/min")
    w("Until M30; M99 returns")
    w("Op = change M97 P#")
    for op in result.operations or []:
        w(dash)
        block(_op_heading(op))
        w(dash)
        cycle_s, _ = _op_cycle(op)
        w(_cycle_label(op))
        for line in _share_chart_text(op, THERMAL_BAR_WIDTH):
            w(line)
        if not op.summaries:
            w("(no tools)")
            continue
        for s in op.summaries:
            desc = " / ".join(s.descriptions) if s.descriptions else "(no comment)"
            w(f"[ ] T{s.tool}")
            block(desc)
            w(f"MinZ {_fmt_z(s.min_z)}  Time {_time_of(s)}")
            for u in s.usages:
                for warn in u.warnings:
                    block(f"! {warn}")
            w(dash)
        w("EACH CHANGE")
        w(dash)
        for u in op.usages:
            share = _pct_of(u, cycle_s)
            w(f"[ ] T{u.tool}")
            block(u.description or "(no comment)")
            block(_usage_meta(u, include_lines=False))
            minz = f"MinZ {_fmt_z(u.min_z)}"
            if u.min_z_line:
                minz += f" L{u.min_z_line}"
            w(f"{minz}  Time {_time_of(u)}  {share:3d}%")
            for warn in u.warnings:
                block(f"! {warn}")
            w(dash)

    w("Op: ________")
    w("Date: ______")
    w("Loaded: [ ]")
    w(bar)
    w("")
    return "\n".join(lines)


def _format_text_80mm_min(result: ParseResult, *, generated: datetime | None) -> str:
    """48-column ticket: per operation T, description, min Z, warnings."""
    now = generated or datetime.now()
    n = THERMAL_WIDTH
    bar = "=" * n
    dash = "-" * n
    lines: list[str] = []
    w = lines.append

    def block(text: str, width: int = n) -> None:
        for part in _wrap(text, width):
            w(part)

    w(bar)
    w("CNC TOOLS MIN")
    w("80 mm")
    w(bar)
    block(result.filename or Path(result.path).name or "file")
    block(_program_line(result))
    w(_units_label(result.units))
    w(now.strftime("%Y-%m-%d %H:%M"))
    if result.bang_notes:
        w("! NOTES")
        for note in result.bang_notes:
            block(f"! {_bang_label(note)}")
    w(dash)
    for op in result.operations or []:
        w(dash)
        block(_op_heading(op))
        w(dash)
        w(_cycle_label(op))
        for line in _share_chart_text(op, THERMAL_BAR_WIDTH):
            w(line)
        if not op.summaries:
            w("(no tools)")
            continue
        for s in op.summaries:
            desc = " / ".join(s.descriptions) if s.descriptions else "(no comment)"
            w(f"T{s.tool}")
            block(desc)
            w(f"MinZ {_fmt_z(s.min_z)}")
            for u in s.usages:
                for warn in u.warnings:
                    block(f"! {warn}")
            w(dash)

    w("Op: ________")
    w("Date: ______")
    w("Loaded: [ ]")
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
) -> str:
    paper = paper.lower()
    if paper in (PAPER_80MM, PAPER_80MM_MIN):
        return _html_80mm(
            result,
            generated=generated,
            auto_print=auto_print,
            image_paths=image_paths,
            short=paper == PAPER_80MM_MIN,
        )
    return _html_a4(
        result,
        generated=generated,
        auto_print=auto_print,
        image_paths=image_paths,
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
        parts.append(
            f'<img class="step-view" alt="STEP isometric" '
            f'src="data:image/png;base64,{b64}">'
        )
    if not parts:
        return ""
    return '<div class="step-views">' + "".join(parts) + "</div>"


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
<html lang="en">
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
  <button type="button" onclick="window.print()">Print</button>
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
) -> str:
    now = generated or datetime.now()
    title = f"Tool report {_program_line(result)}"
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
    if result.header_comments:
        items = "".join(f"<li>({escape(c)})</li>" for c in result.header_comments)
        notes = f'<ul class="notes">{items}</ul>'
    if result.bang_notes:
        items = "".join(
            f"<li>{escape(_bang_label(note))}</li>" for note in result.bang_notes
        )
        notes += f'<h2>Programmer notes (!)</h2><ul class="notes">{items}</ul>'

    op_html: list[str] = []
    if not result.operations:
        op_html.append("<p>(no operations found)</p>")
    for op in result.operations:
        cycle_s, _ = _op_cycle(op)
        setup_rows = []
        if not op.summaries:
            setup_rows.append('<tr><td colspan="6">(no tool changes until M30)</td></tr>')
        for s in op.summaries:
            desc = escape(" / ".join(s.descriptions) if s.descriptions else "(no comment)")
            warns = "".join(
                f'<div class="warn">WARNING: {escape(w)}</div>'
                for u in s.usages
                for w in u.warnings
            )
            setup_rows.append(
                "<tr>"
                f'<td class="c"><span class="box"></span></td>'
                f"<td>T{s.tool}</td>"
                f"<td>{desc}{warns}</td>"
                f'<td class="n">{escape(_fmt_z(s.min_z))}</td>'
                f'<td class="n">{escape(_time_of(s))}</td>'
                f'<td class="c"><span class="box"></span></td>'
                "</tr>"
            )
        change_rows = []
        if not op.usages:
            change_rows.append('<tr><td colspan="8">(no Txx M6)</td></tr>')
        for u in op.usages:
            extra = "".join(
                f'<div class="warn">WARNING: {escape(warn)}</div>' for warn in u.warnings
            )
            bc = " ".join(p for p in (_fmt_axis("B", u.b), _fmt_axis("C", u.c)) if p) or "—"
            share = _pct_of(u, cycle_s)
            change_rows.append(
                "<tr>"
                f'<td class="c"><span class="box"></span></td>'
                f"<td>T{u.tool}</td>"
                f"<td>{escape(u.description or '(no comment)')}{extra}</td>"
                f"<td>{escape(u.subprogram)}</td>"
                f"<td>{escape(bc)}</td>"
                f"<td>{escape(' '.join(p for p in (_fmt_h(u.h_offset), _fmt_d(u.d_offset), _fmt_s(u.s_rpm)) if p) or '—')}</td>"
                f'<td class="n">{escape(_fmt_z(u.min_z))}</td>'
                f'<td class="n">{escape(_time_of(u))}  {share}%</td>'
                "</tr>"
            )
        op_html.append(f"<h2>{escape(_op_heading(op))}</h2>")
        op_html.append(f'<p class="cycle">{escape(_cycle_label(op))}</p>')
        op_html.append(_share_chart_html(op))
        op_html.append(
            "<table><thead><tr>"
            '<th class="c">Load</th><th>T</th><th>Description</th>'
            '<th class="n">Min Z</th><th class="n">Time</th><th class="c">OK</th>'
            "</tr></thead><tbody>"
            + "".join(setup_rows)
            + "</tbody></table>"
        )
        op_html.append("<h3>Each tool change</h3>")
        op_html.append(
            "<table><thead><tr>"
            '<th class="c">Load</th><th>T</th><th>Description</th><th>Sub</th>'
            '<th>B/C</th><th>H / D / S</th><th class="n">Min Z</th>'
            '<th class="n">Time</th>'
            "</tr></thead><tbody>"
            + "".join(change_rows)
            + "</tbody></table>"
        )

    body = f"""
<h1>CNC tool report</h1>
{_step_views_html(image_paths)}
<div class="meta">
  <b>File</b><span>{escape(result.filename or result.path)}</span>
  <b>Units</b><span>{escape(_units_label(result.units))}</span>
  <b>Program</b><span>{escape(_program_line(result))}</span>
  <b>Printed</b><span>{escape(now.strftime("%Y-%m-%d %H:%M"))}</span>
</div>
{notes}
<p class="fine">Min Z is lowest work-coordinate Z (G53/G28 ignored).
Time is programmed motion and canned cycles (approx; rapids
{escape(f"{RAPID_MM_PER_MIN/1000:.0f}")} m/min; no accel). Cycle is the sum for
that operation until M30. The chart under Cycle is each T as a share of that
cycle. Each Txx M6 also shows its own %. A trailing + means missing F or S.
Each operation is simulated until M30 (M97 calls a sub, M99 returns).
Select a header op by changing M97 P# in main.</p>
{"".join(op_html)}
<div class="sign">
  <div class="line">Operator</div>
  <div class="line">Date</div>
  <div class="line">Tools loaded</div>
</div>
"""
    hint = "Print dialog: A4, portrait, 100% scale, headers and footers off."
    return _html_shell(title, css, body, auto_print=auto_print, hint=hint)


def _html_80mm(
    result: ParseResult,
    *,
    generated: datetime | None,
    auto_print: bool,
    image_paths: list[Path] | None = None,
    short: bool = False,
) -> str:
    now = generated or datetime.now()
    title = f"{'80mm min' if short else '80mm'} {_program_line(result)}"
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
    a(f"<h1>{'CNC TOOLS MIN' if short else 'CNC TOOLS'}</h1>")
    a(f'<div class="center">80 mm</div>')
    views = _step_views_html(image_paths)
    if views:
        a(views)
    a(f'<div class="d">{escape(result.filename or result.path)}</div>')
    a(f'<div class="d">{escape(_program_line(result))}</div>')
    a(f"<div>{escape(_units_label(result.units))} · {escape(now.strftime('%Y-%m-%d %H:%M'))}</div>")
    for c in result.header_comments[:8]:
        a(f'<div class="d">({escape(c)})</div>')
    if result.bang_notes:
        a('<div class="warn">! NOTES</div>')
        for note in result.bang_notes:
            a(f'<div class="warn d">! {escape(_bang_label(note))}</div>')
    a('<hr class="rule">')
    a("<div>Min Z = work Z</div>")
    a(f"<div>Time ≈ moves {RAPID_MM_PER_MIN/1000:.0f} m/min</div>")
    if not short:
        a("<div>Until M30; M99 returns</div>")
        a("<div>Op = change M97 P#</div>")
    if not result.operations:
        a("<div>(no operations)</div>")
    for op in result.operations:
        cycle_s, _ = _op_cycle(op)
        a('<hr class="rule">')
        a(f'<div class="tline d">{escape(_op_heading(op))}</div>')
        a(f'<div class="cycle">{escape(_cycle_label(op))}</div>')
        chart = _share_chart_pre(op, THERMAL_BAR_WIDTH)
        if chart:
            a(chart)
        if not op.summaries:
            a("<div>(no tools)</div>")
            continue
        for s in op.summaries:
            desc = " / ".join(s.descriptions) if s.descriptions else "(no comment)"
            a('<div class="tool">')
            if short:
                a(f'<div class="tline">T{s.tool}</div>')
            else:
                a(f'<div class="tline"><span class="box"></span>T{s.tool}</div>')
            a(f'<div class="d">{escape(desc)}</div>')
            a(f'<div class="kv"><span>Min Z</span><span>{escape(_fmt_z(s.min_z))}</span></div>')
            if not short:
                a(f'<div class="kv"><span>Time</span><span>{escape(_time_of(s))}</span></div>')
            for u in s.usages:
                for warn in u.warnings:
                    a(f'<div class="warn">! {escape(warn)}</div>')
            a("</div>")
        if short:
            continue
        a('<div class="tline">EACH CHANGE</div>')
        for u in op.usages:
            share = _pct_of(u, cycle_s)
            a('<div class="tool">')
            a(f'<div class="tline"><span class="box"></span>T{u.tool}</div>')
            a(f'<div class="d">{escape(u.description or "(no comment)")}</div>')
            a(f'<div class="d">{escape(_usage_meta(u, include_lines=False))}</div>')
            a(f'<div class="kv"><span>Min Z</span><span>{escape(_fmt_z(u.min_z))}</span></div>')
            a(
                f'<div class="kv"><span>Time</span>'
                f'<span>{escape(_time_of(u))}  {share}%</span></div>'
            )
            for warn in u.warnings:
                a(f'<div class="warn">! {escape(warn)}</div>')
            a("</div>")
    a('<hr class="rule">')
    a("<div>Op: ____________</div>")
    a("<div>Date: __________</div>")
    a('<div><span class="box"></span>Loaded</div>')

    hint = (
        "Print dialog: select the 80 mm printer, paper 80 mm, 100% scale, "
        "headers/footers off, do not fit to A4."
    )
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
    paper = paper.lower()
    if kind == "html":
        suffix = "A4.html" if paper == PAPER_A4 else "80mm.html"
        return directory / f"{src.stem}_tool_report_{suffix}"
    if paper == PAPER_80MM_MIN:
        return directory / f"{src.stem}_tool_report_80mm_min.txt"
    if paper == PAPER_80MM:
        return directory / f"{src.stem}_tool_report_80mm.txt"
    return directory / f"{src.stem}_tool_report.txt"


def write_report(
    result: ParseResult,
    dest: str | Path | None = None,
    *,
    out_dir: str | Path | None = None,
    papers: str = "both",
    image_paths: list[Path] | None = None,
) -> list[Path]:
    """Write text + HTML for A4, 80 mm, or both. Returns paths written."""
    if dest:
        base = Path(dest)
        directory = base.parent
        stem = (
            base.stem.replace("_tool_report_80mm_min", "")
            .replace("_tool_report_80mm", "")
            .replace("_tool_report", "")
        )
    else:
        directory = Path(out_dir) if out_dir else Path(result.path).parent
        stem = Path(result.path).stem
    directory.mkdir(parents=True, exist_ok=True)

    want = {PAPER_A4, PAPER_80MM} if papers == "both" else {papers.lower()}
    written: list[Path] = []
    if PAPER_A4 in want:
        a4_txt = directory / f"{stem}_tool_report.txt"
        a4_txt.write_text(format_report(result, paper=PAPER_A4), encoding="utf-8")
        a4_html = directory / f"{stem}_tool_report_A4.html"
        a4_html.write_text(
            format_print_html(result, paper=PAPER_A4, image_paths=image_paths),
            encoding="utf-8",
        )
        written.extend([a4_txt, a4_html])
    if PAPER_80MM in want:
        mm_txt = directory / f"{stem}_tool_report_80mm.txt"
        mm_txt.write_text(format_report(result, paper=PAPER_80MM), encoding="utf-8")
        mm_html = directory / f"{stem}_tool_report_80mm.html"
        mm_html.write_text(
            format_print_html(result, paper=PAPER_80MM, image_paths=image_paths),
            encoding="utf-8",
        )
        written.extend([mm_txt, mm_html])
    if PAPER_80MM_MIN in want:
        min_txt = directory / f"{stem}_tool_report_80mm_min.txt"
        min_txt.write_text(format_report(result, paper=PAPER_80MM_MIN), encoding="utf-8")
        written.append(min_txt)
    return written


def open_print_html(
    result: ParseResult,
    *,
    paper: str = PAPER_A4,
    auto_print: bool = True,
    image_paths: list[Path] | None = None,
) -> Path:
    """Write a temp HTML file and open it in the default browser for printing."""
    import tempfile

    paper = paper.lower()
    stem = Path(result.path).stem or "report"
    tag = "A4" if paper == PAPER_A4 else ("80mm_min" if paper == PAPER_80MM_MIN else "80mm")
    path = Path(tempfile.gettempdir()) / f"fh6parse_{stem}_{tag}.html"
    path.write_text(
        format_print_html(
            result, paper=paper, auto_print=auto_print, image_paths=image_paths
        ),
        encoding="utf-8",
    )
    webbrowser.open(path.resolve().as_uri())
    return path
