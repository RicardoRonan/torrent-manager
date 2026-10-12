import json
import os
import secrets
import threading
from copy import deepcopy

from . import config

_lock = threading.RLock()


def _ensure_dirs():
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)


def _read(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return deepcopy(default)


def _write(path, data):
    _ensure_dirs()
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)


def _merge(base, patch):
    out = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def get_settings():
    with _lock:
        stored = _read(config.SETTINGS_FILE, {})
        return _merge(config.DEFAULT_SETTINGS, stored)


def update_settings(patch):
    with _lock:
        current = get_settings()
        merged = _merge(current, patch or {})
        if merged.get("seed_time", 0) != 0:
            merged["seed_time"] = 0
        merged["seed_ratio"] = 0.0
        _write(config.SETTINGS_FILE, merged)
        return merged


def get_token():
    with _lock:
        _ensure_dirs()
        try:
            token = config.TOKEN_FILE.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            token = ""
        if not token:
            token = secrets.token_urlsafe(32)
            config.TOKEN_FILE.write_text(token, encoding="utf-8")
        return token


def get_rpc_secret():
    with _lock:
        _ensure_dirs()
        path = config.STATE_DIR / "rpc_secret"
        try:
            secret = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            secret = ""
        if not secret:
            secret = secrets.token_hex(24)
            path.write_text(secret, encoding="utf-8")
        return secret


def _collection(path, default):
    return _read(path, default)


def get_categories():
    return _collection(config.CATEGORIES_FILE, config.DEFAULT_CATEGORIES)


def set_categories(items):
    with _lock:
        _write(config.CATEGORIES_FILE, items)
    return items


def get_tags():
    return _collection(config.TAGS_FILE, config.DEFAULT_TAGS)


def set_tags(items):
    with _lock:
        _write(config.TAGS_FILE, items)
    return items


def get_views():
    return _collection(config.VIEWS_FILE, config.DEFAULT_VIEWS)


def set_views(items):
    with _lock:
        _write(config.VIEWS_FILE, items)
    return items


def get_meta():
    return _collection(config.META_FILE, {})


def set_meta(data):
    with _lock:
        _write(config.META_FILE, data)
    return data


def record_meta(key, category="", tags=None, added_at=None):
    if not key:
        return
    with _lock:
        data = get_meta()
        entry = data.get(key, {})
        if category:
            entry["category"] = category
        if tags is not None:
            entry["tags"] = tags
        if added_at is not None:
            entry.setdefault("addedAt", added_at)
        data[key] = entry
        _write(config.META_FILE, data)


def resolve_meta(item):
    data = get_meta()
    infohash = (item.get("infoHash") or "").lower()
    gid = item.get("gid") or ""
    for key in (infohash, gid):
        if key and key in data:
            return data[key]
    return {}


def promote_meta(gid, infohash):
    if not gid or not infohash:
        return
    infohash = infohash.lower()
    with _lock:
        data = get_meta()
        if gid in data and infohash not in data:
            data[infohash] = data.pop(gid)
            _write(config.META_FILE, data)
