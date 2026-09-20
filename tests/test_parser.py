"""Parser fixtures against the three sample CNC programs."""

from __future__ import annotations

import unittest
from pathlib import Path

from fh6parse.parser import parse_nc_file, parse_nc_text
from fh6parse.report import (
    PAPER_80MM,
    PAPER_80MM_MIN,
    PAPER_80MM_SET,
    PAPER_A4,
    THERMAL_WIDTH,
    format_print_html,
    format_report,
)


SAMPLES = Path(__file__).resolve().parent / "samples"


def _by_tool(usages, tool: int):
    return [u for u in usages if u.tool == tool]


def _called(usages):
    return [u for u in usages if u.called_from_main]


def _uncalled(usages):
    return [u for u in usages if not u.called_from_main]


class TestD0134078(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = parse_nc_file(SAMPLES / "D0134078.nc")

    def test_header(self) -> None:
        self.assertEqual(self.result.program_number, "O04078")
        self.assertEqual(self.result.program_title, "D0134078")
        self.assertEqual(self.result.units, "mm")

    def test_tools_and_min_z(self) -> None:
        self.assertEqual([u.tool for u in self.result.usages], [15, 26])
        t15, t26 = self.result.usages
        self.assertEqual(t15.description, "ZDERZAK FI10")
        self.assertEqual(t15.min_z, 0.0)
        self.assertTrue(t15.called_from_main)
        self.assertEqual(t26.description, "FREZ FI12")
        self.assertEqual(t26.min_z, -11.5)
        self.assertTrue(t26.called_from_main)

    def test_g53_machine_z_ignored(self) -> None:
        t26 = self.result.usages[1]
        self.assertEqual(t26.min_z, -11.5)
        self.assertNotEqual(t26.min_z, 0.0)

    def test_preselect_t_is_not_a_change(self) -> None:
        self.assertEqual(len(self.result.usages), 2)


class TestSE0241282(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = parse_nc_file(SAMPLES / "SE0241282.nc")

    def test_cycle_bottoms(self) -> None:
        called = {s.tool: s for s in self.result.called_summaries}
        self.assertAlmostEqual(called[3].min_z, -32.803)
        self.assertAlmostEqual(called[7].min_z, -33.404)
        self.assertEqual(called[1].min_z, 26.0)
        self.assertAlmostEqual(called[15].min_z, 26.65)

    def test_goto_skips_second_t15_chamfer(self) -> None:
        t15 = _by_tool(self.result.usages, 15)
        self.assertEqual(len(t15), 3)
        self.assertTrue(t15[0].called_from_main)
        self.assertFalse(t15[1].called_from_main)
        self.assertTrue(t15[2].called_from_main)
        self.assertIsNone(t15[1].min_z)

    def test_probe_not_called(self) -> None:
        t20 = _by_tool(self.result.usages, 20)
        self.assertEqual(len(t20), 1)
        self.assertFalse(t20[0].called_from_main)
        self.assertIsNone(t20[0].min_z)
        self.assertIn("SONDA", t20[0].description)
        self.assertNotIn(20, {s.tool for s in self.result.called_summaries})

    def test_n900_tools_called(self) -> None:
        tools = {s.tool for s in self.result.called_summaries}
        self.assertTrue({9, 10, 11}.issubset(tools))

    def test_header_n60_is_own_operation(self) -> None:
        ops = {op.n: op for op in self.result.operations}
        self.assertIn(60, ops)
        self.assertIn(None, ops)
        self.assertEqual({s.tool for s in ops[60].summaries}, {20})
        self.assertNotIn(20, {s.tool for s in ops[None].summaries})
        from fh6parse.parser import NO_FEED_WARN

        t20 = [u for u in ops[60].usages if u.tool == 20][0]
        self.assertIn(NO_FEED_WARN, t20.warnings)


class Test000814086(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = parse_nc_file(SAMPLES / "000814086.nc")

    def test_op1_depths(self) -> None:
        called = {s.tool: s for s in self.result.called_summaries}
        self.assertEqual(called[10].min_z, -35.5)
        self.assertEqual(called[18].min_z, -35.5)
        self.assertEqual(called[1].min_z, -18.5)
        self.assertEqual(called[23].min_z, -2.0)
        self.assertEqual(called[24].min_z, 0.0)
        self.assertAlmostEqual(called[73].min_z, -14.545)

    def test_h_mismatch_warning(self) -> None:
        t10 = _by_tool(_called(self.result.usages), 10)[0]
        self.assertEqual(t10.h_offset, 25)
        self.assertEqual(t10.d_offset, 25)
        self.assertTrue(any("H25" in w for w in t10.warnings))
        self.assertTrue(any("D25" in w for w in t10.warnings))

    def test_op2_is_separate_operation(self) -> None:
        ops = {op.n: op for op in self.result.operations}
        self.assertIn(10, ops)
        self.assertIn(20, ops)
        op1_tools = {s.tool for s in ops[10].summaries}
        op2_tools = {s.tool for s in ops[20].summaries}
        self.assertIn(10, op1_tools)
        self.assertNotIn(10, op2_tools)
        op2 = [u for u in ops[20].usages if u.subprogram == "N20"]
        self.assertTrue(op2)
        t23_op2 = [u for u in ops[20].usages if u.tool == 23][0]
        self.assertEqual(t23_op2.min_z, -19.0)
        t24_op2 = [u for u in ops[20].usages if u.tool == 24][0]
        self.assertEqual(t24_op2.min_z, -17.0)

    def test_g53_z63_never_wins(self) -> None:
        for u in self.result.usages:
            if u.min_z is not None:
                self.assertLess(u.min_z, 63.5)

    def test_preselect_not_counted(self) -> None:
        # T10 and T1 appear as preselect after other tools; only M6 counts.
        self.assertGreater(len(_by_tool(self.result.usages, 10)), 0)
        t_numbers_in_order = [u.tool for u in self.result.usages]
        self.assertEqual(t_numbers_in_order[1], 10)


class TestSyntheticRules(unittest.TestCase):
    def test_comment_z_ignored(self) -> None:
        src = """
O1 (TEST)
T1 M6
G90
G43 Z60. H1
G81 Z26. (Z25.538) R33. F40.
G80
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertEqual(r.usages[0].min_z, 26.0)

    def test_g53_ignored(self) -> None:
        src = """
O1
T1 M6
G90
G43 Z15. H1
G1 Z-5.
G53 G0 Z63.5
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertEqual(r.usages[0].min_z, -5.0)

    def test_preselect_t_without_m6(self) -> None:
        src = """
O1
T24 M6
G90
G43 Z15. H24
T10
G1 Z0.
T10 M6
G43 Z15. H10
G1 Z-35.5
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertEqual([u.tool for u in r.usages], [24, 10])
        self.assertEqual(r.usages[0].min_z, 0.0)
        self.assertEqual(r.usages[1].min_z, -35.5)

    def test_g91_incremental_z(self) -> None:
        src = """
O1
T1 M6
G90
G43 Z10. H1
G1 Z0.
G91
G1 Z-2.
G1 Z-3.
G90
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertEqual(r.usages[0].min_z, -5.0)

    def test_goto_skips_tool(self) -> None:
        src = """
O1
T1 M6
G90 G1 Z-1.
GOTO20
T2 M6
G1 Z-99.
N20
T3 M6
G1 Z-4.
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertEqual([u.tool for u in r.usages], [1, 2, 3])
        self.assertTrue(r.usages[0].called_from_main)
        self.assertFalse(r.usages[1].called_from_main)
        self.assertTrue(r.usages[2].called_from_main)
        self.assertIsNone(r.usages[1].min_z)
        self.assertNotIn(2, {s.tool for s in r.called_summaries})

    def test_header_ops_m97_swap_until_m30(self) -> None:
        src = """
O1 (TEST OPS)
(N5 - FIRST)
(N7 - SECOND)
G90
M97 P5
M30
N5 (FIRST)
T1 M6
G1 Z-1.
M97 P99
M99
N7 (SECOND)
T2 M6
G1 Z-2.
M99
N99 (HELPER)
T3 M6
G1 Z-3.
M99
"""
        r = parse_nc_text(src, "t.nc")
        ops = {op.n: op for op in r.operations}
        self.assertEqual(set(ops), {5, 7})
        self.assertEqual({s.tool for s in ops[5].summaries}, {1, 3})
        self.assertEqual({s.tool for s in ops[7].summaries}, {2})
        self.assertEqual(ops[5].call, "M97 P5")
        self.assertEqual(ops[7].call, "M97 P7")
        z1 = {s.tool: s.min_z for s in ops[5].summaries}
        self.assertEqual(z1[1], -1.0)
        self.assertEqual(z1[3], -3.0)


class TestDOffsetMismatch(unittest.TestCase):
    def test_g43_wrong_d_warns(self) -> None:
        src = """O1
T1 M6
G43 Z10. H1 D99
G1 Z-1.
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.d_offset, 99)
        self.assertIn("D99 does not match T1", u.warnings)
        self.assertFalse(any(w.startswith("H") for w in u.warnings))

    def test_g41_wrong_d_warns(self) -> None:
        src = """O1
T2 M6
G43 Z10. H2
G41 D50 X0.
G1 Z-1.
G40
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.d_offset, 50)
        self.assertIn("D50 does not match T2", u.warnings)

    def test_g42_wrong_d_warns(self) -> None:
        src = """O1
T3 M6
G43 Z10. H3
G42 D8 X0.
G1 Z-1.
G40
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.d_offset, 8)
        self.assertIn("D8 does not match T3", u.warnings)

    def test_matching_d_does_not_warn(self) -> None:
        src = """O1
T4 M6
G43 Z10. H4 D4
G41 D4 X0.
G1 Z-1.
G40
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.d_offset, 4)
        self.assertEqual(u.warnings, [])

    def test_wrong_d_on_g43_and_g41_is_one_warning(self) -> None:
        src = """O1
T5 M6
G43 Z10. H5 D9
G41 D9 X0.
G1 Z-1.
G40
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        d_warns = [w for w in u.warnings if w.startswith("D")]
        self.assertEqual(d_warns, ["D9 does not match T5"])

    def test_report_prints_d_mismatch(self) -> None:
        src = """O1
T1 M6
G43 Z10. H1 D99
G41 D99 X0.
G1 Z-1.
G40
M30
"""
        text = format_report(parse_nc_text(src, "t.nc"))
        self.assertIn("WARNING: D99 does not match T1", text)


class TestCommentsAndG95(unittest.TestCase):
    def test_comment_below_t_m6_joins_description(self) -> None:
        src = """O1
T1 M6 (WIERTO)
(FI 8.5 x 30)
G43 Z10. H1
G1 Z-1.
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.description, "WIERTO / FI 8.5 x 30")

    def test_comment_below_skipped_if_code_in_between(self) -> None:
        src = """O1
T1 M6
G0 X0.
(TOO LATE)
G43 Z10. H1
G1 Z-1.
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.description, "")

    def test_bang_notes_collected_and_printed(self) -> None:
        src = """O1
(REV 1)
T1 M6
G0 X0. (! CHECK CLAMP)
G1 Z-1. (normal)
( ! OIL HOLE )
M30
"""
        r = parse_nc_text(src, "t.nc")
        texts = [n.text for n in r.bang_notes]
        self.assertEqual(texts, ["! CHECK CLAMP", "! OIL HOLE"])
        self.assertEqual(r.bang_notes[0].line, 4)
        a4 = format_report(r)
        self.assertIn("Programmer notes (!):", a4)
        self.assertIn("! CHECK CLAMP", a4)
        mm = format_report(r, paper=PAPER_80MM_SET)
        self.assertIn("! NOTES", mm)
        self.assertIn("! OIL HOLE", mm)
        load = format_report(r, paper=PAPER_80MM_MIN)
        self.assertNotIn("! NOTES", load)

    def test_g95_warns_on_next_tool_until_g94(self) -> None:
        src = """O1
T1 M6
G95 G1 Z-5. F0.2
T2 M6
G43 Z10. H2
G1 Z-1.
G94
T3 M6
G43 Z10. H3
G1 Z-2.
M30
"""
        r = parse_nc_text(src, "t.nc")
        from fh6parse.parser import G95_NEXT_WARN, G95_END_WARN

        self.assertEqual(r.usages[0].warnings, [])
        self.assertIn(G95_NEXT_WARN, r.usages[1].warnings)
        self.assertNotIn(G95_END_WARN, r.usages[1].warnings)
        self.assertEqual(r.usages[2].warnings, [])

    def test_g95_on_same_line_as_next_t_does_not_warn_if_g94(self) -> None:
        src = """O1
T1 M6
G95
T2 M6 G94
G1 Z-1.
M30
"""
        r = parse_nc_text(src, "t.nc")
        from fh6parse.parser import G95_NEXT_WARN

        self.assertNotIn(G95_NEXT_WARN, r.usages[1].warnings)

    def test_g95_left_on_at_m30(self) -> None:
        src = """O1
T1 M6
G95 G1 Z-5. F0.2
M30
"""
        r = parse_nc_text(src, "t.nc")
        from fh6parse.parser import G95_END_WARN

        self.assertIn(G95_END_WARN, r.usages[0].warnings)
        self.assertIn("WARNING: G95 still active at M30", format_report(r))


