#!/usr/bin/env python3
"""B3A299 regression on synthetic PID-tagged strings; no file access/writes."""
from pathlib import Path
import runpy

tool = runpy.run_path(
    str(Path(__file__).resolve().with_name("B3A299-Audit-VIDA-Log-PID-Census.py")),
    run_name="b3a299_test_import",
)
summary = tool["summary"]
scan_bytes = tool["scan_bytes"]


sample = (
    b"[PID=00001828 IEXPLORE.EXE] synthetic message A\r\n"
    b"[PID=0000A1B2 IEXPLORE.EXE] synthetic message B\r\n"
    b"[PID=0000A1B2 IEXPLORE.EXE] synthetic message C\r\n"
    b"[PID=00003333 VIDASERVICE.EXE] synthetic message D\r\n"
    b"[PID=00003333 VIDASERVICE.EXE] synthetic message E\r\n"
    b"partial or nonnative line\r\n"
)
found, total, untagged = scan_bytes(sample)
assert total == 6
assert untagged == 1
assert found[("00001828", "IEXPLORE.EXE")] == 1
assert found[("0000A1B2", "IEXPLORE.EXE")] == 2
assert found[("00003333", "VIDASERVICE.EXE")] == 2
rows = summary(sample, "00001828")
assert "B3A299_IEXPLORE_UNIQUE_PIDS=2" in rows
assert "B3A299_IEXPLORE_TOTAL_LINES=3" in rows
assert "B3A299_PREVIOUS_PID_LINES=1" in rows
assert "B3A299_IEXPLORE_PID=0000A1B2,lines:2" in rows
assert "B3A299_HOST=VIDASERVICE.EXE,lines:2" in rows
assert "B3A299_STATUS=MULTIPLE_IEXPLORE_PIDS" in rows
assert "B3A299_RESULT=READ_ONLY_COMPLETE" in rows

changed = summary(
    b"[PID=0000A1B2 iexplore.exe] synthetic\r\n", "00001828"
)
assert "B3A299_STATUS=DIFFERENT_IEXPLORE_PID_FOUND" in changed
assert "B3A299_IEXPLORE_PID=0000A1B2,lines:1" in changed

no_ie = summary(
    b"[PID=00005555 VIDASERVICE.EXE] synthetic\r\n", "00001828"
)
assert "B3A299_STATUS=NO_IEXPLORE_TAGS" in no_ie

none = summary(b"non-natively formatted\r\n", "00001828")
assert "B3A299_STATUS=NO_RECOGNIZED_PID_TAGS" in none
print("B3A299_SYNTHETIC_PID_CENSUS_REGRESSION=PASS")
