"""Polish / English UI catalogs and kiosk language persistence."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fh6parse.i18n import (
    GUI_DEFAULT,
    KIOSK_DEFAULT,
    STRINGS,
    file_count,
    parse_language,
    t,
    update_button_label,
)
from fh6parse.kiosk import load_kiosk_config, save_kiosk_values
from fh6parse.update import UpdateCheck


class TestI18n(unittest.TestCase):
    def test_catalogs_have_the_same_keys(self) -> None:
        self.assertEqual(set(STRINGS["pl"]), set(STRINGS["en"]))

    def test_kiosk_default_is_polish(self) -> None:
        self.assertEqual(KIOSK_DEFAULT, "pl")
        self.assertEqual(parse_language("", default=KIOSK_DEFAULT), "pl")
        self.assertEqual(t("pl", "insert_usb"), "Włóż pendrive")
        self.assertEqual(t("en", "insert_usb"), "Insert USB")

    def test_gui_default_is_english(self) -> None:
        self.assertEqual(GUI_DEFAULT, "en")
        self.assertEqual(parse_language("", default=GUI_DEFAULT), "en")

    def test_aliases(self) -> None:
        self.assertEqual(parse_language("PL"), "pl")
        self.assertEqual(parse_language("polski"), "pl")
        self.assertEqual(parse_language("en_GB"), "en")

    def test_polish_file_plural(self) -> None:
        self.assertEqual(file_count("pl", 1), "1 plik")
        self.assertEqual(file_count("pl", 2), "2 pliki")
        self.assertEqual(file_count("pl", 4), "4 pliki")
        self.assertEqual(file_count("pl", 5), "5 plików")
        self.assertEqual(file_count("pl", 12), "12 plików")
        self.assertEqual(file_count("pl", 22), "22 pliki")
        self.assertEqual(file_count("en", 1), "1 file")
        self.assertEqual(file_count("en", 3), "3 files")

    def test_update_button_follows_language(self) -> None:
        status = UpdateCheck(
            True, "available", current_version="1.3.4", new_version="1.3.5"
        )
        self.assertIn("AKTUALIZUJ do 1.3.5", update_button_label("pl", status))
        self.assertIn("UPDATE to 1.3.5", update_button_label("en", status))


class TestLanguageIni(unittest.TestCase):
    def setUp(self) -> None:
        import os
        from unittest.mock import patch

        self._home = tempfile.TemporaryDirectory()
        self._home_patch = patch.dict(
            os.environ,
            {"HOME": self._home.name, "USERPROFILE": self._home.name},
        )
        self._home_patch.start()

    def tearDown(self) -> None:
        self._home_patch.stop()
        self._home.cleanup()

    def test_missing_language_stays_unset(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "kiosk.ini"
            path.write_text("[kiosk]\nidle_seconds = 60\n", encoding="utf-8")
            cfg = load_kiosk_config(path)
            self.assertEqual(cfg.language, "")
            self.assertEqual(cfg.source, path)

    def test_reads_and_saves_language_without_dropping_pins(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "kiosk.ini"
            path.write_text(
                "[kiosk]\nencoder_clk = 5\nlanguage = en\n",
                encoding="utf-8",
            )
            cfg = load_kiosk_config(path)
            self.assertEqual(cfg.language, "en")
            saved = save_kiosk_values({"language": "pl"}, path)
            again = load_kiosk_config(saved)
            self.assertEqual(again.language, "pl")
            self.assertEqual(again.encoder_clk, 5)

    def test_user_overlay_overrides_main_ini(self) -> None:
        from fh6parse.kiosk import ui_overlay_path

        with tempfile.TemporaryDirectory() as raw:
            main = Path(raw) / "kiosk.ini"
            main.write_text("[kiosk]\nlanguage = en\n", encoding="utf-8")
            save_kiosk_values({"language": "pl"}, ui_overlay_path())
            cfg = load_kiosk_config(main)
            self.assertEqual(cfg.language, "pl")
