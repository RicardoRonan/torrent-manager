import base64
import json
import time
import urllib.error
import urllib.request

from . import config, platform, store


class Aria2Error(RuntimeError):
    pass


def _error_message(body):
    err = body.get("error")
    if isinstance(err, dict):
        return err.get("message", str(err))
    return str(err) if err else ""


class Aria2Client:
    def __init__(self):
        self.proc = None
        self.secret = store.get_rpc_secret()

    @property
    def port(self):
        return int(store.get_settings().get("rpc_port", 6800))

    @property
    def endpoint(self):
        return f"http://127.0.0.1:{self.port}/jsonrpc"

    def rpc(self, method, params=None, timeout=15):
        payload = {
            "jsonrpc": "2.0",
            "id": "tm",
            "method": method,
            "params": [f"token:{self.secret}"] + (params or []),
        }
        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            try:
                body = json.loads(raw)
                raise Aria2Error(_error_message(body) or f"aria2 HTTP {exc.code}")
            except json.JSONDecodeError:
                raise Aria2Error(f"aria2 HTTP {exc.code}: {raw[:200]}")
        except urllib.error.URLError as exc:
            raise Aria2Error(f"aria2 unreachable: {exc.reason}")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            raise Aria2Error(f"invalid aria2 response: {raw[:200]}")
        if "error" in body:
            raise Aria2Error(_error_message(body))
        return body.get("result")

    def alive(self):
        try:
            self.rpc("aria2.getVersion", timeout=3)
            return True
        except Exception:
            return False

    def _build_cmd(self, settings):
        binary = platform.aria2_binary()
        if not binary:
            raise Aria2Error("aria2c not found. Install aria2 or bundle it under bin/")
        cmd = [
            binary,
            "--enable-rpc",
            "--rpc-listen-all=false",
            f"--rpc-listen-port={self.port}",
            f"--rpc-secret={self.secret}",
            "--continue=true",
            f"--dir={settings['download_dir']}",
            "--seed-time=0",
            "--seed-ratio=0.0",
            "--bt-save-metadata=true",
            "--follow-torrent=true",
            "--bt-detach-seed-only=true",
            f"--enable-dht={'true' if settings.get('dht') else 'false'}",
            "--enable-dht6=false",
            f"--bt-enable-lpd={'true' if settings.get('lpd') else 'false'}",
            f"--enable-peer-exchange={'true' if settings.get('pex') else 'false'}",
            "--bt-require-crypto=false",
            f"--listen-port={settings.get('listen_port', '6881-6999')}",
            f"--dht-listen-port={settings.get('listen_port', '6881-6999')}",
            f"--max-concurrent-downloads={settings.get('max_concurrent', 10)}",
            f"--max-connection-per-server={settings.get('max_connection_per_server', 8)}",
            f"--bt-max-peers={settings.get('bt_max_peers', 128)}",
            f"--bt-request-peer-speed-limit={settings.get('bt_request_peer_speed_limit', '1M')}",
            f"--disk-cache={settings.get('disk_cache', '64M')}",
            f"--file-allocation={settings.get('file_allocation', 'falloc')}",
            f"--bt-max-open-files={settings.get('bt_max_open_files', 200)}",
            f"--enable-mmap={'true' if settings.get('enable_mmap') else 'false'}",
            f"--optimize-concurrent-downloads={'true' if settings.get('optimize_concurrent_downloads') else 'false'}",
            f"--auto-save-interval={settings.get('auto_save_interval', 30)}",
            f"--bt-tracker-connect-timeout={settings.get('bt_tracker_connect_timeout', 5)}",
            f"--bt-tracker-timeout={settings.get('bt_tracker_timeout', 5)}",
            "--save-session-interval=30",
            f"--save-session={config.SESSION_FILE}",
            "--auto-file-renaming=true",
            "--rpc-allow-origin-all=false",
            "--quiet=true",
            "--summary-interval=0",
            "--console-log-level=warn",
        ]
        if config.SESSION_FILE.exists() and config.SESSION_FILE.stat().st_size > 0:
            cmd.append(f"--input-file={config.SESSION_FILE}")
        interface = settings.get("interface")
        if interface and interface.strip():
            cmd.append(f"--interface={interface.strip()}")
        if settings.get("global_download_limit"):
            cmd.append(f"--max-overall-download-limit={settings['global_download_limit']}")
        if settings.get("global_upload_limit"):
            cmd.append(f"--max-overall-upload-limit={settings['global_upload_limit']}")
        if not settings.get("upload_while_downloading", True):
            cmd.append("--max-upload-limit=0")
        lowest = str(settings.get("lowest_speed_limit") or "0")
        if lowest not in ("0", ""):
            cmd.append(f"--lowest-speed-limit={lowest}")
        if settings.get("encryption", True):
            cmd.append("--bt-min-crypto-level=arc4")
        return cmd

    def ensure_started(self):
        settings = store.get_settings()
        if self.alive():
            return
        config.STATE_DIR.mkdir(parents=True, exist_ok=True)
        self.proc = platform.spawn_detached(self._build_cmd(settings))
        for _ in range(60):
            if self.alive():
                return
            time.sleep(0.1)
        raise Aria2Error("aria2 RPC did not start")

    def restart(self):
        self.shutdown()
        self.secret = store.get_rpc_secret()
        self.ensure_started()

    def shutdown(self):
        if not self.proc:
            return
        try:
            self.rpc("aria2.shutdown", timeout=5)
        except Exception:
            pass
        try:
            self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=3)
            except Exception:
                pass
        self.proc = None

    def save_session(self):
        try:
            self.rpc("aria2.saveSession", timeout=5)
        except Exception:
            pass

    def global_stat(self):
        return self.rpc("aria2.getGlobalStat") or {}

    def version(self):
        return self.rpc("aria2.getVersion") or {}

    def list_downloads(self):
        keys = STATUS_KEYS
        active = self.rpc("aria2.tellActive", [keys]) or []
        waiting = self.rpc("aria2.tellWaiting", [0, 2000, keys]) or []
        stopped = self.rpc("aria2.tellStopped", [0, 2000, keys]) or []
        return active + waiting + stopped

    def status(self, gid):
        return self.rpc("aria2.tellStatus", [gid, DETAIL_KEYS]) or {}

    def add_uri(self, uri, options=None):
        return self.rpc("aria2.addUri", [[uri], options or {}])

    def add_torrent(self, raw_bytes, options=None):
        return self.rpc(
            "aria2.addTorrent", [base64.b64encode(raw_bytes).decode(), [], options or {}]
        )

    def pause(self, gid):
        return self.rpc("aria2.pause", [gid])

    def unpause(self, gid):
        return self.rpc("aria2.unpause", [gid])

    def _try_remove(self, gid):
        for method in ("aria2.remove", "aria2.forceRemove"):
            try:
                self.rpc(method, [gid])
                return True
            except Aria2Error:
                continue
        return False

    def remove(self, gid):
        if self._try_remove(gid):
            return
        infohash = ""
        try:
            infohash = (self.rpc("aria2.tellStatus", [gid, ["infoHash"]]) or {}).get("infoHash", "")
        except Aria2Error:
            infohash = ""
        if not infohash:
            return
        for item in self.list_downloads():
            other = item.get("gid")
            if other != gid and (item.get("infoHash") or "").lower() == infohash.lower():
                self._try_remove(other)

    def remove_result(self, gid):
        try:
            self.rpc("aria2.removeDownloadResult", [gid])
        except Aria2Error:
            pass

    def change_option(self, gid, options):
        return self.rpc("aria2.changeOption", [gid, options])

    def change_global_option(self, options):
        return self.rpc("aria2.changeGlobalOption", [options])

    def get_peers(self, gid):
        return self.rpc("aria2.getPeers", [gid]) or []

    def get_trackers(self, gid):
        return self.rpc("aria2.getTrackers", [gid]) or []

    def get_servers(self, gid):
        return self.rpc("aria2.getServers", [gid]) or []

    def purge_results(self):
        try:
            self.rpc("aria2.purgeDownloadResult")
        except Aria2Error:
            pass


