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
# MethodDef tokens are unique only *inside an assembly*, not globally.
KNOWN = {
    "detect": ("Frontend.Client.Core.dll", "0x0600132B"),
    "execute": ("Frontend.Client.Core.dll", "0x0600115D"),
    "pre_detect": ("Frontend.Client.Core.dll", "0x0600133D"),
    "get_vin": ("Frontend.Client.Core.dll", "0x0600133A"),
    "get_config": ("Frontend.Client.Core.dll", "0x06001339"),
    "parse_data": ("Frontend.Client.Core.dll", "0x06001160"),
    "ui_done": ("Frontend.exe", "0x06002472"),
    "send_v2": ("Client.Core.dll", "0x060002EF"),
}


def parse_excerpts(text):
    """Read intact MethodDef blocks and verify exact decoded opcode counts."""
    blocks = {}
    current = None
    for line in text.splitlines():
        heading = HEADER.fullmatch(line.strip())
        if heading:
            token = heading.group(2).upper().replace("0X", "0x")
            key = (heading.group(1), token)
            if key in blocks:
                raise ValueError("duplicate_method_token")
            current = {"declared": int(heading.group(4)), "ops": [], "offsets": []}
            blocks[key] = current
            continue
        if line.startswith("IL_"):
            if current is None:
                raise ValueError("unattributed_il")
            op = IL.fullmatch(line)
            if not op:
                raise ValueError("invalid_il_line")
            offset = int(op.group(1), 16)
            if current["offsets"] and offset <= current["offsets"][-1]:
                raise ValueError("nonmonotonic_il_offsets")
            current["offsets"].append(offset)
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


def _has_motif(ops, steps):
    """Contiguous CIL shape only; no claim the CFG reaches this code."""
    if not steps or len(ops) < len(steps):
        return False
    for start in range(len(ops) - len(steps) + 1):
        if all(
            actual[0] == expected[0]
            and (expected[1] is None or actual[1].startswith(expected[1]))
            for actual, expected in zip(ops[start:start + len(steps)], steps)
        ):
            return True
    return False


def _model_shapes(detect):
    # Construct an *observed* def-use neighborhood, not de-flattened paths.
    get_resultdata = next((i for i, (op, arg) in enumerate(detect)
                           if op == "callvirt" and arg.startswith("0x06001142")), None)
    near_local2 = get_resultdata is not None and any(
        op == "stloc.2" for op, _ in detect[get_resultdata + 1:get_resultdata + 17]
    )
    return {
        "detect_resultdata_near_local2_store": near_local2,
        "detect_result_constructor_from_volvo_and_local2": _has_motif(detect, [
            ("ldarg.0", None), ("ldarg.0", None),
            ("call", "0x060012E2"), ("ldloc.2", None),
            ("newobj", "0x060011BB"), ("call", "0x060012E9"),
        ]),
        "detect_ecus_constructor_from_detect_result": _has_motif(detect, [
            ("ldarg.0", None), ("ldarg.0", None),
            ("call", "0x060012E8"), ("newobj", "0x0600126D"),
            ("call", "0x060012DF"),
        ]),
        "detect_model_stores_command_datahash": _has_motif(detect, [
            ("ldarg.0", None), ("ldloc.1", None),
            ("callvirt", "0x0600113C"), ("stfld", "0x040003A9"),
        ]),
        "detect_has_result_units_enumeration": _has_motif(detect, [
            ("call", "0x060012E8"), ("callvirt", "0x06001B99"),
            ("callvirt", "0x0A00011A"),
        ]),
        "detect_has_both_boolean_return_sites":
            _has_motif(detect, [("ldc.i4.1", None), ("ret", None)])
            and _has_motif(detect, [("ldc.i4.0", None), ("ret", None)]),
    }


def _branch_destination(ops, offsets, i):
    """Resolve a printed relative CIL jump to an *existing* IL offset.

    This is one structural edge only; it does not de-flatten all switch paths
    or establish that the source basic block can ever be executed.
    """
    if i < 0 or i + 1 >= len(ops) or len(ops) != len(offsets):
        return None
    opcode, argument = ops[i]
    if opcode not in ("brfalse", "brfalse.s", "brtrue", "brtrue.s"):
        return None
    if not re.fullmatch(r"[+-]?\d+", argument):
        return None
    dest = offsets[i + 1] + int(argument)
    try:
        return offsets.index(dest)
    except ValueError:
        return None


