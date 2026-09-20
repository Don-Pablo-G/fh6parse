"""Programmed-motion time: parametric F, arcs, canned cycles."""

from __future__ import annotations

import unittest

from fh6parse.machtime import (
    G73_PULLBACK_MM,
    MachineProfile,
    RAPID_MM_PER_MIN,
    arc_xy_length,
    canned_cycle_seconds,
    feed_per_min,
    format_machine_time,
    seconds_for_length,
)
from fh6parse.parser import parse_nc_text
from fh6parse.report import (
    BAR_FILL,
    PAPER_80MM,
    PAPER_80MM_MIN,
    PAPER_80MM_SET,
    PAPER_A4,
    THERMAL_WIDTH,
    format_print_html,
    format_report,
)


class TestMachtimeHelpers(unittest.TestCase):
    def test_g94_length(self) -> None:
        # 100 mm at 500 mm/min = 12 s
        self.assertAlmostEqual(
            seconds_for_length(100, 500, rapid=False, inch=False), 12.0
        )

    def test_rapid_uses_assumed_rate(self) -> None:
        s = seconds_for_length(20000, None, rapid=True, inch=False)
        self.assertAlmostEqual(s, 60.0)

    def test_g95_feed_is_f_times_s(self) -> None:
        self.assertAlmostEqual(feed_per_min(0.2, per_rev=True, rpm=1000), 200.0)

    def test_quarter_circle_r(self) -> None:
        length = arc_xy_length(10, 0, 0, 10, r=10, i=None, j=None, clockwise=False)
        self.assertAlmostEqual(length, 10 * 3.1415926535 / 2, places=4)

    def test_g81_feed_plunge(self) -> None:
        # R33 to Z26 = 7 mm at 40 mm/min; G98 return 7 mm rapid from 26 to 33?
        # z_initial 50, R 33, Z 26. Rapid 17 + feed 7 + rapid |26-50|=24
        s = canned_cycle_seconds(
            81,
            z_initial=50,
            r=33,
            z=26,
            q=None,
            k=None,
            feed=40,
            g98=True,
            inch=False,
        )
        feed_s = 60 * 7 / 40
        rapid_s = 60 * (17 + 24) / RAPID_MM_PER_MIN
        self.assertAlmostEqual(s, feed_s + rapid_s, places=5)

    def test_g73_chip_break_is_0_2_mm(self) -> None:
        self.assertEqual(G73_PULLBACK_MM, 0.2)
        s = canned_cycle_seconds(
            73,
            z_initial=0,
            r=0,
            z=-8,
            q=4,
            k=None,
            feed=100,
            g98=True,
            inch=False,
        )
        feed_s = 60.0 * 8.0 / 100.0
        rapid_s = 60.0 * (0.4 + 8.0) / RAPID_MM_PER_MIN
        self.assertAlmostEqual(s, feed_s + rapid_s, places=5)

    def test_g83_retracts_to_r_then_reapproaches(self) -> None:
        s = canned_cycle_seconds(
            83,
            z_initial=0,
            r=0,
            z=-10,
            q=5,
            k=None,
            feed=100,
            g98=True,
            inch=False,
        )
        feed_s = 60.0 * (5.0 + 5.5) / 100.0
        rapid_s = 60.0 * (5.0 + 4.5 + 10.0) / RAPID_MM_PER_MIN
        self.assertAlmostEqual(s, feed_s + rapid_s, places=5)

    def test_g84_retract_at_one_times_feed(self) -> None:
        s = canned_cycle_seconds(
            84,
            z_initial=10,
            r=5,
            z=0,
            q=None,
            k=None,
            feed=50,
            g98=True,
            inch=False,
        )
        feed_s = 60.0 * 10.0 / 50.0
        rapid_s = 60.0 * (5.0 + 5.0) / RAPID_MM_PER_MIN
        self.assertAlmostEqual(s, feed_s + rapid_s, places=5)

    def test_g82_adds_dwell_seconds(self) -> None:
        drill = canned_cycle_seconds(
            81, z_initial=10, r=5, z=0, q=None, k=None, feed=100, g98=True, inch=False
        )
        spot = canned_cycle_seconds(
            82,
            z_initial=10,
            r=5,
            z=0,
            q=None,
            k=None,
            feed=100,
            g98=True,
            inch=False,
            p=2,
        )
        self.assertAlmostEqual(spot - drill, 2.0, places=5)

    def test_g86_rapids_out_g85_feeds_out(self) -> None:
        bore = canned_cycle_seconds(
            85, z_initial=10, r=5, z=0, q=None, k=None, feed=100, g98=True, inch=False
        )
        stop = canned_cycle_seconds(
            86, z_initial=10, r=5, z=0, q=None, k=None, feed=100, g98=True, inch=False
        )
        self.assertGreater(bore, stop)

    def test_format_plus_when_incomplete(self) -> None:
        self.assertEqual(format_machine_time(90), "1:30")
        self.assertEqual(format_machine_time(90, incomplete=True), "1:30+")