class TestSplitTM6(unittest.TestCase):
    def test_t_then_m6_counts_as_tool_change(self) -> None:
        src = """O1
T12
M6
G90 G43 Z10. H12
G1 Z-2. F100
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertEqual([u.tool for u in r.usages], [12])
        self.assertTrue(r.usages[0].called_from_main)
        self.assertEqual(r.usages[0].min_z, -2.0)
        self.assertEqual(r.usages[0].h_offset, 12)

    def test_comment_on_t_line_joins_split_m6(self) -> None:
        src = """O1
T12 (FREZ FI12)
M6
G43 Z10. H12
G1 Z-1. F100
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.tool, 12)
        self.assertEqual(u.description, "FREZ FI12")

    def test_comment_above_t_joins_split_m6(self) -> None:
        src = """O1
(FREZ FI12)
T12
M6
G43 Z10. H12
G1 Z-1. F100
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.description, "FREZ FI12")

    def test_comment_below_split_m6_joins(self) -> None:
        src = """O1
T1
M6 (WIERTO)
(FI 8.5 x 30)
G43 Z10. H1
G1 Z-1.
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.description, "WIERTO / FI 8.5 x 30")

    def test_preselect_t_not_a_change_until_m6(self) -> None:
        src = """O1
T1 M6
G43 Z10. H1
G1 Z-1. F100
T2
G1 X10. F100
T2 M6
G43 Z10. H2
G1 Z-3. F100
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertEqual([u.tool for u in r.usages], [1, 2])
        self.assertEqual(r.usages[0].min_z, -1.0)
        self.assertEqual(r.usages[1].min_z, -3.0)

    def test_m6_without_any_t_is_not_a_tool(self) -> None:
        src = """O1
