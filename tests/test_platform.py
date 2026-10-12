import os
from pathlib import Path

from app import desktop, platform


def test_resource_dir_points_at_project():
    assert (platform.resource_dir() / "static" / "index.html").is_file()


def test_config_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("TM_CONFIG_DIR", str(tmp_path / "cfg"))
    assert platform.config_dir("x") == tmp_path / "cfg"


def test_interface_up_empty_is_true():
    assert platform.interface_up("") is True


def test_aria2_binary_resolves():
    binary = platform.aria2_binary()
    assert binary is None or os.path.basename(binary).startswith("aria2c")


def test_icon_path_exists():
    icon = desktop.icon_path()
    assert icon.endswith("icon.svg")
    assert Path(icon).is_file()


def test_install_linux_desktop(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    info = desktop.install_linux_desktop(exe="/bin/true", register_magnet=False)
    desktop_file = Path(info["desktop_file"])
    assert desktop_file.is_file()
    text = desktop_file.read_text()
    assert "x-scheme-handler/magnet" in text
    assert 'Exec="/bin/true" %u' in text
