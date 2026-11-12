#!/usr/bin/env python3
"""Summarize P3Tool-relevant J2534 Connect and SET_CONFIG from Virtual Car text log.

Only exact, 16-byte, big-endian *metadata* events emitted by Virtual Car are
parsed. All CAN TX/RX, host names, PID, VIN, paths and arbitrary values remain
local and are never placed in the JSON output. No protocol alias is assumed.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

FORMAT = "virtualcar-j2534-connect-audit-v2"
CONNECT = "J2534 Connect result protocol/flags/baud/status (BE)"
CONFIG = "J2534 SET_CONFIG channel/parameter/value/applied (BE)"
PREFIX = re.compile(r"^\[PID=[0-9a-fA-F]{8} [^\]\r\n]{1,80}\] ")
HEX_BYTE = re.compile(r"[0-9A-Fa-f]{2}\Z")
PROTOCOLS = {5: "CAN", 6: "ISO15765", 0x8004: "CAN_PS",
             0x8005: "ISO15765_PS", 0x10000001: "CAN_XON_XOFF"}
FLAGS = {0: "none", 0x100: "CAN_29BIT_ID", 0x20000000: "VOLVO_CH2", 0x600: "CAN_11BIT_ID_HS",
         0x20000600: "CAN_11BIT_ID_LS"}
BAUDS = {125000: "125000", 250000: "250000", 500000: "500000"}
STATUS = {0: "ok", 3: "invalid_protocol", 4: "null_parameter",
          12: "channel_limit", 25: "invalid_baud", 26: "invalid_device"}
PARAMS = {1: "DATA_RATE", 3: "LOOP_BACK", 23: "BIT_SAMPLE_POINT",
          30: "ISO15765_BS", 31: "ISO15765_STMIN", 779: "LEGACY_PARAMETER_779",
          0x8001: "J2534_PINS"}
MAX_LINES = 250000
MAX_LINE = 512


def _decode_words(text):
    parts = text.strip().split(" ")
    if len(parts) != 16 or any(HEX_BYTE.fullmatch(x) is None for x in parts):
        return None
    data = bytes(int(part, 16) for part in parts)
    return tuple(int.from_bytes(data[i:i + 4], "big") for i in (0, 4, 8, 12))


def audit(lines):
    connects = Counter()
    configs = Counter()
    invalid_connect = invalid_config = 0
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
        if content.startswith(CONNECT):
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
            channel, parameter, value, applied = words
            if channel == 0 or applied not in (0, 1):
                invalid_config += 1
                continue
            if parameter == 1:
                handling = "applied_baud" if applied else "accepted_no_effect"
            elif parameter == 0x8001:
                # The PS laboratory applies only 0x030B to a virtual channel.
                # A local J2534 pin setting is NOT physical bus evidence.
                if applied and value != 0x030B:
                    invalid_config += 1
                    continue
                handling = "virtual_ms_pins_applied" if applied else "accepted_no_effect"
            elif parameter == 0 and value == 0 and applied:
                # PR #319 may redact an applied K-Line option to all zeros.
                # The original parameter identity is not recoverable here.
                handling = "redacted_applied_unidentified"
            elif applied:
                invalid_config += 1
                continue
            else:
                handling = "accepted_no_effect"
            key = (PARAMS.get(parameter, "other"), handling)
            configs[key] += 1
    statuses = Counter()
    for (_proto, _flags, _baud, status), count in connects.items():
        statuses[status] += count
    return {
        "format": FORMAT,
        "source_scope": "exact_virtualcar_j2534_metadata_only",
        "contains_payload_data": False,
        "vehicle_identity_verified": False,
        "p2_p3_compatibility_verified": False,
        "limitations": [
            "Connect OK proves only virtual channel allocation, not ECU discovery",
            "VOLVO_CH2 is a recorded numeric flag, not a simulated physical LS bus",
            "J2534-2 PS support depends on the exact build and explicit lab configuration; no physical pins are verified",
            "SET_CONFIG virtual_ms_pins_applied is virtual channel state, not CAN wire or ECU RX",
            "Redacted applied parameter cannot be attributed to ISO9141 setting by this audit",
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
