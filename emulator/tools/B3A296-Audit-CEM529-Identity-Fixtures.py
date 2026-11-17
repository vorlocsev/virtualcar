#!/usr/bin/env python3
"""B3A296: owner-local, read-only CEM 529 / GGD identifier fixture guard.

Reports only whether the original private INI can supply explicit, nonempty
read-only 29-bit CEM F110/F106/F114 DID replies under the current C source.
Never prints raw values, VIN, CAN frames, INI paths, or firmware identities.
Does not read CarCom, launch VIDA, contact an ECU, or write any file.
"""
from __future__ import annotations

import argparse
import configparser
from pathlib import Path
import re
import sys


def yes(b: bool) -> str:
    return "TRUE" if b else "FALSE"


def hex_blob_length(value: str, cap: int = 192) -> int:
    # Mirror the accepted parse_hex_blob separators and byte-pair rule.
    data = re.sub(r"[ \t,:-]+", "", value)
    if not data:
        return 0
    if len(data) % 2 or re.fullmatch(r"[0-9A-Fa-f]+", data) is None:
        return 0
    n = len(data) // 2
    return n if n <= cap else 0


def did_code(value: str) -> int:
    value = value.strip()
    if not value:
        return -1
    if value.lower().startswith("0x"):
        value = value[2:]
    if not 1 <= len(value) <= 4 or re.fullmatch(r"[0-9A-Fa-f]+", value) is None:
        return -1
    return int(value, 16)


def run(ini_text: str, c_text: str) -> list[str]:
    result = [
        "B3A296_SCOPE=PRIVATE_INI_AND_EXACT_SOURCE_STATIC_AUDIT",
        "B3A296_CARCOM_529_CONFIG=541_GGD_500000_29BIT_OWNER_CONFIRMED",
        "B3A296_ONWIRE_OEM_POSITIVE_RESPONSE=NOT_PROVEN",
    ]
    required_src = (
        "#define MAX_EXTRA_DID_SLOTS 4",
        "#define MAX_EXTRA_DID 192",
        "g_ecu[i].did_code[slot]==0xF114u",
        "req[2]==0x14&&ecu->req==0x726u",
        "if(!sz)sz=answer_uds",
        "GetPrivateProfileStringA(key,kcode",
        "GetPrivateProfileStringA(key,kbytes",
    )
    source_verified = all(token in c_text for token in required_src)
    result.append("B3A296_C_SOURCE_EXPECTED_GUARDS=" + ("PASS" if source_verified else "NOT_VERIFIED"))
    ini = configparser.ConfigParser(
        interpolation=None, strict=True, inline_comment_prefixes=(";", "#")
    )
    ini.read_string(ini_text)
    lab = ini.get("Diagnostics", "EnableGGDCemLab", fallback="").strip() == "1"
    route = (
        ini.get("ECU1", "RequestId", fallback="").strip().upper().removeprefix("0X") == "18DA50F1"
        and ini.get("ECU1", "ResponseId", fallback="").strip().upper().removeprefix("0X") == "18DAF150"
        and ini.get("Vehicle", "ECUCount", fallback="").strip() == "2"
    )
    result += [
        "B3A296_GGD_LAB_ENABLED=" + yes(lab),
        "B3A296_PRIVATE_29BIT_CEM_ROUTE=" + ("PASS" if route else "NOT_VERIFIED"),
    ]
    fixtures: dict[int, list[int]] = {}
    other = 0
    invalid = 0
    for slot in range(4):
        key = f"DID{slot}Code"
        raw = ini.get("ECU1", key, fallback="")
        code = did_code(raw)
        value = ini.get("ECU1", f"DID{slot}Hex", fallback="")
        payload_length = hex_blob_length(value)
        if code < 0 and not raw:
            continue
        if (
            code < 0xF100 or code > 0xF1FF
            or code in (0xF114, 0xF190, 0xF1B0, 0xF1A3)
            or payload_length == 0
        ):
            invalid += 1
            continue
        fixtures.setdefault(code, []).append(payload_length)
        if code not in (0xF110, 0xF106):
            other += 1
    result.extend([
        f"B3A296_ECU1_VALID_OTHER_F1XX_SLOTS={other}",
        f"B3A296_ECU1_INVALID_OR_IGNORED_DID_SLOTS={invalid}",
    ])
    for did in (0xF110, 0xF114, 0xF106):
        suffix = f"{did:04X}"
        lens = fixtures.get(did, [])
        result.append(f"B3A296_{suffix}_EXPLICIT_VALID_FIXTURE=" + yes(bool(lens)))
        if lens:
            result.append(f"B3A296_{suffix}_FIXTURE_BYTES_FIRST_SLOT={lens[0]}")
            result.append(f"B3A296_{suffix}_DUPLICATE_VALID_SLOTS={len(lens) - 1}")
        if did == 0xF114:
            result.append("B3A296_F114_29BIT_DIRECT_FIXTURE_BLOCKED_BY_SOURCE=" +
                          yes(source_verified))
        else:
            result.append(f"B3A296_{suffix}_MAY_REPLY_POSITIVE_ONLY_IF_CONFIGURED=" +
                          yes(source_verified and bool(lens)))
    result.extend((
        "B3A296_DID_TO_CARCOM_F0_MAPPING=NOT_PROVEN",
        "B3A296_GUI_CEM_IDENT_ACCEPTANCE=NOT_ASSESSED",
        "B3A296_RESULT=READ_ONLY_COMPLETE",
    ))
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="B3A296 local private CEM529 F1xx fixture availability audit")
    p.add_argument("--ini", type=Path, required=True)
    p.add_argument("--source", type=Path,
                   default=Path(__file__).resolve().parent.parent / "src" / "virtualcar.c")
    args = p.parse_args()
    try:
        ini_text = args.ini.read_bytes().decode("latin-1")
        source_text = args.source.read_text(encoding="utf-8", errors="replace")
        rows = run(ini_text, source_text)
    except (OSError, configparser.Error, ValueError, UnicodeError):
        print("B3A296_RESULT=ERROR_PRIVATE_INPUT_OR_SOURCE")
        return 1
    for row in rows:
        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