STATUS_KEYS = [
    "gid",
    "status",
    "totalLength",
    "completedLength",
    "uploadLength",
    "downloadSpeed",
    "uploadSpeed",
    "connections",
    "numSeeders",
    "seeder",
    "dir",
    "infoHash",
    "errorCode",
    "errorMessage",
    "files",
    "bittorrent",
    "numPieces",
    "pieceLength",
]

DETAIL_KEYS = STATUS_KEYS + ["pieceProgress", "verifiedLength"]


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def derive_name(item):
    info = (item.get("bittorrent") or {}).get("info") or {}
    if info.get("name"):
        return info["name"]
    files = item.get("files") or []
    if files:
        path = files[0].get("path") or ""
        base = path.rstrip("/").split("/")[-1]
        if base:
            return base
    infohash = item.get("infoHash")
    if infohash:
        return f"[METADATA] {infohash[:12]}"
    return item.get("gid", "unknown")


def derive_state(item):
    status = item.get("status")
    if status == "active" and _int(item.get("totalLength")) == 0:
        return "metadata"
    if status == "active":
        if item.get("seeder") == "true":
            return "seeding"
        total = _int(item.get("totalLength"))
        done = _int(item.get("completedLength"))
        if total and done >= total:
            return "seeding"
        return "downloading"
    if status == "waiting":
        return "queued"
    if status == "paused":
        return "paused"
    if status == "error":
        return "error"
    if status == "complete":
        return "complete"
    if status == "removed":
        return "removed"
    return status or "unknown"


