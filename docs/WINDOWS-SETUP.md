# Windows setup

Run Torrent Manager from source on Windows 10 or 11. Every command below is
PowerShell, run from the project folder.

## 1. Install Python 3.10+

```powershell
winget install Python.Python.3.12
```

Or download it from <https://www.python.org/downloads/windows/>. Tick **Add
python.exe to PATH** in the installer. Verify with `py -3 --version`.

## 2. Install aria2c

The app drives [aria2](https://aria2.github.io/) behind the scenes and needs
`aria2c.exe` on your `PATH`.

1. Download a Windows build from the
   [aria2 releases page](https://github.com/aria2/aria2/releases)
   (for example `aria2-1.37.0-win-64bit-build1.zip`).
2. Extract `aria2c.exe` to a permanent folder, for example
   `%LOCALAPPDATA%\Programs\aria2`.
3. Add that folder to `PATH` (Settings, then System, then About, then Advanced
   system settings, then Environment Variables). Or, for the current session
   only:

```powershell
$env:PATH += ";$env:LOCALAPPDATA\Programs\aria2"
```

4. Verify with `aria2c --version`.

## 3. Create a virtual environment and install dependencies

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If you prefer an activated shell instead of calling `python.exe` directly,
activation may be blocked by the default execution policy. Allow it for the
current session only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 4. Run it

```powershell
.\.venv\Scripts\python.exe -m app.main
```

Or, using the CLI entry point:

```powershell
.\.venv\Scripts\python.exe run.py
```

The server starts at <http://127.0.0.1:8080> and opens in your browser.
Options: `--host` (default `127.0.0.1`), `--port` (default `8080`),
`--browser`, `--window`, `--no-open`, `--reload`.

By default the app starts and supervises its own `aria2c` process. Keep the
server bound to `127.0.0.1` unless you add real authentication.

## 5. Native window (optional)

Instead of a browser tab you can run the UI in a native window:

```powershell
.\.venv\Scripts\python.exe -m pip install pywebview
.\.venv\Scripts\python.exe run.py --window
```

The window uses WebView2, which is preinstalled on Windows 10 and 11. If it is
missing, install the
[WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/).
If the window fails to start, the app falls back to your browser automatically.

## 6. Magnet links and one-click launch (optional)

Register the app as the `magnet:` handler so clicking a magnet link opens it:

```powershell
.\.venv\Scripts\python.exe run.py --register-magnet
```

This writes `HKCU\Software\Classes\magnet`. Windows and your browser still ask
once to confirm the handler. `--install-desktop` does the same thing on Windows.

You can also send a magnet or URL to a running instance:

```powershell
.\.venv\Scripts\python.exe run.py "magnet:?xt=urn:btih:..."
.\.venv\Scripts\python.exe run.py --add "https://example.com/file.torrent"
```

## 7. Allow it through the firewall (optional)

For incoming peer connections, allow Python or `aria2c.exe` on private
networks when Windows Firewall prompts. Forward the listen port range
(TCP+UDP, default `6881-6999`) on your router so peers can reach you. This is
the single biggest real-world speed factor. Some ISPs use CGNAT, where
forwarding is impossible without a VPN that offers it.

## Where files live

| What | Path |
|------|------|
| Config (settings, categories, tags, token) | `%APPDATA%\torrent-manager` |
| State (session, metadata, `error.log`) | `%LOCALAPPDATA%\torrent-manager\state` |
| Default downloads | `%USERPROFILE%\Downloads\torrents` |

Override the config and state locations with the `TM_CONFIG_DIR` and
`TM_STATE_DIR` environment variables. If startup fails, the traceback is
written to `%LOCALAPPDATA%\torrent-manager\state\error.log`.

## Troubleshooting

- **`aria2c` not found**: the app falls back to bundled `bin\aria2c.exe` if
  present, then to `PATH`. Recheck step 2 and open a fresh terminal after
  editing `PATH`.
- **Port already in use**: start with `--port 8081`.
- **`Activate.ps1 cannot be loaded`**: use the execution-policy bypass in step
  3, or call `.\.venv\Scripts\python.exe` directly.
- **Slow downloads**: check port forwarding and the performance preset under
  Settings, then Performance.

To build a standalone `.exe` instead of running from source, see the Windows
section under Packaging in the main [README](../README.md).
