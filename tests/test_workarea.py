"""Machine travel vs work AABB: allowed G54 origin box in G53 mm."""

from __future__ import annotations

import unittest

from fh6parse.machtime import MachineProfile
from fh6parse.parser import parse_nc_text
from fh6parse.report import format_report
from fh6parse.workarea import WorkBBox, g54_window, window_for_result


def _mill(**kwargs: object) -> MachineProfile:
    return MachineProfile(id="vf", name="VF", **kwargs)  # type: ignore[arg-type]


class TestG54Window(unittest.TestCase):
    def test_leftover_travel_is_valid_g54_box(self) -> None:
        mill = _mill(x_min=-500, x_max=0, y_min=-400, y_max=0)
        bbox = WorkBBox()
        bbox.add(0, 0, 0)
        bbox.add(100, 50, -10)
        window = g54_window(mill, bbox)
        assert window is not None
        self.assertTrue(window.fits)
        self.assertAlmostEqual(window.x_min, -500)
        self.assertAlmostEqual(window.x_max, -100)
        self.assertAlmostEqual(window.y_min, -400)
        self.assertAlmostEqual(window.y_max, -50)
        cx, cy = window.center
        self.assertAlmostEqual(cx, -300)
        self.assertAlmostEqual(cy, -225)
        sw, se, ne, nw = window.corners
        self.assertEqual(sw, (-500, -400))
        self.assertEqual(se, (-100, -400))
        self.assertEqual(ne, (-100, -50))
        self.assertEqual(nw, (-500, -50))
        self.assertAlmostEqual(window.leftover_x, 400)
        self.assertAlmostEqual(window.leftover_y, 350)
        self.assertAlmostEqual(window.max_tool_dia_mm or 0, 350)

    def test_too_big_when_work_exceeds_travel(self) -> None:
        mill = _mill(x_min=-500, x_max=0, y_min=-400, y_max=0)
        bbox = WorkBBox()
        bbox.add(0, 0)
        bbox.add(600, 10)
        window = g54_window(mill, bbox)
        assert window is not None
        self.assertFalse(window.fits)
        self.assertIsNone(window.max_tool_dia_mm)

    def test_stored_g54_inside_and_out(self) -> None:
        mill = _mill(
            x_min=-500,
            x_max=0,
            y_min=-400,
            y_max=0,
            offset_x=-300,
            offset_y=-200,
            offset_z=-100,
        )
        bbox = WorkBBox()
        bbox.add(0, 0)
        bbox.add(100, 50)
        inside = g54_window(mill, bbox)
        assert inside is not None
        self.assertTrue(inside.g54_inside)
        out = g54_window(
            _mill(
                x_min=-500,
                x_max=0,
                y_min=-400,
                y_max=0,
                offset_x=-50,
                offset_y=-200,
                offset_z=-100,
            ),
            bbox,
        )
        assert out is not None
        self.assertFalse(out.g54_inside)

    def test_z_window_subtracts_tool_length(self) -> None:
        mill = _mill(
            x_min=-500,
            x_max=0,
            y_min=-400,
            y_max=0,
            z_min=-400,
            z_max=0,
            tool_length_mm=100,
        )
        bbox = WorkBBox()
        bbox.add(0, 0, 0)
        bbox.add(10, 10, -20)
        window = g54_window(mill, bbox)
        assert window is not None
        self.assertAlmostEqual(window.z_min or 0, -480)
        self.assertAlmostEqual(window.z_max or 0, -100)

    def test_inch_work_converted_to_mm(self) -> None:
        mill = _mill(x_min=-500, x_max=0, y_min=-400, y_max=0)
        bbox = WorkBBox()
        bbox.add(0, 0)
        bbox.add(1, 0)
        window = g54_window(mill, bbox, inch=True)
        assert window is not None
        self.assertAlmostEqual(window.x_max, -25.4)

    def test_default_mill_has_no_window(self) -> None:
        bbox = WorkBBox()
        bbox.add(0, 0)
        bbox.add(10, 10)
        self.assertIsNone(g54_window(_mill(), bbox))


