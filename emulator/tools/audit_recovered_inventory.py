#!/usr/bin/env python3
"""Sanitize a locally held VDASH recovered-method inventory without raw IL.

This is a static inventory cross-check, NOT a decompiler, a runtime test,
or proof of VDASH/CEM success. Original binaries never enter the repository.
"""
import argparse
import json
from pathlib import Path
import re
import sys

FORMAT = "virtualcar-vdash-recovered-inventory-audit-v1"
INPUT_FORMAT = "vdash-static-recovered-il-method-inventory-v1"
MODULE = "Frontend.Client.Core.dll"
MAX_INPUT = 32 * 1024 * 1024
SHA = re.compile(r"[0-9a-fA-F]{64}\Z")
TOKEN = re.compile(r"0x[0-9a-fA-F]{8}\Z")
FOCUS = {
    "detect": "0x0600132b",
    "execute": "0x0600115d",
    "parse_data": "0x06001160",
}
# These are only two-to-four opcode prefixes from the previously recovered
# *private inventory*. Never treat them as a deobfuscated logical predicate.
ENTRY_PREFIX = {
    "detect": ("call", "dup", "ldc.i4.0", "call"),
    "execute": ("ldarg.0", "ldfld", "ldarg.0", "ldftn"),
    "parse_data": ("ldarg.1", "brtrue.s"),
}
_OPCODE = re.compile(r"[a-z][a-z0-9_.]{0,40}\Z")
KNOWN = {
    "detect": {
        "methodspec_generic_call": "0x2b000002",
        "opaque_predicate_call": "0x06001359",
        "get_result_data_call": "0x06001142",
        "detect_result_constructor": "0x060011bb",
        "ecus_constructor": "0x0600126d",
    },
    "execute": {"parse_data_call": "0x06001160"},
    "parse_data": {
        "get_result_data_call": "0x06001142",
        "raise_event_call": "0x06001161",
        "set_data_hash_call": "0x0600113d",
        "parse_data_callback_88": "0x06001195",
        "parse_data_callback_1": "0x06001198",
    },
}


def _digest(value):
    return isinstance(value, str) and bool(SHA.fullmatch(value))


def _object(value, name):
    if not isinstance(value, dict):
        raise ValueError("invalid_" + name)
    return value


def _positive_int(value):
    return type(value) is int and 0 <= value <= 10000000


def _entry_shape(row, name):
    """Allowlisted prefix classification, never raw opcodes or inferred logic."""
    ops = row.get("first_operations")
    if ops is None:
        return "not_reported"
    if (not isinstance(ops, list) or len(ops) > 32
            or not all(isinstance(op, str) and _OPCODE.fullmatch(op)
                       for op in ops)):
        raise ValueError("invalid_first_operations")
    prefix = ENTRY_PREFIX[name]
    return ("expected_static_prefix_observed"
            if tuple(ops[:len(prefix)]) == prefix
            else "different_or_incomplete_prefix")


def _stub_status(row):
    value = row.get("return_only_stub")
    if value is None:
        return "not_reported"
    if type(value) is not bool:
        raise ValueError("invalid_stub_flag")
    return "reported_stub" if value else "reported_non_stub"


def _build_binding(module, rea):
    if rea is None:
        return "not_checked"
    d = _object(_object(rea, "rea").get("normalized_result"), "rea_result")
    artifact = _object(d.get("artifact"), "rea_artifact")
    ident = _object(d.get("identity_scope"), "rea_identity")
    module_info = _object(d.get("module"), "rea_module")
    actual = artifact.get("sha256")
    module_name = module_info.get("name")
    if (not _digest(actual) or not isinstance(module_name, str)
            or module_name.casefold() != MODULE.casefold()):
        raise ValueError("invalid_rea_assembly")
    if (ident.get("token_identity") != "build-local"
            or ident.get("requires_artifact_sha256") != actual):
        raise ValueError("invalid_rea_identity_scope")
    mvid = module_info.get("mvid")
    required = ident.get("requires_mvid")
    if required is not None and (not mvid or str(mvid).casefold() != str(required).casefold()):
        raise ValueError("invalid_rea_mvid")
    if actual.casefold() == module["recovered_sha256"].casefold():
        return "matched_recovered_material"
    if actual.casefold() == module["source_sha256"].casefold():
        return "matched_original_material"
    raise ValueError("different_build")


