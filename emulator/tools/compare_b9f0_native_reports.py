#!/usr/bin/env python3
"""Compare two privacy-safe native D2 audits without reopening source CAN logs.

Both inputs MUST be freshly generated with the same current B9F0 audit.
Numeric differences are observations only, never proof of logger-fix causality,
physical CAN, B9F0 ECU identity, or SectorV/VIDA acceptance.
"""
import argparse
import json
from pathlib import Path
import sys

SCHEMA = "virtualcar-b9f0-emitter-rx-v1"
OUTPUT_SCHEMA = "virtualcar-b9f0-native-before-after-v1"
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_ROWS = 6000000
MAX_TAGS = 150000

CATEGORY_KEYS = frozenset((
    "paired_strict_native_rx_tag", "malformed_tag",
    "unpaired_no_prior_rx", "unpaired_rx_context_without_delivery",
    "unpaired_invalid_rx_context", "unpaired_session_or_channel_boundary",
    "unpaired_delivery_without_valid_rx_context",
    "unpaired_nonclassic_or_invalid_rx_record",
    "unpaired_pending_rx_without_tag", "unpaired_intervening_hardware_observer",
    "unpaired_intervening_d2_event", "unpaired_intervening_j2534_event",
    "unpaired_intervening_other_same_pid_event",
    "unpaired_other_unverified_predecessor",
    "mismatch_invalid_generation_or_frame", "mismatch_channel",
    "mismatch_protocol_not_can", "mismatch_zero_baud",
    "mismatch_rx_status", "mismatch_rx_length",
))
PREDECESSOR_KEYS = frozenset((
    "unpaired_no_prior_rx", "unpaired_invalid_rx_context",
    "unpaired_session_or_channel_boundary",
    "unpaired_intervening_hardware_observer", "unpaired_intervening_d2_event",
    "unpaired_intervening_j2534_event",
    "unpaired_intervening_other_same_pid_event",
    "unpaired_other_unverified_predecessor",
))
PREVIOUS_EVENT_KEYS = frozenset((
    "none", "rx_context", "rx_delivery", "d2_delivery_tag",
    "hardware_rx_observer", "hardware_other_observer", "tx_context",
    "tx_request", "periodic_tx_context", "clear_rx_context", "open_boundary",
    "close_boundary", "disconnect_boundary", "d2_request", "other_d2_marker",
    "other_passthru_marker", "other_j2534_marker", "other_native_event",
))
BRIDGE_KEYS = frozenset((
    "native_shape_consistent_only", "metadata_mismatch", "malformed_tag",
    "interrupted_before_tag",
))
WIDE_KEYS = frozenset((
    "byte_swapped_known_id_shape", "all_bits_set", "other_16bit_value",
    "low_word_zero", "other_32bit_value",
))
NON_CAN_KEYS = frozenset(("ISO15765_6", "other_non_CAN"))
OTHER_PROTOCOL_KEYS = frozenset(("other_protocol_value",) +
                               tuple("protocol_" + str(i) for i in range(13)))


