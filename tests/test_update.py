"""Source-checkout update: git pull --ff-only, pip only if pyproject changed.

When CAD ([models]) is already importable, pip uses .[models] so cubes survive.
"""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from fh6parse.update import (
    FROZEN_MSG,
    UpdateCheck,
    check_for_update,
    check_github_windows_exe,
    editable_install_target,
    find_git_root,
    parse_windows_release,
    perform_frozen_exe_update,
    perform_update,
    release_tag_version,
    version_from_text,
    version_key,
)


class _Proc:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestEditableInstallTarget(unittest.TestCase):
    def test_plain_editable_path(self) -> None:
        root = Path("/home/kiosk/fh6parse")
        self.assertEqual(editable_install_target(root, keep_models=False), str(root))

    def test_models_extra_appended(self) -> None:
        root = Path("/home/kiosk/fh6parse")
        self.assertEqual(
            editable_install_target(root, keep_models=True),
            f"{root}[models]",
        )


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
            keep_models=False,
        )
        self.assertEqual(code, 0)
        self.assertIn("reinstalling", out.getvalue())
        self.assertNotIn("[models]", out.getvalue())
        self.assertTrue(any("pip" in c for c in self.calls))
        self.assertFalse(any(any("[models]" in arg for arg in c) for c in self.calls))
        self.assertIn("restart the kiosk yourself", err.getvalue())

    def test_pip_keeps_models_extra_when_cad_present(self) -> None:
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
        code = perform_update(
            frozen=False,
            start=self.start,
            runner=run,
            stdout=out,
            stderr=io.StringIO(),
            keep_models=True,
        )
        self.assertEqual(code, 0)
        self.assertIn("reinstalling with [models]", out.getvalue())
        pip_calls = [c for c in self.calls if "pip" in c]
        self.assertTrue(pip_calls)
        self.assertTrue(any(arg.endswith("[models]") for arg in pip_calls[0]))

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

    def test_restart_falls_back_to_sudo(self) -> None:
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
                return _Proc(1, stderr="Access denied")
            if cmd[:3] == ["sudo", "-n", "systemctl"]:
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
        self.assertIn("restarted fh6parse-kiosk", out.getvalue())
        self.assertTrue(any(c[:3] == ["sudo", "-n", "systemctl"] for c in self.calls))

    def test_gui_git_update_skips_systemd(self) -> None:
        def run(cmd: list[str], **_kwargs) -> _Proc:
            joined = " ".join(cmd)
            if "rev-parse" in joined:
                return _Proc(0, stdout="deadbeef\n")
            if "pull" in joined:
                return _Proc(0, stdout="Already up to date.\n")
            if "diff" in joined:
                return _Proc(0, stdout="")
            if "systemctl" in joined:
                self.fail("GUI update must not touch systemd")
            return _Proc(0)

        out = io.StringIO()
        code = perform_update(
            frozen=False,
            start=self.start,
            runner=run,
            stdout=out,
            stderr=io.StringIO(),
            restart_kiosk=False,
        )
        self.assertEqual(code, 0)
        self.assertIn("restart the app", out.getvalue())


