#!/bin/bash
set -e

SERVICE_FILE="/home/quant/.config/systemd/user/school-bot.service"
echo "[*] Installing Decoupled School Bot Service..."

cat << 'UNIT' > "$SERVICE_FILE"
[Unit]
Description=Independent School Assistant Bot (Isolated)
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/mycelium/school-bot
ExecStart=%h/mycelium/school-bot/bot.py
Restart=on-failure
RestartSec=5
Environment=SCHOOL_BOT_PORT=9060

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now school-bot.service

echo "[+] School Bot active and running on port 9060."