def audit(data, rea=None):
    root = _object(data, "inventory")
    if root.get("format") != INPUT_FORMAT:
        raise ValueError("unsupported_inventory_format")
    if not _digest(root.get("source_zip_sha256")):
        raise ValueError("invalid_inventory_zip_digest")
    modules = _object(root.get("recovered_modules"), "modules")
    module = _object(modules.get(MODULE), "module")
    if not all(_digest(module.get(k)) for k in ("source_sha256", "recovered_sha256")):
        raise ValueError("invalid_module_digests")
    if (module.get("metadata_row_alignment_normalized") is not True
            or module.get("duplicate_heap_names_normalized") is not True):
        raise ValueError("unattested_recovered_alignment")
    binding = _build_binding(module, rea)
    rows = root.get("selected_methods")
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError("invalid_method_inventory")
    targets = {}
    for entry in rows:
        row = _object(entry, "method_row")
        if row.get("module") != MODULE:
            continue
        raw = row.get("method_token")
        if not isinstance(raw, str) or not TOKEN.fullmatch(raw):
            raise ValueError("invalid_method_token")
        key = raw.casefold()
        if key not in FOCUS.values():
            continue
        if key in targets:
            raise ValueError("duplicate_focus_method")
        il_bytes = row.get("il_bytes")
        decoded = row.get("decoded_instructions")
        issues = row.get("decoder_issues")
        index = row.get("method_index")
        if (not all(_positive_int(v) for v in (il_bytes, decoded, issues, index))
                or index != (int(key, 16) & 0xFFFFFF)
                or decoded > il_bytes):
            raise ValueError("invalid_recovered_method_counts")
        calls = row.get("calls")
        if not isinstance(calls, list) or len(calls) > 10000:
            raise ValueError("invalid_call_inventory")
        by_token = {}
        for call in calls:
            c = _object(call, "call")
            token, count = c.get("token"), c.get("count")
            if (not isinstance(token, str) or not TOKEN.fullmatch(token)
                    or not _positive_int(count) or count == 0):
                raise ValueError("invalid_call_entry")
            tid = token.casefold()
            if tid in by_token:
                raise ValueError("duplicate_call_token")
            by_token[tid] = count
        name = next(name for name, token in FOCUS.items() if token == key)
        targets[key] = {
            "il_bytes": il_bytes,
            "decoded_instructions": decoded,
            "decoder_issues": issues,
            "calls": by_token,
            "entry_opcode_shape": _entry_shape(row, name),
            "stub_status": _stub_status(row),
        }
    method_summary = {}
    for name, token in FOCUS.items():
        row = targets.get(token)
        method_summary[name] = (
            {"inventory_record": "not_reported", "call_counts": {}}
            if row is None else {
                "inventory_record": "reported",
                "il_bytes": row["il_bytes"],
                "decoded_instructions": row["decoded_instructions"],
                "decoder_issues": row["decoder_issues"],
                "entry_opcode_shape": row["entry_opcode_shape"],
                "stub_status": row["stub_status"],
                "call_counts": {
                    label: row["calls"].get(target, 0)
                    for label, target in KNOWN[name].items()
                },
            }
        )
    return {
        "format": FORMAT,
        "source": "private_recovered_inventory_static_summary",
        "inventory_module_reported": True,
        "reported_normalized_method_alignment": True,
        "rea_material_binding": binding,
        "exact_original_il_body_available_here": False,
        "original_binary_verified_by_runtime": False,
        "client_ecu_acceptance_verified": False,
        "contains_binary_digests_or_private_symbols": False,
        "methods": method_summary,
        "limitations": [
            "Counts and opcode prefixes are inventory claims, not a fresh complete REA IL decode",
            "An ldarg.1 then brtrue.s prefix is a conditional branch shape, not a verified semantic guard",
            "Method names, control-flow reachability and successful ECU parsing remain unproven",
            "A source hash match alone does not attest recovered/normalized MethodDef token alignment",
            "A recovered-file digest match ties material, not VDASH runtime or server outcomes",
            "Missing selected methods are not proof that those methods are absent from the DLL",
        ],
    }


def _read_json(path):
    if path.stat().st_size > MAX_INPUT:
        raise ValueError("input_limit")
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path, help="Private recovered inventory JSON")
    parser.add_argument("--rea-members", type=Path,
                        help="Optional private complete REA member JSON (build-hash match)")
    parser.add_argument("--output", required=True, type=Path,
                        help="New sanitized report JSON (never overwrite)")
    args = parser.parse_args(argv)
    try:
        if (args.inventory.resolve() == args.output.resolve()
                or (args.rea_members is not None and
                    args.rea_members.resolve() == args.output.resolve())):
            raise ValueError("same_file")
        inventory = _read_json(args.inventory)
        rea = _read_json(args.rea_members) if args.rea_members else None
        summary = audit(inventory, rea)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(summary, stream, indent=2)
            stream.write("\n")
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        print("VDASH inventory audit failed (private source details suppressed)", file=sys.stderr)
        return 2
    print("PASS: sanitized recovered inventory; VDASH ECU acceptance unverified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
