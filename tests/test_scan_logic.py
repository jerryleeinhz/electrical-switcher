import unittest

from scan_logic import classify_continuity, generate_crossbar_pairs, parse_manual_pairs, run_continuity_scan


class PairGenerationTests(unittest.TestCase):
    def test_generates_crossbar_pairs_inclusive(self):
        self.assertEqual(
            generate_crossbar_pairs(1001, 1002, 1031, 1032),
            [("1001", "1031"), ("1001", "1032"), ("1002", "1031"), ("1002", "1032")],
        )

    def test_rejects_inverted_range(self):
        with self.assertRaises(ValueError):
            generate_crossbar_pairs(1002, 1001, 1031, 1032)

    def test_parses_manual_pairs_and_skips_blank_lines(self):
        self.assertEqual(
            parse_manual_pairs("1001,1031\n\n1002, 1032"),
            [("1001", "1031"), ("1002", "1032")],
        )

    def test_rejects_invalid_manual_pair_text(self):
        with self.assertRaises(ValueError):
            parse_manual_pairs('1001"); channel.openall(); --,1031')


class ClassificationTests(unittest.TestCase):
    def test_classifies_pass_when_resistance_is_at_or_below_threshold(self):
        self.assertEqual(classify_continuity(10.0, 10.0), "PASS")

    def test_classifies_open_when_resistance_is_missing_or_high(self):
        self.assertEqual(classify_continuity(None, 10.0), "OPEN")
        self.assertEqual(classify_continuity(10.1, 10.0), "OPEN")


class FakeSwitch:
    def __init__(self):
        self.calls = []

    def open_all(self):
        self.calls.append("open_all")
        return ""

    def close_channels(self, channels):
        self.calls.append(("close_channels", channels))
        return channels


class FakeMeter:
    def __init__(self, result=None, fail=False):
        self.calls = []
        self.result = result or {"voltage": 0.1, "current": 0.01, "resistance": 10.0, "raw": "0.1,0.01,10"}
        self.fail = fail

    def output_off(self):
        self.calls.append("output_off")

    def output_on(self):
        self.calls.append("output_on")

    def measure(self):
        self.calls.append("measure")
        if self.fail:
            raise RuntimeError("measurement failed")
        return self.result


class ScanOrchestrationTests(unittest.TestCase):
    def test_runs_safe_sequence_for_each_pair(self):
        switch = FakeSwitch()
        meter = FakeMeter()

        rows = run_continuity_scan(
            switch=switch,
            meter=meter,
            pairs=[("1001", "1031")],
            source_mode="voltage",
            source_level=0.1,
            compliance=0.01,
            settle_time_s=0,
            resistance_threshold=20.0,
            switch_idn="3706 IDN",
            meter_idn="2400 IDN",
        )

        self.assertEqual(switch.calls, ["open_all", ("close_channels", "1001,1031"), "open_all"])
        self.assertEqual(meter.calls, ["output_off", "output_on", "measure", "output_off"])
        self.assertEqual(rows[0]["status"], "PASS")
        self.assertEqual(rows[0]["switch_idn"], "3706 IDN")
        self.assertEqual(rows[0]["meter_idn"], "2400 IDN")

    def test_attempts_to_make_instruments_safe_after_measurement_error(self):
        switch = FakeSwitch()
        meter = FakeMeter(fail=True)

        rows = run_continuity_scan(
            switch=switch,
            meter=meter,
            pairs=[("1001", "1031")],
            source_mode="current",
            source_level=0.001,
            compliance=1.0,
            settle_time_s=0,
            resistance_threshold=20.0,
        )

        self.assertIn("output_off", meter.calls)
        self.assertEqual(switch.calls[-1], "open_all")
        self.assertEqual(rows[0]["status"], "ERROR")
        self.assertIn("measurement failed", rows[0]["error"])


if __name__ == "__main__":
    unittest.main()
