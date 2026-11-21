#!/usr/bin/env python3
"""B3A31: category-only overlay of B3A30 TX marker bookkeeping.

Line proximity is source order only. Execution on supplied input does not
authenticate that input, establish transport, or attribute unscoped TX to errors.
"""
import argparse
from bisect import bisect_left, bisect_right
from dataclasses import replace
import json
from pathlib import Path
import re
import sys

import audit_vida_b3a30_tx_coverage as base

KINDS = ("ARROW", "ALTERNATE")
SCHEMA = "virtualcar-vida-b3a31-header-families-v1"
# Fixed output contract, independent of future dependency schema additions.
_INVENTORY_KEYS = tuple("""
write_calls write_batch_single write_batch_multiple invalid_write_calls
write_calls_other_component write_calls_unscoped
write_batch_single_other_component write_batch_multiple_other_component
write_batch_single_unscoped write_batch_multiple_unscoped
arrow_tx_exact_component arrow_tx_other_component arrow_tx_unscoped
alternate_tx_records alternate_tx_exact_component alternate_tx_other_component alternate_tx_unscoped
malformed_tx_records unvalidated_tx_records unbound_tx_records write_not_supported_errors
session_boundaries lifecycle_barriers clock_barriers write_calls_without_matched_terminal_error
""".split())
SCOPES = ("EXACT_COMPONENT", "OTHER_COMPONENT", "UNSCOPED")
FAMILIES = ("EXACT_COMPONENT_BRACKETS", "OTHER_COMPONENT_BRACKETS",
            "LEGACY_NUMERIC_PREFIX", "BARE_ARROW", "OTHER_OR_UNKNOWN")
REASONS = (
    "UNKNOWN_THREAD_IDENTITY", "NO_PENDING_SAME_THREAD_WRITE",
    "LAST_WRITE_CLEARED_BY_LIFECYCLE", "LAST_WRITE_CLEARED_BY_INTERVENING_CALL",
    "LAST_WRITE_CLEARED_BY_TERMINAL_ERROR", "LAST_WRITE_CLEARED_BY_OTHER_RECORD",
    "LAST_WRITE_EXPIRED", "CLOCK_MISSING_OR_BACKWARDS", "UNKNOWN_LAYOUT_BARRIER",
)
SYNTAX = ("VALID_SYNTAX", "MALFORMED_SYNTAX", "UNVALIDATED_IDENTITY")
COHORTS = ("UNSCOPED_ARROWS", "BASE_UNBOUND_ARROWS")
DIRECTIONS = ("PRECEDING_WRITE", "FOLLOWING_WRITE",
              "PRECEDING_WRITE_ERROR", "FOLLOWING_WRITE_ERROR")
BUCKETS = ("ROWS_0_5", "ROWS_6_20", "ROWS_21_100", "ROWS_OVER_100", "UNKNOWN")
_LEGACY = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}\s+"
                     r"[0-9A-Fa-f]{4}\s+[0-9A-Fa-f]{6}\s+")
_TX_COUNTERS = {
    "ARROW": ("arrow_tx_exact_component", "arrow_tx_other_component", "arrow_tx_unscoped"),
    "ALTERNATE": ("alternate_tx_exact_component", "alternate_tx_other_component", "alternate_tx_unscoped"),
}
_WRITE_COUNTERS = ("write_calls", "write_calls_other_component", "write_calls_unscoped")


def _require(condition):
    if not condition:
        raise ValueError("inconclusive marker bookkeeping")


def _zeros(names):
    return dict.fromkeys(names, 0)


def _matrix(names):
    return {kind: {scope: _zeros(names) for scope in SCOPES} for kind in KINDS}


def _identity(line):
    strict = base._VIDA_LINE.fullmatch(line)
    general = base._ANY_HEADER.fullmatch(line)
    if strict:
        return int(strict[1], 16), strict[2], "EXACT_COMPONENT"
    if general:
        return int(general[2], 16), general[3], "OTHER_COMPONENT"
    return None, line, "UNSCOPED"


def _family(line, scope):
    if scope == "EXACT_COMPONENT":
        return "EXACT_COMPONENT_BRACKETS"
    if scope == "OTHER_COMPONENT":
        return "OTHER_COMPONENT_BRACKETS"
    # This is the fixed lexical shape of an existing synthetic discovery
    # fixture. Neither numeric field is interpreted as a reliable thread ID.
    if _LEGACY.match(line):
        return "LEGACY_NUMERIC_PREFIX"
    if re.match(r"^-{2,}\s*>", line):
        return "BARE_ARROW"
    return "OTHER_OR_UNKNOWN"


