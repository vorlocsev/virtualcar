#!/usr/bin/env python3
"""Read-only M32C CEM Flash module-number candidates. Never prints VIN/EEPROM.

The two ASCII fields are code/build identifiers, not confirmed B9F0 contents.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

SIZE = 320 * 1024
OFFSETS = (0x4FF40, 0x4FF68)
F0_FOOTER = bytes.fromhex('0f 00 07 00')

def scan(path: Path) -> dict:
    binary = path.read_bytes()
    if len(binary) != SIZE:
        raise ValueError(f"ожидалось {SIZE} байт M32C Flash, получено {len(binary)}")
    labels = []
    for offset in OFFSETS:
        text = binary[offset:offset+8].decode('ascii', errors='replace')
        labels.append({"offset":f"0x{offset:05X}", "number": text if re.fullmatch(r'\d{8}', text) else None})
    tables=[]
    for i in range(0,0xB000):
        if binary[i:i+2] != bytes.fromhex('f0 00') or binary[i+8:i+10] != bytes.fromhex('07 00'):
            continue
        if binary[i+6:i+8] != bytes.fromhex('0f 00'):
            continue
        address=int.from_bytes(binary[i+2:i+6],'little')
        if address>0xFFFF:continue
        tables.append({"entry_offset":f"0x{i:05X}", "address":f"0x{address:08X}",
                       "within_flash_image":0xFB0000<=address<=0xFFFFFF})
    return {"file":path.name, "size":len(binary), "ascii_number_candidates":labels,
            "f0_table_entries":tables,
            "note":"These strings and table addresses do not establish the live B9F0 reply."}

if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('flash',type=Path,nargs='+')
    ap.add_argument('--out',type=Path)
    args=ap.parse_args()
    data=[scan(x) for x in args.flash]
    result=json.dumps(data,ensure_ascii=False,indent=2)
    if args.out:args.out.write_text(result+'\n',encoding='utf-8')
    else:print(result)
