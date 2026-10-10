#!/bin/bash
# pi-app-store: 1
# pi-app-store-category: apps
set -eu
cd -- "$(dirname -- "$0")"
ready() { python3 -c 'import curses;from PIL import Image' >/dev/null 2>&1; }
case "${1:-run}" in
 install)
  if ready; then echo 'Wayglint dependencies already installed.';exit 0;fi
  [ "$(id -u)" -eq 0 ] || { echo 'Install dependencies through the Store with sudo.';exit 1; }
  if command -v apt-get >/dev/null; then apt-get update;apt-get install -y python3 python3-pil ca-certificates
  elif command -v apk >/dev/null; then apk add --no-cache python3 py3-pillow ca-certificates
  elif command -v pacman >/dev/null; then echo 'This can upgrade the entire Arch system; review the package-manager prompt.';pacman -Syu --needed python python-pillow ca-certificates
  else echo 'Install Python 3, curses, Pillow and CA certificates using your distro package manager.';exit 1;fi
  ready ;;
 status) ready ;;
 run) exec python3 wayglint.py ;;
 *) echo 'Use install, status or run';exit 2 ;;
esac
