#!/usr/bin/env python3
"""VC090D: conservative offline identity-delivery audit of a frozen native log.

No client startup, live traffic, registry, SQL, or ECU access. Output contains
counts/categories only. This is not a VIDA script/GUI acceptance test.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import stat
import struct

from audit_p2_b9fb_shape import audit_frames
from audit_vida_b3a54_private_b9fb_vin import VIN_SHAPE

MAX_LOG = 16 * 1024 * 1024
MAX_LINES = 250000
PREFIX = re.compile(r"^\[PID=([0-9A-Fa-f]{8}) ([^\]\r\n]{1,47})\] (.*)$")
TX = "TX context channel/protocol/flags/baud/time-us (BE)"
RX = "RX context channel/protocol/status/baud/time-us (BE)"
TAG = "P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE)"
TX_DATA = "TX (app request)"
RX_DATA = "PassThruReadMsgs -> delivered"
OPEN = "PassThruOpen -> device 1"
CLOSE = "PassThruClose"
RESET = ("PassThruConnect ", "PassThruDisconnect", "CLEAR_RX context ",
         "J2534 CLEAR_RX_BUFFER", "J2534 DATA_RATE changed")
TOKEN = re.compile(r"[0-9A-Fa-f]{2}")


def payload(event, label, maximum, exact=None):
    if not event.startswith(label + " "):
        return None
    parts = event[len(label)+1:].split()
    if not 1 <= len(parts) <= maximum or (exact is not None and len(parts) != exact):
        return None
    if not all(TOKEN.fullmatch(part) for part in parts):
        return None
    return bytes(int(part, 16) for part in parts)


def audit(text, pid, host, expected_vin, displayed_vin=None):
    if not VIN_SHAPE.fullmatch(expected_vin):
        raise ValueError("invalid_expected_vin")
    if displayed_vin is not None and not VIN_SHAPE.fullmatch(displayed_vin):
        raise ValueError("invalid_owner_displayed_vin")
    if not 0 < pid <= 0xffffffff or not re.fullmatch(r"[^\]\r\n]{1,47}", host):
        raise ValueError("invalid_logger_selection")
    if len(text) > MAX_LOG or not text.endswith("\n"):
        raise ValueError("incomplete_or_oversized_log")
    counts = Counter()
    pending = {}
    context = None
    last_d2 = None
    active = False
    completed = []
    # A single complete Open/Close interval is required. Do not cross
    # process lifetimes or silently combine retries on the same channel.
    def invalidate(channel=None):
        keys = list(pending) if channel is None else [channel]
        for key in keys:
            if pending.pop(key, None) is not None:
                counts["incomplete"] += 1

    def accept(kind, observed):
        counts[kind + "_positive"] += 1
        counts[kind + ("_vin_equal" if observed == expected_vin else "_vin_different")] += 1
        completed.append(observed)

    for line_no, line in enumerate(text.splitlines()):
        if line_no >= MAX_LINES:
            raise ValueError("too_many_log_lines")
        match = PREFIX.fullmatch(line)
        if not match:
            # A damaged/unattributed row could hide a boundary.
            if active:
                invalidate()
                context = last_d2 = None
                counts["unattributed_inside_session"] += 1
            continue
        if int(match[1], 16) != pid or match[2] != host:
            continue
        event = match[3].rstrip()
        counts["selected_lines"] += 1
        if event == OPEN:
            counts["opens"] += 1
            if active:
                counts["boundary_errors"] += 1
            invalidate()
            context = last_d2 = None
            active = True
            continue
        if event == CLOSE:
            counts["closes"] += 1
            if not active:
                counts["boundary_errors"] += 1
            invalidate()
            context = last_d2 = None
            active = False
            continue
        if not active:
            continue
        # D2 tag must immediately follow the delivered record for this
        # logger prefix. Intervening selected lines fail closed.
        previous, last_d2 = last_d2, None
        if event.startswith(TAG):
            tag = payload(event, TAG, 20, 20)
            if previous is None or tag is None:
                counts["unpaired_d2_tags"] += 1
                continue
            channel, generation, index, _, _ = struct.unpack(">5I", tag)
            ch, can_id, frame = previous
            request = pending.get(ch)
            if (channel != ch or not generation or request is None or request["kind"] != "b9fb"
                    or index != len(request["frames"]) + 1
                    or request.get("generation", generation) != generation):
                counts["invalid_d2_sequence"] += 1
                invalidate(ch)
                continue
            request["generation"] = generation
            request["frames"].append((can_id, frame))
            if len(request["frames"]) == 13:
                frames = request["frames"]
                result = audit_frames(frames, target=request["target"])
                if (result["transport"] == "complete" and
                        result["published_88_byte_shape"] == "matches_one_observed_example" and
                        result["vin_shaped_field"]):
                    observed = b"".join(data[1:] for _, data in frames)[14:31].decode("ascii")
                    accept("b9fb", observed)
                    pending.pop(ch)
                else:
                    counts["invalid_d2_sequence"] += 1
                    invalidate(ch)
            continue
        if event.startswith(RESET):
            invalidate()
            context = None
            continue
        if event.startswith(TX) or event.startswith(RX):
            direction = "tx" if event.startswith(TX) else "rx"
            raw = payload(event, TX if direction == "tx" else RX, 20, 20)
            context = (direction, struct.unpack(">5I", raw)) if raw else None
            if raw is None:
                invalidate()
                counts["invalid_context"] += 1
            continue
        meta, context = context, None
        if not (event.startswith(TX_DATA) or event.startswith(RX_DATA)):
            continue
        direction = "tx" if event.startswith(TX_DATA) else "rx"
        raw = payload(event, TX_DATA if direction == "tx" else RX_DATA, 52)
        if meta is None or meta[0] != direction or raw is None or len(raw) < 4 or len(raw) == 52:
            invalidate()
            counts["unattributed_messages"] += 1
            continue
        channel, protocol, flags, baud, _ = meta[1]
        can_id = int.from_bytes(raw[:4], "big")
        data = raw[4:]
        if channel == 0 or can_id > 0x1fffffff:
            invalidate()
            counts["invalid_context"] += 1
            continue
        if direction == "tx":
            invalidate(channel)
            if (protocol == 5 and can_id == 0xffffe and flags == 0x100 and
                    len(data) == 8 and data[0] == 0xcb and data[2:] == b"\xb9\xfb\0\0\0\0"
                    and (data[1], baud) in ((0x40, 125000), (0x50, 500000))):
                counts["b9fb_requests"] += 1
                pending[channel] = dict(kind="b9fb", target=data[1], baud=baud, frames=[])
            elif (protocol == 6 and can_id == 0x7e0 and flags in (0, 0x40) and
                  baud == 500000 and data == b"\x22\xf1\x90"):
                counts["f190_requests"] += 1
                pending[channel] = dict(kind="f190", baud=baud)
            continue
        request = pending.get(channel)
        if request is None:
            continue
        if request["baud"] != baud:
            invalidate(channel)
            counts["wrong_context"] += 1
            continue
        if request["kind"] == "b9fb":
            if protocol == 5 and flags == 0x100 and len(data) == 8:
                last_d2 = (channel, can_id, data)
            else:
                invalidate(channel)
                counts["wrong_context"] += 1
        elif protocol == 6 and can_id == 0x7e8 and flags == 2 and not data:
            # J2534 START_OF_MESSAGE indication is not positive data.
            counts["start_indications"] += 1
        elif protocol == 6 and can_id == 0x7e8 and flags == 0 and len(data) == 20 and data[:3] == b"\x62\xf1\x90":
            observed = data[3:].decode("ascii", errors="replace")
            if VIN_SHAPE.fullmatch(observed):
                accept("f190", observed)
                pending.pop(channel)
            else:
                invalidate(channel)
                counts["invalid_vin_shape"] += 1
        else:
            invalidate(channel)
            counts["other_rx"] += 1
    invalidate()
    single = counts["opens"] == counts["closes"] == 1 and not active and not counts["boundary_errors"]
    clean = single and not any(counts[k] for k in (
        "unattributed_inside_session", "invalid_context", "unattributed_messages",
        "invalid_d2_sequence", "unpaired_d2_tags", "wrong_context", "incomplete",
        "invalid_vin_shape", "other_rx"))
    comparison = ("not_supplied" if displayed_vin is None else
                  "equal_to_expected" if displayed_vin == expected_vin else "different_from_expected")
    if not clean:
        gate = "incomplete_or_ambiguous_native_evidence"
    elif not completed:
        gate = "no_positive_identity_delivery_observed"
    elif any(value != expected_vin for value in completed):
        gate = "delivered_identity_differs"
    else:
        gate = "matching_lab_identity_delivery_observed"
    return {
        "schema": "vc090d-native-readvin-evidence-v1",
        "single_closed_logger_session": single,
        "native_evidence_gate": gate,
        "counts": {k: counts[k] for k in (
            "selected_lines", "opens", "closes", "boundary_errors", "incomplete",
            "unattributed_inside_session", "invalid_context", "unattributed_messages",
            "invalid_d2_sequence", "unpaired_d2_tags", "wrong_context", "invalid_vin_shape",
            "other_rx", "start_indications", "b9fb_requests", "b9fb_positive",
            "b9fb_vin_equal", "b9fb_vin_different", "f190_requests", "f190_positive",
            "f190_vin_equal", "f190_vin_different")},
        "owner_transcribed_displayed_vin_comparison": comparison,
        "owner_displayed_vin_matches_delivered": (
            "not_assessable" if displayed_vin is None or not clean or not completed else
            "equal" if all(v == displayed_vin for v in completed) else "different"),
        "original_vida_process_authenticated": False,
        "loaded_module_identity_verified": False,
        "readvin_script_execution_verified": False,
        "original_vida_vin_accepted_verified": False,
        "ecu_identity_accepted_verified": False,
        "physical_j2534_verified": False,
    }


def read_frozen(path, maximum):
    path = Path(path)
    if not path.is_absolute() or path.anchor.startswith("\\\\"):
        raise ValueError("explicit_local_path_required")
    for part in (path, *path.parents):
        info = part.lstat()
        if part.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("reparse_path")
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
        raise ValueError("invalid_source_size")
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    after = path.stat()
    if (len(data) != before.st_size or len(data) > maximum or
            (before.st_size, before.st_mtime_ns, before.st_ino) !=
            (after.st_size, after.st_mtime_ns, after.st_ino)):
        raise ValueError("source_changed")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-log", type=Path, required=True)
    parser.add_argument("--pid-hex", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--expected-vin-file", type=Path, required=True,
                        help="Private text file containing exactly one expected VIN")
    parser.add_argument("--displayed-vin-file", type=Path,
                        help="Optional independently transcribed VIDA display, not automatic GUI proof")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"[0-9a-fA-F]{8}", args.pid_hex):
            raise ValueError("invalid_pid")
        paths = [args.native_log, args.expected_vin_file]
        if args.displayed_vin_file is not None:
            paths.append(args.displayed_vin_file)
        out = args.output
        repo = Path(__file__).resolve().parents[2]
        if not out.is_absolute() or out.anchor.startswith("\\\\") or repo in out.resolve().parents:
            raise ValueError("external_output_required")
        for part in out.parents:
            info = part.lstat()
            if part.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("reparse_output")
        if len({p.resolve() for p in paths + [out]}) != len(paths) + 1:
            raise ValueError("source_alias")
        originals = [read_frozen(p, MAX_LOG if i == 0 else 128) for i, p in enumerate(paths)]
        result = audit(originals[0].decode("latin1"), int(args.pid_hex, 16), args.host,
                       originals[1].decode("ascii").strip(),
                       originals[2].decode("ascii").strip() if len(originals) == 3 else None)
        if any(read_frozen(p, MAX_LOG if i == 0 else 128) != originals[i]
               for i, p in enumerate(paths)):
            raise ValueError("source_changed")
        with out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    except (OSError, ValueError, UnicodeError):
        parser.exit(2, "ERROR: invalid, ambiguous or unreadable local input/output\n")
    print("VC090D_NATIVE_EVIDENCE=" + result["native_evidence_gate"])
    print("VC090D_ORIGINAL_VIDA_READVIN=NOT_VERIFIED")


if __name__ == "__main__":
    main()
