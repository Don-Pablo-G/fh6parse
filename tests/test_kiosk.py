"""Kiosk helpers: screensaver gate, USB file scan, ESC/POS payload."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fh6parse.idle import ScreensaverGate
from fh6parse.kiosk import _gpio_fail_hint, load_kiosk_config, prefer_lgpio_factory
from fh6parse.printer import CUT, INIT, encode_ticket, print_ticket
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

    def test_writes_usb_device_and_skips_cups(self) -> None:
        from unittest.mock import patch

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            dest = Path(tmp.name)
        try:
            with patch("fh6parse.printer.shutil.which", return_value="/usr/bin/lp"):
                with patch("fh6parse.printer.subprocess.run") as run:
                    route = print_ticket(
                        "HELLO", queue="munbyn", device=str(dest)
                    )
            self.assertEqual(route, f"device:{dest}")
            run.assert_not_called()
            data = dest.read_bytes()
            self.assertTrue(data.startswith(INIT))
            self.assertTrue(data.endswith(CUT))
        finally:
            dest.unlink(missing_ok=True)

    def test_named_cups_only_if_device_missing(self) -> None:
        from unittest.mock import MagicMock, patch

        proc = MagicMock(returncode=0, stderr=b"")
        with patch("fh6parse.printer.shutil.which", return_value="/usr/bin/lp"):
            with patch("fh6parse.printer.subprocess.run", return_value=proc) as run:
                route = print_ticket(
                    "HELLO",
                    queue="munbyn",
                    device="/no/such/fh6parse-lp",
                )
        self.assertEqual(route, "lp:munbyn")
        cmd = run.call_args[0][0]
        self.assertEqual(cmd[:4], ["/usr/bin/lp", "-d", "munbyn", "-o"])
        self.assertEqual(cmd[4], "raw")

    def test_empty_queue_never_calls_lp(self) -> None:
        from unittest.mock import patch

        with patch("fh6parse.printer.shutil.which", return_value="/usr/bin/lp"):
            with patch("fh6parse.printer.subprocess.run") as run:
                with self.assertRaises(RuntimeError) as ctx:
                    print_ticket(
                        "HELLO",
                        queue="",
                        device="/no/such/fh6parse-lp",
                    )
        run.assert_not_called()
        self.assertIn("missing", str(ctx.exception))


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
            self.assertEqual(cfg.encoder_steps, 1)
            self.assertEqual(cfg.printer_queue, "")
            self.assertEqual(str(cfg.printer_device), "/dev/usb/lp0")

    def test_reads_encoder_steps(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "kiosk.ini"
            path.write_text("[kiosk]\nencoder_steps = 4\n", encoding="utf-8")
            cfg = load_kiosk_config(path)
            self.assertEqual(cfg.encoder_steps, 4)

    def test_encoder_steps_clamped(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "kiosk.ini"
            path.write_text("[kiosk]\nencoder_steps = 99\n", encoding="utf-8")
            self.assertEqual(load_kiosk_config(path).encoder_steps, 16)
            path.write_text("[kiosk]\nencoder_steps = 0\n", encoding="utf-8")
            self.assertEqual(load_kiosk_config(path).encoder_steps, 1)

    def test_overlay_overrides_pins_and_steps(self) -> None:
        import os
        from unittest.mock import patch

        from fh6parse.kiosk import save_kiosk_values, ui_overlay_path

        with tempfile.TemporaryDirectory() as home:
            with patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
                with tempfile.TemporaryDirectory() as raw:
                    main = Path(raw) / "kiosk.ini"
                    main.write_text(
                        "[kiosk]\nencoder_clk = 17\nencoder_steps = 1\n",
                        encoding="utf-8",
                    )
                    save_kiosk_values(
                        {
                            "encoder_clk": "5",
                            "encoder_steps": "2",
                            "encoder_swap": "true",
                        },
                        ui_overlay_path(),
                    )
                    cfg = load_kiosk_config(main)
                    self.assertEqual(cfg.encoder_clk, 5)
                    self.assertEqual(cfg.encoder_steps, 2)
                    self.assertTrue(cfg.encoder_swap)


    def test_reads_machine_table(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "kiosk.ini"
            path.write_text(
                "[kiosk]\nmachine = vf-4ss\n\n"
                "[machine.vf-4ss]\n"
                "name = Haas VF-4SS\n"
                "rapid_mm_min = 25400\n"
                "rotary_deg_min = 6000\n"
                "tool_change_s = 2.8\n",
                encoding="utf-8",
            )
            cfg = load_kiosk_config(path)
            self.assertEqual(cfg.machine_id, "vf-4ss")
            mill = cfg.active_machine()
            self.assertEqual(mill.id, "vf-4ss")
            self.assertEqual(mill.name, "Haas VF-4SS")
            self.assertEqual(mill.rapid_mm_min, 25400.0)
            self.assertEqual(mill.rotary_deg_min, 6000.0)
            self.assertAlmostEqual(mill.tool_change_s, 2.8)
            self.assertEqual(cfg.machines[0].id, "default")

    def test_unknown_machine_falls_back_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "kiosk.ini"
            path.write_text("[kiosk]\nmachine = missing\n", encoding="utf-8")
            cfg = load_kiosk_config(path)
            self.assertEqual(cfg.machine_id, "default")
            self.assertEqual(cfg.active_machine().rapid_mm_min, 20000.0)

    def test_overlay_overrides_machine(self) -> None:
        import os
        from unittest.mock import patch

        from fh6parse.kiosk import save_kiosk_values, ui_overlay_path

        with tempfile.TemporaryDirectory() as home:
            with patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
                with tempfile.TemporaryDirectory() as raw:
                    main = Path(raw) / "kiosk.ini"
                    main.write_text(
                        "[kiosk]\nmachine = default\n\n"
                        "[machine.vf-2]\n"
                        "name = Haas VF-2\n"
                        "rapid_mm_min = 25400\n"
                        "tool_change_s = 8\n",
                        encoding="utf-8",
                    )
                    save_kiosk_values({"machine": "vf-2"}, ui_overlay_path())
                    cfg = load_kiosk_config(main)
                    self.assertEqual(cfg.machine_id, "vf-2")
                    self.assertEqual(cfg.active_machine().tool_change_s, 8.0)

    def test_unique_machine_id_avoids_default_and_collisions(self) -> None:
        from fh6parse.kiosk import unique_machine_id

        self.assertEqual(unique_machine_id("Default mill"), "mill")
        self.assertEqual(unique_machine_id("Haas VF-4SS"), "haas-vf-4ss")
        self.assertEqual(
            unique_machine_id("Haas VF-4SS", {"haas-vf-4ss"}), "haas-vf-4ss-2"
        )

    def test_parse_machine_form_converts_m_min(self) -> None:
        from fh6parse.kiosk import parse_machine_form

        mill = parse_machine_form(
            name="Haas VF-4SS",
            rapid_m_min="25,4",
            rotary_deg_min="6000",
            tool_change_s="2.8",
        )
        self.assertEqual(mill.id, "haas-vf-4ss")
        self.assertEqual(mill.name, "Haas VF-4SS")
        self.assertAlmostEqual(mill.rapid_mm_min, 25400.0)
        self.assertEqual(mill.rotary_deg_min, 6000.0)
        self.assertAlmostEqual(mill.tool_change_s, 2.8)

    def test_parse_machine_form_requires_name(self) -> None:
        from fh6parse.kiosk import parse_machine_form

        with self.assertRaises(ValueError) as ctx:
            parse_machine_form(name="  ")
        self.assertEqual(str(ctx.exception), "machine_name_required")

    def test_save_machine_profile_round_trips(self) -> None:
        from fh6parse.kiosk import parse_machine_form, save_machine_profile

        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "kiosk.ini"
            path.write_text("[kiosk]\nmachine = default\n", encoding="utf-8")
            mill = parse_machine_form(
                name="Haas VF-2",
                rapid_m_min="25.4",
                tool_change_s="8",
            )
            save_machine_profile(mill, dest=path)
            cfg = load_kiosk_config(path)
            self.assertEqual(cfg.machine_id, "haas-vf-2")
            self.assertEqual(cfg.active_machine().name, "Haas VF-2")
            self.assertAlmostEqual(cfg.active_machine().rapid_mm_min, 25400.0)
            self.assertEqual(cfg.active_machine().tool_change_s, 8.0)


    def test_reads_last_folder_and_paper(self) -> None:
        from fh6parse.kiosk import parse_gui_paper
        from fh6parse.report import PAPER_80MM

        self.assertEqual(parse_gui_paper("80mm"), PAPER_80MM)
        self.assertEqual(parse_gui_paper("thermal"), PAPER_80MM)
        self.assertEqual(parse_gui_paper("nope"), "a4")
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "kiosk.ini"
            nc = Path(raw) / "stick"
            nc.mkdir()
            path.write_text(
                "[kiosk]\n"
                f"last_nc_dir = {nc.as_posix()}\n"
                f"last_out_dir = {Path(raw).as_posix()}\n"
                "last_paper = 80mm\n",
                encoding="utf-8",
            )
            cfg = load_kiosk_config(path)
            self.assertEqual(Path(cfg.last_nc_dir), nc)
            self.assertEqual(Path(cfg.last_out_dir), Path(raw))
            self.assertEqual(cfg.last_paper, PAPER_80MM)

    def test_overlay_overrides_last_paper(self) -> None:
        import os
        from unittest.mock import patch

        from fh6parse.kiosk import save_kiosk_values, ui_overlay_path
        from fh6parse.report import PAPER_80MM

        with tempfile.TemporaryDirectory() as home:
            with patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
                with tempfile.TemporaryDirectory() as raw:
                    main = Path(raw) / "kiosk.ini"
                    main.write_text("[kiosk]\nlast_paper = a4\n", encoding="utf-8")
                    save_kiosk_values({"last_paper": "80mm"}, ui_overlay_path())
                    cfg = load_kiosk_config(main)
                    self.assertEqual(cfg.last_paper, PAPER_80MM)


class TestKioskPreview(unittest.TestCase):
    def test_two_ops_show_tools_time_and_step(self) -> None:
        from fh6parse.kiosk import format_kiosk_preview
        from fh6parse.parser import parse_nc_file

        samples = Path(__file__).resolve().parent / "samples"
        r = parse_nc_file(samples / "000814086.nc")
        text = format_kiosk_preview(r, lang="en", step_ready=False)
        self.assertIn("OP1", text)
        self.assertIn("OP2", text)
        self.assertIn("tools", text)
        self.assertIn("no STEP", text)
        self.assertNotIn("3D ready", text)
        ready = format_kiosk_preview(r, lang="en", step_ready=True)
        self.assertIn("3D ready", ready)
        pl = format_kiosk_preview(r, lang="pl", step_ready=False)
        self.assertIn("narzęd", pl)
        self.assertIn("brak STEP", pl)
        rendering = format_kiosk_preview(r, lang="en", cad_reason="rendering")
        self.assertIn("rendering…", rendering)
        searching = format_kiosk_preview(r, lang="pl", cad_reason="searching")
        self.assertIn("szuka…", searching)
        share = format_kiosk_preview(r, lang="pl", cad_reason="share_down")
        self.assertIn("Z: wył.", share)

    def test_single_op_shows_cycle(self) -> None:
        from fh6parse.kiosk import format_kiosk_preview
        from fh6parse.parser import parse_nc_text

        src = """O1
