#!/usr/bin/env python3
"""B3A65: opt-in disposable D2_40 B9FB laboratory INI, never an OEM reply.

Source is the already published synthetic CEM50 PS fixture in this checkout.
Only a NEW isolated directory is created. The installed provider, VIDA and
registry are not touched. This does NOT enable B9 F0, A3 or A6 responses.
"""
import argparse
import configparser
import io
import os
from pathlib import Path
import re
import sys

from audit_vida_b3a53_b9fb_loader import audit_text, _valid_d2

SOURCE = Path(__file__).resolve().parents[1] / "adapters" / "cem50" / "virtualcar.ini"
REPO = Path(__file__).resolve().parents[2]
PROVENANCE = "synthetic_public_2005_donor_retargeted_50_to_40_lab_only"
AUTHORITY = "synthetic_d2_40_route_experiment_not_oem"
VIN_RE = re.compile(rb"[A-HJ-NPR-Z0-9]{17}\Z")


def _cfg(text):
    if type(text) is not str or len(text.encode("utf-8")) > 512 * 1024:
        raise ValueError("invalid source size")
    cfg = configparser.ConfigParser(interpolation=None, strict=True)
    cfg.optionxform = str
    cfg.read_string(text)
    if len({section.casefold() for section in cfg.sections()}) != len(cfg.sections()):
        raise ValueError("ambiguous section names")
    return cfg


def _frame(cfg, section, index):
    raw = cfg.get(section, "B9FBFrame" + format(index, "X"))
    parts = raw.strip().split()
    if len(parts) != 8 or any(re.fullmatch(r"[0-9A-Fa-f]{2}", x) is None
                              for x in parts):
        raise ValueError("not an eight-byte lab frame")
    return bytes(int(x, 16) for x in parts)


def _frames(cfg, section, target):
    if cfg.has_option(section, "FrameCount"):
        raise ValueError("ambiguous native frame-count precedence")
    if cfg.get(section, "B9FBFrameCount") != "13":
        raise ValueError("expected known 13-frame synthetic donor")
    frames = [_frame(cfg, section, i) for i in range(13)]
    if not _valid_d2(frames, target):
        raise ValueError("D2 framing rejected")
    return frames


def build_lab_ini(source):
    """Build in memory. Source data remains explicitly synthetic."""
    cfg = _cfg(source)
    if (cfg.get("Vehicle", "ModelYear") != "2009"
            or cfg.get("P2", "StrictRouting") != "1"
            or cfg.get("P2", "FixtureAuthority") != "synthetic_lab_not_oem_attested"
            or cfg.get("J2534_2", "Enabled") != "1"
            or cfg.get("PassiveCAN", "Enabled") != "0"
            or cfg.get("D2_40", "ResponseId").upper() != "00800003"
            or cfg.get("D2_50", "ResponseId").upper() != "01200003"
            or cfg.get("D2_40", "B9FBFrameCount") != "0"):
        raise ValueError("unknown or non-isolated donor")
    for section in ("D2_40_B9F0", "D2_50_B9F0", "D2_40_B9FC", "D2_50_B9FC"):
        if cfg.get(section, "FrameCount") != "0":
            raise ValueError("unexpected extra positive ECU response")
    original = _frames(cfg, "D2_50", 0x50)
    content = b"".join(frame[1:] for frame in original)
    if content[:3] != b"\x50\xF9\xFB" or len(content) != 91:
        raise ValueError("unknown donor payload")
    payload = content[3:]
    vin = cfg.get("Vehicle", "VIN").encode("ascii")
    if (len(payload) != 88 or payload[0] != 0x57 or
            payload[86:88] != b"\x0d\x0a" or
            VIN_RE.fullmatch(vin) is None or payload[11:28] != vin):
        raise ValueError("unexpected synthetic payload/VIN relationship")

    # Only the logical D2 response target is changed. All 88 application
    # bytes remain the unverified synthetic donor. The CAN response ID is
    # the pre-existing, not independently attested CEM40 lab setting.
    modified = [bytes([frame[0], 0x40]) + frame[2:]
                if i == 0 else frame
                for i, frame in enumerate(original)]
    if not _valid_d2(modified, 0x40):
        raise ValueError("retargeted D2 framing rejected")
    cfg.set("D2_40", "B9FBFrameCount", "13")
    for index, frame in enumerate(modified):
        cfg.set("D2_40", "B9FBFrame" + format(index, "X"),
                frame.hex(" ").upper())
    cfg.set("P2", "FixtureAuthority", AUTHORITY)
    cfg.set("P2", "FixtureProvenance", PROVENANCE)

    out = io.StringIO()
    out.write("; ISOLATED SYNTHETIC CEM40 TEST ONLY - NOT OEM DATA\n")
    out.write("; D2_40 B9FB is retargeted from a published CEM50 lab donor.\n")
    out.write("; No proof of original VIDA acceptance or response-ID filters.\n")
    out.write("; NEVER overwrite the installed virtualcar.ini with this file.\n\n")
    cfg.write(out, space_around_delimiters=True)
    text = out.getvalue()
    post = _cfg(text)
    new_frames = _frames(post, "D2_40", 0x40)
    if (post.get("D2_40", "ResponseId") != "00800003"
            or new_frames != modified
            or _frames(post, "D2_50", 0x50) != original
            or b"".join(f[1:] for f in new_frames)[3:] != payload):
        raise ValueError("source payload or route was altered unexpectedly")
    report = audit_text(text)["b9fb"]
    if not all(report[k]["static_loader_class"] ==
               "locally_structural_reply_not_oem_verified"
               for k in ("CEM_40", "CEM_50")):
        raise ValueError("B3A53 did not validate both D2 routes")
    return text