G90
M6
G1 Z-1. F100
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertEqual(r.usages, [])

    def test_split_t_hash_m6_uses_assign_comment(self) -> None:
        src = """O1
#100=12 (Frez fi12)
T#100
M6
G43 Z10. H#100
G1 Z-1. F100
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.tool, 12)
        self.assertEqual(u.tool_hash, 100)
        self.assertEqual(u.description, "Frez fi12")
        self.assertEqual(u.h_offset, 12)


class TestReport(unittest.TestCase):
    def test_report_contains_operator_sections(self) -> None:
        r = parse_nc_file(SAMPLES / "D0134078.nc")
        text = format_report(r)
        self.assertIn("CNC TOOL REPORT", text)
        self.assertIn("TOOL LIST", text)
        self.assertIn("EACH TOOL CHANGE", text)
        self.assertIn("T15", text)
        self.assertIn("T26", text)
        self.assertIn("-11.500", text)
        self.assertIn("ZDERZAK FI10", text)
        self.assertIn("Operator:", text)
        self.assertNotIn("Reach", text)

    def test_report_splits_ops(self) -> None:
        r = parse_nc_file(SAMPLES / "000814086.nc")
        text = format_report(r)
        self.assertIn("OP1  (N10)", text)
        self.assertIn("OP2  (N20)", text)
        self.assertIn("M97 P10", text)
        self.assertIn("M97 P20", text)
        self.assertNotIn("Reach", text)

    def test_80mm_text_fits_thermal_width(self) -> None:
        r = parse_nc_file(SAMPLES / "000814086.nc")
        text = format_report(r, paper=PAPER_80MM)
        self.assertIn("80 mm", text)
        self.assertIn("T10", text)
        for line in text.splitlines():
            self.assertLessEqual(
                len(line),
                THERMAL_WIDTH,
                msg=f"line too wide for 80mm ({len(line)}): {line!r}",
            )

    def test_print_html_page_sizes(self) -> None:
        r = parse_nc_file(SAMPLES / "D0134078.nc")
        a4 = format_print_html(r, paper=PAPER_A4)
        mm = format_print_html(r, paper=PAPER_80MM)
        self.assertIn("size: A4", a4)
        self.assertIn("size: 80mm", mm)
        self.assertIn("T15", a4)
        self.assertIn("T26", mm)
        self.assertIn("ZDERZAK FI10", a4)
        self.assertIn("window.print", a4 + mm)

    def test_80mm_min_is_short_and_fits_width(self) -> None:
        r = parse_nc_file(SAMPLES / "000814086.nc")
        text = format_report(r, paper=PAPER_80MM_MIN)
        self.assertIn("CNC TOOLS LOAD", text)
        self.assertIn("OP1  (N10)", text)
        self.assertIn("OP2  (N20)", text)
        self.assertIn("MinZ", text)
        self.assertIn("T10", text)
        self.assertNotIn("EACH CHANGE", text)
        self.assertNotIn("EACH TOOL CHANGE", text)
        for line in text.splitlines():
            self.assertLessEqual(
                len(line),
                THERMAL_WIDTH,
                msg=f"line too wide for 80mm-min ({len(line)}): {line!r}",
            )

    def test_80mm_min_shows_hds_and_mismatch_flags(self) -> None:
        src = """O1
