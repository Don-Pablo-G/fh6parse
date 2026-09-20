"""Office GUI helpers that do not need a Tk display."""

from __future__ import annotations

import unittest

from fh6parse.gui import nc_keys_to_reload


class TestGuiReload(unittest.TestCase):
    def test_reload_when_mtime_or_size_changes(self) -> None:
        stamps = {"a.nc": (100.0, 10), "b.nc": (200.0, 20)}
        disk = {"a.nc": (100.0, 10), "b.nc": (200.0, 20)}
        self.assertEqual(nc_keys_to_reload(stamps, disk), [])
        disk["a.nc"] = (101.0, 10)
        self.assertEqual(nc_keys_to_reload(stamps, disk), ["a.nc"])
        disk["a.nc"] = (100.0, 11)
        self.assertEqual(nc_keys_to_reload(stamps, disk), ["a.nc"])

    def test_missing_file_does_not_reload(self) -> None:
        stamps = {"gone.nc": (1.0, 8)}
        self.assertEqual(nc_keys_to_reload(stamps, {"gone.nc": None}), [])

    def test_new_stamp_after_first_parse(self) -> None:
        stamps = {"a.nc": None}
        self.assertEqual(
            nc_keys_to_reload(stamps, {"a.nc": (1.0, 4)}),
            ["a.nc"],
        )
