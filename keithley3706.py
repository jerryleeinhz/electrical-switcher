import re
import sys


class ChannelValidationError(ValueError):
    pass


CHANNEL_PART_RE = re.compile(r"^\d{4}(?::\d{4})?$")


def format_channel_list(value):
    if value is None:
        raise ChannelValidationError("No channels specified")

    text = str(value).strip()
    if not text:
        raise ChannelValidationError("No channels specified")

    parts = []
    for raw_part in text.split(","):
        part = raw_part.strip()
        if not CHANNEL_PART_RE.fullmatch(part):
            raise ChannelValidationError(f"Invalid channel expression: {part}")
        if ":" in part:
            start_text, end_text = part.split(":", 1)
            if int(start_text) > int(end_text):
                raise ChannelValidationError(f"Invalid channel range: {part}")
        parts.append(part)

    return ",".join(parts)


def tsp_print(expression):
    command = str(expression).strip()
    if command.lower().startswith("print("):
        return command
    return f"print({command})"


def list_visa_resources(visa_backend=None):
    pyvisa = Keithley3706A._load_pyvisa()
    manager = pyvisa.ResourceManager(visa_backend) if visa_backend else pyvisa.ResourceManager()
    try:
        return tuple(manager.list_resources())
    finally:
        manager.close()


def probe_visa_resources(visa_backend=None, timeout_ms=3000):
    pyvisa = Keithley3706A._load_pyvisa()
    manager = pyvisa.ResourceManager(visa_backend) if visa_backend else pyvisa.ResourceManager()
    results = []
    try:
        for resource_name in manager.list_resources():
            identity = ""
            error = ""
            try:
                device = manager.open_resource(resource_name)
                device.timeout = timeout_ms
                identity = device.query("*IDN?").strip()
                device.close()
            except Exception as exc:
                error = str(exc)
            results.append({"resource": resource_name, "identity": identity, "error": error})
    finally:
        manager.close()
    return results


def find_resource_by_idn(keyword, visa_backend=None, timeout_ms=3000):
    needle = str(keyword).upper()
    for result in probe_visa_resources(visa_backend=visa_backend, timeout_ms=timeout_ms):
        if needle in result["identity"].upper():
            return result["resource"]
    return None


class Keithley3706A:
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
            resource_name = self._find_3706_resource()
            if resource_name is None:
                raise ConnectionError("No Keithley 3706A-S found on available VISA resources")

        self.device = self.resource_manager.open_resource(resource_name)
        self.device.timeout = self.timeout_ms
        self.resource_name = resource_name
        identity = self.identity()
        if "3706" not in identity:
            self.disconnect()
            raise ConnectionError(f"Connected instrument is not a Keithley 3706A-S: {identity}")
        return identity

    def disconnect(self):
        if self.device is not None:
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

    def get_closed_channels(self):
        return self.query_expression('channel.getclose("allslots")')

    def close_channels(self, channels):
        channel_list = format_channel_list(channels)
        self._write(f'channel.close("{channel_list}")')
        return self.get_closed_channels()

    def open_channels(self, channels):
        channel_list = format_channel_list(channels)
        self._write(f'channel.open("{channel_list}")')
        return self.get_closed_channels()

    def open_all(self):
        self._write('channel.open("allslots")')
        return self.get_closed_channels()

    def query_expression(self, expression):
        return self._query(tsp_print(expression)).strip()

    def write_raw(self, command):
        text = str(command).strip()
        if not text:
            raise ValueError("No command specified")
        self._write(text)

    def _query(self, command):
        self._require_connection()
        return self.device.query(command)

    def _write(self, command):
        self._require_connection()
        self.device.write(command)

    def _require_connection(self):
        if self.device is None:
            raise ConnectionError("Device not connected")

    def _find_3706_resource(self):
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
            if "3706" in identity:
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
                "PyVISA could not be imported by this Flask process. "
                f"Python: {sys.executable}. "
                f"Original error: {exc}. "
                "Install with this exact Python: python -m pip install -r requirements.txt"
            ) from exc
        return pyvisa