def _syntax(body, kind, scope):
    if scope == "UNSCOPED":
        return "UNVALIDATED_IDENTITY"
    packet = base._ALT.fullmatch(body) if kind == "ALTERNATE" else base._VIDA_PACKET.fullmatch(body)
    data = packet[2] if packet and kind == "ALTERNATE" else packet[3] if packet else None
    return ("VALID_SYNTAX" if data is not None and base._payload(data, kind == "ALTERNATE") is not None
            else "MALFORMED_SYNTAX")


def _bucket(distance):
    if distance is None:
        return "UNKNOWN"
    _require(distance >= 0)
    return ("ROWS_0_5" if distance <= 5 else "ROWS_6_20" if distance <= 20
            else "ROWS_21_100" if distance <= 100 else "ROWS_OVER_100")


class _Overlay:
    def __init__(self):
        self.audit = base._Audit()
        self.scopes = _matrix(("total", "active_write_present", "base_unbound"))
        self.reasons = _matrix(REASONS)
        self.syntax = _matrix(SYNTAX)
        self.families = {kind: _zeros(FAMILIES) for kind in KINDS}
        self.proximity = {cohort: {direction: _zeros(BUCKETS) for direction in DIRECTIONS}
                          for cohort in COHORTS}
        self.cleared = {}
        self.writes = []
        self.errors = []
        self.arrows = []

    def finish_session(self):
        # Reference lists are recognized parameterized call / error records.
        # The direction is source row order, with no transport/time inference.
        for row, unscoped, unbound in self.arrows:
            distances = {}
            for rows, suffix in ((self.writes, "WRITE"), (self.errors, "WRITE_ERROR")):
                before = bisect_left(rows, row) - 1
                after = bisect_right(rows, row)
                distances["PRECEDING_" + suffix] = row - rows[before] if before >= 0 else None
                distances["FOLLOWING_" + suffix] = rows[after] - row if after < len(rows) else None
            for cohort, member in (("UNSCOPED_ARROWS", unscoped), ("BASE_UNBOUND_ARROWS", unbound)):
                if member:
                    for direction, distance in distances.items():
                        self.proximity[cohort][direction][_bucket(distance)] += 1
        self.writes.clear()
        self.errors.clear()
        self.arrows.clear()

    def removal_reason(self, writer, tid, event_thread, body, scope, stamp, number, clocks):
        # Match the actual ordering of base.feed invalidations. A tombstone
        # describes observed parser state removal, never an ECU failure cause.
        if event_thread == tid and (stamp is None or
                (tid in clocks and stamp < clocks[tid])):
            return "CLOCK_MISSING_OR_BACKWARDS"
        if number - writer.line > base.MAX_CALL_LINES:
            return "LAST_WRITE_EXPIRED"
        if event_thread == tid and not base._fresh(writer.line, writer.stamp, number,
                stamp, base.MAX_CALL_LINES, base.MAX_CALL_MS):
            return "LAST_WRITE_EXPIRED"
        if body.startswith(("PassThruOpen", "PassThruClose", "PassThruDisconnect", "PassThruConnect")):
            return "LAST_WRITE_CLEARED_BY_LIFECYCLE"
        if body == "J2534Channel::ClearRxBuffer()":
            return "LAST_WRITE_CLEARED_BY_LIFECYCLE"
        error = base._VIDA_ERROR.match(body)
        if error and error[1] == "WriteMsgs" and event_thread == tid:
            return "LAST_WRITE_CLEARED_BY_TERMINAL_ERROR"
        if scope == "UNSCOPED":
            return "UNKNOWN_LAYOUT_BARRIER"
        if re.match(r"^<\s*-{2,}", body):
            return "LAST_WRITE_CLEARED_BY_OTHER_RECORD"
        if base._FUNCTION.match(body) or body.startswith("PassThru") or base._TARGET_ERROR.search(body):
            return "LAST_WRITE_CLEARED_BY_INTERVENING_CALL"
        # A change to the pinned dependency's state machine needs review.
        raise ValueError("unrecognized parser transition")

    def feed(self, line, number):
        boundary = line.strip().startswith("Starting new logsession:")
        if boundary:
            self.finish_session()
            self.cleared.clear()
        thread, body, scope = _identity(line)
        stamp = base._stamp(line)
        originals = dict(self.audit.pending)
        # Marker processing mutates dataclass objects in place; copy values
        # before calling the dependency, retaining identity separately.
        writers = {tid: replace(item) for tid, item in originals.items() if isinstance(item, base._Write)}
        clocks = dict(self.audit.clocks)
        before = dict(self.audit.inventory)
        self.audit.feed(line, number)
        _require(set(self.audit.inventory) == set(_INVENTORY_KEYS))
        delta = {key: self.audit.inventory[key] - value for key, value in before.items()}
        _require(all(value >= 0 for value in delta.values()))

        if not boundary:
            for tid, writer in writers.items():
                if self.audit.pending.get(tid) is not originals[tid]:
                    self.cleared[tid] = self.removal_reason(writer, tid, thread, body, scope,
                                                          stamp, number, clocks)
            # A new Write removes the old tombstone. A still-active malformed
            # Write remains active for base bookkeeping, as in exact #321.
            for tid, pending in self.audit.pending.items():
                if isinstance(pending, base._Write):
                    self.cleared.pop(tid, None)
        _require(len(self.cleared) <= base.MAX_STATES)

        writes = sum(delta[key] for key in _WRITE_COUNTERS)
        errors = delta["write_not_supported_errors"]
        _require(writes in (0, 1) and errors in (0, 1))
        if writes:
            self.writes.append(number)
        if errors:
            self.errors.append(number)
        _require(all(delta[key] in (0, 1) for keys in _TX_COUNTERS.values() for key in keys))
        events = [(kind, expected_scope) for kind, keys in _TX_COUNTERS.items()
                  for expected_scope, key in zip(SCOPES, keys) if delta[key]]
        _require(len(events) <= 1)
        unbound = delta["unbound_tx_records"]
        _require(unbound in (0, 1) and unbound <= len(events))
        if not events:
            return
        kind, observed_scope = events[0]
        _require(observed_scope == scope)
        cell = self.scopes[kind][scope]
        cell["total"] += 1
        cell["base_unbound" if unbound else "active_write_present"] += 1
        self.families[kind][_family(line, scope)] += 1
        self.syntax[kind][scope][_syntax(body, kind, scope)] += 1
        if unbound:
            reason = ("UNKNOWN_THREAD_IDENTITY" if thread is None else
                      self.cleared.get(thread, "NO_PENDING_SAME_THREAD_WRITE"))
            self.reasons[kind][scope][reason] += 1
        if kind == "ARROW":
            self.arrows.append((number, scope == "UNSCOPED", bool(unbound)))

    def report(self):
        self.finish_session()
        original = self.audit.report()
        result = {
            "schema": SCHEMA,
            "b3a30_inventory": original["inventory"],
            "log_error_categories": original["error_categories"],
            "error_connect_candidates": original["error_connect_candidates"],
            "marker_scope_counts": self.scopes,
            "unbound_reason_counts": self.reasons,
            "header_family_counts": self.families,
            "marker_syntax_counts": self.syntax,
            "source_order_proximity": self.proximity,
            "bookkeeping": {"all_invariants_passed": True},
            "claims": {
                "audit_execution_on_supplied_input": "COMPLETED",
                "log_error_categories_computed": True,
                "input_authenticity": "NOT_VERIFIED",
                "actual_transport": "UNVERIFIED",
                "connect_success": "NOT_PROVEN",
                "physical_ecu_rx": "NOT_PROVEN",
                "original_vida_automatic_vin": "NOT_PROVEN",
                "unscoped_marker_error_attribution": "NOT_ESTABLISHED",
                "proximity_meaning": "SOURCE_ROW_ORDER_ONLY_WITHIN_LOGSESSION",
                "proximity_reference_policy": "PARAMETERIZED_WRITE_RECORDS_AND_ERR_NOT_SUPPORTED_MENTIONS",
            },
            "contains_source_data": False,
            "replay_approved": False,
        }
        _validate_report(result)
        return result


