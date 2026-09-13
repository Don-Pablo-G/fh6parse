"""Source-checkout update: git pull --ff-only, pip only if pyproject changed."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from fh6parse.update import FROZEN_MSG, find_git_root, perform_update


class _Proc:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestFindGitRoot(unittest.TestCase):
    def test_walks_up_to_dot_git(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / ".git").mkdir()
            nested = root / "fh6parse" / "pkg"
            nested.mkdir(parents=True)
            self.assertEqual(find_git_root(nested / "update.py"), root)

    def test_missing_git_is_none(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            self.assertIsNone(find_git_root(Path(raw)))


class TestPerformUpdate(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".git").mkdir()
        (self.root / "fh6parse").mkdir()
        self.start = self.root / "fh6parse" / "update.py"
        self.start.write_text("# stub\n", encoding="utf-8")
        self.calls: list[list[str]] = []

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_frozen_exits_2(self) -> None:
        err = io.StringIO()
        code = perform_update(frozen=True, start=self.start, stderr=err, stdout=io.StringIO())
        self.assertEqual(code, 2)
        self.assertIn("one-file package", err.getvalue())
        self.assertIn(FROZEN_MSG.split(";")[0], err.getvalue())

    def test_skip_pip_when_pyproject_unchanged(self) -> None:
        def run(cmd: list[str], **_kwargs) -> _Proc:
            self.calls.append(cmd)
            joined = " ".join(cmd)
            if "rev-parse" in joined:
                return _Proc(0, stdout="deadbeef\n")
            if "pull" in joined:
                return _Proc(0, stdout="Already up to date.\n")
            if "diff" in joined:
                return _Proc(0, stdout="")
            if joined.startswith("systemctl cat"):
                return _Proc(0, stdout="# unit\n")
            if joined.startswith("systemctl restart"):
                return _Proc(0)
            if "pip" in cmd:
                self.fail("pip should not run when pyproject is unchanged")
            return _Proc(0)

        out = io.StringIO()
        code = perform_update(
            frozen=False,
            start=self.start,
            runner=run,
            stdout=out,
            stderr=io.StringIO(),
        )
        self.assertEqual(code, 0)
        self.assertIn("skipping pip", out.getvalue())
        self.assertIn("restarted fh6parse-kiosk", out.getvalue())
        self.assertTrue(any("pull" in " ".join(c) and "--ff-only" in c for c in self.calls))

    def test_pip_when_pyproject_changed(self) -> None:
        heads = iter(["oldsha\n", "newsha\n"])

        def run(cmd: list[str], **_kwargs) -> _Proc:
            self.calls.append(cmd)
            joined = " ".join(cmd)
            if "rev-parse" in joined:
                return _Proc(0, stdout=next(heads))
            if "pull" in joined:
                return _Proc(0, stdout="Updating oldsha..newsha\n")
            if "diff" in joined:
                return _Proc(0, stdout="pyproject.toml\n")
            if "pip" in cmd:
                return _Proc(0, stdout="Successfully installed fh6parse\n")
            if joined.startswith("systemctl cat"):
                return _Proc(1, stderr="not found")
            return _Proc(0)

        out = io.StringIO()
        err = io.StringIO()
        code = perform_update(
            frozen=False,
            start=self.start,
            runner=run,
            stdout=out,
            stderr=err,
        )
        self.assertEqual(code, 0)
        self.assertIn("reinstalling", out.getvalue())
        self.assertTrue(any("pip" in c for c in self.calls))
        self.assertIn("restart the kiosk yourself", err.getvalue())

    def test_ff_only_failure_is_nonzero(self) -> None:
        def run(cmd: list[str], **_kwargs) -> _Proc:
            self.calls.append(cmd)
            joined = " ".join(cmd)
            if "rev-parse" in joined:
                return _Proc(0, stdout="deadbeef\n")
            if "pull" in joined:
                return _Proc(1, stderr="fatal: Not possible to fast-forward")
            return _Proc(0)

        err = io.StringIO()
        code = perform_update(
            frozen=False,
            start=self.start,
            runner=run,
            stdout=io.StringIO(),
            stderr=err,
        )
        self.assertEqual(code, 1)
        self.assertIn("fast-forward", err.getvalue())
        self.assertFalse(any("pip" in c for c in self.calls))

    def test_no_git_root_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            start = Path(raw) / "fh6parse" / "x.py"
            start.parent.mkdir()
            start.write_text("x\n", encoding="utf-8")
            err = io.StringIO()
            code = perform_update(
                frozen=False,
                start=start,
                runner=lambda *_a, **_k: _Proc(0),
                stdout=io.StringIO(),
                stderr=err,
            )
            self.assertEqual(code, 2)
            self.assertIn("not a git checkout", err.getvalue())


if __name__ == "__main__":
    unittest.main()
