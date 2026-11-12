#!/usr/bin/env python3
"""B3A30: offline VIDA TX log-format inventory and fail-closed error attribution.

Only fixed aggregate categories leave this tool. A complete logged TX is not
proof of actual transport, PASSTHRU_MSG ABI fields, Connect success or ECU RX.
"""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys

from audit_j2534_discovery import (
    _VIDA_BOUNDARY, _VIDA_CONNECT, _VIDA_ERROR, _VIDA_IO, _VIDA_LINE,
    _VIDA_PACKET, _stamp, _vida_number,
)

MAX_BYTES = 32 * 1024 * 1024
MAX_LINES = 200_000
MAX_LINE = 32768
MAX_STATES = 256
MAX_CALL_LINES = 20
MAX_CALL_MS = 5000
MAX_CONNECT_LINES = 200
MAX_CONNECT_MS = 30000
ERROR_CATEGORIES = (
    "NO_TX_RECORD", "TX_RECORD_OTHER_COMPONENT", "MULTI_MESSAGE",
    "AMBIGUOUS_OR_MALFORMED_RECORD", "COMPLETE_SINGLE_LOGGED_TX", "UNMATCHED_ERROR",
)
CONNECT_CATEGORIES = (
    "SAME_THREAD_ISO9141_10400_UNACKNOWLEDGED", "SAME_THREAD_OTHER_UNACKNOWLEDGED",
    "CROSS_THREAD_PROTOCOL_UNVERIFIED", "MISSING_OR_STALE",
)
LITERAL_SHAPES = (
    "RELAY_CLOSE_LITERAL", "B9F0_LITERAL", "TEARDOWN_LITERAL", "OTHER_LITERAL",
)
INVENTORY = (
    "write_calls", "write_batch_single", "write_batch_multiple", "invalid_write_calls",
    "write_calls_other_component", "write_calls_unscoped",
    "write_batch_single_other_component", "write_batch_multiple_other_component",
    "write_batch_single_unscoped", "write_batch_multiple_unscoped",
    "arrow_tx_exact_component", "arrow_tx_other_component", "arrow_tx_unscoped",
    "alternate_tx_records", "alternate_tx_exact_component",
    "alternate_tx_other_component", "alternate_tx_unscoped",
    "malformed_tx_records", "unvalidated_tx_records", "unbound_tx_records", "write_not_supported_errors",
    "session_boundaries", "lifecycle_barriers", "clock_barriers",
    "write_calls_without_matched_terminal_error",
)
# General header is inventory-only. Only _VIDA_LINE establishes the component.
_ANY_HEADER = re.compile(
    r"^(?:\d{2}:\d{2}:\d{2},\d{3}\s+)?"
    r"\[([^\]]+)\]\[([0-9A-Fa-f]{1,8})\]\[[^\]]+\]\s*(.*)$")
_ALT = re.compile(r"^PassThruWriteMsgs\(\) msg\[([0-9]+)\]\.Data = \[(.*)\]\s*$")
_ALT_MENTION = re.compile(r"PassThruWriteMsgs\(\)\s+msg\[")
_TARGET_ERROR = re.compile(
    r"J2534 function:PassThruWriteMsgs failed with return value:ERR_NOT_SUPPORTED\b")
_DISCONNECT = re.compile(r"^PassThruDisconnect\(\s*([0-9]+)\s*\)\s*$")
_FUNCTION = re.compile(r"(?:^PassThru[A-Za-z]+\(|^J2534 function:PassThru)")


def _zeros(names):
    return dict.fromkeys(names, 0)


def _fresh(start_line, start_ms, end_line, end_ms, line_bound, time_bound):
    return (start_ms is not None and end_ms is not None
            and 0 <= end_line - start_line <= line_bound
            and 0 <= end_ms - start_ms <= time_bound)


def _payload(data, alternate=False):
    # Same full-token comma-byte validation as discovery, without its CAN-only
    # minimum of five bytes: the source-backed teardown literal is four bytes.
    tokens = data.split(",")
    if tokens and not tokens[-1].strip():
        tokens.pop()
    pattern = r"0[xX][0-9A-Fa-f]{2}" if alternate else r"[0-9A-Fa-f]{2}"
    if not 1 <= len(tokens) <= 4128 or any(
            not re.fullmatch(pattern, token.strip()) for token in tokens):
        return None
    return bytes(int(token.strip(), 16) for token in tokens)