class TestParserMachineTime(unittest.TestCase):
    def test_parametric_f_hash(self) -> None:
        src = """O1
T1 M6
G90 G94
#108=500.
G0 X0 Y0 Z0
G1 X100 F#108
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertAlmostEqual(u.time_s, 12.0, places=4)
        self.assertFalse(u.time_incomplete)

    def test_missing_feed_is_incomplete(self) -> None:
        src = """O1
T1 M6
G90 G0 X0
G1 X100
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        self.assertTrue(u.time_incomplete)
        self.assertIn("Time 0:00+", format_report(parse_nc_text(src, "t.nc")))

    def test_g81_in_report(self) -> None:
        src = """O1
T1 M6
G90 G94 G0 X0 Y0 Z50
G98 G81 X0 Y0 Z26 R33 F40
G80
M30
"""
        r = parse_nc_text(src, "t.nc")
        self.assertGreater(r.usages[0].time_s, 10.0)
        self.assertIn("Time", format_report(r))

    def test_g95_tap(self) -> None:
        src = """O1
T1 M6
S100 M3
G90 G0 X0 Y0 Z10
G95
G98 G84 X0 Y0 Z0 R5 F0.5
G94
G80
M30
"""
        u = parse_nc_text(src, "t.nc").usages[0]
        # depth 5 mm, tap in+out = 10 mm at 0.5 mm/rev * 100 rpm = 50 mm/min → 12 s feed
        self.assertGreater(u.time_s, 11.0)
        self.assertFalse(u.time_incomplete)

    def test_sample_has_time(self) -> None:
        from pathlib import Path

        sample = Path(__file__).resolve().parent / "samples" / "D0134078.nc"
        r = parse_nc_text(sample.read_text(encoding="utf-8"), sample)
        mill = [u for u in r.usages if u.tool == 26][0]
        self.assertGreater(mill.time_s, 30.0)
        self.assertFalse(mill.time_incomplete)