T1 M6
G43 Z10. H1 D99
S1200
G1 Z-1. F100
M30
"""
        r = parse_nc_text(src, "t.nc")
        text = format_report(r, paper=PAPER_80MM_MIN)
        self.assertIn("T1", text)
        self.assertIn("H1", text)
        self.assertIn("D99", text)
        self.assertIn("S1200", text)
        self.assertIn("! D99 does not match T1", text)
        self.assertNotIn("EACH CHANGE", text)
        html = format_print_html(r, paper=PAPER_80MM_MIN)
        self.assertIn("H1", html)
        self.assertIn("D99", html)
        self.assertIn("S1200", html)
        self.assertIn("D99 does not match T1", html)

    def test_80mm_set_and_run_section_sets(self) -> None:
        r = parse_nc_file(SAMPLES / "000814086.nc")
        sett = format_report(r, paper=PAPER_80MM_SET)
        run = format_report(r, paper=PAPER_80MM)
        load = format_report(r, paper=PAPER_80MM_MIN)
        self.assertIn("CNC TOOLS SET", sett)
        self.assertNotIn("EACH CHANGE", sett)
        self.assertNotIn("SHARE", sett)
        self.assertIn("Cycle", sett)
        self.assertIn("EACH CHANGE", run)
        self.assertIn("SHARE", run)
        self.assertNotIn("Cycle", load)
        self.assertNotIn("EACH CHANGE", load)
        for paper_text in (sett, run, load):
            for line in paper_text.splitlines():
                self.assertLessEqual(len(line), THERMAL_WIDTH, msg=repr(line))

    def test_80mm_min_flags_g95_left_on(self) -> None:
        src = """O1
