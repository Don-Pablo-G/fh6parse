"""Update fh6parse: git checkout (kiosk / Windows GUI) or Windows one-file exe."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import subprocess
from pathlib import Path
import sys
import urllib.error
import urllib.request
from typing import Any, Callable, Sequence

from ._version import __version__

Run = Callable[..., subprocess.CompletedProcess[str]]

FROZEN_MSG = (
    "this install is a one-file package; copy a new tarball or use a git checkout"
)
WINDOWS_FROZEN_MSG = (
    "this Windows exe updates from a GitHub release; "
    "build and publish fh6parse-*-windows-x64.exe, or use a git checkout"
)
KIOSK_UNIT = "fh6parse-kiosk"
PYPROJECT = "pyproject.toml"
VERSION_FILE = "fh6parse/_version.py"
FETCH_TIMEOUT = 20
VERSION_RE = re.compile(r"""__version__\s*=\s*["']([^"']+)["']""")
WINDOWS_EXE_RE = re.compile(
    r"fh6parse-(\d+(?:\.\d+)*)-windows-x64\.exe$", re.IGNORECASE
)
GITHUB_REPO = "Don-Pablo-G/fh6parse"
GITHUB_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def version_from_text(text: str) -> str:
    match = VERSION_RE.search(text or "")
    return match.group(1) if match else ""


def version_key(text: str) -> tuple[int, ...]:
    nums = [int(p) for p in re.findall(r"\d+", text or "")]
    return tuple(nums) if nums else (0,)


def find_git_root(start: Path) -> Path | None:
    """Nearest directory that contains `.git`, walking up from start."""
    path = start.resolve()
    if path.is_file():
        path = path.parent
    for candidate in [path, *path.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def _run(
    cmd: Sequence[str],
    *,
    runner: Run,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    kwargs: dict = {"capture_output": True, "text": True, "check": False}
    if timeout is not None:
        kwargs["timeout"] = timeout
    try:
        return runner(list(cmd), **kwargs)
    except TypeError:
        kwargs.pop("timeout", None)
        return runner(list(cmd), **kwargs)
    except subprocess.TimeoutExpired as exc:
        out = getattr(exc, "stdout", None) or ""
        err = getattr(exc, "stderr", None) or "timeout"
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        return subprocess.CompletedProcess(list(cmd), 1, out, err)


def _pyproject_changed(
    repo: Path,
    old_head: str,
    new_head: str,
    *,
    runner: Run,
) -> bool:
    if old_head == new_head:
        return False
    proc = _run(
        ["git", "-C", str(repo), "diff", "--name-only", old_head, new_head, "--", PYPROJECT],
        runner=runner,
    )
    names = {line.strip() for line in (proc.stdout or "").splitlines() if line.strip()}
    return PYPROJECT in names


@dataclass(frozen=True)
class UpdateCheck:
    """Result of a non-blocking look at origin or a GitHub exe. Never raises."""

    available: bool
    detail: str = ""
    current_version: str = ""
    new_version: str = ""
    remote_sha: str = ""
    kind: str = "git"
    download_url: str = ""

    def button_label(self) -> str:
        if self.new_version and self.new_version != self.current_version:
            return f"UPDATE to {self.new_version}"
        if self.remote_sha:
            return f"UPDATE  {self.remote_sha}"
        return "UPDATE"


def _remote_sha(root: Path, *, runner: Run) -> str:
    for ref in ("@{upstream}", "origin/HEAD", "origin/master", "origin/main"):
        proc = _run(["git", "-C", str(root), "rev-parse", ref], runner=runner)
        sha = (proc.stdout or "").strip()
        if proc.returncode == 0 and sha:
            return sha
    return ""


def check_for_update(
    *,
    frozen: bool | None = None,
    start: Path | None = None,
    runner: Run | None = None,
    timeout: float = FETCH_TIMEOUT,
) -> UpdateCheck:
    """Fetch origin and compare HEAD to the tracked branch. Offline = no update."""
    run: Run = runner if runner is not None else subprocess.run
    current = __version__
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return UpdateCheck(False, "frozen", current_version=current)
    here = start if start is not None else Path(__file__).resolve()
    root = find_git_root(here)
    if root is None:
        return UpdateCheck(False, "not git", current_version=current)
    fetch = _run(
        ["git", "-C", str(root), "fetch", "--quiet"],
        runner=run,
        timeout=timeout,
    )
    if fetch.returncode != 0:
        return UpdateCheck(False, "offline", current_version=current)
    local = _run(["git", "-C", str(root), "rev-parse", "HEAD"], runner=run)
    if local.returncode != 0:
        return UpdateCheck(False, "git error", current_version=current)
    local_sha = (local.stdout or "").strip()
    remote_sha = _remote_sha(root, runner=run)
    if not local_sha or not remote_sha:
        return UpdateCheck(False, "no remote", current_version=current)
    if local_sha == remote_sha:
        return UpdateCheck(False, "up to date", current_version=current)
    shown = _run(
        ["git", "-C", str(root), "show", f"{remote_sha}:{VERSION_FILE}"],
        runner=run,
    )
    new_ver = version_from_text(shown.stdout or "") or current
    return UpdateCheck(
        True,
        "available",
        current_version=current,
        new_version=new_ver,
        remote_sha=remote_sha[:7],
    )


def _restart_kiosk(*, runner: Run) -> subprocess.CompletedProcess[str]:
    restart = _run(["systemctl", "restart", KIOSK_UNIT], runner=runner)
    if restart.returncode == 0:
        return restart
    return _run(["sudo", "-n", "systemctl", "restart", KIOSK_UNIT], runner=runner)


def perform_update(
    *,
    frozen: bool | None = None,
    start: Path | None = None,
    runner: Run | None = None,
    stdout=None,
    stderr=None,
    restart_kiosk: bool | None = None,
) -> int:
    """Pull this checkout, pip only if pyproject.toml changed, restart kiosk.

    Returns 0 on success, 1 on git/pip/restart failure, 2 if this is not a
    source checkout (frozen binary or no git root). Frozen Windows exe uses
    GitHub Releases instead (see perform_frozen_exe_update).
    """
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    run: Run = runner if runner is not None else subprocess.run
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        print(FROZEN_MSG, file=err)
        return 2

    here = start if start is not None else Path(__file__).resolve()
    root = find_git_root(here)
    if root is None:
        print("error: not a git checkout; clone the repo to update", file=err)
        return 2

    print(f"updating {root}", file=out)
    before = _run(["git", "-C", str(root), "rev-parse", "HEAD"], runner=run)
    if before.returncode != 0:
        print((before.stderr or before.stdout or "git rev-parse failed").strip(), file=err)
        return 1
    old_head = (before.stdout or "").strip()

    pull = _run(["git", "-C", str(root), "pull", "--ff-only"], runner=run)
    if pull.stdout:
        print(pull.stdout.rstrip(), file=out)
    if pull.returncode != 0:
        print((pull.stderr or "git pull --ff-only failed").strip(), file=err)
        return 1

    after = _run(["git", "-C", str(root), "rev-parse", "HEAD"], runner=run)
    if after.returncode != 0:
        print((after.stderr or after.stdout or "git rev-parse failed").strip(), file=err)
        return 1
    new_head = (after.stdout or "").strip()

    if _pyproject_changed(root, old_head, new_head, runner=run):
        print(f"{PYPROJECT} changed; reinstalling", file=out)
        pip = _run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-e",
                str(root),
                "--break-system-packages",
            ],
            runner=run,
        )
        if pip.stdout:
            print(pip.stdout.rstrip(), file=out)
        if pip.returncode != 0:
            print((pip.stderr or "pip install failed").strip(), file=err)
            return 1
    else:
        print(f"{PYPROJECT} unchanged; skipping pip", file=out)

    if restart_kiosk is False:
        print("restart the app to load the new code", file=out)
        return 0

    loaded = _run(["systemctl", "cat", f"{KIOSK_UNIT}.service"], runner=run)
    if loaded.returncode != 0:
        print("restart the kiosk yourself (systemctl restart fh6parse-kiosk)", file=err)
        return 0
    restart = _restart_kiosk(runner=run)
    if restart.returncode != 0:
        print(
            (restart.stderr or f"failed to restart {KIOSK_UNIT}").strip(),
            file=err,
        )
        print("restart the kiosk yourself (systemctl restart fh6parse-kiosk)", file=err)
        return 1
    print(f"restarted {KIOSK_UNIT}", file=out)
    return 0


def _github_headers() -> dict[str, str]:
    return {
        "User-Agent": f"fh6parse/{__version__}",
        "Accept": "application/vnd.github+json",
    }


def _http_json(
    url: str,
    *,
    timeout: float,
    opener: Callable[..., Any] | None = None,
) -> tuple[int, Any]:
    req = urllib.request.Request(url, headers=_github_headers())
    fetch = opener if opener is not None else urllib.request.urlopen
    try:
        with fetch(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200) or 200)
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0, None
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", "replace")
    else:
        text = str(raw)
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, None


def parse_windows_release(payload: dict[str, Any], *, current: str) -> UpdateCheck:
    """Pick a newer fh6parse-*-windows-x64.exe from a GitHub release JSON."""
    current = current or __version__
    assets = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(assets, list):
        return UpdateCheck(False, "no release", current_version=current, kind="exe")
    best_ver = ""
    best_url = ""
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        match = WINDOWS_EXE_RE.match(name)
        if not match:
            continue
        ver = match.group(1)
        url = str(asset.get("browser_download_url") or "")
        if url and version_key(ver) >= version_key(best_ver):
            best_ver = ver
            best_url = url
    if not best_url or not best_ver:
        return UpdateCheck(False, "no exe", current_version=current, kind="exe")
    if version_key(best_ver) <= version_key(current):
        return UpdateCheck(
            False,
            "up to date",
            current_version=current,
            new_version=best_ver,
            kind="exe",
        )
    return UpdateCheck(
        True,
        "available",
        current_version=current,
        new_version=best_ver,
        kind="exe",
        download_url=best_url,
    )


def check_github_windows_exe(
    *,
    current: str | None = None,
    opener: Callable[..., Any] | None = None,
    timeout: float = FETCH_TIMEOUT,
) -> UpdateCheck:
    """Look at GitHub latest release for a newer Windows one-file exe."""
    ver = current or __version__
    status, payload = _http_json(GITHUB_LATEST, timeout=timeout, opener=opener)
    if status == 0:
        return UpdateCheck(False, "offline", current_version=ver, kind="exe")
    if status == 404 or not isinstance(payload, dict):
        return UpdateCheck(False, "no release", current_version=ver, kind="exe")
    if status >= 400:
        return UpdateCheck(False, "offline", current_version=ver, kind="exe")
    return parse_windows_release(payload, current=ver)


def _download_file(
    url: str,
    dest: Path,
    *,
    opener: Callable[..., Any] | None = None,
    timeout: float = 120,
) -> bool:
    req = urllib.request.Request(url, headers=_github_headers())
    fetch = opener if opener is not None else urllib.request.urlopen
    try:
        with fetch(req, timeout=timeout) as resp:
            blob = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
    if not blob:
        return False
    dest.write_bytes(blob if isinstance(blob, bytes) else bytes(blob))
    return dest.is_file() and dest.stat().st_size > 0


def _updater_bat(exe: Path, staged: Path, pid: int) -> str:
    exe_s = str(exe)
    new_s = str(staged)
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        f'set "EXE={exe_s}"\r\n'
        f'set "NEW={new_s}"\r\n'
        f"set PID={int(pid)}\r\n"
        ":wait\r\n"
        'tasklist /FI "PID eq %PID%" | find "%PID%" >nul\r\n'
        "if not errorlevel 1 (\r\n"
        "  timeout /t 1 /nobreak >nul\r\n"
        "  goto wait\r\n"
        ")\r\n"
        'copy /Y "%NEW%" "%EXE%" >nul\r\n'
        "if errorlevel 1 (\r\n"
        "  echo update copy failed\r\n"
        "  pause\r\n"
        "  exit /b 1\r\n"
        ")\r\n"
        'del "%NEW%" >nul 2>nul\r\n'
        'start "" "%EXE%"\r\n'
        'del "%~f0"\r\n'
    )


def perform_frozen_exe_update(
    *,
    exe: Path | None = None,
    opener: Callable[..., Any] | None = None,
    pid: int | None = None,
    spawn: Callable[..., Any] | None = None,
    stdout=None,
    stderr=None,
) -> int:
    """Download a newer Windows exe from GitHub and swap it after this process exits."""
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    target = Path(exe) if exe is not None else Path(sys.executable)
    if not sys.platform.startswith("win") and exe is None:
        print(FROZEN_MSG, file=err)
        return 2
    status = check_github_windows_exe(opener=opener)
    if not status.available or not status.download_url:
        print(WINDOWS_FROZEN_MSG, file=err)
        if status.detail:
            print(status.detail, file=err)
        return 2
    staged = target.with_name(target.name + ".new")
    print(f"downloading {status.new_version}", file=out)
    if not _download_file(status.download_url, staged, opener=opener):
        print("download failed", file=err)
        return 1
    bat = target.with_name("_fh6parse_update.bat")
    bat.write_text(
        _updater_bat(target, staged, pid if pid is not None else os.getpid()),
        encoding="ascii",
        errors="replace",
    )
    launch = spawn if spawn is not None else subprocess.Popen
    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    try:
        launch(
            ["cmd.exe", "/c", str(bat)],
            close_fds=True,
            creationflags=creationflags,
            cwd=str(target.parent),
        )
    except OSError as exc:
        print(str(exc), file=err)
        return 1
    print("restart the app to finish the exe swap", file=out)
    return 0


def relaunch_gui() -> None:
    """Replace this process with a fresh GUI (git checkout after pull)."""
    if getattr(sys, "frozen", False):
        os.execv(sys.executable, [sys.executable])
    os.execv(sys.executable, [sys.executable, "-m", "fh6parse", "--gui"])
