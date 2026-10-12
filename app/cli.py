import argparse
import json
import threading
import time
import urllib.request
import webbrowser

from . import desktop, store

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080


def _rpc_headers():
    return {"X-Auth-Token": store.get_token()}


def _running(host, port, timeout=1.5):
    try:
        req = urllib.request.Request(f"http://{host}:{port}/api/status", headers=_rpc_headers())
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _post_magnet(host, port, uri):
    payload = json.dumps({"magnets": [uri]}).encode()
    headers = {"Content-Type": "application/json", **_rpc_headers()}
    req = urllib.request.Request(
        f"http://{host}:{port}/api/downloads", data=payload, headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status == 200


def _wait(host, port, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _running(host, port):
            return True
        time.sleep(0.3)
    return False


def _add_later(host, port, uris):
    if not _wait(host, port):
        return
    for uri in uris:
        try:
            _post_magnet(host, port, uri)
        except Exception:
            pass


def _run_browser(host, port, url, uris, no_open):
    import uvicorn

    def opener():
        if _wait(host, port):
            if not no_open:
                webbrowser.open(url)
            for uri in uris:
                try:
                    _post_magnet(host, port, uri)
                except Exception:
                    pass

    threading.Thread(target=opener, daemon=True).start()
    uvicorn.run(_app(), host=host, port=port, log_level="warning")


def _run_window(host, port, url, uris):
    import uvicorn

    server = uvicorn.Server(uvicorn.Config(_app(), host=host, port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait(host, port)
    threading.Thread(target=_add_later, args=(host, port, uris), daemon=True).start()

    opened = False
    try:
        import webview

        webview.create_window("Torrent Manager", url, width=1180, height=760)
        webview.start()
        opened = True
    except Exception:
        opened = False
    if not opened:
        webbrowser.open(url)
    server.should_exit = True
    thread.join()


def _app():
    from .main import app

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(prog="torrent-manager", description="Torrent Manager")
    parser.add_argument("uri", nargs="?", help="magnet: or http(s) URI to add and exit")
    parser.add_argument("--add", action="append", metavar="URI", help="add a magnet/URL (repeatable)")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--window", action="store_true", help="open a native window")
    parser.add_argument("--browser", action="store_true", help="open in the browser")
    parser.add_argument("--no-open", action="store_true", help="start without opening a UI")
    parser.add_argument("--install-desktop", action="store_true", help="install launcher + magnet handler")
    parser.add_argument("--register-magnet", action="store_true", help="register magnet: handler only")
    parser.add_argument("--reload", action="store_true", help="dev auto-reload")
    args = parser.parse_args(argv)

    if args.install_desktop or args.register_magnet:
        print(json.dumps(desktop.register_magnet(), indent=2))
        return 0

    uris = list(args.add or [])
    if args.uri:
        uris.append(args.uri)
    uris = [u for u in uris if u]

    if uris and _running(args.host, args.port):
        ok = all(_post_magnet(args.host, args.port, u) for u in uris)
        print("sent to running instance" if ok else "failed to send to running instance")
        return 0 if ok else 1

    url = f"http://{args.host}:{args.port}/"

    if args.reload:
        import uvicorn

        uvicorn.run("app.main:app", host=args.host, port=args.port, reload=True)
        return 0

    if args.browser:
        _run_browser(args.host, args.port, url, uris, args.no_open)
    else:
        _run_window(args.host, args.port, url, uris)
    return 0
