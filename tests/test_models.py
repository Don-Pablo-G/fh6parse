"""Part-id / STEP matching and ESC/POS raster helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fh6parse.kiosk import load_kiosk_config, save_model_roots
from fh6parse.modelmatch import ModelFile, index_models, pick_model
from fh6parse.modelprep import ModelPrep
from fh6parse.modelrender import (
    MAX_VIEW_HEIGHT,
    MIN_VIEW_HEIGHT,
    THERMAL_DOTS,
    _raster_view,
    _ticket_basis,
    ticket_view_pixels,
)
from fh6parse.partid import identity_from_nc, identity_from_nc_path, parse_model_stem
from fh6parse.parser import parse_nc_file
from fh6parse.printer import CUT, INIT, bitmap_to_escpos, encode_ticket
from fh6parse.report import PAPER_80MM, format_print_html

SAMPLES = Path(__file__).resolve().parent / "samples"


def _outward_unit_cube():
    import numpy as np

    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 1.0],
            [1.0, 1.0, 1.0],
            [0.0, 1.0, 1.0],
        ],
        dtype=np.float64,
    )
    faces = np.array(
        [
            [0, 2, 1],
            [0, 3, 2],
            [4, 5, 6],
            [4, 6, 7],
            [0, 1, 5],
            [0, 5, 4],
            [3, 6, 2],
            [3, 7, 6],
            [0, 7, 3],
            [0, 4, 7],
            [1, 2, 6],
            [1, 6, 5],
        ],
        dtype=np.int64,
    )
    return vertices, faces


class TestParseModelStem(unittest.TestCase):
    def test_plain_part_number(self) -> None:
        ident = parse_model_stem("D0134078")
        self.assertEqual(ident.base, "D0134078")
        self.assertIsNone(ident.rev)

    def test_explicit_rev_suffix(self) -> None:
        ident = parse_model_stem("D0134078_Rev03_detail")
        self.assertEqual(ident.base, "D0134078")
        self.assertIsNotNone(ident.rev)
        self.assertTrue(ident.rev.matches(parse_model_stem("D0134078-R3").rev))

    def test_hyphen_short_rev(self) -> None:
        ident = parse_model_stem("SE0241282-0")
        self.assertEqual(ident.base, "SE0241282")
        self.assertEqual(ident.rev.number, 0)

    def test_glued_letter_rev(self) -> None:
        ident = parse_model_stem("D0134078A")
        self.assertEqual(ident.base, "D0134078")
        self.assertEqual(ident.rev.letter, "A")


class TestIdentityFromNc(unittest.TestCase):
    def test_samples(self) -> None:
        d = identity_from_nc_path(SAMPLES / "D0134078.nc")
        self.assertEqual(d.base, "D0134078")
        self.assertIsNone(d.rev)

        se = identity_from_nc_path(SAMPLES / "SE0241282.nc")
        self.assertEqual(se.base, "SE0241282")
        self.assertIsNotNone(se.rev)
        self.assertEqual(se.rev.number, 0)

        alu = identity_from_nc_path(SAMPLES / "000814086.nc")
        self.assertEqual(alu.base, "000814086")
        self.assertIsNone(alu.rev)

    def test_header_rev_comment_wins(self) -> None:
        text = "%\nO1234 (D0134078-0)\n(REV 3)\nG21\nT1 M6\nM30\n"
        ident = identity_from_nc(filename="D0134078.nc", text=text)
        self.assertEqual(ident.base, "D0134078")
        self.assertEqual(ident.rev.number, 3)

    def test_rewizja_comment(self) -> None:
        text = "%\nO1 (SE0241282)\n(Rewizja: 02)\nT1 M6\nM30\n"
        ident = identity_from_nc(filename="SE0241282.nc", text=text)
        self.assertEqual(ident.rev.number, 2)


class TestPickModel(unittest.TestCase):
    def _files(self, *stems: str) -> list[ModelFile]:
        out: list[ModelFile] = []
        for i, stem in enumerate(stems):
            path = Path(f"/models/{stem}.stp")
            out.append(
                ModelFile(path=path, identity=parse_model_stem(stem), mtime=float(i))
            )
        return out

    def test_prefix_and_latest_rev_when_nc_has_none(self) -> None:
        nc = parse_model_stem("D0134078")
        models = self._files(
            "D0134078_Rev01",
            "D0134078_Rev03_machining",
            "D0134078_Rev02",
            "D0134079_Rev09",
        )
        picked = pick_model(nc, models)
        self.assertIsNotNone(picked)
        self.assertEqual(picked.identity.rev.number, 3)
        self.assertIn("Rev03", picked.path.stem)

    def test_gcode_rev_must_match_not_latest(self) -> None:
        nc = identity_from_nc(
            filename="D0134078.nc",
            text="%\nO1 (D0134078)\n(REV 2)\nT1 M6\nM30\n",
        )
        models = self._files("D0134078_Rev02", "D0134078_Rev03")
        picked = pick_model(nc, models)
        self.assertIsNotNone(picked)
        self.assertEqual(picked.identity.rev.number, 2)

    def test_nearby_part_number_does_not_match(self) -> None:
        nc = parse_model_stem("D0134078")
        models = self._files("D0134079_Rev01")
        self.assertIsNone(pick_model(nc, models))

    def test_closest_suffix_among_same_rev(self) -> None:
        nc = identity_from_nc(
            filename="SE0241282.nc",
            text="%\nO01282 (SE0241282-0 WIERCENIA)\nT1 M6\nM30\n",
        )
        models = self._files("SE0241282-0", "SE0241282-0_extra_notes")
        picked = pick_model(nc, models)
        self.assertEqual(picked.path.stem, "SE0241282-0")

    def test_index_walks_subfolders(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            nested = root / "cad" / "rev"
            nested.mkdir(parents=True)
            (nested / "D0134078_Rev01.STEP").write_text("solid", encoding="utf-8")
            (root / "ignore.txt").write_text("no", encoding="utf-8")
            found = index_models([root])
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].identity.base, "D0134078")


class TestEscposRaster(unittest.TestCase):
    def test_bitmap_sits_at_top_of_ticket(self) -> None:
        raster = bitmap_to_escpos(8, 8, bytes([0xFF] * 8))
        data = encode_ticket("HELLO", rasters=[raster])
        self.assertTrue(data.startswith(INIT))
        self.assertTrue(data.endswith(CUT))
        self.assertIn(b"\x1dv0\x00", data)
        hello_at = data.find(b"HELLO")
        raster_at = data.find(b"\x1dv0\x00")
        self.assertGreater(hello_at, raster_at)
        self.assertGreater(raster_at, 0)

    def test_ticket_without_rasters_unchanged_shape(self) -> None:
        data = encode_ticket("HELLO\nT15")
        self.assertTrue(data.startswith(INIT))
        self.assertIn(b"HELLO\r\nT15", data)
        self.assertTrue(data.endswith(CUT))


class TestKioskModelRoots(unittest.TestCase):
    def test_reads_several_model_roots(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "kiosk.ini"
            a = Path(raw) / "cad"
            b = Path(raw) / "archive"
            path.write_text(
                "[kiosk]\n"
                f"model_roots = {a},{b}\n"
                f"extra_roots = {Path(raw) / 'nc'}\n",
                encoding="utf-8",
            )
            cfg = load_kiosk_config(path)
            self.assertEqual(cfg.model_roots, [a, b])
            self.assertEqual(cfg.extra_roots, [Path(raw) / "nc"])

    def test_save_model_roots_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            dest = Path(raw) / "fh6parse-kiosk.ini"
            cad = Path(raw) / "cad"
            save_model_roots([cad], dest)
            cfg = load_kiosk_config(dest)
            self.assertEqual(cfg.model_roots, [cad])


class TestHtmlStepViews(unittest.TestCase):
    def test_print_html_embeds_png_near_top(self) -> None:
        result = parse_nc_file(SAMPLES / "D0134078.nc")
        with tempfile.TemporaryDirectory() as raw:
            png = Path(raw) / "iso.png"
            png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
            html = format_print_html(
                result, paper=PAPER_80MM, image_paths=[png]
            )
        self.assertIn("data:image/png;base64,", html)
        self.assertIn('class="step-view"', html)
        self.assertLess(html.find("step-views"), html.find("D0134078.nc"))


class TestTicketViewLayout(unittest.TestCase):
    def test_long_shaft_is_a_needle_across_80mm(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not installed")
        # 2 m × 20 mm bar, modeled along X, Y, or Z.
        for sizes in ((2000.0, 20.0, 20.0), (20.0, 2000.0, 20.0), (20.0, 20.0, 2000.0)):
            xs = np.linspace(-sizes[0] / 2, sizes[0] / 2, 5)
            ys = np.linspace(-sizes[1] / 2, sizes[1] / 2, 3)
            zs = np.linspace(-sizes[2] / 2, sizes[2] / 2, 3)
            grid = np.array([(x, y, z) for x in xs for y in ys for z in zs])
            width, height = ticket_view_pixels(grid)
            self.assertEqual(width, THERMAL_DOTS)
            self.assertLessEqual(height, MIN_VIEW_HEIGHT + 8)
            self.assertLess(height, width / 8)

    def test_bulky_part_height_is_capped(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not installed")
        xs = np.linspace(-50.0, 50.0, 4)
        grid = np.array([(x, y, z) for x in xs for y in xs for z in xs])
        width, height = ticket_view_pixels(grid)
        self.assertEqual(width, THERMAL_DOTS)
        self.assertLessEqual(height, MAX_VIEW_HEIGHT)

    def test_isometric_look_uses_all_three_axes(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not installed")
        cube = np.array(
            [[i, j, k] for i in (0.0, 1.0) for j in (0.0, 1.0) for k in (0.0, 1.0)]
        )
        look = _ticket_basis(cube, opposite=False)[:, 2]
        for component in look:
            self.assertAlmostEqual(abs(float(component)), 1.0 / np.sqrt(3.0), places=6)

    def test_isometric_axes_equally_foreshortened(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not installed")
        cube = np.array(
            [[i, j, k] for i in (0.0, 1.0) for j in (0.0, 1.0) for k in (0.0, 1.0)]
        )
        basis = _ticket_basis(cube, opposite=False)
        lengths = [float(np.linalg.norm((axis @ basis)[:2])) for axis in np.eye(3)]
        self.assertAlmostEqual(lengths[0], lengths[1], places=6)
        self.assertAlmostEqual(lengths[1], lengths[2], places=6)

    def test_longest_axis_stays_across_the_ticket(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not installed")
        box = np.array(
            [
                [x, y, z]
                for x in (-100.0, 100.0)
                for y in (-10.0, 10.0)
                for z in (-5.0, 5.0)
            ]
        )
        basis = _ticket_basis(box, opposite=False)
        projected = (np.array([1.0, 0.0, 0.0]) @ basis)[:2]
        self.assertGreater(abs(float(projected[0])), abs(float(projected[1])) * 8)

    def test_opposite_view_flips_look(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not installed")
        cube = np.array(
            [[i, j, k] for i in (0.0, 1.0) for j in (0.0, 1.0) for k in (0.0, 1.0)]
        )
        a = _ticket_basis(cube, opposite=False)[:, 2]
        b = _ticket_basis(cube, opposite=True)[:, 2]
        np.testing.assert_allclose(a, -b)

    def test_raster_is_visible_edges_not_shading(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not installed")
        vertices, faces = _outward_unit_cube()
        img = _raster_view(vertices, faces, opposite=False)
        unique = set(int(v) for v in np.unique(img))
        self.assertEqual(unique, {0, 255})
        ink = float((img == 0).mean())
        self.assertGreater(ink, 0.002)
        self.assertLess(ink, 0.12)
        # A filled isometric cube would ink a hexagon (~1/3 of the frame).
        self.assertLess(ink, 0.25)


class TestModelPrepDoesNotBlock(unittest.TestCase):
    def test_missing_model_returns_no_images(self) -> None:
        prep = ModelPrep([])
        self.assertEqual(prep.ready_images(Path("missing.nc")), [])
        self.assertFalse(prep.is_ready(Path("missing.nc")))


if __name__ == "__main__":
    unittest.main()