def _literal(raw):
    return {
        b"\x84\x40\x13\xb2\xf0\x00": "RELAY_CLOSE_LITERAL",
        b"\x83\x51\x13\xb9\xf0": "B9F0_LITERAL",
        b"\x82\x51\x13\xa0": "TEARDOWN_LITERAL",
    }.get(raw, "OTHER_LITERAL")


@dataclass
class _Connect:
    thread: int
    channel: int
    line: int
    stamp: int
    iso9141_10400: bool


@dataclass
class _Write:
    channel: int
    count: int
    line: int
    stamp: int
    connect: str
    next_index: int = 0
    syntax: str = ""
    shape: str = "OTHER_LITERAL"
    malformed: bool = False
    other_component: bool = False


class _Audit:
    def __init__(self):
        self.inventory = _zeros(INVENTORY)
        self.categories = _zeros(ERROR_CATEGORIES)
        self.connect_counts = _zeros(CONNECT_CATEGORIES)
        self.shapes = _zeros(LITERAL_SHAPES)
        self.pending = {}
        self.connects = {}
        self.clocks = {}
        self.matched_errors = 0
        self.valid_writes = 0

    def reset(self):
        self.pending.clear()
        self.connects.clear()
        self.clocks.clear()

    def forget_channel(self, channel):
        self.pending = {t: p for t, p in self.pending.items() if p.channel != channel}
        self.connects.pop(channel, None)

    def clear_thread(self, thread):
        self.pending.pop(thread, None)
        self.connects = {c: p for c, p in self.connects.items() if p.thread != thread}

    def connect_category(self, thread, channel, number, stamp):
        candidate = self.connects.get(channel)
        if candidate is None or not _fresh(candidate.line, candidate.stamp, number,
                                          stamp, MAX_CONNECT_LINES, MAX_CONNECT_MS):
            return "MISSING_OR_STALE"
        if candidate.thread != thread:
            return "CROSS_THREAD_PROTOCOL_UNVERIFIED"
        return ("SAME_THREAD_ISO9141_10400_UNACKNOWLEDGED" if candidate.iso9141_10400
                else "SAME_THREAD_OTHER_UNACKNOWLEDGED")

    def error(self, pending):
        if not isinstance(pending, _Write):
            category = "UNMATCHED_ERROR"
        else:
            self.matched_errors += 1
            self.connect_counts[pending.connect] += 1
            if pending.malformed or (pending.other_component and pending.next_index):
                category = "AMBIGUOUS_OR_MALFORMED_RECORD"
            elif pending.count > 1:
                category = "MULTI_MESSAGE"
            elif pending.other_component:
                category = "TX_RECORD_OTHER_COMPONENT"
            elif pending.next_index == 1:
                category = "COMPLETE_SINGLE_LOGGED_TX"
                self.shapes[pending.shape] += 1
            else:
                category = "NO_TX_RECORD"
        self.categories[category] += 1

    def feed(self, line, number):
        # A malformed session declaration is also a barrier, never permission
        # to carry an old call into a new session.
        if (_VIDA_BOUNDARY.fullmatch(line.strip())
                or line.strip().startswith("Starting new logsession:")):
            self.inventory["session_boundaries"] += 1
            self.reset()
            return
        strict = _VIDA_LINE.fullmatch(line)
        general = _ANY_HEADER.fullmatch(line)
        exact = strict is not None
        thread = int(strict[1], 16) if exact else int(general[2], 16) if general else None
        body = strict[2] if exact else general[3] if general else line
        scope = "exact_component" if exact else "other_component" if general else "unscoped"
        stamp = _stamp(line)
        if thread is not None:
            previous = self.clocks.get(thread)
            if stamp is None or (previous is not None and stamp < previous):
                self.inventory["clock_barriers"] += 1
                self.clear_thread(thread)
            if stamp is not None:
                self.clocks[thread] = stamp

        # Bound all active state, including harmless unrelated logger threads.
        if max(len(self.clocks), len(self.pending), len(self.connects)) > MAX_STATES:
            raise ValueError("state limit exceeded")
        for tid, p in list(self.pending.items()):
            if number - p.line > MAX_CALL_LINES:
                self.pending.pop(tid)
        pending = self.pending.get(thread)
        if pending is not None and not _fresh(pending.line, pending.stamp, number,
                                             stamp, MAX_CALL_LINES, MAX_CALL_MS):
            self.pending.pop(thread, None)
            pending = None

        arrow = _VIDA_PACKET.fullmatch(body)
        arrow_mention = re.match(r"^-{2,}\s*>", body) or (not general and "--->" in body)
        alt = _ALT.fullmatch(body)
        alt_mention = _ALT_MENTION.search(body) is not None
        if arrow_mention or alt_mention:
            alternate = alt_mention
            if alternate:
                self.inventory["alternate_tx_records"] += 1
                self.inventory["alternate_tx_" + scope] += 1
            else:
                self.inventory["arrow_tx_" + scope] += 1
            packet = alt if alternate else arrow
            raw = _payload(packet[2] if alternate else packet[3], alternate) if packet else None
            if thread is None:
                self.inventory["unvalidated_tx_records"] += 1
            elif raw is None:
                self.inventory["malformed_tx_records"] += 1
            if thread is None:
                # An unknown identity layout cannot rule out an intervening
                # record for any writer. Retain only ambiguous attribution.
                for candidate in self.pending.values():
                    if isinstance(candidate, _Write):
                        candidate.malformed = True
            if not isinstance(pending, _Write):
                self.inventory["unbound_tx_records"] += 1
            elif not exact:
                # Only presence of a record in another component is retained;
                # its payload cannot become a positive candidate.
                pending.other_component = True
            else:
                index = int(packet[1] if alternate else packet[2]) if packet else -1
                syntax = "alternate" if alternate else "arrow"
                if (raw is None or index != pending.next_index or index >= pending.count
                        or (pending.syntax and pending.syntax != syntax)):
                    pending.malformed = True
                else:
                    pending.syntax = syntax
                    pending.next_index += 1
                    if index == 0:
                        pending.shape = _literal(raw)
            return

        if _TARGET_ERROR.search(body):
            self.inventory["write_not_supported_errors"] += 1
            # Unscoped/error mentions are counted conservatively, never bound.
            error = _VIDA_ERROR.match(body) if exact else None
            self.error(pending if error and error.groups() == ("WriteMsgs", "ERR_NOT_SUPPORTED") else None)
            if thread is not None:
                self.pending.pop(thread, None)
            else:
                self.reset()
            return

        io = _VIDA_IO.fullmatch(body)
        if not general and not io:
            # Literal format inventory only; an unknown prefix establishes no
            # thread, component or actual invocation, even if its suffix parses.
            start = body.find("PassThruWriteMsgs(")
            io = _VIDA_IO.fullmatch(body[start:]) if start >= 0 else None
        if io and io[1] == "Write":
            if not exact:
                self.inventory["write_calls_" + scope] += 1
                channel, count, timeout = map(int, io.groups()[1:])
                if channel <= 0xFFFFFFFF and timeout <= 0xFFFFFFFF and 1 <= count <= 4096:
                    batch = "write_batch_single_" if count == 1 else "write_batch_multiple_"
                    self.inventory[batch + scope] += 1
                if thread is not None:
                    self.pending.pop(thread, None)
                else:
                    self.reset()
                return
            self.inventory["write_calls"] += 1
            channel, count, timeout = map(int, io.groups()[1:])
            self.pending.pop(thread, None)
            if (channel > 0xFFFFFFFF or timeout > 0xFFFFFFFF or not 1 <= count <= 4096):
                self.inventory["invalid_write_calls"] += 1
                return
            self.inventory["write_batch_single" if count == 1 else "write_batch_multiple"] += 1
            self.valid_writes += 1
            if stamp is not None:
                self.pending[thread] = _Write(channel, count, number, stamp,
                    self.connect_category(thread, channel, number, stamp))
            return

        # Lifecycle records are global barriers even from another component.
        # The text lacks a reliable device identity for Close/Open.
        if body.startswith(("PassThruOpen", "PassThruClose")):
            self.inventory["lifecycle_barriers"] += 1
            self.reset()
            return
        if body.startswith("PassThruDisconnect"):
            self.inventory["lifecycle_barriers"] += 1
            disconnect = _DISCONNECT.fullmatch(body)
            if disconnect and int(disconnect[1]) <= 0xFFFFFFFF:
                self.forget_channel(int(disconnect[1]))
            else:
                self.reset()
            return
        connect = _VIDA_CONNECT.fullmatch(body)
        if body.startswith("PassThruConnect"):
            self.pending.pop(thread, None)
            if not exact or not connect:
                self.reset()
                return
            device, protocol, flags, baud, channel = map(_vida_number, connect.groups())
            if baud == 0 or any(v > 0xFFFFFFFF for v in (device, protocol, flags, baud, channel)):
                self.reset()
                return
            self.forget_channel(channel)
            if stamp is not None:
                candidate = _Connect(thread, channel, number, stamp, protocol == 3 and baud == 10400)
                self.connects[channel] = candidate
                self.pending[thread] = candidate
            return
        error = _VIDA_ERROR.match(body)
        if error and error[1] == "Connect":
            if isinstance(pending, _Connect):
                self.forget_channel(pending.channel)
            elif thread is not None:
                self.clear_thread(thread)
            else:
                self.reset()
        if body == "J2534Channel::ClearRxBuffer()":
            self.pending.clear()
        elif re.match(r"^<\s*-{2,}", body) or (not general and "<---" in body):
            # A receive record cannot be a continuation of a Write call.
            if thread is not None:
                self.pending.pop(thread, None)
            else:
                self.reset()
        elif _FUNCTION.match(body) or body.startswith("PassThru"):
            # Any intervening call/error supersedes the pending call, including
            # malformed Write/Read/Ioctl records. Alternate records returned above.
            if body.startswith("PassThruWriteMsgs("):
                self.inventory["invalid_write_calls"] += 1
            if thread is not None:
                self.pending.pop(thread, None)
            else:
                self.reset()
        elif not general and ("PassThru" in body or "J2534 function:" in body):
            # Unknown identity layout may hide an intervening lifecycle/call.
            self.reset()

    def report(self):
        self.inventory["write_calls_without_matched_terminal_error"] = (
            self.valid_writes - self.matched_errors)
        return {
            "schema": "virtualcar-vida-b3a30-tx-coverage-v1",
            "inventory": self.inventory,
            "error_categories": self.categories,
            "error_connect_candidates": self.connect_counts,
            "complete_literal_shapes": self.shapes,
            "claims": {
                "actual_j2534_tx": "NOT_ESTABLISHED_BY_LOG_COVERAGE",
                "connect_success": "NOT_PROVEN",
                "passthru_msg_abi_fields": "NOT_PROVEN",
                "local_ack": "NOT_PROVEN",
                "physical_ecu_rx": "NOT_PROVEN",
                "original_vida_automatic_vin": "NOT_PROVEN",
                "original_18_event_classification": "REQUIRES_OWNER_LOCAL_RUN",
            },
            "contains_source_data": False,
            "replay_approved": False,
        }


