#!/usr/bin/env python3
"""Read-only streaming audit of SavvyCAN classic-CAN CSV captures.

NO payloads/identifiers are exported; this is NOT a replay/ECU profile creator.
The analysis never changes vehicle state or J2534 diagnostic behavior.
"""

import argparse
from collections import Counter, defaultdict
import csv
import json
import re
from pathlib import Path
from typing import TextIO

HEX_ID = re.compile(r"(?:0[xX])?[0-9a-fA-F]{1,8}\Z")
HEX_BYTE = re.compile(r"[0-9a-fA-F]{2}\Z")
FIELDS = ("Time Stamp", "ID", "Extended", "Bus", "LEN")


class CaptureError(ValueError):
    pass


def _frame(row):
    """Return (bus, id, extended, time_us, dlc, direction), or a reason.

    SavvyCAN 'Time Stamp' is in microseconds in the two reviewed captures.
    Hex bytes are checked but never stored in the report.
    """
    try:
        ts = int(row["Time Stamp"])
        if ts < 0:
            return None, "invalid_timestamp"
        bus = int(row["Bus"])
        if bus < 0 or bus > 255:
            return None, "invalid_bus"
        id_text = (row["ID"] or "").strip()
        if not HEX_ID.fullmatch(id_text):
            return None, "invalid_can_id"
        arb_id = int(id_text, 16)
        extended_text = (row["Extended"] or "").strip().lower()
        if extended_text not in ("true", "false", "1", "0"):
            return None, "invalid_extended_flag"
        extended = extended_text in ("true", "1")
        if arb_id > (0x1FFFFFFF if extended else 0x7FF):
            return None, "out_of_range_can_id"
        dlc = int(row["LEN"])
        if not 0 <= dlc <= 8:
            return None, "non_classic_can_length"
        for index in range(1, dlc + 1):
            value = (row.get(f"D{index}") or "").strip()
            if not HEX_BYTE.fullmatch(value):
                return None, "malformed_payload_byte"
        direction = (row.get("Dir") or "unknown").strip().lower()
        return (bus, arb_id, extended, ts, dlc, direction), None
    except (KeyError, TypeError, ValueError):
        return None, "malformed_row"