class TestParserWorkBBox(unittest.TestCase):
    def test_g53_moves_are_not_work(self) -> None:
        src = """O1
T1 M6
G90 G0 X0 Y0 Z10
G1 X100 Y50 Z-5 F200
G53 G0 X-800 Y-10
M30
"""
        result = parse_nc_text(src, "t.nc")
        box = result.work_bbox
        self.assertAlmostEqual(box.min_x or 0, 0)
        self.assertAlmostEqual(box.max_x or 0, 100)
        self.assertAlmostEqual(box.min_y or 0, 0)
        self.assertAlmostEqual(box.max_y or 0, 50)
        self.assertAlmostEqual(box.min_z or 0, -5)
        self.assertAlmostEqual(box.max_z or 0, 10)

    def test_ticket_lists_corners_and_center(self) -> None:
        mill = _mill(
            x_min=-500,
            x_max=0,
            y_min=-400,
            y_max=0,
            offset_x=-300,
            offset_y=-200,
            offset_z=-100,
        )
        src = """O1
T1 M6
G90 G0 X0 Y0 Z0
G1 X100 Y50 F200
M30
"""
        result = parse_nc_text(src, "t.nc", machine=mill)
        window = window_for_result(result)
        assert window is not None
        self.assertTrue(window.fits)
        text = format_report(result)
        self.assertIn("Work offset origin in G53 mm", text)
        self.assertIn("SW -500,-400", text)
        self.assertIn("SE -100,-400", text)
        self.assertIn("NE -100,-50", text)
        self.assertIn("NW -500,-50", text)
        self.assertIn("Center -300,-225", text)
        self.assertIn("Max Ø G41/G42 centred 350 mm", text)
        self.assertIn("Stored offset is inside this box.", text)


    def test_g68_r90_rotates_work_xy(self) -> None:
        src = """O1
T1 M6
G90 G0 X0 Y0 Z10
G68 X0 Y0 R90
G1 X100 Y0 F200
G69
M30
"""
        box = parse_nc_text(src, "t.nc").work_bbox
        self.assertAlmostEqual(box.min_x or 0, 0)
        self.assertAlmostEqual(box.max_x or 0, 0)
        self.assertAlmostEqual(box.min_y or 0, 0)
        self.assertAlmostEqual(box.max_y or 0, 100)


def _umc(**kwargs: object) -> MachineProfile:
    return MachineProfile(  # type: ignore[arg-type]
        id="umc",
        name="UMC",
        x_min=-500,
        x_max=0,
        y_min=-400,
        y_max=0,
        z_min=-500,
        z_max=0,
        mrzp_x=-250,
        mrzp_y=-200,
        mrzp_z=-400,
        **kwargs,
    )