T1 M6
G90 G94
G0 X0 Y0 Z0
G1 X100 F500
M30
"""
        r = parse_nc_text(src, "t.nc")
        text = format_kiosk_preview(r, lang="en", step_ready=True)
        self.assertIn("MAIN", text)
        self.assertIn("1 tool", text)
        self.assertIn("0:12", text)
        self.assertIn("3D ready", text)


class TestEncoderClicks(unittest.TestCase):
    def test_one_tick_is_one_file_by_default(self) -> None:
        from fh6parse.kiosk import encoder_file_delta

        moved, left = encoder_file_delta(1, 0, 1)
        self.assertEqual((moved, left), (1, 0))
        moved, left = encoder_file_delta(-1, 0, 1)
        self.assertEqual((moved, left), (-1, 0))

    def test_rest_wiggle_does_not_change_file(self) -> None:
        from fh6parse.kiosk import encoder_file_delta

        moved, leftover = encoder_file_delta(1, 0, 4)
        self.assertEqual((moved, leftover), (0, 1))
        moved, leftover = encoder_file_delta(-1, leftover, 4)
        self.assertEqual((moved, leftover), (0, 0))

    def test_highlight_changes_at_half_tooth(self) -> None:
        from fh6parse.kiosk import encoder_file_delta

        leftover = 0
        moved, leftover = encoder_file_delta(1, leftover, 4)
        self.assertEqual((moved, leftover), (0, 1))
        moved, leftover = encoder_file_delta(1, leftover, 4)
        self.assertEqual(moved, 1)
        self.assertEqual(leftover, -2)

    def test_full_tooth_lands_on_next_rest(self) -> None:
        from fh6parse.kiosk import encoder_file_delta

        leftover = 0
        moved_total = 0
        for _ in range(4):
            moved, leftover = encoder_file_delta(1, leftover, 4)
            moved_total += moved
        self.assertEqual(moved_total, 1)
        self.assertEqual(leftover, 0)

    def test_two_teeth_are_two_files(self) -> None:
        from fh6parse.kiosk import encoder_file_delta

        leftover = 0
        moved_total = 0
        for _ in range(8):
            moved, leftover = encoder_file_delta(1, leftover, 4)
            moved_total += moved
        self.assertEqual(moved_total, 2)
        self.assertEqual(leftover, 0)

    def test_next_unused_bcm_skips_taken_pins(self) -> None:
        from fh6parse.kiosk import next_unused_bcm

        self.assertEqual(next_unused_bcm(17, {18, 19}, 1), 20)
        self.assertEqual(next_unused_bcm(17, {16}, -1), 15)
        self.assertEqual(next_unused_bcm(27, {0}, 1), 1)


class TestUsbReload(unittest.TestCase):
    def test_file_stamp_changes_with_size(self) -> None:
        from fh6parse.kiosk import file_stamp, preview_cache_stale

        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "a.nc"
            path.write_bytes(b"O1\nM30\n")
            first = file_stamp(path)
            self.assertIsNotNone(first)
            path.write_bytes(b"O1\nT1 M6\nG0 X0\nM30\n")
            second = file_stamp(path)
            self.assertIsNotNone(second)
            self.assertNotEqual(first, second)
            self.assertTrue(preview_cache_stale(first, second))
            self.assertFalse(preview_cache_stale(second, second))
            self.assertTrue(preview_cache_stale(None, second))
            self.assertFalse(preview_cache_stale(first, None))

    def test_usb_remove_hint(self) -> None:
        from fh6parse.kiosk import usb_remove_hint

        self.assertEqual(usb_remove_hint("en", has_usb=False, busy=True), "")
        self.assertEqual(
            usb_remove_hint("en", has_usb=True, busy=True), "Reading USB — wait"
        )
        self.assertEqual(
            usb_remove_hint("pl", has_usb=True, busy=False), "Można wyjąć"
        )

    def test_path_on_usb(self) -> None:
        from fh6parse.kiosk import path_on_usb

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            nested = root / "op1"
            nested.mkdir()
            nc = nested / "a.nc"
            nc.write_text("O1\nM30\n", encoding="utf-8")
            self.assertTrue(path_on_usb(nc, [root]))
            self.assertFalse(path_on_usb(nc, [root / "other"]))


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
        hint = _gpio_fail_hint(
            RuntimeError("Unable to load RPi.GPIO pin factory"), "en"
        )
        self.assertIn("python3-lgpio", hint)
        self.assertIn("Pi 5", hint)
        pl = _gpio_fail_hint(
            RuntimeError("Unable to load RPi.GPIO pin factory"), "pl"
        )
        self.assertIn("wymaga python3-lgpio", pl)


if __name__ == "__main__":
    unittest.main()
