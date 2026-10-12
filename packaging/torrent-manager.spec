# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project = Path(SPECPATH).parent
spec_dir = Path(SPECPATH)
bin_dir = spec_dir / "bin"

datas = [(str(project / "static"), "static")]
icon = spec_dir / "icon.svg"
if icon.exists():
    datas.append((str(icon), "."))
if bin_dir.exists():
    datas.append((str(bin_dir), "bin"))

hiddenimports = collect_submodules("uvicorn")
hiddenimports += ["app", "app.main", "app.cli", "app.desktop", "app.platform"]
try:
    hiddenimports += collect_submodules("webview")
except Exception:
    pass

a = Analysis(
    [str(project / "run.py")],
    pathex=[str(project)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TorrentManager",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="TorrentManager",
)
