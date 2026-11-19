#!/usr/bin/env python3
"""VIDA 2015A source-only SHA-pinned MemberRef arity and branch-entry census.

Reads three original DLLs as bytes. No code execution, field values, IL
dumps, raw names, tokens, paths, CFG or stack provenance assertions.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from audit_vida_2015a_inithw_metadata import EXPECTED, MAX_FILE, MAX_FILES_WALK, MetadataError, _u
from audit_vida_2015a_inithw_il_calls import _metadata_tables, _sections, _body, _rva_to_file
from audit_vida_2015a_inithw_callsite_adjacent import _instructions
from audit_vida_2015a_inithw_assembly_identity import _table_layout
from audit_vida_2015a_inithw_signature_shapes import _SigReader, UnsupportedSignature

KINDS = ("newobj", "callvirt", "unclassified")
ARITIES = ("zero", "one", "two_or_more", "unclassified")
SINKS = ("reader", "writer")


def _arity(layout, token):
    if token >> 24 != 10 or token & 0xFFFFFF == 0:
        return "unclassified"
    p = layout["row"](10, token & 0xFFFFFF)
    idx = layout["u"](p + layout["memberref_parent_size"] +
                       layout["strsize"], layout["blobsize"])
    try:
        r = _SigReader(layout["blob"](idx))
        flags = r.byte()
        if flags & 0x80 or flags & 0x0F not in (0, 5):
            return "unclassified"
        if flags & 0x10 and r.uint() > 64:
            raise MetadataError("unbounded method generic arity")
        count = r.uint()
        if count > 255:
            raise MetadataError("unbounded MemberRef method parameters")
        r.typ()
        for _ in range(count):
            r.typ()
        if r.pos != len(r.blob):
            return "unclassified"
        return "zero" if count == 0 else "one" if count == 1 else "two_or_more"
    except UnsupportedSignature:
        return "unclassified"


def _moresects(blob, rva, sections):
    pos = _rva_to_file(blob, rva, 2, sections)
    kind = blob[pos] & 3
    if kind == 2:
        return False
    if kind == 3:
        return bool(_u(blob, pos, 2) & 8)
    raise MetadataError("invalid method header kind")


def _branch_targets(code, ins):
    targets = set()
    for start, op, _, end in ins:
        if 0x2B <= op <= 0x37 or op == 0xDE:
            if end - start != 2:
                raise MetadataError("invalid short branch width")
            targets.add(end + int.from_bytes(code[start + 1:end], "little", signed=True))
        elif 0x38 <= op <= 0x44 or op == 0xDD:
            if end - start != 5:
                raise MetadataError("invalid branch width")
            targets.add(end + int.from_bytes(code[start + 1:end], "little", signed=True))
        elif op == 0x45:
            n = _u(code, start + 1, 4)
            if end != start + 5 + n * 4:
                raise MetadataError("invalid switch width")
            for j in range(n):
                targets.add(end + int.from_bytes(
                    code[start + 5 + 4 * j:start + 9 + 4 * j], "little", signed=True))
    starts = {x[0] for x in ins}
    if any(x < 0 or x > len(code) or
           (x != len(code) and x not in starts) for x in targets):
        raise MetadataError("invalid aligned branch target")
    return targets


def _field_token(code, instruction, opcode):
    start, op, _, end = instruction
    if op != opcode or end - start != 5:
        raise MetadataError("invalid adjacent field instruction")
    token = _u(code, start + 1, 4)
    if token >> 24 != 4 or token & 0xFFFFFF == 0:
        raise MetadataError("field operand not FieldDef")
    return token


def inspect_module(blob, *, require_interface_memberref):
    meta = _metadata_tables(blob)
    targets = {tok for tok, family in
               meta["target_reference_parent_type_families"].items()
               if family == "icarcom_repository"}
    if require_interface_memberref:
        if len(targets) != 1:
            raise MetadataError("ambiguous interface MemberRef")
        if any(meta["target_reference_signature_contracts"].get(tok) is None or
               meta["target_reference_signature_contracts"][tok]["parameters"] != 1 or
               not meta["target_reference_signature_contracts"][tok]["has_this"]
               for tok in targets):
            raise MetadataError("interface signature contract mismatch")
    elif targets:
        raise MetadataError("repository assembly has unexpected target MemberRef")
    sections, layout = _sections(blob), _table_layout(blob)
    methods = meta["methods"]
    if len(methods) > 100000:
        raise MetadataError("unbounded source MethodDef count")
    bodies, fields = [], set()
    reader_sites = []
    for method in methods.values():
        if not method["rva"]:
            continue
        code = _body(blob, method["rva"], sections)
        ins = _instructions(code)
        bid = len(bodies)
        bodies.append((code, ins, _moresects(blob, method["rva"], sections)))
        for i, (start, op, token, _) in enumerate(ins):
            if op not in (0x28, 0x6F) or token not in targets:
                continue
            if len(reader_sites) >= 100 or i == 0:
                raise MetadataError("target reader bound or adjacency mismatch")
            field = _field_token(code, ins[i - 1], 0x7B)
            fields.add(field)
            reader_sites.append((bid, start))
    counts = {
        "cil_method_bodies_examined": len(bodies),
        "target_getinithw_calls": len(reader_sites),
        "distinct_fielddefs": len(fields),
        "target_stfld_writes": 0,
        "writer_predecessor_arity": {k: {v: 0 for v in ARITIES} for k in KINDS},
        "sink_with_static_direct_branch_entry": {s: 0 for s in SINKS},
        "sink_without_static_direct_branch_entry": {s: 0 for s in SINKS},
        "sink_in_method_with_more_sections": {s: 0 for s in SINKS},
        "sink_in_method_without_more_sections": {s: 0 for s in SINKS},
    }
    branches = [_branch_targets(code, ins) for code, ins, _ in bodies]
    def mark(bid, start, sink):
        more = bodies[bid][2]
        counts["sink_with_static_direct_branch_entry" if start in branches[bid]
               else "sink_without_static_direct_branch_entry"][sink] += 1
        counts["sink_in_method_with_more_sections" if more
               else "sink_in_method_without_more_sections"][sink] += 1
    for bid, start in reader_sites:
        mark(bid, start, "reader")
    for bid, (code, ins, _) in enumerate(bodies):
        for i, inst in enumerate(ins):
            if inst[1] != 0x7D:
                continue
            field = _field_token(code, inst, 0x7D)
            if field not in fields:
                continue
            counts["target_stfld_writes"] += 1
            if counts["target_stfld_writes"] > 10000:
                raise MetadataError("unbounded target writer count")
            kind, arity = "unclassified", "unclassified"
            if i and ins[i - 1][1] in (0x73, 0x6F):
                prev = ins[i - 1]
                if prev[3] - prev[0] != 5:
                    raise MetadataError("invalid predecessor operand width")
                kind = "newobj" if prev[1] == 0x73 else "callvirt"
                arity = _arity(layout, _u(code, prev[0] + 1, 4))
            counts["writer_predecessor_arity"][kind][arity] += 1
            mark(bid, inst[0], "writer")
    if sum(sum(v.values()) for v in counts["writer_predecessor_arity"].values()) != counts["target_stfld_writes"]:
        raise MetadataError("inconsistent writer arity totals")
    for sink, total in (("reader", len(reader_sites)),
                        ("writer", counts["target_stfld_writes"])):
        if (counts["sink_with_static_direct_branch_entry"][sink] +
                counts["sink_without_static_direct_branch_entry"][sink] != total or
            counts["sink_in_method_with_more_sections"][sink] +
                counts["sink_in_method_without_more_sections"][sink] != total):
            raise MetadataError("inconsistent branch entry count")
    return counts


def audit(folder):
    if not folder.is_dir() or folder.is_symlink():
        raise MetadataError("invalid source folder")
    files, seen = {}, 0
    def on_error(_):
        raise MetadataError("original source walk failed")
    for root, dirs, names in os.walk(folder, followlinks=False, onerror=on_error):
        dirs[:] = [x for x in dirs if not (Path(root) / x).is_symlink()]
        for name in names:
            seen += 1
            if seen > MAX_FILES_WALK:
                raise MetadataError("bounded original source walk exceeded")
            key = name.casefold()
            if key in EXPECTED:
                path = Path(root) / name
                if key in files or path.is_symlink() or not path.is_file():
                    raise MetadataError("ambiguous original DLL source")
                files[key] = path
    if set(files) != set(EXPECTED):
        raise MetadataError("missing pinned original source")
    results = []
    for key, (name, digest) in sorted(EXPECTED.items()):
        p = files[key]
        n = p.stat().st_size
        if n < 128 or n > MAX_FILE:
            raise MetadataError("invalid original DLL length")
        with p.open("rb") as stream:
            raw = stream.read(MAX_FILE + 1)
        if len(raw) != n or p.stat().st_size != n or hashlib.sha256(raw).hexdigest() != digest:
            raise MetadataError("source SHA256 mismatch")
        results.append({"module_basename": name, "counts": inspect_module(
            raw, require_interface_memberref=(key != "bizservices.carcom.db.dll"))})
    return {
        "schema_version": "virtualcar-vida-original-2015a-writer-arity-branch-entry-v1",
        "status": "owner_original_sha_pinned_writer_arity_direct_branch_census",
        "results": results,
        "source_writes_performed": False,
        "original_assemblies_loaded_or_executed": False,
        "original_names_tokens_IL_signatures_values_or_paths_exported": False,
        "no_direct_branch_proves_stack_producer_consumer": False,
        "more_sections_flag_proves_eh_fully_decoded": False,
        "arity_proves_argument_values": False,
        "original_profile_identifiers_proven": False,
        "original_vida_2015a_generic_profile_inheritance_verified": False,
        "d2_baudrate_verified": False,
        "original_vida_readvin_accepted": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Owner-only SHA-pinned VIDA 2015A static writer arity and branch-entry counts")
    p.add_argument("--folder", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        print(json.dumps(audit(args.folder), sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
