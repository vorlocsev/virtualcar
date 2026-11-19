#!/usr/bin/env python3
"""Owner-only VIDA 2015A local nested MethodDef return and call input census.

Only the three established SHA256-pinned original DLLs, read as bytes.
For a target stfld whose immediate predecessor is newobj and whose
preceding opcode is callvirt LOCAL MethodDef, categorize the instruction
before callvirt and static return sites within that MethodDef body.
No original IL offsets, method/field/type names, metadata tokens, strings,
parameter values, file paths, runtime execution or profile IDs exported.
This is not CLR operand-stack/CFG/alias proof or VIDA ReadVin acceptance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from audit_vida_2015a_inithw_metadata import (
    EXPECTED, MAX_FILE, MAX_FILES_WALK, MetadataError, _u,
)
from audit_vida_2015a_inithw_il_calls import _metadata_tables, _sections, _body
from audit_vida_2015a_inithw_callsite_adjacent import (
    _instructions, _fixed_adjacent_class,
)
from audit_vida_2015a_inithw_assembly_identity import _table_layout
from audit_vida_2015a_inithw_precursor_types import _arg_slot, _signature, _field_token
from audit_vida_2015a_inithw_stack_boundaries import _branch_targets, _moresects

MAX_METHODS = 100000
MAX_TARGET_READERS = 100
MAX_NESTED_SITES = 100
MAX_RET_SITES = 4096
SLOTS = ("slot0", "slot1", "slot2plus", "address_slot0", "address_slot1",
         "address_slot2plus", "other_or_unclassified")
ARG_ROLES = ("instance_this", "instance_first_explicit",
             "instance_later_explicit", "static_first_explicit",
             "static_second_or_later_explicit", "out_of_signature_or_unclassified")
RETURN_FAMILIES = (
    "none", "load_arg_or_address", "load_local_or_address",
    "load_field_or_address", "nested_call_or_calli_unresolved_return",
    "new_object_or_array", "load_null", "load_string", "load_numeric",
    "duplicate_stack_item", "type_cast_or_transform",
    "array_element_or_length", "load_method_or_type_handle",
    "prefix_not_value_producer", "nop", "other_or_unresolved",
)
METHOD_SIGNATURES = ("instance_zero_explicit_class_return",
                     "other_or_unclassified")


def _caller_arg_role(layout: dict, caller_methoddef: int, slot: str) -> str:
    sig = _signature(layout, caller_methoddef)
    if sig is None or slot.startswith("address_"):
        return "out_of_signature_or_unclassified"
    _, args, has_this = sig
    if slot == "slot0":
        if has_this:
            return "instance_this"
        return "static_first_explicit" if args else "out_of_signature_or_unclassified"
    if slot == "slot1":
        if has_this:
            return "instance_first_explicit" if args else "out_of_signature_or_unclassified"
        return "static_second_or_later_explicit" if len(args) > 1 else "out_of_signature_or_unclassified"
    if slot == "slot2plus":
        if has_this:
            return "instance_later_explicit" if len(args) > 1 else "out_of_signature_or_unclassified"
        return "static_second_or_later_explicit" if len(args) > 2 else "out_of_signature_or_unclassified"
    return "out_of_signature_or_unclassified"


def _local_return_census(code: bytes) -> tuple[int, dict, int]:
    """Static predecessor-to-ret classes, and direct branches to ret."""
    ins = _instructions(code)
    branch_targets = _branch_targets(code, ins)
    histogram = {name: 0 for name in RETURN_FAMILIES}
    branch_to_ret = 0
    rets = 0
    for i, (start, op, _, _) in enumerate(ins):
        if op != 0x2A:
            continue
        rets += 1
        if rets > MAX_RET_SITES:
            raise MetadataError("original local MethodDef return limit exceeded")
        family = _fixed_adjacent_class(ins[i - 1][1] if i else None)
        if family not in histogram:
            raise MetadataError("unknown original return predecessor class")
        histogram[family] += 1
        branch_to_ret += int(start in branch_targets)
    return rets, histogram, branch_to_ret


def inspect_module(blob: bytes, *, require_interface_memberref: bool) -> dict:
    meta = _metadata_tables(blob)
    targets = {tok for tok, kind in meta["target_reference_parent_type_families"].items()
               if kind == "icarcom_repository"}
    if require_interface_memberref:
        if len(targets) != 1 or any(
            meta["target_reference_signature_contracts"].get(tok) is None or
            meta["target_reference_signature_contracts"][tok]["parameters"] != 1 or
            not meta["target_reference_signature_contracts"][tok]["has_this"]
            for tok in targets
        ):
            raise MetadataError("original GetInitHwSettings MemberRef contract mismatch")
    elif targets:
        raise MetadataError("unexpected repository target MemberRef")
    methods = meta["methods"]
    if len(methods) > MAX_METHODS:
        raise MetadataError("original MethodDef table exceeds bound")
    sections, layout = _sections(blob), _table_layout(blob)
    bodies, fields = [], set()
    reader_count = 0
    for rid, method in methods.items():
        if not method["rva"]:
            continue
        code = _body(blob, method["rva"], sections)
        ins = _instructions(code)
        bodies.append((rid, code, ins))
        for i, (start, op, token, end) in enumerate(ins):
            if op not in (0x28, 0x6F) or token not in targets:
                continue
            reader_count += 1
            if reader_count > MAX_TARGET_READERS or not i:
                raise MetadataError("invalid target GetInitHwSettings callsite")
            if ins[i - 1][3] != start:
                raise MetadataError("target ldfld and callvirt not adjacent")
            fields.add(_field_token(code, ins[i - 1], 0x7B))

    counts = {
        "cil_method_bodies_examined": len(bodies),
        "target_getinithw_calls": reader_count,
        "distinct_target_fielddefs": len(fields),
        "nested_local_callvirt_before_newobj_sites": 0,
        "distinct_nested_local_methoddefs": 0,
        "nested_call_input_slot_counts": {k: 0 for k in SLOTS},
        "nested_call_caller_arg_role_counts": {k: 0 for k in ARG_ROLES},
        "nested_method_signature_counts": {k: 0 for k in METHOD_SIGNATURES},
        "nested_method_with_il_body": 0,
        "nested_method_without_il_body": 0,
        "nested_method_moresects": 0,
        "nested_method_no_moresects": 0,
        "nested_method_return_sites": 0,
        "nested_method_return_preceding_opcode_families": {
            k: 0 for k in RETURN_FAMILIES
        },
        "nested_method_return_direct_branch_entry": 0,
    }
    found_local = set()
    for rid, code, ins in bodies:
        for i, (start, op, _, end) in enumerate(ins):
            if op != 0x7D:
                continue
            if end - start != 5 or _u(code, start + 1, 4) not in fields:
                continue
            if i < 3:
                continue
            newobj, nested, precursor = ins[i - 1], ins[i - 2], ins[i - 3]
            if newobj[1] != 0x73 or nested[1] != 0x6F:
                continue
            if newobj[3] != start or nested[3] != newobj[0] or precursor[3] != nested[0]:
                raise MetadataError("misaligned nested call/newobj/stfld chain")
            if nested[3] - nested[0] != 5:
                raise MetadataError("invalid nested MethodDef operand width")
            method_token = _u(code, nested[0] + 1, 4)
            if method_token >> 24 != 6 or not (method_token & 0xFFFFFF):
                continue
            counts["nested_local_callvirt_before_newobj_sites"] += 1
            if counts["nested_local_callvirt_before_newobj_sites"] > MAX_NESTED_SITES:
                raise MetadataError("too many nested original callsites")
            slot = _arg_slot(code, precursor)
            counts["nested_call_input_slot_counts"][slot] += 1
            counts["nested_call_caller_arg_role_counts"][
                _caller_arg_role(layout, 0x06000000 | rid, slot)
            ] += 1
            method_rid = method_token & 0xFFFFFF
            sig = _signature(layout, method_token)
            label = (
                "instance_zero_explicit_class_return" if (
                    sig is not None and sig[2] and not sig[1] and
                    sig[0] is not None and sig[0][0] == "class"
                ) else "other_or_unclassified"
            )
            if method_rid in found_local:
                continue
            found_local.add(method_rid)
            counts["nested_method_signature_counts"][label] += 1
            method = methods.get(method_rid)
            if method is None:
                raise MetadataError("nested MethodDef row missing from original module")
            if not method["rva"]:
                counts["nested_method_without_il_body"] += 1
                continue
            counts["nested_method_with_il_body"] += 1
            counts["nested_method_moresects" if _moresects(blob, method["rva"], sections)
                   else "nested_method_no_moresects"] += 1
            body = _body(blob, method["rva"], sections)
            rets, histogram, targeted = _local_return_census(body)
            counts["nested_method_return_sites"] += rets
            counts["nested_method_return_direct_branch_entry"] += targeted
            if counts["nested_method_return_sites"] > MAX_RET_SITES:
                raise MetadataError("unbounded total return sites")
            for key, value in histogram.items():
                counts["nested_method_return_preceding_opcode_families"][key] += value
    counts["distinct_nested_local_methoddefs"] = len(found_local)
    total = counts["nested_local_callvirt_before_newobj_sites"]
    unique = counts["distinct_nested_local_methoddefs"]
    if (sum(counts["nested_call_input_slot_counts"].values()) != total or
        sum(counts["nested_call_caller_arg_role_counts"].values()) != total or
        sum(counts["nested_method_signature_counts"].values()) != unique or
        counts["nested_method_with_il_body"] + counts["nested_method_without_il_body"] != unique or
        counts["nested_method_moresects"] + counts["nested_method_no_moresects"] !=
            counts["nested_method_with_il_body"] or
        sum(counts["nested_method_return_preceding_opcode_families"].values()) !=
            counts["nested_method_return_sites"] or
        counts["nested_method_return_direct_branch_entry"] >
            counts["nested_method_return_sites"]):
        raise MetadataError("unreconciled nested MethodDef source counters")
    return counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise MetadataError("invalid original VIDA source directory")
    selected, seen = {}, 0
    def failure(_):
        raise MetadataError("original source walk failed")
    for root, dirs, names in os.walk(folder, followlinks=False, onerror=failure):
        dirs[:] = [d for d in dirs if not (Path(root) / d).is_symlink()]
        for name in names:
            seen += 1
            if seen > MAX_FILES_WALK:
                raise MetadataError("original source file scan limit exceeded")
            key = name.casefold()
            if key in EXPECTED:
                path = Path(root) / name
                if key in selected or path.is_symlink() or not path.is_file():
                    raise MetadataError("ambiguous source DLL")
                selected[key] = path
    if set(selected) != set(EXPECTED):
        raise MetadataError("three pinned original DLLs missing")
    results = []
    for key, (name, expected) in sorted(EXPECTED.items()):
        path = selected[key]
        length = path.stat().st_size
        if not 128 <= length <= MAX_FILE:
            raise MetadataError("original binary size exceeds source bounds")
        with path.open("rb") as stream:
            data = stream.read(MAX_FILE + 1)
        if len(data) != length or path.stat().st_size != length or hashlib.sha256(data).hexdigest() != expected:
            raise MetadataError("original pinned SHA256 mismatch")
        results.append({
            "module_basename": name,
            "counts": inspect_module(
                data, require_interface_memberref=(key != "bizservices.carcom.db.dll"),
            ),
        })
    return {
        "schema_version": "virtualcar-vida-original-2015a-getinithw-nested-method-returns-v1",
        "status": "owner_original_readonly_nested_method_return_opcode_census_only",
        "results": results,
        "original_assemblies_loaded_or_executed": False,
        "source_writes_performed": False,
        "original_IL_names_tokens_signatures_strings_or_paths_emitted": False,
        "nested_method_return_adjacency_proves_return_value_source": False,
        "nested_call_input_slot_proves_runtime_receiver": False,
        "return_sites_prove_reachable_runtime_path": False,
        "original_profile_identifiers_proven": False,
        "original_vida_2015a_generic_profile_inheritance_verified": False,
        "d2_baudrate_verified": False,
        "original_vida_readvin_accepted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Owner-only original VIDA nested MethodDef return/predecessor census")
    p.add_argument("--folder", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        print(json.dumps(audit(args.folder), indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
