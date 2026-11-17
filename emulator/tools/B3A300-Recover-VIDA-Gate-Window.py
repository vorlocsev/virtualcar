#!/usr/bin/env python3
"""B3A300: recover a *historical* original VIDA J2534 action window, read only.

Anchor a previously captured B3A298 --window-bytes to a B3A299
LOG_END_OFFSET, then use its newly discovered exact IEXPLORE.EXE PID.
The original window equivalence is CONDITIONAL: no log appends between
the end of B3A298 and the B3A299 end-offset snapshot.

No VIDA operation, file writes, J2534 changes, SQL operations, CAN/ECU commands,
private VIN, raw frames or log lines are emitted. A separately captured GUI
screenshot is needed to assess ECU identification acceptance.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import runpy
import sys


def load_peer(filename: str):
    return runpy.run_path(str(Path(__file__).resolve().with_name(filename)),
                          run_name="b3a300_readonly_peer")


def capture_historic(stream, *, end_offset: int, window_bytes: int):
    """Return complete lines between immutable offsets from a read-only stream."""
    stream.seek(0, 2)
    file_end = stream.tell()
    if (window_bytes <= 0 or end_offset <= 0
            or window_bytes > end_offset or end_offset > file_end):
        raise ValueError("INVALID_OR_TRUNCATED_OFFSETS")
    start = end_offset - window_bytes
    stream.seek(start - 1 if start else 0)
    leading_boundary = start == 0 or stream.read(1) == b"\n"
    stream.seek(start)
    chunk = stream.read(window_bytes)
    if len(chunk) != window_bytes:
        raise ValueError("INCOMPLETE_READ")
    discarded = 0
    if not leading_boundary:
        pos = chunk.find(b"\n")
        discarded += len(chunk) if pos < 0 else pos + 1
        chunk = chunk[pos + 1:] if pos >= 0 else b""
    if chunk and not chunk.endswith(b"\n"):
        pos = chunk.rfind(b"\n")
        trailing = len(chunk) if pos < 0 else len(chunk) - pos - 1
        discarded += trailing
        chunk = chunk[:pos+1] if pos >= 0 else b""
    return chunk, file_end, discarded, start


def recovery_report(chunk: bytes, pid: str, gate: str,
                    expected_tagged: int | None = None) -> list[str]:
    census = load_peer("B3A299-Audit-VIDA-Log-PID-Census.py")["scan_bytes"]
    analyze = load_peer("B3A298-VIDA-Gate-Window.py")["analyze"]
    entries, total, untagged = census(chunk)
    tagged = sum(entries.values())
    host_lines = entries[(pid, "IEXPLORE.EXE")]
    exact_census = expected_tagged is None or expected_tagged == tagged
    output = [
        f"B3A300_COMPLETE_LINES={total}",
        f"B3A300_TAGGED_LINES={tagged}",
        f"B3A300_UNTAGGED_LINES={untagged}",
        f"B3A300_SELECTED_IEXPLORE_PID={pid}",
        f"B3A300_SELECTED_PID_LINES={host_lines}",
        f"B3A300_EXPECTED_TAGGED_LINES=" +
            ("NOT_SUPPLIED" if expected_tagged is None else str(expected_tagged)),
        f"B3A300_CENSUS_MATCH={'TRUE' if exact_census else 'FALSE'}",
        "B3A300_EQUIVALENT_TO_B3A298_WINDOW="
        "ONLY_IF_NO_LOG_WRITES_BETWEEN_CAPTURE_AND_B3A299_CENSUS",
        "B3A300_GUI_CAUSALITY=NOT_PROVEN_FROM_TRAFFIC_ALONE",
    ]
    if not exact_census:
        output.append("B3A300_RESULT=ERROR_CENSUS_MISMATCH")
        return output
    if host_lines == 0:
        output.append("B3A300_RESULT=ERROR_PID_NOT_IN_WINDOW")
        return output
    output.extend(analyze(chunk.decode("latin-1"), pid, gate))
    output.append("B3A300_RESULT=READ_ONLY_COMPLETE")
    return output


def main() -> int:
    ap = argparse.ArgumentParser(description="B3A300 recover a prior VIDA gate window by immutable log offsets")
    ap.add_argument("--log", type=Path, required=True)
    ap.add_argument("--end-offset", type=int, required=True)
    ap.add_argument("--window-bytes", type=int, required=True)
    ap.add_argument("--pid", default="00002710")
    ap.add_argument("--gate", choices=("cem-ident", "readvin"), required=True)
    ap.add_argument("--expected-tagged-lines", type=int)
    args = ap.parse_args()
    pid = args.pid.upper()
    if (re.fullmatch(r"[0-9A-F]{8}", pid) is None
            or not 1 <= args.window_bytes <= 32 * 1024 * 1024
            or args.end_offset < args.window_bytes
            or args.end_offset <= 0
            or args.expected_tagged_lines is not None
            and not 0 <= args.expected_tagged_lines <= 500000):
        print("B3A300_RESULT=ERROR_INVALID_ARGUMENT")
        return 2
    try:
        with args.log.open("rb") as stream:
            data, file_end, discarded, start = capture_historic(
                stream, end_offset=args.end_offset,
                window_bytes=args.window_bytes)
    except (OSError, ValueError):
        print("B3A300_RESULT=ERROR_LOG_OFFSETS_OR_READ")
        return 1
    print(f"B3A300_ANCHORED_WINDOW_START={start}")
    print(f"B3A300_ANCHORED_WINDOW_END={args.end_offset}")
    print(f"B3A300_CURRENT_FILE_END={file_end}")
    print(f"B3A300_DISCARDED_PARTIAL_LINE_BYTES={discarded}")
    for item in recovery_report(data, pid, args.gate, args.expected_tagged_lines):
        print(item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