def normalize(item, meta=None):
    meta = meta or {}
    total = _int(item.get("totalLength"))
    done = _int(item.get("completedLength"))
    uploaded = _int(item.get("uploadLength"))
    speed = _int(item.get("downloadSpeed"))
    percent = round(done / total * 100, 2) if total else 0.0
    eta = int((total - done) / speed) if speed > 0 and total > done else None
    ratio = round(uploaded / done, 3) if done and uploaded else 0.0
    files = item.get("files") or []
    return {
        "gid": item.get("gid"),
        "name": derive_name(item),
        "state": derive_state(item),
        "status": item.get("status"),
        "totalLength": total,
        "completedLength": done,
        "uploadLength": uploaded,
        "percent": percent,
        "downloadSpeed": speed,
        "uploadSpeed": _int(item.get("uploadSpeed")),
        "connections": _int(item.get("connections")),
        "seeds": _int(item.get("numSeeders")),
        "ratio": ratio,
        "eta": eta,
        "dir": item.get("dir"),
        "infoHash": (item.get("infoHash") or "").lower(),
        "filesCount": len(files),
        "numPieces": _int(item.get("numPieces")),
        "errorCode": item.get("errorCode"),
        "errorMessage": item.get("errorMessage") or "",
        "category": meta.get("category", ""),
        "tags": meta.get("tags", []),
        "addedAt": meta.get("addedAt"),
    }


def file_entries(item):
    out = []
    for index, entry in enumerate(item.get("files") or []):
        path = entry.get("path") or ""
        total = _int(entry.get("length"))
        done = _int(entry.get("completedLength"))
        selected = entry.get("selected") == "true"
        out.append(
            {
                "index": index,
                "path": path,
                "name": path.rstrip("/").split("/")[-1] or path,
                "length": total,
                "completedLength": done,
                "percent": round(done / total * 100, 2) if total else 0.0,
                "selected": selected,
            }
        )
    return out
