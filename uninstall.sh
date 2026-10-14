#!/bin/bash
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then
    echo 'Run: sudo bash uninstall.sh' >&2
    exit 1
fi
rm -f /usr/lib/systemd/system-sleep/acer-wlan-resume
systemctl disable --now acer-wlan-enable.service
rm -f /etc/systemd/system/acer-wlan-enable.service
rm -f /usr/local/libexec/acer-wlan-enable.py
systemctl daemon-reload
echo 'Removed. Current radio state and saved Wi-Fi profiles are unchanged.'
