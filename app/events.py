import json
import queue
import threading
import time
from pathlib import Path

from . import aria2, platform, store


class EventHub:
    def __init__(self, client):
        self.client = client
        self.subscribers = set()
        self.lock = threading.Lock()
        self.latest = {"items": [], "global": {}, "events": [], "ts": 0}
        self._states = {}
        self._thread = None
        self._stop = threading.Event()

    def subscribe(self):
        q = queue.Queue(maxsize=50)
        with self.lock:
            self.subscribers.add(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            self.subscribers.discard(q)

    def _broadcast(self, message):
        with self.lock:
            targets = list(self.subscribers)
        for q in targets:
            try:
                q.put_nowait(message)
            except queue.Full:
                pass

    def _interface_up(self, name):
        return platform.interface_up(name)

    def _kill_switch(self, items):
        settings = store.get_settings()
        if not settings.get("kill_switch"):
            return
        interface = (settings.get("interface") or "").strip()
        if not interface or self._interface_up(interface):
            return
        for item in items:
            if item["state"] in ("downloading", "seeding", "metadata", "queued"):
                try:
                    self.client.pause(item["gid"])
                except aria2.Aria2Error:
                    pass

    def poll_once(self):
        items_raw = self.client.list_downloads()
        items = []
        events = []
        for raw in items_raw:
            infohash = (raw.get("infoHash") or "").lower()
            gid = raw.get("gid")
            if infohash and gid:
                store.promote_meta(gid, infohash)
            meta = store.resolve_meta(raw)
            item = aria2.normalize(raw, meta)
            prev = self._states.get(gid)
            if item["state"] == "complete" and prev != "complete":
                events.append({"type": "completed", "name": item["name"], "gid": gid})
            self._states[gid] = item["state"]
            items.append(item)
        self._kill_switch(items)
        payload = {"items": items, "global": self.client.global_stat(), "events": events, "ts": time.time()}
        self.latest = payload
        self._broadcast(payload)
        return payload

    def _run(self):
        while not self._stop.is_set():
            try:
                refresh = store.get_settings().get("refresh_ms", 1000)
                self.poll_once()
            except Exception:
                refresh = 2000
                self.latest = {
                    "items": self.latest.get("items", []),
                    "global": {"error": "aria2 unreachable"},
                    "events": [],
                    "ts": time.time(),
                }
            self._stop.wait(max(refresh, 300) / 1000)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def stream(self):
        q = self.subscribe()
        try:
            yield f"data: {json.dumps(self.latest)}\n\n"
            while True:
                try:
                    message = q.get(timeout=15)
                    yield f"data: {json.dumps(message)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            self.unsubscribe(q)


class WatchFolder:
    def __init__(self, client):
        self.client = client
        self._stop = threading.Event()
        self._thread = None

    def _run(self):
        while not self._stop.is_set():
            try:
                settings = store.get_settings()
                folder = settings.get("watch_folder") or ""
                if folder:
                    source = Path(folder)
                    if source.is_dir():
                        target = source / "added"
                        for torrent in sorted(source.glob("*.torrent")):
                            try:
                                gid = self.client.add_torrent(
                                    torrent.read_bytes(), {"dir": settings["download_dir"]}
                                )
                                store.record_meta(gid, added_at=time.time())
                                target.mkdir(exist_ok=True)
                                torrent.rename(target / torrent.name)
                            except Exception:
                                pass
            except Exception:
                pass
            self._stop.wait(5)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