T1 M6
G95 G1 Z-5. F0.2
M30
"""
        text = format_report(parse_nc_text(src, "t.nc"), paper=PAPER_80MM_MIN)
        self.assertIn("G95", text)
        self.assertIn("set G94", text)
        self.assertNotIn("EACH CHANGE", text)


class TestProgrammedPath(unittest.TestCase):
    def test_while_incremental_z(self) -> None:
        src = """O1
T1 M6
G90 G94
G0 X0 Y0 Z0
#100=0
WHILE [#100 LT 4] DO1
#100=#100+1
G91 G1 Z-1. F100
G90
END1
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.min_z, -4.0)
        self.assertAlmostEqual(u.time_s, 2.4, places=3)

    def test_if_goto_skips_tool_min_z(self) -> None:
        src = """O1
T1 M6
G90 G1 Z-1. F100
#100=1
IF [#100 EQ 1] GOTO 20
T2 M6
G1 Z-99. F100
N20
T3 M6
G1 Z-4. F100
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertTrue(r.usages[0].called_from_main)
        self.assertFalse(r.usages[1].called_from_main)
        self.assertTrue(r.usages[2].called_from_main)
        self.assertIsNone(r.usages[1].min_z)
        self.assertEqual(r.usages[2].min_z, -4.0)

    def test_m97_l_repeats_sub(self) -> None:
        src = """O1
T1 M6
G90 G94 G0 X0 Y0 Z0
M97 P100 L3
M30
N100
G91 G1 Z-1. F60
G90
M99
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.min_z, -3.0)
        self.assertAlmostEqual(u.time_s, 3.0, places=3)

    def test_g81_l_g90_repeats_same_xy(self) -> None:
        one = """O1
T1 M6
G90 G94 G0 X0 Y0 Z50
G98 G81 X0 Y0 Z26 R33 F40
G80
M30
"""
        eight = """O1
T1 M6
G90 G94 G0 X0 Y0 Z50
G98 G81 X0 Y0 Z26 R33 L8 F40
G80
M30
"""
        t1 = parse_nc_text(one, "t.nc").usages[0]
        t8 = parse_nc_text(eight, "t.nc").usages[0]
        self.assertEqual(t1.min_z, 26.0)
        self.assertEqual(t8.min_z, 26.0)
        self.assertAlmostEqual(t8.time_s / t1.time_s, 8.0, delta=0.35)

    def test_g81_l_g91_steps_xy(self) -> None:
        src = """O1
T1 M6
G90 G94 G0 X0 Y0 Z10
G91 G98 G81 X10. Y0. Z-12. R-8. L8 F300
G80
M30
"""
        listed = """O1
T1 M6
G90 G94 G0 X0 Y0 Z10
G91 G98 G81 X10. Y0. Z-12. R-8. F300
X10.
X10.
X10.
X10.
X10.
X10.
X10.
G80
M30
"""
        one = """O1
T1 M6
G90 G94 G0 X0 Y0 Z10
G91 G98 G81 X10. Y0. Z-12. R-8. F300
G80
M30
"""
        u_l = parse_nc_text(src, "t.nc").usages[0]
        u_xy = parse_nc_text(listed, "t.nc").usages[0]
        u_one = parse_nc_text(one, "t.nc").usages[0]
        self.assertAlmostEqual(u_l.min_z, u_xy.min_z)
        self.assertAlmostEqual(u_l.time_s, u_xy.time_s, places=2)
        self.assertGreater(u_l.time_s, u_one.time_s)


class TestParametricTools(unittest.TestCase):
    def test_t_hash_resolves_and_uses_assign_comment(self) -> None:
        src = """O1 (TEST)
G90 G21
#100=1 (Frez fi12)
#101=2 (Wierlo 8.5)
T#100 M6
G43 Z10. H#100 D#100
G1 Z-1. F100
T#101 M6
G43 Z10. H#101 D#101
G1 Z-5. F100
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertEqual([u.tool for u in r.usages], [1, 2])
        self.assertEqual(r.usages[0].tool_hash, 100)
        self.assertEqual(r.usages[0].description, "Frez fi12")
        self.assertEqual(r.usages[0].h_offset, 1)
        self.assertEqual(r.usages[0].h_hash, 100)
        self.assertEqual(r.usages[0].d_offset, 1)
        self.assertEqual(r.usages[0].d_hash, 100)
        self.assertEqual(r.usages[1].tool_hash, 101)
        self.assertEqual(r.usages[1].description, "Wierlo 8.5")
        self.assertEqual(r.usages[1].min_z, -5.0)
        text = format_report(r)
        self.assertIn("T1 (#100)", text)
        self.assertIn("Frez fi12", text)
        self.assertIn("H1 (#100)", text)
        self.assertIn("D1 (#100)", text)
        self.assertNotIn("does not match", text)
        mini = format_report(r, paper=PAPER_80MM_MIN)
        self.assertIn("T1 (#100)", mini)
        self.assertIn("Frez fi12", mini)
        self.assertIn("H1 (#100)", mini)
        for line in mini.splitlines():
            self.assertLessEqual(len(line), THERMAL_WIDTH, msg=repr(line))

    def test_h_d_hash_must_match_t_hash(self) -> None:
        src = """O1