def analyze(stream: TextIO, *, source_model: str, source_model_year: int,
            target_model: str = "XC90 V8", target_model_year: int = 2009,
            bus_speeds: dict | None = None, gap_threshold_ms: int = 5000):
    """Summarize capture metadata, not raw CAN payloads or vehicle identifiers."""
    if source_model_year < 1980 or source_model_year > 2100:
        raise CaptureError("source_model_year is outside supported range")
    if gap_threshold_ms < 1:
        raise CaptureError("gap_threshold_ms must be >= 1")
    if not source_model.strip():
        raise CaptureError("source_model is required")
    reader = csv.DictReader(stream)
    if reader.fieldnames is None or not set(FIELDS).issubset(reader.fieldnames):
        raise CaptureError("CSV requires Time Stamp,ID,Extended,Bus,LEN headers")
    errors = Counter()
    bus_stats = defaultdict(lambda: {"accepted": 0, "directions": Counter(),
                                     "observed_ext": 0, "observed_std": 0,
                                     "max_gap_ms": 0.0, "gaps_over_threshold": 0})
    id_stats = {}
    last_global = {}
    accepted = 0
    total = 0
    for line_index, row in enumerate(reader, start=2):
        total += 1
        result, err = _frame(row)
        if err:
            errors[err] += 1
            continue
        bus, arb_id, ext, ts, dlc, direction = result
        # Extended vs standard and bus are part of frame identity. Never
        # deduplicate solely on arbitration ID.
        key = (bus, arb_id, ext)
        item = id_stats.setdefault(key, {"count": 0, "last_us": None,
                                          "period_count": 0, "sum_delta_us": 0,
                                          "min_delta_us": None, "max_delta_us": None})
        prev = item["last_us"]
        if prev is not None and ts < prev:
            errors["out_of_order_timestamp"] += 1
            # Do not let one regressing timestamp distort the period distribution.
            continue
        item["count"] += 1
        if prev is not None:
            delta = ts - prev
            item["period_count"] += 1
            item["sum_delta_us"] += delta
            item["min_delta_us"] = delta if item["min_delta_us"] is None else min(item["min_delta_us"], delta)
            item["max_delta_us"] = delta if item["max_delta_us"] is None else max(item["max_delta_us"], delta)
        item["last_us"] = ts
        s = bus_stats[bus]
        s["accepted"] += 1
        s["directions"][direction] += 1
        s["observed_ext" if ext else "observed_std"] += 1
        last = last_global.get(bus)
        if last is not None and ts > last:
            gap_ms = (ts - last) / 1000.0
            s["max_gap_ms"] = max(s["max_gap_ms"], gap_ms)
            if gap_ms >= gap_threshold_ms:
                s["gaps_over_threshold"] += 1
        last_global[bus] = max(ts, last if last is not None else ts)
        accepted += 1
    if accepted == 0:
        errors["no_valid_frames"] += 1
    ids = []
    for (bus, can_id, ext), s in sorted(id_stats.items()):
        if s["count"] == 0:
            continue
        n = s["period_count"]
        ids.append({"bus": bus, "can_id": f"0x{can_id:08X}" if ext else f"0x{can_id:03X}",
                    "extended": ext, "frame_count": s["count"],
                    "period_samples": n,
                    "mean_period_ms": round(s["sum_delta_us"] / (n * 1000), 3) if n else None,
                    "min_period_ms": round(s["min_delta_us"] / 1000, 3) if n else None,
                    "max_period_ms": round(s["max_delta_us"] / 1000, 3) if n else None})
    buses = []
    for bus, s in sorted(bus_stats.items()):
        buses.append({"bus": bus, "configured_speed_bps": (bus_speeds or {}).get(bus),
                      "frame_count": s["accepted"], "unique_message_ids": sum(x["bus"] == bus for x in ids),
                      "extended_frames": s["observed_ext"], "standard_frames": s["observed_std"],
                      "directions": dict(sorted(s["directions"].items())),
                      "gaps_over_threshold": s["gaps_over_threshold"],
                      "max_observed_gap_ms": round(s["max_gap_ms"], 3)})
    same_identity = source_model.strip().lower() == target_model.strip().lower() and source_model_year == target_model_year
    return {"format": "virtualcar-can-capture-audit-v1", "read_only": True,
            "contains_payload_data": False,
            "source": {"model": source_model, "model_year": source_model_year},
            "target": {"model": target_model, "model_year": target_model_year},
            "compatibility": "identity_match_not_verified" if same_identity else "source_vehicle_differs_from_target",
            "replay_approved": False,
            "notes": ["Reported bitrates are user-declared metadata, not measured by CSV.",
                      "No broadcast frame indicates successful CEM diagnostic normal mode or ignition reference 0x1A04.",
                      "IDs and signal positions may differ by vehicle generation; verification required before replay."],
            "total_csv_rows": total, "valid_frames": accepted,
            "discarded_rows": sum(errors.values()) - errors["no_valid_frames"],
            "errors": dict(sorted(errors.items())), "buses": buses, "ids": ids}


def _speed(value):
    try:
        bus, bps = value.split("=", 1)
        bus_id, speed = int(bus), int(bps)
        if not 0 <= bus_id <= 255 or not 10000 <= speed <= 1000000:
            raise ValueError
        return bus_id, speed
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected bus=bps, e.g. 0=125000 or 1=250000") from exc


def main(argv=None):
    p = argparse.ArgumentParser(description="Read-only classic-CAN metadata audit; never creates a replay profile")
    p.add_argument("csv", type=Path)
    p.add_argument("--source-model", required=True)
    p.add_argument("--source-model-year", required=True, type=int)
    p.add_argument("--target-model", default="XC90 V8")
    p.add_argument("--target-model-year", default=2009, type=int)
    p.add_argument("--bus-speed", type=_speed, action="append", default=[], metavar="BUS=BPS")
    p.add_argument("--gap-threshold-ms", type=int, default=5000)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    speeds = dict(args.bus_speed)
    try:
        if args.csv.resolve() == args.output.resolve():
            p.error("output must not overwrite the source CSV")
        with args.csv.open("r", encoding="utf-8-sig", newline="") as stream:
            report = analyze(stream, source_model=args.source_model,
                             source_model_year=args.source_model_year,
                             target_model=args.target_model,
                             target_model_year=args.target_model_year,
                             bus_speeds=speeds, gap_threshold_ms=args.gap_threshold_ms)
        with args.output.open("x", encoding="utf-8") as out:
            json.dump(report, out, indent=2, ensure_ascii=False)
            out.write("\n")
    except (OSError, CaptureError) as exc:
        p.error(str(exc))
    print(f"Audited {report['total_csv_rows']} CSV rows: {report['valid_frames']} valid; "
          f"{report['discarded_rows']} discarded. Replay approved: NO")
    print(f"Saved metadata (NO CAN payloads): {args.output}")


if __name__ == "__main__":
    main()
