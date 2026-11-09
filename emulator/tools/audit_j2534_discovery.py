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


def _context(text, label, strict=False):
    if not text.startswith(label):
        return None
    if strict and not re.fullmatch(r"(?:[0-9A-Fa-f]{2}\s+){19}[0-9A-Fa-f]{2}", text[len(label):].strip()):
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


def _request(raw, include_obd=False):
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
    if include_obd:
        if can_id in (0x7DF, 0x7E0) and (data == b"\x09\x02" or
                (3 <= len(data) <= 8 and data[:3] == b"\x02\x09\x02"
                 and not any(data[3:]))):
            return ("OBD", "0902", None, can_id)
        if can_id == 0x18DB33F1 and data == b"\x3E\x80":
            return ("OBD", "3E80", None, can_id)
    return None


def _flow_control(raw, include_obd=False):
    """A CAN ISO-TP FC preserves P3 or opt-in OBD transport."""
    if len(raw) < 5:
        return False
    can_id = int.from_bytes(raw[:4], "big")
    if include_obd and can_id == 0x7E0:
        return 7 <= len(raw) <= 12 and raw[4] in (0x30, 0x31, 0x32)
    return can_id in (0x726, 0x18DA50F1) and raw[4] & 0xF0 == 0x30


def _p3_uds(tx, head, uds_length):
    """Evaluate only application headers and declared length, never identity data."""
    if tx["route"] == "OBD":
        if len(head) < 3:
            tx["_invalid"] = True
        elif head[:2] == b"\x7F\x09":
            if head[2] == 0x78:
                tx["_p3_pending"] += 1
            else:
                tx["_p3_negative"] = True
        elif head == b"\x49\x02\x01":
            # Header + record index + 17 bytes. No VIN value/checksum decoding.
            if uds_length == 20:
                tx["_complete"] = True
            else:
                tx["_p3_missing_data"] = True
        else:
            tx["_p3_mismatch"] = True
        return
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


def _p3_expected_header(tx, data):
    """Identify only the expected SID/DID or an NRC, never ECU identity bytes."""
    if len(data) < 3:
        return False
    if data[:2] == b"\x7F\x22":
        return True
    return (tx["service"].startswith("22") and len(tx["service"]) == 6
            and data[:3] == bytes.fromhex("62" + tx["service"][2:]))


