#!/usr/bin/env python3
"""B3A287: read-only local comparison of private D2_50 B9FB with CEM529 FB metadata.

No SQL, network, registry, VIDA process, or file mutations. Never prints
input path, VIN, CAN frame content, chassis, or any source identifying bytes.
T141 offsets and lengths are interpreted as *hypothetical* bit units.
"""
from __future__ import annotations

import argparse
import configparser
from pathlib import Path
import re
import sys

# Exact original CarCom T141 FB metadata collected by owner at B3A286.
FIELDS = (
    ("DATA_LENGTH", 0, 8),
    ("CAR_CONFIG_DOC_NUMBER", 8, 40),
    ("CAR_CONFIG_ISSUE", 48, 24),
    ("VIN", 88, 136),
    ("FYON", 240, 72),
    ("TYPE_PNR3", 328, 24),
    ("CHASSIS", 368, 48),
    ("FACTORY_CODE", 432, 16),
    ("STRUCTURE_WEEK", 464, 48),
    ("PACKAGE_IDENTITY", 528, 160),
    ("FB_VEHICLE_INFORMATION", 704, 304),
    ("MARKETING_CODE", 1024, 16),
    ("INTERIOR_CODE", 1056, 32),
    ("EXTERIOR_COLOR", 1104, 40),
    ("S_MESSAGE", 1160, 40),
    ("SERVICE_INFORMATION", 1216, 112),
)
VIN_ALLOWED = re.compile(rb"[A-HJ-NPR-Z0-9]{17}\Z")
HEX_BYTES = re.compile(r"^[0-9A-Fa-f\s,]+$")


def parse_frame(raw: str) -> bytes:
    raw = re.sub(r"\b0[xX](?=[0-9A-Fa-f]{2}\b)", "", raw).strip()
    if not HEX_BYTES.fullmatch(raw):
        raise ValueError("INVALID_FRAME_HEX")
    pieces = raw.replace(",", " ").split()
    if len(pieces) == 8 and all(len(x) == 2 for x in pieces):
        return bytes(int(x, 16) for x in pieces)
    compact = "".join(pieces)
    if len(compact) == 16:
        return bytes.fromhex(compact)
    raise ValueError("INVALID_FRAME_LENGTH")


def load_frames(path: Path) -> list[bytes]:
    ini = configparser.ConfigParser(
        interpolation=None, strict=True, inline_comment_prefixes=(";", "#")
    )
    ini.read_string(path.read_bytes().decode("latin-1"))
    if not ini.has_section("D2_50"):
        raise ValueError("MISSING_D2_50_SECTION")
    section = ini["D2_50"]
    count_raw = section.get("FrameCount") or section.get("B9FBFrameCount")
    try:
        count = int(count_raw or "")
    except ValueError as exc:
        raise ValueError("INVALID_FRAME_COUNT") from exc
    if not 1 <= count <= 64:
        raise ValueError("FRAME_COUNT_OUT_OF_RANGE")
    frames = []
    for i in range(count):
        value = section.get(f"B9FBFrame{i:X}") or section.get(f"Frame{i:X}")
        if value is None:
            raise ValueError("MISSING_FRAME_ENTRY")
        frames.append(parse_frame(value))
    return frames


def reconstruct(frames: list[bytes]) -> bytes:
    if len(frames) != 13:
        raise ValueError("NOT_13_FRAME_DONOR")
    if frames[0][0] != 0x8F or frames[0][1:4] != bytes.fromhex("50 F9 FB"):
        raise ValueError("UNEXPECTED_D2_50_B9FB_ECHO")
    sequence = 1
    end_found = False
    for i in range(1, len(frames)):
        h = frames[i][0]
        if 0x48 <= h <= 0x4F:
            if i != len(frames) - 1 or h != 0x4F:
                raise ValueError("INVALID_TERMINAL_FRAME")
            end_found = True
            continue
        if (h & 0xF8) == 0x50:
            if i == len(frames) - 1:
                raise ValueError("TERMINAL_FRAME_MISSING")
            continue
        if (
            h == 0x8F
            and i > 1
            and (frames[i - 1][0] & 0xF8) == 0x50
            and frames[i][1:4] == bytes.fromhex("50 F9 FB")
        ):
            continue
        if h != (0x08 | sequence):
            raise ValueError("D2_SEQUENCE_INVALID")
        sequence = (sequence + 1) & 7
    if not end_found:
        raise ValueError("MISSING_TERMINAL_FRAME")
    stream = b"".join(frame[1:] for frame in frames)
    if stream[:3] != bytes.fromhex("50 F9 FB"):
        raise ValueError("UNEXPECTED_D2_STREAM_ECHO")
    return stream[3:]


