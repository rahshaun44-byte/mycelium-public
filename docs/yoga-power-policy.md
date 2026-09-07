# Yoga Node Power & Sleep Policy

## Why Lid Suspend is Disabled
The QuantumFlex node must operate as an autonomous background daemon. Standard laptop configurations suspend execution when the lid is closed, terminating active `SSL_read` loops and dropping external network traffic. We have enforced `HandleLidSwitch=ignore` at the systemd-logind level to guarantee process continuity.

## When it Applies
This policy applies permanently while the host is configured as a dedicated node. It applies on both AC power and Battery power.

## How to Revert It
To restore normal laptop behavior, remove the `ignore` directives from `/etc/systemd/logind.conf` and restart the logind daemon:
```bash
sudo sed -i "/HandleLidSwitch=ignore/d" /etc/systemd/logind.conf
sudo sed -i "/HandleLidSwitchExternalPower=ignore/d" /etc/systemd/logind.conf
sudo sed -i "/HandleLidSwitchDocked=ignore/d" /etc/systemd/logind.conf
sudo systemctl restart systemd-logind
```
