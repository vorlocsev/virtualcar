#!/usr/bin/env python3
"""Evidence-only audit of Virtual Car and legacy J2534 text traces.

No frame payloads, VINs, PIDs, host names or source paths are written to JSON.
'delivered' means J2534 returned RX, NOT that a diagnostic client accepted an ECU.
This tool never changes the emulator and never creates replay fixtures.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

PREFIX = re.compile(r"^\[PID=([0-9A-Fa-f]{8}) [^\]]+\] (.*)$")
LEGACY_TIME = re.compile(r"^(\d\d):(\d\d):(\d\d),(\d{3})\b")
HEX = re.compile(r"\b[0-9A-Fa-f]{2}\b")
LEGACY_BYTE = re.compile(r"\b0x([0-9A-Fa-f]{1,2})\b")
D2_SERVICES = (0xF0, 0xFB, 0xFC)
MAX_TRANSACTIONS = 20000


def _words(text):
    if "Data = [" in text:
        return bytes(int(x, 16) for x in LEGACY_BYTE.findall(text.split("Data = [", 1)[1]))
    return bytes(int(x, 16) for x in HEX.findall(text))


def _context(text, label):
    if not text.startswith(label):
        return None
    data = _words(text[len(label):])
    if len(data) != 20:
        return None
    return [int.from_bytes(data[i:i+4], "big") for i in range(0, 20, 4)]


def _stamp(line):
    m = LEGACY_TIME.match(line)
    if not m:
        return None
    h, minute, second, ms = map(int, m.groups())
    if h > 23 or minute > 59 or second > 59:
        return None
    return ((h * 60 + minute) * 60 + second) * 1000 + ms


def _request(raw):
    if len(raw) < 5:
        return None
    can_id = int.from_bytes(raw[:4], "big")
    if can_id > 0x1FFFFFFF:
        return None
    data = raw[4:]
    if can_id == 0x000FFFFE:
        if len(data) >= 4 and data[0] == 0xCB and data[2] == 0xB9 and data[3] in D2_SERVICES:
            return ("D2", f"B9{data[3]:02X}", data[1], can_id)
        if data[0] in (0xA3, 0xA6):
            return ("D2", f"{data[0]:02X}", None, can_id)
    if can_id in (0x726, 0x18DA50F1):
        # Identification may use 22 F1xx, but reporting does not imply support.
        if len(data) >= 4 and data[1] == 0x22:
            return ("P3", f"22{data[2]:02X}{data[3]:02X}", None, can_id)
        return ("P3", "other", None, can_id)
    return None


def _id_format(can_id, flags):
    if can_id > 0x7FF or (flags is not None and flags & 0x100):
        return "29bit"
    return "11bit" if flags is not None else "unknown"


def _result(tx):
    if tx["_no_fixture"]:
        status, reason = "no_fixture", "explicit_missing_fixture"
    elif tx["_bad_route"]:
        status, reason = "unsupported", "strict_route_rejected"
    elif tx["_invalid"]:
        status, reason = "partial_rx", "invalid_d2_sequence"
    elif tx["_complete"]:
        status, reason = "delivered", "complete_d2_transport_only"
    elif tx["rx_frames"]:
        status, reason = "partial_rx", "incomplete_or_unverified_transport"
    elif tx["_timeout"]:
        status, reason = "timeout", "j2534_read_timeout_observed"
    else:
        status, reason = "unverified", tx["_end_reason"]
    window = None
    if tx["_start"] is not None and tx["_last"] is not None:
        delta = (tx["_last"] - tx["_start"]) % tx["_time_mod"]
        if delta < 60000 * (1000 if tx["_time_mod"] == 2**32 else 1):
            window = round(delta / (1000 if tx["_time_mod"] == 2**32 else 1), 3)
    return {
        "session": tx["session"], "service": tx["service"],
        "route": tx["route"], "can_id": tx["can_id"],
        "id_format": tx["id_format"], "channel": tx["channel"],
        "protocol": tx["protocol"], "baud_bps": tx["baud_bps"],
        "target": tx["target"], "rx_frames": tx["rx_frames"],
        "off_route_rx": tx["off_route_rx"], "window_ms": window,
        "status": status, "reason": reason,
    }


def audit(lines):
    sessions = {}
    epoch = 0
    results = []
    errors = Counter()

    def scope(pid):
        nonlocal epoch
        if pid not in sessions:
            epoch += 1
            sessions[pid] = {"number": epoch, "active": {},
                             "txctx": None, "rxctx": None, "clearctx": None}
        return sessions[pid]

    def finish(s, channel, why):
        tx = s["active"].pop(channel, None)
        if tx:
            tx["_end_reason"] = why
            results.append(_result(tx))

    def start(s, request, stamp):
        kind, service, target, can_id = request
        ctx = s["txctx"]
        channel = ctx[0] if ctx else None
        finish(s, channel, "superseded_by_tx")
        flags = ctx[2] if ctx else None
        start_at = ctx[4] if ctx else stamp
        mod = 2**32 if ctx else 86400000
        tx = {
            "session": s["number"], "service": service, "route": kind,
            "can_id": f"0x{can_id:08X}" if can_id > 0x7FF else f"0x{can_id:03X}",
            "id_format": _id_format(can_id, flags), "channel": channel,
            "protocol": {5: "CAN", 6: "ISO15765"}.get(ctx[1], "other") if ctx else "unknown",
            "baud_bps": ctx[3] if ctx else None,
            "target": f"0x{target:02X}" if target is not None else None,
            "rx_frames": 0, "off_route_rx": 0,
            "_start": start_at, "_last": None, "_time_mod": mod,
            "_rxid": None, "_seq": 1, "_base": 0x08, "_subblock": False,
            "_complete": False, "_invalid": False,
            "_no_fixture": False, "_bad_route": False,
            "_timeout": False, "_end_reason": "no_delivery_evidence",
        }
        s["active"][channel] = tx

    def active(s, channel):
        if channel in s["active"]:
            return s["active"][channel]
        if channel is None and len(s["active"]) == 1:
            return next(iter(s["active"].values()))
        return None

    def receive(s, raw, stamp):
        ctx = s["rxctx"]
        channel = ctx[0] if ctx else None
        tx = active(s, channel)
        if not tx or len(raw) < 5:
            return
        can_id = int.from_bytes(raw[:4], "big")
        payload = raw[4:]
        if can_id > 0x1FFFFFFF:
            errors["invalid_rx_can_id"] += 1
            return
        if tx["route"] == "P3":
            request_id = int(tx["can_id"], 16)
            expected = 0x72E if request_id == 0x726 else 0x18DAF150
            if can_id != expected:
                tx["off_route_rx"] += 1
                return
            tx["rx_frames"] += 1
            # P3 payload delivery is not validated as UDS success.
            tx["_complete"] = True
        else:
            head = payload[0]
            if tx["_rxid"] is None:
                if tx["service"].startswith("B9") and len(payload) >= 4:
                    opcode = int(tx["service"][-2:], 16)
                    target = int(tx["target"], 16)
                    if head in (0x8F, 0x97) and payload[1:4] == bytes((target, 0xF9, opcode)):
                        tx["_rxid"] = can_id
                        tx["_base"] = 0x10 if head == 0x97 else 0x08
                        tx["rx_frames"] += 1
                    elif head & 0xF8 == 0xC8 and payload[1:4] == bytes((target, 0xF9, opcode)):
                        tx["_rxid"] = can_id
                        tx["rx_frames"] += 1
                        tx["_complete"] = True
                    else:
                        tx["off_route_rx"] += 1
                else:
                    # A3/A6 have no authenticated response framing yet.
                    tx["off_route_rx"] += 1
            elif can_id != tx["_rxid"] or tx["_complete"]:
                tx["off_route_rx"] += 1
            else:
                tx["rx_frames"] += 1
                if 0x48 <= head <= 0x4F:
                    tx["_complete"] = True
                elif head & 0xF8 == 0x50:
                    tx["_subblock"] = True
                elif tx["_subblock"] and head == 0x8F and len(payload) >= 4 and payload[1:4] == bytes((int(tx["target"], 16), 0xF9, int(tx["service"][-2:], 16))):
                    tx["_subblock"] = False
                elif head == (tx["_base"] | tx["_seq"]):
                    tx["_seq"] = (tx["_seq"] + 1) & 7
                    tx["_subblock"] = False
                else:
                    tx["_invalid"] = True
        at = ctx[4] if ctx else stamp
        if at is not None and tx["_time_mod"] == (2**32 if ctx else 86400000):
            tx["_last"] = at

    for line in lines:
        if "=== SECTORV VIRTUALCAR SESSION " in line:
            for s in sessions.values():
                for ch in list(s["active"]):
                    finish(s, ch, "session_boundary")
            sessions.clear()
            continue
        m = PREFIX.match(line)
        pid, text = (m.group(1), m.group(2)) if m else ("legacy", line)
        s = scope(pid)
        stamp = _stamp(line)
        if "PassThruOpen ->" in text:
            for ch in list(s["active"]):
                finish(s, ch, "new_connection")
            s["txctx"] = s["rxctx"] = s["clearctx"] = None
        txctx = _context(text, "TX context channel/protocol/flags/baud/time-us (BE)")
        if txctx is not None:
            s["txctx"] = txctx
            continue
        rxctx = _context(text, "RX context channel/protocol/status/baud/time-us (BE)")
        if rxctx is not None:
            s["rxctx"] = rxctx
            continue
        clearctx = _context(text, "CLEAR_RX context channel/protocol/flags/baud/time-us (BE)")
        if clearctx is not None:
            s["clearctx"] = clearctx
            continue
        if "TX (app request)" in text or "PassThruWriteMsgs() msg" in text:
            marker = "TX (app request)" if "TX (app request)" in text else "Data = ["
            raw = _words(text.split(marker, 1)[1])
            req = _request(raw)
            if req:
                start(s, req, stamp)
            else:
                # Unrelated TX ends a legacy single-channel observation,
                # but not other channels' in-flight requests.
                ch = s["txctx"][0] if s["txctx"] else None
                finish(s, ch, "superseded_by_other_tx")
            s["txctx"] = None
            continue
        if "PassThruReadMsgs -> delivered" in text or "PassThruReadMsgs() msg" in text:
            marker = "PassThruReadMsgs -> delivered" if "PassThruReadMsgs -> delivered" in text else "Data = ["
            receive(s, _words(text.split(marker, 1)[1]), stamp)
            s["rxctx"] = None
            continue
        if "P2 D2 read command: no validated response fixture" in text or "P2 D2 command: no recorded ECU fixture" in text:
            tx = active(s, None)
            if tx:
                tx["_no_fixture"] = True
        if "P2 D2 strict route rejected" in text:
            tx = active(s, None)
            if tx:
                tx["_bad_route"] = True
        if "P3 CEM " in text and " unavailable" in text:
            tx = active(s, None)
            if tx:
                tx["_no_fixture"] = True
        if "PassThruReadMsgs timeout:" in text:
            dat = _words(text.split("(BE)", 1)[-1])
            if len(dat) == 12:
                ch = int.from_bytes(dat[:4], "big")
                tx = active(s, ch)
                if tx:
                    tx["_timeout"] = True
        if "J2534 CLEAR_RX_BUFFER:" in text:
            ch = s["clearctx"][0] if s["clearctx"] else None
            tx = active(s, ch)
            if tx:
                finish(s, ch, "clear_rx_buffer")
            s["clearctx"] = None
        if "PassThruClose" in text or "PassThruDisconnect" in text:
            for ch in list(s["active"]):
                finish(s, ch, "connection_closed")
            s["txctx"] = s["rxctx"] = None
    for s in sessions.values():
        for ch in list(s["active"]):
            finish(s, ch, "end_of_log")
    if len(results) > MAX_TRANSACTIONS:
        raise ValueError("too many transactions to audit safely")
    statuses = Counter(x["status"] for x in results)
    return {
        "format": "virtualcar-j2534-evidence-v1", "read_only": True,
        "contains_payload_data": False, "replay_approved": False,
        "notes": [
            "J2534 RX delivery does not prove diagnostic-client ECU acceptance.",
            "Legacy logs without channel, flags or timestamps leave route metadata unknown.",
            "No A3/A6 or P3 positive ECU identity is inferred without a verified fixture.",
            "Window is observed first-to-last delivered RX, not a claimed ECU processing duration.",
        ],
        "transactions": results,
        "counts": dict(sorted(statuses.items())),
        "parse_errors": dict(sorted(errors.items())),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Privacy-safe, read-only J2534 evidence audit")
    parser.add_argument("log", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.log.resolve() == args.output.resolve():
        parser.error("output must not overwrite input")
    try:
        with args.log.open("r", encoding="utf-8-sig", errors="replace") as stream:
            report = audit(stream)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Audited {len(report['transactions'])} read-only probes; "
          f"statuses: {report['counts']}; replay approved: NO")


if __name__ == "__main__":
    main()
