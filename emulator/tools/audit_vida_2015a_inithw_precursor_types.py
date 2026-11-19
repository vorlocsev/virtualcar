#!/usr/bin/env python3
"""Owner-private SHA-pinned original VIDA 2015A preceding producer inputs.

Narrow metadata-signature census for three GetInitHwSettings-related stfld
sites: ldstr versus a newobj constructor's sole parameter, nested call
return versus newobj constructor's sole parameter, and ldarg slot preceding
zero-explicit-param callvirt. Read-only, no original binaries executed.

All original IL, metadata tokens, names, strings, values and paths stay
inside the process. Output fixed counts only. Adjacency and matching CLR
metadata references are NOT stack flow, runtime execution, selected profile
identifiers, generic InitHw selection, D2 bitrate or VIDA ReadVin acceptance.
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
from audit_vida_2015a_inithw_callsite_adjacent import _instructions
from audit_vida_2015a_inithw_assembly_identity import _table_layout
from audit_vida_2015a_inithw_signature_shapes import _SigReader, UnsupportedSignature

MAX_METHODS = 100000
MAX_READERS = 100
MAX_WRITERS = 10000
SOURCE = ("ldstr", "nested_call", "receiver_ldarg", "other_or_unclassified")
RELATION = ("exact_same_module_type", "different_type", "unclassified")
CALL_OPS = ("call", "callvirt", "calli", "other_or_unclassified")
TOKENS = ("memberref", "methoddef", "other_or_unclassified")
SLOTS = ("slot0", "slot1", "slot2plus", "address_slot0", "address_slot1",
         "address_slot2plus", "other_or_unclassified")
KINDS = ("string", "class", "primitive", "other_or_unclassified")
_ATOMS = {
    0x01: "void", 0x02: "bool", 0x03: "char", 0x04: "i1",
    0x05: "u1", 0x06: "i2", 0x07: "u2", 0x08: "i4",
    0x09: "u4", 0x0A: "i8", 0x0B: "u8", 0x0C: "r4",
    0x0D: "r8", 0x0E: "string", 0x18: "nativeint",
    0x19: "nativeuint", 0x1C: "object",
}


def _simple_type(r: _SigReader) -> tuple | None:
    """Read a single bounded CLR type. Keep coded TypeDefOrRef private."""
    tag = r.byte()
    if tag == 0x12:  # ELEMENT_TYPE_CLASS
        coded = r.uint()
        if coded >> 2 == 0 or coded & 3 == 3:
            raise MetadataError("invalid local CLR class coded reference")
        return ("class", coded)
    if tag in _ATOMS:
        return (_ATOMS[tag],)
    # Supportable but not comparable to a simple class/string primitive.
    # Discard all private signature values after bounded parsing.
    r.pos -= 1
    r.typ()
    return None


def _signature(layout: dict, token: int) -> tuple[tuple | None, tuple, bool] | None:
    """MethodDef or MemberRef signature, exact local type tags kept in memory."""
    tid, rid = token >> 24, token & 0xFFFFFF
    if not rid or tid not in (6, 10):
        return None
    p = layout["row"](tid, rid)
    if tid == 10:
        offset = p + layout["memberref_parent_size"] + layout["strsize"]
    else:
        offset = p + 8 + layout["strsize"]  # MethodDef: RVA/ImplFlags/Flags/Name
    raw = layout["blob"](layout["u"](offset, layout["blobsize"]))
    try:
        r = _SigReader(raw)
        flags = r.byte()
        if flags & 0x80 or (flags & 0x0F) not in (0, 5):
            return None
        if flags & 0x10 and r.uint() > 64:
            raise MetadataError("method generic argument count out of bounds")
        n = r.uint()
        if n > 255:
            raise MetadataError("method parameter count out of bounds")
        ret = _simple_type(r)
        args = tuple(_simple_type(r) for _ in range(n))
        if r.pos != len(raw):
            return None
        return ret, args, bool(flags & 0x20)
    except UnsupportedSignature:
        return None


def _type_kind(t: tuple | None) -> str:
    if t is None:
        return "other_or_unclassified"
    if t[0] == "class":
        return "class"
    if t[0] == "string":
        return "string"
    return "primitive" if t[0] in _ATOMS.values() else "other_or_unclassified"


def _relation(a: tuple | None, b: tuple | None) -> str:
    if a is None or b is None:
        return "unclassified"
    return "exact_same_module_type" if a == b else "different_type"


def _arg_slot(code: bytes, inst: tuple) -> str:
    start, op, _, end = inst
    if 0x02 <= op <= 0x05:
        slot, address = op - 0x02, False
    elif op in (0x0E, 0x0F):
        if end - start != 2:
            raise MetadataError("invalid short argument loader instruction")
        slot, address = code[start + 1], op == 0x0F
    elif op in (0xFE09, 0xFE0A):
        if end - start != 4:
            raise MetadataError("invalid long argument loader instruction")
        slot, address = _u(code, start + 2, 2), op == 0xFE0A
    else:
        return "other_or_unclassified"
    label = ("slot0" if slot == 0 else "slot1" if slot == 1 else "slot2plus")
    return "address_" + label if address else label


def _field_token(code: bytes, ins: tuple, op: int) -> int:
    start, actual, _, end = ins
    if actual != op or end - start != 5:
        raise MetadataError("invalid original local FieldDef instruction")
    token = _u(code, start + 1, 4)
    if token >> 24 != 4 or not (token & 0xFFFFFF):
        raise MetadataError("invalid local FieldDef token")
    return token


def inspect_module(blob: bytes, *, require_interface_memberref: bool) -> dict:
    md = _metadata_tables(blob)
    targets = {tok for tok, fam in
               md["target_reference_parent_type_families"].items()
               if fam == "icarcom_repository"}
    if require_interface_memberref:
        if len(targets) != 1 or any(
            md["target_reference_signature_contracts"].get(tok) is None or
            md["target_reference_signature_contracts"][tok]["parameters"] != 1 or
            not md["target_reference_signature_contracts"][tok]["has_this"]
            for tok in targets
        ):
            raise MetadataError("unexpected original interface MemberRef contract")
    elif targets:
        raise MetadataError("unexpected original repository interface MemberRef")
    if len(md["methods"]) > MAX_METHODS:
        raise MetadataError("unbounded original MethodDef metadata")
    sections, layout = _sections(blob), _table_layout(blob)
    bodies, fields = [], set()
    reads = 0
    for method in md["methods"].values():
        if not method["rva"]:
            continue
        code = _body(blob, method["rva"], sections)
        ins = _instructions(code)
        bodies.append((code, ins))
        for i, (_, op, tok, _) in enumerate(ins):
            if op not in (0x28, 0x6F) or tok not in targets:
                continue
            if i == 0 or reads >= MAX_READERS:
                raise MetadataError("invalid original GetInitHwSettings site")
            fields.add(_field_token(code, ins[i - 1], 0x7B))
            reads += 1
    counts = {
        "cil_method_bodies_examined": len(bodies),
        "target_getinithw_calls": reads,
        "distinct_target_fielddefs_in_module": len(fields),
        "target_field_stfld_sites": 0,
        "newobj_producer_sites": 0,
        "callvirt_producer_sites": 0,
        "producer_input_source_counts": {k: 0 for k in SOURCE},
        "newobj_constructor_one_param_kind": {k: 0 for k in KINDS},
        "newobj_ldstr_constructor_parameter_relation": {k: 0 for k in RELATION},
        "newobj_nested_call_opcode_counts": {k: 0 for k in CALL_OPS},
        "newobj_nested_call_token_kind_counts": {k: 0 for k in TOKENS},
        "newobj_nested_call_return_to_constructor_parameter_relation": {
            k: 0 for k in RELATION
        },
        "callvirt_receiver_arg_slot_counts": {k: 0 for k in SLOTS},
        "callvirt_receiver_is_address": 0,
        "callvirt_receiver_is_value": 0,
        "callvirt_receiver_other_or_unclassified": 0,
    }
    for code, ins in bodies:
        for i, (start, op, _, end) in enumerate(ins):
            if op != 0x7D:
                continue
            if end - start != 5:
                raise MetadataError("invalid original stfld instruction")
            field = _u(code, start + 1, 4)
            if field not in fields:
                continue
            counts["target_field_stfld_sites"] += 1
            if counts["target_field_stfld_sites"] > MAX_WRITERS:
                raise MetadataError("unbounded target stfld count")
            if i < 2 or ins[i - 1][1] not in (0x73, 0x6F):
                counts["producer_input_source_counts"]["other_or_unclassified"] += 1
                continue
            prev = ins[i - 1]
            pstart, producer_op, _, pend = prev
            if pend != start or pend - pstart != 5:
                raise MetadataError("invalid original producer boundary")
            memberref = _u(code, pstart + 1, 4)
            sig = _signature(layout, memberref)
            input_inst = ins[i - 2]
            input_start, input_op, _, input_end = input_inst
            if input_end != pstart:
                raise MetadataError("invalid original source instruction boundary")
            if producer_op == 0x73:  # one-param constructor
                counts["newobj_producer_sites"] += 1
                param = sig[1][0] if sig is not None and len(sig[1]) == 1 else None
                counts["newobj_constructor_one_param_kind"][_type_kind(param)] += 1
                if input_op == 0x72:
                    counts["producer_input_source_counts"]["ldstr"] += 1
                    if input_end - input_start != 5 or (
                        _u(code, input_start + 1, 4) >> 24 != 0x70
                    ):
                        raise MetadataError("invalid original ldstr user string token")
                    counts["newobj_ldstr_constructor_parameter_relation"][
                        _relation(("string",), param)
                    ] += 1
                elif input_op in (0x28, 0x6F, 0x29):
                    counts["producer_input_source_counts"]["nested_call"] += 1
                    key = ("call" if input_op == 0x28 else
                           "callvirt" if input_op == 0x6F else "calli")
                    counts["newobj_nested_call_opcode_counts"][key] += 1
                    if input_end - input_start != 5:
                        raise MetadataError("invalid original nested call boundary")
                    producer_tok = _u(code, input_start + 1, 4)
                    token_table = producer_tok >> 24
                    token_kind = (
                        "memberref" if token_table == 10 else
                        "methoddef" if token_table == 6 else
                        "other_or_unclassified"
                    )
                    counts["newobj_nested_call_token_kind_counts"][token_kind] += 1
                    nested = (_signature(layout, producer_tok)
                              if input_op != 0x29 else None)
                    returned = nested[0] if nested is not None else None
                    counts["newobj_nested_call_return_to_constructor_parameter_relation"][
                        _relation(returned, param)
                    ] += 1
                else:
                    counts["producer_input_source_counts"]["other_or_unclassified"] += 1
            else:
                counts["callvirt_producer_sites"] += 1
                slot = _arg_slot(code, input_inst)
                if slot == "other_or_unclassified":
                    counts["producer_input_source_counts"]["other_or_unclassified"] += 1
                    counts["callvirt_receiver_other_or_unclassified"] += 1
                else:
                    counts["producer_input_source_counts"]["receiver_ldarg"] += 1
                    counts["callvirt_receiver_arg_slot_counts"][slot] += 1
                    counts["callvirt_receiver_is_address" if slot.startswith("address")
                           else "callvirt_receiver_is_value"] += 1

    total = counts["target_field_stfld_sites"]
    if sum(counts["producer_input_source_counts"].values()) != total:
        raise MetadataError("unreconciled producer source classifications")
    if sum(counts["newobj_constructor_one_param_kind"].values()) != counts["newobj_producer_sites"]:
        raise MetadataError("unreconciled newobj constructor input kind totals")
    if (sum(counts["newobj_ldstr_constructor_parameter_relation"].values()) !=
        counts["producer_input_source_counts"]["ldstr"] or
        sum(counts["newobj_nested_call_opcode_counts"].values()) !=
        counts["producer_input_source_counts"]["nested_call"] or
        sum(counts["newobj_nested_call_token_kind_counts"].values()) !=
        counts["producer_input_source_counts"]["nested_call"] or
        sum(counts["newobj_nested_call_return_to_constructor_parameter_relation"].values()) !=
        counts["producer_input_source_counts"]["nested_call"] or
        sum(counts["callvirt_receiver_arg_slot_counts"].values()) !=
        counts["producer_input_source_counts"]["receiver_ldarg"] or
        sum(counts[k] for k in (
            "callvirt_receiver_is_address", "callvirt_receiver_is_value",
            "callvirt_receiver_other_or_unclassified"
        )) != counts["callvirt_producer_sites"]):
        raise MetadataError("unreconciled nested call/receiver categories")
    return counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise MetadataError("invalid original VIDA directory")
    found, seen = {}, 0
    def scan_error(_):
        raise MetadataError("cannot safely scan pinned original DLL folder")
    for root, dirs, names in os.walk(folder, followlinks=False, onerror=scan_error):
        dirs[:] = [x for x in dirs if not (Path(root) / x).is_symlink()]
        for name in names:
            seen += 1
            if seen > MAX_FILES_WALK:
                raise MetadataError("bounded source walk exceeded")
            key = name.casefold()
            if key in EXPECTED:
                f = Path(root) / name
                if key in found or f.is_symlink() or not f.is_file():
                    raise MetadataError("ambiguous pinned original DLL")
                found[key] = f
    if set(found) != set(EXPECTED):
        raise MetadataError("missing pinned original source")
    output = []
    for key, (name, digest) in sorted(EXPECTED.items()):
        f = found[key]
        size = f.stat().st_size
        if not 128 <= size <= MAX_FILE:
            raise MetadataError("original source outside bounded size")
        with f.open("rb") as stream:
            blob = stream.read(MAX_FILE + 1)
        if (len(blob) != size or f.stat().st_size != size or
                hashlib.sha256(blob).hexdigest() != digest):
            raise MetadataError("original SHA256 pin mismatch")
        output.append({
            "module_basename": name,
            "counts": inspect_module(
                blob, require_interface_memberref=(key != "bizservices.carcom.db.dll"),
            ),
        })
    return {
        "schema_version": "virtualcar-vida-original-2015a-getinithw-precursor-signatures-v1",
        "status": "owner_original_source_only_precursor_signature_and_arg_slot_counts",
        "results": output,
        "source_writes_performed": False,
        "original_assemblies_loaded_or_executed": False,
        "original_signatures_tokens_strings_method_type_field_names_or_paths_emitted": False,
        "immediate_precursor_proves_constructor_input_or_receiver": False,
        "local_metadata_signature_match_proves_stack_provenance": False,
        "original_profile_identifiers_proven": False,
        "original_vida_2015a_generic_profile_inheritance_verified": False,
        "d2_baudrate_verified": False,
        "original_vida_readvin_accepted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Original VIDA source-only precursor method signatures")
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
