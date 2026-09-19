"""Removable-volume scan for NC programs (USB sticks on the Pi kiosk)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_EXTENSIONS = (".nc", ".tap")
SKIP_DIR_NAMES = {
    "system volume information",
    "$recycle.bin",
    "trashes",
    ".trashes",
    ".trash-1000",
}
SKIP_FS = {
    "proc",
    "sysfs",
    "devtmpfs",
    "devpts",
    "tmpfs",
    "cgroup",
    "cgroup2",
    "overlay",
    "squashfs",
    "autofs",
    "bpf",
    "debugfs",
    "pstore",
    "securityfs",
    "mqueue",
    "hugetlbfs",
    "configfs",
    "fusectl",
    "ramfs",
    "tracefs",
    "rpc_pipefs",
    "nfsd",
    "binfmt_misc",
    "efivarfs",
    # Company NAS / Windows share — never treat as a USB stick.
    "cifs",
    "smb3",
    "smb2",
    "smbfs",
    "nfs",
    "nfs4",
    "nfsv4",
    "ceph",
    "glusterfs",
}
SKIP_MOUNTPOINTS = {
    "/",
    "/boot",
    "/boot/firmware",
    "/home",
    "/usr",
    "/var",
    "/opt",
    "/snap",
    "/run",
    "/sys",
    "/proc",
    "/dev",
    "/mnt/fh6parse-cad",
}


def _decode_mount_path(raw: str) -> str:
    return raw.replace("\\040", " ").replace("\\011", "\t").replace("\\012", "\n")


def linux_removable_mounts() -> list[Path]:
    proc = Path("/proc/mounts")
    if not proc.is_file():
        return []
    found: list[Path] = []
    seen: set[str] = set()
    for line in proc.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        device, raw_mp, fstype = parts[0], parts[1], parts[2]
        if fstype in SKIP_FS:
            continue
        mp = _decode_mount_path(raw_mp)
        if mp in SKIP_MOUNTPOINTS or mp.startswith("/snap"):
            continue
        if "mmcblk" in device:
            continue
        under_hotplug = (
            mp.startswith("/media/")
            or mp.startswith("/run/media/")
            or mp.startswith("/mnt/")
        )
        usb_block = device.startswith("/dev/sd") or device.startswith("/dev/hd")
        if not under_hotplug and not usb_block:
            continue
        if mp in seen:
            continue
        seen.add(mp)
        path = Path(mp)
        if path.is_dir():
            found.append(path)
    return found


def windows_removable_mounts() -> list[Path]:
    if os.name != "nt":
        return []
    import ctypes

    get_drives = ctypes.windll.kernel32.GetLogicalDriveStringsW
    get_type = ctypes.windll.kernel32.GetDriveTypeW
    buf = ctypes.create_unicode_buffer(256)
    n = get_drives(ctypes.sizeof(buf), buf)
    if n == 0:
        return []
    found: list[Path] = []
    blob = buf.raw[: n * 2].decode("utf-16-le", "ignore")
    for item in blob.split("\x00"):
        if not item:
            continue
        # 2 = DRIVE_REMOVABLE
        if get_type(item) == 2:
            path = Path(item)
            if path.is_dir():
                found.append(path)
    return found


def removable_mounts() -> list[Path]:
    if sys.platform.startswith("linux"):
        return linux_removable_mounts()
    if os.name == "nt":
        return windows_removable_mounts()
    return []


def list_nc_files(
    roots: list[Path],
    *,
    max_depth: int = 1,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
) -> list[Path]:
    """NC files in each root. max_depth=1 is the folder itself (no subfolders)."""
    exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    found: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            current = Path(dirpath)
            try:
                rel = current.relative_to(root)
            except ValueError:
                dirnames.clear()
                continue
            depth = 0 if rel == Path(".") else len(rel.parts)
            if depth >= max_depth:
                dirnames.clear()
                continue
            dirnames[:] = [
                d
                for d in dirnames
                if not d.startswith(".") and d.lower() not in SKIP_DIR_NAMES
            ]
            for name in filenames:
                path = current / name
                if path.suffix.lower() not in exts:
                    continue
                try:
                    resolved = path.resolve()
                except OSError:
                    continue
                if resolved in seen:
                    continue
                seen.add(resolved)
                found.append(path)
    return sorted(found, key=lambda p: (p.name.lower(), str(p).lower()))
