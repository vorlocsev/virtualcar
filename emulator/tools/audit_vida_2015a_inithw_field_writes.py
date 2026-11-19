#!/usr/bin/env python3
"""Original VIDA 2015A: immediate GetInitHwSettings FieldDef and local writers.

Owner-only read-only source check against exactly three SHA256-pinned DLLs.
For each original ICarComRepository.GetInitHwSettings call, compare a simple
CLASS TypeDefOrRef coded token between the preceding ldfld FieldSig and the
target's one method parameter **within the SAME metadata module**. Then
count all stfld/stsfld to those exact local FieldDef tokens in that module.

Only aggregate counts are emitted. No field names, type names, token row
numbers, IL bytes, argument values or profile identifiers are published.
Stored CLR TypeDefOrRef token equality is stronger than token-neutral shape
but it is NOT stack provenance, field-value provenance or runtime binding.
Search for writes is limited to IL in those three pinned DLLs; reflection,
P/Invoke, other assemblies and object initialization cannot be excluded.
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
from audit_vida_2015a_inithw_signature_shapes import _SigReader, UnsupportedSignature

MAX_METHODS = 100000
MAX_SITES_PER_MODULE = 100
MAX_MATCHED_WRITES_PER_MODULE = 10000

WRITER_METHOD_FAMILIES = (
    "instance_constructor", "type_initializer", "other_named_method",
)
WRITER_PREDECESSOR_OPCODES = (
    "newobj", "newarr", "call", "callvirt", "calli", "other_or_none",
)
WRITER_PREDECESSOR_TOKEN_KINDS = (
    "methoddef", "memberref", "methodspec", "typedef", "typeref",
    "typespec", "standalonesig", "not_applicable",
)
_OPERAND_KIND = {
    0x06: "methoddef", 0x0A: "memberref", 0x2B: "methodspec",
    0x02: "typedef", 0x01: "typeref", 0x1B: "typespec",
    0x11: "standalonesig",
}
_PREDECESSOR_CLASS = {
    0x73: ("newobj", (0x06, 0x0A, 0x2B)),
    0x8D: ("newarr", (0x02, 0x01, 0x1B)),
    0x28: ("call", (0x06, 0x0A, 0x2B)),
    0x6F: ("callvirt", (0x06, 0x0A, 0x2B)),
    0x29: ("calli", (0x11,)),
}


def _writer_predecessor_operand_category(
    code: bytes, instructions: list[tuple], index: int,
) -> tuple[str, str]:
    """Return fixed opcode+token-kind categories, never original token values."""
    if not index:
        return "other_or_none", "not_applicable"
    start, opcode, _, end = instructions[index - 1]
    if opcode not in _PREDECESSOR_CLASS:
        return "other_or_none", "not_applicable"
    name, allowed = _PREDECESSOR_CLASS[opcode]
    if end - start != 5 or start + 5 > len(code):
        raise MetadataError("invalid CIL writer predecessor instruction width")
    token = _u(code, start + 1, 4)
    if (token & 0xFFFFFF) == 0 or token >> 24 not in allowed:
        raise MetadataError("invalid CIL writer predecessor metadata token kind")
    return name, _OPERAND_KIND[token >> 24]


def _coded_type(reader: _SigReader) -> int | None:
    """Return local TypeDefOrRef coded index, never for output."""
    kind = reader.byte()
    if kind != 0x12:  # ECMA ELEMENT_TYPE_CLASS only
        return None
    encoded = reader.uint()
    if (encoded >> 2) == 0 or (encoded & 3) not in (0, 1, 2):
        raise MetadataError("invalid local TypeDefOrRef coded reference")
    return encoded


def _simple_field_class(layout: dict, fielddef_token: int) -> int | None:
    if fielddef_token >> 24 != 0x04 or not (fielddef_token & 0xFFFFFF):
        raise MetadataError("expected original local FieldDef token")
    index = fielddef_token & 0xFFFFFF
    p = layout["row"](4, index)
    blob_index = layout["u"](p + 2 + layout["strsize"], layout["blobsize"])
    raw = layout["blob"](blob_index)
    reader = _SigReader(raw)
    if reader.byte() != 0x06:
        raise MetadataError("original field signature is not FieldSig")
    value = _coded_type(reader)
    return value if value is not None and reader.pos == len(raw) else None


def _simple_parameter_class(raw: bytes | None) -> int | None:
    if raw is None:
        return None
    reader = _SigReader(raw)
    flags = reader.byte()
    if flags & 0x80 or (flags & 0x0F) not in (0, 5):
        raise MetadataError("invalid original CLR target method convention")
    try:
        if flags & 0x10:  # generic method arity
            reader.uint()
        argc = reader.uint()
        if argc != 1:
            raise MetadataError("original GetInitHwSettings parameter count not one")
        reader.typ()  # validate and consume return signature
        encoded = _coded_type(reader)
        return encoded if encoded is not None and reader.pos == len(raw) else None
    except UnsupportedSignature:
        return None


def inspect_module(blob: bytes, *, require_interface_memberref: bool) -> dict:
    meta = _metadata_tables(blob)
    targets = {
        token: meta["target_reference_signature_bytes_private"].get(token)
        for token, family in meta["target_reference_parent_type_families"].items()
        if family == "icarcom_repository"
    }
    if require_interface_memberref:
        if len(targets) != 1:
            raise MetadataError("expected exactly one ICarComRepository method MemberRef")
        for token in targets:
            contract = meta["target_reference_signature_contracts"].get(token)
            if contract is None or contract["parameters"] != 1 or not contract["has_this"]:
                raise MetadataError("original target signature header did not match")
    elif targets:
        raise MetadataError("unexpected ICarComRepository target MemberRef in repository DLL")
    parameter_types = {token: _simple_parameter_class(raw) for token, raw in targets.items()}
    layout = _table_layout(blob)
    sections = _sections(blob)
    methods = meta["methods"]
    if len(methods) > MAX_METHODS:
        raise MetadataError("bounded MethodDef limit exceeded")
    callsite_fielddef_tokens = []
    callsite_method_indices = set()
    all_instructions = []
    counts = {
        "cil_method_bodies_examined": 0,
        "target_callvirt_sites": 0,
        "target_call_sites": 0,
        "target_calls_preceded_by_ldfld_fielddef": 0,
        "target_calls_preceded_by_other_instruction": 0,
        "exact_same_module_typedeforref_token_equal_sites": 0,
        "exact_same_module_typedeforref_token_different_sites": 0,
        "exact_type_token_unclassified_sites": 0,
        "distinct_target_fielddefs_in_module": 0,
        "target_fielddef_stfld_write_sites": 0,
        "target_fielddef_stsfld_write_sites": 0,
        "distinct_target_fielddefs_with_any_stfld": 0,
        "distinct_target_fielddefs_without_local_stfld": 0,
        "distinct_methods_writing_target_fielddefs": 0,
        "distinct_target_call_methods_in_module": 0,
        "distinct_target_call_methods_with_local_field_write": 0,
        "distinct_target_call_methods_without_local_field_write": 0,
        "target_field_write_sites_in_target_call_methods": 0,
        "target_field_write_sites_outside_target_call_methods": 0,
        "immediately_preceding_stfld_opcode_family_counts": {
            name: 0 for name in (
                "none", "load_arg_or_address", "load_local_or_address",
                "load_field_or_address", "nested_call_or_calli_unresolved_return",
                "new_object_or_array", "load_null", "load_string",
                "load_numeric", "duplicate_stack_item", "type_cast_or_transform",
                "array_element_or_length", "load_method_or_type_handle",
                "prefix_not_value_producer", "nop", "other_or_unresolved",
            )
        },
        "writer_method_family_counts": {
            kind: 0 for kind in WRITER_METHOD_FAMILIES
        },
        "writer_write_sites_by_method_family": {
            kind: 0 for kind in WRITER_METHOD_FAMILIES
        },
        "preceding_stfld_exact_opcode_counts": {
            kind: 0 for kind in WRITER_PREDECESSOR_OPCODES
        },
        "preceding_stfld_operand_token_kind_counts": {
            kind: 0 for kind in WRITER_PREDECESSOR_TOKEN_KINDS
        },
        "preceding_stfld_opcode_by_writer_method_family": {
            family: {kind: 0 for kind in WRITER_PREDECESSOR_OPCODES}
            for family in WRITER_METHOD_FAMILIES
        },
    }
    for method in methods.values():
        if not method["rva"]:
            continue
        counts["cil_method_bodies_examined"] += 1
        code = _body(blob, method["rva"], sections)
        ins = _instructions(code)
        all_instructions.append((method["name"], code, ins))
        for i, (start, op, token, end) in enumerate(ins):
            if op not in (0x28, 0x6F) or token not in targets:
                continue
            key = "target_callvirt_sites" if op == 0x6F else "target_call_sites"
            callsite_method_indices.add(len(all_instructions) - 1)
            counts[key] += 1
            if counts["target_callvirt_sites"] + counts["target_call_sites"] > MAX_SITES_PER_MODULE:
                raise MetadataError("bounded target callsite limit exceeded")
            if i == 0 or ins[i - 1][1] != 0x7B:  # exact instance-field value, not address
                counts["target_calls_preceded_by_other_instruction"] += 1
                continue
            pstart, _, _, pend = ins[i - 1]
            if pend != start or pend - pstart != 5:
                raise MetadataError("invalid original preceding ldfld boundary")
            field_token = _u(code, pstart + 1, 4)
            if field_token >> 24 != 0x04 or not (field_token & 0xFFFFFF):
                raise MetadataError("expected original local FieldDef before target call")
            counts["target_calls_preceded_by_ldfld_fielddef"] += 1
            callsite_fielddef_tokens.append(field_token)
            field_coded = _simple_field_class(layout, field_token)
            parameter_coded = parameter_types[token]
            if field_coded is None or parameter_coded is None:
                counts["exact_type_token_unclassified_sites"] += 1
            elif field_coded == parameter_coded:
                counts["exact_same_module_typedeforref_token_equal_sites"] += 1
            else:
                counts["exact_same_module_typedeforref_token_different_sites"] += 1

    fields = set(callsite_fielddef_tokens)
    counts["distinct_target_fielddefs_in_module"] = len(fields)
    writers = set()
    fields_written = set()
    for method_index, (method_name, code, ins) in enumerate(all_instructions):
        method_family = (
            "instance_constructor" if method_name == ".ctor" else
            "type_initializer" if method_name == ".cctor" else
            "other_named_method"
        )
        matched_writes = 0
        for instruction_index, (start, op, _, end) in enumerate(ins):
            if op not in (0x7D, 0x80):  # stfld / stsfld
                continue
            if end - start != 5:
                raise MetadataError("invalid original field writer boundary")
            token = _u(code, start + 1, 4)
            if token not in fields:
                continue
            matched_writes += 1
            if matched_writes > MAX_MATCHED_WRITES_PER_MODULE:
                raise MetadataError("bounded original field writers limit exceeded")
            counts[
                "target_fielddef_stfld_write_sites" if op == 0x7D
                else "target_fielddef_stsfld_write_sites"
            ] += 1
            predecessor = ins[instruction_index - 1][1] if instruction_index else None
            category = _fixed_adjacent_class(predecessor)
            counts["immediately_preceding_stfld_opcode_family_counts"][category] += 1
            precise_opcode, precise_token_kind = _writer_predecessor_operand_category(
                code, ins, instruction_index
            )
            counts["preceding_stfld_exact_opcode_counts"][precise_opcode] += 1
            counts["preceding_stfld_operand_token_kind_counts"][precise_token_kind] += 1
            counts["preceding_stfld_opcode_by_writer_method_family"][
                method_family
            ][precise_opcode] += 1
            counts["writer_write_sites_by_method_family"][method_family] += 1
            counts[
                "target_field_write_sites_in_target_call_methods"
                if method_index in callsite_method_indices else
                "target_field_write_sites_outside_target_call_methods"
            ] += 1
            fields_written.add(token)
        if matched_writes:
            writers.add(method_index)
            counts["writer_method_family_counts"][method_family] += 1
    counts["distinct_methods_writing_target_fielddefs"] = len(writers)
    counts["distinct_target_call_methods_in_module"] = len(callsite_method_indices)
    counts["distinct_target_call_methods_with_local_field_write"] = len(
        callsite_method_indices & writers
    )
    counts["distinct_target_call_methods_without_local_field_write"] = len(
        callsite_method_indices - writers
    )
    counts["distinct_target_fielddefs_with_any_stfld"] = len(fields_written)
    counts["distinct_target_fielddefs_without_local_stfld"] = len(fields - fields_written)

    field_sites = counts["target_calls_preceded_by_ldfld_fielddef"]
    total_calls = counts["target_callvirt_sites"] + counts["target_call_sites"]
    if (
        field_sites + counts["target_calls_preceded_by_other_instruction"] != total_calls or
        counts["exact_same_module_typedeforref_token_equal_sites"] +
        counts["exact_same_module_typedeforref_token_different_sites"] +
        counts["exact_type_token_unclassified_sites"] != field_sites or
        counts["distinct_target_fielddefs_with_any_stfld"] +
        counts["distinct_target_fielddefs_without_local_stfld"] != len(fields) or
        sum(counts["writer_method_family_counts"].values()) != len(writers) or
        sum(counts["preceding_stfld_exact_opcode_counts"].values()) !=
            counts["target_fielddef_stfld_write_sites"] +
            counts["target_fielddef_stsfld_write_sites"] or
        sum(counts["preceding_stfld_operand_token_kind_counts"].values()) !=
            counts["target_fielddef_stfld_write_sites"] +
            counts["target_fielddef_stsfld_write_sites"] or
        any(
            sum(counts["preceding_stfld_opcode_by_writer_method_family"][family].values()) !=
            counts["writer_write_sites_by_method_family"][family]
            for family in WRITER_METHOD_FAMILIES
        ) or
        sum(counts["writer_write_sites_by_method_family"].values()) !=
            counts["target_fielddef_stfld_write_sites"] +
            counts["target_fielddef_stsfld_write_sites"] or
        any(
            sum(counts["preceding_stfld_opcode_by_writer_method_family"][family][kind]
                for family in WRITER_METHOD_FAMILIES) !=
            counts["preceding_stfld_exact_opcode_counts"][kind]
            for kind in WRITER_PREDECESSOR_OPCODES
        ) or
        sum(counts["immediately_preceding_stfld_opcode_family_counts"].values()) !=
            counts["target_fielddef_stfld_write_sites"] +
            counts["target_fielddef_stsfld_write_sites"] or
        counts["target_field_write_sites_in_target_call_methods"] +
        counts["target_field_write_sites_outside_target_call_methods"] !=
            counts["target_fielddef_stfld_write_sites"] +
            counts["target_fielddef_stsfld_write_sites"] or
        counts["distinct_target_call_methods_with_local_field_write"] +
        counts["distinct_target_call_methods_without_local_field_write"] !=
            counts["distinct_target_call_methods_in_module"]
    ):
        raise MetadataError("original field source aggregate counts did not reconcile")
    return counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise MetadataError("invalid original VIDA folder")
    found = {}
    seen = 0
    def walk_error(_):
        raise MetadataError("original source cannot be traversed")
    for root, dirs, names in os.walk(folder, topdown=True, followlinks=False, onerror=walk_error):
        dirs[:] = [d for d in dirs if not (Path(root) / d).is_symlink()]
        for name in names:
            seen += 1
            if seen > MAX_FILES_WALK:
                raise MetadataError("bounded source scan exceeded")
            key = name.casefold()
            if key not in EXPECTED:
                continue
            file = Path(root) / name
            if key in found or file.is_symlink() or not file.is_file():
                raise MetadataError("ambiguous original pinned DLL")
            found[key] = file
    if set(found) != set(EXPECTED):
        raise MetadataError("original pinned DLL set incomplete")
    result = []
    for key, (basename, expected_sha) in sorted(EXPECTED.items()):
        file = found[key]
        size = file.stat().st_size
        if not 128 <= size <= MAX_FILE:
            raise MetadataError("source file size outside approved limits")
        with file.open("rb") as stream:
            raw = stream.read(MAX_FILE + 1)
        if (len(raw) != size or file.stat().st_size != size or
                hashlib.sha256(raw).hexdigest() != expected_sha):
            raise MetadataError("original pinned DLL SHA256 mismatch")
        row = inspect_module(
            raw, require_interface_memberref=(key != "bizservices.carcom.db.dll")
        )
        result.append({"module_basename": basename, "counts": row})
    return {
        "schema_version": "virtualcar-vida-original-2015a-getinithw-fielddef-identity-writes-v1",
        "status": "owner_original_sha_pinned_local_fielddef_type_token_and_writes_counts_only",
        "results": result,
        "original_assemblies_loaded_or_executed": False,
        "source_writes_performed": False,
        "original_field_names_type_names_tokens_values_IL_or_paths_exported": False,
        "exact_local_type_token_match_proves_argument_value_source": False,
        "observed_field_writes_exhaustive_across_all_assemblies": False,
        "control_flow_stack_or_exception_handlers_traced": False,
        "field_assignments_or_runtime_values_verified": False,
        "preceding_stfld_opcode_proves_value_source": False,
        "writer_predecessor_metadata_token_kind_proves_return_type": False,
        "writer_opcode_cross_tab_proves_runtime_write_order": False,
        "writer_and_caller_same_method_proves_write_reaches_call": False,
        "profile_identifiers_argument_proven": False,
        "original_vida_2015a_generic_profile_inheritance_verified": False,
        "d2_baudrate_verified": False,
        "original_vida_readvin_accepted": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Original VIDA GetInitHwSettings local FieldDef identity and writer census"
    )
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(audit(args.folder), indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
