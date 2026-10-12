import base64
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import actions, aria2, config, store
from .events import EventHub, WatchFolder
from .models import (
    ActionRequest,
    AddRequest,
    BatchRequest,
    CategoryIn,
    FilesRequest,
    OptionsRequest,
    ViewIn,
)

client = aria2.Aria2Client()
hub = EventHub(client)
watcher = WatchFolder(client)

EDITABLE_TORRENT_OPTIONS = {
    "max-download-limit",
    "max-upload-limit",
    "select-file",
    "bt-prioritize-piece",
    "bt-max-peers",
    "max-connection-per-server",
    "seed-time",
}


@asynccontextmanager
async def lifespan(app):
    settings = store.get_settings()
    if settings.get("autostart_aria2", True):
        try:
            client.ensure_started()
        except Exception:
            pass
    hub.start()
    watcher.start()
    yield
    hub.stop()
    watcher.stop()
    try:
        client.save_session()
    except Exception:
        pass
    client.shutdown()


def require_auth(request: Request):
    token = store.get_token()
    supplied = request.headers.get("x-auth-token") or request.cookies.get("tm_token")
    if supplied != token:
        raise HTTPException(status_code=401, detail="unauthorized")
    return True


api = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])
app = FastAPI(title="Torrent Manager", lifespan=lifespan)


def _category_path(name):
    for entry in store.get_categories():
        if entry.get("name") == name:
            return entry.get("path") or ""
    return ""


def _gid_infohash_map():
    mapping = {}
    try:
        for raw in client.list_downloads():
            mapping[raw.get("gid")] = (raw.get("infoHash") or "").lower()
    except Exception:
        pass
    return mapping


def _meta_key(gid, mapping):
    infohash = mapping.get(gid) or ""
    return infohash or gid


@api.get("/status")
def status():
    return {
        "global": hub.latest.get("global", {}),
        "version": _safe(lambda: client.version().get("version")),
        "aria2Running": client.alive(),
        "ts": time.time(),
    }


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


@api.get("/downloads")
def downloads():
    return {"items": hub.latest.get("items", []), "global": hub.latest.get("global", {})}


@api.get("/downloads/{gid}")
def download_detail(gid: str):
    raw = _safe(lambda: client.status(gid))
    if not raw:
        raise HTTPException(404, "not found")
    meta = store.resolve_meta(raw)
    item = aria2.normalize(raw, meta)
    item["files"] = aria2.file_entries(raw)
    item["peers"] = _safe(lambda: client.get_peers(gid), [])
    item["trackers"] = _safe(lambda: client.get_trackers(gid), [])
    item["servers"] = _safe(lambda: client.get_servers(gid), [])
    item["pieceLength"] = int(raw.get("pieceLength") or 0)
    return item


@api.post("/downloads")
def add_downloads(req: AddRequest):
    settings = store.get_settings()
    directory = req.dir or _category_path(req.category) or settings["download_dir"]
    os.makedirs(directory, exist_ok=True)
    options = {"dir": directory}
    added = []
    now = time.time()
    for uri in req.magnets:
        uri = uri.strip()
        if not uri:
            continue
        gid = client.add_uri(uri, options)
        store.record_meta(gid, category=req.category, tags=req.tags, added_at=now)
        added.append(gid)
    for url in req.urls:
        url = url.strip()
        if not url:
            continue
        gid = client.add_uri(url, options)
        store.record_meta(gid, category=req.category, tags=req.tags, added_at=now)
        added.append(gid)
    for torrent in req.torrents:
        raw = base64.b64decode(torrent.data)
        gid = client.add_torrent(raw, options)
        store.record_meta(gid, category=req.category, tags=req.tags, added_at=now)
        added.append(gid)
    hub.poll_once()
    return {"count": len(added), "gids": added, "dir": directory}


@api.post("/downloads/batch")
def batch(req: BatchRequest):
    mapping = _gid_infohash_map()
    performed = 0
    for gid in req.gids:
        if req.action == "pause":
            _safe(lambda g=gid: client.pause(g))
        elif req.action == "resume":
            _safe(lambda g=gid: client.unpause(g))
        elif req.action == "remove":
            client.remove(gid)
            client.remove_result(gid)
        elif req.action == "category":
            store.record_meta(_meta_key(gid, mapping), category=req.category)
        elif req.action == "tags":
            store.record_meta(_meta_key(gid, mapping), tags=req.tags)
        performed += 1
    hub.poll_once()
    return {"count": performed}


@api.post("/downloads/{gid}/pause")
def pause(gid: str):
    client.pause(gid)
    return {"ok": True}


@api.post("/downloads/{gid}/resume")
def resume(gid: str):
    client.unpause(gid)
    return {"ok": True}


@api.post("/downloads/{gid}/remove")
def remove(gid: str):
    client.remove(gid)
    client.remove_result(gid)
    return {"ok": True}