def _validate_report(report):
    _require(set(report) == {"schema", "b3a30_inventory", "log_error_categories",
             "error_connect_candidates", "marker_scope_counts", "unbound_reason_counts",
             "header_family_counts", "marker_syntax_counts", "source_order_proximity",
             "bookkeeping", "claims", "contains_source_data", "replay_approved"})
    _require(report["schema"] == SCHEMA)
    inventory = report["b3a30_inventory"]
    _require(set(inventory) == set(_INVENTORY_KEYS))
    _require(all(type(n) is int and n >= 0 for n in inventory.values()))
    _require(set(report["log_error_categories"]) == set(base.ERROR_CATEGORIES))
    _require(set(report["error_connect_candidates"]) == set(base.CONNECT_CATEGORIES))
    for key in ("log_error_categories", "error_connect_candidates"):
        _require(all(type(n) is int and n >= 0 for n in report[key].values()))
    for key in ("marker_scope_counts", "unbound_reason_counts", "header_family_counts", "marker_syntax_counts"):
        _require(set(report[key]) == set(KINDS))
        if key != "header_family_counts":
            _require(all(set(report[key][kind]) == set(SCOPES) for kind in KINDS))
    total_unbound = 0
    for kind in KINDS:
        total = 0
        for scope, counter in zip(SCOPES, _TX_COUNTERS[kind]):
            counts = report["marker_scope_counts"][kind][scope]
            reasons = report["unbound_reason_counts"][kind][scope]
            syntax = report["marker_syntax_counts"][kind][scope]
            _require(set(counts) == {"total", "active_write_present", "base_unbound"})
            _require(set(reasons) == set(REASONS) and set(syntax) == set(SYNTAX))
            _require(all(type(n) is int and n >= 0 for n in (*counts.values(), *reasons.values(), *syntax.values())))
            _require(counts["total"] == inventory[counter]
                     == counts["active_write_present"] + counts["base_unbound"])
            _require(sum(reasons.values()) == counts["base_unbound"])
            _require(sum(syntax.values()) == counts["total"])
            if scope == "UNSCOPED":
                _require(counts["active_write_present"] == 0)
                _require(reasons["UNKNOWN_THREAD_IDENTITY"] == counts["total"])
            total += counts["total"]
            total_unbound += counts["base_unbound"]
        families = report["header_family_counts"][kind]
        _require(set(families) == set(FAMILIES) and sum(families.values()) == total)
        _require(all(type(n) is int and n >= 0 for n in families.values()))
        scopes = report["marker_scope_counts"][kind]
        _require(families["EXACT_COMPONENT_BRACKETS"] == scopes["EXACT_COMPONENT"]["total"])
        _require(families["OTHER_COMPONENT_BRACKETS"] == scopes["OTHER_COMPONENT"]["total"])
    _require(inventory["alternate_tx_records"] == sum(
        report["marker_scope_counts"]["ALTERNATE"][scope]["total"] for scope in SCOPES))
    _require(inventory["malformed_tx_records"] == sum(
        report["marker_syntax_counts"][kind][scope]["MALFORMED_SYNTAX"] for kind in KINDS for scope in SCOPES))
    _require(inventory["unvalidated_tx_records"] == sum(
        report["marker_syntax_counts"][kind][scope]["UNVALIDATED_IDENTITY"] for kind in KINDS for scope in SCOPES))
    _require(total_unbound == inventory["unbound_tx_records"])
    _require(sum(report["log_error_categories"].values()) == inventory["write_not_supported_errors"])
    _require(sum(report["error_connect_candidates"].values()) ==
             inventory["write_not_supported_errors"] - report["log_error_categories"]["UNMATCHED_ERROR"])
    arrows = report["marker_scope_counts"]["ARROW"]
    expected = {"UNSCOPED_ARROWS": arrows["UNSCOPED"]["total"],
                "BASE_UNBOUND_ARROWS": sum(cell["base_unbound"] for cell in arrows.values())}
    _require(set(report["source_order_proximity"]) == set(COHORTS))
    for cohort in COHORTS:
        _require(set(report["source_order_proximity"][cohort]) == set(DIRECTIONS))
        for direction in DIRECTIONS:
            counts = report["source_order_proximity"][cohort][direction]
            _require(set(counts) == set(BUCKETS))
            _require(all(type(n) is int and n >= 0 for n in counts.values()))
            _require(sum(counts.values()) == expected[cohort])
    _require(report["bookkeeping"] == {"all_invariants_passed": True})


