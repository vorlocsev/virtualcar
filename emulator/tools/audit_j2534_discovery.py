#!/usr/bin/env python3
"""Evidence-only audit of Virtual Car, legacy and VIDA J2534 text traces.

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
# Observed CEM diagnostic route candidates, not a model-year compatibility map.
D2_A6_RESPONSE_IDS = {
    "0x40": (0x00800003,),
    "0x50": (0x01000003, 0x01200003),
}


def _words(text):
    if "Data = [" in text or LEGACY_BYTE.search(text):
        return bytes(int(x, 16) for x in LEGACY_BYTE.findall(text.split("Data = [", 1)[-1]))
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
        # D2 CAN requests carry C8 + significant-byte count, target, service.
        # Attribute only known CEM targets and complete classic-CAN requests;
        # parameters/padding remain private and no response meaning is inferred.
        if (3 <= len(data) <= 8 and 0xCA <= data[0] <= 0xCF
                and len(data) >= data[0] - 0xC8 + 1
                and data[1] in (0x40, 0x50) and data[2] in (0xA3, 0xA6)):
            return ("D2", f"{data[2]:02X}", data[1], can_id)
        # Preserve historical traces which logged the service without a prefix.
        if data[0] in (0xA3, 0xA6):
            return ("D2", f"{data[0]:02X}", None, can_id)
    if can_id in (0x726, 0x18DA50F1):
        # CAN exposes a Single Frame PCI, ISO15765 J2534 exposes raw UDS.
        # A Flow Control frame is transport, never a fresh diagnostic request.
        if data[0] & 0xF0 == 0x30:
            return None
        if len(data) >= 3 and data[0] == 0x22:
            return ("P3", f"22{data[1]:02X}{data[2]:02X}", None, can_id)
        if len(data) >= 4 and 3 <= data[0] <= 7 and data[1] == 0x22:
            return ("P3", f"22{data[2]:02X}{data[3]:02X}", None, can_id)
        return ("P3", "other", None, can_id)
    return None


def _flow_control(raw):
    """A CAN ISO-TP FC preserves an in-progress P3 transaction."""
    if len(raw) < 5:
        return False
    can_id = int.from_bytes(raw[:4], "big")
    return can_id in (0x726, 0x18DA50F1) and raw[4] & 0xF0 == 0x30


def _p3_uds(tx, head, uds_length):
    """Evaluate only UDS header and declared length, never identity data."""
    if len(head) < 3:
        tx["_invalid"] = True
    elif head[0] == 0x7F and head[1] == 0x22:
        if head[2] == 0x78:
            # NRC responsePending is not a terminal rejection or ECU identity.
            tx["_p3_pending"] += 1
        else:
            tx["_p3_negative"] = True
    elif (tx["service"].startswith("22") and tx["service"] != "other"
          and head[:3] == bytes.fromhex("62" + tx["service"][2:])):
        if uds_length <= 3:
            # 0x62 + DID without a data-record byte proves no complete DID.
            tx["_p3_missing_data"] = True
        else:
            tx["_complete"] = True
    else:
        tx["_p3_mismatch"] = True


def _p3_frame(tx, payload, protocol):
    """Track raw CAN ISO-TP, or already reassembled J2534 ISO15765 RX."""
    if (tx["_complete"] or tx["_p3_negative"] or tx["_p3_mismatch"]
            or tx["_p3_missing_data"] or tx["_invalid"]):
        tx["off_route_rx"] += 1
        return
    if protocol == "ISO15765":
        tx["rx_frames"] += 1
        _p3_uds(tx, payload[:3], len(payload))
        return
    head = payload[0]
    kind = head & 0xF0
    if kind == 0x00 and tx["_p3_total"] is None:
        size = head & 0x0F
        tx["rx_frames"] += 1
        if size < 3 or size > 7 or size > len(payload) - 1:
            tx["_invalid"] = True
        else:
            _p3_uds(tx, payload[1:4], size)
    elif kind == 0x10 and tx["_p3_total"] is None:
        tx["rx_frames"] += 1
        if len(payload) < 8:
            tx["_invalid"] = True
            return
        total = ((head & 0x0F) << 8) | payload[1]
        if total <= 7 or total > 4095:
            tx["_invalid"] = True
            return
        tx["_p3_total"] = total
        tx["_p3_received"] = 6
        tx["_p3_sequence"] = 1
        tx["_p3_header"] = payload[2:5]  # UDS header only, never VIN.
    elif kind == 0x20 and tx["_p3_total"] is not None:
        tx["rx_frames"] += 1
        if (head & 0x0F) != tx["_p3_sequence"]:
            tx["_invalid"] = True
            return
        remaining = tx["_p3_total"] - tx["_p3_received"]
        chunk = min(len(payload) - 1, remaining)
        if chunk <= 0 or (chunk < 7 and chunk < remaining):
            tx["_invalid"] = True
            return
        tx["_p3_received"] += chunk
        tx["_p3_sequence"] = (tx["_p3_sequence"] + 1) & 0x0F
        if tx["_p3_received"] >= tx["_p3_total"]:
            _p3_uds(tx, tx["_p3_header"], tx["_p3_total"])
    else:
        tx["rx_frames"] += 1
        tx["_invalid"] = True


def _id_format(can_id, flags):
    if can_id > 0x7FF or (flags is not None and flags & 0x100):
        return "29bit"
    return "11bit" if flags is not None else "unknown"


def _a6_request_identifier(raw):
    """Retain only the two-byte echo key for the documented CD ... A6 ... 01 shape."""
    data = raw[4:]
    if (6 <= len(data) <= 8 and data[0] == 0xCD and data[2] == 0xA6
            and data[5] == 1):
        return data[3:5]
    return None


def _a6_frame(tx, can_id, payload, ctx):
    """Attribute a single-frame E6 without reading or exporting its value bytes."""
    if (tx["_a6_identifier"] is None or tx["protocol"] not in ("CAN", "unknown")
            or can_id not in D2_A6_RESPONSE_IDS.get(tx["target"], ())
            or (ctx is not None and (ctx[1] != 5
                or (tx["baud_bps"] is not None and ctx[3] != tx["baud_bps"])))
            or len(payload) < 3
            or payload[1:3] != bytes((int(tx["target"], 16), 0xE6))
            or (len(payload) >= 4 and not tx["_a6_identifier"].startswith(payload[3:5]))
            or tx["_complete"] or tx["_a6_error"]):
        tx["off_route_rx"] += 1
        return False
    tx["rx_frames"] += 1
    tx["_rxid"] = can_id
    count = payload[0] & 7
    if not 0xC8 <= payload[0] <= 0xCF:
        tx["_a6_error"] = "unsupported_d2_a6_framing"
    elif len(payload) > 8 or len(payload) < 5 or count < 4 or len(payload) < count + 1:
        tx["_a6_error"] = "invalid_d2_a6_length"
    elif count == 4:
        # Target + E6 + identifier without a data-record byte is not complete.
        tx["_a6_error"] = "missing_d2_a6_data"
    else:
        tx["_complete"] = True
    return True


def _result(tx):
    if tx["_source_error"]:
        status, reason = "unverified", tx["_source_error"]
    elif tx["_bad_route"]:
        status, reason = "unsupported", "strict_route_rejected"
    elif tx["_no_fixture"]:
        status, reason = "no_fixture", "explicit_missing_fixture"
    elif tx["_a6_error"]:
        status, reason = "partial_rx", tx["_a6_error"]
    elif tx["_invalid"]:
        status, reason = "partial_rx", ("invalid_iso_tp_framing" if tx["route"] == "P3" else "invalid_d2_sequence")
    elif tx["_p3_negative"]:
        status, reason = "negative_response", "uds_negative_response_observed"
    elif tx["_p3_missing_data"]:
        status, reason = "partial_rx", "missing_uds_identifier_data"
    elif tx["_p3_mismatch"]:
        status, reason = "unverified", "uds_response_does_not_match_request"
    elif tx["_complete"]:
        status = "delivered"
        reason = ("p3_uds_transport_only" if tx["route"] == "P3" else
                  "d2_a6_single_frame_transport_only" if tx["service"] == "A6" else
                  "complete_d2_transport_only")
    elif tx["_p3_pending"]:
        if tx["_timeout"]:
            status, reason = "timeout", "j2534_timeout_after_response_pending"
        else:
            status, reason = "unverified", "uds_response_pending_only"
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
        "response_pending_frames": tx["_p3_pending"],
        "off_route_rx": tx["off_route_rx"], "window_ms": window,
        "status": status, "reason": reason,
    }


_VIDA_LINE = re.compile(
    r"^(?:\d{2}:\d{2}:\d{2},\d{3}\s+)?"
    r"\[J2534ChannelMana\s*\]\[([0-9A-Fa-f]{1,8})\]\[[^\]]+\]\s*(.*)$")
_VIDA_LOGGER = re.compile(
    r"^(?:\d{2}:\d{2}:\d{2},\d{3}\s+)?\[[^\]]+\]\[[0-9A-Fa-f]{1,8}\]\[[^\]]+\]")
_VIDA_NUMBER = r"(?:0[xX][0-9A-Fa-f]+|[0-9]+)"
_VIDA_CONNECT = re.compile(
    r"^PassThruConnect\(\s*(" + _VIDA_NUMBER + r")\s*,\s*("
    + _VIDA_NUMBER + r")\s*,\s*(" + _VIDA_NUMBER + r")\s*,\s*("
    + _VIDA_NUMBER + r")\s*,\s*(" + _VIDA_NUMBER + r")\s*\)\s*$")
_VIDA_IO = re.compile(
    r"^PassThru(Read|Write)Msgs\(\s*([0-9]+)\s*,\s*PASSTHRU_MSG\s*,"
    r"\s*([0-9]+)\s*,\s*([0-9]+)\s*\)(?:\s.*)?$")
_VIDA_PACKET = re.compile(r"^(--->|<---)\s*\(([0-9]+)\)\s*(.*)$")
_VIDA_ERROR = re.compile(
    r"^J2534 function:PassThru(ReadMsgs|WriteMsgs|Connect) failed with return value:(ERR_[A-Z_]+)\b")
_VIDA_BOUNDARY = re.compile(r"^Starting new logsession: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s*$")


def _vida_number(text):
    return int(text, 16 if text.lower().startswith("0x") else 10)


class _VidaText:
    """Bind VIDA's comma-byte records to calls in the same logged thread.

    Only explicit Connect metadata is used. Client-level VehComm messages,
    adapter names and inferred vehicle identity never become transport evidence.
    """

    def __init__(self, errors):
        self.errors = errors
        self.reset()

    def reset(self):
        self.channels = {}
        self.pending = {}

    def _forget_channel(self, channel):
        self.channels.pop(channel, None)
        self.pending = {t: p for t, p in self.pending.items() if p["channel"] != channel}

    def feed(self, line):
        if _VIDA_BOUNDARY.fullmatch(line.strip()):
            self.reset()
            return {"kind": "boundary"}
        match = _VIDA_LINE.match(line.rstrip("\r\n"))
        if not match:
            return {"kind": "ignore"} if _VIDA_LOGGER.match(line) else None
        thread, text = match.groups()
        clock = _stamp(line)
        event = {"kind": "ignore", "stamp": clock}
        connect = _VIDA_CONNECT.fullmatch(text)
        if connect:
            device, protocol, flags, baud, channel = map(_vida_number, connect.groups())
            if baud == 0 or any(x > 0xFFFFFFFF for x in (device, protocol, flags, baud, channel)):
                self.errors["vida_invalid_connect"] += 1
                self.pending.pop(thread, None)
                if channel <= 0xFFFFFFFF:
                    self._forget_channel(channel)
                    return {"kind": "connect_failed", "channel": channel}
                return event
            previous = self.channels.get(channel)
            self._forget_channel(channel)
            if len(self.channels) >= 256 or len(self.pending) >= 256:
                raise ValueError("too many VIDA channels or threads to audit safely")
            metadata = {"channel": channel, "protocol": protocol,
                        "flags": flags, "baud": baud, "device": device}
            if previous is not None and previous["device"] != device:
                # IO calls print ChannelID only. A collision between devices
                # cannot be disambiguated from this text format.
                self.errors["vida_ambiguous_channel"] += 1
                metadata.update(protocol=None, flags=None, baud=None, device=None)
            self.channels[channel] = metadata
            self.pending[thread] = {"kind": "connect", "channel": channel}
            return {"kind": "connect", "channel": channel}
        if text.startswith("PassThruConnect("):
            self.errors["vida_invalid_connect"] += 1
            self.reset()
            return {"kind": "format_boundary"}
        call = _VIDA_IO.fullmatch(text)
        if call:
            method, channel, count, timeout = call.groups()
            channel, count, timeout = map(int, (channel, count, timeout))
            self.pending.pop(thread, None)
            if channel > 0xFFFFFFFF or timeout > 0xFFFFFFFF or not 1 <= count <= 4096:
                self.errors["vida_invalid_call"] += 1
                return event
            if len(self.channels) > 256 or len(self.pending) >= 256:
                raise ValueError("too many VIDA channels or threads to audit safely")
            self.pending[thread] = {"kind": "rx" if method == "Read" else "tx",
                                    "channel": channel, "count": count, "next": 0,
                                    "wait_ms": timeout}
            return event
        if text.startswith(("PassThruReadMsgs(", "PassThruWriteMsgs(")):
            self.errors["vida_invalid_call"] += 1
            self.pending.pop(thread, None)
            return {"kind": "unbound_tx"} if text.startswith("PassThruWriteMsgs(") else event
        error = _VIDA_ERROR.match(text)
        if error:
            method, code = error.groups()
            pending = self.pending.pop(thread, None)
            kind = {"ReadMsgs": "rx", "WriteMsgs": "tx", "Connect": "connect"}[method]
            if pending is None or pending["kind"] != kind:
                self.errors["vida_unbound_call_error"] += 1
                return event
            channel = pending["channel"]
            if kind == "connect":
                self._forget_channel(channel)
                return {"kind": "connect_failed", "channel": channel}
            if kind == "tx":
                return {"kind": "write_failed", "channel": channel}
            if code == "ERR_TIMEOUT" or (code == "ERR_BUFFER_EMPTY" and pending["wait_ms"] > 0):
                return {"kind": "timeout", "channel": channel}
            return event
        disconnect = re.fullmatch(r"PassThruDisconnect\(\s*([0-9]+)\s*\)\s*", text)
        if disconnect:
            channel = int(disconnect[1])
            self._forget_channel(channel)
            return {"kind": "disconnect", "channel": channel}
        if re.fullmatch(r"PassThruClose\(\s*(?:[0-9]+)?\s*\)\s*", text):
            self.reset()
            return {"kind": "close"}
        clear = re.fullmatch(
            r"PassThruIoctl\(\s*([0-9]+)\s*,\s*(?:CLEAR_RX_BUFFER|0[xX]0*8|8)\s*,.*\)\s*", text)
        if clear:
            channel = int(clear[1])
            self.pending = {t: p for t, p in self.pending.items() if p["channel"] != channel}
            return {"kind": "clear", "channel": channel}
        if text == "J2534Channel::ClearRxBuffer()":
            # No channel is printed; do not borrow one from another call/thread.
            self.pending.clear()
            return {"kind": "clear_all"}
        packet = _VIDA_PACKET.fullmatch(text)
        if packet:
            direction, index, data = packet.groups()
            kind = "tx" if direction == "--->" else "rx"
            pending = self.pending.get(thread)
            if (pending is None or pending["kind"] != kind
                    or int(index) != pending["next"] or int(index) >= pending["count"]):
                self.errors["vida_unbound_payload"] += 1
                self.pending.pop(thread, None)
                return {"kind": "unbound_tx"} if kind == "tx" else event
            # Parsing whole tokens prevents truncated or decorated hex from
            # silently turning into a plausible positive response.
            tokens = data.split(",")
            if tokens and not tokens[-1].strip():
                tokens.pop()
            # ID-only RX records contain no application bytes; receive() ignores
            # them, just as it does in the existing native text format.
            minimum = 4 if kind == "rx" else 5
            if (not minimum <= len(tokens) <= 4128
                    or any(not re.fullmatch(r"[0-9A-Fa-f]{2}", x.strip()) for x in tokens)):
                self.errors["vida_malformed_payload"] += 1
                self.pending.pop(thread, None)
                return {"kind": "malformed_" + kind, "channel": pending["channel"]}
            pending["next"] += 1
            channel = pending["channel"]
            metadata = self.channels.get(channel, {"channel": channel,
                       "protocol": None, "flags": None, "baud": None})
            return {"kind": kind, "channel": channel, "metadata": metadata,
                    "raw": bytes(int(x.strip(), 16) for x in tokens), "stamp": clock}
        return event



def audit(lines):
    sessions = {}
    epoch = 0
    results = []
    errors = Counter()
    vida = _VidaText(errors)

    def scope(pid):
        nonlocal epoch
        if pid not in sessions:
            epoch += 1
            sessions[pid] = {"number": epoch, "active": {},
                             "txctx": None, "rxctx": None, "clearctx": None,
                             "last_tx_channel": None, "disconnect_channel": None}
        return sessions[pid]

    def finish(s, channel, why):
        tx = s["active"].pop(channel, None)
        if tx:
            tx["_end_reason"] = why
            results.append(_result(tx))

    def start(s, request, stamp, raw, metadata=None):
        kind, service, target, can_id = request
        ctx = s["txctx"]
        channel = metadata["channel"] if metadata is not None else ctx[0] if ctx else None
        s["last_tx_channel"] = channel
        finish(s, channel, "superseded_by_tx")
        flags = metadata["flags"] if metadata is not None else ctx[2] if ctx else None
        protocol = metadata["protocol"] if metadata is not None else ctx[1] if ctx else None
        baud = metadata["baud"] if metadata is not None else ctx[3] if ctx else None
        start_at = ctx[4] if ctx else stamp
        mod = 2**32 if ctx else 86400000
        tx = {
            "session": s["number"], "service": service, "route": kind,
            "can_id": f"0x{can_id:08X}" if can_id > 0x7FF else f"0x{can_id:03X}",
            "id_format": _id_format(can_id, flags), "channel": channel,
            "protocol": {5: "CAN", 6: "ISO15765"}.get(protocol, "other") if protocol is not None else "unknown",
            "baud_bps": baud,
            "target": f"0x{target:02X}" if target is not None else None,
            "rx_frames": 0, "off_route_rx": 0,
            "_start": start_at, "_last": None, "_time_mod": mod,
            "_rxid": None, "_seq": 1, "_base": 0x08, "_subblock": False,
            "_complete": False, "_invalid": False,
            "_source_error": None,
            "_a6_identifier": _a6_request_identifier(raw) if service == "A6" else None,
            "_a6_error": None,
            "_no_fixture": False, "_bad_route": False,
            "_timeout": False, "_end_reason": "no_delivery_evidence",
            "_p3_total": None, "_p3_received": 0, "_p3_sequence": 1,
            "_p3_header": b"", "_p3_negative": False, "_p3_mismatch": False,
            "_p3_missing_data": False, "_p3_pending": 0,
        }
        s["active"][channel] = tx

    def active(s, channel):
        if channel in s["active"]:
            return s["active"][channel]
        if channel is None and len(s["active"]) == 1:
            return next(iter(s["active"].values()))
        return None

    def receive(s, raw, stamp, metadata=None):
        ctx = s["rxctx"]
        channel = metadata["channel"] if metadata is not None else ctx[0] if ctx else None
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
            # The protocol is from the requesting channel, not an unrelated RX.
            # ISO15765 J2534 returns reassembled UDS; CAN returns PCI frames.
            if metadata is not None and tx["protocol"] not in ("CAN", "ISO15765"):
                tx["rx_frames"] += 1
                tx["_source_error"] = "vida_unknown_transport"
            else:
                _p3_frame(tx, payload, tx["protocol"])
        elif tx["service"] == "A6":
            route_ctx = ([channel, metadata["protocol"], None, metadata["baud"], None]
                         if metadata is not None and metadata["protocol"] is not None else ctx)
            if not _a6_frame(tx, can_id, payload, route_ctx):
                return
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
                    # A3 and other opaque probes remain outside validated RX framing.
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
        event = vida.feed(line)
        if event is not None:
            kind = event["kind"]
            if kind == "ignore":
                continue
            if kind == "boundary":
                s = sessions.pop("vida", None)
                if s:
                    for ch in list(s["active"]):
                        finish(s, ch, "session_boundary")
                continue
            s = scope("vida")
            if kind in ("close", "clear_all", "unbound_tx", "format_boundary"):
                for ch in list(s["active"]):
                    finish(s, ch, {"close": "connection_closed",
                                  "clear_all": "clear_rx_buffer_unknown_channel",
                                  "unbound_tx": "unattributed_tx", "format_boundary": "vida_invalid_connect"}[kind])
            elif kind in ("connect", "connect_failed", "disconnect", "write_failed", "clear", "malformed_tx"):
                finish(s, event["channel"], {
                    "connect": "channel_reconnected", "connect_failed": "connection_failed",
                    "disconnect": "channel_disconnected", "write_failed": "j2534_write_failed",
                    "clear": "clear_rx_buffer", "malformed_tx": "malformed_tx"}[kind])
            elif kind == "malformed_rx":
                tx = active(s, event["channel"])
                if tx:
                    tx["_source_error"] = "vida_malformed_rx_record"
            elif kind == "timeout":
                tx = active(s, event["channel"])
                if tx:
                    tx["_timeout"] = True
            elif kind == "tx":
                request = _request(event["raw"])
                if request:
                    start(s, request, event["stamp"], event["raw"], event["metadata"])
                elif event["metadata"]["protocol"] != 5 or not _flow_control(event["raw"]):
                    finish(s, event["channel"], "superseded_by_other_tx")
            elif kind == "rx":
                receive(s, event["raw"], event["stamp"], event["metadata"])
            continue
        if "=== SECTORV VIRTUALCAR SESSION " in line:
            vida.reset()
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
            s["last_tx_channel"] = s["disconnect_channel"] = None
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
        if text.startswith("PassThruDisconnect channel (BE)"):
            data = _words(text.split("(BE)", 1)[-1])
            if len(data) == 4:
                s["disconnect_channel"] = int.from_bytes(data, "big")
            continue
        if "TX (app request)" in text or "PassThruWriteMsgs() msg" in text:
            marker = "TX (app request)" if "TX (app request)" in text else "Data = ["
            raw = _words(text.split(marker, 1)[1])
            req = _request(raw)
            if req:
                start(s, req, stamp, raw)
            elif _flow_control(raw):
                # Flow Control belongs to an ongoing CAN ISO-TP response.
                # It must not supersede a diagnostic request.
                pass
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
            tx = active(s, s["last_tx_channel"])
            if tx:
                tx["_no_fixture"] = True
        if "P2 D2 strict route rejected" in text:
            tx = active(s, s["last_tx_channel"])
            if tx:
                tx["_bad_route"] = True
        if "P3 CEM " in text and " unavailable" in text:
            tx = active(s, s["last_tx_channel"])
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
        if text.startswith("PassThruClose"):
            for ch in list(s["active"]):
                finish(s, ch, "connection_closed")
            s["txctx"] = s["rxctx"] = None
            s["last_tx_channel"] = s["disconnect_channel"] = None
        elif text.startswith("PassThruDisconnect"):
            ch = s["disconnect_channel"]
            if ch is None and len(s["active"]) == 1:
                ch = next(iter(s["active"]))
            if ch in s["active"]:
                finish(s, ch, "channel_disconnected")
            s["disconnect_channel"] = None
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
            "negative_response identifies a final UDS rejection, not successful ECU discovery.",
            "UDS NRC 0x78 is nonterminal; pending-only probes stay unverified unless a read timeout is logged.",
            "A positive ReadDataByIdentifier header requires at least one data-record byte.",
            "P3 transport checks parse only UDS headers and ISO-TP lengths, not VIN or identity authenticity.",
            "A6 delivery validates a single-frame E6 echo and length only; no parameter value or normal-mode state is decoded.",
            "A6 route candidates are limited to observed CEM IDs; unknown routes and non-CD ... 01 request shapes stay unverified.",
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
