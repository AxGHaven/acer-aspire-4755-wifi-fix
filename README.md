# Acer Aspire 4755 Wi-Fi hard-block workaround

A small boot and resume workaround for an **Acer Aspire 4755, BIOS V2.07,
Qualcomm Atheros AR9485 (`168c:0032`), running Arch Linux with NetworkManager**.

This is a platform radio-enable workaround, not a replacement Wi-Fi driver.
Keep the kernel's `ath9k` driver installed.

## When this applies

On the tested laptop, `rfkill list all` showed:

```text
acer-wireless: Soft blocked: no, Hard blocked: no
phy0:         Soft blocked: no, Hard blocked: yes
```

Wi-Fi worked in Windows and had worked in the Arch installation environment.
Software unblocking, Fn+F3, unloading `acer_wmi`, reinitializing `ath9k`,
switching to iwd, and testing multiple kernels did not resolve the hard block.

Reading this laptop's ACPI table identified the embedded controller's
**byte `0x71`, bit 0 (`WLEN`)** as its WLAN-enable control. It was off even
though the platform's software switch reported unblocked. Setting that bit
enabled the card and cleared the actual hardware block. Sending additional
radio-enable commands afterward was followed by the block returning; the
successful sequence sends those requests first and sets `WLEN` last.

The card's EEPROM reported `RF Silent = 29`: GPIO 7, active-low. Its GPIO
register agreed with the hardware-disable reading. The underlying reason the
normal Acer control path leaves `WLEN` off is not proven.

## Supported hardware and limits

Only one physical laptop has been tested:

- Acer Aspire 4755, BIOS **V2.07** (2011-07-22).
- AR9485 PCI ID **`168c:0032`**, subsystem **`144d:4105`**.
- Card at PCI address **`0000:03:00.0`**, driver `ath9k`.
- Arch Linux, systemd, Python 3 and NetworkManager.

The helper rejects other models, BIOS versions, PCI IDs and card subsystem IDs. It is not
a universal Acer, AR9485 or Linux fix. Do not remove the guards to try it on
another machine: EC layouts can differ even between similar laptops.

Verified: hardware block cleared, network scanning, a WPA-protected connection,
internet traffic explicitly routed through Wi-Fi, and automatic reconnection
after reboot on kernel `6.18.56-1-lts`.

Suspend/resume caused a later recurrence. Restarting the helper restored the
connection; a resume hook was installed and its event handling tested. A full
subsequent suspend/wake cycle and an hour-long idle test are **not yet verified**.
The regular kernel was restored to `7.2.9`; post-reboot operation on that kernel
has not been independently verified.

## Important: embedded-controller access

This requires root and temporarily loads `ec_sys` with `write_support=1`.
It reads byte `0x71`, sets only bit 0, preserves the other bits, verifies the
readback, and unloads `ec_sys` if it loaded the module itself. It does not flash
firmware, write the Wi-Fi EEPROM, change BIOS settings, blacklist drivers or
store network passwords.

Direct EC writes are hardware-specific and can malfunction; the kernel warns
that recovery may require a reboot or removing power. Use only on the matching
hardware after reviewing the code. The helper enables Wi-Fi at boot and after
waking, including when it was manually disabled before sleeping.

## Install

First check the model, BIOS and card:

```bash
cat /sys/class/dmi/id/product_name
cat /sys/class/dmi/id/bios_version
lspci -nnk -s 03:00.0
rfkill list all
```

Dependencies: `python`, `networkmanager`, `util-linux` (`rfkill`), `kmod`,
systemd and a kernel providing `ec_sys` and debugfs. `wireless-regdb` should
also be installed for normal regulatory data. Keep NetworkManager enabled;
do not run standalone iwd alongside its default wpa_supplicant backend.

```bash
git clone https://github.com/AxGHaven/acer-aspire-4755-wifi-fix.git
cd acer-aspire-4755-wifi-fix
sudo bash install.sh
```

The installer refuses to overwrite existing fix files. It installs:

- `/usr/local/libexec/acer-wlan-enable.py`
- `/etc/systemd/system/acer-wlan-enable.service`
- `/usr/lib/systemd/system-sleep/acer-wlan-resume`

The service runs after NetworkManager starts. The sleep hook queues a restart
of the same service after wake without blocking completion of the sleep hooks.
No timer repeatedly forces the radio on.

Connect through your desktop's Wi-Fi menu, or use the actual interface name
from `nmcli device status`:

```bash
nmcli --ask device wifi connect 'YOUR_SSID' ifname wlan0
```

Enter the password locally. Ensure the saved profile has autoconnect enabled.

## Verify

```bash
systemctl is-enabled acer-wlan-enable.service
systemctl status acer-wlan-enable.service --no-pager
journalctl -b -u acer-wlan-enable.service --no-pager
rfkill list all
nmcli device status
ping -I wlan0 -c 3 1.1.1.1
```

Both WLAN soft and hard blocks should be `no`. An `active (exited)` service
is normal: this is a one-shot hardware setup task, not a background daemon.

Save work before testing reboot or suspend. Allow roughly 15 seconds after
boot or wake for recovery and reconnection. If the block returns, collect the
service journal and `rfkill` output rather than disabling additional drivers.
To rerun the existing fix manually:

```bash
sudo systemctl restart acer-wlan-enable.service
```

## Remove

```bash
sudo bash uninstall.sh
```

This removes the service, helper and resume hook. It leaves the currently
enabled radio and saved network profiles alone. The original hard-block
behavior may return at the next boot or resume.

## Tests

The tests use mocked hardware; they never access your EC or change services.

```bash
python -m unittest discover -s tests -v
python tests/test_resume_hook.py
bash -n install.sh uninstall.sh
systemd-analyze verify acer-wlan-enable.service
```

## References

- [Linux Wireless: ath9k](https://wireless.docs.kernel.org/en/latest/en/users/drivers/ath9k.html)
- [Kernel ath9k rfkill GPIO implementation](https://github.com/torvalds/linux/blob/v6.18/drivers/net/wireless/ath/ath9k/gpio.c)
- [Kernel EEPROM RF-silent definitions](https://github.com/torvalds/linux/blob/v6.18/drivers/net/wireless/ath/ath9k/eeprom.h)
- [Kernel EC debug access implementation](https://github.com/torvalds/linux/blob/v6.18/drivers/acpi/ec_sys.c)

## License

MIT. See [LICENSE](LICENSE).
