import unittest

from keithley2400 import Keithley2400


class FakeVisaDevice:
    def __init__(self):
        self.commands = []
        self.timeout = None

    def query(self, command):
        self.commands.append(("query", command))
        if command == "*IDN?":
            return "KEITHLEY INSTRUMENTS INC.,MODEL 2400,123456,1.0"
        if command == ":READ?":
            return "1.000000E-01,1.000000E-02,1.000000E+01"
        return "0"

    def write(self, command):
        self.commands.append(("write", command))

    def close(self):
        self.commands.append(("close_device", None))


class FakeResourceManager:
    def __init__(self):
        self.device = FakeVisaDevice()
        self.resource_name = None

    def open_resource(self, resource_name):
        self.resource_name = resource_name
        return self.device

    def list_resources(self):
        return ("GPIB0::24::INSTR",)

    def close(self):
        pass


class FakePyvisa:
    def __init__(self):
        self.manager = FakeResourceManager()

    def ResourceManager(self):
        return self.manager


class Keithley2400Tests(unittest.TestCase):
    def test_connect_by_address_verifies_identity(self):
        fake_pyvisa = FakePyvisa()
        original_loader = Keithley2400._load_pyvisa
        Keithley2400._load_pyvisa = staticmethod(lambda: fake_pyvisa)
        try:
            meter = Keithley2400()
            identity = meter.connect(address=24)
        finally:
            Keithley2400._load_pyvisa = original_loader

        self.assertIn("MODEL 2400", identity)
        self.assertEqual(fake_pyvisa.manager.resource_name, "GPIB0::24::INSTR")

    def test_configures_voltage_source_and_output(self):
        fake_pyvisa = FakePyvisa()
        original_loader = Keithley2400._load_pyvisa
        Keithley2400._load_pyvisa = staticmethod(lambda: fake_pyvisa)
        try:
            meter = Keithley2400()
            meter.connect(resource="GPIB0::24::INSTR")
            meter.configure_source_voltage(0.1, 0.01)
            meter.output_on()
            meter.output_off()
        finally:
            Keithley2400._load_pyvisa = original_loader

        commands = fake_pyvisa.manager.device.commands
        self.assertIn(("write", ":SOUR:FUNC VOLT"), commands)
        self.assertIn(("write", ":SOUR:VOLT 0.1"), commands)
        self.assertIn(("write", ":SENS:CURR:PROT 0.01"), commands)
        self.assertIn(("write", ":OUTP ON"), commands)
        self.assertIn(("write", ":OUTP OFF"), commands)

    def test_measure_parses_voltage_current_resistance(self):
        fake_pyvisa = FakePyvisa()
        original_loader = Keithley2400._load_pyvisa
        Keithley2400._load_pyvisa = staticmethod(lambda: fake_pyvisa)
        try:
            meter = Keithley2400()
            meter.connect(resource="GPIB0::24::INSTR")
            result = meter.measure()
        finally:
            Keithley2400._load_pyvisa = original_loader

        self.assertEqual(result["voltage"], 0.1)
        self.assertEqual(result["current"], 0.01)
        self.assertEqual(result["resistance"], 10.0)
        self.assertEqual(result["raw"], "1.000000E-01,1.000000E-02,1.000000E+01")


if __name__ == "__main__":
    unittest.main()
