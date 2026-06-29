import unittest

from keithley3706 import ChannelValidationError, Keithley3706A, format_channel_list, tsp_print


class ChannelFormattingTests(unittest.TestCase):
    def test_accepts_single_channel(self):
        self.assertEqual(format_channel_list("1001"), "1001")

    def test_accepts_comma_list_and_range(self):
        self.assertEqual(format_channel_list("1001, 1002:1004"), "1001,1002:1004")

    def test_rejects_inverted_range(self):
        with self.assertRaises(ChannelValidationError):
            format_channel_list("1005:1001")

    def test_rejects_tsp_injection_text(self):
        with self.assertRaises(ChannelValidationError):
            format_channel_list('1001"); channel.openall(); --')


class TspFormattingTests(unittest.TestCase):
    def test_wraps_expression_in_print(self):
        self.assertEqual(tsp_print("channel.getclose()"), "print(channel.getclose())")

    def test_does_not_double_wrap_print(self):
        self.assertEqual(tsp_print("print(channel.getclose())"), "print(channel.getclose())")


class FakeVisaDevice:
    def __init__(self):
        self.commands = []
        self.timeout = None

    def query(self, command):
        self.commands.append(("query", command))
        if command == "*IDN?":
            return "KEITHLEY INSTRUMENTS,MODEL 3706A-S,123456,1.0"
        if command == 'print(channel.getclose("allslots"))':
            return "1001"
        return "ok"

    def write(self, command):
        self.commands.append(("write", command))

    def close(self):
        self.commands.append(("close_device", None))


class FakeResourceManager:
    def __init__(self):
        self.device = FakeVisaDevice()

    def open_resource(self, resource_name):
        self.resource_name = resource_name
        return self.device

    def close(self):
        pass


class FakePyvisa:
    def __init__(self):
        self.manager = FakeResourceManager()

    def ResourceManager(self):
        return self.manager


class KeithleyCommandTests(unittest.TestCase):
    def test_close_channels_sends_normalized_channel_close_command(self):
        fake_pyvisa = FakePyvisa()
        original_loader = Keithley3706A._load_pyvisa
        Keithley3706A._load_pyvisa = staticmethod(lambda: fake_pyvisa)
        try:
            driver = Keithley3706A()
            driver.connect(address=18)
            driver.close_channels("1001, 1002")
        finally:
            Keithley3706A._load_pyvisa = original_loader

        self.assertIn(("write", 'channel.close("1001,1002")'), fake_pyvisa.manager.device.commands)
        self.assertIn(("query", 'print(channel.getclose("allslots"))'), fake_pyvisa.manager.device.commands)

    def test_open_all_opens_allslots_and_queries_closed_channels(self):
        fake_pyvisa = FakePyvisa()
        original_loader = Keithley3706A._load_pyvisa
        Keithley3706A._load_pyvisa = staticmethod(lambda: fake_pyvisa)
        try:
            driver = Keithley3706A()
            driver.connect(address=18)
            driver.open_all()
        finally:
            Keithley3706A._load_pyvisa = original_loader

        self.assertIn(("write", 'channel.open("allslots")'), fake_pyvisa.manager.device.commands)
        self.assertIn(("query", 'print(channel.getclose("allslots"))'), fake_pyvisa.manager.device.commands)


if __name__ == "__main__":
    unittest.main()
