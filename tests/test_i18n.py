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
    tool_count,
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

    def test_polish_tool_plural(self) -> None:
        self.assertEqual(tool_count("pl", 1), "1 narzędzie")
        self.assertEqual(tool_count("pl", 2), "2 narzędzia")
        self.assertEqual(tool_count("pl", 5), "5 narzędzi")
        self.assertEqual(tool_count("en", 1), "1 tool")
        self.assertEqual(tool_count("en", 6), "6 tools")

    def test_update_button_follows_language(self) -> None:
        status = UpdateCheck(
            True, "available", current_version="1.3.4", new_version="1.3.5"
        )
        self.assertIn("AKTUALIZUJ do 1.3.5", update_button_label("pl", status))
        self.assertIn("UPDATE to 1.3.5", update_button_label("en", status))

    def test_update_button_uses_sha_when_remote_is_older(self) -> None:
        status = UpdateCheck(
            True,
            "available",
            current_version="1.4.1",
            new_version="1.4.0",
            remote_sha="abc1234",
        )
        self.assertEqual(update_button_label("en", status), "UPDATE  abc1234")
        self.assertIn("abc1234", update_button_label("pl", status))

    def test_placeholders_match(self) -> None:
        import re

        def fields(text: str) -> tuple[str, ...]:
            return tuple(re.findall(r"\{(\w+)\}", text))

        for key in STRINGS["en"]:
            self.assertEqual(
                fields(STRINGS["en"][key]),
                fields(STRINGS["pl"][key]),
                key,
            )

    def test_default_mill_label_follows_language(self) -> None:
        from fh6parse.kiosk import machine_display_name
        from fh6parse.machtime import DEFAULT_MACHINE, MachineProfile

        self.assertEqual(machine_display_name(DEFAULT_MACHINE, "en"), "Default mill")
        self.assertEqual(
            machine_display_name(DEFAULT_MACHINE, "pl"), "Domyślna obrabiarka"
        )
        custom = MachineProfile(id="default", name="Haas VF-2")
        self.assertEqual(machine_display_name(custom, "pl"), "Haas VF-2")

    def test_print_and_gpio_errors_are_translated(self) -> None:
        self.assertEqual(t("en", "print_fail", detail="lp0"), "Print failed: lp0")
        self.assertEqual(t("pl", "print_fail", detail="lp0"), "Druk nieudany: lp0")
        self.assertEqual(t("pl", "print_paper"), "Brak papieru")
        self.assertEqual(t("en", "print_cover"), "Printer cover open")
        self.assertIn("python3-lgpio", t("pl", "gpio_pi5"))
        self.assertIn("RPi.GPIO", t("en", "gpio_pi5"))

    def test_print_legend_matches_panel_buttons(self) -> None:
        self.assertIn("LOAD", t("en", "legend_load"))
        self.assertIn("short", t("en", "legend_load"))
        self.assertIn("SET", t("en", "legend_set"))
        self.assertIn("RUN", t("en", "legend_run"))
        self.assertIn("załadunek", t("pl", "legend_load"))
        self.assertIn("ustawianie", t("pl", "legend_set"))
        self.assertIn("pełny", t("pl", "legend_run"))
        self.assertIn("green", t("en", "pin_load"))
        self.assertIn("zielony", t("pl", "pin_load"))


class TestTicketLanguage(unittest.TestCase):
    def _sample(self):
        from fh6parse.parser import parse_nc_text

        src = """O1
T1 M6
G43 Z10. H99
G1 Z-1. F200
M30
"""
        return parse_nc_text(src, "t.nc")

    def test_default_ticket_stays_english(self) -> None:
        from fh6parse.report import PAPER_80MM, format_print_html, format_report

        r = self._sample()
        text = format_report(r)
        self.assertIn("CNC TOOL REPORT  |  A4", text)
        self.assertIn("WARNING: H99 does not match T1", text)
        self.assertIn("Cycle ", text)
        mm = format_report(r, paper=PAPER_80MM)
        self.assertIn("SPLIT", mm)
        html = format_print_html(r)
        self.assertIn('lang="en"', html)
        self.assertIn("Print", html)

    def test_polish_tickets_translate_labels_and_warnings(self) -> None:
        from fh6parse.report import (
            PAPER_80MM,
            PAPER_80MM_MIN,
            format_print_html,
            format_report,
        )

        r = self._sample()
        a4 = format_report(r, lang="pl")
        self.assertIn("RAPORT NARZĘDZI CNC  |  A4", a4)
        self.assertIn("UWAGA: H99 nie zgadza się z T1", a4)
        self.assertIn("Cykl ", a4)
        self.assertIn("Udział cyklu", a4)
        self.assertNotIn("WARNING:", a4)
        mm = format_report(r, paper=PAPER_80MM, lang="pl")
        self.assertIn("ROZKŁAD", mm)
        self.assertIn("KAŻDA WYMIANA", mm)
        mini = format_report(r, paper=PAPER_80MM_MIN, lang="pl")
        self.assertIn("NARZĘDZIA CNC ZAŁADUNEK", mini)
        html = format_print_html(r, lang="pl")
        self.assertIn('lang="pl"', html)
        self.assertIn("Drukuj", html)
        self.assertIn("H99 nie zgadza się z T1", html)


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

    def test_overlay_keys_include_gpio(self) -> None:
        from fh6parse.kiosk import UI_OVERLAY_KEYS

        self.assertIn("encoder_clk", UI_OVERLAY_KEYS)
        self.assertIn("encoder_steps", UI_OVERLAY_KEYS)
        self.assertIn("button_load", UI_OVERLAY_KEYS)
        self.assertIn("encoder_mill_clk", UI_OVERLAY_KEYS)
        self.assertIn("report_load", UI_OVERLAY_KEYS)
        self.assertIn("report_run", UI_OVERLAY_KEYS)
        self.assertNotIn("width", UI_OVERLAY_KEYS)
        self.assertNotIn("height", UI_OVERLAY_KEYS)
