#!/usr/bin/env bash
# Bind sshd to loopback + this node's Tailscale IPv4 only.
# Removes 0.0.0.0:22 and [::]:22. Requires sudo.
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run: sudo $0"
  exit 1
fi

TS_IP="$(tailscale ip -4)"
if [[ -z "${TS_IP}" ]]; then
  echo "Could not read Tailscale IPv4 address"
  exit 1
fi

cat > /etc/ssh/sshd_config.d/99-no-wildcard-bind.conf << CFG
# Restrict sshd off 0.0.0.0 / [::]. Loopback + Tailscale only.
ListenAddress 127.0.0.1
ListenAddress ${TS_IP}
CFG

sshd -t
systemctl reload sshd
echo "sshd now listening on:"
ss -lnt | awk '/:22 / {print $4}'