class CompareError(Exception):
    """Failures must never disclose raw report contents or source paths."""


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CompareError("duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(_value):
    raise CompareError("non_finite_json_value")


def read_report(path):
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
            raise CompareError("invalid_input_file")
        with path.open("r", encoding="utf-8-sig") as src:
            return json.load(src, object_pairs_hook=_no_duplicates,
                             parse_constant=_reject_constant)
    except CompareError:
        raise
    except (OSError, ValueError, UnicodeError, RecursionError):
        raise CompareError("invalid_input_json") from None


def _counter(value, max_value):
    if type(value) is not int or not 0 <= value <= max_value:
        raise CompareError("invalid_counter")
    return value


def _mapping(value, allowed):
    if not isinstance(value, dict) or not set(value) <= allowed:
        raise CompareError("unexpected_counter_category")
    return {name: _counter(count, MAX_TAGS) for name, count in value.items()}


def _flag(value, expected):
    if value is not expected:
        raise CompareError("invalid_evidence_flag")


def _must_dict(value):
    if not isinstance(value, dict):
        raise CompareError("invalid_report_section")
    return value


def validate_report(report):
    r = _must_dict(report)
    if r.get("schema_version") != SCHEMA:
        raise CompareError("unsupported_schema")
    _flag(r.get("complete_source_scan"), True)
    _flag(r.get("real_ecu_response_verified"), False)
    _flag(r.get("sectorv_ecu_identity_accepted_verified"), False)

    scan = _must_dict(r.get("source_scan_counts"))
    rows = _counter(scan.get("source_rows_scanned"), MAX_ROWS)
    tag_rows = _counter(scan.get("tag_rows"), MAX_TAGS)
    oversized = _counter(scan.get("oversized_rows_ignored"), MAX_ROWS)
    if tag_rows > rows or oversized > rows:
        raise CompareError("inconsistent_source_counts")

    native = _must_dict(r.get("native_d2_delivery_tags"))
    d = _must_dict(r.get("tag_adjacency_diagnostics"))
    for key in ("replay_approved", "b9f0_replay_stage_correlated_to_rx",
                "b9f0_original_client_ecu_identity_accepted"):
        _flag(native.get(key), False)
    if (native.get("physical_can_or_ecu_provenance") != "not_verified"
            or native.get("client_vin_and_ecu_acceptance") != "not_verified"):
        raise CompareError("invalid_native_evidence")
    if native.get("source") != "local_emulator_native_d2_delivery_tags_only":
        raise CompareError("invalid_native_source")
    _flag(native.get("observed"), tag_rows > 0)

    fields = (
        "tag_records", "paired_tag_records", "unpaired_tag_records",
        "malformed_tag_records", "route_or_metadata_mismatch", "generation_groups",
        "groups_with_frame_indices_1_to_n",
        "groups_with_missing_duplicate_or_out_of_order_indices",
        "b9fb_13frame_control_sequence_groups",
        "b9f0_emitter_rx_groups_with_positive_first_echo",
        "b9f0_emitter_rx_groups_with_contiguous_terminal",
    )
    n = {key: _counter(native.get(key), MAX_TAGS) for key in fields}
    if (n["tag_records"] != tag_rows
            or n["paired_tag_records"] + n["unpaired_tag_records"]
            + n["malformed_tag_records"] + n["route_or_metadata_mismatch"] != tag_rows
            or n["generation_groups"] > n["paired_tag_records"]
            or n["groups_with_frame_indices_1_to_n"]
            + n["groups_with_missing_duplicate_or_out_of_order_indices"]
            != n["generation_groups"]
            or n["b9fb_13frame_control_sequence_groups"] > n["generation_groups"]
            or n["b9f0_emitter_rx_groups_with_contiguous_terminal"]
            > n["b9f0_emitter_rx_groups_with_positive_first_echo"]
            or n["b9f0_emitter_rx_groups_with_positive_first_echo"]
            > n["generation_groups"]):
        raise CompareError("inconsistent_native_totals")
    # These lists can contain source-dependent baud/target metadata. Check their
    # counted totals without copying any list member to the comparison output.
    groups = native.get("b9f0_emitter_rx_groups")
    if not isinstance(groups, list) or len(groups) > MAX_TAGS:
        raise CompareError("invalid_b9f0_groups")
    group_sum = 0
    terminal_sum = 0
    for entry in groups:
        entry = _must_dict(entry)
        if (entry.get("target") not in ("0x40", "0x50")
                or entry.get("delivery_shape") not in (
                    "delivered_contiguous_terminal_shape", "partial_or_ambiguous")):
            raise CompareError("invalid_b9f0_group_shape")
        baud = entry.get("baud_bps")
        if baud != "mixed" and (type(baud) is not int or not 0 < baud <= 1000000):
            raise CompareError("invalid_b9f0_group_baud")
        count = _counter(entry.get("count"), MAX_TAGS)
        group_sum += count
        if entry["delivery_shape"] == "delivered_contiguous_terminal_shape":
            terminal_sum += count
    if (group_sum != n["b9f0_emitter_rx_groups_with_positive_first_echo"]
            or terminal_sum != n["b9f0_emitter_rx_groups_with_contiguous_terminal"]):
        raise CompareError("inconsistent_b9f0_groups")

    if d.get("scope") != "categorical_same_pid_native_rx_adjacency_only":
        raise CompareError("unsupported_attribution_scope")
    for key in (
        "category_totals_agree_with_legacy_auditor",
        "missing_rx_context_predecessor_counts_reconcile",
        "non_CAN_protocol_counts_reconcile", "non_CAN_other_values_reconcile",
        "non_CAN_wide_protocol_shapes_reconcile",
        "no_prior_rx_previous_events_reconcile",
        "observer_only_bridge_counts_reconcile",
    ):
        _flag(d.get(key), True)
    _flag(d.get("observer_only_bridge_is_strict_delivery_evidence"), False)
    _flag(d.get("b9f0_specific_causal_attribution_verified"), False)
    cats = _mapping(d.get("categories"), CATEGORY_KEYS)
    prev = _mapping(d.get("missing_rx_context_predecessor_categories"), PREDECESSOR_KEYS)
    non_can = _mapping(d.get("non_CAN_protocol_categories"), NON_CAN_KEYS)
    other = _mapping(d.get("non_CAN_other_protocol_values"), OTHER_PROTOCOL_KEYS)
    wide = _mapping(d.get("non_CAN_wide_protocol_shapes"), WIDE_KEYS)
    previous_events = _mapping(d.get("no_prior_rx_previous_event_classes"), PREVIOUS_EVENT_KEYS)
    bridges = _mapping(d.get("observer_only_bridge_outcomes"), BRIDGE_KEYS)
    started = _counter(d.get("observer_only_bridge_candidates_started"), MAX_TAGS)
    incomplete = _counter(d.get("observer_only_bridge_incomplete_at_scan_end"), MAX_TAGS)
    if (sum(cats.values()) != tag_rows
            or _counter(d.get("total_tag_records_classified"), MAX_TAGS) != tag_rows
            or cats.get("paired_strict_native_rx_tag", 0) != n["paired_tag_records"]
            or cats.get("malformed_tag", 0) != n["malformed_tag_records"]
            or sum(v for key, v in cats.items() if key.startswith("unpaired_"))
            != n["unpaired_tag_records"]
            or sum(v for key, v in cats.items() if key.startswith("mismatch_"))
            != n["route_or_metadata_mismatch"]
            or sum(prev.values()) != cats.get("unpaired_delivery_without_valid_rx_context", 0)
            or sum(non_can.values()) != cats.get("mismatch_protocol_not_can", 0)
            or sum(other.values()) != non_can.get("other_non_CAN", 0)
            or sum(wide.values()) != other.get("other_protocol_value", 0)
            or sum(previous_events.values()) != prev.get("unpaired_no_prior_rx", 0)
            or started != sum(bridges.values()) + incomplete
            or bridges.get("native_shape_consistent_only", 0)
            > cats.get("unpaired_intervening_hardware_observer", 0)):
        raise CompareError("inconsistent_adjacency_totals")
    return {
        "rows": rows, "tags": tag_rows, "oversized": oversized,
        "metrics": {
            "strict_paired": n["paired_tag_records"],
            "unpaired": n["unpaired_tag_records"],
            "malformed": n["malformed_tag_records"],
            "metadata_mismatch": n["route_or_metadata_mismatch"],
            "non_can_protocol_mismatch": cats.get("mismatch_protocol_not_can", 0),
            "wide_protocol_value": other.get("other_protocol_value", 0),
            "no_valid_rx_context": cats.get("unpaired_delivery_without_valid_rx_context", 0),
            "hw_observer_interrupted_strict": cats.get("unpaired_intervening_hardware_observer", 0),
            "observer_only_shape_consistent": bridges.get("native_shape_consistent_only", 0),
            "observer_only_shape_mismatch": bridges.get("metadata_mismatch", 0),
            "observer_only_interrupted": bridges.get("interrupted_before_tag", 0),
            "b9fb_13frame_emitter_groups": n["b9fb_13frame_control_sequence_groups"],
            "b9f0_contiguous_terminal_emitter_groups": n["b9f0_emitter_rx_groups_with_contiguous_terminal"],
        },
    }


def _per_1000(count, tags):
    return round(1000 * count / tags, 3) if tags else None


def compare(before, after):
    left, right = validate_report(before), validate_report(after)
    return {
        "schema_version": OUTPUT_SCHEMA,
        "scope": "same_auditor_schema_aggregate_d2_tag_comparison_only",
        "report_inputs_validated": True,
        "same_diagnostic_workload_verified": False,
        "after_capture_uses_append_only_logger_verified": False,
        "logger_fix_causal_effect_verified": False,
        "original_vida_or_sectorv_vin_accepted_verified": False,
        "b9f0_ecu_identity_accepted_verified": False,
        "physical_can_ecu_provenance_verified": False,
        "before_scan": {"rows": left["rows"], "d2_tags": left["tags"],
                        "oversized_rows_ignored": left["oversized"]},
        "after_scan": {"rows": right["rows"], "d2_tags": right["tags"],
                       "oversized_rows_ignored": right["oversized"]},
        "sample_sizes_equal": left["tags"] == right["tags"],
        "insufficient_tag_evidence": not (left["tags"] and right["tags"]),
        "metric_differences": {
            key: {"before": left["metrics"][key], "after": right["metrics"][key],
                  "delta": right["metrics"][key] - left["metrics"][key],
                  "before_per_1000_d2_tags": _per_1000(left["metrics"][key], left["tags"]),
                  "after_per_1000_d2_tags": _per_1000(right["metrics"][key], right["tags"])}
            for key in left["metrics"]
        },
        "notes": [
            "Re-audit both private native logs using the same current analyzer before comparing.",
            "The after scan must be captured after installing the append-only DLL; reports cannot attest installed binaries.",
            "Changes in rates can reflect different clients, sessions, workloads or logging, not necessarily the patch.",
            "An observer-only bridge never upgrades a strict D2 delivery or B9F0 ECU identity.",
            "No source filename, raw CAN, VIN, PID, original timestamp or client identity is exported.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only before/after native D2 audit comparison")
    parser.add_argument("--before-report", type=Path, required=True)
    parser.add_argument("--after-report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = compare(read_report(args.before_report), read_report(args.after_report))
    except CompareError:
        print('ERROR: invalid_or_unverified_aggregate_reports', file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
