from flask import Flask, jsonify, request, send_from_directory

from keithley3706 import ChannelValidationError, Keithley3706A, format_channel_list


app = Flask(__name__, static_folder="static", static_url_path="")
instrument = Keithley3706A()


def json_error(message, status_code):
    return jsonify({"success": False, "error": str(message)}), status_code


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/connect", methods=["POST"])
def connect():
    data = request.get_json(silent=True) or {}
    try:
        identity = instrument.connect(
            resource=data.get("resource"),
            address=data.get("address"),
        )
    except Exception as exc:
        return json_error(exc, 500)
    return jsonify({"success": True, "identity": identity})


@app.route("/api/disconnect", methods=["POST"])
def disconnect():
    instrument.disconnect()
    return jsonify({"success": True})


@app.route("/api/status", methods=["GET"])
def status():
    if not instrument.connected:
        return jsonify({"connected": False})
    try:
        return jsonify({
            "connected": True,
            "identity": instrument.identity(),
            "closed_channels": instrument.get_closed_channels(),
        })
    except Exception as exc:
        return jsonify({"connected": False, "error": str(exc)})


@app.route("/api/channels/close", methods=["POST"])
def close_channels():
    data = request.get_json(silent=True) or {}
    try:
        channels = format_channel_list(data.get("channels"))
        closed = instrument.close_channels(channels)
    except ChannelValidationError as exc:
        return json_error(exc, 400)
    except Exception as exc:
        return json_error(exc, 500)
    return jsonify({"success": True, "closed_channels": closed})


@app.route("/api/channels/open", methods=["POST"])
def open_channels():
    data = request.get_json(silent=True) or {}
    try:
        channels = format_channel_list(data.get("channels"))
        closed = instrument.open_channels(channels)
    except ChannelValidationError as exc:
        return json_error(exc, 400)
    except Exception as exc:
        return json_error(exc, 500)
    return jsonify({"success": True, "closed_channels": closed})


@app.route("/api/channels/openall", methods=["POST"])
def open_all_channels():
    try:
        closed = instrument.open_all()
    except Exception as exc:
        return json_error(exc, 500)
    return jsonify({"success": True, "closed_channels": closed})


@app.route("/api/command", methods=["POST"])
def command():
    data = request.get_json(silent=True) or {}
    raw_command = str(data.get("command", "")).strip()
    mode = str(data.get("mode", "query")).strip().lower()
    if not raw_command:
        return json_error("No command specified", 400)

    try:
        if mode == "write":
            instrument.write_raw(raw_command)
            return jsonify({"success": True})
        result = instrument.query_expression(raw_command)
    except Exception as exc:
        return json_error(exc, 500)
    return jsonify({"success": True, "result": result})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
