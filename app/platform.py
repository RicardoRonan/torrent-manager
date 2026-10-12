import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def resource_dir():
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


def app_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def config_dir(app_name):
    override = os.environ.get("TM_CONFIG_DIR")
    if override:
        return Path(override)
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return Path(base) / app_name
    if IS_MAC:
        return Path.home() / "Library" / "Application Support" / app_name
    return Path.home() / ".config" / app_name


def state_dir(app_name):
    override = os.environ.get("TM_STATE_DIR")
    if override:
        return Path(override)
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        return Path(base) / app_name / "state"
    if IS_MAC:
        return Path.home() / "Library" / "Application Support" / app_name / "state"
    return Path.home() / ".local" / "state" / app_name


def aria2_binary():
    exe = "aria2c.exe" if IS_WINDOWS else "aria2c"
    candidates = [
        resource_dir() / "bin" / exe,
        app_root() / "bin" / exe,
    ]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which(exe) or shutil.which("aria2c")


def spawn_detached(cmd):
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if IS_WINDOWS:
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        kwargs["close_fds"] = True
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def open_path(path):
    full = Path(path)
    if not full.exists():
        raise FileNotFoundError(str(full))
    if IS_WINDOWS:
        os.startfile(str(full))
    elif IS_MAC:
        spawn_detached(["open", str(full)])
    else:
        spawn_detached(["xdg-open", str(full)])
    return str(full)


def reveal_target(path):
    full = Path(path)
    if not full.exists():
        raise FileNotFoundError(str(full))
    if IS_WINDOWS:
        spawn_detached(["explorer", "/select,", str(full)])
        return str(full)
    if IS_MAC:
        spawn_detached(["open", "-R", str(full)])
        return str(full)
    uri = "file://" + quote(str(full))
    if shutil.which("dbus-send"):
        spawn_detached(
            [
                "dbus-send",
                "--session",
                "--dest=org.freedesktop.FileManager1",
                "--type=method_call",
                "/org/freedesktop/FileManager1",
                "org.freedesktop.FileManager1.ShowItems",
                f"array:string:{uri}",
                "string:",
            ]
        )
        return str(full)
    folder = full if full.is_dir() else full.parent
    spawn_detached(["xdg-open", str(folder)])
    return str(folder)


def interface_up(name):
    if not name:
        return True
    if IS_WINDOWS:
        return True
    if IS_MAC:
        try:
            out = subprocess.run(["ifconfig", name], capture_output=True, text=True, timeout=5).stdout
        except Exception:
            return True
        return "status: active" in out or "UP" in out
    try:
        state = Path(f"/sys/class/net/{name}/operstate").read_text().strip()
    except OSError:
        return True
    return state in ("up", "unknown")
