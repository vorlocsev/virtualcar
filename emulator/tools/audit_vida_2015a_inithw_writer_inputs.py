#!/usr/bin/env python3
"""Owner-only VIDA 2015A: one-argument newobj and zero-argument callvirt inputs.

Read only the 3 existing SHA-256 pinned original VIDA DLLs as bytes.
For each stfld into a GetInitHwSettings-adjacent local FieldDef, inspect the
exact preceding newobj or callvirt MemberRef, its declared arity/type and
the immediate instruction BEFORE that producer. Count direct branch targets
to producer and precursor, plus writer method MoreSects presence.

This is a *local CIL textual adjacency census*, NOT verified operand-stack
data flow, producer-to-stfld proof, aliasing, execution, field values,
profileIdentifiers list, generic InitHw inheritance, D2 baud or ReadVin.
Original offsets, tokens, type/method/field names, IL bytes, paths and values
remain private. JSON contains ONLY fixed category counts and false flags.
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
from audit_vida_2015a_inithw_callsite_adjacent import _instructions, _fixed_adjacent_class
from audit_vida_2015a_inithw_assembly_identity import _table_layout
from audit_vida_2015a_inithw_field_writes import _simple_field_class
from audit_vida_2015a_inithw_writer_memberrefs import _memberref_relation
from audit_vida_2015a_inithw_stack_boundaries import _arity, _moresects, _branch_targets

MAX_METHODS = 100000
MAX_READERS = 100
MAX_WRITERS = 10000
PREDECESSORS = ("newobj", "callvirt", "other_or_unclassified")
SOURCE_FAMILIES = (
    "none", "load_arg_or_address", "load_local_or_address",
    "load_field_or_address", "nested_call_or_calli_unresolved_return",
    "new_object_or_array", "load_null", "load_string", "load_numeric",
    "duplicate_stack_item", "type_cast_or_transform",
    "array_element_or_length", "load_method_or_type_handle",
    "prefix_not_value_producer", "nop", "other_or_unresolved",
)
TYPE_RELATIONS = ("equal", "different", "unclassified")
ARITIES = ("zero", "one", "two_or_more", "unclassified")


def _field_operand(code: bytes, instruction: tuple, kind: int) -> int:
    start, opcode, _, end = instruction
    if opcode != kind or end - start != 5:
        raise MetadataError("original adjacent field operand size invalid")
    tok = _u(code, start + 1, 4)
    if tok >> 24 != 0x04 or not (tok & 0xFFFFFF):
        raise MetadataError("target field operand must be local FieldDef")
    return tok


def _producer_details(code: bytes, ins: list[tuple], i: int, layout: dict,
                      field_token: int) -> tuple[str, str, str]:
    """Return only fixed classes, never original method/type identifiers."""
    if i == 0:
        return "other_or_unclassified", "unclassified", "unclassified"
    pstart, op, _, pend = ins[i - 1]
    if op not in (0x73, 0x6F):
        return "other_or_unclassified", "unclassified", "unclassified"
    if pend - pstart != 5:
        raise MetadataError("writer predecessor method token boundary invalid")
    tok = _u(code, pstart + 1, 4)
    kind = "newobj" if op == 0x73 else "callvirt"
    arity = _arity(layout, tok)
    relation = _memberref_relation(
        layout, tok, _simple_field_class(layout, field_token), kind,
    )
    if relation in (kind + "_owner_exact_field_type",
                    kind + "_return_exact_field_type"):
        match = "equal"
    elif relation in (kind + "_owner_different_field_type",
                      kind + "_return_different_field_type"):
        match = "different"
    else:
        match = "unclassified"
    return kind, arity, match


def inspect_module(blob: bytes, *, require_interface_memberref: bool) -> dict:
    meta = _metadata_tables(blob)
    targets = {
        tok for tok, fam in meta["target_reference_parent_type_families"].items()
        if fam == "icarcom_repository"
    }
    if require_interface_memberref:
        if len(targets) != 1:
            raise MetadataError("original interface method MemberRef is not unique")
        if any(meta["target_reference_signature_contracts"].get(tok) is None or
               meta["target_reference_signature_contracts"][tok]["parameters"] != 1 or
               not meta["target_reference_signature_contracts"][tok]["has_this"]
               for tok in targets):
            raise MetadataError("original target interface signature contract mismatch")
    elif targets:
        raise MetadataError("unexpected target MemberRef in original repository DLL")
    sections, layout = _sections(blob), _table_layout(blob)
    if len(meta["methods"]) > MAX_METHODS:
        raise MetadataError("too many original CIL MethodDef rows")
    bodies, fields = [], set()
    reader_calls = 0
    for method in meta["methods"].values():
        if not method["rva"]:
            continue
        raw = _body(blob, method["rva"], sections)
        ins = _instructions(raw)
        bodies.append((raw, ins, _moresects(blob, method["rva"], sections)))
        for i, (_, op, tok, _) in enumerate(ins):
            if op not in (0x28, 0x6F) or tok not in targets:
                continue
            reader_calls += 1
            if reader_calls > MAX_READERS or i == 0:
                raise MetadataError("original target reader count or predecessor invalid")
            fields.add(_field_operand(raw, ins[i - 1], 0x7B))

    counts = {
        "cil_method_bodies_examined": len(bodies),
        "target_getinithw_call_sites": reader_calls,
        "distinct_target_fielddefs": len(fields),
        "target_field_stfld_sites": 0,
        "writer_predecessor_kind_counts": {k: 0 for k in PREDECESSORS},
        "writer_memberref_arity_by_kind": {
            k: {a: 0 for a in ARITIES} for k in PREDECESSORS
        },
        "writer_type_relation_by_kind": {
            k: {r: 0 for r in TYPE_RELATIONS} for k in PREDECESSORS
        },
        "immediately_before_writer_producer_opcode_family": {
            k: {v: 0 for v in SOURCE_FAMILIES} for k in PREDECESSORS
        },
        "producer_has_direct_branch_entry": 0,
        "producer_has_no_direct_branch_entry": 0,
        "producer_input_has_direct_branch_entry": 0,
        "producer_input_has_no_direct_branch_entry": 0,
        "writer_method_has_more_sections": 0,
        "writer_method_has_no_more_sections": 0,
        "writer_source_arity_as_expected": 0,
        "writer_source_arity_not_as_expected_or_unclassified": 0,
    }
    for raw, ins, more in bodies:
        branches = _branch_targets(raw, ins)
        for i, (_, op, _, _) in enumerate(ins):
            if op != 0x7D:
                continue
            start, _, _, end = ins[i]
            if end - start != 5:
                raise MetadataError("invalid original stfld width")
            field = _u(raw, start + 1, 4)
            if field not in fields:
                continue
            counts["target_field_stfld_sites"] += 1
            if counts["target_field_stfld_sites"] > MAX_WRITERS:
                raise MetadataError("original target writer bound exceeded")
            kind, arity, match = _producer_details(raw, ins, i, layout, field)
            counts["writer_predecessor_kind_counts"][kind] += 1
            counts["writer_memberref_arity_by_kind"][kind][arity] += 1
            counts["writer_type_relation_by_kind"][kind][match] += 1
            precursor = ins[i - 2] if i >= 2 else None
            source_class = _fixed_adjacent_class(precursor[1] if precursor else None)
            if source_class not in SOURCE_FAMILIES:
                raise MetadataError("unsupported predecessor opcode output class")
            counts["immediately_before_writer_producer_opcode_family"][kind][
                source_class
            ] += 1
            counts[
                "producer_has_direct_branch_entry"
                if i and ins[i - 1][0] in branches else
                "producer_has_no_direct_branch_entry"
            ] += 1
            counts[
                "producer_input_has_direct_branch_entry"
                if precursor and precursor[0] in branches else
                "producer_input_has_no_direct_branch_entry"
            ] += 1
            counts[
                "writer_method_has_more_sections" if more else
                "writer_method_has_no_more_sections"
            ] += 1
            correct = (kind == "newobj" and arity == "one" or
                       kind == "callvirt" and arity == "zero")
            counts[
                "writer_source_arity_as_expected" if correct else
                "writer_source_arity_not_as_expected_or_unclassified"
            ] += 1
    total = counts["target_field_stfld_sites"]
    for key in PREDECESSORS:
        if any(sum(counts[name][key].values()) != counts["writer_predecessor_kind_counts"][key]
               for name in ("writer_memberref_arity_by_kind",
                            "writer_type_relation_by_kind",
                            "immediately_before_writer_producer_opcode_family")):
            raise MetadataError("writer precursor count inconsistent")
    for one, two in (
        ("producer_has_direct_branch_entry", "producer_has_no_direct_branch_entry"),
        ("producer_input_has_direct_branch_entry", "producer_input_has_no_direct_branch_entry"),
        ("writer_method_has_more_sections", "writer_method_has_no_more_sections"),
        ("writer_source_arity_as_expected",
         "writer_source_arity_not_as_expected_or_unclassified"),
    ):
        if counts[one] + counts[two] != total:
            raise MetadataError("writer input classification count inconsistent")
    return counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise MetadataError("invalid original VIDA directory")
    files, seen = {}, 0
    def walk_error(_):
        raise MetadataError("source walk failure")
    for root, dirs, names in os.walk(folder, followlinks=False, onerror=walk_error):
        dirs[:] = [x for x in dirs if not (Path(root) / x).is_symlink()]
        for name in names:
            seen += 1
            if seen > MAX_FILES_WALK:
                raise MetadataError("original source discovery bound exceeded")
            key = name.casefold()
            if key in EXPECTED:
                path = Path(root) / name
                if key in files or path.is_symlink() or not path.is_file():
                    raise MetadataError("ambiguous original source file")
                files[key] = path
    if set(files) != set(EXPECTED):
        raise MetadataError("exact original three SHA pinned DLLs absent")
    results = []
    for key, (name, sha) in sorted(EXPECTED.items()):
        file = files[key]
        size = file.stat().st_size
        if not 128 <= size <= MAX_FILE:
            raise MetadataError("source DLL exceeds bounded limits")
        with file.open("rb") as stream:
            raw = stream.read(MAX_FILE + 1)
        if len(raw) != size or file.stat().st_size != size or hashlib.sha256(raw).hexdigest() != sha:
            raise MetadataError("SHA256 mismatch on original source")
        results.append({
            "module_basename": name,
            "counts": inspect_module(
                raw, require_interface_memberref=(key != "bizservices.carcom.db.dll"),
            ),
        })
    return {
        "schema_version": "virtualcar-vida-original-2015a-getinithw-writer-input-adjacency-v1",
        "status": "owner_original_readonly_writer_input_opcode_categories_only",
        "results": results,
        "original_assemblies_loaded_or_executed": False,
        "source_writes_performed": False,
        "original_IL_tokens_types_names_values_paths_or_method_signatures_exported": False,
        "adjacent_writer_input_proves_operand_stack_value_source": False,
        "original_profile_identifiers_argument_proven": False,
        "control_flow_stack_or_receiver_aliases_traced": False,
        "original_vida_2015a_generic_profile_inheritance_verified": False,
        "d2_baudrate_verified": False,
        "original_vida_readvin_accepted": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Original VIDA SHA pinned writer precursor source families")
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(audit(args.folder), sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
