#!/usr/bin/env python3
"""B3A299: read-only process/PID census for a private VirtualCar J2534 log.

Counts only "[PID=... process.exe]" line prefixes from a bounded log tail.
Never prints or persists raw log lines, packet bytes, VIN, private paths,
vehicle identifiers, registry, or VIDA/CarCom data. No side effects.

CAVEAT: the last N bytes are the exact previous GUI action window ONLY if
no additional logging occurred after that GUI action's snapshot.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import sys

TAG = re.compile(rb"^\[PID=([0-9A-Fa-f]{8}) ([^\]\r\n]{1,120})\] ")
SAFE_PROCESS = re.compile(rb"[A-Za-z0-9_.-]{1,64}", re.ASCII)
PID = re.compile(r"[0-9A-Fa-f]{8}\Z")


def scan_bytes(data: bytes) -> tuple[Counter[tuple[str, str]], int, int]:
    found: Counter[tuple[str, str]] = Counter()
    untagged = 0
    total = 0
    for line in data.splitlines():
        if not line:
            continue
        total += 1
        m = TAG.match(line)
        if m is None:
            untagged += 1
            continue
        name = m.group(2)
        if not SAFE_PROCESS.fullmatch(name):
            name = b"REDACTED_PROCESS"
        pid = m.group(1).decode("ascii").upper()
        found[(pid, name.decode("ascii").upper())] += 1
    return found, total, untagged


def summary(data: bytes, previous_pid: str, *, exact_window: bool = False) -> list[str]:
    found, total, untagged = scan_bytes(data)
    pid_counts = Counter()
    hosts = Counter()
    for (pid, host), count in found.items():
        hosts[host] += count
        if host == "IEXPLORE.EXE":
            pid_counts[pid] += count

    out = [
        f"B3A299_ANALYZED_COMPLETE_LINES={total}",
        f"B3A299_TAGGED_LINES={sum(found.values())}",
        f"B3A299_UNTAGGED_LINES={untagged}",
        f"B3A299_IEXPLORE_TOTAL_LINES={sum(pid_counts.values())}",
        f"B3A299_IEXPLORE_UNIQUE_PIDS={len(pid_counts)}",
        f"B3A299_PREVIOUS_PID={previous_pid.upper()}",
        f"B3A299_PREVIOUS_PID_LINES={pid_counts[previous_pid.upper()]}",
        "B3A299_TAIL_EQUIVALENT_TO_CAPTURE_ONLY_IF_NO_NEW_LOG_WRITES=" +
        ("NOT_APPLICABLE" if exact_window else "TRUE"),
    ]
    for pid, count in sorted(pid_counts.items(), key=lambda x: (-x[1], x[0]))[:20]:
        out.append(f"B3A299_IEXPLORE_PID={pid},lines:{count}")
    for host, count in hosts.most_common(12):
        out.append(f"B3A299_HOST={host},lines:{count}")
    if not found:
        status = "NO_RECOGNIZED_PID_TAGS"
    elif not pid_counts:
        status = "NO_IEXPLORE_TAGS"
    elif len(pid_counts) == 1 and previous_pid.upper() not in pid_counts:
        status = "DIFFERENT_IEXPLORE_PID_FOUND"
    elif len(pid_counts) == 1:
        status = "ONLY_PREVIOUS_IEXPLORE_PID"
    else:
        status = "MULTIPLE_IEXPLORE_PIDS"
    out.append(f"B3A299_STATUS={status}")
    out.append("B3A299_RESULT=READ_ONLY_COMPLETE")
    return out


def tail_complete_lines(path: Path, requested: int) -> tuple[bytes, int]:
    with path.open("rb") as f:
        f.seek(0, 2)
        end = f.tell()
        start = max(0, end-requested)
        # If the sample begins inside a line, skip that partial line.
        if start:
            f.seek(start-1)
            preceded_by_newline = f.read(1) == b"\n"
        else:
            preceded_by_newline = True
        f.seek(start)
        data = f.read(end-start)
    if not preceded_by_newline:
        pos = data.find(b"\n")
        data = data[pos+1:] if pos >= 0 else b""
    # Do not treat an actively written/incomplete final line as a full record.
    if data and not data.endswith(b"\n"):
        pos = data.rfind(b"\n")
        data = data[:pos+1] if pos >= 0 else b""
    return data, end


def main() -> int:
    p = argparse.ArgumentParser(description="B3A299 read-only VirtualCar log PID census")
    p.add_argument("--log", required=True, type=Path)
    p.add_argument("--tail-bytes", required=True, type=int)
    p.add_argument("--previous-pid", default="00001828")
    args = p.parse_args()
    if not 1 <= args.tail_bytes <= 32*1024*1024 or not PID.fullmatch(args.previous_pid):
        print("B3A299_RESULT=ERROR_INVALID_ARGUMENT")
        return 2
    try:
        data, end = tail_complete_lines(args.log, args.tail_bytes)
    except OSError:
        print("B3A299_RESULT=ERROR_LOG_UNAVAILABLE")
        return 1

    print(f"B3A299_LOG_END_OFFSET={end}")
    print(f"B3A299_REQUESTED_TAIL_BYTES={args.tail_bytes}")
    print(f"B3A299_COMPLETE_LINE_BYTES={len(data)}")
    for row in summary(data, args.previous_pid):
        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
