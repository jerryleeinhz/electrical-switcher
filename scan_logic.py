import time
from datetime import datetime

from keithley3706 import format_channel_list


def generate_crossbar_pairs(a_start, a_end, b_start, b_end):
    a_start = int(a_start)
    a_end = int(a_end)
    b_start = int(b_start)
    b_end = int(b_end)
    if a_start > a_end:
        raise ValueError("A range start must be less than or equal to A range end")
    if b_start > b_end:
        raise ValueError("B range start must be less than or equal to B range end")
    return [
        (str(channel_a), str(channel_b))
        for channel_a in range(a_start, a_end + 1)
        for channel_b in range(b_start, b_end + 1)
    ]


def parse_manual_pairs(text):
    pairs = []
    for line_number, raw_line in enumerate(str(text).splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 2:
            raise ValueError(f"Line {line_number} must contain exactly two channels separated by a comma")
        channel_a = format_channel_list(parts[0])
        channel_b = format_channel_list(parts[1])
        pairs.append((channel_a, channel_b))
    return pairs


def classify_continuity(resistance, threshold):
    if resistance is None:
        return "OPEN"
    try:
        return "PASS" if float(resistance) <= float(threshold) else "OPEN"
    except (TypeError, ValueError):
        return "OPEN"


def run_continuity_scan(
    switch,
    meter,
    pairs,
    source_mode,
    source_level,
    compliance,
    settle_time_s,
    resistance_threshold,
    switch_idn="",
    meter_idn="",
    stop_on_error=False,
):
    rows = []
    for channel_a, channel_b in pairs:
        row = _base_row(
            channel_a=channel_a,
            channel_b=channel_b,
            source_mode=source_mode,
            source_level=source_level,
            compliance=compliance,
            settle_time_s=settle_time_s,
            resistance_threshold=resistance_threshold,
            switch_idn=switch_idn,
            meter_idn=meter_idn,
        )
        try:
            meter.output_off()
            switch.open_all()
            switch.close_channels(format_channel_list(f"{channel_a},{channel_b}"))
            if settle_time_s:
                time.sleep(float(settle_time_s))
            meter.output_on()
            measurement = meter.measure()
            row.update(
                {
                    "voltage": measurement.get("voltage"),
                    "current": measurement.get("current"),
                    "resistance": measurement.get("resistance"),
                    "raw": measurement.get("raw", ""),
                }
            )
            row["status"] = classify_continuity(row["resistance"], resistance_threshold)
        except Exception as exc:
            row["status"] = "ERROR"
            row["error"] = str(exc)
        finally:
            _attempt_safe_shutdown(meter, switch, row)
        rows.append(row)
        if stop_on_error and row["status"] == "ERROR":
            break
    return rows


def _base_row(
    channel_a,
    channel_b,
    source_mode,
    source_level,
    compliance,
    settle_time_s,
    resistance_threshold,
    switch_idn,
    meter_idn,
):
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "switch_idn": switch_idn,
        "meter_idn": meter_idn,
        "source_mode": source_mode,
        "source_level": source_level,
        "compliance": compliance,
        "settle_time_s": settle_time_s,
        "resistance_threshold": resistance_threshold,
        "pair": f"{channel_a},{channel_b}",
        "channel_a": channel_a,
        "channel_b": channel_b,
        "voltage": None,
        "current": None,
        "resistance": None,
        "raw": "",
        "status": "OPEN",
        "error": "",
    }


def _attempt_safe_shutdown(meter, switch, row):
    try:
        meter.output_off()
    except Exception as exc:
        row["error"] = _append_error(row["error"], f"output_off failed: {exc}")
    try:
        switch.open_all()
    except Exception as exc:
        row["error"] = _append_error(row["error"], f"open_all failed: {exc}")


def _append_error(existing, message):
    return f"{existing}; {message}" if existing else message