def _p3_frame(tx, payload, protocol):
    """Track raw CAN ISO-TP, or already reassembled J2534 ISO15765 RX."""
    if (tx["_complete"] or tx["_p3_negative"] or tx["_p3_mismatch"]
            or tx["_p3_missing_data"] or tx["_invalid"]
            or tx["_p3_transport_error"]):
        tx["off_route_rx"] += 1
        return
    if protocol == "ISO15765":
        # With J2534 ISO15765, RX carries UDS only, not an ISO-TP PCI byte.
        # Distinguish an incorrectly exposed CAN SF/FF from a malformed
        # application response. Only match the expected DID or NRC header.
        if len(payload) == 8 and (
            (3 <= payload[0] <= 7 and
             _p3_expected_header(tx, payload[1:4])) or
            ((payload[0] & 0xF0) == 0x10 and
             (((payload[0] & 0x0F) << 8) | payload[1]) > 7 and
             _p3_expected_header(tx, payload[2:5]))
        ):
            tx["rx_frames"] += 1
            tx["_p3_transport_error"] = "p3_can_pci_on_iso15765_channel"
            return
        tx["rx_frames"] += 1
        _p3_uds(tx, payload[:3], len(payload))
        return
    if protocol == "CAN" and _p3_expected_header(tx, payload[:3]):
        # A complete UDS message on a raw CAN channel has no ISO-TP PCI.
        # The capture format or channel metadata is inconsistent; do not
        # attribute this to an actual malformed ECU frame.
        tx["rx_frames"] += 1
        tx["_p3_transport_error"] = "p3_uds_without_pci_on_can_channel"
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
        status, reason = "partial_rx", (
            "d2_classic_can_rx_size_invalid" if tx["_d2_rx_size_invalid"]
            else "d2_13frame_final_marker_mismatch" if tx["_d2_final_marker_mismatch"]
            else "invalid_iso_tp_framing" if tx["route"] in ("P3", "OBD")
            else "invalid_d2_sequence")
    elif tx["_p3_transport_error"]:
        status, reason = "unverified", tx["_p3_transport_error"]
    elif tx["_p3_negative"]:
        status, reason = "negative_response", ("obd_negative_response_observed" if tx["route"] == "OBD" else "uds_negative_response_observed")
    elif tx["_p3_missing_data"]:
        status, reason = "partial_rx", ("invalid_obd_vin_length" if tx["route"] == "OBD" else "missing_uds_identifier_data")
    elif tx["_p3_mismatch"]:
        status, reason = "unverified", ("obd_response_does_not_match_request" if tx["route"] == "OBD" else "uds_response_does_not_match_request")
    elif tx["_complete"] and tx["_ambiguous_f114_retry"]:
        # Two identical in-flight ReadDataByIdentifier requests cannot be
        # distinguished by CAN ID, UDS DID or J2534 RX content alone.
        status, reason = "unverified", "identical_f114_retry_unattributable"
    elif tx["_complete"]:
        status = "delivered"
        reason = ("obd_vin_header_length_transport_only" if tx["route"] == "OBD" else
                  "p3_uds_transport_only" if tx["route"] == "P3" else
                  "d2_a6_single_frame_transport_only" if tx["service"] == "A6" else
                  "complete_d2_transport_only")
    elif tx["route"] == "OBD" and tx["service"] == "3E80":
        status, reason = "unverified", "suppressed_response_request_not_ecu_discovery"
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
    result = {
        "session": tx["session"], "service": tx["service"],
        "route": tx["route"], "can_id": tx["can_id"],
        "id_format": tx["id_format"], "channel": tx["channel"],
        "protocol": tx["protocol"], "baud_bps": tx["baud_bps"],
        "target": tx["target"], "rx_frames": tx["rx_frames"],
        "response_pending_frames": tx["_p3_pending"],
        "off_route_rx": tx["off_route_rx"], "window_ms": window,
        "status": status, "reason": reason,
        "request_origin": tx["_request_origin"],
    }
    if tx["route"] == "OBD":
        result["start_indications"] = tx["_obd_starts"]
        result["repeat_index"] = tx["_obd_repeat"]
        result["ended_by"] = tx["_end_reason"]
        result["request_line"] = tx["_obd_request_line"]
        result["last_rx_line"] = tx["_obd_last_rx_line"]
        result["client_result"] = "client_result_unknown"
        result["vehicle_identity_verified"] = False
    return result


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



def _native_event(text):
    """Count exact source markers, not inferred calls, channels or filter effects."""
    exact = {"PassThruOpen -> device 1": "open", "PassThruClose": "close",
             "PassThruDisconnect": "disconnect",
             "J2534 CLEAR_RX_BUFFER: queued and staged D2 dropped": "clear_rx"}
    if text in exact:
        return exact[text]
    for label, size, name in (
            ("J2534 Connect result protocol/flags/baud/status (BE)", 16, "connect_result"),
            ("J2534 SET_CONFIG channel/parameter/value/applied (BE)", 16, "set_config"),
            ("PassThruStartMsgFilter type / id (BE)", 8, "filter_start")):
        if text.startswith(label) and re.fullmatch(
                r"(?:[0-9A-Fa-f]{2}\s+){%d}[0-9A-Fa-f]{2}" % (size - 1),
                text[len(label):].strip()):
            return name
    if text.startswith("TX (app request) "):
        return "tx_record"
    if text.startswith("J2534 periodic TX (read-only simulator) "):
        return "periodic_scheduler_tx_record"
    if text.startswith("PassThruReadMsgs -> delivered "):
        return "rx_delivery_record"
    return None


