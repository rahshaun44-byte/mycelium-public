#!/usr/bin/env bash
# Sync QuantumFlex 5D Wallpaper to Google Pixel 11 Pro via USB MTP
set -euo pipefail

WALLPAPER_SRC="/home/quant/Pictures/Wallpapers/quantumflex_pixel_5d.jpg"
GVFS_DIR="/run/user/$(id -u)/gvfs"

echo "=== QuantumFlex Pixel Wallpaper Sync ==="

if [ ! -f "$WALLPAPER_SRC" ]; then
    echo "[-] Error: Source wallpaper not found at $WALLPAPER_SRC" >&2
    exit 1
fi

PIXEL_MTP=$(find "$GVFS_DIR" -maxdepth 1 -name "mtp:host=Google_Pixel*" 2>/dev/null | head -n 1)

if [ -z "$PIXEL_MTP" ]; then
    echo "[!] Pixel 11 Pro is not currently mounted via USB MTP."
    echo "[*] Please unlock your Pixel, plug in the USB cable, and ensure USB mode is set to 'File Transfer / Android Auto'."
    echo "[*] Alternatively, view the wallpaper directly at http://100.64.1.31:8089/quantumflex_pixel_5d.jpg over Tailscale."
    exit 0
fi

DEST_DIR="$PIXEL_MTP/Internal shared storage/Pictures/Wallpapers"
mkdir -p "$DEST_DIR"
cp "$WALLPAPER_SRC" "$DEST_DIR/quantumflex_pixel_5d.jpg"
mkdir -p "$PIXEL_MTP/Internal shared storage/Download"
cp "$WALLPAPER_SRC" "$PIXEL_MTP/Internal shared storage/Download/quantumflex_pixel_5d.jpg"

echo "[+] Successfully copied QuantumFlex 5D Wallpaper to Pixel 11 Pro:"
echo "    -> $DEST_DIR/quantumflex_pixel_5d.jpg"
echo "    -> $PIXEL_MTP/Internal shared storage/Download/quantumflex_pixel_5d.jpg"
echo "[*] Open Settings > Wallpaper & style on your Pixel to apply the Cinematic 5D effect!"
