"""Company STEP folders stay read-only; cache writes stay in temp."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fh6parse.modelrender import cache_dir, ensure_cache_path, staged_step_copy
from fh6parse.parser import parse_nc_text
from fh6parse.report import write_report
from fh6parse.safepath import ProtectedWriteError, is_protected, refuse_write
from fh6parse.usbwatch import SKIP_FS


class TestSafePath(unittest.TestCase):
    def test_company_folder_and_children_are_protected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "cad"
            root.mkdir()
            child = root / "stp" / "part.stp"
            child.parent.mkdir()
            child.write_text("solid", encoding="utf-8")
            other = Path(raw) / "reports"
            other.mkdir()
            self.assertTrue(is_protected(root, [root]))
            self.assertTrue(is_protected(child, [root]))
            self.assertFalse(is_protected(other, [root]))
            refuse_write(other, [root])
            with self.assertRaises(ProtectedWriteError):
                refuse_write(child, [root])

    def test_write_report_refuses_company_folder(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            cad = Path(raw) / "cad"
            cad.mkdir()
            nc = cad / "t.nc"
            nc.write_text("O1\nT1 M6\nG1 Z-1. F100\nM30\n", encoding="utf-8")
            result = parse_nc_text(nc.read_text(encoding="utf-8"), nc)
            with self.assertRaises(ProtectedWriteError):
                write_report(result, protected_roots=[cad])
            self.assertEqual(list(cad.glob("*_tool_report*")), [])

    def test_write_report_allows_other_folder(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            cad = Path(raw) / "cad"
            out = Path(raw) / "out"
            cad.mkdir()
            out.mkdir()
            nc = cad / "t.nc"
            nc.write_text("O1\nT1 M6\nG1 Z-1. F100\nM30\n", encoding="utf-8")
            result = parse_nc_text(nc.read_text(encoding="utf-8"), nc)
            dests = write_report(result, out_dir=out, protected_roots=[cad])
            self.assertTrue(dests)
            self.assertTrue(all(p.parent == out for p in dests))
            self.assertEqual(list(cad.glob("*_tool_report*")), [])

    def test_cache_dest_cannot_leave_temp(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            outside = Path(raw) / "cad" / "sneaky.png"
            outside.parent.mkdir()
            with self.assertRaises(PermissionError):
                ensure_cache_path(outside)
        dest = cache_dir() / "ok.png"
        self.assertEqual(ensure_cache_path(dest), dest.resolve())

    def test_step_copy_reads_source_and_writes_only_cache(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            src = Path(raw) / "part.stp"
            payload = b"ISO-10303-21; dummy"
            src.write_bytes(payload)
            before = src.stat()
            copy = staged_step_copy(src)
            self.assertTrue(str(copy).startswith(str(cache_dir().resolve())))
            self.assertEqual(copy.read_bytes(), payload)
            after = src.stat()
            self.assertEqual(after.st_mtime, before.st_mtime)
            self.assertEqual(after.st_size, before.st_size)

    def test_usb_scan_skips_windows_share_filesystems(self) -> None:
        for name in ("cifs", "smb3", "nfs4"):
            self.assertIn(name, SKIP_FS)


if __name__ == "__main__":
    unittest.main()
