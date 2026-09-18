"""Programmed-motion time: parametric F, arcs, canned cycles."""

from __future__ import annotations

import unittest

from fh6parse.machtime import (
    G73_PULLBACK_MM,
    RAPID_MM_PER_MIN,
    arc_xy_length,
    canned_cycle_seconds,
    feed_per_min,
    format_machine_time,
    seconds_for_length,
)
from fh6parse.parser import parse_nc_text
from fh6parse.report import format_report


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


if __name__ == "__main__":
    unittest.main()
