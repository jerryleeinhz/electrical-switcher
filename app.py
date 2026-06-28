"""
Keithley 3706A-S Switch Matrix Controller
Flask backend with PyVISA GPIB control
"""

import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import pyvisa

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

# Global device reference
_device = None
_resource_manager = None


def get_device():
    """Get or initialize the PyVISA device connection."""
    global _device, _resource_manager
    if _device is not None:
        try:
            _device.query("*IDN?")
            return _device
        except Exception:
            _device = None
            _resource_manager = None

    try:
        _resource_manager = pyvisa.ResourceManager("@py")
        resources = _resource_manager.list_resources()
        gpib_resources = [r for r in resources if "GPIB" in r]

        if not gpib_resources:
            return None

        for resource in gpib_resources:
            try:
                inst = _resource_manager.open_resource(resource)
                inst.timeout = 10000
                idn = inst.query("*IDN?")
                if "3706" in idn:
                    _device = inst
                    return _device
            except Exception:
                continue

        return None
    except Exception:
        _resource_manager = None
        return None


def close_device():
    """Close the device connection."""
    global _device, _resource_manager
    if _device is not None:
        try:
            _device.close()
        except Exception:
            pass
        _device = None
    if _resource_manager is not None:
        try:
            _resource_manager.close()
        except Exception:
            pass
        _resource_manager = None


# --- API Routes ---


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/connect", methods=["POST"])
def connect():
    """Connect to the Keithley 3706A via GPIB."""
    data = request.get_json(silent=True) or {}
    gpib_address = data.get("address", None)

    global _device, _resource_manager

    # Close existing connection
    close_device()

    try:
        _resource_manager = pyvisa.ResourceManager("@py")

        if gpib_address is not None:
            resource_string = f"GPIB0::{int(gpib_address)}::INSTR"
            _device = _resource_manager.open_resource(resource_string)
        else:
            # Auto-detect
            _device = get_device()
            if _device is None:
                return jsonify({"success": False, "error": "No Keithley 3706A found on GPIB bus"}), 404

        _device.timeout = 10000
        idn = _device.query("*IDN?")

        return jsonify({"success": True, "identity": idn.strip()})
    except Exception as e:
        close_device()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/disconnect", methods=["POST"])
def disconnect():
    """Disconnect from the device."""
    close_device()
    return jsonify({"success": True})


@app.route("/api/status", methods=["GET"])
def status():
    """Get device connection status and all channel states."""
    dev = get_device()
    if dev is None:
        return jsonify({"connected": False})

    try:
        idn = dev.query("*IDN?").strip()
        closed = dev.query("channel.getclose()").strip()
        return jsonify({
            "connected": True,
            "identity": idn,
            "closed_channels": closed,
        })
    except Exception as e:
        return jsonify({"connected": False, "error": str(e)})


@app.route("/api/channels/close", methods=["POST"])
def close_channels():
    """Close (connect) specified channels."""
    dev = get_device()
    if dev is None:
        return jsonify({"success": False, "error": "Device not connected"}), 400

    data = request.get_json(silent=True) or {}
    channels = data.get("channels", "")

    if not channels:
        return jsonify({"success": False, "error": "No channels specified"}), 400

    try:
        dev.write(f'channel.close("{channels}")')
        # Read any response to clear buffer
        closed = dev.query("channel.getclose()").strip()
        return jsonify({"success": True, "closed_channels": closed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/channels/open", methods=["POST"])
def open_channels():
    """Open (disconnect) specified channels."""
    dev = get_device()
    if dev is None:
        return jsonify({"success": False, "error": "Device not connected"}), 400

    data = request.get_json(silent=True) or {}
    channels = data.get("channels", "")

    if not channels:
        return jsonify({"success": False, "error": "No channels specified"}), 400

    try:
        dev.write(f'channel.open("{channels}")')
        closed = dev.query("channel.getclose()").strip()
        return jsonify({"success": True, "closed_channels": closed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/channels/openall", methods=["POST"])
def open_all_channels():
    """Open (disconnect) all channels."""
    dev = get_device()
    if dev is None:
        return jsonify({"success": False, "error": "Device not connected"}), 400

    try:
        dev.write("channel.openall()")
        closed = dev.query("channel.getclose()").strip()
        return jsonify({"success": True, "closed_channels": closed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/channels/connect", methods=["POST"])
def connect_channels():
    """Connect two channels (for matrix cards)."""
    dev = get_device()
    if dev is None:
        return jsonify({"success": False, "error": "Device not connected"}), 400

    data = request.get_json(silent=True) or {}
    ch1 = data.get("channel1", "")
    ch2 = data.get("channel2", "")

    if not ch1 or not ch2:
        return jsonify({"success": False, "error": "Two channels required"}), 400

    try:
        dev.write(f'channel.connect("{ch1}, {ch2}")')
        closed = dev.query("channel.getclose()").strip()
        return jsonify({"success": True, "closed_channels": closed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/channels/disconnect", methods=["POST"])
def disconnect_channels():
    """Disconnect two channels (for matrix cards)."""
    dev = get_device()
    if dev is None:
        return jsonify({"success": False, "error": "Device not connected"}), 400

    data = request.get_json(silent=True) or {}
    ch1 = data.get("channel1", "")
    ch2 = data.get("channel2", "")

    if not ch1 or not ch2:
        return jsonify({"success": False, "error": "Two channels required"}), 400

    try:
        dev.write(f'channel.disconnect("{ch1}, {ch2}")')
        closed = dev.query("channel.getclose()").strip()
        return jsonify({"success": True, "closed_channels": closed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/command", methods=["POST"])
def send_command():
    """Send a raw TSP command to the device."""
    dev = get_device()
    if dev is None:
        return jsonify({"success": False, "error": "Device not connected"}), 400

    data = request.get_json(silent=True) or {}
    cmd = data.get("command", "")

    if not cmd:
        return jsonify({"success": False, "error": "No command specified"}), 400

    try:
        # Determine if it's a query or write
        if cmd.strip().endswith("?"):
            result = dev.query(cmd).strip()
            return jsonify({"success": True, "result": result})
        else:
            dev.write(cmd)
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