class TestDwoWindow(unittest.TestCase):
    def test_b0_c0_matches_linear_leftover(self) -> None:
        mill = _umc()
        bbox = WorkBBox()
        bbox.add(0, 0, 0)
        bbox.add(100, 50, -10)
        linear = g54_window(mill, bbox)
        dwo = g54_window(mill, bbox, rotary_poses=((0.0, 0.0),))
        assert linear is not None and dwo is not None
        self.assertFalse(dwo.dwo)
        self.assertAlmostEqual(dwo.x_min, linear.x_min)
        self.assertAlmostEqual(dwo.x_max, linear.x_max)
        self.assertAlmostEqual(dwo.y_min, linear.y_min)
        self.assertAlmostEqual(dwo.y_max, linear.y_max)
        self.assertAlmostEqual(dwo.z_min or 0, linear.z_min or 0)
        self.assertAlmostEqual(dwo.z_max or 0, linear.z_max or 0)

    def test_without_mrzp_ignores_rotary(self) -> None:
        mill = _mill(x_min=-500, x_max=0, y_min=-400, y_max=0)
        bbox = WorkBBox()
        bbox.add(0, 0)
        bbox.add(100, 50)
        window = g54_window(mill, bbox, rotary_poses=((0.0, 90.0),))
        assert window is not None
        self.assertFalse(window.dwo)
        self.assertAlmostEqual(window.x_max, -100)

    def test_c90_point_work_inner_box(self) -> None:
        mill = _umc()
        bbox = WorkBBox()
        bbox.add(0, 0, 0)
        window = g54_window(mill, bbox, rotary_poses=((0.0, 0.0), (0.0, 90.0)))
        assert window is not None
        self.assertTrue(window.dwo)
        self.assertTrue(window.fits)
        self.assertAlmostEqual(window.x_min, -450, places=0)
        self.assertAlmostEqual(window.x_max, -50, places=0)
        self.assertAlmostEqual(window.y_min, -400, places=0)
        self.assertAlmostEqual(window.y_max, 0, places=0)
        self.assertAlmostEqual(window.z_min or 0, -500, places=0)
        self.assertAlmostEqual(window.z_max or 0, 0, places=0)
        from fh6parse.workarea import dwo_g53_xyz

        mrzp = (-250.0, -200.0, -400.0)
        for origin in window.corners_xyz:
            for b, c in ((0.0, 0.0), (0.0, 90.0)):
                gx, gy, gz = dwo_g53_xyz(origin, (0.0, 0.0, 0.0), b, c, mrzp)
                self.assertGreaterEqual(gx, -500 - 1e-6)
                self.assertLessEqual(gx, 1e-6)
                self.assertGreaterEqual(gy, -400 - 1e-6)
                self.assertLessEqual(gy, 1e-6)
                self.assertGreaterEqual(gz, -500 - 1e-6)
                self.assertLessEqual(gz, 1e-6)

    def test_parser_collects_machine_c_and_ticket_lists_xyz(self) -> None:
        mill = _umc(offset_x=-250, offset_y=-200, offset_z=-400)
        src = """O1
T1 M6
G90 G0 X0 Y0 Z0
G1 X0 Y0 F200
G0 C90
G1 X0 Y0
M30
"""
        result = parse_nc_text(src, "t.nc", machine=mill)
        self.assertIn((0.0, 90.0), result.rotary_poses)
        window = window_for_result(result)
        assert window is not None
        self.assertTrue(window.dwo)
        text = format_report(result)
        self.assertIn("Work offset origin in G53 mm (DWO limits)", text)
        self.assertIn("Machine B/C", text)
        self.assertIn("0/90", text)
        self.assertIn("Center ", text)
        self.assertRegex(text, r"-?\d+,-?\d+,-?\d+")

    def test_c45_and_b90_corners_stay_in_travel(self) -> None:
        from fh6parse.workarea import dwo_g53_xyz

        mill = _umc()
        bbox = WorkBBox()
        bbox.add(-20, -20, -5)
        bbox.add(20, 20, 5)
        window = g54_window(
            mill, bbox, rotary_poses=((0.0, 0.0), (0.0, 45.0), (90.0, 0.0))
        )
        assert window is not None
        self.assertTrue(window.dwo)
        self.assertTrue(window.fits)
        mrzp = (-250.0, -200.0, -400.0)
        works = (
            (-20.0, -20.0, -5.0),
            (20.0, 20.0, 5.0),
            (-20.0, 20.0, 5.0),
            (20.0, -20.0, -5.0),
        )
        for origin in window.corners_xyz:
            for work in works:
                for b, c in ((0.0, 0.0), (0.0, 45.0), (90.0, 0.0)):
                    gx, gy, gz = dwo_g53_xyz(origin, work, b, c, mrzp)
                    self.assertGreaterEqual(gx, -500 - 1e-4)
                    self.assertLessEqual(gx, 1e-4)
                    self.assertGreaterEqual(gy, -400 - 1e-4)
                    self.assertLessEqual(gy, 1e-4)
                    self.assertGreaterEqual(gz, -500 - 1e-4)
                    self.assertLessEqual(gz, 1e-4)

    def test_stored_offset_checked_against_dwo_planes(self) -> None:
        mill = _umc(offset_x=-250, offset_y=-200, offset_z=-400)
        bbox = WorkBBox()
        bbox.add(0, 0, 0)
        inside = g54_window(
            mill, bbox, rotary_poses=((0.0, 0.0), (0.0, 90.0))
        )
        assert inside is not None
        self.assertTrue(inside.g54_inside)
        out = g54_window(
            _umc(offset_x=-20, offset_y=-200, offset_z=-400),
            bbox,
            rotary_poses=((0.0, 0.0), (0.0, 90.0)),
        )
        assert out is not None
        self.assertFalse(out.g54_inside)


if __name__ == "__main__":
    unittest.main()
