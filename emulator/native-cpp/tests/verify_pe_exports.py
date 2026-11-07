#!/usr/bin/env python3
"""Verify a locally built M3 Windows DLL's PE machine and exact 14 exports.

Pure stdlib, no execution, no external upload, no source-car information.
This is an ABI gate, NOT working J2534 transport certification.
"""
from __future__ import annotations

from pathlib import Path
import struct
import sys

EXPORTS = {
    "PassThruOpen", "PassThruClose", "PassThruConnect", "PassThruDisconnect",
    "PassThruReadMsgs", "PassThruWriteMsgs", "PassThruStartPeriodicMsg",
    "PassThruStopPeriodicMsg", "PassThruStartMsgFilter", "PassThruStopMsgFilter",
    "PassThruSetProgrammingVoltage", "PassThruReadVersion",
    "PassThruGetLastError", "PassThruIoctl",
}

def verify(path: Path, arch: str) -> None:
    data = path.read_bytes()
    if not (0x100 <= len(data) <= 8 * 1024 * 1024) or data[:2] != b"MZ":
        raise ValueError("Not a bounded PE image")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe + 24 > len(data) or data[pe:pe + 4] != b"PE\x00\x00":
        raise ValueError("Invalid PE signature")
    machine = struct.unpack_from("<H", data, pe + 4)[0]
    sections = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    flags = struct.unpack_from("<H", data, pe + 22)[0]
    optional = pe + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    expected = {"Win32": (0x14C, 0x10B), "x64": (0x8664, 0x20B)}
    if arch not in expected or (machine, magic) != expected[arch]:
        raise ValueError("Wrong bitness or PE32/PE32+ format")
    if not flags & 0x2000:
        raise ValueError("Image is not a DLL")
    if sections < 1 or sections > 64 or optional + optional_size > len(data):
        raise ValueError("Invalid section table")
    section_table = optional + optional_size

    def map_rva(rva: int) -> int:
        for n in range(sections):
            entry = section_table + n * 40
            if entry + 40 > len(data):
                break
            virtual_size, virtual_address, raw_size, raw_ptr = struct.unpack_from(
                "<IIII", data, entry + 8
            )
            if virtual_address <= rva < virtual_address + max(virtual_size, raw_size):
                offset = raw_ptr + (rva - virtual_address)
                if 0 <= offset < len(data):
                    return offset
        raise ValueError("Unmapped PE export RVA")

    directory = optional + (96 if magic == 0x10B else 112)
    if directory + 8 > optional + optional_size:
        raise ValueError("Missing export data directory")
    export_rva, export_size = struct.unpack_from("<II", data, directory)
    if not export_rva or export_size < 40:
        raise ValueError("No export directory")
    export_at = map_rva(export_rva)
    num_exports = struct.unpack_from("<I", data, export_at + 24)[0]
    names_rva = struct.unpack_from("<I", data, export_at + 32)[0]
    if num_exports != len(EXPORTS) or not names_rva:
        raise ValueError("Not exactly 14 named exports")
    names_at = map_rva(names_rva)
    found: set[str] = set()
    for n in range(num_exports):
        name_rva = struct.unpack_from("<I", data, names_at + n * 4)[0]
        position = map_rva(name_rva)
        ending = data.find(b"\x00", position, position + 96)
        if ending < 0:
            raise ValueError("Unterminated export name")
        found.add(data[position:ending].decode("ascii"))
    if found != EXPORTS:
        raise ValueError("Unexpected or decorated J2534 exports")
    print(f"PASS: PE machine/format and exact 14 exports ({arch})")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_pe_exports.py DLL Win32|x64")
    verify(Path(sys.argv[1]), sys.argv[2])
