#!/usr/bin/env python3
"""Owner-private original VIDA 2015A interface MethodDef / MethodImpl census.

All original input is immutable and SHA-256 pinned. Only fixed numerical
classifications leave the process. Neither an explicit MethodImpl nor a
name/signature compatible implicit implementation proves runtime invocation,
the caller's profileIdentifiers list, inherited InitHw, D2 baud, or ReadVin.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from audit_vida_2015a_inithw_metadata import (
    EXPECTED, MAX_FILE, MAX_FILES_WALK, MetadataError,
)
from audit_vida_2015a_inithw_assembly_identity import (
    _table_layout, _repository_interface, _def_type,
)

TARGET = "GetInitHwSettings"


def _method_rows(meta: dict, type_index: int) -> list[dict]:
    u, row, st = meta["u"], meta["row"], meta["strsize"]
    tdor = meta["typedeforref_size"]
    counts = meta["counts"]
    ntypes = counts.get(2, 0)
    nmethods = counts.get(6, 0)
    if not 1 <= type_index <= ntypes:
        raise MetadataError("invalid local type index")
    field_width = 4 if counts.get(4, 0) >= 65536 else 2
    method_width = 4 if nmethods >= 65536 else 2
    def _start(i):
        return u(row(2, i) + 4 + st * 2 + tdor + field_width, method_width)
    first = _start(type_index)
    last = _start(type_index + 1) if type_index < ntypes else nmethods + 1
    if not 1 <= first <= last <= nmethods + 1:
        raise MetadataError("invalid original TypeDef MethodList range")
    result = []
    for mid in range(first, last):
        p = row(6, mid)
        name = meta["typename"](u(p + 8, st))
        if name != TARGET:
            continue
        flags = u(p + 6, 2)
        signature_index = u(p + 8 + st, meta["blobsize"])
        result.append({
            "method_row_private": mid,
            "signature_private": meta["blob"](signature_index),
            "public": (flags & 0x0007) == 0x0006,
            "static": bool(flags & 0x0010),
            "virtual": bool(flags & 0x0040),
            "newslot": bool(flags & 0x0100),
            "abstract": bool(flags & 0x0400),
            "specialname": bool(flags & 0x0800),
        })
    return result


def _types(meta):
    if _repository_interface(meta)[1] != "local_typedef":
        raise MetadataError("expected original local ICarComRepository TypeDef")
    repo = [i for i in range(1, meta["counts"].get(2, 0) + 1)
            if _def_type(meta, i)[1] == "CarComRepository"]
    interface = [i for i in range(1, meta["counts"].get(2, 0) + 1)
                 if _def_type(meta, i)[1] == "ICarComRepository"]
    if len(repo) != 1 or len(interface) != 1:
        raise MetadataError("ambiguous local repository/interface TypeDef")
    return repo[0], interface[0]


def _methodimpl_details(meta, repository_type: int,
                        repository_mid: int, interface_mid: int):
    counts = {
        "repository_methodimpl_rows_total": 0,
        "repository_methodimpl_body_repository_target": 0,
        "repository_methodimpl_declaration_interface_target": 0,
        "repository_methodimpl_exact_target_pair": 0,
        "repository_methodimpl_other_or_unresolved_rows": 0,
    }
    u, row = meta["u"], meta["row"]
    tsize = meta["typedef_index_size"]
    nmethods = meta["counts"].get(6, 0)
    nrefs = meta["counts"].get(10, 0)
    coded_size = 4 if max(nmethods, nrefs) >= (1 << 15) else 2
    for index in range(1, meta["counts"].get(25, 0) + 1):
        p = row(25, index)
        owner = u(p, tsize)
        if owner != repository_type:
            continue
        counts["repository_methodimpl_rows_total"] += 1
        body = u(p + tsize, coded_size)
        decl = u(p + tsize + coded_size, coded_size)
        btag, bindex = body & 1, body >> 1
        dtag, dindex = decl & 1, decl >> 1
        if (bindex == 0 or dindex == 0 or
                (btag == 0 and bindex > nmethods) or
                (btag == 1 and bindex > nrefs) or
                (dtag == 0 and dindex > nmethods) or
                (dtag == 1 and dindex > nrefs)):
            raise MetadataError("invalid original MethodImpl coded token")
        body_match = btag == 0 and bindex == repository_mid
        decl_match = dtag == 0 and dindex == interface_mid
        counts["repository_methodimpl_body_repository_target"] += int(body_match)
        counts["repository_methodimpl_declaration_interface_target"] += int(decl_match)
        counts["repository_methodimpl_exact_target_pair"] += int(body_match and decl_match)
        counts["repository_methodimpl_other_or_unresolved_rows"] += int(
            not body_match and not decl_match
        )
    return counts


def inspect_metadata(meta: dict) -> dict:
    repo_index, interface_index = _types(meta)
    repos = _method_rows(meta, repo_index)
    ifaces = _method_rows(meta, interface_index)
    if len(repos) != 1 or len(ifaces) != 1:
        raise MetadataError("original GetInitHwSettings declarations not unique")
    repo, iface = repos[0], ifaces[0]
    counts = {
        "repository_typedef_candidates": 1,
        "interface_typedef_candidates": 1,
        "repository_getinithw_methoddef_candidates": 1,
        "interface_getinithw_methoddef_candidates": 1,
        "same_module_raw_method_signature_equal": int(
            repo["signature_private"] == iface["signature_private"]
        ),
        "same_module_raw_method_signature_different": int(
            repo["signature_private"] != iface["signature_private"]
        ),
        "repository_method_public": int(repo["public"]),
        "repository_method_instance": int(not repo["static"]),
        "repository_method_virtual": int(repo["virtual"]),
        "repository_method_newslot": int(repo["newslot"]),
        "repository_method_abstract": int(repo["abstract"]),
        "interface_method_public": int(iface["public"]),
        "interface_method_instance": int(not iface["static"]),
        "interface_method_virtual": int(iface["virtual"]),
        "interface_method_abstract": int(iface["abstract"]),
    }
    counts.update(_methodimpl_details(
        meta, repo_index, repo["method_row_private"], iface["method_row_private"]
    ))
    return counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise MetadataError("invalid original VIDA source folder")
    found = {}
    visited = 0
    def _on_error(_):
        raise MetadataError("unreadable original VIDA source folder")
    for root, dirs, files in os.walk(folder, topdown=True, followlinks=False, onerror=_on_error):
        dirs[:] = [x for x in dirs if not (Path(root) / x).is_symlink()]
        for filename in files:
            visited += 1
            if visited > MAX_FILES_WALK:
                raise MetadataError("original file discovery limit exceeded")
            key = filename.casefold()
            if key not in EXPECTED:
                continue
            candidate = Path(root) / filename
            if key in found or candidate.is_symlink() or not candidate.is_file():
                raise MetadataError("ambiguous exact original assembly")
            found[key] = candidate
    if set(found) != set(EXPECTED):
        raise MetadataError("missing original SHA-pinned assemblies")
    metadata = {}
    for key, (_, digest) in sorted(EXPECTED.items()):
        file = found[key]
        n = file.stat().st_size
        if not 128 <= n <= MAX_FILE:
            raise MetadataError("original DLL outside bounded size")
        with file.open("rb") as stream:
            source = stream.read(MAX_FILE + 1)
        if len(source) != n or hashlib.sha256(source).hexdigest() != digest or file.stat().st_size != n:
            raise MetadataError("original DLL SHA256 does not match exact source")
        metadata[key] = _table_layout(source)
    return {
        "schema_version": "virtualcar-vida-original-2015a-carcom-methodimpl-v1",
        "status": "owner_original_sha_pinned_static_methodimpl_and_implicit_candidate_counts_only",
        "counts": inspect_metadata(metadata["bizservices.carcom.db.dll"]),
        "source_writes_performed": False,
        "original_assemblies_loaded_or_executed": False,
        "original_methods_signatures_tokens_types_or_paths_exported": False,
        "implicit_interface_dispatch_verified": False,
        "explicit_methodimpl_proves_runtime_execution": False,
        "memberref_dispatch_from_caller_verified": False,
        "caller_profile_identifiers_argument_verified": False,
        "original_vida_2015a_generic_profile_inheritance_verified": False,
        "d2_baudrate_verified": False,
        "original_vida_readvin_accepted": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Owner-only original VIDA static MethodImpl candidate counts")
    parser.add_argument("--folder", required=True, type=Path)
    opts = parser.parse_args(argv)
    try:
        print(json.dumps(audit(opts.folder), indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
