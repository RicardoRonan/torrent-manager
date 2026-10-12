#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(dirname "$here")"
src="$root/dist/TorrentManager"
dest="${1:-$HOME/.local/opt/torrent-manager}"

if [ ! -x "$src/TorrentManager" ]; then
  echo "Build first:  .venv/bin/pyinstaller --noconfirm packaging/torrent-manager.spec"
  exit 1
fi

mkdir -p "$dest"
cp -r "$src/." "$dest/"
chmod +x "$dest/TorrentManager"

# Register the launcher and the magnet: handler (writes ~/.local/share/applications)
"$dest/TorrentManager" --install-desktop

mkdir -p "$HOME/.local/bin"
ln -sf "$dest/TorrentManager" "$HOME/.local/bin/torrent-manager"

echo
echo "Installed to: $dest"
echo "Launcher:     http://127.0.0.1:8080  (and 'torrent-manager' on PATH if ~/.local/bin is)"
echo "magnet handler: $(xdg-mime query default x-scheme-handler/magnet || echo '(not set)')"
