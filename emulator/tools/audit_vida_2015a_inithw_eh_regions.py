#!/usr/bin/env python3
"""Read-only VIDA 2015A: count EH regions around original GetInitHwSettings calls.

Reads ONLY three SHA256-pinned original DLLs as bytes. Parses ECMA-335
CorILMethod_Sect EH clauses for methods containing the six static target
call sites. Reports count categories, never IL offsets/tokens/field names,
catch type names, original code, paths or profile values.

EH region membership is not CFG, stack or runtime argument provenance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from audit_vida_2015a_inithw_metadata import EXPECTED, MAX_FILE, MAX_FILES_WALK, MetadataError, _u
from audit_vida_2015a_inithw_il_calls import _metadata_tables, _sections, _body, _rva_to_file
from audit_vida_2015a_inithw_callsite_adjacent import _instructions
from audit_vida_2015a_inithw_stack_boundaries import _field_token

MAX_SECTIONS = 16
MAX_CLAUSES = 4096
EH_KINDS = {0: "catch", 1: "filter", 2: "finally", 4: "fault"}
EH_COUNTERS = ("catch", "filter", "finally", "fault")


def _eh_clauses(blob: bytes, rva: int, sections: list, code: bytes,
                starts: set[int]) -> tuple[list[tuple], int, int, int]:
    """Private clauses: (kind, try_start, try_end, handler_start, handler_end, filter_off).
    Return clauses, EH small sections, EH fat sections, non-EH section count.
    """
    at = _rva_to_file(blob, rva, 1, sections)
    flavor = blob[at] & 3
    if flavor == 2:
        return [], 0, 0, 0
    if flavor != 3:
        raise MetadataError("unexpected original IL method header")
    _rva_to_file(blob, rva, 12, sections)
    flags = _u(blob, at, 2)
    header_bytes = (flags >> 12) * 4
    if not 12 <= header_bytes <= 32:
        raise MetadataError("fat IL method header size out of bounds")
    size = _u(blob, at + 4, 4)
    if size != len(code):
        raise MetadataError("source MethodDef code size changed")
    if not flags & 8:
        return [], 0, 0, 0
    section_pos = (at + header_bytes + len(code) + 3) & ~3
    clauses, small, fat, other = [], 0, 0, 0
    for _ in range(MAX_SECTIONS):
        rel = section_pos - at
        if _rva_to_file(blob, rva + rel, 4, sections) != section_pos:
            raise MetadataError("original IL section misaligned to PE RVA")
        kind = blob[section_pos]
        is_fat = bool(kind & 0x40)
        more = bool(kind & 0x80)
        section_bytes = (
            int.from_bytes(blob[section_pos + 1:section_pos + 4], "little")
            if is_fat else blob[section_pos + 1]
        )
        if section_bytes < 4:
            raise MetadataError("invalid original IL extra section length")
        if (_rva_to_file(blob, rva + rel, section_bytes, sections) != section_pos):
            raise MetadataError("original IL section not contained in PE")
        if (kind & 0x3F) == 1:  # CorILMethod_Sect_EHTable
            clause_size = 24 if is_fat else 12
            if (section_bytes - 4) % clause_size:
                raise MetadataError("nonintegral EH clause count")
            if is_fat:
                fat += 1
            else:
                small += 1
            for off in range(section_pos + 4, section_pos + section_bytes, clause_size):
                if len(clauses) >= MAX_CLAUSES:
                    raise MetadataError("original EH clause limit exceeded")
                if is_fat:
                    flags_c, tr, tl, hd, hl, extra = (
                        _u(blob, off + i * 4, 4) for i in range(6)
                    )
                else:
                    flags_c = _u(blob, off, 2)
                    tr, tl = _u(blob, off + 2, 2), blob[off + 4]
                    hd, hl = _u(blob, off + 5, 2), blob[off + 7]
                    extra = _u(blob, off + 8, 4)
                if flags_c not in EH_KINDS:
                    raise MetadataError("unsupported original EH clause flags")
                tr_end, hd_end = tr + tl, hd + hl
                if tl == 0 or hl == 0 or tr_end > len(code) or hd_end > len(code):
                    raise MetadataError("original EH range outside IL body")
                if any(x not in starts for x in (tr, tr_end, hd, hd_end)):
                    raise MetadataError("original EH range not instruction aligned")
                filter_off = None
                if flags_c == 1:
                    filter_off = extra
                    if filter_off not in starts or filter_off >= hd:
                        raise MetadataError("original EH filter range invalid")
                clauses.append((EH_KINDS[flags_c], tr, tr_end, hd, hd_end, filter_off))
        else:
            other += 1
        section_pos = (section_pos + section_bytes + 3) & ~3
        if not more:
            break
    else:
        raise MetadataError("too many chained original IL sections")
    return clauses, small, fat, other


def _reader_membership(start: int, clauses: list[tuple]) -> tuple[bool, bool, bool, bool]:
    in_try = any(tr <= start < te for _, tr, te, _, _, _ in clauses)
    in_handler = any(hd <= start < he for _, _, _, hd, he, _ in clauses)
    in_filter = any(f is not None and f <= start < hd for _, _, _, hd, _, f in clauses)
    return in_try, in_handler, in_filter, not (in_try or in_handler or in_filter)


def inspect_module(blob: bytes, *, require_interface_memberref: bool) -> dict:
    md = _metadata_tables(blob)
    targets = {t for t, f in md["target_reference_parent_type_families"].items()
               if f == "icarcom_repository"}
    if require_interface_memberref:
        if len(targets) != 1:
            raise MetadataError("target original interface MemberRef is not unique")
        if any(md["target_reference_signature_contracts"].get(t) is None or
               md["target_reference_signature_contracts"][t]["parameters"] != 1 or
               not md["target_reference_signature_contracts"][t]["has_this"]
               for t in targets):
            raise MetadataError("unexpected original GetInitHwSettings signature")
    elif targets:
        raise MetadataError("repository module has unexpected target MemberRef")
    counts = {
        "cil_method_bodies_examined": 0,
        "target_getinithw_calls": 0,
        "target_calling_methods_with_extra_sections": 0,
        "target_calling_methods_without_extra_sections": 0,
        "small_eh_sections": 0,
        "fat_eh_sections": 0,
        "other_extra_sections": 0,
        "eh_clause_kind_counts": {k: 0 for k in EH_COUNTERS},
        "reader_in_try": 0, "reader_in_handler": 0,
        "reader_in_filter": 0, "reader_outside_eh_regions": 0,
        "reader_in_multiple_eh_regions": 0,
        "reader_ldfld_and_call_cross_eh_membership": 0,
    }
    sections = _sections(blob)
    for method in md["methods"].values():
        if not method["rva"]:
            continue
        counts["cil_method_bodies_examined"] += 1
        code = _body(blob, method["rva"], sections)
        ins = _instructions(code)
        sites = []
        for i, (start, op, token, _) in enumerate(ins):
            if op not in (0x28, 0x6F) or token not in targets:
                continue
            if i == 0:
                raise MetadataError("target original call missing preceding ldfld")
            _field_token(code, ins[i - 1], 0x7B)
            sites.append((ins[i - 1][0], start))
        if not sites:
            continue
        counts["target_getinithw_calls"] += len(sites)
        if counts["target_getinithw_calls"] > 100:
            raise MetadataError("target callsite count outside limit")
        starts = {x[0] for x in ins} | {len(code)}
        clauses, small, fat, other = _eh_clauses(
            blob, method["rva"], sections, code, starts
        )
        counts["small_eh_sections"] += small
        counts["fat_eh_sections"] += fat
        counts["other_extra_sections"] += other
        counts[
            "target_calling_methods_with_extra_sections" if (small + fat + other)
            else "target_calling_methods_without_extra_sections"
        ] += 1
        for kind, *_ in clauses:
            counts["eh_clause_kind_counts"][kind] += 1
        for ldfld_start, call_start in sites:
            call_region = _reader_membership(call_start, clauses)
            fld_region = _reader_membership(ldfld_start, clauses)
            for key, selected in zip(
                ("reader_in_try", "reader_in_handler", "reader_in_filter",
                 "reader_outside_eh_regions"), call_region
            ):
                counts[key] += int(selected)
            counts["reader_in_multiple_eh_regions"] += int(sum(call_region[:3]) > 1)
            counts["reader_ldfld_and_call_cross_eh_membership"] += int(
                fld_region != call_region
            )
    total = counts["target_getinithw_calls"]
    if (counts["reader_outside_eh_regions"] > total or
        any(counts[k] > total for k in
            ("reader_in_try", "reader_in_handler", "reader_in_filter")) or
        counts["reader_ldfld_and_call_cross_eh_membership"] > total):
        raise MetadataError("unreconciled original EH region membership counts")
    return counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise MetadataError("invalid original VIDA folder")
    found, n = {}, 0
    def scan_error(_):
        raise MetadataError("cannot traverse pinned original source")
    for root, dirs, files in os.walk(folder, followlinks=False, onerror=scan_error):
        dirs[:] = [d for d in dirs if not (Path(root) / d).is_symlink()]
        for filename in files:
            n += 1
            if n > MAX_FILES_WALK:
                raise MetadataError("original bounded scan limit exceeded")
            k = filename.casefold()
            if k in EXPECTED:
                p = Path(root) / filename
                if k in found or p.is_symlink() or not p.is_file():
                    raise MetadataError("ambiguous original source binary")
                found[k] = p
    if set(found) != set(EXPECTED):
        raise MetadataError("missing exact SHA-pinned original DLLs")
    results = []
    for k, (name, sha) in sorted(EXPECTED.items()):
        file = found[k]
        size = file.stat().st_size
        if not 128 <= size <= MAX_FILE:
            raise MetadataError("original source DLL size invalid")
        with file.open("rb") as stream:
            raw = stream.read(MAX_FILE + 1)
        if len(raw) != size or file.stat().st_size != size or hashlib.sha256(raw).hexdigest() != sha:
            raise MetadataError("original pinned SHA256 mismatch")
        results.append({"module_basename": name, "counts": inspect_module(
            raw, require_interface_memberref=(k != "bizservices.carcom.db.dll"))})
    return {
        "schema_version": "virtualcar-vida-original-2015a-getinithw-eh-regions-v1",
        "status": "owner_original_source_only_eh_region_counts",
        "results": results,
        "source_writes_performed": False,
        "original_assemblies_loaded_or_executed": False,
        "original_eh_offsets_tokens_types_names_values_or_paths_exported": False,
        "eh_regions_prove_runtime_execution_or_stack_provenance": False,
        "original_profile_identifiers_argument_verified": False,
        "original_vida_2015a_generic_profile_inheritance_verified": False,
        "d2_baudrate_verified": False,
        "original_vida_readvin_accepted": False,
    }


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description="Original VIDA read-only EH region census")
    a.add_argument("--folder", type=Path, required=True)
    opts = a.parse_args(argv)
    try:
        print(json.dumps(audit(opts.folder), indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