def audit_lines(lines):
    audit = _Audit()
    total = 0
    for number, raw in enumerate(lines, 1):
        if not isinstance(raw, str) or len(raw) > MAX_LINE or number > MAX_LINES:
            raise ValueError("input limit exceeded")
        encoded_size = len(raw.encode("utf-8"))
        total += encoded_size
        if total > MAX_BYTES or encoded_size > MAX_LINE or "\x00" in raw:
            raise ValueError("input limit exceeded")
        # The API also accepts synthetic rows without newline terminators.
        line = raw.rstrip("\r\n")
        if "\r" in line or "\n" in line:
            raise ValueError("invalid row")
        audit.feed(line, number)
    return audit.report()


def _file_lines(path):
    # Never read an unbounded file or line, including a concurrently growing log.
    total = 0
    with path.open("rb") as source:
        if not source.seekable() or source.seek(0, 2) > MAX_BYTES:
            raise ValueError("input limit exceeded")
        source.seek(0)
        for number in range(1, MAX_LINES + 2):
            raw = source.readline(MAX_LINE + 1)
            if not raw:
                break
            total += len(raw)
            if (len(raw) > MAX_LINE or total > MAX_BYTES or number > MAX_LINES
                    or not raw.endswith(b"\n")):
                raise ValueError("incomplete or oversized input")
            yield raw.decode("utf-8-sig" if number == 1 else "utf-8", errors="strict")


class _SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "B3A30 FAIL-CLOSED: invalid command arguments.\n")


def main(argv=None):
    parser = _SafeParser(description=__doc__)
    parser.add_argument("--vida-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = audit_lines(_file_lines(args.vida_log))
        text = json.dumps(report, ensure_ascii=True, indent=2) + "\n"
        # Exclusive creation also rejects source==output and existing symlinks.
        # Parent is an existing owner-controlled directory; no directory creation.
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(text)
        print("B3A30: category-only report created; source claims remain unverified.")
        return 0
    except (OSError, ValueError, OverflowError):
        parser.exit(2, "B3A30 FAIL-CLOSED: input or output rejected.\n")


if __name__ == "__main__":
    sys.exit(main())