def audit_lines(lines):
    overlay = _Overlay()
    total = 0
    for number, raw in enumerate(lines, 1):
        if not isinstance(raw, str) or len(raw) > base.MAX_LINE or number > base.MAX_LINES:
            raise ValueError("input limit exceeded")
        size = len(raw.encode("utf-8"))
        total += size
        if size > base.MAX_LINE or total > base.MAX_BYTES or "\x00" in raw:
            raise ValueError("input limit exceeded")
        line = raw.rstrip("\r\n")
        if "\r" in line or "\n" in line:
            raise ValueError("invalid row")
        overlay.feed(line, number)
    return overlay.report()


class _SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "B3A31 FAIL-CLOSED: invalid command arguments.\n")


def main(argv=None):
    parser = _SafeParser(description=__doc__)
    parser.add_argument("--vida-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = audit_lines(base._file_lines(args.vida_log))
        text = json.dumps(report, ensure_ascii=True, indent=2) + "\n"
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(text)
        print("B3A31: aggregate bookkeeping checked; input and transport remain unverified.")
        return 0
    except (OSError, ValueError, OverflowError, KeyError, TypeError):
        parser.exit(2, "B3A31 FAIL-CLOSED: input, bookkeeping or output rejected.\n")


if __name__ == "__main__":
    sys.exit(main())
