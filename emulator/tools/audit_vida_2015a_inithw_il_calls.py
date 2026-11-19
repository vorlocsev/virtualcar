#!/usr/bin/env python3
"""Hash-pinned instruction-boundary CIL call census for original VIDA 2015A.

No original binary is executed or saved. Only three owner-hash-pinned DLLs
are read, using PE/CLR metadata offsets; target methods are matched by actual
MemberRef/MethodDef rows rather than arbitrary ASCII occurrences. The CIL
decoder rejects unknown opcodes and never treats a token inside another
instruction's operand as a call. Counts are only static callsites, not runtime
GetInitHwSettings calls, profile list contents, inheritance or D2 baud.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from audit_vida_2015a_inithw_metadata import (
    EXPECTED, MAX_FILE, MAX_FILES_WALK, MAX_ROWS, MetadataError,
    _cli_metadata, _rva_to_file, _u, parse_metadata,
)

TARGET = "GetInitHwSettings"
MAX_IL_BYTES = 1024 * 1024
MAX_TOTAL_IL_BYTES = 64 * 1024 * 1024
MAX_METHODS = 100000


def _compressed_uint(data: bytes, offset: int) -> tuple[int, int]:
    """ECMA-335 compressed unsigned integer (returns value, next offset)."""
    if not 0 <= offset < len(data):
        raise MetadataError("invalid compressed integer index")
    first = data[offset]
    if first < 0x80:
        return first, offset + 1
    if first < 0xC0 and offset + 1 < len(data):
        return ((first & 0x3F) << 8) | data[offset + 1], offset + 2
    if first < 0xE0 and offset + 3 < len(data):
        return (((first & 0x1F) << 24) | (data[offset + 1] << 16) |
                (data[offset + 2] << 8) | data[offset + 3]), offset + 4
    raise MetadataError("invalid compressed unsigned integer")


def _method_signature_contract(blob_heap: bytes | None, index: int) -> dict | None:
    """Only calling convention/hasThis/generic arity/parameter count, not types."""
    if blob_heap is None or index == 0:
        return None
    size, start = _compressed_uint(blob_heap, index)
    if size < 2 or size > 16384 or start + size > len(blob_heap):
        raise MetadataError("invalid target method signature extent")
    sig = blob_heap[start:start + size]
    cc = sig[0]
    kind = cc & 0x0F
    if kind not in (0, 5):
        raise MetadataError("target signature is not a method signature")
    pos = 1
    generic_arity = 0
    if cc & 0x10:
        generic_arity, pos = _compressed_uint(sig, pos)
        if generic_arity > 64:
            raise MetadataError("unbounded target method generic arity")
    params, pos = _compressed_uint(sig, pos)
    if params > 255:
        raise MetadataError("unbounded target method param count")
    return {
        "parameters": params,
        "has_this": bool(cc & 0x20),
        "explicit_this": bool(cc & 0x40),
        "generic_arity": generic_arity,
        "vararg": kind == 5,
    }


def _metadata_tables(blob: bytes) -> dict:
    streams = _cli_metadata(blob)
    tables = streams.get("#~", streams.get("#-"))
    strings = streams["#Strings"]
    blob_heap = streams.get("#Blob")
    if tables is None or len(tables) < 24:
        raise MetadataError("required CLR metadata tables missing")
    heaps = _u(tables, 6, 1)
    valid = _u(tables, 8, 8)
    counts, pos = {}, 24
    for tid in range(64):
        if valid & (1 << tid):
            cnt = _u(tables, pos, 4)
            pos += 4
            if cnt > MAX_ROWS:
                raise MetadataError("oversized CLR table")
            counts[tid] = cnt
    def idx(tid):
        return 4 if counts.get(tid, 0) >= 65536 else 2
    def coded(tids, bits):
        return 4 if max(counts.get(t, 0) for t in tids) >= 1 << (16 - bits) else 2
    ss = 4 if heaps & 1 else 2
    gs = 4 if heaps & 2 else 2
    bs = 4 if heaps & 4 else 2
    tdor = coded((1, 2, 27), 2)
    ref_parent = coded((2, 1, 26, 6, 27), 3)
    schemas = {
        0: 2 + ss + gs * 3,
        1: coded((0, 26, 35, 1), 2) + ss * 2,
        2: 4 + ss * 2 + tdor + idx(4) + idx(6),
        3: idx(4),
        4: 2 + ss + bs,
        5: idx(6),
        6: 8 + ss + bs + idx(8),
        7: idx(8),
        8: 4 + ss,
        9: idx(2) + tdor,
        10: ref_parent + ss + bs,
    }
    offsets = {}
    for tid in range(11):
        if counts.get(tid, 0):
            if tid not in schemas:
                raise MetadataError("unsupported CLR metadata table")
            end = pos + schemas[tid] * counts[tid]
            if end > len(tables):
                raise MetadataError("truncated CLR table")
            offsets[tid] = pos
            pos = end
    if counts.get(3) or counts.get(5) or counts.get(7):
        raise MetadataError("unresolved pointer tables")
    def row(tid, num):
        if not 1 <= num <= counts.get(tid, 0):
            raise MetadataError("CLR row index not present")
        return offsets[tid] + schemas[tid] * (num - 1)
    def name(off):
        if off <= 0 or off >= len(strings):
            raise MetadataError("invalid CLR name index")
        end = strings.find(b"\x00", off)
        if end < 0 or end - off > 512:
            raise MetadataError("unbounded CLR name")
        try:
            return strings[off:end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MetadataError("invalid CLR name") from exc
    def typename(tid, num):
        o = row(tid, num)
        c = 4 if tid == 2 else coded((0, 26, 35, 1), 2)
        return name(_u(tables, o + c, ss))

    methods = {}
    for i in range(1, counts.get(6, 0) + 1):
        o = row(6, i)
        method_name = name(_u(tables, o + 8, ss))
        methods[i] = {
            "rva": _u(tables, o, 4),
            "name": method_name,
            "signature_contract": (
                _method_signature_contract(blob_heap, _u(tables, o + 8 + ss, bs))
                if method_name == TARGET else None
            ),
        }
    typedefs = []
    for i in range(1, counts.get(2, 0) + 1):
        o = row(2, i)
        first = _u(tables, o + 4 + ss * 2 + tdor + idx(4), idx(6))
        typedefs.append((typename(2, i), first))
    if counts.get(6, 0) > MAX_METHODS:
        raise MetadataError("too many CLR method bodies")
    if methods and not typedefs:
        raise MetadataError("unowned CLR methods")
    for i, (type_name, first) in enumerate(typedefs):
        stop = typedefs[i + 1][1] if i + 1 < len(typedefs) else len(methods) + 1
        if not (1 <= first <= stop <= len(methods) + 1):
            raise MetadataError("invalid TypeDef method range")
        for k in range(first, stop):
            methods[k]["repository_owner"] = type_name == "CarComRepository"
            methods[k]["hwsettings_owner"] = type_name == "HwSettings"
    if any("repository_owner" not in m or "hwsettings_owner" not in m
           for m in methods.values()):
        raise MetadataError("unowned CLR method")
    # InterfaceImpl rows: exact Class=CarComRepository TypeDef row,
    # Interface=ICarComRepository TypeRef/TypeDef row. This still does not
    # prove that any method was invoked or bound at runtime.
    repo_typedefs = {i for i, (label, _) in enumerate(typedefs, 1)
                     if label == "CarComRepository"}
    direct_iface_impls = 0
    for i in range(1, counts.get(9, 0) + 1):
        o = row(9, i)
        owner_type = _u(tables, o, idx(2))
        iface_token = _u(tables, o + idx(2), tdor)
        tag, num = iface_token & 3, iface_token >> 2
        if owner_type in repo_typedefs and num and tag in (0, 1):
            iface_name = typename(2 if tag == 0 else 1, num)
            direct_iface_impls += int(iface_name == "ICarComRepository")
    references = {}
    reference_signature_contracts = {}
    reference_parent_category = {}
    reference_parent_kind = {}
    reference_parent_type_family = {}
    reference_typeref_resolution_scope = {}
    for i in range(1, counts.get(10, 0) + 1):
        off = row(10, i)
        parent = _u(tables, off, ref_parent)
        refname = name(_u(tables, off + ref_parent, ss))
        if refname != TARGET:
            continue
        signature_contract = _method_signature_contract(
            blob_heap, _u(tables, off + ref_parent + ss, bs)
        )
        tag, index = parent & 7, parent >> 3
        if tag not in (0, 1, 2, 3, 4) or not index:
            raise MetadataError("invalid MemberRefParent coded tag")
        kinds = ("typedef", "typeref", "moduleref", "methoddef", "typespec")
        kind = kinds[tag]
        scope = "not_typeref"
        if tag == 1:
            type_ref_offset = row(1, index)
            scope_coded = _u(tables, type_ref_offset, coded((0, 26, 35, 1), 2))
            scope_tag = scope_coded & 3
            scope_index = scope_coded >> 2
            scope_names = ("module", "moduleref", "assemblyref", "nested_typeref")
            scope = scope_names[scope_tag] if scope_index else "unresolved"
        if tag == 0:
            parent_name = typename(2, index)
        elif tag == 1:
            parent_name = typename(1, index)
        else:
            parent_name = None
        token = 0x0A000000 | i
        references[token] = parent_name == "CarComRepository"
        reference_signature_contracts[token] = signature_contract
        reference_parent_category[token] = (
            "carcom_repository" if parent_name == "CarComRepository" else
            "hwsettings" if parent_name == "HwSettings" else "other_or_unresolved"
        )
        reference_parent_kind[token] = kind
        reference_typeref_resolution_scope[token] = scope
        reference_parent_type_family[token] = (
            "carcom_repository" if parent_name == "CarComRepository" else
            "icarcom_repository" if parent_name == "ICarComRepository" else
            "hwsettings" if parent_name == "HwSettings" else
            "icarcom_repository_suffix_lexical" if
                parent_name is not None and parent_name.startswith("I") and
                parent_name.endswith("CarComRepository") else
            "other_or_unresolved"
        )
    target_defs = {
        0x06000000 | i: m["repository_owner"]
        for i, m in methods.items() if m["name"] == TARGET
    }
    definition_owner_category = {
        0x06000000 | i: (
            "carcom_repository" if m["repository_owner"] else
            "hwsettings" if m["hwsettings_owner"] else "other"
        )
        for i, m in methods.items() if m["name"] == TARGET
    }
    return {
        "methods": methods,
        "carcom_repository_direct_icarcomrepository_interfaceimpl_rows": direct_iface_impls,
        "target_references": references,
        "target_reference_signature_contracts": reference_signature_contracts,
        "target_reference_parent_categories": reference_parent_category,
        "target_reference_parent_kinds": reference_parent_kind,
        "target_reference_parent_type_families": reference_parent_type_family,
        "target_reference_typeref_resolution_scopes": reference_typeref_resolution_scope,
        "target_definitions": target_defs,
        "target_definition_owner_categories": definition_owner_category,
        "fixed_name_tables_parsed": True,
    }


def _sections(blob: bytes) -> list[tuple[int, int, int, int]]:
    if blob[:2] != b"MZ":
        raise MetadataError("invalid PE image")
    pe = _u(blob, 0x3C, 4)
    if blob[pe:pe + 4] != b"PE\x00\x00":
        raise MetadataError("invalid PE header")
    n = _u(blob, pe + 6, 2)
    opt_size = _u(blob, pe + 20, 2)
    if not 1 <= n <= 96:
        raise MetadataError("invalid PE sections")
    start = pe + 24 + opt_size
    sections = []
    for i in range(n):
        off = start + i * 40
        virtual_size = _u(blob, off + 8, 4)
        virt = _u(blob, off + 12, 4)
        raw_size = _u(blob, off + 16, 4)
        raw = _u(blob, off + 20, 4)
        sections.append((virt, max(virtual_size, raw_size), raw, raw_size))
    return sections


def _body(blob: bytes, rva: int, sections: list) -> bytes:
    offset = _rva_to_file(blob, rva, 1, sections)
    flags = blob[offset]
    if flags & 3 == 2:
        hdr = 1
        n = flags >> 2
    elif flags & 3 == 3:
        header_flags = _u(blob, offset, 2)
        words = header_flags >> 12
        if not 3 <= words <= 8:
            raise MetadataError("unexpected fat IL header size")
        hdr = words * 4
        _rva_to_file(blob, rva, hdr, sections)
        n = _u(blob, offset + 4, 4)
    else:
        raise MetadataError("unrecognized IL method header")
    if n > MAX_IL_BYTES:
        raise MetadataError("method IL outside bounded source scope")
    start = _rva_to_file(blob, rva, hdr + max(n, 1), sections) + hdr
    return blob[start:start + n]


# ECMA-335 II.25 opcode operand widths, for ordinary valid one-/two-byte CIL.
_ZERO = (set(range(0x00, 0x0E)) | set(range(0x14, 0x1F)) |
         {0x25, 0x26, 0x2A, 0x76, 0x7A, 0x8E, 0xC3} |
         set(range(0x46, 0x6F)) | set(range(0x82, 0x8C)) |
         set(range(0x90, 0xA3)) | set(range(0xB3, 0xBB)) |
         (set(range(0xD1, 0xDD)) | {0xDF, 0xE0}))
_SHORT = set(range(0x0E, 0x14)) | {0x1F, 0xDE} | set(range(0x2B, 0x38))
_INLINE = (
    {0x20, 0x22, 0x27, 0x28, 0x29, 0x6F, 0xDD, 0x79, 0x8C, 0x8D,
     0x8F, 0xA3, 0xA4, 0xA5, 0xC2, 0xC6, 0xD0, 0x73, 0x74, 0x75,
     0x71, 0x72, 0x70} |
    set(range(0x38, 0x45)) |
    set(range(0x7B, 0x82))
)
_FE_ZERO = set(range(0x00, 0x06)) | {0x0F, 0x11, 0x13, 0x14, 0x17, 0x18, 0x1A, 0x1D, 0x1E}
_FE_SHORT = {0x12, 0x19}  # unaligned. and no. prefixes (ECMA-335)
_FE_WORD = set(range(0x09, 0x0F))
_FE_INLINE = {0x06, 0x07, 0x15, 0x16, 0x1C}


def _calls(code: bytes) -> list[tuple[str, int]]:
    result = []
    p = 0
    while p < len(code):
        op = code[p]
        p += 1
        if op == 0xFE:
            if p >= len(code):
                raise MetadataError("truncated two-byte CIL opcode")
            extra = code[p]
            p += 1
            if extra in _FE_ZERO:
                n = 0
            elif extra in _FE_SHORT:
                n = 1
            elif extra in _FE_WORD:
                n = 2
            elif extra in _FE_INLINE:
                n = 4
            else:
                raise MetadataError("unsupported two-byte CIL opcode FE_%02X" % extra)
            operation = "ldftn" if extra == 0x06 else "ldvirtftn" if extra == 0x07 else ""
        elif op in _ZERO:
            n, operation = 0, ""
        elif op in _SHORT:
            n, operation = 1, ""
        elif op in _INLINE:
            n = 4
            operation = ("call" if op == 0x28 else
                         "callvirt" if op == 0x6F else
                         "newobj" if op == 0x73 else "")
        elif op in (0x21, 0x23):
            n, operation = 8, ""
        elif op == 0x45:
            if p + 4 > len(code):
                raise MetadataError("truncated CIL switch")
            count = _u(code, p, 4)
            if count > (len(code) - p - 4) // 4:
                raise MetadataError("unbounded CIL switch")
            n, operation = 4 + count * 4, ""
        else:
            raise MetadataError("unknown CIL opcode %02X" % op)
        if p + n > len(code):
            raise MetadataError("truncated CIL operand")
        if operation:
            result.append((operation, _u(code, p, 4)))
        p += n
    return result


def inspect_module(blob: bytes) -> dict:
    meta = _metadata_tables(blob)
    # Independently run the proven old TypeDef/MethodDef/MemberRef index gate.
    original = parse_metadata(blob)
    for name, total in original["target_memberref_name_counts"].items():
        if name == TARGET and total != len(meta["target_references"]):
            raise MetadataError("inconsistent exact CLR MemberRef count")
    section_map = _sections(blob)
    ref = meta["target_references"]
    local = meta["target_definitions"]
    def _parameter_buckets(items):
        totals = {}
        for item in items:
            key = "unavailable" if item is None else "param_count_" + str(item["parameters"])
            totals[key] = totals.get(key, 0) + 1
        return dict(sorted(totals.items()))
    target_definition_sigs = [
        m["signature_contract"] for m in meta["methods"].values()
        if m["name"] == TARGET
    ]
    target_reference_sigs = list(meta["target_reference_signature_contracts"].values())
    counts = {
        "method_bodies_present": 0,
        "carcom_repository_direct_icarcomrepository_interfaceimpl_rows":
            meta["carcom_repository_direct_icarcomrepository_interfaceimpl_rows"],
        "getinithw_methoddef_parameter_count_categories": _parameter_buckets(target_definition_sigs),
        "getinithw_memberref_parameter_count_categories": _parameter_buckets(target_reference_sigs),
        "getinithw_methoddef_signature_unavailable": sum(x is None for x in target_definition_sigs),
        "getinithw_memberref_signature_unavailable": sum(x is None for x in target_reference_sigs),
        "getinithw_methoddef_has_this": sum(x is not None and x["has_this"] for x in target_definition_sigs),
        "getinithw_memberref_has_this": sum(x is not None and x["has_this"] for x in target_reference_sigs),
        "getinithw_methoddef_vararg": sum(x is not None and x["vararg"] for x in target_definition_sigs),
        "getinithw_memberref_vararg": sum(x is not None and x["vararg"] for x in target_reference_sigs),
        "method_bodies_decoded": 0,
        "method_bodies_unsupported": 0,
        "target_name_memberref_rows": len(ref),
        "target_name_memberrefs_on_repository_type": sum(ref.values()),
        "target_name_methoddef_rows": len(local),
        "target_name_methoddefs_on_repository_type": sum(local.values()),
        "target_memberref_parent_kind_counts": {
            kind: sum(x == kind for x in meta["target_reference_parent_kinds"].values())
            for kind in ("typedef", "typeref", "moduleref", "methoddef", "typespec")
        },
        "target_memberref_parent_type_family_counts": {
            family: sum(x == family for x in meta["target_reference_parent_type_families"].values())
            for family in (
                "carcom_repository", "icarcom_repository", "hwsettings",
                "icarcom_repository_suffix_lexical", "other_or_unresolved"
            )
        },
        "target_memberref_typeref_scope_counts": {
            scope: sum(x == scope for x in meta["target_reference_typeref_resolution_scopes"].values())
            for scope in (
                "module", "moduleref", "assemblyref", "nested_typeref",
                "unresolved", "not_typeref"
            )
        },
        "target_memberref_parent_carcom_repository_rows": sum(
            cat == "carcom_repository" for cat in meta["target_reference_parent_categories"].values()
        ),
        "target_memberref_parent_hwsettings_rows": sum(
            cat == "hwsettings" for cat in meta["target_reference_parent_categories"].values()
        ),
        "target_memberref_parent_other_or_unresolved_rows": sum(
            cat == "other_or_unresolved" for cat in meta["target_reference_parent_categories"].values()
        ),
        "target_methoddef_owner_hwsettings_rows": sum(
            cat == "hwsettings" for cat in meta["target_definition_owner_categories"].values()
        ),
        "target_methoddef_owner_other_rows": sum(
            cat == "other" for cat in meta["target_definition_owner_categories"].values()
        ),
        "direct_call_memberref_sites": 0,
        "direct_call_local_methoddef_sites": 0,
        "direct_call_to_repository_memberref_sites": 0,
        "direct_call_to_repository_local_methoddef_sites": 0,
        "ldftn_reference_sites_not_calls": 0,
        "distinct_methods_with_target_calls": 0,
        "distinct_target_caller_methods_in_carcom_repository": 0,
        "distinct_target_caller_methods_in_hwsettings": 0,
        "distinct_target_caller_methods_in_other_types": 0,
        "direct_target_calls_to_hwsettings_memberref": 0,
        "direct_target_calls_to_other_or_unresolved_memberref": 0,
        "method_bodies_unsupported_unknown_opcode": 0,
        "method_bodies_unsupported_truncated_or_invalid_operand": 0,
        "method_bodies_unsupported_other": 0,
        "unsupported_unknown_opcode_histogram": {},
    }
    total_bytes = 0
    for method in meta["methods"].values():
        if method["rva"] == 0:
            continue
        counts["method_bodies_present"] += 1
        body = _body(blob, method["rva"], section_map)
        total_bytes += len(body)
        if total_bytes > MAX_TOTAL_IL_BYTES:
            raise MetadataError("total original CIL scan bound exceeded")
        try:
            calls = _calls(body)
        except MetadataError as exc:
            counts["method_bodies_unsupported"] += 1
            reason = str(exc)
            if "opcode" in reason:
                counts["method_bodies_unsupported_unknown_opcode"] += 1
                opcode = reason.rsplit(" ", 1)[-1]
                if (len(opcode) == 2 or
                        (len(opcode) == 5 and opcode.startswith("FE_"))) and all(
                    digit in "0123456789ABCDEF" for digit in opcode.replace("FE_", "")
                ):
                    opcode_class = "cil_opcode_" + opcode
                else:
                    opcode_class = "cil_opcode_unresolved"
                bins = counts["unsupported_unknown_opcode_histogram"]
                bins[opcode_class] = bins.get(opcode_class, 0) + 1
            elif "operand" in reason or "switch" in reason:
                counts["method_bodies_unsupported_truncated_or_invalid_operand"] += 1
            else:
                counts["method_bodies_unsupported_other"] += 1
            continue
        counts["method_bodies_decoded"] += 1
        has_call = False
        for kind, target_token in calls:
            if target_token in ref:
                if kind in ("call", "callvirt"):
                    counts["direct_call_memberref_sites"] += 1
                    counts["direct_call_to_repository_memberref_sites"] += int(ref[target_token])
                    category = meta["target_reference_parent_categories"][target_token]
                    counts["direct_target_calls_to_hwsettings_memberref"] += int(category == "hwsettings")
                    counts["direct_target_calls_to_other_or_unresolved_memberref"] += int(category == "other_or_unresolved")
                    has_call = True
                elif kind in ("ldftn", "ldvirtftn"):
                    counts["ldftn_reference_sites_not_calls"] += 1
            elif target_token in local:
                if kind in ("call", "callvirt"):
                    counts["direct_call_local_methoddef_sites"] += 1
                    counts["direct_call_to_repository_local_methoddef_sites"] += int(local[target_token])
                    has_call = True
                elif kind in ("ldftn", "ldvirtftn"):
                    counts["ldftn_reference_sites_not_calls"] += 1
        counts["distinct_methods_with_target_calls"] += int(has_call)
        if has_call:
            category = ("distinct_target_caller_methods_in_carcom_repository" if method["repository_owner"] else
                        "distinct_target_caller_methods_in_hwsettings" if method["hwsettings_owner"] else
                        "distinct_target_caller_methods_in_other_types")
            # For caller provenance, count distinct methods here; a method
            # containing multiple callsites still counts only once.
            counts[category] += 1
    if (counts["method_bodies_decoded"] + counts["method_bodies_unsupported"]
            != counts["method_bodies_present"] or
            counts["method_bodies_unsupported"] !=
            counts["method_bodies_unsupported_unknown_opcode"] +
            counts["method_bodies_unsupported_truncated_or_invalid_operand"] +
            counts["method_bodies_unsupported_other"] or
            counts["distinct_methods_with_target_calls"] !=
            counts["distinct_target_caller_methods_in_carcom_repository"] +
            counts["distinct_target_caller_methods_in_hwsettings"] +
            counts["distinct_target_caller_methods_in_other_types"] or
            counts["target_name_memberref_rows"] !=
            counts["target_memberref_parent_carcom_repository_rows"] +
            counts["target_memberref_parent_hwsettings_rows"] +
            counts["target_memberref_parent_other_or_unresolved_rows"] or
            sum(counts["target_memberref_parent_kind_counts"].values()) !=
            counts["target_name_memberref_rows"] or
            sum(counts["target_memberref_parent_type_family_counts"].values()) !=
            counts["target_name_memberref_rows"] or
            sum(counts["target_memberref_typeref_scope_counts"].values()) !=
            counts["target_name_memberref_rows"] or
            sum(counts["unsupported_unknown_opcode_histogram"].values()) !=
            counts["method_bodies_unsupported_unknown_opcode"]):
        raise MetadataError("unreconciled CIL decoder scope")
    counts["all_present_cil_method_bodies_decoded"] = (
        counts["method_bodies_unsupported"] == 0
    )
    return counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise MetadataError("invalid original assembly folder")
    found, visited = {}, 0
    def walk_error(_):
        raise MetadataError("unable to traverse original binary folder")
    for root, dirs, files in os.walk(folder, followlinks=False, onerror=walk_error):
        dirs[:] = [x for x in dirs if not (Path(root) / x).is_symlink()]
        for name in files:
            visited += 1
            if visited > MAX_FILES_WALK:
                raise MetadataError("binary source walk bound exceeded")
            key = name.casefold()
            if key not in EXPECTED:
                continue
            path = Path(root) / name
            if path.is_symlink() or not path.is_file() or key in found:
                raise MetadataError("ambiguous owner-pinned original DLL")
            found[key] = path
    if set(found) != set(EXPECTED):
        raise MetadataError("missing pinned original DLL")
    results = []
    for key, (basename, sha) in sorted(EXPECTED.items()):
        file = found[key]
        n = file.stat().st_size
        if not 128 <= n <= MAX_FILE:
            raise MetadataError("pinned source outside bounded size")
        with file.open("rb") as stream:
            blob = stream.read(MAX_FILE + 1)
        if len(blob) != n or hashlib.sha256(blob).hexdigest() != sha or file.stat().st_size != n:
            raise MetadataError("original source SHA256 changed")
        counts = inspect_module(blob)
        results.append({"module_basename": basename, "sha256": sha, "counts": counts})
    return {
        "schema_version": "virtualcar-vida-original-2015a-getinithw-cil-calls-v1",
        "status": "owner_original_hash_pinned_static_cil_callsite_counts_only",
        "results": results,
        "source_writes_performed": False,
        "original_assemblies_loaded_or_executed": False,
        "source_il_bytes_method_names_profiles_or_paths_exported": False,
        "static_calls_prove_execution": False,
        "memberref_owner_name_proves_runtime_target_binding": False,
        "carcom_repository_interfaceimpl_name_proves_runtime_binding": False,
        "method_parameter_count_proves_argument_types": False,
        "memberref_assemblyref_identity_verified": False,
        "callsite_arguments_or_profile_list_proven": False,
        "original_vida_2015a_generic_profile_inheritance_verified": False,
        "d2_baudrate_verified": False,
        "original_vida_readvin_accepted": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only owner VIDA hash-pinned CIL callsite categories")
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(audit(args.folder), sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
