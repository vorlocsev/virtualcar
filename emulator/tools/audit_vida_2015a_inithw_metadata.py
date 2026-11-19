#!/usr/bin/env python3
"""Hash-pinned, stdlib-only CLR TypeDef/MethodDef/MemberRef census for VIDA DLLs.

Reads three specifically pinned original 2015A assemblies as bytes without
loading, executing, disassembling IL, or invoking SQL/VIDA. Separates a real
MethodDef or MemberRef metadata row from an arbitrary string token. NO call
instructions, runtime profile selection, inheritance or D2 bitrate proved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

EXPECTED = {
    "bizservices.carcom.db.dll": (
        "BizServices.CarCom.DB.DLL",
        "a54117e6b2cc97c28bacf5df72f060ee8694de85291194046235bfd85a700be6",
    ),
    "bizservices.vehiclecommprovider.dll": (
        "BizServices.VehicleCommProvider.DLL",
        "763c26d195ee7324fd08d6da1bf7304e0090a7220c29ec46038ae695db5a82e5",
    ),
    "workflow.dll": (
        "Workflow.DLL",
        "ba78b669efea360887d333353451e9411e82004e368b356f74200d8fcb427ebd",
    ),
}
TARGET_METHODS = ("GetInitHwSettings", "GetHwSettings", "vadis_GetHwSettings")
TARGET_TYPE = "CarComRepository"
MAX_FILE = 128 * 1024 * 1024
MAX_FILES_WALK = 30000
MAX_META = 32 * 1024 * 1024
MAX_ROWS = 600000


class MetadataError(ValueError):
    pass


def _u(blob: bytes, offset: int, size: int) -> int:
    if offset < 0 or size not in (1, 2, 4, 8) or offset + size > len(blob):
        raise MetadataError("truncated original PE/CLR metadata")
    return int.from_bytes(blob[offset:offset + size], "little")


def _rva_to_file(blob: bytes, rva: int, size: int,
                 sections: list[tuple[int, int, int, int]]) -> int:
    if size < 1:
        raise MetadataError("invalid RVA size")
    for virt, span, raw, raw_len in sections:
        delta = rva - virt
        if 0 <= delta and delta + size <= span and delta + size <= raw_len:
            if raw + delta + size > len(blob):
                raise MetadataError("invalid PE raw data extent")
            return raw + delta
    raise MetadataError("unmapped CLR RVA")


def _stream_headers(meta: bytes) -> dict[str, bytes]:
    if len(meta) < 24 or meta[:4] != b"BSJB":
        raise MetadataError("missing CLR metadata signature")
    version_len = _u(meta, 12, 4)
    if version_len > 512 or 16 + version_len + 4 > len(meta):
        raise MetadataError("invalid CLR version header")
    pos = (16 + version_len + 3) & ~3
    num = _u(meta, pos + 2, 2)
    pos += 4
    if not 1 <= num <= 12:
        raise MetadataError("unexpected CLR stream count")
    result = {}
    for _ in range(num):
        start = pos
        offset, length = _u(meta, pos, 4), _u(meta, pos + 4, 4)
        pos += 8
        stop = meta.find(b"\x00", pos, min(pos + 64, len(meta)))
        if stop < 0:
            raise MetadataError("unterminated CLR stream name")
        try:
            name = meta[pos:stop].decode("ascii")
        except UnicodeDecodeError as exc:
            raise MetadataError("invalid CLR stream name") from exc
        pos = (stop + 4) & ~3
        if pos - start > 80 or offset + length > len(meta) or name in result:
            raise MetadataError("invalid CLR stream extent")
        result[name] = meta[offset:offset + length]
    if "#Strings" not in result or ("#~" not in result and "#-" not in result):
        raise MetadataError("required CLR metadata streams absent")
    return result


def _cli_metadata(blob: bytes) -> dict[str, bytes]:
    if len(blob) < 0x100 or blob[:2] != b"MZ":
        raise MetadataError("not an MS PE binary")
    pe = _u(blob, 0x3C, 4)
    if pe + 24 > len(blob) or blob[pe:pe + 4] != b"PE\x00\x00":
        raise MetadataError("invalid PE signature")
    coff = pe + 4
    nsections, opt_size = _u(blob, coff + 2, 2), _u(blob, coff + 16, 2)
    if not 1 <= nsections <= 96:
        raise MetadataError("invalid PE section count")
    opt = coff + 20
    magic = _u(blob, opt, 2)
    dir_start = opt + (96 if magic == 0x10B else 112 if magic == 0x20B else -10000)
    if dir_start < opt or dir_start + 15 * 8 > opt + opt_size:
        raise MetadataError("missing PE CLI data directory")
    rva, _ = _u(blob, dir_start + 14 * 8, 4), _u(blob, dir_start + 14 * 8 + 4, 4)
    sections = []
    sections_start = opt + opt_size
    for i in range(nsections):
        s = sections_start + 40 * i
        virtual_size = _u(blob, s + 8, 4)
        virtual_address = _u(blob, s + 12, 4)
        raw_size = _u(blob, s + 16, 4)
        raw_ptr = _u(blob, s + 20, 4)
        sections.append((virtual_address, max(virtual_size, raw_size), raw_ptr, raw_size))
    cli = _rva_to_file(blob, rva, 16, sections)
    md_rva, md_size = _u(blob, cli + 8, 4), _u(blob, cli + 12, 4)
    if not 16 <= md_size <= MAX_META:
        raise MetadataError("unexpected CLR metadata size")
    md_off = _rva_to_file(blob, md_rva, md_size, sections)
    return _stream_headers(blob[md_off:md_off + md_size])


def parse_metadata(blob: bytes) -> dict:
    streams = _cli_metadata(blob)
    tables = streams.get("#~", streams.get("#-"))
    strings = streams["#Strings"]
    if tables is None or len(tables) < 24:
        raise MetadataError("invalid CLR metadata tables")
    heap_sizes = _u(tables, 6, 1)
    valid = _u(tables, 8, 8)
    counts = {}
    pos = 24
    for tid in range(64):
        if valid & (1 << tid):
            cnt = _u(tables, pos, 4)
            pos += 4
            if cnt > MAX_ROWS:
                raise MetadataError("oversized CLR metadata table")
            counts[tid] = cnt
    def index(table_id: int) -> int:
        return 4 if counts.get(table_id, 0) >= (1 << 16) else 2
    def coded(table_ids: tuple[int, ...], bits: int) -> int:
        return 4 if max(counts.get(t, 0) for t in table_ids) >= (1 << (16 - bits)) else 2
    str_size = 4 if heap_sizes & 1 else 2
    guid_size = 4 if heap_sizes & 2 else 2
    blob_size = 4 if heap_sizes & 4 else 2
    tdor = coded((2, 1, 27), 2)
    row_sizes = {
        0: 2 + str_size + 3 * guid_size,
        1: coded((0, 26, 35, 1), 2) + str_size * 2,
        2: 4 + str_size * 2 + tdor + index(4) + index(6),
        3: index(4),
        4: 2 + str_size + blob_size,
        5: index(6),
        6: 4 + 2 + 2 + str_size + blob_size + index(8),
        7: index(8),
        8: 2 + 2 + str_size,
        9: index(2) + tdor,
        10: coded((2, 1, 26, 6, 27), 3) + str_size + blob_size,
    }
    offsets = {}
    for tid in range(11):
        if tid in counts:
            start, end = pos, pos + row_sizes[tid] * counts[tid]
            if end > len(tables):
                raise MetadataError("truncated CLR metadata rows")
            offsets[tid] = start
            pos = end

    def name_at(offset: int) -> str:
        if offset <= 0 or offset >= len(strings):
            raise MetadataError("invalid CLR name index")
        end = strings.find(b"\x00", offset)
        if end < 0 or end - offset > 512:
            raise MetadataError("invalid CLR name extent")
        try:
            return strings[offset:end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MetadataError("invalid CLR name encoding") from exc

    def name_from_row(tid: int, i: int, col_offset: int) -> str:
        row = offsets[tid] + row_sizes[tid] * i
        return name_at(_u(tables, row + col_offset, str_size))

    typed_methods = []
    if counts.get(5, 0):
        raise MetadataError("MethodPtr metadata tables are unsupported")
    for i in range(counts.get(2, 0)):
        row = offsets[2] + row_sizes[2] * i
        type_name = name_from_row(2, i, 4)
        # MethodList follows Flags, TypeName, Namespace, Extends, FieldList.
        method_list_col = 4 + str_size * 2 + tdor + index(4)
        first = _u(tables, row + method_list_col, index(6))
        typed_methods.append((type_name, first))
    mtotal = counts.get(6, 0)
    if mtotal and not typed_methods:
        raise MetadataError("methods without declaring types")
    if typed_methods:
        first_positions = [first for _, first in typed_methods]
        if first_positions != sorted(first_positions) or any(
            i < 1 or i > mtotal + 1 for i in first_positions
        ):
            raise MetadataError("invalid TypeDef method boundaries")

    def owner(mindex: int) -> str:
        for j, (type_name, first) in enumerate(typed_methods):
            end = typed_methods[j + 1][1] if j + 1 < len(typed_methods) else mtotal + 1
            if first <= mindex < end:
                return type_name
        raise MetadataError("unresolved MethodDef declaring type")

    methods = {x: 0 for x in TARGET_METHODS}
    declared_by_repository = {x: 0 for x in TARGET_METHODS}
    refs = {x: 0 for x in TARGET_METHODS}
    for i in range(mtotal):
        method = name_from_row(6, i, 8)
        if method in methods:
            methods[method] += 1
            if owner(i + 1) == TARGET_TYPE:
                declared_by_repository[method] += 1
    for i in range(counts.get(10, 0)):
        member = name_from_row(10, i, coded((2, 1, 26, 6, 27), 3))
        if member in refs:
            refs[member] += 1
    return {
        "carcom_repository_typedef_count": sum(t[0] == TARGET_TYPE for t in typed_methods),
        "target_methoddef_counts": methods,
        "target_methoddefs_in_carcom_repository": declared_by_repository,
        "target_memberref_name_counts": refs,
    }


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise MetadataError("invalid original VIDA folder")
    found = {}
    visited = 0
    def fail_walk(err):
        raise MetadataError("unreadable original directory")
    for root, dirs, files in os.walk(folder, followlinks=False, onerror=fail_walk):
        dirs[:] = [x for x in dirs if not (Path(root) / x).is_symlink()]
        for name in files:
            visited += 1
            if visited > MAX_FILES_WALK:
                raise MetadataError("bounded directory scan exceeded")
            key = name.casefold()
            if key not in EXPECTED:
                continue
            file = Path(root) / name
            if file.is_symlink() or not file.is_file() or key in found:
                raise MetadataError("ambiguous pinned original assembly path")
            found[key] = file
    if set(found) != set(EXPECTED):
        raise MetadataError("one or more pinned original assembly files missing")
    matches = []
    for key in sorted(EXPECTED):
        basename, expected_hash = EXPECTED[key]
        file = found[key]
        stat_before = file.stat()
        if stat_before.st_size < 128 or stat_before.st_size > MAX_FILE:
            raise MetadataError("original assembly size outside verified scope")
        with file.open("rb") as handle:
            data = handle.read(MAX_FILE + 1)
        if len(data) != stat_before.st_size or file.stat().st_size != stat_before.st_size:
            raise MetadataError("original assembly source changed during read")
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected_hash:
            raise MetadataError("original assembly SHA256 does not match owner pin")
        result = parse_metadata(data)
        matches.append({"module_basename": basename, "sha256": digest, **result})
    return {
        "schema_version": "virtualcar-vida-original-carcom-methoddef-memberref-v1",
        "status": "owner_original_three_sha_pinned_cli_metadata_only",
        "pinned_original_assemblies_verified": 3,
        "results": matches,
        "original_binary_contents_paths_or_private_values_emitted": False,
        "source_writes_performed": False,
        "assemblies_loaded_or_executed": False,
        "il_call_instructions_inspected": False,
        "memberref_name_proves_actual_callsite": False,
        "original_vida_2015a_profile_list_callers_verified": False,
        "original_vida_2015a_inheritance_verified": False,
        "d2_baudrate_verified": False,
        "original_vida_readvin_accepted": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only original pinned VIDA CLR metadata")
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