class TestReportCycleShare(unittest.TestCase):
    def _equal_tools(self):
        src = """O1
T1 M6
G90 G94
G0 X0 Y0 Z0
G1 X100 F500
T2 M6
G0 X100 Y0 Z0
G1 X200 F500
M30
"""
        return parse_nc_text(src, "t.nc")

    def test_cycle_on_short_and_full(self) -> None:
        r = self._equal_tools()
        for paper in (PAPER_A4, PAPER_80MM):
            text = format_report(r, paper=paper)
            self.assertIn("Cycle 0:24", text, msg=paper)
            self.assertIn(" 50%", text, msg=paper)
            self.assertIn(BAR_FILL, text, msg=paper)
            self.assertTrue("SHARE" in text or "Share of cycle" in text, msg=paper)
        sett = format_report(r, paper=PAPER_80MM_SET)
        self.assertIn("Cycle 0:24", sett)
        self.assertNotIn(BAR_FILL, sett)
        load = format_report(r, paper=PAPER_80MM_MIN)
        self.assertNotIn("Cycle 0:24", load)
        self.assertNotIn(BAR_FILL, load)

    def test_full_each_change_has_share_not_a_second_chart(self) -> None:
        r = self._equal_tools()
        a4 = format_report(r, paper=PAPER_A4)
        head, _, tail = a4.partition("EACH TOOL CHANGE")
        self.assertIn(BAR_FILL, head)
        self.assertNotIn(BAR_FILL, tail)
        self.assertEqual(tail.count(" 50%"), 2)
        mm = format_report(r, paper=PAPER_80MM)
        head_mm, _, tail_mm = mm.partition("EACH CHANGE")
        self.assertIn(BAR_FILL, head_mm)
        self.assertNotIn(BAR_FILL, tail_mm)
        self.assertEqual(tail_mm.count(" 50%"), 2)
        for paper in (PAPER_80MM, PAPER_80MM_MIN):
            for line in format_report(r, paper=paper).splitlines():
                self.assertLessEqual(len(line), THERMAL_WIDTH, msg=repr(line))

    def test_html_cycle_and_chart(self) -> None:
        r = self._equal_tools()
        a4 = format_print_html(r, paper=PAPER_A4)
        self.assertIn("Cycle 0:24", a4)
        self.assertIn("Share of cycle", a4)
        self.assertIn('class="chart"', a4)
        self.assertIn("width:50%", a4)
        self.assertIn("Each tool change", a4)
        mm = format_print_html(r, paper=PAPER_80MM)
        self.assertIn("Cycle 0:24", mm)
        self.assertIn("SHARE", mm)
        self.assertIn(BAR_FILL, mm)
        self.assertIn("EACH CHANGE", mm)
        mini = format_print_html(r, paper=PAPER_80MM_MIN)
        self.assertIn("CNC TOOLS LOAD", mini)
        self.assertNotIn("Cycle 0:24", mini)
        self.assertNotIn("SHARE", mini)
        self.assertNotIn(BAR_FILL, mini)
        self.assertNotIn("EACH CHANGE", mini)
        sett = format_print_html(r, paper=PAPER_80MM_SET)
        self.assertIn("Cycle 0:24", sett)
        self.assertNotIn("SHARE", sett)
        self.assertNotIn(BAR_FILL, sett)
        self.assertNotIn("EACH CHANGE", sett)

    def test_single_tool_is_100_percent(self) -> None:
        src = """O1
T1 M6
G90 G94
G0 X0 Y0 Z0
G1 X100 F500
M30
"""
        text = format_report(parse_nc_text(src, "t.nc"))
        self.assertIn("Cycle 0:12", text)
        self.assertIn("100%", text)
        self.assertIn(BAR_FILL, text)

    def test_block_is_cp852(self) -> None:
        self.assertEqual(BAR_FILL.encode("cp852"), b"\xdb")

    def test_faster_rapid_shortens_g0(self) -> None:
        src = """O1
T1 M6
G90 G94
G0 X0 Y0 Z0
G0 X20000
M30
"""
        slow = parse_nc_text(src, "t.nc")
        fast = parse_nc_text(
            src,
            "t.nc",
            machine=MachineProfile(id="fast", name="Fast", rapid_mm_min=40000),
        )
        self.assertAlmostEqual(slow.usages[0].time_s, 60.0)
        self.assertAlmostEqual(fast.usages[0].time_s, 30.0)

    def test_tool_change_adds_once_per_txx_m6(self) -> None:
        src = """O1
T1 M6
G90 G94
G0 X0 Y0 Z0
G1 X100 F500
T2 M6
G1 X200 F500
M30
"""
        mill = MachineProfile(id="atc", name="ATC mill", tool_change_s=10)
        r = parse_nc_text(src, "t.nc", machine=mill)
        self.assertAlmostEqual(r.usages[0].time_s, 22.0)
        self.assertAlmostEqual(r.usages[1].time_s, 22.0)
        text = format_report(r)
        self.assertIn("Cycle 0:44", text)
        self.assertIn("ATC mill", text)
        self.assertIn("tool change 10 s", text)
        sett = format_report(r, paper=PAPER_80MM_SET)
        self.assertIn("ATC mill", sett)
        self.assertIn("Tchg 10s", sett)
        load = format_report(r, paper=PAPER_80MM_MIN)
        self.assertNotIn("ATC mill", load)
        self.assertNotIn("Tchg 10s", load)

    def test_split_t_then_m6_gets_the_same_tool_change_s(self) -> None:
        together = """O1
T1 M6
G90 G94 G0 X0 Y0 Z0
G1 X100 F500
M30
"""
        split = """O1
T1
M6
G90 G94 G0 X0 Y0 Z0
G1 X100 F500
M30
"""
        mill = MachineProfile(id="atc", name="ATC mill", tool_change_s=10)
        a = parse_nc_text(together, "t.nc", machine=mill).usages[0]
        b = parse_nc_text(split, "t.nc", machine=mill).usages[0]
        self.assertEqual(a.tool, 1)
        self.assertEqual(b.tool, 1)
        self.assertAlmostEqual(a.time_s, b.time_s)