@api.post("/downloads/{gid}/files")
def set_files(gid: str, req: FilesRequest):
    raw = _safe(lambda: client.status(gid)) or {}
    entries = raw.get("files") or []
    if entries:
        selected = [str(f.index + 1) for f in req.files if f.selected]
        options = {"select-file": ",".join(selected) if selected else ""}
        try:
            client.change_option(gid, options)
        except aria2.Aria2Error as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=200)
    if req.sequential is not None:
        _safe(lambda: client.change_option(gid, {"bt-prioritize-piece": "head" if req.sequential else ""}))
    hub.poll_once()
    return {"ok": True}


@api.post("/downloads/{gid}/options")
def set_options(gid: str, req: OptionsRequest):
    clean = {k: str(v) for k, v in req.options.items() if k in EDITABLE_TORRENT_OPTIONS}
    if not clean:
        raise HTTPException(400, "no editable options provided")
    try:
        client.change_option(gid, clean)
    except aria2.Aria2Error as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=200)
    hub.poll_once()
    return {"ok": True}


@api.get("/global")
def get_global():
    settings = store.get_settings()
    return {
        "max_concurrent": settings["max_concurrent"],
        "max_connection_per_server": settings["max_connection_per_server"],
        "global_download_limit": settings["global_download_limit"],
        "global_upload_limit": settings["global_upload_limit"],
        "listen_port": settings["listen_port"],
        "dht": settings["dht"],
        "pex": settings["pex"],
        "lpd": settings["lpd"],
        "encryption": settings["encryption"],
        "interface": settings["interface"],
        "kill_switch": settings["kill_switch"],
    }


@api.post("/session/save")
def save_session():
    client.save_session()
    return {"ok": True}


@api.get("/settings")
def get_settings():
    return store.get_settings()


RESTART_KEYS = {
    "rpc_port",
    "interface",
    "listen_port",
    "dht",
    "pex",
    "lpd",
    "encryption",
    "max_connection_per_server",
    "upload_while_downloading",
    "download_dir",
    "bt_max_peers",
    "bt_request_peer_speed_limit",
    "disk_cache",
    "file_allocation",
    "bt_max_open_files",
    "lowest_speed_limit",
    "enable_mmap",
    "auto_save_interval",
    "bt_tracker_connect_timeout",
    "bt_tracker_timeout",
}


@api.get("/presets")
def presets():
    return config.PERF_PRESETS


@api.put("/settings")
def put_settings(patch: dict):
    updated = store.update_settings(patch)
    if any(key in patch for key in RESTART_KEYS):
        _safe(client.restart)
    live = {}
    if "max_concurrent" in patch:
        live["max-concurrent-downloads"] = str(updated["max_concurrent"])
    if "optimize_concurrent_downloads" in patch:
        live["optimize-concurrent-downloads"] = "true" if updated["optimize_concurrent_downloads"] else "false"
    if "global_download_limit" in patch:
        live["max-overall-download-limit"] = str(updated["global_download_limit"])
    if "global_upload_limit" in patch:
        live["max-overall-upload-limit"] = str(updated["global_upload_limit"])
    if live:
        _safe(lambda: client.change_global_option(live))
    hub.poll_once()
    return updated


@api.post("/engine/restart")
def engine_restart():
    client.restart()
    hub.poll_once()
    return {"ok": True}


@api.get("/categories")
def categories():
    return store.get_categories()


@api.put("/categories")
def put_categories(items: list[CategoryIn]):
    return store.set_categories([i.model_dump() for i in items])


@api.get("/tags")
def tags():
    return store.get_tags()


@api.put("/tags")
def put_tags(items: list[str]):
    return store.set_tags(items)


@api.get("/views")
def views():
    return store.get_views()


@api.put("/views")
def put_views(items: list[ViewIn]):
    return store.set_views([i.model_dump() for i in items])


@api.get("/events")
def events():
    return StreamingResponse(
        hub.stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api.post("/actions/open")
def do_open(req: ActionRequest):
    raw = _safe(lambda: client.status(req.gid))
    if not raw:
        raise HTTPException(404, "not found")
    path = actions.pick_file(raw.get("dir"), raw.get("files"), req.fileIndex)
    try:
        return {"ok": True, "path": actions.open_target(path)}
    except FileNotFoundError as exc:
        raise HTTPException(404, f"missing: {exc}")


@api.post("/actions/reveal")
def do_reveal(req: ActionRequest):
    raw = _safe(lambda: client.status(req.gid))
    if not raw:
        raise HTTPException(404, "not found")
    path = actions.pick_file(raw.get("dir"), raw.get("files"), req.fileIndex)
    try:
        return {"ok": True, "path": actions.reveal_target(path)}
    except FileNotFoundError as exc:
        raise HTTPException(404, f"missing: {exc}")


app.include_router(api)


@app.get("/")
def index(request: Request):
    response = FileResponse(config.STATIC_DIR / "index.html")
    token = store.get_token()
    if request.cookies.get("tm_token") != token:
        response.set_cookie("tm_token", token, httponly=True, samesite="lax")
    return response


app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


def main():
    from .cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    main()
