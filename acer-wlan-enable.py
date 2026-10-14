#!/usr/bin/python
"""Aspire 4755/AR9485 boot workaround confirmed by a temporary EC test."""
import pathlib
import subprocess
import time

def command(*args):
    subprocess.run(args, check=True, timeout=30)

if pathlib.Path('/sys/class/dmi/id/product_name').read_text().strip() != 'Aspire 4755':
    raise SystemExit('Unsupported laptop; EC untouched.')
if pathlib.Path('/sys/class/dmi/id/bios_version').read_text().strip() != 'V2.07':
    raise SystemExit('BIOS differs from verified ACPI mapping; EC untouched.')
pci = pathlib.Path('/sys/bus/pci/devices/0000:03:00.0')
if pci.joinpath('vendor').read_text().strip() != '0x168c' or pci.joinpath('device').read_text().strip() != '0x0032':
    raise SystemExit('Unsupported wireless card; EC untouched.')
if pci.joinpath('subsystem_vendor').read_text().strip() != '0x144d' or pci.joinpath('subsystem_device').read_text().strip() != '0x4105':
    raise SystemExit('Card subsystem differs from tested hardware; EC untouched.')

# Platform radio requests must finish before the direct EC enable.
command('/usr/bin/rfkill', 'unblock', 'wifi')
command('/usr/bin/nmcli', 'radio', 'wifi', 'on')
time.sleep(2)
previously_loaded = pathlib.Path('/sys/module/ec_sys').exists()
try:
    if previously_loaded:
        value = pathlib.Path('/sys/module/ec_sys/parameters/write_support').read_text().strip()
        if value not in ('Y', '1'):
            raise RuntimeError('Existing ec_sys module is read-only; left unchanged.')
    else:
        command('/usr/bin/modprobe', 'ec_sys', 'write_support=1')
    with open('/sys/kernel/debug/ec/ec0/io', 'r+b', buffering=0) as ec:
        ec.seek(0x71)
        original = ec.read(1)
        if len(original) != 1:
            raise RuntimeError('EC byte read failed; no write attempted.')
        target = original[0] | 1
        if target != original[0]:
            ec.seek(0x71)
            if ec.write(bytes([target])) != 1:
                raise RuntimeError('EC WLAN-enable write failed.')
        ec.seek(0x71)
        observed = ec.read(1)
        if len(observed) != 1 or not observed[0] & 1:
            raise RuntimeError('EC WLAN-enable bit did not remain enabled.')
        print(f'Acer WLEN enabled: EC 0x71 0x{original[0]:02x} -> 0x{observed[0]:02x}', flush=True)
    for attempt in range(10):
        time.sleep(1)
        physical = []
        for radio in pathlib.Path('/sys/class/rfkill').glob('rfkill*'):
            if radio.joinpath('name').read_text().strip().startswith('phy'):
                physical.append(radio.joinpath('hard').read_text().strip())
        if physical and all(value == '0' for value in physical):
            print('Wireless hardware block cleared.', flush=True)
            break
    else:
        raise RuntimeError('Radio remained hard-blocked after EC enable.')
finally:
    if not previously_loaded and pathlib.Path('/sys/module/ec_sys').exists():
        command('/usr/bin/modprobe', '-r', 'ec_sys')