#100=1 (Frez fi12)
#101=1 (same pocket)
T#100 M6
G43 Z10. H#101 D#100
G1 Z-1. F100
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.tool, 1)
        self.assertEqual(u.h_offset, 1)
        self.assertIn("H#101 does not match T#100", u.warnings)
        self.assertFalse(any("D#" in w for w in u.warnings))

    def test_h_literal_mismatch_vs_t_hash(self) -> None:
        src = """O1
#100=1 (Frez fi12)
T#100 M6
G43 Z10. H25 D#100
G1 Z-1. F100
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertIn("H25 does not match T1", u.warnings)
        self.assertFalse(any("D" in w and "match" in w for w in u.warnings))

    def test_unassigned_t_hash_warns(self) -> None:
        src = """O1
T#100 M6
G43 Z10. H#100
G1 Z-1. F100
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.tool_hash, 100)
        self.assertEqual(u.tool, 0)
        self.assertIn("T#100 not assigned", u.warnings)
        self.assertIn("T#100", format_report(parse_nc_text(src, "t.nc")))


class TestEmptyPocket(unittest.TestCase):
    def test_middle_stub_warns_last_prep_does_not(self) -> None:
        src = """O1
T1 M6
G90 G1 Z-1. F100
T2 M6
G43 Z10. H2
T1 M6
M30
"""
        from fh6parse.parser import NO_MOTION_WARN, NO_FEED_WARN

        r = parse_nc_text(src, "t.nc")
        self.assertEqual([u.tool for u in r.usages], [1, 2, 1])
        self.assertNotIn(NO_MOTION_WARN, r.usages[0].warnings)
        self.assertIn(NO_MOTION_WARN, r.usages[1].warnings)
        self.assertNotIn(NO_MOTION_WARN, r.usages[2].warnings)
        self.assertNotIn(NO_FEED_WARN, r.usages[2].warnings)
        text = format_report(r, paper=PAPER_80MM_MIN)
        self.assertIn("no motion after tool change", text)
        for line in text.splitlines():
            self.assertLessEqual(len(line), THERMAL_WIDTH, msg=repr(line))

    def test_only_last_tool_with_no_motion_is_prep(self) -> None:
        src = """O1
T1 M6
G53 G0 Z63.5
M30
"""
        from fh6parse.parser import NO_MOTION_WARN

        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertNotIn(NO_MOTION_WARN, u.warnings)

    def test_rapids_only_warns_no_feed(self) -> None:
        src = """O1
T1 M6
G90 G0 X0 Y0 Z10
M30
"""
        from fh6parse.parser import NO_FEED_WARN, NO_MOTION_WARN

        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertIn(NO_FEED_WARN, u.warnings)
        self.assertNotIn(NO_MOTION_WARN, u.warnings)

    def test_sample_cutters_are_not_empty(self) -> None:
        from fh6parse.parser import NO_FEED_WARN, NO_MOTION_WARN

        r = parse_nc_file(SAMPLES / "D0134078.nc")
        for u in r.usages:
            self.assertNotIn(NO_MOTION_WARN, u.warnings)
            self.assertNotIn(NO_FEED_WARN, u.warnings)


class TestG65Macros(unittest.TestCase):
    def test_p9810_xy_rapid_z_feed_and_min_z(self) -> None:
        from fh6parse.parser import NO_FEED_WARN, NO_MOTION_WARN

        src = """O1
T1 M6 (SONDA)
G90 G0 X0 Y0 Z10
G65 P9810 X100 Y0 Z-5 F300
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.min_z, -5)
        self.assertAlmostEqual(u.time_s, 3.3, places=2)
        self.assertTrue(u.had_work)
        self.assertFalse(u.had_cut)
        self.assertIn(NO_FEED_WARN, u.warnings)
        self.assertNotIn(NO_MOTION_WARN, u.warnings)

    def test_p9832_on_off_does_not_move(self) -> None:
        src = """O1
T1 M6
G90 G0 X0 Y0 Z10
G65 P9832
G65 P9833
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.min_z, 10)

    def test_g65_b_c_are_macro_args_not_rotary(self) -> None:
        src = """O1
T1 M6
G90 G0 X0 Y0 Z0
G65 P9811 X10 Y10 Z-2 F100 B1. C2.
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertIsNone(u.b)
        self.assertIsNone(u.c)
        self.assertEqual(u.min_z, -2)

    def test_in_file_g65_sets_hash_1_to_26(self) -> None:
        src = """O1
T1 M6
G90 G0 X0 Y0 Z10
G65 P2000 X50 Z-3 F200
M30
O2000
G0 X#24
G1 Z#26 F#9
M99
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.min_z, -3)
        self.assertTrue(u.had_cut)

    def test_g65_locals_restored_after_m99(self) -> None:
        src = """O1
#26=-1
T1 M6
G90 G0 X0 Y0 Z0
G65 P2000 Z-8
G1 Z#26 F100
M30
O2000
G0 Z10
M99
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertEqual(u.min_z, -1)


class TestProgramStop(unittest.TestCase):
    def test_m00_joins_above_same_and_below_comments(self) -> None:
        src = """O1
