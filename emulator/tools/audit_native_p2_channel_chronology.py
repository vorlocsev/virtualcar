#!/usr/bin/env python3
"""Privacy-bounded chronology of a *native* Virtual Car J2534 P2 session.

Uses the real TX/RX channel IDs *internally* to avoid inventing the
channel binding missing from historic SectorV dev8/dev10 reports.
Exports only per-session channel aliases, fixed event types and timing.
A native log records J2534 API observations, never a client parser verdict.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

from audit_j2534_discovery import PREFIX, _context, _request
from import_p2_trace import validate_response

MAX_BYTES = 4 * 1024 * 1024
MAX_LINES = 45000
MAX_EPOCHS = 128
MAX_EVENTS = 1000
FORMAT = "virtualcar-native-p2-channel-chronology-v3"
TX_CONTEXT = "TX context channel/protocol/flags/baud/time-us (BE)"
RX_CONTEXT = "RX context channel/protocol/status/baud/time-us (BE)"
HEX12 = re.compile(r"^[0-9A-Fa-f]{2}(?:\s+[0-9A-Fa-f]{2}){11}$")
HEX4 = re.compile(r"^[0-9A-Fa-f]{2}(?:\s+[0-9A-Fa-f]{2}){3}$")
RESPONSE_IDS = {0x50: (0x01000003, 0x01200003), 0x40: (0x00800003,)}
EXPECTED_BAUD = {0x50: 500000, 0x40: 125000}


def _can12(text):
    source = text.strip()
    return bytes.fromhex(source) if HEX12.fullmatch(source) else None


def _native_message(text):
    """Validate native J2534 byte records without exporting or decoding them."""
    fields = text.strip().split()
    if not 5 <= len(fields) <= 4096:
        return None
    if not all(re.fullmatch(r"[0-9a-fA-F]{2}", field) for field in fields):
        return None
    return bytes(int(field, 16) for field in fields)


def _gap(after, before):
    if type(after) is not int or type(before) is not int:
        return None
    delta = (after - before) % (1 << 32)
    return round(delta / 1000, 3) if delta <= 60000000 else None


def _state():
    return {
        "tx_ctx": None, "rx_ctx": None, "disconnect_ctx": None,
        "channels": {}, "generations": {}, "events": [], "active": {}, "barriers": [], "incomplete": 0,
        "process_sectorv": False, "source_error": False,
    }


def _alias(state, channel):
    if channel not in state["channels"]:
        state["channels"][channel] = "ch" + str(len(state["channels"]) + 1)
    return state["channels"][channel]


def _event(state, kind, target, channel, baud, timestamp):
    if len(state["events"]) >= MAX_EVENTS:
        raise ValueError("too_many_events")
    item = {
        "order": len(state["events"]) + 1,
        "kind": kind,
        "target": "0x%02X" % target,
        "channel": _alias(state, channel),
        "baud_bps": baud if baud in (125000, 500000) else None,
        "_channel": channel,
        "_generation": state["generations"].get(channel, 0),
        "_time": timestamp,
    }
    state["events"].append(item)
    return item


def _barrier(state, kind):
    if len(state["barriers"]) >= MAX_EVENTS:
        raise ValueError("too_many_intervening_events")
    state["barriers"].append((len(state["events"]), kind))


def _between(state, before, after):
    return next((kind for order, kind in state["barriers"]
                 if before["order"] <= order < after["order"]), None)


def _barrier_status(kind):
    return "intervening_other_app_tx" if kind == "other_app_tx" else "clear_rx_between_events"


def _first_completed_b9fb_a3(state):
    """First A3 after first complete B9FB in *native source order* only.

    This is the first observed A3, NOT necessarily the next app TX. A
    second B9FB TX before that A3 blocks pairing. All channel and time
    metadata stays private except the safely rounded delta in milliseconds.
    """
    events = state["events"]
    completions = [x for x in events if x["kind"] == "b9fb_rx_complete"]
    base = {
        "status": "no_completed_b9fb_observed",
        "b9fb_completion_order": None,
        "first_later_a3_order": None,
        "last_b9fb_rx_to_first_later_a3_ms": None,
        "same_channel_target_generation_verified": False,
        "client_acceptance_verified": False,
    }
    if not completions:
        return base
    completed = completions[0]
    base["b9fb_completion_order"] = completed["order"]
    candidates = [x for x in events
                  if x["kind"] == "a3_tx" and x["order"] > completed["order"]]
    if not candidates:
        base["status"] = "no_later_a3_observed"
        return base
    first = candidates[0]
    base["first_later_a3_order"] = first["order"]
    if any(x["kind"] == "b9fb_tx"
           and completed["order"] < x["order"] < first["order"]
           for x in events):
        base["status"] = "intervening_b9fb_request"
    elif _between(state, completed, first) is not None:
        base["status"] = _barrier_status(_between(state, completed, first))
    elif first["_channel"] != completed["_channel"]:
        base["status"] = "different_channel"
    elif first["_generation"] != completed["_generation"]:
        base["status"] = "channel_reused_after_disconnect"
    elif first["target"] != completed["target"]:
        base["status"] = "different_target"
    elif first["baud_bps"] != completed["baud_bps"]:
        base["status"] = "different_baud"
    elif state["source_error"]:
        base["status"] = "source_context_incomplete"
    else:
        delta = _gap(first["_time"], completed["_time"])
        if delta is None:
            base["status"] = "timestamp_unverified"
        else:
            base["status"] = "same_channel_target_timed"
            base["last_b9fb_rx_to_first_later_a3_ms"] = delta
            base["same_channel_target_generation_verified"] = True
    return base


def _first_completed_b9fb_b9f0(state):
    """First later B9F0 read TX after the first completed B9FB, same native epoch.

    This checks an observed *request* only. No B9F0 reply, ECU part number,
    client acceptance or J2534 WriteMsgs success is inferred.
    """
    events = state["events"]
    completes = [e for e in events if e["kind"] == "b9fb_rx_complete"]
    result = {
        "status": "no_completed_b9fb_observed",
        "b9fb_completion_order": None,
        "first_later_b9f0_order": None,
        "last_b9fb_rx_to_first_later_b9f0_ms": None,
        "same_channel_target_generation_verified": False,
        "b9f0_response_verified": False,
        "client_acceptance_verified": False,
    }
    if not completes:
        return result
    completed = completes[0]
    result["b9fb_completion_order"] = completed["order"]
    later = next((e for e in events
                  if e["kind"] == "b9f0_tx"
                  and e["order"] > completed["order"]), None)
    if later is None:
        result["status"] = "no_later_b9f0_observed"
        return result
    result["first_later_b9f0_order"] = later["order"]
    between_events = [e["kind"] for e in events
                      if completed["order"] < e["order"] < later["order"]]
    barrier = _between(state, completed, later)
    if "b9fb_tx" in between_events:
        result["status"] = "intervening_b9fb_request"
    elif between_events:
        result["status"] = "intervening_other_app_tx"
    elif barrier is not None:
        result["status"] = _barrier_status(barrier)
    elif later["_channel"] != completed["_channel"]:
        result["status"] = "different_channel"
    elif later["_generation"] != completed["_generation"]:
        result["status"] = "channel_reused_after_disconnect"
    elif later["target"] != completed["target"]:
        result["status"] = "different_target"
    elif later["baud_bps"] != completed["baud_bps"]:
        result["status"] = "different_baud"
    elif state["source_error"]:
        result["status"] = "source_context_incomplete"
    else:
        gap = _gap(later["_time"], completed["_time"])
        if gap is None:
            result["status"] = "timestamp_unverified"
        else:
            result["status"] = "same_channel_target_timed"
            result["last_b9fb_rx_to_first_later_b9f0_ms"] = gap
            result["same_channel_target_generation_verified"] = True
    return result


def _finish(state, reason):
    if not state["events"]:
        return None
    complete = [x for x in state["events"] if x["kind"] == "b9fb_rx_complete"]
    a3 = [x for x in state["events"] if x["kind"] == "a3_tx"]
    b9fb = [x for x in state["events"] if x["kind"] == "b9fb_tx"]
    if not a3:
        status = "no_a3_observed"
    elif not complete:
        status = "no_completed_b9fb_observed"
    elif len(a3) != 1 or len(complete) != 1 or len(b9fb) != 1:
        status = "multiple_candidates_no_unique_pairing"
    elif a3[0]["order"] < b9fb[0]["order"]:
        status = "a3_before_b9fb_request"
    elif a3[0]["order"] < complete[0]["order"]:
        status = "a3_during_b9fb_delivery"
    elif _between(state, complete[0], a3[0]) is not None:
        status = "a3_after_b9fb_" + _barrier_status(_between(state, complete[0], a3[0]))
    elif a3[0]["_channel"] != complete[0]["_channel"]:
        status = "a3_after_b9fb_different_channel"
    elif a3[0]["_generation"] != complete[0]["_generation"]:
        status = "a3_after_b9fb_channel_reused_after_disconnect"
    elif a3[0]["target"] != complete[0]["target"]:
        status = "a3_after_b9fb_different_target"
    elif a3[0]["baud_bps"] != complete[0]["baud_bps"]:
        status = "a3_after_b9fb_different_baud"
    else:
        status = "a3_after_b9fb_same_channel_and_target"
    delta = (
        _gap(a3[0]["_time"], complete[0]["_time"])
        if status.startswith("a3_after_b9fb_") and len(a3) == len(complete) == 1
        else None
    )
    return {
        "outcome": status,
        "boundary": reason,
        "observed_process_label": (
            "sectorv_exe_in_native_log" if state["process_sectorv"]
            else "other_or_unverified_process"),
        "b9fb_completed": len(complete),
        "b9fb_requested": len(b9fb),
        "a3_requested": len(a3),
        "b9fb_incomplete": (state["incomplete"] + len(state["active"])),
        "first_completed_b9fb_to_later_a3": _first_completed_b9fb_a3(state),
        "first_completed_b9fb_to_later_b9f0": _first_completed_b9fb_b9f0(state),
        "b9f0_requests_observed": sum(e["kind"] == "b9f0_tx" for e in state["events"]),
        "channel_metadata_complete": not state["source_error"],
        "last_rx_to_a3_ms": delta,
        "same_channel_proven_for_observed_order": status == "a3_after_b9fb_same_channel_and_target"
        and not state["source_error"],
        "events": [{
            k: x[k] for k in ("order", "kind", "target", "channel", "baud_bps")
        } for x in state["events"]],
        "client_b9fb_acceptance_verified": False,
        "a3_security_access_verified": False,
    }


def audit(source):
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_BYTES:
        raise ValueError("invalid_source_size")
    lines = source.splitlines()
    if len(lines) > MAX_LINES:
        raise ValueError("too_many_lines")
    scopes = {}
    results = []
    errors = Counter()

    def end(pid, reason):
        state = scopes.pop(pid, None)
        if state is not None:
            candidate = _finish(state, reason)
            if candidate is not None:
                results.append(candidate)
                if len(results) > MAX_EPOCHS:
                    raise ValueError("too_many_epochs")

    for line in lines:
        if "=== SECTORV VIRTUALCAR SESSION " in line:
            for pid in list(scopes):
                end(pid, "explicit_session_marker")
            continue
        m = PREFIX.fullmatch(line.rstrip("\r\n"))
        if not m:
            continue
        pid, text = m.groups()
        # The PID and hostname are scope keys only; neither is exported.
        if text in ("VirtualCar DLL initialized (v0.3.6.6 extended configuration DID)",
                    "PassThruOpen -> device 1"):
            end(pid, "new_native_session")
            scopes[pid] = _state()
            if " SectorV.exe] " in line:
                scopes[pid]["process_sectorv"] = True
            continue
        if text == "PassThruClose":
            end(pid, "passthru_close")
            continue
        s = scopes.setdefault(pid, _state())
        if " SectorV.exe] " in line:
            s["process_sectorv"] = True

        if text.startswith("TX context "):
            s["tx_ctx"] = _context(text, TX_CONTEXT, strict=True)
            if s["tx_ctx"] is None:
                errors["invalid_tx_context"] += 1
                s["source_error"] = True
            continue
        if text.startswith("RX context "):
            s["rx_ctx"] = _context(text, RX_CONTEXT, strict=True)
            if s["rx_ctx"] is None:
                errors["invalid_rx_context"] += 1
                s["source_error"] = True
            continue
        if text.startswith("PassThruDisconnect channel (BE)"):
            raw = text.split("(BE)", 1)[1].strip()
            s["disconnect_ctx"] = int.from_bytes(bytes.fromhex(raw), "big") if HEX4.fullmatch(raw) else None
            if s["disconnect_ctx"] is None:
                errors["invalid_disconnect_context"] += 1
                s["source_error"] = True
            continue
        if text == "PassThruDisconnect":
            channel = s["disconnect_ctx"]
            if channel is not None:
                if channel in s["active"]:
                    s["incomplete"] += 1
                    del s["active"][channel]
                s["generations"][channel] = s["generations"].get(channel, 0) + 1
            else:
                # Ambiguous disconnect means future attribution needs a
                # fresh connection epoch, not a fabricated channel match.
                s["incomplete"] += len(s["active"])
                s["active"].clear()
                for ch in s["channels"]:
                    s["generations"][ch] = s["generations"].get(ch, 0) + 1
                s["source_error"] = True
            s["disconnect_ctx"] = None
            s["tx_ctx"] = s["rx_ctx"] = None
            continue
        if text.startswith("TX (app request)"):
            raw = _native_message(text[len("TX (app request)"):])
            ctx = s["tx_ctx"]
            s["tx_ctx"] = None
            if (raw is None or ctx is None or ctx[1] not in (5, 6)
                    or (ctx[1] == 5 and len(raw) > 12)):
                errors["unattributed_or_bad_tx"] += 1
                s["source_error"] = True
                continue
            channel, protocol, flags, baud, at = ctx
            if protocol != 5 or len(raw) != 12:
                # Valid ISO15765/short-CAN app TX is not a malformed
                # native record. It is an intervening application TX but
                # cannot be mistaken for an eight-byte D2 CEM request.
                _barrier(s, "other_app_tx")
                continue
            req = _request(raw)
            if req is None or req[0] != "D2" or req[2] not in (0x40, 0x50):
                _barrier(s, "other_app_tx")
                continue
            service, target = req[1], req[2]
            if service == "B9F0":
                # Exactly CB 40/50 B9 F0 is an executable D2 read shape.
                # Preserve it as an ordering event AND as an intervening
                # application-TX barrier for the independent A3 analysis.
                if raw[4] == 0xCB:
                    _event(s, "b9f0_tx", target, channel, baud, at)
                _barrier(s, "other_app_tx")
                continue
            if service not in ("A3", "B9FB"):
                _barrier(s, "other_app_tx")
                continue
            # The observer treats TX as an attempted API write. Neither
            # WriteMsgs return code nor on-wire delivery is proven here.
            if service == "A3" and raw[4] >= 0xCA and raw[4] <= 0xCF:
                _event(s, "a3_tx", target, channel, baud, at)
            if service == "B9FB" and raw[4] == 0xCB:
                if channel in s["active"]:
                    s["incomplete"] += 1
                _event(s, "b9fb_tx", target, channel, baud, at)
                if baud == EXPECTED_BAUD[target]:
                    s["active"][channel] = {
                        "target": target, "baud": baud, "frames": [],
                    }
                else:
                    s["active"].pop(channel, None)
                    errors["b9fb_wrong_baud"] += 1
            continue
        if text.startswith("PassThruReadMsgs -> delivered"):
            raw = _native_message(text[len("PassThruReadMsgs -> delivered"):])
            ctx = s["rx_ctx"]
            s["rx_ctx"] = None
            if (raw is None or ctx is None or ctx[1] not in (5, 6)
                    or (ctx[1] == 5 and len(raw) > 12)):
                errors["unattributed_or_bad_rx"] += 1
                s["source_error"] = True
                continue
            channel, protocol, rx_status, baud, at = ctx
            if protocol == 6:
                # P3's reassembled UDS RX may exceed 12 bytes. This
                # D2-only chronology must neither parse it as B9FB nor
                # report valid ISO15765 RX as corrupted source context.
                continue
            if len(raw) != 12:
                if channel in s["active"]:
                    errors["invalid_d2_rx_size"] += 1
                    s["source_error"] = True
                continue
            if rx_status & (0x01 | 0x02 | 0x08):
                errors["rx_indication_not_ecu_frame"] += 1
                continue
            active = s["active"].get(channel)
            if active is None or active["baud"] != baud:
                continue
            can_id = int.from_bytes(raw[:4], "big")
            if can_id not in RESPONSE_IDS[active["target"]]:
                errors["unrelated_rx_on_b9fb_channel"] += 1
                continue
            active["frames"].append((can_id, raw[4:]))
            if len(active["frames"]) > 64:
                s["incomplete"] += 1
                del s["active"][channel]
                continue
            control = raw[4]
            if 0x48 <= control <= 0x4F or (control & 0xF8) == 0xC8:
                try:
                    validate_response(active["frames"], active["target"], 0xFB)
                    # The transport validator intentionally allows a D2 B9
                    # negative reply. This audit must not count a negative
                    # one-frame service reply as a completed positive B9FB.
                    first = active["frames"][0][1]
                    if first[1:4] != bytes((active["target"], 0xF9, 0xFB)):
                        raise ValueError("nonpositive_b9fb_echo")
                except ValueError:
                    s["incomplete"] += 1
                    errors["invalid_b9fb_frame_sequence"] += 1
                else:
                    _event(s, "b9fb_rx_complete", active["target"],
                           channel, baud, at)
                del s["active"][channel]
            continue
        if text.startswith("J2534 CLEAR_RX_BUFFER:"):
            _barrier(s, "clear_rx")
            s["incomplete"] += len(s["active"])
            s["active"].clear()
            s["rx_ctx"] = None

    for pid in list(scopes):
        end(pid, "end_of_log")
    return {
        "format": FORMAT,
        "read_only": True,
        "source": "virtualcar_native_j2534_text",
        "epochs_with_events": len(results),
        "outcome_counts": dict(sorted(Counter(x["outcome"] for x in results).items())),
        "epochs": results,
        "parse_events": dict(sorted(errors.items())),
        "tx_channel_binding_from_native_context": True,
        "contains_payload_data": False,
        "client_b9fb_acceptance_verified": False,
        "a3_security_access_verified": False,
        "xc90_v8_my2009_verified": False,
        "limitations": [
            "Per-PID session and channel alias are native log observations, not proof of ECU authorization.",
            "A3 before B9FB does not imply a successful post-B9FB Hardware transition.",
            "The first later A3 is not necessarily the first app TX, an ECU reply, or proof of causality.",
            "A first later B9F0 event is request-only: neither a CEM response nor a parsed part number is established.",
            "Valid ISO15765 and short-CAN TX/RX remain distinct from D2 frames and do not falsely invalidate native source context.",
            "A later B9FB request before the first later A3 invalidates pairing to the earlier completion.",
            "Native source-local timings do not join historical SectorV report clocks.",
            "App TX observed before J2534 WriteMsgs returns; TX success/on-wire delivery is not confirmed.",
            "Client process name in a log header is untrusted metadata, not independent executable attestation.",
            "No real VIN, CAN bytes, PID, executable name, source file or private operand is exported.",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        if args.source.resolve() == args.output.resolve():
            raise ValueError("same_file")
        if args.source.stat().st_size > MAX_BYTES:
            raise ValueError("source_too_large")
        result = audit(args.source.read_text(encoding="utf-8-sig", errors="replace"))
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
    except (OSError, ValueError, UnicodeError):
        print("Native P2 channel chronology audit rejected source/output",
              file=sys.stderr)
        return 2
    print("PASS: native P2 channel chronology audited; ECU acceptance unknown")
    return 0


if __name__ == "__main__":
    sys.exit(main())
