#!/usr/bin/env python3
"""B3A288: read-only consistency check of a *private* D2_50 FB VIN/chassis
and the independently configured [Vehicle] VIN used by virtual J2534 UDS.

Only prints booleans, error labels and numeric match counts; no VIN, chassis,
INI path, frame hex, identifiers, hashes, or source contents are ever printed.
No writes, no network, no VIDA access, no ECU commands.
"""
from __future__ import annotations

import argparse
import configparser
from pathlib import Path
import re
import runpy
import sys


def clean_error(tag: str) -> str:
    allowed = {
        "MISSING_D2_50_SECTION",
        "INVALID_FRAME_HEX",
        "INVALID_FRAME_LENGTH",
        "INVALID_FRAME_COUNT",
        "FRAME_COUNT_OUT_OF_RANGE",
        "MISSING_FRAME_ENTRY",
        "NOT_13_FRAME_DONOR",
        "UNEXPECTED_D2_50_B9FB_ECHO",
        "INVALID_TERMINAL_FRAME",
        "TERMINAL_FRAME_MISSING",
        "D2_SEQUENCE_INVALID",
        "MISSING_TERMINAL_FRAME",
        "UNEXPECTED_D2_STREAM_ECHO",
    }
    return tag if tag in allowed else "LOCAL_INPUT_OR_PARSE_ERROR"


def fmt_bool(v: bool) -> str:
    return "TRUE" if v else "FALSE"


def main() -> int:
    parser = argparse.ArgumentParser(description="B3A288: private INI VIN cross-source check; no raw values printed")
    parser.add_argument("--ini", type=Path, required=True)
    args = parser.parse_args()

    try:
        # Import audited B3A287's private D2 reconstruction without running its CLI.
        # The imported module is the adjacent file in the local Git checkout.
        previous = runpy.run_path(
            str(Path(__file__).resolve().with_name("B3A287-Audit-PrivateFB.py")),
            run_name="b3a287_library",
        )
        body: bytes = previous["reconstruct"](previous["load_frames"](args.ini))
        ini = configparser.ConfigParser(
            interpolation=None, strict=True, inline_comment_prefixes=(";", "#")
        )
        ini.read_string(args.ini.read_bytes().decode("latin-1"))
    except (OSError, UnicodeError, configparser.Error, ValueError, KeyError) as e:
        print("B3A288_RESULT=ERROR_" + clean_error(str(e)))
        return 1

    if len(body) != 88:
        print("B3A288_FB_BODY_88_BYTES=" + fmt_bool(False))
        print("B3A288_RESULT=UNSUPPORTED_FB_LAYOUT")
        return 1
    fb_vin: bytes = body[11:28]
    chassis: bytes = body[46:52]
    ascii_vin = re.fullmatch(rb"[A-HJ-NPR-Z0-9]{17}", fb_vin) is not None
    serial = fb_vin[-6:]
    serial_is_digits = all(0x30 <= b <= 0x39 for b in serial)
    chassis_is_digits = all(0x30 <= b <= 0x39 for b in chassis)
    chassis_is_printable = all(0x20 <= b <= 0x7E for b in chassis)

    print("B3A288_D2_B9FB_13_FRAME=PASS")
    print("B3A288_FB_BODY_88_BYTES=TRUE")
    print("B3A288_FB_VIN_FORMAT_VALID=" + fmt_bool(ascii_vin))
    print("B3A288_FB_VIN_LAST6_ALL_DECIMAL=" + fmt_bool(serial_is_digits))
    print("B3A288_FB_CHASSIS_PRINTABLE_ASCII=" + fmt_bool(chassis_is_printable))
    print("B3A288_FB_CHASSIS_ALL_DECIMAL=" + fmt_bool(chassis_is_digits))
    print("B3A288_FB_VIN_LAST6_EQUALS_CHASSIS=" + fmt_bool(serial == chassis))
    print("B3A288_FB_VIN_CHASSIS_DIFFERENT_POSITIONS=" +
          str(sum(a != b for a, b in zip(serial, chassis))))

    if not ini.has_option("Vehicle", "VIN"):
        print("B3A288_VEHICLE_VIN=NOT_CONFIGURED_DLL_USES_DEFAULT")
        print("B3A288_FB_VIN_EQUALS_CONFIGURED_VEHICLE_VIN=NOT_TESTED")
        print("B3A288_CHASSIS_EQUALS_CONFIGURED_VEHICLE_VIN_LAST6=NOT_TESTED")
    else:
        raw_config_vin = ini.get("Vehicle", "VIN").strip()
        # DLL only adopts a 17-character value. Empty/other lengths fall back
        # to its built-in default, which this script deliberately does not infer.
        if len(raw_config_vin) != 17:
            print("B3A288_VEHICLE_VIN=INVALID_LENGTH_DLL_USES_DEFAULT")
            print("B3A288_FB_VIN_EQUALS_CONFIGURED_VEHICLE_VIN=NOT_TESTED")
            print("B3A288_CHASSIS_EQUALS_CONFIGURED_VEHICLE_VIN_LAST6=NOT_TESTED")
        else:
            try:
                config_vin = raw_config_vin.encode("latin-1")
            except UnicodeError:
                print("B3A288_RESULT=ERROR_LOCAL_INPUT_OR_PARSE_ERROR")
                return 1
            print("B3A288_VEHICLE_VIN=EXPLICIT_17_CHAR")
            print("B3A288_FB_VIN_EQUALS_CONFIGURED_VEHICLE_VIN=" +
                  fmt_bool(fb_vin == config_vin))
            print("B3A288_CHASSIS_EQUALS_CONFIGURED_VEHICLE_VIN_LAST6=" +
                  fmt_bool(chassis == config_vin[-6:]))
    print("B3A288_INTERPRETATION=CONSISTENCY_ONLY_NOT_VIDA_ACCEPTANCE")
    print("B3A288_RESULT=READ_ONLY_COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
