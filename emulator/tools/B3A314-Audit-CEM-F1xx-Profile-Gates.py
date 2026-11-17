#!/usr/bin/env python3
"""B3A314: source-backed current CEM 29-bit F1xx fixture readiness (read-only).

This audits the CURRENT virtualcar.ini next to the 32-bit J2534 FunctionLibrary
DLL registered under the unique label "J2534 Diagnostic Lab 277".

Native code provenance (emulator/src/virtualcar.c):
- GetModuleFileNameA(g_module) + virtualcar.ini in load_config()
- ECUCount, ECU[i] RequestId/ResponseId, 4 DIDnCode/DIDnHex slots
- parse_hex_blob permits whitespace, tab, dash, colon, comma separators
  and requires complete hexadecimal byte pairs, max 192 bytes
- F110 and F106 are only answered from a valid explicit configured DID slot
- F114 is RESERVED from slots and its synthetic VIN handler requires
  ecu->req==0x726, not the 29-bit CEM request 0x18DA50F1
- No OEM identity bytes can be inferred from GGD A45F/DD02 positives.

No output of filenames, paths, VIN, configured response payloads, raw
logged frames, INI values, hashes, private ECU data. Never loads DLL,
writes any files, changes INI or registration, runs VIDA or CI.
"""
from __future__ import annotations
import ntpath
import os
from pathlib import Path
import re
import runpy
import sys
from collections import Counter

ADAPTER = "J2534 Diagnostic Lab 277"
SPECIAL_DIDS = frozenset((0xF114, 0xF190, 0xF1B0, 0xF1A3))
TARGET_REQ, TARGET_RESP = 0x18DA50F1, 0x18DAF150
MAX_FIXTURE_BYTES = 192
VALID_LABEL = re.compile(r"[A-Za-z0-9 _().-]{1,120}\Z")


def peer(name: str):
    return runpy.run_path(str(Path(__file__).resolve().with_name(name)),
                          run_name="b3a314_peer_import")


def parse_fixture_length(value: str, cap: int = MAX_FIXTURE_BYTES) -> int:
    """Match source parse_hex_blob on safe strings, never expose decoded bytes."""
    if not value:
        return 0
    i = 0
    total = 0
    digits = set("0123456789abcdefABCDEF")
    while i < len(value):
        while i < len(value) and value[i] in " \t-:,":
            i += 1
        if i >= len(value):
            break
        if value[i] not in digits:
            return 0
        i += 1
        if i >= len(value) or value[i] not in digits or total >= cap:
            return 0
        i += 1
        total += 1
    return total


