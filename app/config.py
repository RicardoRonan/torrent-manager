import os
from pathlib import Path

from . import platform

APP_NAME = "torrent-manager"
CONFIG_DIR = platform.config_dir(APP_NAME)
STATE_DIR = platform.state_dir(APP_NAME)
STATIC_DIR = platform.resource_dir() / "static"

SETTINGS_FILE = CONFIG_DIR / "settings.json"
CATEGORIES_FILE = CONFIG_DIR / "categories.json"
TAGS_FILE = CONFIG_DIR / "tags.json"
VIEWS_FILE = CONFIG_DIR / "views.json"
META_FILE = STATE_DIR / "meta.json"
TOKEN_FILE = CONFIG_DIR / "token"
SESSION_FILE = STATE_DIR / "aria2.session"

DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads" / "torrents")

DEFAULT_SETTINGS = {
    "download_dir": DEFAULT_DOWNLOAD_DIR,
    "theme": "dark",
    "refresh_ms": 1000,
    "autostart_aria2": True,
    "rpc_port": 6800,
    "max_concurrent": 10,
    "max_connection_per_server": 8,
    "global_download_limit": 0,
    "global_upload_limit": 0,
    "seed_time": 0,
    "seed_ratio": 0.0,
    "upload_while_downloading": True,
    "perf_preset": "balanced",
    "bt_max_peers": 128,
    "bt_request_peer_speed_limit": "1M",
    "disk_cache": "64M",
    "file_allocation": "falloc",
    "bt_max_open_files": 200,
    "lowest_speed_limit": "10K",
    "enable_mmap": True,
    "optimize_concurrent_downloads": True,
    "auto_save_interval": 30,
    "bt_tracker_connect_timeout": 5,
    "bt_tracker_timeout": 5,
    "dht": True,
    "pex": True,
    "lpd": True,
    "encryption": True,
    "listen_port": "6881-6999",
    "interface": "",
    "kill_switch": False,
    "notifications": True,
    "watch_folder": "",
    "watch_folder_enabled": False,
    "auth_mode": "auto",
    "row_fields": ["speed", "eta", "seeds", "peers", "size"],
    "sort": {"key": "addedAt", "dir": "desc"},
    "filters": {"status": "all", "category": "", "tag": "", "search": ""},
}

DEFAULT_CATEGORIES = [
    {"name": "Movies", "path": ""},
    {"name": "TV", "path": ""},
    {"name": "Music", "path": ""},
    {"name": "Other", "path": ""},
]

DEFAULT_TAGS = ["linux", "archive.org", "public-domain", "iso"]

DEFAULT_VIEWS = [
    {"name": "Active", "filters": {"status": "downloading"}, "sort": {"key": "downSpeed", "dir": "desc"}},
    {"name": "Completed", "filters": {"status": "complete"}, "sort": {"key": "addedAt", "dir": "desc"}},
]

PERF_PRESETS = {
    "conservative": {
        "max_concurrent": 5,
        "bt_max_peers": 60,
        "bt_request_peer_speed_limit": "256K",
        "disk_cache": "32M",
        "file_allocation": "prealloc",
        "bt_max_open_files": 100,
        "lowest_speed_limit": "0",
        "optimize_concurrent_downloads": False,
        "enable_mmap": False,
        "bt_tracker_connect_timeout": 10,
    },
    "balanced": {
        "max_concurrent": 10,
        "bt_max_peers": 128,
        "bt_request_peer_speed_limit": "1M",
        "disk_cache": "64M",
        "file_allocation": "falloc",
        "bt_max_open_files": 200,
        "lowest_speed_limit": "10K",
        "optimize_concurrent_downloads": True,
        "enable_mmap": True,
        "bt_tracker_connect_timeout": 5,
    },
    "aggressive": {
        "max_concurrent": 20,
        "bt_max_peers": 300,
        "bt_request_peer_speed_limit": "5M",
        "disk_cache": "128M",
        "file_allocation": "none",
        "bt_max_open_files": 500,
        "lowest_speed_limit": "20K",
        "optimize_concurrent_downloads": True,
        "enable_mmap": True,
        "bt_tracker_connect_timeout": 5,
    },
}