class TestCheckForUpdate(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".git").mkdir()
        (self.root / "fh6parse").mkdir()
        self.start = self.root / "fh6parse" / "update.py"
        self.start.write_text("# stub\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _git_run(
        self,
        *,
        local: str,
        remote: str,
        relation: str = "behind",
        version: str = '__version__ = "9.9.9"\n',
        upstream: str | None | bool = True,
        extra_refs: dict[str, str] | None = None,
    ):
        refs = dict(extra_refs or {})
        if upstream is True:
            refs["@{upstream}"] = remote
        elif isinstance(upstream, str):
            refs["@{upstream}"] = upstream

        def run(cmd: list[str], **_kwargs) -> _Proc:
            if "fetch" in cmd:
                return _Proc(0)
            if "merge-base" in cmd and "--is-ancestor" in cmd:
                anc, desc = cmd[-2], cmd[-1]
                if anc == desc:
                    return _Proc(0)
                if relation == "behind" and anc == local and desc == remote:
                    return _Proc(0)
                if relation == "ahead" and anc == remote and desc == local:
                    return _Proc(0)
                return _Proc(1)
            if "rev-parse" in cmd:
                ref = cmd[-1]
                if ref == "HEAD":
                    return _Proc(0, stdout=local + "\n")
                if ref in refs:
                    return _Proc(0, stdout=refs[ref] + "\n")
                return _Proc(1, stderr=f"no {ref}")
            if "show" in cmd:
                return _Proc(0, stdout=version)
            self.fail(f"unexpected command: {cmd}")
            return _Proc(1)

        return run

    def test_frozen_is_not_available(self) -> None:
        status = check_for_update(frozen=True, start=self.start, runner=lambda *_a, **_k: _Proc(0))
        self.assertFalse(status.available)
        self.assertEqual(status.detail, "frozen")

    def test_offline_fetch_is_not_available(self) -> None:
        def run(cmd: list[str], **_kwargs) -> _Proc:
            if "fetch" in cmd:
                return _Proc(1, stderr="Could not resolve host")
            self.fail(f"unexpected command after failed fetch: {cmd}")
            return _Proc(0)

        status = check_for_update(frozen=False, start=self.start, runner=run)
        self.assertFalse(status.available)
        self.assertEqual(status.detail, "offline")

    def test_same_head_is_up_to_date(self) -> None:
        status = check_for_update(
            frozen=False,
            start=self.start,
            runner=self._git_run(local="abc123", remote="abc123", relation="equal"),
        )
        self.assertFalse(status.available)
        self.assertEqual(status.detail, "up to date")

    def test_remote_ahead_is_available(self) -> None:
        status = check_for_update(
            frozen=False,
            start=self.start,
            runner=self._git_run(local="oldsha", remote="newsha"),
        )
        self.assertTrue(status.available)
        self.assertEqual(status.detail, "available")
        self.assertEqual(status.new_version, "9.9.9")
        self.assertEqual(status.button_label(), "UPDATE to 9.9.9")

    def test_local_ahead_is_up_to_date(self) -> None:
        status = check_for_update(
            frozen=False,
            start=self.start,
            runner=self._git_run(
                local="newsha",
                remote="oldsha",
                relation="ahead",
                version='__version__ = "1.4.0"\n',
            ),
        )
        self.assertFalse(status.available)
        self.assertEqual(status.detail, "up to date")

    def test_diverged_is_not_available(self) -> None:
        status = check_for_update(
            frozen=False,
            start=self.start,
            runner=self._git_run(
                local="aaa",
                remote="bbb",
                relation="diverged",
            ),
        )
        self.assertFalse(status.available)
        self.assertEqual(status.detail, "diverged")

    def test_falls_back_to_origin_head(self) -> None:
        status = check_for_update(
            frozen=False,
            start=self.start,
            runner=self._git_run(
                local="oldsha",
                remote="newsha",
                upstream=False,
                extra_refs={"origin/HEAD": "newsha"},
                version='__version__ = "2.0.0"\n',
            ),
        )
        self.assertTrue(status.available)

    def test_not_git_is_not_available(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            start = Path(raw) / "x.py"
            start.write_text("x\n", encoding="utf-8")
            status = check_for_update(
                frozen=False,
                start=start,
                runner=lambda *_a, **_k: _Proc(0),
            )
            self.assertFalse(status.available)
            self.assertEqual(status.detail, "not git")


class TestVersionLabel(unittest.TestCase):
    def test_parses_version_file(self) -> None:
        self.assertEqual(
            version_from_text('"""pkg"""\n__version__ = "1.2.3"\n'),
            "1.2.3",
        )

    def test_button_prefers_new_version(self) -> None:
        status = UpdateCheck(
            True,
            "available",
            current_version="1.3.3",
            new_version="1.3.4",
            remote_sha="abc1234",
        )
        self.assertEqual(status.button_label(), "UPDATE to 1.3.4")

    def test_button_uses_sha_when_version_unchanged(self) -> None:
        status = UpdateCheck(
            True,
            "available",
            current_version="1.3.4",
            new_version="1.3.4",
            remote_sha="deadbee",
        )
        self.assertEqual(status.button_label(), "UPDATE  deadbee")

    def test_button_uses_sha_when_remote_is_older(self) -> None:
        status = UpdateCheck(
            True,
            "available",
            current_version="1.4.1",
            new_version="1.4.0",
            remote_sha="deadbee",
        )
        self.assertEqual(status.button_label(), "UPDATE  deadbee")


class TestWindowsExeRelease(unittest.TestCase):
    def test_version_key_orders_dots(self) -> None:
        self.assertLess(version_key("1.3.4"), version_key("1.3.10"))
        self.assertEqual(version_key("v1.3.4"), version_key("1.3.4"))

    def test_release_tag_strips_v_prefix(self) -> None:
        self.assertEqual(release_tag_version("v1.4.0"), "1.4.0")
        self.assertEqual(release_tag_version("1.4.0"), "1.4.0")
        self.assertEqual(release_tag_version(" V1.4.1 "), "1.4.1")

    def test_workflow_builds_named_windows_exe(self) -> None:
        path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "windows-exe.yml"
        text = path.read_text(encoding="utf-8")
        self.assertIn("windows-latest", text)
        self.assertIn('tags: ["v*"]', text)
        self.assertIn("fh6parse-$Stamp-windows-x64.exe", text)
        self.assertIn("fh6parse-$Ver-windows-x64.exe", text)
        self.assertIn("gh release create", text)

    def test_newer_asset_is_available(self) -> None:
        payload = {
            "assets": [
                {
                    "name": "fh6parse-1.3.5-windows-x64.exe",
                    "browser_download_url": "https://example.test/a.exe",
                }
            ]
        }
        status = parse_windows_release(payload, current="1.3.4")
        self.assertTrue(status.available)
        self.assertEqual(status.new_version, "1.3.5")
        self.assertEqual(status.kind, "exe")
        self.assertEqual(status.download_url, "https://example.test/a.exe")

    def test_stamped_asset_name_uses_package_version(self) -> None:
        from fh6parse.update import WINDOWS_EXE_RE

        match = WINDOWS_EXE_RE.match("fh6parse-1.4.1+0e7f077-windows-x64.exe")
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "1.4.1")
        payload = {
            "assets": [
                {
                    "name": "fh6parse-1.3.5+deadbee-windows-x64.exe",
                    "browser_download_url": "https://example.test/b.exe",
                }
            ]
        }
        status = parse_windows_release(payload, current="1.3.4")
        self.assertTrue(status.available)
        self.assertEqual(status.new_version, "1.3.5")
        self.assertEqual(status.download_url, "https://example.test/b.exe")

    def test_same_version_is_up_to_date(self) -> None:
        payload = {
            "assets": [
                {
                    "name": "fh6parse-1.3.4-windows-x64.exe",
                    "browser_download_url": "https://example.test/a.exe",
                }
            ]
        }
        status = parse_windows_release(payload, current="1.3.4")
        self.assertFalse(status.available)
        self.assertEqual(status.detail, "up to date")

    def test_missing_exe_asset(self) -> None:
        status = parse_windows_release({"assets": []}, current="1.3.4")
        self.assertFalse(status.available)
        self.assertEqual(status.detail, "no exe")

    def test_github_check_uses_opener(self) -> None:
        import json

        class _Resp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            def read(self):
                return json.dumps(
                    {
                        "assets": [
                            {
                                "name": "fh6parse-9.9.9-windows-x64.exe",
                                "browser_download_url": "https://example.test/n.exe",
                            }
                        ]
                    }
                ).encode()

        status = check_github_windows_exe(
            current="1.0.0", opener=lambda *_a, **_k: _Resp()
        )
        self.assertTrue(status.available)
        self.assertEqual(status.new_version, "9.9.9")

    def test_github_404_is_no_release(self) -> None:
        import urllib.error

        def opener(req, timeout=None):
            from email.message import EmailMessage

            raise urllib.error.HTTPError(
                getattr(req, "full_url", "https://example.test"),
                404,
                "not found",
                EmailMessage(),
                None,
            )

        status = check_github_windows_exe(current="1.0.0", opener=opener)
        self.assertFalse(status.available)
        self.assertEqual(status.detail, "no release")

    def test_frozen_exe_update_stages_and_spawns(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as raw:
            exe = Path(raw) / "fh6parse.exe"
            exe.write_bytes(b"old")
            spawned: list[list[str]] = []

            class _Resp:
                def __init__(self, body: bytes):
                    self._body = body
                    self.status = 200

                def __enter__(self):
                    return self

                def __exit__(self, *_a):
                    return False

                def read(self):
                    return self._body

            def opener(req, timeout=None):
                url = getattr(req, "full_url", "")
                if "releases" in url:
                    return _Resp(
                        json.dumps(
                            {
                                "assets": [
                                    {
                                        "name": "fh6parse-2.0.0-windows-x64.exe",
                                        "browser_download_url": "https://example.test/n.exe",
                                    }
                                ]
                            }
                        ).encode()
                    )
                return _Resp(b"new-exe")

            def spawn(cmd, **_k):
                spawned.append(cmd)
                return None

            out = io.StringIO()
            code = perform_frozen_exe_update(
                exe=exe,
                opener=opener,
                pid=1,
                spawn=spawn,
                stdout=out,
                stderr=io.StringIO(),
            )
            self.assertEqual(code, 0)
            self.assertTrue((exe.with_name("fh6parse.exe.new")).is_file())
            self.assertTrue((exe.with_name("_fh6parse_update.bat")).is_file())
            self.assertTrue(spawned)


class TestDisplayVersion(unittest.TestCase):
    def test_plain_number_when_build_unknown(self) -> None:
        from unittest.mock import patch

        from fh6parse._version import __version__, display_version

        with patch("fh6parse._version.local_build", return_value=""):
            self.assertEqual(display_version(), __version__)

    def test_appends_git_or_frozen_sha(self) -> None:
        from unittest.mock import patch

        from fh6parse._version import __version__, display_version

        with patch("fh6parse._version.local_build", return_value="2e68429"):
            self.assertEqual(display_version(), f"{__version__}+2e68429")

    def test_dist_basename_includes_build(self) -> None:
        from unittest.mock import patch

        from fh6parse._version import __version__, dist_basename, package_stamp

        with patch("fh6parse._version.local_build", return_value="0e7f077"):
            self.assertEqual(package_stamp(), f"{__version__}+0e7f077")
            self.assertEqual(
                dist_basename("windows-x64"),
                f"fh6parse-{__version__}+0e7f077-windows-x64",
            )
            self.assertEqual(
                dist_basename("windows-x64", stamped=False),
                f"fh6parse-{__version__}-windows-x64",
            )

    def test_cli_version_includes_build(self) -> None:
        from unittest.mock import patch

        from fh6parse.cli import build_parser

        with patch("fh6parse.cli.display_version", return_value="1.4.0+deadbee"):
            parser = build_parser()
            shown = [
                getattr(action, "version", "")
                for action in parser._actions
                if "--version" in getattr(action, "option_strings", [])
            ]
            self.assertTrue(any("1.4.0+deadbee" in str(item) for item in shown))


if __name__ == "__main__":
    unittest.main()
