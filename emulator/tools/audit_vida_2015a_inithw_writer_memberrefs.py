#!/usr/bin/env python3
"""Owner-only, SHA-pinned VIDA 2015A constructor/callvirt-to-field type refs.

Census only: inspect MemberRef owner of immediately preceding newobj or
MemberRef return type of immediately preceding callvirt at target stfld
sites, compared to the FieldDef's type *within the same CLR module*.

No attempt at CFG, operand-stack, local variable, object identity or
runtime provenance. Original names/row IDs/IL bytes remain in memory.
Only fixed category counters leave this read-only process.
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
from audit_vida_2015a_inithw_field_writes import _simple_field_class
from audit_vida_2015a_inithw_signature_shapes import _SigReader, UnsupportedSignature

MAX_METHODS = 100000
MAX_TARGET_SITES = 100
MAX_WRITES = 10000
MAX_SIGNATURE_ARGS = 255
FAMILIES = ("instance_constructor", "type_initializer", "other_named_method")
RELATIONS = (
    "newobj_owner_exact_field_type", "newobj_owner_different_field_type",
    "newobj_owner_unclassified", "callvirt_return_exact_field_type",
    "callvirt_return_different_field_type", "callvirt_return_unclassified",
    "other_or_unclassified",
)


def _simple_method_return_and_header(raw: bytes) -> tuple[bool, bool, int | None] | None:
    """MethodSig: has_this, returns_void, simple class coded token or None.

    Ignores non-simple return types; strict structural parsing for supported
    signatures. No original CLR signature or type identity leaves memory.
    """
    try:
        r = _SigReader(raw)
        cc = r.byte()
        if cc & 0x80 or (cc & 0x0F) not in (0, 5):
            raise MetadataError("unsupported MemberRef method calling convention")
        if cc & 0x10:
            if r.uint() > 64:
                raise MetadataError("bounded generic method arity exceeded")
        n = r.uint()
        if n > MAX_SIGNATURE_ARGS:
            raise MetadataError("bounded MemberRef signature parameter count exceeded")
        ret_offset = r.pos
        if r.pos >= len(r.blob):
            raise MetadataError("truncated MemberRef return signature")
        class_token = None
        if r.blob[r.pos] == 0x12:  # ELEMENT_TYPE_CLASS, no modifiers
            r.byte()
            class_token = r.uint()
            if not class_token >> 2 or class_token & 3 not in (0, 1, 2):
                raise MetadataError("invalid return TypeDefOrRef coded index")
        else:
            r.typ()
        void_return = raw[ret_offset] == 0x01
        for _ in range(n):
            r.typ()
        if r.pos != len(raw):
            raise MetadataError("trailing MemberRef MethodSig data")
        return (bool(cc & 0x20), void_return, class_token)
    except UnsupportedSignature:
        return None


def _memberref_relation(layout: dict, token: int, field_type: int | None, kind: str) -> str:
    """Return a fixed relation. Equality compares only SAME-module coded types."""
    if token >> 24 != 0x0A or not token & 0xFFFFFF:
        return "other_or_unclassified"
    p = layout["row"](10, token & 0xFFFFFF)
    u = layout["u"]
    ps, ss, bs = (layout["memberref_parent_size"],
                  layout["strsize"], layout["blobsize"])
    coded_parent = u(p, ps)
    parent_tag, parent_row = coded_parent & 7, coded_parent >> 3
    if not parent_row or parent_tag not in (0, 1, 2, 3, 4):
        raise MetadataError("invalid MemberRefParent coded index")
    name = layout["typename"](u(p + ps, ss))
    sig = layout["blob"](u(p + ps + ss, bs))
    header = _simple_method_return_and_header(sig)
    if field_type is None or header is None:
        return kind + "_unclassified"
    has_this, void_return, simple_return = header
    if kind == "newobj":
        if name != ".ctor" or not has_this or not void_return:
            return "newobj_owner_unclassified"
        tag_map = {0: 0, 1: 1, 4: 2}
        if parent_tag not in tag_map:
            return "newobj_owner_unclassified"
        owner = (parent_row << 2) | tag_map[parent_tag]
        return ("newobj_owner_exact_field_type" if owner == field_type
                else "newobj_owner_different_field_type")
    if kind == "callvirt":
        if not has_this or simple_return is None:
            return "callvirt_return_unclassified"
        return ("callvirt_return_exact_field_type" if simple_return == field_type
                else "callvirt_return_different_field_type")
    return "other_or_unclassified"


def inspect_module(blob: bytes, *, require_interface_memberref: bool) -> dict:
    meta = _metadata_tables(blob)
    targets = {
        token for token, family in meta["target_reference_parent_type_families"].items()
        if family == "icarcom_repository"
    }
    if require_interface_memberref:
        if len(targets) != 1:
            raise MetadataError("original interface GetInitHwSettings MemberRef not unique")
        for token in targets:
            sig = meta["target_reference_signature_contracts"].get(token)
            if sig is None or sig["parameters"] != 1 or not sig["has_this"]:
                raise MetadataError("GetInitHwSettings MemberRef contract unexpected")
    elif targets:
        raise MetadataError("unexpected target MemberRef in original repository module")
    layout = _table_layout(blob)
    sections = _sections(blob)
    methods = meta["methods"]
    if len(methods) > MAX_METHODS:
        raise MetadataError("bounded original CIL MethodDef limit exceeded")
    bodies = []
    fields = set()
    callsites = 0
    for method in methods.values():
        if not method["rva"]:
            continue
        raw = _body(blob, method["rva"], sections)
        instructions = _instructions(raw)
        bodies.append((method["name"], raw, instructions))
        for i, (start, op, token, end) in enumerate(instructions):
            if op not in (0x28, 0x6F) or token not in targets:
                continue
            callsites += 1
            if callsites > MAX_TARGET_SITES:
                raise MetadataError("bounded original callsite count exceeded")
            if i == 0 or instructions[i - 1][1] != 0x7B:
                raise MetadataError("original target call missing immediate ldfld")
            pos, _, _, prev_end = instructions[i - 1]
            if prev_end != start or prev_end - pos != 5:
                raise MetadataError("original target field operand boundary invalid")
            field = _u(raw, pos + 1, 4)
            if field >> 24 != 0x04 or not (field & 0xFFFFFF):
                raise MetadataError("original preceding ldfld not local FieldDef")
            fields.add(field)
    if require_interface_memberref and not callsites:
        raise MetadataError("no original target GetInitHwSettings callsites")
    results = {
        "cil_method_bodies_examined": len(bodies),
        "target_getinithw_call_sites": callsites,
        "distinct_target_fielddefs_in_module": len(fields),
        "target_field_stfld_sites": 0,
        "newobj_memberref_preceding_stfld_sites": 0,
        "callvirt_memberref_preceding_stfld_sites": 0,
        "other_writer_predecessor_sites": 0,
        "writer_producer_type_relation_counts": {k: 0 for k in RELATIONS},
        "writer_producer_relation_by_method_family": {
            family: {k: 0 for k in RELATIONS} for family in FAMILIES
        },
    }
    count_writes = 0
    for method_name, raw, instructions in bodies:
        family = ("instance_constructor" if method_name == ".ctor" else
                  "type_initializer" if method_name == ".cctor" else
                  "other_named_method")
        for i, (start, op, token, end) in enumerate(instructions):
            if op != 0x7D:  # only stfld, exact observed original target writers
                continue
            if end - start != 5:
                raise MetadataError("truncated original stfld instruction")
            field = _u(raw, start + 1, 4)
            if field not in fields:
                continue
            count_writes += 1
            if count_writes > MAX_WRITES:
                raise MetadataError("bounded target field write count exceeded")
            rel = "other_or_unclassified"
            if i:
                prev_start, prev_op, _, prev_end = instructions[i - 1]
                if prev_end != start:
                    raise MetadataError("misaligned original predecessor instruction")
                if prev_op in (0x73, 0x6F):  # newobj or callvirt
                    if prev_end - prev_start != 5:
                        raise MetadataError("invalid original MemberRef predecessor width")
                    producer_tok = _u(raw, prev_start + 1, 4)
                    kind = "newobj" if prev_op == 0x73 else "callvirt"
                    if producer_tok >> 24 == 0x0A and producer_tok & 0xFFFFFF:
                        results[kind + "_memberref_preceding_stfld_sites"] += 1
                        rel = _memberref_relation(
                            layout, producer_tok,
                            _simple_field_class(layout, field),
                            kind,
                        )
            if rel == "other_or_unclassified":
                results["other_writer_predecessor_sites"] += 1
            results["writer_producer_type_relation_counts"][rel] += 1
            results["writer_producer_relation_by_method_family"][family][rel] += 1
    results["target_field_stfld_sites"] = count_writes
    if (sum(results["writer_producer_type_relation_counts"].values()) != count_writes or
        sum(results[k] for k in (
            "newobj_memberref_preceding_stfld_sites",
            "callvirt_memberref_preceding_stfld_sites",
            "other_writer_predecessor_sites",
        )) != count_writes or
        any(sum(results["writer_producer_relation_by_method_family"][fam].values())
            < 0 for fam in FAMILIES) or
        any(sum(results["writer_producer_relation_by_method_family"][fam][rel]
                for fam in FAMILIES) !=
            results["writer_producer_type_relation_counts"][rel]
            for rel in RELATIONS)):
        raise MetadataError("unreconciled original producer/field type relation counts")
    return results


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise MetadataError("invalid original VIDA folder")
    selected = {}
    visited = 0
    def _on_error(_):
        raise MetadataError("unreadable original source directory")
    for root, dirs, filenames in os.walk(folder, topdown=True, followlinks=False, onerror=_on_error):
        dirs[:] = [d for d in dirs if not (Path(root) / d).is_symlink()]
        for name in filenames:
            visited += 1
            if visited > MAX_FILES_WALK:
                raise MetadataError("original source walk bound exceeded")
            key = name.casefold()
            if key not in EXPECTED:
                continue
            file = Path(root) / name
            if key in selected or file.is_symlink() or not file.is_file():
                raise MetadataError("ambiguous SHA-pinned original DLL")
            selected[key] = file
    if set(selected) != set(EXPECTED):
        raise MetadataError("exact three original DLLs not found")
    outputs = []
    for key, (name, expected_sha) in sorted(EXPECTED.items()):
        file = selected[key]
        size = file.stat().st_size
        if size < 128 or size > MAX_FILE:
            raise MetadataError("original DLL file size outside limit")
        with file.open("rb") as stream:
            data = stream.read(MAX_FILE + 1)
        if (len(data) != size or file.stat().st_size != size or
                hashlib.sha256(data).hexdigest() != expected_sha):
            raise MetadataError("original DLL SHA256 mismatch")
        outputs.append({
            "module_basename": name,
            "counts": inspect_module(
                data, require_interface_memberref=key != "bizservices.carcom.db.dll",
            ),
        })
    return {
        "schema_version": "virtualcar-vida-original-2015a-getinithw-writer-memberref-types-v1",
        "status": "owner_original_readonly_writer_memberref_type_relation_counts_only",
        "results": outputs,
        "source_writes_performed": False,
        "original_assemblies_loaded_or_executed": False,
        "original_method_field_names_values_tokens_signatures_or_paths_emitted": False,
        "memberref_type_token_equality_proves_stack_value_source": False,
        "memberref_type_token_equality_proves_runtime_write": False,
        "original_getinithw_argument_profile_identifiers_proven": False,
        "control_flow_exception_handlers_or_receiver_aliases_traced": False,
        "original_vida_2015a_generic_profile_inheritance_verified": False,
        "d2_baudrate_verified": False,
        "original_vida_readvin_accepted": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Owner-only original VIDA writer MemberRef type relation counts")
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(audit(args.folder), indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