def audit(body: bytes, expected_year: int | None) -> list[tuple[str, str]]:
    result = [
        ("B3A287_FRAME_COUNT", "13"),
        ("B3A287_D2_ECHO_AND_SEQUENCE", "PASS"),
        ("B3A287_FB_BODY_BYTES", str(len(body))),
        ("B3A287_CARCOM_529_FB_REFERENCE_BYTES_IF_BITS", "166"),
        ("B3A287_FB_STORED_LENGTH_COMPARABLE_TO_ONWIRE", "NOT_PROVEN"),
    ]
    if not body:
        return result + [("B3A287_FB_LENGTH_BYTE", "ABSENT")]
    result += [
        ("B3A287_FB_DECLARED_AFTER_LENGTH_BYTE", str(body[0])),
        ("B3A287_FB_LENGTH_BYTE_MATCHES", str(body[0] == len(body) - 1).upper()),
    ]
    full_fields = [
        (name, off // 8, ln // 8)
        for name, off, ln in FIELDS
        if (off + ln) // 8 <= len(body)
    ]
    result.append(("B3A287_COMPLETE_CARCOM_FIELDS_IF_BITS", str(len(full_fields))))
    result.append(
        ("B3A287_LAST_COMPLETE_FIELD", full_fields[-1][0] if full_fields else "NONE")
    )
    gaps = []
    for (_, start, width), (_, next_start, _) in zip(full_fields, full_fields[1:]):
        if next_start - start - width == 2:
            gaps.append(body[start + width : next_start] == b"\r\n")
    if full_fields:
        _, start, width = full_fields[-1]
        boundary = start + width
        if boundary + 2 == len(body) and boundary + 2 <= 166:
            gaps.append(body[boundary : boundary + 2] == b"\r\n")
    result.append(("B3A287_CRLF_GAPS_TESTED", str(len(gaps))))
    result.append(("B3A287_CRLF_GAPS_VALID", str(sum(gaps))))

    if len(body) >= 28:
        vin = body[11:28]
        result.append(
            ("B3A287_VIN_17_ASCII_FORMAT", str(bool(VIN_ALLOWED.fullmatch(vin))).upper())
        )
        if expected_year is not None:
            # VIN model year symbol for 2001..2030; only position 10 is examined.
            year_codes = "123456789ABCDEFGHJKLMNPRSTVWXY"
            if 2001 <= expected_year <= 2030:
                code = year_codes[expected_year - 2001]
                result.append(
                    ("B3A287_VIN_EXPECTED_MODEL_YEAR_MATCH",
                     str(vin[9:10].decode("latin-1") == code).upper())
                )
            else:
                result.append(
                    ("B3A287_VIN_EXPECTED_MODEL_YEAR_MATCH", "UNSUPPORTED_YEAR")
                )
        if len(body) >= 52:
            result.append(
                ("B3A287_VIN_CHASSIS_MATCH", str(vin[-6:] == body[46:52]).upper())
            )
    else:
        result.append(("B3A287_VIN_17_ASCII_FORMAT", "NOT_ENOUGH_BYTES"))
    return result


ERRORS = {
    "MISSING_D2_50_SECTION", "INVALID_FRAME_HEX", "INVALID_FRAME_LENGTH",
    "INVALID_FRAME_COUNT", "FRAME_COUNT_OUT_OF_RANGE", "MISSING_FRAME_ENTRY",
    "NOT_13_FRAME_DONOR", "UNEXPECTED_D2_50_B9FB_ECHO",
    "INVALID_TERMINAL_FRAME", "TERMINAL_FRAME_MISSING",
    "D2_SEQUENCE_INVALID", "MISSING_TERMINAL_FRAME", "UNEXPECTED_D2_STREAM_ECHO",
}


def main() -> int:
    p = argparse.ArgumentParser(
        description="B3A287 local read-only private FB audit; raw values suppressed"
    )
    p.add_argument("--ini", type=Path, required=True)
    p.add_argument("--expected-model-year", type=int, default=None)
    args = p.parse_args()
    try:
        body = reconstruct(load_frames(args.ini))
    except (OSError, UnicodeError, configparser.Error, ValueError) as exc:
        tag = str(exc)
        if tag not in ERRORS:
            tag = "INPUT_READ_OR_PARSE_ERROR"
        print("B3A287_RESULT=ERROR_" + tag)
        return 1
    for key, value in audit(body, args.expected_model_year):
        print(f"{key}={value}")
    print("B3A287_RESULT=READ_ONLY_COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