def _get_vin_null_branch_to_volvo(ops, offsets):
    for i in range(2, len(ops) - 1):
        if not (
            ops[i] == ("brfalse.s", "108")
            and ops[i - 1][0] == "call"
            and ops[i - 1][1].startswith("0x060012F2")
        ):
            continue
        destination = _branch_destination(ops, offsets, i)
        if destination is not None and _has_motif(
            ops[destination:destination + 2],
            [("ldarg.0", None), ("call", "0x060012E2")]
        ):
            return True
    return False


def _get_config_null_guard(ops, offsets):
    for i, (opcode, arg) in enumerate(ops):
        if opcode != "brtrue.s" or i < 3:
            continue
        if not _has_motif(ops[i - 3:i + 1], [
            ("ldarg.0", None), ("call", "0x060012E8"),
            ("dup", None), ("brtrue.s", None)
        ]):
            continue
        if not _has_motif(ops[i + 1:i + 4], [
            ("pop", None), ("ldnull", None), ("ret", None)
        ]):
            continue
        dest = _branch_destination(ops, offsets, i)
        if dest is not None and _has_motif(ops[dest:dest + 2], [
            ("callvirt", "0x06001B7E"), ("ret", None)
        ]):
            return True
    return False


def _result_failure_branch(ops, offsets):
    # Observed: get_Result -> opaque predicate 0x06001359 -> direct false return.
    # The enum/constant/predicate meaning is intentionally NOT inferred.
    seq = [
        ("ldloc.1", None), ("callvirt", "0x0600113E"),
        ("ldc.i4", None), ("br.s", "0"),
        ("call", "0x2B"), ("call", "0x06001359"),
        ("brfalse", None),
    ]
    for start in range(len(ops) - len(seq) + 1):
        if not _has_motif(ops[start:start + len(seq)], seq):
            continue
        dest = _branch_destination(ops, offsets, start + len(seq) - 1)
        if dest is not None and _has_motif(ops[dest:dest + 2], [
            ("ldc.i4.0", None), ("ret", None)
        ]):
            return True
    return False


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
    by_key = {}
    for method in selected:
        token = method.get("method_token")
        module = method.get("module")
        if not isinstance(token, str) or not TOKEN.fullmatch(token):
            raise ValueError("invalid_inventory_token")
        if not isinstance(module, str) or not module:
            raise ValueError("invalid_inventory_module")
        key = (module, token)
        if key in tokens:
            raise ValueError("duplicate_inventory_token")
        tokens.add(key)
        by_key[key] = method
    blocks = parse_excerpts(excerpts)
    for key, body in blocks.items():
        if key not in tokens:
            raise ValueError("excerpt_method_not_in_inventory")
        if by_key[key].get("decoded_instructions") != body["declared"]:
            raise ValueError("inventory_excerpt_disagreement")

    detect = blocks.get(KNOWN["detect"], {}).get("ops", [])
    execute = blocks.get(KNOWN["execute"], {}).get("ops", [])
    predetect = blocks.get(KNOWN["pre_detect"], {}).get("ops", [])
    getvin_block = blocks.get(KNOWN["get_vin"], {})
    getvin = getvin_block.get("ops", [])
    config_block = blocks.get(KNOWN["get_config"], {})
    detect_block = blocks.get(KNOWN["detect"], {})
    # Fixed schema, no raw strings, source path, VIN, PID or private methods.
    return {
        "format": "recovered-il-evidence-audit-v3",
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
            "get_vin_missing_predetect_direct_volvo_fallback":
                _get_vin_null_branch_to_volvo(getvin, getvin_block.get("offsets", [])),
            "get_config_null_guard_direct_get_config":
                _get_config_null_guard(config_block.get("ops", []),
                                       config_block.get("offsets", [])),
            "detect_calls_create_command": _has_call(detect, "0x06001329"),
            "detect_calls_enqueue": _has_call(detect, "0x0600132C"),
            "detect_calls_wait": _has_call(detect, "0x0600115B"),
            "detect_assigns_ecus_model": _has_call(detect, "0x060012DF"),
            "detect_fires_done": _has_call(detect, "0x06001343"),
            "detect_result_predicate_direct_false_return":
                _result_failure_branch(detect, detect_block.get("offsets", [])),
            "execute_calls_parse_data": _has_call(execute, "0x06001160"),
            "execute_observed_status_numeric_comparisons": _status_values(execute),
            "execute_one_second_timer_shape": _one_shot_timer_shape(execute),
            **_model_shapes(detect),
        },
        "limitations": [
            "Method references do not prove execution order in flattened CFG",
            "Enum meaning and unknown wrapper effects not established",
            "No J2534 request/ECU acceptance claim from recovered IL alone",
            "Constructor/data-flow motifs do not establish runtime reachability",
            "Direct branch targets do not prove that source blocks are reachable",
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
