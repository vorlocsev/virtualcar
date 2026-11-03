#!/usr/bin/env python3
"""Read-only post-B9FB timing audit of native Virtual Car J2534 text logs.

Computes last completed B9FB RX -> first observed app TX within the *same PID
and log epoch*. It never mixes VIDA wall-clock time, SectorV client time,
backend JSONL and native QPC. No payload/vehicle identity is exported.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

from audit_j2534_discovery import PREFIX, _context, _request
from import_p2_trace import validate_response

FORMAT = "virtualcar-d2-b9fb-followup-window-v1"
MAX_BYTES = 4 * 1024 * 1024
MAX_LINES = 45000
MAX_RECORDS = 512
CTX_TX = "TX context channel/protocol/flags/baud/time-us (BE)"
CTX_RX = "RX context channel/protocol/status/baud/time-us (BE)"
HEX12 = re.compile(r"(?:[0-9A-Fa-f]{2}\s+){11}[0-9A-Fa-f]{2}\Z")
RESPONSE_IDS = {0x40: (0x00800003,),
                0x50: (0x01000003, 0x01200003)}
MAX_US_GAP = 60_000_000


def _can12(data):
    if not HEX12.fullmatch(data.strip()):
        return None
    return bytes.fromhex(data)


def _gap(after, before):
    if not isinstance(after, int) or not isinstance(before, int):
        return None
    elapsed = (after - before) % (1 << 32)
    return elapsed if elapsed <= MAX_US_GAP else None


def _window(delta_us, duration_ms):
    if delta_us is None:
        return "timestamp_unverified"
    return "first_tx_within_window" if delta_us <= duration_ms * 1000 else "first_tx_later_than_window"


def _scope():
    return {"tx_ctx": None, "rx_ctx": None, "active": {}, "waiting": []}


def _service_label(request):
    if request is None:
        return "other_or_unclassified_tx"
    route, service, target, _ = request
    if route != "D2":
        return "other_or_unclassified_tx"
    if service == "A3":
        return "d2_a3_target_known" if target in (0x40, 0x50) else "d2_a3_target_unknown"
    if service == "A6":
        return "d2_a6"
    if service in ("B9F0", "B9FB", "B9FC"):
        return "d2_" + service.lower()
    return "other_or_unclassified_tx"


def audit(source):
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_BYTES:
        raise ValueError("invalid_source_size")
    lines = source.splitlines()
    if len(lines) > MAX_LINES:
        raise ValueError("too_many_lines")
    scopes = {}
    results = []
    errors = Counter()
    incomplete = 0

    def finalize(candidate, outcome, *, next_tx=None):
        record = {
            "b9fb_target": "0x%02X" % candidate["target"],
            "b9fb_rx_frames": len(candidate["frames"]),
            "b9fb_transport_complete": True,
            "b9fb_tx_to_last_rx_ms": (
                round(_gap(candidate["last_rx"], candidate["tx_time"]) / 1000, 3)
                if _gap(candidate["last_rx"], candidate["tx_time"]) is not None else None),
            "followup_observation": outcome,
            "first_next_tx_service": None,
            "first_next_tx_target": None,
            "first_next_tx_same_target": None,
            "first_next_tx_same_channel": None,
            "first_next_tx_same_baud": None,
            "last_rx_to_first_next_tx_ms": None,
            "within_500_ms": "no_next_tx_observed",
            "within_1000_ms": "no_next_tx_observed",
            "read_timeout_after_b9fb_on_original_channel": candidate["timeout_after"],
            "client_accepted_b9fb": False,
            "ecu_identity_verified": False,
        }
        if next_tx is not None:
            request, channel, baud, timestamp = next_tx
            delta = _gap(timestamp, candidate["last_rx"])
            record["first_next_tx_service"] = _service_label(request)
            # Output only the two known CEM routes. Unclassified/foreign
            # targets are deliberately not copied from private app TX bytes.
            next_target = (request[2] if request is not None
                           and request[0] == "D2" and request[2] in (0x40, 0x50)
                           else None)
            record["first_next_tx_target"] = (
                "0x%02X" % next_target if next_target is not None else None)
            record["first_next_tx_same_target"] = (
                next_target == candidate["target"]
                if next_target is not None else None)
            record["first_next_tx_same_channel"] = channel == candidate["channel"]
            record["first_next_tx_same_baud"] = baud == candidate["baud"]
            record["last_rx_to_first_next_tx_ms"] = (
                round(delta / 1000, 3) if delta is not None else None)
            record["within_500_ms"] = _window(delta, 500)
            record["within_1000_ms"] = _window(delta, 1000)
        results.append(record)
        if len(results) > MAX_RECORDS:
            raise ValueError("too_many_completed_b9fb_observations")

    def boundary(scope, reason):
        nonlocal incomplete
        incomplete += len(scope["active"])
        for cand in scope["waiting"]:
            finalize(cand, reason)
        scope["active"].clear()
        scope["waiting"].clear()
        scope["tx_ctx"] = scope["rx_ctx"] = None

    for line in lines:
        if "=== SECTORV VIRTUALCAR SESSION " in line:
            for item in scopes.values():
                boundary(item, "session_marker_before_next_tx")
            scopes.clear()
            continue
        match = PREFIX.fullmatch(line.rstrip("\r\n"))
        if match is None:
            continue
        pid, text = match.groups()
        s = scopes.setdefault(pid, _scope())

        if text in ("PassThruOpen -> device 1", "PassThruClose", "PassThruDisconnect"):
            reason = ("open_before_next_tx" if text.startswith("PassThruOpen") else
                      "close_before_next_tx" if text == "PassThruClose" else
                      "disconnect_before_next_tx")
            boundary(s, reason)
            continue

        if text.startswith("TX context "):
            s["tx_ctx"] = _context(text, CTX_TX, strict=True)
            if s["tx_ctx"] is None:
                errors["invalid_tx_context"] += 1
            continue
        if text.startswith("RX context "):
            s["rx_ctx"] = _context(text, CTX_RX, strict=True)
            if s["rx_ctx"] is None:
                errors["invalid_rx_context"] += 1
            continue

        if text.startswith("TX (app request)"):
            raw = _can12(text[len("TX (app request)"):])
            ctx = s["tx_ctx"]
            s["tx_ctx"] = None
            if raw is None or ctx is None or ctx[1] != 5:
                errors["unattributed_or_invalid_tx"] += 1
                # A TX marker exists, but it cannot be correlated with a
                # channel/timestamp. Never silently relabel it as "no TX".
                for candidate in s["waiting"]:
                    finalize(candidate, "next_tx_unattributed")
                    result = results[-1]
                    result["first_next_tx_service"] = "unclassified_unattributed_tx"
                    result["within_500_ms"] = "timestamp_unverified"
                    result["within_1000_ms"] = "timestamp_unverified"
                s["waiting"].clear()
                continue
            channel, protocol, flags, baud, at = ctx
            req = _request(raw)
            for candidate in s["waiting"]:
                finalize(candidate, "first_next_tx_observed",
                         next_tx=(req, channel, baud, at))
            s["waiting"].clear()
            old = s["active"].pop(channel, None)
            if old is not None:
                incomplete += 1
            if (req and req[0] == "D2" and req[1] == "B9FB"
                    and req[2] in RESPONSE_IDS and
                    baud == (125000 if req[2] == 0x40 else 500000)):
                if sum(len(value["active"]) + len(value["waiting"])
                       for value in scopes.values()) >= MAX_RECORDS:
                    raise ValueError("too_many_active_b9fb")
                s["active"][channel] = {
                    "target": req[2], "channel": channel, "baud": baud,
                    "tx_time": at, "last_rx": None, "frames": [],
                    "timeout_after": False,
                }
            continue

        if text.startswith("PassThruReadMsgs -> delivered"):
            raw = _can12(text[len("PassThruReadMsgs -> delivered"):])
            ctx = s["rx_ctx"]
            s["rx_ctx"] = None
            if raw is None or ctx is None or ctx[1] != 5:
                errors["unattributed_or_invalid_rx"] += 1
                continue
            channel, _, rx_status, baud, at = ctx
            # Native J2534 RxStatus can describe a TX echo/indication or
            # an ISO-TP start indication. Neither is a reply from the ECU.
            # CAN_29BIT_ID (0x100) is valid metadata, not an indication.
            if rx_status & (0x01 | 0x02 | 0x08):
                errors["rx_indication_not_ecu_frame"] += 1
                continue
            current = s["active"].get(channel)
            if current is None or baud != current["baud"]:
                continue
            can_id = int.from_bytes(raw[:4], "big")
            if can_id not in RESPONSE_IDS[current["target"]]:
                errors["off_route_b9fb_rx"] += 1
                continue
            current["frames"].append((can_id, raw[4:]))
            current["last_rx"] = at
            if len(current["frames"]) > 64:
                incomplete += 1
                s["active"].pop(channel, None)
                continue
            control = raw[4]
            if 0x48 <= control <= 0x4F or (control & 0xF8) == 0xC8:
                try:
                    validate_response(current["frames"], current["target"], 0xFB)
                    first = current["frames"][0][1]
                    if first[1:4] != bytes((current["target"], 0xF9, 0xFB)):
                        raise ValueError("not_a_positive_b9fb")
                except ValueError:
                    errors["invalid_completed_b9fb"] += 1
                    incomplete += 1
                else:
                    s["waiting"].append(current)
                s["active"].pop(channel, None)
            continue

        if text.startswith("PassThruReadMsgs timeout:"):
            # Channel is taken from the explicit 3-word native marker only.
            raw = text.partition("(BE)")[2].strip()
            words = raw.split()
            if len(words) == 12 and all(re.fullmatch(r"[0-9A-Fa-f]{2}", w) for w in words):
                channel = int.from_bytes(bytes.fromhex(" ".join(words[:4])), "big")
                for candidate in s["waiting"]:
                    if candidate["channel"] == channel:
                        candidate["timeout_after"] = True
            continue
        if text.startswith("J2534 CLEAR_RX_BUFFER:"):
            # Lacks a channel; the context-dependent original audit provides
            # a stronger route attribution. Conservatively mark a boundary.
            boundary(s, "clear_rx_before_next_tx")

    for scope in scopes.values():
        boundary(scope, "end_of_log_no_next_tx_observed")
    return {
        "format": FORMAT, "read_only": True, "contains_payload_data": False,
        "source_clock": "native_32bit_time_us_same_pid_epoch_only",
        "completed_b9fb_count": len(results),
        "incomplete_b9fb_count": incomplete,
        "observations": results,
        "parse_errors": dict(sorted(errors.items())),
        "limitations": [
            "Only source-local native TX/RX context timestamps are compared; no clocks are joined across files.",
            "A complete D2 envelope is transport evidence, not client acceptance of B9FB.",
            "The first next app TX may be on another channel; same-channel matching is reported separately.",
            "Next D2 CEM target is exported only when 0x40 or 0x50; same-target is not an access or identity check.",
            "A3 request observation does not prove an E3 response or normal-mode preparation.",
            "An end-of-log, close, clear or disconnect is not proof of a timeout or 1000 ms silence.",
            "Within-window labels refer to the first logged TX, not proof that every bus frame was captured.",
            "Counters, allowlisted service labels and time gaps only; no VIN, CAN payload, paths or PID are exported.",
            "RX records with J2534 TX_MSG_TYPE, START_OF_MESSAGE or TX_INDICATION status are excluded from ECU RX framing.",
        ],
        "client_acceptance_verified": False,
        "same_run_with_sectorv_client_verified": False,
        "xc90_v8_my2009_verified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.log.resolve() == args.output.resolve():
            raise ValueError("output_overlaps_source")
        if args.log.stat().st_size > MAX_BYTES:
            raise ValueError("source_too_large")
        result = audit(args.log.read_text(encoding="utf-8-sig", errors="replace"))
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
    except (OSError, ValueError, UnicodeError):
        print("Native D2 followup audit refused input/output (private details withheld)",
              file=sys.stderr)
        return 2
    print("PASS: native B9FB followup observation, no ECU acceptance inferred")
    return 0


if __name__ == "__main__":
    sys.exit(main())
