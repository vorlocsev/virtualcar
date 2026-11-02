#!/usr/bin/env python3
"""Audit user-provided recovered .NET IL evidence; never export raw proprietary text.

This tool does NOT deobfuscate binaries, execute VDASH or infer CAN traffic.
Its output is an allowlisted method/shape summary from an independently supplied
inventory JSON and IL excerpt. No source paths, VINs or string literals escape.
"""
import argparse
import json
import re
from pathlib import Path

HEADER = re.compile(r"^([^:\n]+): MethodDef (0x[0-9A-Fa-f]{8}) (.+?); (\d+) decoded opcodes$")
IL = re.compile(r"^IL_([0-9A-Fa-f]{4,8})\s+([A-Za-z0-9_.]+)(?:\s+(.*?))?\s*$")
TOKEN = re.compile(r"0x[0-9A-Fa-f]{8}")
IMPORTANT = ("0x06001329", "0x0600132C", "0x06001160", "0x06002472", "0x060002EF")
KNOWN = {
    "detect": "0x0600132B",
    "execute": "0x0600115D",
    "pre_detect": "0x0600133D",
    "get_vin": "0x0600133A",
    "parse_data": "0x06001160",
    "ui_done": "0x06002472",
    "send_v2": "0x060002EF",
}


def parse_excerpts(text):
    """Read intact MethodDef blocks and verify exact decoded opcode counts."""
    blocks = {}
    current = None
    for line in text.splitlines():
        heading = HEADER.fullmatch(line.strip())
        if heading:
            token = heading.group(2).upper().replace("0X", "0x")
            if token in blocks:
                raise ValueError("duplicate_method_token")
            current = {"declared": int(heading.group(4)), "ops": []}
            blocks[token] = current
            continue
        if line.startswith("IL_"):
            if current is None:
                raise ValueError("unattributed_il")
            op = IL.fullmatch(line)
            if not op:
                raise ValueError("invalid_il_line")
            current["ops"].append((op.group(2), (op.group(3) or "").strip()))
    if not blocks:
        raise ValueError("no_method_bodies")
    for item in blocks.values():
        if len(item["ops"]) != item["declared"]:
            raise ValueError("truncated_or_mismatched_il_body")
    return blocks


def _has_call(ops, token):
    return any(op in ("call", "callvirt") and (TOKEN.search(arg) is not None)
               and TOKEN.search(arg).group(0).upper() == token.upper()
               for op, arg in ops)


def _status_values(ops):
    values = set()
    for a, b in zip(ops, ops[1:]):
        if a[0] in ("call", "callvirt") and a[1].startswith("0x06001178"):
            if b[0] in ("ldc.i4.2", "ldc.i4.3", "ldc.i4.4"):
                values.add(int(b[0][-1]))
    return sorted(values)


def _one_shot_timer_shape(ops):
    # Only recognises the exact recovered IL shape. The unknown helper
    # 0x0600117C might not be the Timer constructor; do not infer execution.
    required = [
        ("ldftn", "0x0600115F"),
        ("newobj", "System.Threading.TimerCallback..ctor"),
        ("ldc.r8", "1.0"),
        ("call", "System.TimeSpan.FromSeconds"),
        ("ldsfld", "System.Threading.Timeout.InfiniteTimeSpan"),
        ("call", "0x0600117C"),
        ("stfld", "0x04000334"),
    ]
    found_at = -1
    for op, arg in ops:
        if required[found_at + 1][0] == op and required[found_at + 1][1] in arg:
            found_at += 1
            if found_at + 1 == len(required):
                return True
    return False


def audit(inventory, excerpts):
    selected = inventory.get("selected_methods")
    if not isinstance(selected, list) or not selected:
        raise ValueError("invalid_inventory")
    tokens = set()
    for method in selected:
        token = method.get("method_token")
        if not isinstance(token, str) or not TOKEN.fullmatch(token):
            raise ValueError("invalid_inventory_token")
        if token in tokens:
            raise ValueError("duplicate_inventory_token")
        tokens.add(token)
    blocks = parse_excerpts(excerpts)
    for token, body in blocks.items():
        if token not in tokens:
            raise ValueError("excerpt_method_not_in_inventory")
        item = next(x for x in selected if x["method_token"] == token)
        if item.get("decoded_instructions") != body["declared"]:
            raise ValueError("inventory_excerpt_disagreement")

    detect = blocks.get(KNOWN["detect"], {}).get("ops", [])
    execute = blocks.get(KNOWN["execute"], {}).get("ops", [])
    predetect = blocks.get(KNOWN["pre_detect"], {}).get("ops", [])
    getvin = blocks.get(KNOWN["get_vin"], {}).get("ops", [])
    # Fixed schema, no raw strings, source path, VIN, PID or private methods.
    return {
        "format": "recovered-il-evidence-audit-v1",
        "selected_methods": len(tokens),
        "fully_extracted_excerpt_methods": len(blocks),
        "unexpanded_selected_methods": len(tokens - set(blocks)),
        "verified_opcode_count": sum(x["declared"] for x in blocks.values()),
        "missing_priority_bodies": [
            label for label in ("parse_data", "ui_done", "send_v2")
            if KNOWN[label] in tokens and KNOWN[label] not in blocks
        ],
        "evidence": {
            "pre_detect_uses_suggested_vin": _has_call(predetect, "0x0600020C"),
            "pre_detect_uses_last_view_wrapper": _has_call(predetect, "0x06001377"),
            "get_vin_reads_pre_detect_result": _has_call(getvin, "0x060012F2"),
            "detect_calls_create_command": _has_call(detect, "0x06001329"),
            "detect_calls_enqueue": _has_call(detect, "0x0600132C"),
            "detect_calls_wait": _has_call(detect, "0x0600115B"),
            "detect_assigns_ecus_model": _has_call(detect, "0x060012DF"),
            "detect_fires_done": _has_call(detect, "0x06001343"),
            "execute_calls_parse_data": _has_call(execute, "0x06001160"),
            "execute_observed_status_numeric_comparisons": _status_values(execute),
            "execute_one_second_timer_shape": _one_shot_timer_shape(execute),
        },
        "limitations": [
            "Method references do not prove execution order in flattened CFG",
            "Enum meaning and unknown wrapper effects not established",
            "No J2534 request/ECU acceptance claim from recovered IL alone",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--excerpts", type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    report = audit(json.loads(args.inventory.read_text(encoding="utf-8")),
                   args.excerpts.read_text(encoding="utf-8"))
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
