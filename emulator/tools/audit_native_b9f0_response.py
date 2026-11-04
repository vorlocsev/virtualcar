#!/usr/bin/env python3
"""Read-only native J2534 audit of CEM B9F0 transport after observed requests.

No ECU data is decoded or exported. A completed positive D2 transport is NOT
proof that a particular CEM, part number or diagnostic client accepted it.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

from audit_j2534_discovery import PREFIX, _context, _request, _flow_control, _p3_frame
from import_p2_trace import validate_response

MAX_BYTES = 4 * 1024 * 1024
MAX_LINES = 45000
MAX_RECORDS = 512
FORMAT = "virtualcar-native-p2-b9f0-response-evidence-v1"
TX_CTX = "TX context channel/protocol/flags/baud/time-us (BE)"
RX_CTX = "RX context channel/protocol/status/baud/time-us (BE)"
CLEAR_CTX = "CLEAR_RX context channel/protocol/flags/baud/time-us (BE)"
RESPONSE_IDS = {0x40: (0x00800003,),
                0x50: (0x01000003, 0x01200003)}
BAUD = {0x40: 125000, 0x50: 500000}
HEX12 = re.compile(r"(?:[0-9a-fA-F]{2}\s+){11}[0-9a-fA-F]{2}\Z")
HEX4 = re.compile(r"[0-9a-fA-F]{2}(?:\s+[0-9a-fA-F]{2}){3}\Z")


def _can12(text):
    return bytes.fromhex(text) if HEX12.fullmatch(text.strip()) else None


def _native_message(text):
    """Decode a bounded, local native record without ever exporting bytes."""
    words = text.strip().split()
    if not 5 <= len(words) <= 4096:
        return None
    if not all(re.fullmatch(r"[0-9A-Fa-f]{2}", word) for word in words):
        return None
    return bytes(int(word, 16) for word in words)


def _tx_prefix(text):
    """Allowlisted service classification uses only the first 12 bytes."""
    raw = _native_message(text)
    return raw[:12] if raw is not None else None


def _elapsed(after, before):
    if type(after) is not int or type(before) is not int:
        return None
    delta = (after - before) % (1 << 32)
    return round(delta / 1000, 3) if delta <= 60_000_000 else None


def _scope():
    return {"tx": None, "rx": None, "disconnect": None, "clear": None,
            "active": {}, "waiting": [], "probes": {}}


def _next_app_tx_label(req):
    """Allowlisted request family only, never private DID or raw operands."""
    if req is None:
        return "other_or_unclassified_tx"
    route, service, target, _ = req
    if route == "D2" and service in ("B9F0", "B9FB", "B9FC", "A3", "A6"):
        return "d2_" + service.lower()
    if route == "P3" and service.startswith("22"):
        return "p3_read_data_by_identifier"
    if route == "P3":
        return "p3_other"
    return "other_or_unclassified_tx"


def audit(source):
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_BYTES:
        raise ValueError("invalid_source_size")
    lines = source.splitlines()
    if len(lines) > MAX_LINES:
        raise ValueError("too_many_lines")
    scopes, records, errors = {}, [], Counter()

    def finish_probe(state, channel, reason):
        """Close first post-B9F0 P3 response window; never infer ECU inventory."""
        probe = state["probes"].pop(channel, None)
        if probe is None:
            return
        transport = probe["transport"]
        if transport["_invalid"]:
            status = "invalid_transport"
        elif transport["_p3_negative"]:
            status = "negative_response"
        elif transport["_p3_missing_data"]:
            status = "missing_did_record"
        elif transport["_p3_mismatch"]:
            status = "mismatched_did_or_service"
        elif transport["_complete"]:
            status = "positive_transport_complete"
        elif transport["_p3_pending"]:
            status = ("response_pending_timeout" if probe["timeout"]
                      else "response_pending_only")
        elif transport["rx_frames"]:
            status = "partial_rx"
        elif probe["timeout"]:
            status = "read_timeout_observed"
        elif probe["offroute"]:
            status = "off_route_rx_only"
        else:
            status = "no_matched_rx"
        record = probe["owner"]
        record["first_next_p3_response_status"] = status
        record["first_next_p3_response_boundary"] = reason
        record["first_next_p3_rx_frames"] = transport["rx_frames"]
        record["first_next_p3_off_route_rx_count"] = probe["offroute"]
        record["first_next_p3_pending_count"] = transport["_p3_pending"]
        record["first_next_p3_ignored_indication_count"] = probe["indications"]
        record["first_next_p3_tx_to_last_rx_ms"] = _elapsed(
            probe["last_rx"], probe["tx_time"])
        record["first_next_p3_positive_transport_complete"] = (
            status == "positive_transport_complete")

    def finish_probes(state, reason, channel=None):
        for candidate in list(state["probes"]):
            if channel is None or candidate == channel:
                finish_probe(state, candidate, reason)

    def stop_waiting(state, reason, channel=None):
        """Close observed post-positive windows at explicit native boundaries."""
        remaining = []
        for record, source_channel, source_baud, rx_at in state["waiting"]:
            if channel is None or source_channel == channel:
                record["first_next_app_tx_observation"] = reason
            else:
                remaining.append((record, source_channel, source_baud, rx_at))
        state["waiting"] = remaining

    def observe_next_tx(state, req, channel=None, baud=None, at=None,
                        protocol=None):
        """Bind only the first P3 read after a positive B9F0 within this PID."""
        prior = state["waiting"]
        if len(prior) == 1 and channel is not None and protocol in (5, 6) and (
                req is not None and req[0] == "P3"
                and req[1].startswith("22") and req[1] != "other"):
            # Use the existing read-only P3 ISO-TP/UDS validator, not a
            # second DID decoder. The private DID stays in memory only.
            state["probes"][channel] = {
                "owner": prior[0][0],
                "request_id": req[3],
                "protocol": protocol,
                "baud": baud,
                "tx_time": at,
                "last_rx": None,
                "offroute": 0,
                "indications": 0,
                "timeout": False,
                "transport": {
                    "route": "P3", "service": req[1], "rx_frames": 0,
                    "off_route_rx": 0, "_complete": False,
                    "_p3_negative": False, "_p3_mismatch": False,
                    "_p3_missing_data": False, "_invalid": False,
                    "_p3_pending": 0, "_p3_total": None,
                    "_p3_received": 0, "_p3_sequence": 1,
                    "_p3_header": b"",
                },
            }
            prior[0][0]["first_next_p3_response_status"] = "awaiting_rx"
        elif len(prior) > 1 and (req is not None and req[0] == "P3"
                                  and req[1].startswith("22")):
            # Two completed B9F0s preceding one first TX do not identify
            # which one the client interpreted; no causal RX claim.
            for record, _, _, _ in prior:
                record["first_next_p3_response_status"] = (
                    "ambiguous_multiple_b9f0_predecessors")
        for record, source_channel, source_baud, rx_at in prior:
            if channel is None:
                record["first_next_app_tx_observation"] = "next_tx_unattributed"
                record["first_next_app_tx_service"] = "unattributed_app_tx"
            else:
                record["first_next_app_tx_observation"] = "first_next_tx_observed"
                record["first_next_app_tx_service"] = _next_app_tx_label(req)
                record["first_next_app_tx_same_channel"] = channel == source_channel
                record["first_next_app_tx_same_baud"] = baud == source_baud
                record["last_b9f0_rx_to_first_next_tx_ms"] = _elapsed(at, rx_at)
        state["waiting"].clear()

    def finish(state, channel, reason, terminal=None):
        candidate = state["active"].pop(channel, None)
        if candidate is None:
            return
        frames = candidate["frames"]
        status = terminal
        if status is None:
            if candidate["invalid"]:
                status = "invalid_transport"
            elif frames:
                status = "partial_rx"
            elif candidate["timeout"]:
                status = "read_timeout_observed"
            elif candidate["offroute"]:
                status = "off_route_rx_only"
            else:
                status = "no_matched_rx"
        records.append({
            "target": "0x%02X" % candidate["target"],
            "status": status,
            "boundary": reason,
            "rx_frames": len(frames),
            "off_route_rx_count": candidate["offroute"],
            "ignored_rx_indication_count": candidate["indications"],
            "read_timeout_observed": candidate["timeout"],
            "tx_to_last_matched_rx_ms": _elapsed(
                candidate["last_rx_time"], candidate["tx_time"]),
            "positive_echo_transport_complete": status == "positive_transport_complete",
            "negative_b9_service_reply_observed": status == "negative_b9_service_reply",
            "part_number_decoded": False,
            "vehicle_identity_verified": False,
            "client_acceptance_verified": False,
            "ecu_enumeration_verified": False,
            "first_next_app_tx_observation": "no_next_tx_observed",
            "first_next_app_tx_service": None,
            "first_next_app_tx_same_channel": None,
            "first_next_app_tx_same_baud": None,
            "last_b9f0_rx_to_first_next_tx_ms": None,
            "first_next_p3_response_status": "not_a_p3_read",
            "first_next_p3_response_boundary": None,
            "first_next_p3_rx_frames": 0,
            "first_next_p3_off_route_rx_count": 0,
            "first_next_p3_pending_count": 0,
            "first_next_p3_ignored_indication_count": 0,
            "first_next_p3_tx_to_last_rx_ms": None,
            "first_next_p3_positive_transport_complete": False,
        })
        if status == "positive_transport_complete":
            # Only a proven terminal RX opens a post-B9F0 observation.
            # Keep state-local channel/baud/timestamp private.
            record = records[-1]
            state["waiting"].append((
                record, channel, candidate["baud"], candidate["last_rx_time"]))
        if len(records) > MAX_RECORDS:
            raise ValueError("too_many_b9f0_records")

    def finish_all(state, reason):
        finish_probes(state, reason)
        for channel in list(state["active"]):
            finish(state, channel, reason)
        state["tx"] = state["rx"] = None
        state["disconnect"] = state["clear"] = None

    for line in lines:
        if "=== SECTORV VIRTUALCAR SESSION " in line:
            for state in scopes.values():
                stop_waiting(state, "session_marker_before_next_tx")
                finish_all(state, "explicit_session_marker")
            scopes.clear()
            continue
        match = PREFIX.fullmatch(line.rstrip("\r\n"))
        if not match:
            continue
        pid, text = match.groups()
        state = scopes.setdefault(pid, _scope())
        if text in ("PassThruOpen -> device 1", "PassThruClose"):
            stop_waiting(state, "open_before_next_tx" if text.startswith(
                "PassThruOpen") else "close_before_next_tx")
            finish_all(state, "open_boundary" if text.startswith("PassThruOpen")
                       else "close_boundary")
            continue
        if text.startswith("PassThruDisconnect channel (BE)"):
            raw = text.partition("(BE)")[2].strip()
            state["disconnect"] = int.from_bytes(bytes.fromhex(raw), "big") if HEX4.fullmatch(raw) else None
            if state["disconnect"] is None:
                errors["invalid_disconnect_context"] += 1
            continue
        if text == "PassThruDisconnect":
            channel = state["disconnect"]
            if channel is None:
                errors["unattributed_disconnect"] += 1
                stop_waiting(state, "unattributed_disconnect_before_next_tx")
                finish_all(state, "unattributed_disconnect")
            else:
                stop_waiting(state, "disconnect_before_next_tx", channel)
                finish_probe(state, channel, "channel_disconnect")
                finish(state, channel, "channel_disconnect")
                state["tx"] = state["rx"] = None
                state["disconnect"] = state["clear"] = None
            continue
        if text.startswith("CLEAR_RX context "):
            state["clear"] = _context(text, CLEAR_CTX, strict=True)
            if state["clear"] is None:
                errors["invalid_clear_context"] += 1
            continue
        if text.startswith("J2534 CLEAR_RX_BUFFER:"):
            if state["clear"] is None:
                errors["unattributed_clear"] += 1
                stop_waiting(state, "unattributed_clear_before_next_tx")
                finish_all(state, "unattributed_clear")
            else:
                stop_waiting(state, "rx_buffer_clear_before_next_tx",
                             state["clear"][0])
                finish_probe(state, state["clear"][0], "rx_buffer_clear")
                finish(state, state["clear"][0], "rx_buffer_clear")
                state["tx"] = state["rx"] = state["clear"] = None
            continue
        if text.startswith("TX context "):
            state["tx"] = _context(text, TX_CTX, strict=True)
            if state["tx"] is None:
                errors["invalid_tx_context"] += 1
            continue
        if text.startswith("RX context "):
            state["rx"] = _context(text, RX_CTX, strict=True)
            if state["rx"] is None:
                errors["invalid_rx_context"] += 1
            continue

        if text.startswith("TX (app request)"):
            ctx = state["tx"]
            data_text = text[len("TX (app request)"):]
            prefix = _tx_prefix(data_text)
            raw = _can12(data_text) if ctx is not None and ctx[1] == 5 else None
            state["tx"] = None
            if ctx is None or prefix is None or ctx[1] not in (5, 6):
                errors["unattributed_or_invalid_tx"] += 1
                observe_next_tx(state, None)
                finish_all(state, "unattributed_app_tx")
                continue
            channel, _, _, baud, at = ctx
            # ISO-TP FC is transport continuation, not a fresh ECU probe.
            # Never let FC consume a post-B9F0 first-app-TX observation,
            # or replace the active request on that J2534 channel.
            if (ctx[1] == 5 and prefix[4] in (0x30, 0x31, 0x32)
                    and _flow_control(prefix, include_obd=True)):
                # Raw ISO15765 J2534 payloads begin with a UDS service,
                # where 0x31 is RoutineControl and 0x3E TesterPresent.
                # Only a classic CAN ISO-TP PCI is a Flow Control.
                continue
            req = _request(prefix)
            finish_probe(state, channel, "superseded_by_app_tx")
            observe_next_tx(state, req, channel, baud, at, ctx[1])
            # The next TX on this channel ends the preceding response window.
            finish(state, channel, "superseded_by_app_tx")
            # D2 fixture requests still require exact classic-CAN framing.
            if (ctx[1] != 5 or raw is None or req is None
                    or req[0] != "D2" or req[1] != "B9F0"
                    or req[2] not in RESPONSE_IDS or raw[4] != 0xCB):
                continue
            target = req[2]
            if baud != BAUD[target]:
                errors["b9f0_wrong_bus_request"] += 1
                continue
            if len(records) + sum(len(s["active"]) for s in scopes.values()) >= MAX_RECORDS:
                raise ValueError("too_many_b9f0_requests")
            state["active"][channel] = {
                "target": target, "baud": baud, "tx_time": at,
                "last_rx_time": None, "frames": [], "offroute": 0,
                "indications": 0, "invalid": False, "timeout": False,
            }
            continue

        if text.startswith("PassThruReadMsgs -> delivered"):
            data_text = text[len("PassThruReadMsgs -> delivered"):]
            ctx = state["rx"]
            state["rx"] = None
            raw_bytes = _native_message(data_text)
            if ctx is None or raw_bytes is None or ctx[1] not in (5, 6):
                errors["unattributed_or_invalid_rx"] += 1
                # Malformed P3 framing is not proof of a delivered identity.
                if ctx is not None and ctx[0] in state["probes"]:
                    state["probes"][ctx[0]]["transport"]["_invalid"] = True
                    finish_probe(state, ctx[0], "unattributed_rx_record")
                continue
            channel, protocol, rxstatus, baud, at = ctx
            probe = state["probes"].get(channel)
            if probe is not None:
                if rxstatus & (0x01 | 0x02 | 0x08):
                    probe["indications"] += 1
                    continue
                expected = (0x72E if probe["request_id"] == 0x726
                            else 0x18DAF150)
                actual_id = int.from_bytes(raw_bytes[:4], "big")
                if (protocol != probe["protocol"] or baud != probe["baud"]
                        or actual_id != expected):
                    probe["offroute"] += 1
                    continue
                if (protocol == 5 and len(raw_bytes) != 12) or (
                        protocol == 6 and len(raw_bytes) < 5):
                    probe["transport"]["_invalid"] = True
                    finish_probe(state, channel, "invalid_native_rx_length")
                    errors["invalid_p3_rx_length"] += 1
                    continue
                _p3_frame(probe["transport"], raw_bytes[4:],
                          "CAN" if protocol == 5 else "ISO15765")
                probe["last_rx"] = at
                frame = probe["transport"]
                if frame["rx_frames"] > 64:
                    frame["_invalid"] = True
                if (frame["_complete"] or frame["_p3_negative"]
                        or frame["_p3_missing_data"] or frame["_p3_mismatch"]
                        or frame["_invalid"]):
                    finish_probe(state, channel, "terminal_p3_rx")
                continue
            raw = raw_bytes if protocol == 5 and len(raw_bytes) == 12 else None
            if raw is None:
                errors["unattributed_or_invalid_rx"] += 1
                continue
            candidate = state["active"].get(channel)
            if candidate is None:
                continue
            if rxstatus & (0x01 | 0x02 | 0x08):
                candidate["indications"] += 1
                continue
            canid = int.from_bytes(raw[:4], "big")
            if baud != candidate["baud"] or canid not in RESPONSE_IDS[candidate["target"]]:
                candidate["offroute"] += 1
                continue
            candidate["frames"].append((canid, raw[4:]))
            candidate["last_rx_time"] = at
            if len(candidate["frames"]) > 64:
                candidate["invalid"] = True
                finish(state, channel, "too_many_frames")
                continue
            control = raw[4]
            if not (0x48 <= control <= 0x4F or 0xC8 <= control <= 0xCF):
                continue
            try:
                validate_response(candidate["frames"], candidate["target"], 0xF0)
                first = candidate["frames"][0][1]
                if first[1:4] == bytes((candidate["target"], 0xF9, 0xF0)):
                    status = "positive_transport_complete"
                elif (len(candidate["frames"]) == 1
                      and first[1:4] == bytes((candidate["target"], 0x7F, 0xB9))):
                    status = "negative_b9_service_reply"
                else:
                    raise ValueError("unpaired_service_echo")
            except ValueError:
                candidate["invalid"] = True
                finish(state, channel, "invalid_terminal")
                errors["invalid_b9f0_transport"] += 1
            else:
                finish(state, channel, "terminal_frame", terminal=status)
            continue

        if text.startswith("PassThruReadMsgs timeout:"):
            fields = text.partition("(BE)")[2].strip().split()
            if len(fields) == 12 and all(re.fullmatch(r"[0-9A-Fa-f]{2}", b) for b in fields):
                channel = int.from_bytes(bytes.fromhex(" ".join(fields[:4])), "big")
                if channel in state["active"]:
                    state["active"][channel]["timeout"] = True
                if channel in state["probes"]:
                    state["probes"][channel]["timeout"] = True
            else:
                errors["invalid_timeout_context"] += 1

    for state in scopes.values():
        stop_waiting(state, "end_of_log_no_next_tx_observed")
        finish_all(state, "end_of_log")
    counts = Counter(item["status"] for item in records)
    post_positive = [item for item in records
                     if item["positive_echo_transport_complete"]]
    next_services = Counter(
        item["first_next_app_tx_service"] or "no_classified_next_tx"
        for item in post_positive)
    p3_statuses = Counter(
        item["first_next_p3_response_status"] for item in post_positive
        if item["first_next_app_tx_service"] == "p3_read_data_by_identifier")
    return {
        "format": FORMAT,
        "read_only": True,
        "evidence_scope": "single_native_j2534_text_log",
        "request_count": len(records),
        "status_counts": dict(sorted(counts.items())),
        "observations": records,
        "parse_errors": dict(sorted(errors.items())),
        "contains_payload_data": False,
        "any_positive_transport_observed": bool(post_positive),
        "post_positive_first_next_tx_service_counts": dict(sorted(
            next_services.items())),
        "post_positive_first_next_tx_observed_count": sum(
            item["first_next_app_tx_observation"] == "first_next_tx_observed"
            for item in post_positive),
        "post_positive_first_p3_response_status_counts": dict(sorted(
            p3_statuses.items())),
        "post_positive_first_p3_positive_transport_count": sum(
            item["first_next_p3_positive_transport_complete"]
            for item in post_positive),
        "b9f0_identity_verified": False,
        "ecu_enumeration_verified": False,
        "client_acceptance_verified": False,
        "limitations": [
            "Only matching native CAN route, channel and D2 framing are checked.",
            "A positive B9F0 echo does not prove vehicle identity or part-number semantics.",
            "No native request record proves PassThruWriteMsgs success or physical transmission.",
            "A negative B9 service reply is not a positive B9F0 response.",
            "A later application TX after positive B9F0 is a request observation, not a client parse verdict or ECU inventory proof.",
            "The first later TX is attributed only within one native PID and uninterrupted source session.",
            "Variable-size ISO15765 application TX is classified by its bounded header only, not parsed as a completed ECU response.",
            "ISO-TP Flow Control TX on P3/OBD routes is transport continuation, not the first later application request.",
            "A first P3 DID read is paired only by same native PID, request channel, protocol, baud and known reply CAN route.",
            "Shared P3 UDS header/ISO-TP validator checks positive, negative, pending and incomplete transport, not true ECU discovery.",
            "Multiple positive B9F0 predecessors of one P3 request remain causally ambiguous.",
            "Neither diagnostic client acceptance nor genuine XC90 V8 MY2009 identity is established.",
            "No VIN, part number, PID, host, timestamp raw bytes, CAN payload, or private source path is exported.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.source.resolve() == args.output.resolve():
            raise ValueError("source_output_overlap")
        if args.source.stat().st_size > MAX_BYTES:
            raise ValueError("source_too_large")
        output = audit(args.source.read_text(encoding="utf-8-sig", errors="replace"))
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(output, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except (OSError, UnicodeError, ValueError):
        print("B9F0 audit rejected source/output; private details withheld", file=sys.stderr)
        return 2
    print("PASS: native B9F0 transport evidence audited; ECU identity unknown")
    return 0


if __name__ == "__main__":
    sys.exit(main())
