import sys


class Keithley2400:
    def __init__(self, visa_backend=None, timeout_ms=10000):
        self.visa_backend = visa_backend
        self.timeout_ms = timeout_ms
        self.resource_manager = None
        self.device = None
        self.resource_name = None

    @property
    def connected(self):
        return self.device is not None

    def connect(self, resource=None, address=None):
        self.disconnect()
        pyvisa = self._load_pyvisa()
        self.resource_manager = pyvisa.ResourceManager(self.visa_backend) if self.visa_backend else pyvisa.ResourceManager()

        resource_name = resource or self._resource_from_address(address)
        if resource_name is None:
            resource_name = self._find_2400_resource()
            if resource_name is None:
                raise ConnectionError("No Keithley 2400 found on available VISA resources")

        self.device = self.resource_manager.open_resource(resource_name)
        self.device.timeout = self.timeout_ms
        self.resource_name = resource_name
        identity = self.identity()
        if "2400" not in identity:
            self.disconnect()
            raise ConnectionError(f"Connected instrument is not a Keithley 2400: {identity}")
        self.output_off()
        return identity

    def disconnect(self):
        if self.device is not None:
            try:
                self.output_off()
            except Exception:
                pass
            try:
                self.device.close()
            finally:
                self.device = None
        if self.resource_manager is not None:
            try:
                self.resource_manager.close()
            finally:
                self.resource_manager = None
        self.resource_name = None

    def identity(self):
        return self._query("*IDN?").strip()

    def configure_source_voltage(self, voltage, compliance_current):
        self._write(":SOUR:FUNC VOLT")
        self._write(":SOUR:VOLT:MODE FIXED")
        self._write(f":SOUR:VOLT {float(voltage):g}")
        self._write(":SENS:FUNC 'CURR'")
        self._write(f":SENS:CURR:PROT {float(compliance_current):g}")

    def configure_source_current(self, current, compliance_voltage):
        self._write(":SOUR:FUNC CURR")
        self._write(":SOUR:CURR:MODE FIXED")
        self._write(f":SOUR:CURR {float(current):g}")
        self._write(":SENS:FUNC 'VOLT'")
        self._write(f":SENS:VOLT:PROT {float(compliance_voltage):g}")

    def output_on(self):
        self._write(":OUTP ON")

    def output_off(self):
        self._write(":OUTP OFF")

    def measure(self):
        raw = self._query(":READ?").strip()
        parts = [part.strip() for part in raw.split(",")]
        voltage = _parse_float(parts, 0)
        current = _parse_float(parts, 1)
        resistance = _parse_float(parts, 2)
        if resistance is None and voltage is not None and current not in (None, 0.0):
            resistance = abs(voltage / current)
        return {
            "voltage": voltage,
            "current": current,
            "resistance": resistance,
            "raw": raw,
        }

    def _query(self, command):
        self._require_connection()
        return self.device.query(command)

    def _write(self, command):
        self._require_connection()
        self.device.write(command)

    def _require_connection(self):
        if self.device is None:
            raise ConnectionError("Device not connected")

    def _find_2400_resource(self):
        for resource_name in self.resource_manager.list_resources():
            if "GPIB" not in resource_name.upper() and "USB" not in resource_name.upper():
                continue
            try:
                candidate = self.resource_manager.open_resource(resource_name)
                candidate.timeout = self.timeout_ms
                identity = candidate.query("*IDN?")
                candidate.close()
            except Exception:
                continue
            if "2400" in identity:
                return resource_name
        return None

    @staticmethod
    def _resource_from_address(address):
        if address is None or address == "":
            return None
        number = int(address)
        if number < 0 or number > 30:
            raise ValueError("GPIB address must be between 0 and 30")
        return f"GPIB0::{number}::INSTR"

    @staticmethod
    def _load_pyvisa():
        try:
            import pyvisa
        except ImportError as exc:
            raise RuntimeError(
                "PyVISA could not be imported by this Python process. "
                f"Python: {sys.executable}. "
                f"Original error: {exc}. "
                "Install with this exact Python: python -m pip install -r requirements.txt"
            ) from exc
        return pyvisa


def _parse_float(parts, index):
    if len(parts) <= index or parts[index] == "":
        return None
    try:
        return float(parts[index])
    except ValueError:
        return None
