import unittest

import app


class FakeInstrument:
    def __init__(self):
        self.commands = []
        self.connected = False

    def connect(self, resource=None, address=None):
        self.connected = True
        return "KEITHLEY INSTRUMENTS,MODEL 3706A-S,123456,1.0"

    def disconnect(self):
        self.connected = False

    def identity(self):
        return "KEITHLEY INSTRUMENTS,MODEL 3706A-S,123456,1.0"

    def get_closed_channels(self):
        return "1001,1003:1004"

    def close_channels(self, channels):
        self.commands.append(("close", channels))
        return channels

    def open_channels(self, channels):
        self.commands.append(("open", channels))
        return ""

    def open_all(self):
        self.commands.append(("open_all", None))
        return ""

    def query_expression(self, expression):
        self.commands.append(("query", expression))
        return "3730"

    def write_raw(self, command):
        self.commands.append(("write", command))


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeInstrument()
        app.instrument = self.fake
        app.app.config["TESTING"] = True
        self.client = app.app.test_client()

    def test_connect_by_address(self):
        response = self.client.post("/api/connect", json={"address": 18})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    def test_close_channels_validates_and_normalizes_input(self):
        self.client.post("/api/connect", json={"address": 18})
        response = self.client.post("/api/channels/close", json={"channels": "1001, 1002:1003"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.fake.commands[-1], ("close", "1001,1002:1003"))

    def test_close_channels_rejects_unsafe_text(self):
        self.client.post("/api/connect", json={"address": 18})
        response = self.client.post(
            "/api/channels/close",
            json={"channels": '1001"); channel.openall(); --'},
        )
        self.assertEqual(response.status_code, 400)

    def test_query_command_supports_tsp_expression_without_question_mark(self):
        self.client.post("/api/connect", json={"address": 18})
        response = self.client.post("/api/command", json={"mode": "query", "command": "slot.cardtype[1]"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["result"], "3730")
        self.assertEqual(self.fake.commands[-1], ("query", "slot.cardtype[1]"))


if __name__ == "__main__":
    unittest.main()
