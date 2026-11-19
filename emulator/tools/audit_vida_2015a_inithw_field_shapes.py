#!/usr/bin/env python3
"""Owner-only original VIDA 2015A GetInitHwSettings preceding-field shape census.

Reads only the same three SHA-256-pinned original DLLs. Distinguishes
ldfld/ldflda/ldsfld/ldsflda and FieldDef versus field MemberRef, and
compares token-neutral field-signature type shape with the one target
parameter type shape. All names, original tokens and actual type data
remain IN MEMORY. This is *not* control-flow or stack provenance.

An adjacent field may not be the producer of the argument across branches,
exception handlers, unverifiable IL or other stack effects. Even equal
token-neutral type shapes do NOT establish semantic CLR type identity,
field values, selected profiles, inheritance, D2 baud or ReadVin acceptance.
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
    _metadata_tables, _sections, _body,
)
from audit_vida_2015a_inithw_callsite_adjacent import _instructions
from audit_vida_2015a_inithw_assembly_identity import _table_layout
from audit_vida_2015a_inithw_signature_shapes import (
    _SigReader, decode_shape, UnsupportedSignature,
)

FIELD_OPCODES = {
    0x7B: "ldfld",
    0x7C: "ldflda",
    0x7E: "ldsfld",
    0x7F: "ldsflda",
}
MAX_METHODS = 100000
MAX_SITES_PER_MODULE = 100
FIELD_SHAPE_TYPES = (
    "primitive", "class", "valuetype", "generic_instance",
    "generic_type_var", "generic_method_var", "szarray",
    "pointer", "byref", "modified", "other_or_unclassified",
)


def _field_signature_shape(raw: bytes) -> tuple:
    """ECMA-335 FieldSig: 0x06 followed by one Type (no field names)."""
    reader = _SigReader(raw)
    if reader.byte() != 0x06:
        raise MetadataError("expected CLR field signature calling convention")
    value = reader.typ()
    if reader.pos != len(raw):
        raise MetadataError("field signature contains unparsed trailing bytes")
    return value


def _shape_family(value: tuple) -> str:
    name = value[0]
    if name in ("void", "bool", "char", "i1", "u1", "i2", "u2",
                "i4", "u4", "i8", "u8", "r4", "r8", "string",
                "typedbyref", "nativeint", "nativeuint", "object"):
        return "primitive"
    if name in FIELD_SHAPE_TYPES:
        return name
    return "other_or_unclassified"


def _field_type_shape(layout: dict, token: int) -> tuple:
    """Resolve field signature bytes privately from a FieldDef/MemberRef token."""
    table_id, index = token >> 24, token & 0xFFFFFF
    if not index or table_id not in (0x04, 0x0A):
        raise MetadataError("invalid field loader metadata token category")
    if table_id == 0x04:
        p = layout["row"](4, index)
        sig_index = layout["u"](p + 2 + layout["strsize"], layout["blobsize"])
    else:
        p = layout["row"](10, index)
        sig_index = layout["u"](
            p + layout["memberref_parent_size"] + layout["strsize"],
            layout["blobsize"],
        )
    return _field_signature_shape(layout["blob"](sig_index))


def _one_parameter_shape(target_private_signature: bytes | None) -> tuple | None:
    if target_private_signature is None:
        return None
    try:
        sig = decode_shape(target_private_signature)
    except (MetadataError, UnsupportedSignature):
        return None
    return sig[2][0] if len(sig[2]) == 1 else None


def inspect_module(blob: bytes, *, require_interface_memberref: bool) -> dict:
    methods = _metadata_tables(blob)
    target = {
        tok: sig
        for tok, family in methods["target_reference_parent_type_families"].items()
        if family == "icarcom_repository"
        for sig in [methods["target_reference_signature_bytes_private"].get(tok)]
    }
    contracts = methods["target_reference_signature_contracts"]
    if require_interface_memberref:
        if len(target) != 1:
            raise MetadataError("expected exactly one original interface GetInitHwSettings MemberRef")
        if any(
            contracts.get(tok) is None or
            contracts[tok]["parameters"] != 1 or
            not contracts[tok]["has_this"]
            for tok in target
        ):
            raise MetadataError("unexpected GetInitHwSettings method signature header")
    elif target:
        raise MetadataError("unexpected interface MemberRef in repository assembly")
    expected_parameter_shapes = {
        token: _one_parameter_shape(raw) for token, raw in target.items()
    }
    layout = _table_layout(blob)
    sections = _sections(blob)
    if len(methods["methods"]) > MAX_METHODS:
        raise MetadataError("bounded original MethodDef limit exceeded")
    counts = {
        "cil_method_bodies_examined": 0,
        "interface_getinithw_callvirt_sites": 0,
        "interface_getinithw_call_sites": 0,
        "immediately_preceding_field_opcodes": {
            name: 0 for name in FIELD_OPCODES.values()
        },
        "preceding_non_field_instruction_sites": 0,
        "field_loads_with_fielddef_token": 0,
        "field_loads_with_memberref_token": 0,
        "field_type_shapes_compared": 0,
        "field_shape_equal_to_target_parameter_ignoring_local_type_tokens": 0,
        "field_shape_different_from_target_parameter": 0,
        "field_or_parameter_shape_unclassified": 0,
        "field_type_shape_family_counts": {
            shape: 0 for shape in FIELD_SHAPE_TYPES
        },
    }
    n_sites = 0
    for method in methods["methods"].values():
        if not method["rva"]:
            continue
        counts["cil_method_bodies_examined"] += 1
        code = _body(blob, method["rva"], sections)
        ins = _instructions(code)
        for i, (start, op, token, end) in enumerate(ins):
            if op not in (0x28, 0x6F) or token not in target:
                continue
            n_sites += 1
            if n_sites > MAX_SITES_PER_MODULE:
                raise MetadataError("too many original target calls in module")
            counts[
                "interface_getinithw_callvirt_sites" if op == 0x6F
                else "interface_getinithw_call_sites"
            ] += 1
            if i == 0 or ins[i - 1][1] not in FIELD_OPCODES:
                counts["preceding_non_field_instruction_sites"] += 1
                continue
            prev_start, prev_op, _, prev_end = ins[i - 1]
            if prev_end - prev_start != 5 or prev_end != start:
                raise MetadataError("invalid preceding field loader instruction boundary")
            counts["immediately_preceding_field_opcodes"][FIELD_OPCODES[prev_op]] += 1
            field_token = _u(code, prev_start + 1, 4)
            table_id = field_token >> 24
            if table_id not in (0x04, 0x0A) or (field_token & 0xFFFFFF) == 0:
                raise MetadataError("invalid preceding CIL field metadata token")
            counts[
                "field_loads_with_fielddef_token" if table_id == 0x04
                else "field_loads_with_memberref_token"
            ] += 1
            try:
                shape = _field_type_shape(layout, field_token)
            except UnsupportedSignature:
                shape = None
            parameter_shape = expected_parameter_shapes[token]
            if shape is not None:
                counts["field_type_shape_family_counts"][_shape_family(shape)] += 1
            else:
                counts["field_type_shape_family_counts"]["other_or_unclassified"] += 1
            if shape is None or parameter_shape is None:
                counts["field_or_parameter_shape_unclassified"] += 1
            else:
                counts["field_type_shapes_compared"] += 1
                key = (
                    "field_shape_equal_to_target_parameter_ignoring_local_type_tokens"
                    if shape == parameter_shape else
                    "field_shape_different_from_target_parameter"
                )
                counts[key] += 1
    field_loads = sum(counts["immediately_preceding_field_opcodes"].values())
    total_sites = counts["interface_getinithw_call_sites"] + counts["interface_getinithw_callvirt_sites"]
    if (field_loads + counts["preceding_non_field_instruction_sites"] != total_sites or
        counts["field_loads_with_fielddef_token"] +
        counts["field_loads_with_memberref_token"] != field_loads or
        counts["field_type_shapes_compared"] +
        counts["field_or_parameter_shape_unclassified"] != field_loads or
        sum(counts["field_type_shape_family_counts"].values()) != field_loads or
        counts["field_shape_equal_to_target_parameter_ignoring_local_type_tokens"] +
        counts["field_shape_different_from_target_parameter"] !=
        counts["field_type_shapes_compared"]):
        raise MetadataError("unreconciled owner-only field signature shape counts")
    return counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise MetadataError("invalid original VIDA directory")
    found = {}
    visited = 0
    def fail_walk(_):
        raise MetadataError("cannot safely scan original VIDA source folder")
    for root, dirs, files in os.walk(folder, followlinks=False, onerror=fail_walk):
        dirs[:] = [x for x in dirs if not (Path(root) / x).is_symlink()]
        for name in files:
            visited += 1
            if visited > MAX_FILES_WALK:
                raise MetadataError("original source discovery limit exceeded")
            key = name.casefold()
            if key not in EXPECTED:
                continue
            path = Path(root) / name
            if key in found or path.is_symlink() or not path.is_file():
                raise MetadataError("duplicate or unsafe original VIDA module")
            found[key] = path
    if set(found) != set(EXPECTED):
        raise MetadataError("exact three SHA-pinned original DLLs not found")
    result = []
    for key, (basename, expected_hash) in sorted(EXPECTED.items()):
        path = found[key]
        size = path.stat().st_size
        if not 128 <= size <= MAX_FILE:
            raise MetadataError("original VIDA DLL outside bounded size")
        with path.open("rb") as stream:
            blob = stream.read(MAX_FILE + 1)
        if (len(blob) != size or path.stat().st_size != size or
                hashlib.sha256(blob).hexdigest() != expected_hash):
            raise MetadataError("original SHA256 mismatch")
        row = inspect_module(
            blob, require_interface_memberref=(key != "bizservices.carcom.db.dll"),
        )
        result.append({"module_basename": basename, "counts": row})
    return {
        "schema_version": "virtualcar-vida-original-2015a-getinithw-preceding-field-shapes-v1",
        "status": "owner_original_sha_pinned_field_shape_adjacency_only",
        "results": result,
        "original_assemblies_loaded_or_executed": False,
        "source_writes_performed": False,
        "original_field_names_type_names_tokens_values_signatures_or_paths_exported": False,
        "field_shape_match_proves_semantic_clr_type_identity": False,
        "field_preceding_callvirt_proves_operand_stack_source": False,
        "field_value_or_writes_traced": False,
        "control_flow_branches_or_exception_handlers_traced": False,
        "profile_identifiers_argument_proven": False,
        "original_vida_2015a_generic_profile_inheritance_verified": False,
        "d2_baudrate_verified": False,
        "original_vida_readvin_accepted": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Owner-only original VIDA GetInitHwSettings preceding FieldSig shape census",
    )
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
