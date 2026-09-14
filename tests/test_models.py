"""Part-id / STEP matching and ESC/POS raster helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fh6parse.kiosk import load_kiosk_config
from fh6parse.modelmatch import ModelFile, index_models, pick_model
from fh6parse.modelprep import ModelPrep
from fh6parse.partid import identity_from_nc, identity_from_nc_path, parse_model_stem
from fh6parse.printer import CUT, INIT, bitmap_to_escpos, encode_ticket

SAMPLES = Path(__file__).resolve().parent / "samples"


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


class TestModelPrepDoesNotBlock(unittest.TestCase):
    def test_missing_model_returns_no_images(self) -> None:
        prep = ModelPrep([])
        self.assertEqual(prep.ready_images(Path("missing.nc")), [])
        self.assertFalse(prep.is_ready(Path("missing.nc")))


if __name__ == "__main__":
    unittest.main()