def evaluate(get) -> list[str]:
    src = peer("B3A306-Audit-Active-GGD-Profile-Origins.py")
    as_number, as_hex = src["source_num"], src["source_hex"]
    count = as_number(get("Vehicle", "ECUCount", "2"), 2)
    if count < 1 or count > 8:
        count = 1  # native fallback
    matching_ecus = []
    active_slots = Counter()
    invalid_payload = Counter()
    duplicate_slots = Counter()
    for i in range(count):
        section = "ECU"+str(i)
        req = as_hex(get(section, "RequestId", "726" if i == 1 else "7E0"),
                     0x726 if i == 1 else 0x7E0)
        resp = as_hex(get(section, "ResponseId", "72E" if i == 1 else "7E8"),
                      0x72E if i == 1 else 0x7E8)
        if req != TARGET_REQ or resp != TARGET_RESP:
            continue
        matching_ecus.append(i)
        seen: set[int] = set()
        for slot in range(4):
            raw_code = get(section, f"DID{slot}Code", "")
            code = as_hex(raw_code, 0xFFFFFFFF)
            if not (0xF100 <= code <= 0xF1FF) or code in SPECIAL_DIDS:
                continue
            length = parse_fixture_length(get(section, f"DID{slot}Hex", ""))
            if length <= 0:
                invalid_payload[code] += 1
                continue
            if code in seen:
                duplicate_slots[code] += 1
            seen.add(code)
            active_slots[code] += 1
    lab_enabled = as_number(
        get("Diagnostics", "EnableGGDCemLab", "0"), 0) == 1
    out = [
        "B3A314_ORIGIN=CURRENT_32BIT_REGISTERED_ADAPTER_DLL_DIRECTORY",
        "B3A314_STATE=CURRENT_INI_NOT_HISTORICAL_LOADED_CONFIG",
        f"B3A314_CEM29_ROUTE_COUNT={len(matching_ecus)}",
        "B3A314_CURRENT_GGD_ENABLED="+("TRUE" if lab_enabled else "FALSE"),
    ]
    for label, code in (("F110", 0xF110), ("F106", 0xF106)):
        out.extend((
            f"B3A314_{label}_VALID_CONFIGURED_SLOTS={active_slots[code]}",
            f"B3A314_{label}_INVALID_PAYLOAD_SLOTS={invalid_payload[code]}",
            f"B3A314_{label}_DUPLICATE_SLOTS={duplicate_slots[code]}",
            f"B3A314_{label}_POSITIVE_POSSIBLE_FROM_CURRENT_INI="+
            ("TRUE" if active_slots[code] > 0 and matching_ecus else "FALSE"),
        ))
    out.extend((
        "B3A314_F114_CONFIGURED_SLOTS_ALLOWED=FALSE",
        "B3A314_F114_29BIT_CEM_SYNTHETIC_VIN_HANDLER_REACHABLE=FALSE",
        "B3A314_F114_ROUTE_CONDITION=ECU_REQUEST_ID_0X726_ONLY",
        "B3A314_NO_OEM_F1XX_FIXTURE_INFERENCE_FROM_GGD_LAB",
        "B3A314_CEM_GUI_IDENT_READVIN_ACCEPTANCE=NOT_ASSESSED",
        "B3A314_NO_PRIVATE_BYTES_OR_PATHS_EMITTED=TRUE",
        "B3A314_NO_REGISTRY_INI_DLL_OR_VIDA_WRITES=TRUE",
        "B3A314_RESULT=READ_ONLY_COMPLETE",
    ))
    return out


def current_ini_path(adapter_label: str) -> tuple[str, str | None]:
    if not VALID_LABEL.fullmatch(adapter_label):
        return "ERROR_INVALID_LABEL", None
    reg = peer("B3A310-Resolve-VIDA-J2534-Adapter-Label.py")["registry_labels_32"]
    status, entries = reg()
    if status != "READ_OK":
        return "ERROR_REG32_"+status, None
    matches = [p for label, p in entries if label == adapter_label]
    if len(matches) != 1:
        return "ERROR_NOT_UNIQUE_REGISTERED_ADAPTER", None
    path = matches[0]
    if not ntpath.isabs(path) or ntpath.splitext(path)[1].lower() != ".dll":
        return "ERROR_INVALID_FUNCTIONLIBRARY_PATH", None
    ini_path = ntpath.join(ntpath.dirname(path), "virtualcar.ini")
    if not os.path.isfile(ini_path):
        return "ERROR_INI_NOT_FOUND", None
    return "READ_OK", ini_path


def main():
    if len(sys.argv) != 1:
        print("B3A314_RESULT=ERROR_UNEXPECTED_ARGUMENTS")
        return 2
    status, current_path = current_ini_path(ADAPTER)
    print("B3A314_ADAPTER_LABEL="+ADAPTER)
    print("B3A314_CURRENT_PROFILE_ACCESS="+status)
    if status != "READ_OK":
        print("B3A314_RESULT=ERROR_PROFILE_UNAVAILABLE")
        return 1
    get = peer("B3A306-Audit-Active-GGD-Profile-Origins.py")["win_ini_getter"](current_path)
    for result in evaluate(get):
        print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
