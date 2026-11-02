#!/usr/bin/env python3
"""Summarize P3Tool-relevant J2534 Connect and SET_CONFIG from Virtual Car text log.

Only exact, allowlisted big-endian *metadata* events emitted by Virtual Car are
parsed. All CAN TX/RX, host names, PID, VIN, paths and arbitrary values remain
local and are never placed in the JSON output. No protocol alias is assumed.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

FORMAT = "virtualcar-j2534-connect-audit-v1"
CONNECT = "J2534 Connect result protocol/flags/baud/status (BE)"
CONFIG = "J2534 SET_CONFIG channel/parameter/value/applied (BE)"
PS_PROBE = "J2534 CAN_PS config probe channel/operation/value/status (BE)"
PS_REJECTED = "J2534 CAN_PS rejected attempt channel/origin/pins/msg-protocol/shape/check/status (BE)"
PS_FILTER = "J2534 CAN_PS rejected filter channel/type/protocols/sizes/flags/flow/mask/pattern/status (BE)"
PS_PERIODIC = "J2534 CAN_PS rejected periodic channel/protocol/interval/check/status (BE)"
PREFIX = re.compile(r"^\[PID=[0-9a-fA-F]{8} [^\]\r\n]{1,80}\] ")
HEX_BYTE = re.compile(r"[0-9A-Fa-f]{2}\Z")
PROTOCOLS = {5: "CAN", 6: "ISO15765", 0x8004: "CAN_PS",
             0x8005: "ISO15765_PS", 0x10000001: "CAN_XON_XOFF"}
FLAGS = {0: "none", 0x20000000: "VOLVO_CH2", 0x600: "CAN_11BIT_ID_HS",
         0x20000600: "CAN_11BIT_ID_LS"}
BAUDS = {125000: "125000", 250000: "250000", 500000: "500000"}
STATUS = {0: "ok", 1: "not_supported", 3: "invalid_protocol", 4: "null_parameter",
          5: "invalid_ioctl_value", 6: "invalid_flags",
          12: "channel_limit", 25: "invalid_baud", 26: "invalid_device"}
PARAMS = {1: "DATA_RATE", 3: "LOOP_BACK", 23: "BIT_SAMPLE_POINT",
          30: "ISO15765_BS", 31: "ISO15765_STMIN", 0x8001: "J1962_PINS"}
PS_OPERATIONS = {1: "channel_allocated", 2: "set_pin_observation", 3: "get_pin_observation",
                 4: "write_rejected", 5: "filter_rejected", 6: "periodic_rejected",
                 7: "config_rejected"}
PS_PINS = {0x030B: "pins_3_11", 0x060E: "pins_6_14"}
ATTEMPT_ORIGINS = {1: "write_call", 2: "periodic_registration_call"}
ATTEMPT_PROTOCOLS = {0: "uninspected_or_other", 5: "CAN", 6: "ISO15765", 0x8004: "CAN_PS"}
ATTEMPT_CHECKS = {0: "inspected_raw_classic_can", 1: "invalid_data_size",
                  2: "invalid_can_id", 3: "unsupported_message_protocol",
                  4: "outside_flag_address_catalog", 5: "zero_count",
                  6: "batch_uninspected"}
ATTEMPT_SHAPES = {
    0: "unknown", 1: "OBD_7DF_0902", 2: "OBD_7E0_0902",
    3: "TP_7DF_3E80", 4: "TP_FUNC29_3E80",
    40: "excluded_control_or_security", 41: "excluded_D2_control_prefix",
    42: "D2_D8_unverified_prefix",
}
FILTER_TYPES = {0: "other_redacted", 1: "pass_filter", 2: "block_filter", 3: "flow_control_filter"}
FILTER_PROTOCOLS = {0: "other_redacted", 1: "both_CAN_PS", 2: "both_CAN", 3: "both_ISO15765", 4: "mixed_known"}
FILTER_SIZES = {0: "outside_catalog", 1: "both_id_only", 2: "both_full_classic_can",
                3: "same_short_classic_can", 4: "different_within_catalog"}
FILTER_FLAGS = {0: "other_redacted", 1: "both_zero", 2: "both_extended", 3: "mixed_known"}
FILTER_MASKS = {0: "uninspected", 1: "zero", 2: "full_uint32", 3: "id_29_bits", 4: "id_11_bits", 5: "other_redacted"}
FILTER_PATTERNS = {0: "uninspected", 1: "zero", 2: "nonzero_11_bit_range", 3: "29_bit_range", 4: "outside_can_id_range"}
PERIODIC_INTERVALS = {value: str(value) for value in (5, 100, 250, 500, 1000, 2000, 4000, 5000, 10000, 60000)}
PERIODIC_CHECKS = {0: "valid_catalog_interval", 1: "valid_other_interval_redacted", 2: "invalid_interval_redacted"}
for _target, _base in (("40", 10), ("50", 15)):
    ATTEMPT_SHAPES.update({_base+i: f"D2_{_target}_{service}"
                           for i, service in enumerate(("A3", "A6", "B9F0", "B9FB", "B9FC"))})
for _target, _base in (("726", 20), ("29", 25)):
    ATTEMPT_SHAPES.update({_base+i: f"P3_{_target}_{did}"
                           for i, did in enumerate(("F114", "F1B0", "F1A3", "F106", "F190"))})
MAX_LINES = 250000
MAX_LINE = 512
MAX_REJECTED_ATTEMPTS = 20000


def _decode_words(text, word_count=4):
    parts = text.strip().split(" ")
    if len(parts) != word_count*4 or any(HEX_BYTE.fullmatch(x) is None for x in parts):
        return None
    data = bytes(int(part, 16) for part in parts)
    return tuple(int.from_bytes(data[i:i + 4], "big") for i in range(0, len(data), 4))


def _rejected_attempt(words):
    if words is None:
        return None
    channel, origin, pins, protocol, shape, check, status = words
    if (channel == 0 or origin not in ATTEMPT_ORIGINS or pins not in (0, *PS_PINS)
            or protocol not in ATTEMPT_PROTOCOLS or shape not in ATTEMPT_SHAPES
            or check not in ATTEMPT_CHECKS or status != 1):
        return None
    if check == 3:
        valid = protocol in (0, 6)
    elif check in (5, 6):
        valid = protocol == 0 and origin == 1
    else:
        valid = protocol in (5, 0x8004)
    if not valid or (check != 0 and shape != 0):
        return None
    return (ATTEMPT_ORIGINS[origin], PS_PINS.get(pins, "unselected"),
            ATTEMPT_PROTOCOLS[protocol], ATTEMPT_SHAPES[shape], ATTEMPT_CHECKS[check])


def _rejected_filter(words):
    if words is None:
        return None
    channel, kind, protocols, sizes, flags, flow, mask, pattern, status = words
    if (channel == 0 or kind not in FILTER_TYPES or protocols not in FILTER_PROTOCOLS
            or sizes not in FILTER_SIZES or flags not in FILTER_FLAGS or flow not in (0, 1)
            or mask not in FILTER_MASKS or pattern not in FILTER_PATTERNS or status != 1):
        return None
    inspected = protocols in (1, 2) and sizes == 1
    if (inspected and (mask == 0 or pattern == 0)) or (not inspected and (mask != 0 or pattern != 0)):
        return None
    return (FILTER_TYPES[kind], FILTER_PROTOCOLS[protocols], FILTER_SIZES[sizes],
            FILTER_FLAGS[flags], "present_uninspected" if flow else "absent",
            FILTER_MASKS[mask], FILTER_PATTERNS[pattern])


def _rejected_periodic(words):
    if words is None:
        return None
    channel, protocol, interval, check, status = words
    if channel == 0 or protocol not in ATTEMPT_PROTOCOLS or check not in PERIODIC_CHECKS or status != 1:
        return None
    if (check == 0 and interval not in PERIODIC_INTERVALS) or (check != 0 and interval != 0):
        return None
    return (ATTEMPT_PROTOCOLS[protocol], PERIODIC_INTERVALS.get(interval, "redacted"), PERIODIC_CHECKS[check])


def audit(lines):
    connects = Counter()
    configs = Counter()
    invalid_connect = invalid_config = 0
    ps_probes = Counter()
    invalid_ps = 0
    rejected = Counter()
    rejected_order = []
    invalid_rejected = 0
    filters, periodic = Counter(), Counter()
    invalid_filter = invalid_periodic = 0
    setup_order = []
    for index, raw in enumerate(lines, 1):
        if index > MAX_LINES:
            raise ValueError("line_limit")
        if len(raw) > MAX_LINE:
            # Raw TX/RX data and untrusted long text are not inspected.
            continue
        line = raw.rstrip("\r\n")
        prefix = PREFIX.match(line)
        if prefix is None:
            continue
        content = line[prefix.end():]
        if content.startswith(PS_FILTER) or content.startswith(PS_PERIODIC):
            is_filter = content.startswith(PS_FILTER)
            marker = PS_FILTER if is_filter else PS_PERIODIC
            words = _decode_words(content[len(marker):], 9 if is_filter else 5)
            setup = _rejected_filter(words) if is_filter else _rejected_periodic(words)
            if setup is None:
                if is_filter:
                    invalid_filter += 1
                else:
                    invalid_periodic += 1
                continue
            if len(setup_order) >= MAX_REJECTED_ATTEMPTS:
                raise ValueError("rejected_setup_limit")
            (filters if is_filter else periodic)[setup] += 1
            setup_order.append({"line": index, "api": "filter" if is_filter else "periodic_registration",
                                "outcome": "rejected_not_registered"})
        elif content.startswith(PS_REJECTED):
            attempt = _rejected_attempt(_decode_words(content[len(PS_REJECTED):], 7))
            if attempt is None:
                invalid_rejected += 1
                continue
            if len(rejected_order) >= MAX_REJECTED_ATTEMPTS:
                raise ValueError("rejected_attempt_limit")
            rejected[attempt] += 1
            rejected_order.append(dict(zip(
                ("origin", "pins", "message_protocol", "shape", "inspection"), attempt),
                line=index, outcome="rejected_not_transmitted"))
        elif content.startswith(PS_PROBE):
            words = _decode_words(content[len(PS_PROBE):])
            if words is None:
                invalid_ps += 1
                continue
            channel, operation, value, status = words
            valid = channel != 0 and operation in PS_OPERATIONS
            if operation == 1:
                valid = valid and value == 0x8004 and status == 0
                selection = "protocol_can_ps"
            elif operation == 2:
                valid = valid and ((value in PS_PINS and status in (0, 1)) or (value == 0 and status == 5))
                selection = PS_PINS.get(value, "redacted")
            elif operation == 3:
                valid = valid and value in (0, *PS_PINS) and status == 0
                selection = PS_PINS.get(value, "unselected")
            elif operation == 7:
                valid = valid and ((value == 1 and status == 25) or (value == 0 and status == 1))
                selection = "data_rate" if value == 1 else "redacted"
            else:
                valid = valid and value == 0 and status == 1
                selection = "none"
            if not valid:
                invalid_ps += 1
                continue
            ps_probes[(PS_OPERATIONS[operation], selection, STATUS[status])] += 1
        elif content.startswith(CONNECT):
            words = _decode_words(content[len(CONNECT):])
            if words is None:
                invalid_connect += 1
                continue
            protocol, flags, baud, status = words
            key = (PROTOCOLS.get(protocol, "other"),
                   FLAGS.get(flags, "other"),
                   BAUDS.get(baud, "other"),
                   STATUS.get(status, "other_error"))
            connects[key] += 1
        elif content.startswith(CONFIG):
            words = _decode_words(content[len(CONFIG):])
            if words is None:
                invalid_config += 1
                continue
            channel, parameter, _value, applied = words
            # A configured channel must be nonzero. A label of applied=1
            # is meaningful only for DATA_RATE in this Virtual Car build.
            if channel == 0 or applied not in (0, 1) or (applied and parameter != 1):
                invalid_config += 1
                continue
            key = (PARAMS.get(parameter, "other"),
                   "applied_baud" if applied else "accepted_no_effect")
            configs[key] += 1
    statuses = Counter()
    for (_proto, _flags, _baud, status), count in connects.items():
        statuses[status] += count
    report = {
        "format": FORMAT,
        "source_scope": "exact_virtualcar_j2534_metadata_only",
        "contains_payload_data": False,
        "vehicle_identity_verified": False,
        "p2_p3_compatibility_verified": False,
        "limitations": [
            "Connect OK proves only virtual channel allocation, not ECU discovery",
            "VOLVO_CH2 is a recorded numeric flag, not a simulated physical LS bus",
            "CAN_PS transport remains unsupported; an opt-in configuration-only probe may allocate a quarantined channel",
            "ISO15765_PS and CAN_XON_XOFF remain unsupported",
            "SET_CONFIG accepted_no_effect means success was returned but no physical option was implemented",
            "No raw CAN, VIN, keys, host names, process IDs, source paths or arbitrary parameters are exported",
        ],
        "connect": {
            "attempts": sum(connects.values()),
            "invalid_events": invalid_connect,
            "statuses": dict(sorted(statuses.items())),
            "modes": [
                {"protocol": protocol, "flags": flags, "baud_bps": baud,
                 "status": status, "count": count}
                for (protocol, flags, baud, status), count in sorted(connects.items())
            ],
        },
        "set_config": {
            "events": sum(configs.values()),
            "invalid_events": invalid_config,
            "parameters": [
                {"parameter": parameter, "handling": handling, "count": count}
                for (parameter, handling), count in sorted(configs.items())
            ],
        },
    }
    if ps_probes or invalid_ps:
        report["can_ps_config_probe"] = {
            "events": sum(ps_probes.values()), "invalid_events": invalid_ps,
            "mode": "configuration_only_no_transport",
            "state_correlation_performed": False,
            "hardware_pins_verified": False,
            "operations": [
                {"operation": operation, "selection": selection, "status": status, "count": count}
                for (operation, selection, status), count in sorted(ps_probes.items())
            ],
        }
    if rejected or invalid_rejected:
        report["rejected_can_ps_attempts"] = {
            "calls": sum(rejected.values()), "invalid_events": invalid_rejected,
            "outcome": "rejected_not_transmitted",
            "classification_scope": "lexical_request_shape_only",
            "state_correlation_performed": False,
            "hardware_pins_verified": False,
            "ecu_response_verified": False,
            "read_only_reference_approved": False,
            "periodic_firing_observed": False,
            "categories": [
                dict(zip(("origin", "pins", "message_protocol", "shape", "inspection"), key), count=count)
                for key, count in sorted(rejected.items())
            ],
            "source_order": rejected_order,
        }
    if filters or periodic or invalid_filter or invalid_periodic:
        report["can_ps_rejected_setup"] = {
            "filter_calls": sum(filters.values()), "invalid_filter_events": invalid_filter,
            "periodic_registration_calls": sum(periodic.values()), "invalid_periodic_events": invalid_periodic,
            "classification_scope": "api_setup_argument_categories_only",
            "outcome": "rejected_not_registered",
            "state_correlation_performed": False, "hardware_pins_verified": False,
            "read_only_reference_approved": False, "periodic_firing_observed": False,
            "filters": [
                dict(zip(("type", "message_protocols", "sizes", "flags", "flow", "mask", "pattern"), key), count=count)
                for key, count in sorted(filters.items())
            ],
            "periodic": [
                dict(zip(("message_protocol", "interval_ms", "interval_check"), key), count=count)
                for key, count in sorted(periodic.items())
            ],
            "source_order": setup_order,
        }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path,
                        help="Private local SectorVVirtualCar.log, never sent to GitHub")
    parser.add_argument("--output", type=Path, required=True,
                        help="New metadata-only JSON output, must not already exist")
    args = parser.parse_args(argv)
    with args.source.open("r", encoding="utf-8", errors="replace") as source:
        result = audit(source)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, ensure_ascii=False, sort_keys=True)
        output.write("\n")


if __name__ == "__main__":
    main()
