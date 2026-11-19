#!/usr/bin/env python3
"""Owner-private VIDA 2015A ICarComRepository assembly reference identity census.

The three original DLLs are hash-pinned and only read as bytes. Original
assembly names, versions, culture, public keys, type namespaces and token
indices stay IN MEMORY; the output contains only fixed aggregate counts.

Equality of original AssemblyRef (name/version/culture/flags/key bytes) is
stronger than name or signature shape, but does NOT prove CLR runtime binding,
interface method signature equality, execution or selected profile settings.
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
    _cli_metadata, _u,
)
from audit_vida_2015a_inithw_il_calls import _compressed_uint

MAX_ASSEMBLY_REFS = 10000
MAX_BLOB_SIZE = 16384
MAX_NAME = 512


def _table_layout(blob: bytes):
    streams = _cli_metadata(blob)
    tables = streams.get("#~", streams.get("#-"))
    if tables is None or len(tables) < 24:
        raise MetadataError("original CLR tables missing")
    strings = streams["#Strings"]
    blob_heap = streams.get("#Blob")
    if blob_heap is None:
        raise MetadataError("CLR Blob stream missing")
    valid, heaps, pos = _u(tables, 8, 8), _u(tables, 6, 1), 24
    counts = {}
    for tid in range(64):
        if valid & (1 << tid):
            n = _u(tables, pos, 4)
            pos += 4
            if n > MAX_ROWS:
                raise MetadataError("unbounded original CLR table")
            counts[tid] = n

    def idx(tid):
        return 4 if counts.get(tid, 0) >= 65536 else 2

    def coded(tids, bits):
        return 4 if max((counts.get(t, 0) for t in tids), default=0) >= 1 << (16 - bits) else 2

    st = 4 if heaps & 1 else 2
    gd = 4 if heaps & 2 else 2
    bl = 4 if heaps & 4 else 2
    tdor = coded((2, 1, 27), 2)
    rs = coded((0, 26, 35, 1), 2)
    # ECMA-335 II.22 metadata table row layouts through AssemblyRef (0x23).
    sizes = {
        0: 2 + st + 3 * gd,
        1: rs + 2 * st,
        2: 4 + 2 * st + tdor + idx(4) + idx(6),
        3: idx(4),
        4: 2 + st + bl,
        5: idx(6),
        6: 8 + st + bl + idx(8),
        7: idx(8),
        8: 4 + st,
        9: idx(2) + tdor,
        10: coded((2, 1, 26, 6, 27), 3) + st + bl,
        11: 2 + coded((4, 8, 23), 2) + bl,
        12: coded((6, 4, 1, 2, 8, 9, 10, 0, 14, 23, 20,
                   17, 26, 27, 32, 35, 38, 39, 40, 42, 44, 43), 5)
            + coded((6, 10), 3) + bl,
        13: coded((4, 8), 1) + bl,
        14: 2 + coded((2, 6, 32), 2) + bl,
        15: 6 + idx(2),
        16: 4 + idx(4),
        17: bl,
        18: idx(2) + idx(20),
        19: idx(20),
        20: 2 + st + tdor,
        21: idx(2) + idx(23),
        22: idx(23),
        23: 2 + st + bl,
        24: 2 + idx(6) + coded((20, 23), 1),
        25: idx(2) + 2 * coded((6, 10), 1),
        26: st,
        27: bl,
        28: 2 + coded((4, 6), 1) + st + idx(26),
        29: 4 + idx(4),
        30: 8,
        31: 4,
        32: 16 + bl + 2 * st,
        33: 4,
        34: 12,
        35: 12 + 2 * bl + 2 * st,
    }
    offsets = {}
    for tid in range(36):
        if counts.get(tid, 0):
            end = pos + sizes[tid] * counts[tid]
            if end > len(tables):
                raise MetadataError("incomplete original CLR table layout")
            offsets[tid] = pos
            pos = end

    def row(tid, num):
        if not 1 <= num <= counts.get(tid, 0) or tid not in offsets:
            raise MetadataError("invalid original CLR row reference")
        return offsets[tid] + sizes[tid] * (num - 1)

    def name(index):
        if not index or index >= len(strings):
            raise MetadataError("invalid original CLR string index")
        end = strings.find(b"\x00", index)
        if end == -1 or end - index > MAX_NAME:
            raise MetadataError("invalid original CLR string extent")
        try:
            return strings[index:end].decode("utf-8")
        except UnicodeDecodeError as ex:
            raise MetadataError("invalid original CLR string encoding") from ex

    def blob_at(index):
        if index == 0:
            return b""
        n, start = _compressed_uint(blob_heap, index)
        if n > MAX_BLOB_SIZE or start + n > len(blob_heap):
            raise MetadataError("bounded original CLR blob missing")
        return blob_heap[start:start + n]

    return {
        "table": tables, "counts": counts, "row": row,
        "strsize": st, "blobsize": bl, "refscope_size": rs,
        "typedeforref_size": tdor, "typename": name,
        "blob": blob_at, "u": lambda p, sz: _u(tables, p, sz),
        "typedef_index_size": idx(2),
        "memberref_parent_size": coded((2, 1, 26, 6, 27), 3),
    }


def _ref_type(meta, index):
    u, row, st, rs = meta["u"], meta["row"], meta["strsize"], meta["refscope_size"]
    p = row(1, index)
    scope = u(p, rs)
    name = meta["typename"](u(p + rs, st))
    ns_idx = u(p + rs + st, st)
    ns = meta["typename"](ns_idx) if ns_idx else ""
    return {"type": (ns, name), "scope": (scope & 3, scope >> 2)}


def _def_type(meta, index):
    u, p, st = meta["u"], meta["row"](2, index), meta["strsize"]
    name = meta["typename"](u(p + 4, st))
    ns_idx = u(p + 4 + st, st)
    return (meta["typename"](ns_idx) if ns_idx else "", name)


def _assembly_ref(meta, index):
    u, p, st, bl = meta["u"], meta["row"](35, index), meta["strsize"], meta["blobsize"]
    version = tuple(u(p + i * 2, 2) for i in range(4))
    flags = u(p + 8, 4)
    key_blob = meta["blob"](u(p + 12, bl))
    name = meta["typename"](u(p + 12 + bl, st))
    culture_idx = u(p + 12 + bl + st, st)
    culture = meta["typename"](culture_idx) if culture_idx else ""
    return (name.casefold(), version, culture.casefold(), flags, key_blob)


def _repository_interface(meta):
    u, row = meta["u"], meta["row"]
    candidates = set()
    for i in range(1, meta["counts"].get(2, 0) + 1):
        if _def_type(meta, i)[1] == "CarComRepository":
            candidates.add(i)
    if len(candidates) != 1:
        raise MetadataError("ambiguous original repository TypeDef")
    results = []
    for i in range(1, meta["counts"].get(9, 0) + 1):
        p = row(9, i)
        owner = u(p, meta["typedef_index_size"])
        coded = u(p + meta["typedef_index_size"], meta["typedeforref_size"])
        tag, index = coded & 3, coded >> 2
        if owner not in candidates or not index or tag not in (0, 1):
            continue
        if tag == 0:
            type_identity = _def_type(meta, index)
            scope_kind, assembly_identity = "local_typedef", None
        else:
            typeref = _ref_type(meta, index)
            type_identity = typeref["type"]
            scope_tag, scope_index = typeref["scope"]
            scope_kind = "assemblyref" if scope_tag == 2 and scope_index else "other_scope"
            assembly_identity = _assembly_ref(meta, scope_index) if scope_kind == "assemblyref" else None
        if type_identity[1] == "ICarComRepository":
            results.append((type_identity, scope_kind, assembly_identity))
    if len(results) != 1:
        raise MetadataError("original repository interface reference is not unique")
    return results[0]


def _caller_interface_memberrefs(meta):
    u, row = meta["u"], meta["row"]
    found = []
    for i in range(1, meta["counts"].get(10, 0) + 1):
        p = row(10, i)
        parent_coded = u(p, meta["memberref_parent_size"])
        name = meta["typename"](u(p + meta["memberref_parent_size"], meta["strsize"]))
        if name != "GetInitHwSettings":
            continue
        parent_tag, index = parent_coded & 7, parent_coded >> 3
        if parent_tag != 1 or index == 0:
            continue
        ref = _ref_type(meta, index)
        if ref["type"][1] != "ICarComRepository":
            continue
        scope_tag, scope_index = ref["scope"]
        kind = "assemblyref" if scope_tag == 2 and scope_index else "other_scope"
        assembly_identity = _assembly_ref(meta, scope_index) if kind == "assemblyref" else None
        found.append((ref["type"], kind, assembly_identity))
    if len(found) != 1:
        raise MetadataError("original interface caller MemberRef is not unique")
    return found[0]


def _compare_private(metadata):
    repo = _repository_interface(metadata["bizservices.carcom.db.dll"])
    callers = [
        _caller_interface_memberrefs(metadata["bizservices.vehiclecommprovider.dll"]),
        _caller_interface_memberrefs(metadata["workflow.dll"]),
    ]
    counts = {
        "repository_interfaceimpl_candidates": 1,
        "caller_interface_memberref_candidates": len(callers),
        "repository_interface_scope_assemblyref": int(repo[1] == "assemblyref"),
        "repository_interface_scope_local_typedef": int(repo[1] == "local_typedef"),
        "repository_interface_scope_other": int(repo[1] == "other_scope"),
        "caller_interface_scope_assemblyref": 0,
        "caller_interface_scope_other": 0,
        "stored_full_typename_equal": 0,
        "stored_full_typename_different": 0,
        "stored_assemblyref_identity_equal": 0,
        "stored_assemblyref_identity_different": 0,
        "stored_assemblyref_identity_not_comparable": 0,
    }
    for caller in callers:
        counts["caller_interface_scope_assemblyref" if caller[1] == "assemblyref"
               else "caller_interface_scope_other"] += 1
        counts["stored_full_typename_equal" if caller[0] == repo[0]
               else "stored_full_typename_different"] += 1
        if repo[1] != "assemblyref" or caller[1] != "assemblyref":
            counts["stored_assemblyref_identity_not_comparable"] += 1
        else:
            counts["stored_assemblyref_identity_equal" if caller[2] == repo[2]
                   else "stored_assemblyref_identity_different"] += 1
    if (
        counts["caller_interface_scope_assemblyref"] + counts["caller_interface_scope_other"] != 2 or
        counts["stored_full_typename_equal"] + counts["stored_full_typename_different"] != 2 or
        counts["stored_assemblyref_identity_equal"] +
        counts["stored_assemblyref_identity_different"] +
        counts["stored_assemblyref_identity_not_comparable"] != 2
    ):
        raise MetadataError("unreconciled CLR assembly reference comparison")
    return counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise MetadataError("invalid owner-original VIDA folder")
    located, nfiles = {}, 0
    def walk_error(_):
        raise MetadataError("original source folder unreadable")
    for directory, subdirs, filenames in os.walk(folder, topdown=True, followlinks=False, onerror=walk_error):
        subdirs[:] = [x for x in subdirs if not (Path(directory) / x).is_symlink()]
        for filename in filenames:
            nfiles += 1
            if nfiles > MAX_FILES_WALK:
                raise MetadataError("source file count limit exceeded")
            name = filename.casefold()
            if name not in EXPECTED:
                continue
            p = Path(directory) / filename
            if name in located or p.is_symlink() or not p.is_file():
                raise MetadataError("duplicate or unsafe pinned original DLL")
            located[name] = p
    if set(located) != set(EXPECTED):
        raise MetadataError("three original pinned DLLs not found")
    private = {}
    for key, (_, expected_sha) in sorted(EXPECTED.items()):
        file = located[key]
        size = file.stat().st_size
        if not 128 <= size <= MAX_FILE:
            raise MetadataError("original file size outside scope")
        with file.open("rb") as stream:
            data = stream.read(MAX_FILE + 1)
        if (len(data) != size or file.stat().st_size != size or
                hashlib.sha256(data).hexdigest() != expected_sha):
            raise MetadataError("original file SHA256 mismatch")
        private[key] = _table_layout(data)
    return {
        "schema_version": "virtualcar-vida-original-2015a-getinithw-assemblyrefs-v1",
        "status": "owner_private_sha_pinned_original_assemblyref_equality_counts_only",
        "counts": _compare_private(private),
        "source_writes_performed": False,
        "original_assemblies_loaded_or_executed": False,
        "original_assembly_names_versions_keys_typenames_or_paths_emitted": False,
        "assemblyref_tuple_equality_proves_loaded_assembly_identity": False,
        "assemblyref_tuple_equality_proves_interface_method_dispatch": False,
        "original_methodimpl_dispatch_verified": False,
        "original_vida_2015a_profile_list_proven": False,
        "original_vida_2015a_generic_profile_inheritance_verified": False,
        "d2_baudrate_verified": False,
        "original_vida_readvin_accepted": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Owner-only original VIDA static CLR AssemblyRef identity counts")
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
