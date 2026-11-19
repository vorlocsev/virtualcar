#!/usr/bin/env python3
"""Owner-only, hash-pinned immediate CIL callsite adjacency census for VIDA 2015A.

Uses EXACTLY three previously SHA-256-pinned original VIDA DLLs as read-only
sources. Reports ONLY allowed fixed opcode-family counts for the instruction
IMMEDIATELY before each GetInitHwSettings interface call, not the actual
profileIdentifiers argument. Branches/exception handlers, locals, stack
merges, fields and nested return values require separate provenance work.

Never exports actual original instructions, IL bytes, metadata tokens,
method names (except fixed GetInitHwSettings), profile IDs, paths, VIN, or
assembly values. No original VIDA/CLR code is loaded/executed.
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
from audit_vida_2015a_inithw_il_calls import (
    _metadata_tables, _sections, _body, _calls,
    _ZERO, _SHORT, _INLINE, _FE_ZERO, _FE_SHORT, _FE_WORD, _FE_INLINE,
)

MAX_INSTRUCTIONS_PER_METHOD = 200000
MAX_METHODS_PER_ASSEMBLY = 100000
MAX_CANDIDATES_PER_ASSEMBLY = 100


def _instructions(code: bytes) -> list[tuple[int, int, int | None, int]]:
    """Decode bytecode boundaries, mirroring _calls; tokens stay in memory."""
    pos = 0
    instructions = []
    while pos < len(code):
        if len(instructions) >= MAX_INSTRUCTIONS_PER_METHOD:
            raise MetadataError("bounded CIL instruction count exceeded")
        start = pos
        op = code[pos]
        pos += 1
        if op == 0xFE:
            if pos == len(code):
                raise MetadataError("truncated two-byte CIL opcode")
            ext = code[pos]
            pos += 1
            op = 0xFE00 | ext
            if ext in _FE_ZERO:
                n = 0
            elif ext in _FE_SHORT:
                n = 1
            elif ext in _FE_WORD:
                n = 2
            elif ext in _FE_INLINE:
                n = 4
            else:
                raise MetadataError("unrecognized CIL FE instruction")
        elif op in _ZERO:
            n = 0
        elif op in _SHORT:
            n = 1
        elif op in _INLINE:
            n = 4
        elif op in (0x21, 0x23):
            n = 8
        elif op == 0x45:
            if pos + 4 > len(code):
                raise MetadataError("truncated CIL switch")
            count = _u(code, pos, 4)
            if count > (len(code) - pos - 4) // 4:
                raise MetadataError("CIL switch outside bounded body")
            n = 4 + 4 * count
        else:
            raise MetadataError("unknown CIL opcode while classifying adjacency")
        if pos + n > len(code):
            raise MetadataError("incomplete CIL instruction operand")
        token = _u(code, pos, 4) if op in (0x28, 0x6F) else None
        pos += n
        instructions.append((start, op, token, pos))
    if len([x for x in instructions if x[2] is not None]) != len([
            x for x in _calls(code) if x[0] in ("call", "callvirt")]):
        raise MetadataError("misaligned new and existing IL decoders")
    return instructions


def _fixed_adjacent_class(op: int | None) -> str:
    """Never confuse a previous opcode family with proven stack provenance."""
    if op is None:
        return "none"
    if op in (0x02, 0x03, 0x04, 0x05, 0x0E, 0x0F, 0xFE09, 0xFE0A):
        return "load_arg_or_address"
    if op in (0x06, 0x07, 0x08, 0x09, 0x11, 0x12, 0xFE0C, 0xFE0D):
        return "load_local_or_address"
    if op in (0x7B, 0x7C, 0x7E, 0x7F):
        return "load_field_or_address"
    if op in (0x28, 0x6F, 0x29):
        return "nested_call_or_calli_unresolved_return"
    if op in (0x73, 0x8D):
        return "new_object_or_array"
    if op == 0x14:
        return "load_null"
    if op == 0x72:
        return "load_string"
    if 0x15 <= op <= 0x23:
        return "load_numeric"
    if op == 0x25:
        return "duplicate_stack_item"
    if op in (0x74, 0x75, 0x79, 0x8C, 0xA5):
        return "type_cast_or_transform"
    if op in (0x8F, 0x90, 0x91, 0x92, 0x93, 0x94, 0x95, 0x96,
              0x97, 0x98, 0x99, 0x9A, 0xA3, 0x8E):
        return "array_element_or_length"
    if op in (0xFE06, 0xFE07, 0xD0):
        return "load_method_or_type_handle"
    if op in (0xFE12, 0xFE13, 0xFE14, 0xFE16, 0xFE19, 0xFE1E):
        return "prefix_not_value_producer"
    if op == 0x00:
        return "nop"
    return "other_or_unresolved"


def inspect_module(blob: bytes, *, require_interface_memberref: bool) -> dict:
    metadata = _metadata_tables(blob)
    candidates = {
        tok: con
        for tok, family in metadata["target_reference_parent_type_families"].items()
        if family == "icarcom_repository"
        for con in [metadata["target_reference_signature_contracts"].get(tok)]
    }
    if require_interface_memberref:
        if len(candidates) != 1:
            raise MetadataError("expected one original interface MemberRef")
        if any(x is None or x["parameters"] != 1 or not x["has_this"] for x in candidates.values()):
            raise MetadataError("original interface target signature contract unexpected")
    else:
        if candidates:
            raise MetadataError("unexpected original interface MemberRef in repository module")
    sections = _sections(blob)
    methods = metadata["methods"]
    if len(methods) > MAX_METHODS_PER_ASSEMBLY:
        raise MetadataError("bounded MethodDef limit exceeded")
    records = []
    bodies = 0
    for method in methods.values():
        if method["rva"] == 0:
            continue
        bodies += 1
        code = _body(blob, method["rva"], sections)
        ins = _instructions(code)
        for i, instruction in enumerate(ins):
            _, op, token, _ = instruction
            if op not in (0x28, 0x6F) or token not in candidates:
                continue
            if len(records) >= MAX_CANDIDATES_PER_ASSEMBLY:
                raise MetadataError("bounded target site count exceeded")
            preceding = ins[i - 1][1] if i > 0 else None
            records.append((op, _fixed_adjacent_class(preceding)))
    classes = {
        "none", "load_arg_or_address", "load_local_or_address",
        "load_field_or_address", "nested_call_or_calli_unresolved_return",
        "new_object_or_array", "load_null", "load_string", "load_numeric",
        "duplicate_stack_item", "type_cast_or_transform",
        "array_element_or_length", "load_method_or_type_handle",
        "prefix_not_value_producer", "nop", "other_or_unresolved",
    }
    histogram = {key: sum(r[1] == key for r in records) for key in sorted(classes)}
    if sum(histogram.values()) != len(records):
        raise MetadataError("CIL adjacency counts do not reconcile")
    return {
        "cil_methods_examined": bodies,
        "aligned_interface_getinithw_sites": len(records),
        "static_call_instruction_count": sum(r[0] == 0x28 for r in records),
        "static_callvirt_instruction_count": sum(r[0] == 0x6F for r in records),
        "immediately_preceding_opcode_family_counts": histogram,
        "adjacency_proves_operand_stack_provenance": False,
        "callsite_branch_control_flow_traced": False,
        "callsite_exception_handlers_traced": False,
        "local_variable_definitions_traced": False,
    }


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise MetadataError("invalid original VIDA directory")
    found = {}
    visited = 0
    def fail_walk(_):
        raise MetadataError("unable to traverse original binary folder")
    for root, dirs, files in os.walk(folder, topdown=True, followlinks=False, onerror=fail_walk):
        dirs[:] = [x for x in dirs if not (Path(root) / x).is_symlink()]
        for name in files:
            visited += 1
            if visited > MAX_FILES_WALK:
                raise MetadataError("original file discovery bounded limit exceeded")
            key = name.casefold()
            if key not in EXPECTED:
                continue
            file = Path(root) / name
            if key in found or file.is_symlink() or not file.is_file():
                raise MetadataError("ambiguous exact original VIDA assembly")
            found[key] = file
    if set(found) != set(EXPECTED):
        raise MetadataError("missing exact owner-pinned original DLL")
    result = []
    for key, (basename, expected_sha) in sorted(EXPECTED.items()):
        file = found[key]
        size = file.stat().st_size
        if not 128 <= size <= MAX_FILE:
            raise MetadataError("original binary size out of supported bounds")
        with file.open("rb") as stream:
            blob = stream.read(MAX_FILE + 1)
        if (len(blob) != size or file.stat().st_size != size or
                hashlib.sha256(blob).hexdigest() != expected_sha):
            raise MetadataError("source SHA256 does not match owner verified pin")
        row = inspect_module(blob, require_interface_memberref=(key != "bizservices.carcom.db.dll"))
        result.append({"module_basename": basename, "counts": row})
    return {
        "schema_version": "virtualcar-vida-original-2015a-getinithw-immediate-cil-adjacency-v1",
        "status": "owner_private_static_preceding_opcode_family_counts_only",
        "results": result,
        "original_assemblies_loaded_or_executed": False,
        "source_writes_performed": False,
        "original_il_bytecode_tokens_private_type_names_or_paths_exported": False,
        "static_callsite_proves_runtime_execution": False,
        "adjacent_opcode_proves_actual_argument_source": False,
        "profile_identifiers_argument_proven": False,
        "original_vida_2015a_generic_profile_inheritance_verified": False,
        "d2_baudrate_verified": False,
        "original_vida_readvin_accepted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Original VIDA 2015A static GetInitHwSettings callsite opcode families")
    p.add_argument("--folder", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        print(json.dumps(audit(args.folder), indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