def _safe_new_directory(destination):
    if not destination.is_absolute() or destination.name in ("", ".", ".."):
        raise ValueError("an absolute new output directory is required")
    if destination.is_symlink() or destination.exists():
        raise ValueError("refusing existing output directory")
    dest = destination.resolve(strict=False)
    if dest.is_relative_to(REPO.resolve()):
        raise ValueError("refusing output inside repo")
    roots = [os.environ.get(k) for k in
             ("PROGRAMDATA", "WINDIR", "PROGRAMFILES", "PROGRAMFILES(X86)")]
    for raw in roots:
        if raw and dest.is_relative_to(Path(raw).resolve(strict=False)):
            raise ValueError("refusing protected installation/system directory")
    if not dest.parent.is_dir() or dest.parent.is_symlink():
        raise ValueError("parent directory must already exist and not be symlink")
    return dest


def create_exclusive(directory, content):
    directory = _safe_new_directory(directory)
    directory.mkdir(mode=0o700)
    target = directory / "virtualcar.ini"
    try:
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except BaseException:
        try:
            target.unlink(missing_ok=True)
            directory.rmdir()
        except OSError:
            pass
        raise
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="NEW empty lab directory; no automatic installation")
    parser.add_argument("--accept-synthetic-lab-only", action="store_true",
                        help="explicit opt-in to synthetic target 0x40 profile")
    args = parser.parse_args(argv)
    if not args.accept_synthetic_lab_only:
        parser.error("explicit --accept-synthetic-lab-only required")
    try:
        if SOURCE.is_symlink() or not SOURCE.is_file():
            raise ValueError("source fixture missing")
        text = build_lab_ini(SOURCE.read_text(encoding="utf-8-sig"))
        create_exclusive(args.output_dir, text)
    except (OSError, ValueError, UnicodeError, configparser.Error):
        print("B3A65: REJECTED; no installed profile changed", file=sys.stderr)
        return 2
    print("B3A65: CREATED_NEW_ISOLATED_SYNTHETIC_INI")
    print("D2_40 B9FB: 13 source-retargeted synthetic frames; D2_50: 13 unchanged")
    print("B9 F0 / B9 FC: DISABLED; VIN/ECU/VIDA acceptance: NOT_VERIFIED")
    print("No paths, VIN, frame bytes, live J2534 or OEM data exported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