T1 M6
G0 X0 Y0 Z10
(CHECK CLAMP)
M00 (PROGRAM STOP)
(CONTINUE)
G1 Z-1 F200
T2 M6
G1 Z-2 F200
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertEqual([u.tool for u in r.usages], [1, 2])
        stops = [u for op in r.operations for u in op.usages if u.is_stop()]
        self.assertEqual(len(stops), 1)
        self.assertEqual(
            stops[0].description, "CHECK CLAMP / PROGRAM STOP / CONTINUE"
        )
        self.assertEqual(r.usages[0].description, "")
        a4 = format_report(r)
        _, _, changes = a4.partition("EACH TOOL CHANGE")
        self.assertIn("[ ] M00  CHECK CLAMP / PROGRAM STOP / CONTINUE", changes)
        self.assertNotIn("T0", a4.split("EACH TOOL CHANGE")[0])
        html = format_print_html(r)
        self.assertIn(">M00<", html)
        self.assertIn("PROGRAM STOP", html)
        load = format_report(r, paper=PAPER_80MM_MIN)
        self.assertNotIn("M00", load)
        sett = format_report(r, paper=PAPER_80MM_SET)
        self.assertNotIn("M00", sett)
        mm = format_report(r, paper=PAPER_80MM)
        self.assertIn("[ ] M00", mm)
        self.assertIn("PROGRAM STOP", mm)

    def test_bare_m0_still_listed(self) -> None:
        src = """O1
T1 M6
G1 Z-1 F200
M0
T2 M6
G1 Z-2 F200
M30
"""
        r = parse_nc_text(src, "t.nc")
        stops = [u for op in r.operations for u in op.usages if u.is_stop()]
        self.assertEqual(len(stops), 1)
        self.assertEqual(stops[0].description, "")
        text = format_report(r, paper=PAPER_80MM)
        self.assertIn("[ ] M00", text)

    def test_sample_m00_mocowanie(self) -> None:
        r = parse_nc_file(SAMPLES / "D0134078.nc")
        self.assertEqual([u.tool for u in r.usages], [15, 26])
        stops = [u for op in r.operations for u in op.usages if u.is_stop()]
        self.assertTrue(stops)
        self.assertEqual(stops[0].description, "MOCOWANIE")
        a4 = format_report(r)
        self.assertIn("MOCOWANIE", a4.partition("EACH TOOL CHANGE")[2])

    def test_trailing_m00_does_not_warn_last_tool(self) -> None:
        from fh6parse.parser import NO_MOTION_WARN

        src = """O1
T1 M6
G1 Z-1 F200
T2 M6
M00 (CHECK)
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertNotIn(NO_MOTION_WARN, r.usages[1].warnings)
        self.assertEqual(r.usages[1].tool, 2)

    def test_m00_after_m30_is_not_listed(self) -> None:
        src = """O1
T1 M6
G1 Z-1 F200
M30
M00 (LATE)
"""
        r = parse_nc_text(src, "t.nc")
        stops = [u for op in r.operations for u in op.usages if u.is_stop()]
        self.assertEqual(stops, [])


class TestWorkOffset(unittest.TestCase):
    def test_g54_before_first_tool_is_quiet(self) -> None:
        src = """O1
G54
T1 M6
G1 Z-1 F200
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertEqual(r.operations[0].warnings, [])
        self.assertNotIn("after operation started", format_report(r))

    def test_g54_on_first_txx_m6_line_is_quiet(self) -> None:
        src = """O1
G54 T1 M6
G1 Z-1 F200
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertEqual(r.operations[0].warnings, [])

    def test_g55_after_txx_m6_warns(self) -> None:
        src = """O1
G54
T1 M6
G1 Z-1 F200
G55
G1 Z-2 F200
M30
"""
        r = parse_nc_text(src, "t.nc")
        warns = r.operations[0].warnings
        self.assertTrue(any("G55 after operation started" in w for w in warns))
        self.assertIn("WARNING: G55 after operation started", format_report(r))
        sett = format_report(r, paper=PAPER_80MM_SET)
        self.assertIn("G55 after operation started", sett)
        pl = format_report(r, lang="pl")
        self.assertIn("G55 po starcie operacji", pl)

    def test_second_offset_in_preamble_is_quiet(self) -> None:
        src = """O1
