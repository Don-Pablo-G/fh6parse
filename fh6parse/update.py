"""Update a git checkout of fh6parse on the Pi kiosk (not the one-file binary)."""

from __future__ import annotations

from dataclasses import dataclass
import re
import subprocess
from pathlib import Path
import sys
from typing import Callable, Sequence

from ._version import __version__

Run = Callable[..., subprocess.CompletedProcess[str]]

FROZEN_MSG = (
    "this install is a one-file package; copy a new tarball or use a git checkout"
)
KIOSK_UNIT = "fh6parse-kiosk"
PYPROJECT = "pyproject.toml"
VERSION_FILE = "fh6parse/_version.py"
FETCH_TIMEOUT = 20
VERSION_RE = re.compile(r"""__version__\s*=\s*["']([^"']+)["']""")


def version_from_text(text: str) -> str:
    match = VERSION_RE.search(text or "")
    return match.group(1) if match else ""


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
    """Result of a non-blocking look at origin. Never raises."""

    available: bool
    detail: str = ""
    current_version: str = ""
    new_version: str = ""
    remote_sha: str = ""

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
) -> int:
    """Pull this checkout, pip only if pyproject.toml changed, restart kiosk.

    Returns 0 on success, 1 on git/pip/restart failure, 2 if this is not a
    source checkout (frozen binary or no git root).
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
