# -*- mode: python ; coding: utf-8 -*-
"""One-file PyInstaller spec. Build natively on Windows and on Linux (Docker)."""

from pathlib import Path
import subprocess
import importlib.util

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
LAUNCHER = str(ROOT / "packaging" / "launcher.py")

# Bake the git short SHA into the frozen binary so --version / GUI / kiosk
# show the same build as a git checkout (version plus git SHA).
# Docker copies have no .git — keep a host-written fh6parse/_build.py if git fails.
_sha = ""
try:
    _sha = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "--short=7", "HEAD"],
        text=True,
        timeout=5,
    ).strip()
except Exception:
    _sha = ""
_build_py = ROOT / "fh6parse" / "_build.py"
if not _sha and _build_py.is_file():
    for line in _build_py.read_text(encoding="utf-8").splitlines():
        if line.startswith("__build__"):
            _sha = line.split("=", 1)[-1].strip().strip("'\"")
            break
_build_py.write_text(
    f'"""Baked at freeze time. Not committed."""\n__build__ = {_sha!r}\n',
    encoding="utf-8",
)

hiddenimports = [
    "tkinter",
    "tkinter.ttk",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "tkinter.font",
    "tkinter.constants",
    "webbrowser",
    "fh6parse.kiosk",
    "fh6parse.printer",
    "fh6parse.usbwatch",
    "fh6parse.idle",
    "fh6parse.update",
    "fh6parse.partid",
    "fh6parse.modelmatch",
    "fh6parse.modelrender",
    "fh6parse.modelprep",
    "fh6parse.cadmark",
    "fh6parse.i18n",
    "fh6parse.workarea",
    "fh6parse._build",
]
extra_datas = []
extra_binaries = []

# gpiozero / lgpio (Pi 5) / RPi.GPIO (Pi 3/4) exist on the Raspberry image;
# skip on Windows.
for pkg, spec_name in (
    ("gpiozero", "gpiozero"),
    ("RPi.GPIO", "RPi.GPIO"),
    ("lgpio", "lgpio"),
):
    try:
        found = importlib.util.find_spec(spec_name)
    except ModuleNotFoundError:
        continue
    if found is None:
        continue
    try:
        ds, bins, hid = collect_all(pkg)
        extra_datas += ds
        extra_binaries += bins
        hiddenimports += hid
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

# STEP isometric views. Collect C-extension binaries only.
# Do not collect_submodules("trimesh") — that pulls optional torch/pandas
# from the build machine.
for pkg in ("numpy", "PIL", "cascadio"):
    try:
        found = importlib.util.find_spec(pkg)
    except ModuleNotFoundError:
        continue
    if found is None:
        continue
    try:
        ds, bins, hid = collect_all(pkg)
        extra_datas += ds
        extra_binaries += bins
        hiddenimports += hid
    except Exception:
        pass
hiddenimports += ["numpy", "PIL", "PIL.Image", "trimesh", "cascadio"]

a = Analysis(
    [LAUNCHER],
    pathex=[str(ROOT)],
    binaries=extra_binaries,
    datas=extra_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "torchvision",
        "torchaudio",
        "tensorflow",
        "pandas",
        "matplotlib",
        "scipy",
        "pyarrow",
        "botocore",
        "boto3",
        "IPython",
        "notebook",
        "sklearn",
        "cv2",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="fh6parse",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
