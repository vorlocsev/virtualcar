#!/usr/bin/env python3
"""B3A300 synthetic regression; no original VIDA, files or proprietary data."""
import io
from pathlib import Path
import runpy

module = runpy.run_path(str(Path(__file__).resolve().with_name(
    "B3A300-Recover-VIDA-Gate-Window.py")), run_name="b3a300_import_only")
capture = module["capture_historic"]
report = module["recovery_report"]


def log(prefix: str, payload: str, pid: str = "00002710") -> bytes:
    return (f"[PID={pid} IEXPLORE.EXE] {prefix} {payload} \r\n").encode("ascii")


first = log("TX (app request)", "18 DA 50 F1 22 F1 10")
second = log("PassThruReadMsgs -> delivered", "18 DA F1 50 7F 22 31")
other = log("TX (app request)", "18 DA 50 F1 22 F1 14", "00001828")
past = log("TX (app request)", "18 DA 50 F1 22 DD 02", "00001828")
future = log("TX (app request)", "18 DA 50 F1 22 F1 06")
window = first + second + other
anchor = len(past + window)
full_log = past + window + future

data, file_end, discarded, start = capture(
    io.BytesIO(full_log), end_offset=anchor, window_bytes=len(window)
)
assert file_end == len(full_log)
assert start == len(past)
assert discarded == 0
assert data == window
rows = report(data, "00002710", "cem-ident", expected_tagged=3)
assert "B3A300_COMPLETE_LINES=3" in rows
assert "B3A300_CENSUS_MATCH=TRUE" in rows
assert "B3A300_SELECTED_PID_LINES=2" in rows
assert "B3A298_PID_LINES_IN_WINDOW=2" in rows
assert "B3A298_UDS_F110_TX=1" in rows
assert "B3A298_UDS_F114_TX=0" in rows
assert "B3A298_UDS_22_NRC_31_DELIVERED=1" in rows
assert "B3A300_RESULT=READ_ONLY_COMPLETE" in rows
mismatch = report(data, "00002710", "cem-ident", expected_tagged=4)
assert "B3A300_CENSUS_MATCH=FALSE" in mismatch
assert "B3A300_RESULT=ERROR_CENSUS_MISMATCH" in mismatch
assert not any(line.startswith("B3A298_") for line in mismatch)
missing = report(data, "FEEDBEEF", "cem-ident", expected_tagged=3)
assert "B3A300_RESULT=ERROR_PID_NOT_IN_WINDOW" in missing

lead_partial = past + b"broken-" + window + future
first_byte = len(past) + len(b"broken-")
data, _, discarded, start = capture(
    io.BytesIO(lead_partial), end_offset=len(past) + len(b"broken-") + len(window),
    window_bytes=len(window) + 7)
assert start == len(past)
assert discarded == len(b"broken-") + len(first)
assert data == second + other

# Trim a final partial line when the end-offset bisects its bytes.
truncated = past + first + second[:8] + future
data, _, discarded, _ = capture(
    io.BytesIO(truncated), end_offset=len(past) + len(first) + 8,
    window_bytes=len(first) + 8)
assert data == first
assert discarded == 8
print("B3A300_SYNTHETIC_RECOVERY_REGRESSION=PASS")