G54
G55
T1 M6
G1 Z-1 F200
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertEqual(r.operations[0].warnings, [])

    def test_g55_after_m97_warns(self) -> None:
        src = """O1
(N10 - OP1)
G54
M97 P10
G55
M30
N10
T1 M6
G1 Z-1 F200
M99
"""
        r = parse_nc_text(src, "t.nc")
        warns = [w for op in r.operations for w in op.warnings]
        self.assertTrue(any("G55 after operation started" in w for w in warns))

    def test_g54_inside_op_body_warns(self) -> None:
        src = """O1
(N10 - OP1)
G54
M97 P10
M30
N10
G55
T1 M6
G1 Z-1 F200
M99
"""
        r = parse_nc_text(src, "t.nc")
        op1 = [op for op in r.operations if op.n == 10][0]
        self.assertTrue(any("G55 after operation started" in w for w in op1.warnings))

    def test_sample_d0134078_warns_on_g55_in_main(self) -> None:
        r = parse_nc_file(SAMPLES / "D0134078.nc")
        warns = [w for op in r.operations for w in op.warnings]
        self.assertTrue(any(w.startswith("G55 after operation started") for w in warns))
        self.assertTrue(any(w.startswith("G54 after operation started") for w in warns))

    def test_sample_000814086_preamble_g54_is_quiet(self) -> None:
        r = parse_nc_file(SAMPLES / "000814086.nc")
        warns = [w for op in r.operations for w in op.warnings]
        self.assertEqual(warns, [])


class TestSpindleLimit(unittest.TestCase):
    def test_s_above_mill_max_warns(self) -> None:
        from fh6parse.machtime import MachineProfile

        src = """O1
T1 M6
S12000 M3
G1 Z-1 F200
M30
"""
        mill = MachineProfile(id="vf", name="VF", max_rpm=8000)
        r = parse_nc_text(src, "t.nc", machine=mill)
        self.assertIn("S12000 exceeds mill max 8000", r.usages[0].warnings)
        self.assertIn("WARNING: S12000 exceeds mill max 8000", format_report(r))
        load = format_report(r, paper=PAPER_80MM_MIN)
        self.assertIn("S12000 exceeds mill max 8000", load)
        pl = format_report(r, lang="pl")
        self.assertIn("S12000 przekracza max wrzeciona 8000", pl)

    def test_s_at_mill_max_is_quiet(self) -> None:
        from fh6parse.machtime import MachineProfile

        src = """O1
T1 M6
S8000 M3
G1 Z-1 F200
M30
"""
        mill = MachineProfile(id="vf", name="VF", max_rpm=8000)
        r = parse_nc_text(src, "t.nc", machine=mill)
        self.assertFalse(any("exceeds mill max" in w for w in r.usages[0].warnings))

    def test_no_max_rpm_is_quiet(self) -> None:
        src = """O1
T1 M6
S12000 M3
G1 Z-1 F200
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertFalse(any("exceeds mill max" in w for w in r.usages[0].warnings))


class TestG68(unittest.TestCase):
    def test_g68_g69_warns_on_all_papers(self) -> None:
        src = """O1
T1 M6
G90 G0 X0 Y0 Z10
G68 X0 Y0 R90
G1 X100 Y0 F200
G69
M30
"""
        r = parse_nc_text(src, "t.nc")
        msg = "G68 T1 L4 to G69 T1 L6"
        self.assertIn(msg, r.operations[0].warnings)
        a4 = format_report(r)
        load = format_report(r, paper=PAPER_80MM_MIN)
        sett = format_report(r, paper=PAPER_80MM_SET)
        run = format_report(r, paper=PAPER_80MM)
        self.assertIn(f"WARNING: {msg}", a4)
        for text in (a4, load, sett, run):
            self.assertIn(msg, text)
        pl = format_report(r, lang="pl")
        self.assertIn("G68 T1 L4 do G69 T1 L6", pl)
        self.assertIn("UWAGA:", pl)

    def test_g68_without_g69_warns(self) -> None:
        src = """O1
T1 M6
G90 G0 X0 Y0 Z10
G68 X0 Y0 R90
G1 X100 Y0 F200
M30
"""
        r = parse_nc_text(src, "t.nc")
        msg = "G68 T1 L4 without G69"
        self.assertIn(msg, r.operations[0].warnings)
        self.assertIn(msg, format_report(r, paper=PAPER_80MM_MIN))
        self.assertIn("G68 T1 L4 bez G69", format_report(r, lang="pl"))

    def test_g69_on_later_tool(self) -> None:
        src = """O1
T1 M6
G90 G0 X0 Y0
G68 X0 Y0 R45
G1 X10 F200
T2 M6
G69
G1 X20 F200
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertIn("G68 T1 L4 to G69 T2 L7", r.operations[0].warnings)

    def test_g68_before_first_t(self) -> None:
        src = """O1
G90
G68 X0 Y0 R90
T1 M6
G1 X100 Y0 F200
G69
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertIn("G68 L3 to G69 T1 L6", r.operations[0].warnings)

    def test_g69_m30_same_line_cancels(self) -> None:
        src = """O1
T1 M6
G90 G0 X0 Y0
G68 X0 Y0 R90
G1 X10 F200
G69 M30
"""
        r = parse_nc_text(src, "t.nc")
        warns = r.operations[0].warnings
        self.assertTrue(any("to G69" in w for w in warns))
        self.assertFalse(any("without G69" in w for w in warns))

    def test_no_g68_is_quiet(self) -> None:
        src = """O1
T1 M6
G1 X10 F200
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertFalse(any("G68" in w for w in r.operations[0].warnings))


if __name__ == "__main__":
    unittest.main()
