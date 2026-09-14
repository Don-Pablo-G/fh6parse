"""Kiosk helpers: screensaver gate, USB file scan, ESC/POS payload."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fh6parse.idle import ScreensaverGate
from fh6parse.kiosk import _gpio_fail_hint, load_kiosk_config, prefer_lgpio_factory
from fh6parse.printer import CUT, INIT, encode_ticket
from fh6parse.usbwatch import list_nc_files


class TestScreensaverGate(unittest.TestCase):
    def test_encoder_wakes_without_step(self) -> None:
        gate = ScreensaverGate(60)
        self.assertTrue(gate.sleep())
        self.assertEqual(gate.encoder(), "wake")
        self.assertFalse(gate.asleep)
        self.assertEqual(gate.encoder(), "step")

    def test_usb_insert_wakes(self) -> None:
        gate = ScreensaverGate(60)
        gate.sleep()
        self.assertEqual(gate.usb_insert(), "wake")
        self.assertFalse(gate.asleep)
        self.assertEqual(gate.usb_insert(), "ok")

    def test_hid_wakes_without_print(self) -> None:
        gate = ScreensaverGate(60)
        gate.sleep()
        self.assertFalse(gate.allow_print())
        self.assertEqual(gate.hid(), "wake")
        self.assertFalse(gate.asleep)
        self.assertTrue(gate.allow_print())
        self.assertEqual(gate.hid(), "ok")

    def test_print_ignored_while_asleep(self) -> None:
        gate = ScreensaverGate(60)
        self.assertTrue(gate.allow_print())
        gate.sleep()
        self.assertFalse(gate.allow_print())
        self.assertTrue(gate.asleep)

    def test_disabled_idle_never_sleeps(self) -> None:
        gate = ScreensaverGate(0)
        self.assertFalse(gate.enabled)
        self.assertFalse(gate.sleep())
        self.assertFalse(gate.asleep)


class TestUsbWatch(unittest.TestCase):
    def test_lists_nc_in_root_only_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "a.nc").write_text("O1\nM30\n", encoding="utf-8")
            (root / "notes.txt").write_text("nope", encoding="utf-8")
            sub = root / "op1"
            sub.mkdir()
            (sub / "b.TAP").write_text("O2\nM30\n", encoding="utf-8")
            hidden = root / ".hidden"
            hidden.mkdir()
            (hidden / "secret.nc").write_text("O3\nM30\n", encoding="utf-8")
            files = list_nc_files([root])
            names = {p.name.lower() for p in files}
            self.assertEqual(names, {"a.nc"})

    def test_scan_depth_can_include_subfolders(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "a.nc").write_text("O1\nM30\n", encoding="utf-8")
            sub = root / "op1"
            sub.mkdir()
            (sub / "b.TAP").write_text("O2\nM30\n", encoding="utf-8")
            files = list_nc_files([root], max_depth=2)
            names = {p.name.lower() for p in files}
            self.assertEqual(names, {"a.nc", "b.tap"})


class TestPrinter(unittest.TestCase):
    def test_ticket_is_escpos_with_cut(self) -> None:
        data = encode_ticket("HELLO\nT15")
        self.assertTrue(data.startswith(INIT))
        self.assertIn(b"HELLO\r\nT15", data)
        self.assertTrue(data.endswith(CUT))
        self.assertNotIn(b"\x00HELLO", data)


class TestKioskConfig(unittest.TestCase):
    def test_reads_idle_and_pins(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "kiosk.ini"
            path.write_text(
                "[kiosk]\nidle_seconds = 60\nencoder_clk = 5\nbutton_full = 6\n",
                encoding="utf-8",
            )
            cfg = load_kiosk_config(path)
            self.assertEqual(cfg.idle_seconds, 60.0)
            self.assertEqual(cfg.encoder_clk, 5)
            self.assertEqual(cfg.button_full, 6)


class TestPi5GpioFactory(unittest.TestCase):
    def test_env_factory_is_left_alone(self) -> None:
        import os

        previous = os.environ.get("GPIOZERO_PIN_FACTORY")
        os.environ["GPIOZERO_PIN_FACTORY"] = "mock"
        try:
            self.assertEqual(prefer_lgpio_factory(), "mock")
        finally:
            if previous is None:
                os.environ.pop("GPIOZERO_PIN_FACTORY", None)
            else:
                os.environ["GPIOZERO_PIN_FACTORY"] = previous

    def test_missing_gpiozero_is_empty(self) -> None:
        import os

        previous = os.environ.pop("GPIOZERO_PIN_FACTORY", None)
        try:
            name = prefer_lgpio_factory()
        finally:
            if previous is not None:
                os.environ["GPIOZERO_PIN_FACTORY"] = previous
        self.assertIn(name, {"", "lgpio"})

    def test_rpi_gpio_error_mentions_pi5(self) -> None:
        hint = _gpio_fail_hint(RuntimeError("Unable to load RPi.GPIO pin factory"))
        self.assertIn("python3-lgpio", hint)
        self.assertIn("Pi 5", hint)


if __name__ == "__main__":
    unittest.main()
