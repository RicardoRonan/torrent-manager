import subprocess
import sys
from pathlib import Path

from . import platform

DESKTOP_ID = "torrent-manager.desktop"


def _exe_path():
    return str(Path(sys.executable).resolve())


def icon_path():
    for candidate in (
        platform.app_root() / "icon.svg",
        platform.resource_dir() / "icon.svg",
        platform.app_root() / "packaging" / "icon.svg",
    ):
        if candidate.is_file():
            return str(candidate)
    return "torrent-manager"


def install_linux_desktop(exe=None, name="Torrent Manager", register_magnet=True):
    exe = exe or _exe_path()
    apps_dir = Path.home() / ".local" / "share" / "applications"
    apps_dir.mkdir(parents=True, exist_ok=True)
    desktop_file = apps_dir / DESKTOP_ID
    desktop_file.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={name}\n"
        "Comment=Torrent downloads (aria2)\n"
        f'Exec="{exe}" %u\n'
        f"Icon={icon_path()}\n"
        "Terminal=false\n"
        "Categories=Network;FileTransfer;P2P;\n"
        "MimeType=x-scheme-handler/magnet;\n",
        encoding="utf-8",
    )
    desktop_file.chmod(0o755)
    results = {}
    for cmd in (
        ["update-desktop-database", str(apps_dir)],
        (["xdg-mime", "default", DESKTOP_ID, "x-scheme-handler/magnet"] if register_magnet else None),
    ):
        if not cmd:
            continue
        try:
            subprocess.run(cmd, capture_output=True, timeout=15)
            results[cmd[0]] = "ok"
        except Exception as exc:
            results[cmd[0]] = str(exc)
    return {"desktop_file": str(desktop_file), "results": results}


def register_windows_magnet(exe=None):
    if not platform.IS_WINDOWS:
        raise RuntimeError("Windows-only")
    import winreg

    exe = exe or _exe_path()
    base = r"Software\Classes\magnet\shell\open\command"
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, base)
    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{exe}" "%1"')
    winreg.CloseKey(key)
    proto = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\magnet")
    winreg.SetValueEx(proto, "", 0, winreg.REG_SZ, "URL:Magnet link")
    winreg.SetValueEx(proto, "URL Protocol", 0, winreg.REG_SZ, "")
    winreg.CloseKey(proto)
    return {"registered": base}


def register_magnet(exe=None):
    if platform.IS_WINDOWS:
        return register_windows_magnet(exe)
    if platform.IS_MAC:
        raise RuntimeError("macOS magnet registration is not implemented")
    return install_linux_desktop(exe)
