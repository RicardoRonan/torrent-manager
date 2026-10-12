from pathlib import Path

from . import platform


def resolve_target(dir_path, relative_path):
    if not dir_path:
        raise ValueError("missing download directory")
    target = Path(relative_path)
    if target.is_absolute():
        full = target
    else:
        full = Path(dir_path) / relative_path
    return full


def open_target(path):
    return platform.open_path(path)


def reveal_target(path):
    return platform.reveal_target(path)


def pick_file(dir_path, files, index):
    if index is None:
        return dir_path
    entries = files or []
    if index < 0 or index >= len(entries):
        raise IndexError("file index out of range")
    rel = entries[index].get("path") or ""
    if not rel:
        return dir_path
    return str(resolve_target(dir_path, rel))