class TestG53FrameTime(unittest.TestCase):
    mill = MachineProfile(
        id="vf",
        name="VF G53",
        rapid_mm_min=60000.0,
        tool_change_s=2.0,
        atc_x=0.0,
        atc_y=0.0,
        atc_z=0.0,
        offset_x=0.0,
        offset_y=0.0,
        offset_z=0.0,
        tool_length_mm=0.0,
    )

    def test_default_mill_has_no_g53_frame(self) -> None:
        from fh6parse.machtime import DEFAULT_MACHINE, work_to_g53

        self.assertFalse(DEFAULT_MACHINE.has_g53_frame())
        self.assertIsNone(work_to_g53(0, 0, 10, None, None, DEFAULT_MACHINE, inch=False)[2])

    def test_work_to_g53_adds_origin_and_tool_length(self) -> None:
        from fh6parse.machtime import work_to_g53

        mill = MachineProfile(
            id="vf",
            name="VF",
            atc_x=0,
            atc_y=0,
            atc_z=0,
            offset_x=-400,
            offset_y=-250,
            offset_z=-400,
            tool_length_mm=120,
        )
        mx, my, mz, _, _ = work_to_g53(10, 5, 10, None, None, mill, inch=False)
        self.assertAlmostEqual(mx, -390)
        self.assertAlmostEqual(my, -245)
        self.assertAlmostEqual(mz, -270)

    def test_m6_charges_z_then_xy_on_finishing_tool(self) -> None:
        src = """O1
T1 M6
G90 G0 X0 Y0 Z10
T2 M6
G0 X0 Y0 Z50
M30
"""
        r = parse_nc_text(src, "t.nc", machine=self.mill)
        t1, t2 = r.usages
        # T1: 2 s swap + 10 mm from ATC to Z10 + 10 mm Z retract to ATC
        self.assertAlmostEqual(t1.time_s, 2.02, places=4)
        # T2: 2 s swap + 50 mm from ATC to Z50
        self.assertAlmostEqual(t2.time_s, 2.05, places=4)
        self.assertIn("G53 ATC/offset", format_report(r))

    def test_g53_to_atc_does_not_double_count_m6_retract(self) -> None:
        with_g53 = """O1
T1 M6
G90 G0 X100 Y0 Z10
G53 G0 Z0
T2 M6
M30
"""
        without = """O1
T1 M6
G90 G0 X100 Y0 Z10
T2 M6
M30
"""
        a = parse_nc_text(with_g53, "t.nc", machine=self.mill).usages[0]
        b = parse_nc_text(without, "t.nc", machine=self.mill).usages[0]
        # G53 Z retract replaces the M6 Z leg; a second Z charge would make `a` larger.
        self.assertAlmostEqual(a.time_s, b.time_s, places=4)
        approach = (100.0**2 + 10.0**2) ** 0.5 / 1000.0
        self.assertAlmostEqual(a.time_s, 2.0 + approach + 0.01 + 0.1, places=3)


if __name__ == "__main__":
    unittest.main()
