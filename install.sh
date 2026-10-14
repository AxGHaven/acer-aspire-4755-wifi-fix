#!/bin/bash
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then
    echo 'Run: sudo bash install.sh' >&2
    exit 1
fi
src=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
helper=/usr/local/libexec/acer-wlan-enable.py
unit=/etc/systemd/system/acer-wlan-enable.service
hook=/usr/lib/systemd/system-sleep/acer-wlan-resume
for command in python nmcli rfkill modprobe systemctl install grep; do
    command -v "$command" >/dev/null || { echo "Missing command: $command" >&2; exit 1; }
done
for destination in "$helper" "$unit" "$hook"; do
    if [ -e "$destination" ]; then
        echo "Already exists: $destination. Refusing to overwrite." >&2
        exit 1
    fi
done
install -d -m 755 /usr/local/libexec /usr/lib/systemd/system-sleep
install -m 755 "$src/acer-wlan-enable.py" "$helper"
install -m 644 "$src/acer-wlan-enable.service" "$unit"
install -m 755 "$src/acer-wlan-resume" "$hook"
systemctl daemon-reload
if ! systemctl enable --now acer-wlan-enable.service; then
    systemctl disable --now acer-wlan-enable.service || true
    rm -f "$helper" "$unit" "$hook"
    systemctl daemon-reload
    echo 'Helper failed; its installation was removed. Inspect the journal.' >&2
    exit 1
fi
rfkill list all
nmcli device status
echo 'Installed for boot and resume. Connect using your normal Wi-Fi menu.'
