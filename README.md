# Torrent Manager

A local web UI for adding and managing torrents — single or bulk — backed by
[aria2](https://aria2.github.io/). FastAPI + SSE on the backend, no-build vanilla
JS on the front end. Downloads never seed (`seed-time=0`).

The interface uses a design language adapted from
[Beautiful UI](https://www.beautifului.dev) by Turbo (MIT — see
`LICENSE-beautifului`): soft monochrome surfaces with a single blue accent,
hairline borders, generous radii, Inter + JetBrains Mono, and motion from the
`cubic-bezier(.23,1,.32,1)` family.

## Features

- **Torrent list** — capsule "task rows" with a progress ring, status chip, and
  expandable body (detail chips + per-file sub-steps).
- **Bulk operations** — hover-select rows and batch pause / resume / remove.
- **Details drawer** — General, Files (select + sequential), Peers, Trackers.
- **Organization** — categories (with save paths), tags, and saved views.
- **Add ergonomically** — paste magnets, drop `.torrent` files, add URLs; pick
  category/tags/save path at add time.
- **Bandwidth & queue** — global and per-torrent limits, presets, max concurrent.
- **Privacy** — bind to an interface (e.g. a VPN) and an optional kill switch.
- **Desktop notifications** on completion, light/dark themes (dark first),
  keyboard shortcuts, pixel-grid loading states.
- **Watch folder** — auto-add `.torrent` files dropped into a directory.
- **Local actions** — open a file or reveal it in your file manager.
- Session persistence via aria2, so the list survives restarts.

## Requirements

- Python 3.10+
- `aria2c` on your `PATH` (`sudo apt install aria2`)

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

```bash
.venv/bin/python -m app.main
# or: .venv/bin/uvicorn app.main:app --port 8080
```

Open <http://127.0.0.1:8080>.

Options: `--host` (default `127.0.0.1`), `--port` (default `8080`), `--reload`.

### Auth

The server generates a token on first run (`~/.config/torrent-manager/token`)
and sets it as an HttpOnly cookie automatically when you open the UI, so there
is no login prompt on localhost. Scripts can pass it via the `X-Auth-Token`
header. Keep the server bound to `127.0.0.1` unless you also add real auth.

## Magnet links & one-click launch

The CLI accepts URIs and forwards them to a running instance (single-instance):

```bash
python run.py "magnet:?xt=urn:btih:..."     # adds to the running app, else starts it
python run.py --add "https://example.com/file.torrent"
./run.py --install-desktop                   # register launcher + magnet: handler
```

`--install-desktop` writes `~/.local/share/applications/torrent-manager.desktop` and
registers it as the default `x-scheme-handler/magnet` via `xdg-mime`, so clicking a
magnet link in your browser opens the app and adds the torrent. Browsers still ask
once to confirm the handler.

## Packaging (desktop app)

### Linux (one-folder)
```bash
.venv/bin/pip install -r packaging/requirements-build.txt
.venv/bin/pyinstaller --noconfirm packaging/torrent-manager.spec   # -> dist/TorrentManager/
bash packaging/install-linux.sh                                    # -> ~/.local/opt/torrent-manager
```
`install-linux.sh` copies the build, creates a `torrent-manager` shim on `~/.local/bin`,
and runs `--install-desktop`.

- **Window:** on Linux the native window uses pywebview's GTK/WebKit backend; if
  WebKit isn't available the app **falls back to your browser automatically**. To
  enable a native window, install `sudo apt install gir1.2-webkit2-4.1` and run from a
  venv that can see PyGObject (e.g. created with `--system-site-packages`).
- **aria2:** the frozen app uses a bundled `bin/aria2c` if present, otherwise the
  system `aria2c` on `PATH`. aria2 publishes no static Linux build, so for a portable
  Linux bundle drop a static `aria2c` at `packaging/bin/aria2c` before building.

### Windows (build on a Windows machine)
```powershell
.\.venv\Scripts\pip install -r packaging\requirements-build.txt
.\packaging\fetch-aria2-windows.ps1        # bundles bin\aria2c.exe (GPL; license copied)
.\.venv\Scripts\pyinstaller --noconfirm packaging\torrent-manager.spec
.\dist\TorrentManager\TorrentManager.exe --register-magnet
```
The native window uses WebView2 (preinstalled on Windows 10/11). `--register-magnet`
writes `HKCU\Software\Classes\magnet` so magnet links open the app.

Packaged startup errors are written to `<state>/error.log` (state dir is
`%LOCALAPPDATA%\torrent-manager\state` on Windows, `~/.local/state/torrent-manager` on Linux).

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| `/` | Focus search |
| `a` | Select all visible |
| `p` / `r` | Pause / resume selected |
| `Delete` | Remove selected |
| `Esc` | Close drawer / modal / menu |

## Performance tuning

Settings → **Performance** offers three presets (Balanced is the default). They
map to aria2 options that actually affect throughput:

| Setting | Conservative | Balanced | Aggressive |
|---|---|---|---|
| `max-concurrent-downloads` | 5 | 10 | 20 |
| `bt-max-peers` | 60 | 128 | 300 |
| `bt-request-peer-speed-limit` | 256K | 1M | 5M |
| `disk-cache` | 32M | 64M | 128M |
| `file-allocation` | prealloc | falloc | none |
| `bt-max-open-files` | 100 | 200 | 500 |
| `lowest-speed-limit` | off | 10K | 20K |
| `optimize-concurrent-downloads` | off | on | on |
| `enable-mmap` | off | on | on |

Changing these restarts the aria2 engine (use **Restart engine** in Settings).
`max-concurrent` and `optimize-concurrent-downloads` apply live.

Notes:

- **Threading in the app won't speed up downloads.** aria2 is a separate
  process that already downloads pieces from many peers in parallel; this app
  only sends it RPC commands.
- **Port forwarding is the biggest real-world factor.** Forward the listen port
  range (TCP+UDP, default `6881-6999`) on your router to this PC so peers can
  connect *to* you. The app cannot configure your router, and some ISPs use
  CGNAT where forwarding is impossible without a VPN that offers it.
- Presets trade speed for resources: more peers means more CPU/RAM/open files
  and heavier router NAT tables. Aggressive is not always faster.

## Layout

```
run.py                       entry point (CLI: magnets, --install-desktop, window/browser)
app/
  main.py      FastAPI app, routers, cookie auth, static mount
  cli.py       argument parsing, single-instance forward, window/browser launch
  platform.py  cross-platform paths, aria2 discovery, open/reveal, spawn
  desktop.py   .desktop / magnet handler (Linux) and registry (Windows)
  aria2.py     JSON-RPC client, normalization, launch flags
  events.py    poller + SSE broadcaster, completion events, watch folder
  actions.py   open / reveal in file manager
  store.py     settings, categories, tags, views, token, per-torrent meta
  config.py    paths and defaults
static/
  index.html   app shell
  tokens.css   design tokens (colors, radii, shadows, motion, fonts)
  fonts/       Inter + JetBrains Mono (woff2)
  app.js       capsule task list, sidebar, drawer, modals
  style.css    component styles
packaging/                   PyInstaller spec, icons, install scripts
tests/                       unit tests (pytest)
```

Config and state live under `~/.config/torrent-manager/` and
`~/.local/state/torrent-manager/` (override with `TM_CONFIG_DIR` / `TM_STATE_DIR`).

## HTTP API

All `/api/*` routes require the auth cookie or `X-Auth-Token`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/status` | Global stats + aria2 version |
| GET | `/api/downloads` | Normalized torrent list |
| GET | `/api/downloads/{gid}` | Details (files, peers, trackers) |
| POST | `/api/downloads` | Add magnets / torrents / urls |
| POST | `/api/downloads/{gid}/{pause\|resume\|remove}` | Per-torrent action |
| POST | `/api/downloads/batch` | Batch action + category/tags |
| POST | `/api/downloads/{gid}/files` | Select files / sequential |
| POST | `/api/downloads/{gid}/options` | Per-torrent limits |
| GET | `/api/events` | SSE stream of updates |
| GET | `/api/settings`, PUT `/api/settings` | Settings |
| GET | `/api/categories`, PUT | Categories |
| GET | `/api/tags`, PUT | Tags |
| GET | `/api/views`, PUT | Saved views |
| POST | `/api/actions/{open\|reveal}` | Local file actions |
| POST | `/api/engine/restart` | Restart aria2 with current settings |

## Tests

```bash
.venv/bin/pytest -q
```

## Legal

This is a general-purpose BitTorrent client front-end. Downloading or
distributing copyrighted material without permission is illegal in most
jurisdictions. Use it only with content you have the right to download — for
example public-domain films from the [Internet Archive](https://archive.org),
Linux distributions, or other freely licensed media.
