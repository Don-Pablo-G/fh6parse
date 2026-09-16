"""Parser fixtures against the three sample CNC programs."""

from __future__ import annotations

import unittest
from pathlib import Path

from fh6parse.parser import parse_nc_file, parse_nc_text
from fh6parse.report import (
    PAPER_80MM,
    PAPER_80MM_MIN,
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
        self.assertEqual(t15[1].min_z, 26.65)

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
        self.assertIn("CNC TOOLS MIN", text)
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


if __name__ == "__main__":
    unittest.main()