def audit(lines, *, include_obd=False):
    sessions = {}
    epoch = 0
    results = []
    errors = Counter()
    vida = _VidaText(errors)
    observed_events = Counter()

    def scope(pid):
        nonlocal epoch
        if pid not in sessions:
            epoch += 1
            sessions[pid] = {"number": epoch, "active": {},
                             "txctx": None, "periodicctx": None,
                             "rxctx": None, "clearctx": None,
                             "last_tx_channel": None, "disconnect_channel": None,
                             "obd_repeats": {}}
        return sessions[pid]

    def finish(s, channel, why):
        tx = s["active"].pop(channel, None)
        if tx:
            tx["_end_reason"] = why
            results.append(_result(tx))

    def start(s, request, stamp, raw, metadata=None, origin="direct_write",
              context_override=None):
        kind, service, target, can_id = request
        # The scheduler context is single-use and was consumed by the
        # parser before this call; pass the validated snapshot explicitly.
        ctx = context_override if context_override is not None else s["txctx"]
        channel = metadata["channel"] if metadata is not None else ctx[0] if ctx else None
        previous = s["active"].get(channel)
        flags = metadata["flags"] if metadata is not None else ctx[2] if ctx else None
        protocol = metadata["protocol"] if metadata is not None else ctx[1] if ctx else None
        baud = metadata["baud"] if metadata is not None else ctx[3] if ctx else None
        protocol_name = ({5: "CAN", 6: "ISO15765"}.get(protocol, "other")
                         if protocol is not None else "unknown")
        ambiguous_f114_retry = (
            kind == "P3" and service == "22F114" and previous is not None
            and previous["route"] == kind and previous["service"] == service
            and int(previous["can_id"], 16) == can_id
            and previous["protocol"] == protocol_name
            and previous["baud_bps"] == baud
            and not (previous["_complete"] or previous["_p3_negative"]
                     or previous["_no_fixture"] or previous["_bad_route"])
        )
        s["last_tx_channel"] = channel
        finish(s, channel, "superseded_by_tx")
        start_at = ctx[4] if ctx else stamp
        mod = 2**32 if ctx else 86400000
        tx = {
            "session": s["number"], "service": service, "route": kind,
            "_request_origin": origin,
            "can_id": f"0x{can_id:08X}" if can_id > 0x7FF else f"0x{can_id:03X}",
            "id_format": _id_format(can_id, flags), "channel": channel,
            "protocol": {5: "CAN", 6: "ISO15765"}.get(protocol, "other") if protocol is not None else "unknown",
            "baud_bps": baud,
            "target": f"0x{target:02X}" if target is not None else None,
            "rx_frames": 0, "off_route_rx": 0,
            "_start": start_at, "_last": None, "_time_mod": mod,
            "_rxid": None, "_seq": 1, "_base": 0x08, "_subblock": False,
            "_complete": False, "_invalid": False,
            "_d2_final_marker_mismatch": False,
            "_d2_rx_size_invalid": False,
            "_source_error": ("d2_request_non_can_transport"
                              if kind == "D2" and protocol is not None
                              and protocol != 5 else None),
            "_a6_identifier": _a6_request_identifier(raw) if service == "A6" else None,
            "_a6_error": None,
            "_no_fixture": False, "_bad_route": False,
            "_timeout": False, "_end_reason": "no_delivery_evidence",
            "_p3_total": None, "_p3_received": 0, "_p3_sequence": 1,
            "_p3_header": b"", "_p3_negative": False, "_p3_mismatch": False,
            "_p3_missing_data": False, "_p3_pending": 0,
            "_p3_transport_error": None,
            "_ambiguous_f114_retry": ambiguous_f114_retry,
            "_obd_starts": 0, "_obd_repeat": 0,
            "_obd_request_line": line_number, "_obd_last_rx_line": None,
        }
        if kind == "OBD":
            key = (service, can_id, channel, protocol, baud, flags)
            tx["_obd_repeat"] = s["obd_repeats"].get(key, 0) + 1
            s["obd_repeats"][key] = tx["_obd_repeat"]
            if service == "0902" and not (
                    (protocol == 6 and raw[4:] == b"\x09\x02") or
                    (protocol == 5 and raw[4:7] == b"\x02\x09\x02")):
                tx["_source_error"] = "obd_unknown_or_mismatched_transport"
            if service == "0902" and flags is not None and flags & 0x180:
                tx["_source_error"] = "obd_unsupported_addressing_flags"
            if service == "3E80" and protocol not in (5, 6):
                tx["_source_error"] = "obd_unknown_transport"
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
        if not tx or len(raw) < (4 if tx["route"] == "OBD" else 5):
            return
        can_id = int.from_bytes(raw[:4], "big")
        payload = raw[4:]
        if can_id > 0x1FFFFFFF:
            errors["invalid_rx_can_id"] += 1
            return
        if tx["route"] == "D2":
            # A B9 response is a sequence of *classic CAN* 8-byte frames,
            # not ISO15765 J2534 reassembly, TX echo or a byte-shortened
            # fake final 0x4F. Keep unknown legacy protocol metadata
            # unknown, but never silently accept contradictory metadata.
            rx_protocol = (metadata["protocol"] if metadata is not None
                           else ctx[1] if ctx else None)
            rx_baud = (metadata["baud"] if metadata is not None
                       else ctx[3] if ctx else None)
            if rx_protocol is not None and rx_protocol != 5:
                errors["d2_rx_protocol_mismatch"] += 1
                tx["off_route_rx"] += 1
                return
            if (rx_baud is not None and tx["baud_bps"] is not None
                    and rx_baud != tx["baud_bps"]):
                errors["d2_rx_baud_mismatch"] += 1
                tx["off_route_rx"] += 1
                return
            if ctx is not None and ctx[2] & 0x0B:
                # START_OF_MESSAGE, TX_MSG_TYPE and TX_INDICATION are
                # never an actual received eight-byte ECU CAN payload.
                errors["d2_rx_indication_not_payload"] += 1
                tx["off_route_rx"] += 1
                return
            if tx["service"].startswith("B9") and len(payload) != 8:
                # A short/long frame is evidence of malformed B9
                # transport only when it belongs to this response route.
                # A different CAN ID, or an unrelated first-frame opcode,
                # must remain off-route rather than poisoning a legitimate
                # independent reply in the same J2534 channel.
                if tx["_rxid"] is not None:
                    matching = can_id == tx["_rxid"]
                else:
                    matching = (len(payload) >= 4
                                and (payload[0] in (0x8F, 0x97)
                                     or (payload[0] & 0xF8) == 0xC8)
                                and payload[1:4] == bytes((
                                    int(tx["target"], 16), 0xF9,
                                    int(tx["service"][-2:], 16))))
                if not matching:
                    tx["off_route_rx"] += 1
                    return
                tx["_invalid"] = True
                tx["_d2_rx_size_invalid"] = True
                tx["rx_frames"] += 1
                errors["d2_classic_can_rx_size_invalid"] += 1
                return
        if tx["route"] == "OBD":
            if tx["service"] != "0902":
                tx["off_route_rx"] += 1
                return
            expected = range(0x7E8, 0x7F0) if tx["can_id"] == "0x7DF" else (0x7E8,)
            rx_protocol = metadata["protocol"] if metadata is not None else ctx[1] if ctx else None
            rx_baud = metadata["baud"] if metadata is not None else ctx[3] if ctx else None
            if (can_id not in expected or
                    (tx["_rxid"] is not None and can_id != tx["_rxid"]) or
                    (rx_protocol is not None and {5: "CAN", 6: "ISO15765"}.get(rx_protocol) != tx["protocol"]) or
                    (rx_baud is not None and tx["baud_bps"] is not None and rx_baud != tx["baud_bps"]) or
                    (ctx is not None and ctx[2] & 0x180)):
                tx["off_route_rx"] += 1
                return
            if rx_protocol is None or tx["protocol"] not in ("CAN", "ISO15765"):
                tx["_source_error"] = "obd_missing_transport_context"
                return
            if ctx is not None and ctx[2] & 0x09:
                # TX_MSG_TYPE / TX_INDICATION are not ECU replies.
                return
            if ctx is not None and ctx[2] & 0x02:
                if rx_protocol == 6 and not payload:
                    tx["_obd_starts"] += 1
                else:
                    tx["_source_error"] = "invalid_obd_start_indication"
                return
            if not payload:
                return  # VIDA has no RxStatus: an ID-only record stays unidentified.
            if (tx["_complete"] or tx["_p3_negative"] or tx["_p3_mismatch"]
                    or tx["_p3_missing_data"] or tx["_invalid"]):
                tx["off_route_rx"] += 1
                return
            if tx["_rxid"] is None:
                tx["_rxid"] = can_id
            if tx["protocol"] == "CAN" and len(payload) > 8:
                tx["rx_frames"] += 1
                tx["_invalid"] = True
            else:
                _p3_frame(tx, payload, tx["protocol"])
            tx["_obd_last_rx_line"] = line_number
        elif len(raw) < 5:
            return
        elif tx["route"] == "P3":
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
                rx_protocol = metadata["protocol"] if metadata is not None else ctx[1] if ctx else None
                rx_baud = metadata["baud"] if metadata is not None else ctx[3] if ctx else None
                if (rx_protocol in (5, 6) and
                        {5: "CAN", 6: "ISO15765"}[rx_protocol] != tx["protocol"]):
                    tx["_source_error"] = "p3_rx_protocol_metadata_mismatch"
                elif (rx_baud is not None and tx["baud_bps"] is not None
                      and rx_baud != tx["baud_bps"]):
                    tx["_source_error"] = "p3_rx_baud_metadata_mismatch"
                elif ctx is not None and ctx[2] & 0x09:
                    # TX echoes / indications are not replies from the ECU.
                    return
                elif ctx is not None and ctx[2] & 0x02:
                    # A valid ISO15765 START_OF_MESSAGE is an ID-only
                    # indication; unexpected payload must never complete DID.
                    tx["_source_error"] = "p3_invalid_start_indication"
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
                    # The source C fixture verifier already rejects a 13-
                    # frame D2 0x08-series sequence unless its last frame is
                    # 0x4F (seven useful bytes). The text audit must not
                    # report the same 13-frame wire trace as delivered when
                    # the terminal announces fewer valid bytes. Preserve
                    # other lengths and the independent 0x10-series rules.
                    if (tx["route"] == "D2"
                            and tx["service"].startswith("B9")
                            and tx["_base"] == 0x08
                            and tx["rx_frames"] == 13
                            and head != 0x4F):
                        tx["_invalid"] = True
                        tx["_d2_final_marker_mismatch"] = True
                    else:
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

    for line_number, line in enumerate(lines, 1):
        event = vida.feed(line)
        if event is not None:
            kind = event["kind"]
            if kind == "ignore":
                continue
            if include_obd:
                observed_events["vida_" + kind] += 1
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
                request = _request(event["raw"], include_obd)
                if request:
                    start(s, request, event["stamp"], event["raw"], event["metadata"])
                elif event["metadata"]["protocol"] != 5 or not _flow_control(event["raw"], include_obd):
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
        if include_obd and m:
            observed = _native_event(text.rstrip("\r\n"))
            if observed:
                observed_events[observed] += 1
        s = scope(pid)
        stamp = _stamp(line)
        # The native scheduler emits context immediately before its tick.
        # Any intervening text discards that context rather than binding a
        # later unrelated or forged periodic payload to the old channel.
        if (s["periodicctx"] is not None
                and not text.startswith((
                    "Periodic TX context ",
                    "J2534 periodic TX (read-only simulator)"))):
            s["periodicctx"] = None
        if "PassThruOpen ->" in text:
            for ch in list(s["active"]):
                finish(s, ch, "new_connection")
            s["txctx"] = s["periodicctx"] = s["rxctx"] = s["clearctx"] = None
            s["last_tx_channel"] = s["disconnect_channel"] = None
            s["obd_repeats"].clear()
        txctx = _context(text, "TX context channel/protocol/flags/baud/time-us (BE)", include_obd)
        if txctx is not None:
            s["txctx"] = txctx
            continue
        periodicctx = _context(
            text, "Periodic TX context channel/protocol/flags/baud/time-us (BE)",
            True)
        if periodicctx is not None:
            s["periodicctx"] = periodicctx
            continue
        if text.startswith("Periodic TX context "):
            s["periodicctx"] = None
            errors["malformed_periodic_context"] += 1
            continue
        rxctx = _context(text, "RX context channel/protocol/status/baud/time-us (BE)", include_obd)
        if rxctx is not None:
            s["rxctx"] = rxctx
            continue
        clearctx = _context(text, "CLEAR_RX context channel/protocol/flags/baud/time-us (BE)", include_obd)
        if clearctx is not None:
            s["clearctx"] = clearctx
            continue
        if include_obd:
            bad_context = next((name for prefix, name in (
                ("TX context ", "txctx"), ("RX context ", "rxctx"),
                ("CLEAR_RX context ", "clearctx")) if text.startswith(prefix)), None)
            if bad_context:
                s[bad_context] = None
                errors["malformed_context"] += 1
                continue
        if text.startswith("PassThruDisconnect channel (BE)"):
            data = _words(text.split("(BE)", 1)[-1])
            if len(data) == 4:
                s["disconnect_channel"] = int.from_bytes(data, "big")
            continue
        if text.startswith("J2534 periodic TX (read-only simulator)"):
            # This is a scheduler-generated dispatch, never a new direct
            # PassThruWriteMsgs call by SectorV. Require an immediately
            # preceding, valid, scoped native context; do not infer a channel
            # from an unrelated direct TX or RX log entry.
            marker = "J2534 periodic TX (read-only simulator)"
            suffix = text[len(marker):].strip()
            ctx = s["periodicctx"]
            s["periodicctx"] = None
            if (ctx is None or not re.fullmatch(
                    r"[0-9A-Fa-f]{2}(?:\s+[0-9A-Fa-f]{2}){4,4127}", suffix)):
                errors["unattributed_periodic_tx"] += 1
                continue
            raw = _words(suffix)
            if (ctx[0] == 0 or ctx[1] not in (5, 6) or ctx[3] == 0 or
                    (ctx[1] == 5 and len(raw) > 12)):
                errors["invalid_periodic_transport"] += 1
                continue
            req = _request(raw, include_obd)
            if req and req[0] == "D2" and ctx[1] != 5:
                errors["invalid_periodic_transport"] += 1
                continue
            if req:
                start(s, req, stamp, raw, origin="periodic_scheduler",
                      context_override=ctx)
            elif ctx[1] == 5 and _flow_control(raw, include_obd):
                pass  # Flow Control continues an existing ISO-TP response.
            else:
                finish(s, ctx[0], "superseded_by_other_periodic_tx")
            continue
        if "TX (app request)" in text or "PassThruWriteMsgs() msg" in text:
            marker = "TX (app request)" if "TX (app request)" in text else "Data = ["
            raw = _words(text.split(marker, 1)[1])
            plain_valid = marker != "TX (app request)" or (text.startswith(marker) and re.fullmatch(
                r"[0-9A-Fa-f]{2}(?:\s+[0-9A-Fa-f]{2})*", text.split(marker, 1)[1].strip()))
            req = _request(raw, include_obd)
            if req:
                start(s, req, stamp, raw)
                if req[0] == "OBD" and not plain_valid:
                    active(s, s["last_tx_channel"])["_source_error"] = "malformed_obd_tx_record"
            elif _flow_control(raw, include_obd and plain_valid and s["txctx"] is not None and s["txctx"][1] == 5):
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
            tx = active(s, s["rxctx"][0] if s["rxctx"] else None)
            if (include_obd and tx and tx["route"] == "OBD" and marker == "PassThruReadMsgs -> delivered"
                    and (not text.startswith(marker) or not re.fullmatch(r"[0-9A-Fa-f]{2}(?:\s+[0-9A-Fa-f]{2})*", text.split(marker, 1)[1].strip()))):
                tx["_source_error"] = "malformed_obd_rx_record"
            receive(s, _words(text.split(marker, 1)[1]), stamp)
            s["rxctx"] = None
            continue
        if "P2 D2 read command: no validated response fixture" in text or "P2 D2 command: no recorded ECU fixture" in text:
            tx = active(s, s["last_tx_channel"])
            if tx and tx["route"] != "OBD":
                tx["_no_fixture"] = True
        if "P2 D2 strict route rejected" in text:
            tx = active(s, s["last_tx_channel"])
            if tx and tx["route"] != "OBD":
                tx["_bad_route"] = True
        if "P3 CEM " in text and " unavailable" in text:
            tx = active(s, s["last_tx_channel"])
            if tx and tx["route"] != "OBD":
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
            s["txctx"] = s["periodicctx"] = s["rxctx"] = None
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
    report = {
        "format": "virtualcar-j2534-evidence-v1", "read_only": True,
        "contains_payload_data": False, "replay_approved": False,
        "notes": [
            "J2534 RX delivery does not prove diagnostic-client ECU acceptance.",
            "Legacy logs without channel, flags or timestamps leave route metadata unknown.",
            "No A3/A6 or P3 positive ECU identity is inferred without a verified fixture.",
            "A 13-frame D2 0x08-series terminal must be 0x4F; this checks transport shape, never OEM payload authenticity.",
            "B9 D2 replies need full 8-byte classic CAN RX; mismatched protocol, baud or J2534 indications cannot prove delivered ECU frames.",
            "negative_response identifies a final UDS rejection, not successful ECU discovery.",
            "UDS NRC 0x78 is nonterminal; pending-only probes stay unverified unless a read timeout is logged.",
            "A positive ReadDataByIdentifier header requires at least one data-record byte.",
            "P3 transport checks parse only UDS headers and ISO-TP lengths, not VIN or identity authenticity.",
            "P3 raw CAN PCI and ISO15765 reassembled UDS are distinguished; format mismatch is not an ECU framing diagnosis.",
            "A second identical F114 request before the first completes leaves later RX attribution ambiguous without a reset boundary.",
            "A6 delivery validates a single-frame E6 echo and length only; no parameter value or normal-mode state is decoded.",
            "A6 route candidates are limited to observed CEM IDs; unknown routes and non-CD ... 01 request shapes stay unverified.",
            "Periodic scheduler TX is a separate source from direct PassThruWriteMsgs; it is not proof that the GUI initiated each tick.",
            ("OBD window_ms is observed TX-to-last matched RX, not a claimed ECU processing duration."
             if include_obd else "Window is observed first-to-last delivered RX, not a claimed ECU processing duration."),
        ],
        "transactions": results,
        "counts": dict(sorted(statuses.items())),
        "parse_errors": dict(sorted(errors.items())),
    }
    if include_obd:
        obd = [item for item in results if item["route"] == "OBD"]
        report["obd_observation"] = {
            "scope": "0902_on_7df_7e0_and_exact_18db33f1_3e80_only",
            "vin_requests": sum(item["service"] == "0902" for item in obd),
            "vin_delivered": sum(item["service"] == "0902" and item["status"] == "delivered" for item in obd),
            "tester_present_requests": sum(item["service"] == "3E80" for item in obd),
            "recognized_d2_p3_probes": sum(item["route"] != "OBD" for item in results),
            "client_result": "client_result_unknown",
            "vehicle_identity_verified": False,
            "filter_effect": "not_observed",
        }
        report["observed_event_markers"] = dict(sorted(observed_events.items()))
        report["notes"] += [
            "OBD support is opt-in; client name/version and empty ECU UI are not inferred from log text.",
            "VIN header/length delivery does not verify VIN characters, checksum, identity, or ECU discovery.",
            "Functional OBD correlates one observed responder per request; other responders are off-route evidence.",
            "START_OF_MESSAGE is counted only with explicit native RxStatus and no payload; it is not VIN data.",
            "Event marker counts do not prove API return status, filter channel identity or a filter rejection.",
            "Use backend evidence audit for request IDs, queue lifecycle and explicit filter_reject; do not join by timing alone.",
            "OBD request_line/last_rx_line record source order, not a clock shared with another log or process.",
            "ISO15765 ExtraDataIndex metadata is not validated here; native DLL tests cover the synthetic 4/0 and 24/24 forms.",
        ]
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Privacy-safe, read-only J2534 evidence audit")
    parser.add_argument("log", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--include-obd", action="store_true",
                        help="Also audit narrow OBD VIN/TesterPresent observations; never infer client acceptance")
    args = parser.parse_args(argv)
    if args.log.resolve() == args.output.resolve():
        parser.error("output must not overwrite input")
    try:
        with args.log.open("r", encoding="utf-8-sig", errors="replace") as stream:
            report = audit(stream, include_obd=args.include_obd)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Audited {len(report['transactions'])} read-only probes; "
          f"statuses: {report['counts']}; replay approved: NO")


if __name__ == "__main__":
    main()
