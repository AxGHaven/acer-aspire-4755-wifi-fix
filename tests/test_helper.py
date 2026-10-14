import contextlib
import io
from pathlib import Path
import runpy
import subprocess
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parent.parent / 'acer-wlan-enable.py'
PCI = '/sys/bus/pci/devices/0000:03:00.0'


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.values = {
            '/sys/class/dmi/id/product_name': 'Aspire 4755',
            '/sys/class/dmi/id/bios_version': 'V2.07',
            PCI + '/vendor': '0x168c', PCI + '/device': '0x0032',
            PCI + '/subsystem_vendor': '0x144d', PCI + '/subsystem_device': '0x4105',
            '/sys/module/ec_sys/parameters/write_support': 'Y',
            '/sys/class/rfkill/rfkill2/name': 'phy0',
            '/sys/class/rfkill/rfkill2/hard': '0',
        }
        self.events = []
        self.loaded = False
        self.ec_data = bytearray(256)
        self.ec_data[0x71] = 0xA2

    def execute(self):
        case = self
        real_open = open

        class FakePath:
            def __init__(self, name):
                self.name = str(name)

            def read_text(self):
                return case.values[self.name]

            def joinpath(self, name):
                return FakePath(self.name + '/' + name)

            def exists(self):
                return case.loaded

            def glob(self, pattern):
                return [FakePath('/sys/class/rfkill/rfkill2')]

        class FakeEC(io.BytesIO):
            def write(self, data):
                case.events.append(('EC-write', self.tell(), bytes(data)))
                return super().write(data)

            def close(self):
                case.ec_data[:] = self.getvalue()

        def fake_open(name, *args, **kwargs):
            if str(name) == '/sys/kernel/debug/ec/ec0/io':
                return FakeEC(case.ec_data)
            return real_open(name, *args, **kwargs)

        def fake_run(args, **kwargs):
            case.events.append(tuple(args))
            if args == ('/usr/bin/modprobe', 'ec_sys', 'write_support=1'):
                case.loaded = True
            elif args == ('/usr/bin/modprobe', '-r', 'ec_sys'):
                case.loaded = False
            return subprocess.CompletedProcess(args, 0)

        with patch('pathlib.Path', FakePath), patch('builtins.open', fake_open), \
                patch('subprocess.run', fake_run), patch('time.sleep'), \
                contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(SCRIPT), run_name='__main__')

    def test_preserves_other_ec_bits_and_orders_radio_requests(self):
        self.execute()
        self.assertEqual(self.ec_data[0x71], 0xA3)
        write_index = next(i for i, event in enumerate(self.events) if event[0] == 'EC-write')
        self.assertLess(self.events.index(('/usr/bin/rfkill', 'unblock', 'wifi')), write_index)
        self.assertLess(self.events.index(('/usr/bin/nmcli', 'radio', 'wifi', 'on')), write_index)
        self.assertFalse(self.loaded, 'Temporary EC write access must be unloaded.')

    def test_wrong_bios_and_card_are_rejected_without_side_effects(self):
        for field in ('/sys/class/dmi/id/bios_version', PCI + '/subsystem_device'):
            with self.subTest(field=field):
                original = self.values[field]
                self.values[field] = 'unsupported'
                with self.assertRaises(SystemExit):
                    self.execute()
                self.assertEqual(self.events, [])
                self.assertEqual(self.ec_data[0x71], 0xA2)
                self.values[field] = original

    def test_existing_read_only_ec_module_is_left_unchanged(self):
        self.loaded = True
        self.values['/sys/module/ec_sys/parameters/write_support'] = 'N'
        with self.assertRaises(RuntimeError):
            self.execute()
        self.assertTrue(self.loaded)
        self.assertFalse(any(event[0] == 'EC-write' for event in self.events))

    def test_hardware_block_timeout_unloads_temporary_module(self):
        self.values['/sys/class/rfkill/rfkill2/hard'] = '1'
        with self.assertRaises(RuntimeError):
            self.execute()
        self.assertFalse(self.loaded)


if __name__ == '__main__':
    unittest.main()
