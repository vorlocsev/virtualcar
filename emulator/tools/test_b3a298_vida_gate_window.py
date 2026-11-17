#!/usr/bin/env python3
"""Offline synthetic regression for B3A298 single GUI-action window analysis.

No original VIDA/CarCom/proprietary data, process interaction, or file writes.
"""
from pathlib import Path
import runpy

script = Path(__file__).resolve().with_name("B3A298-VIDA-Gate-Window.py")
module = runpy.run_path(str(script), run_name="b3a298_import_only")
analyze = module["analyze"]
hex_suffix = module["hex_suffix"]


def line(prefix: str, hex_bytes: str, pid: str = "00001828") -> str:
    return f"[PID={pid} IEXPLORE.EXE] {prefix} {hex_bytes} \r\n"


sample = "".join((
    line("TX (app request)", "18 DA 50 F1 22 F1 10"),
    line("PassThruReadMsgs -> delivered", "18 DA F1 50 7F 22 31"),
    line("TX (app request)", "18 DA 50 F1 22 A4 5F"),
    line("PassThruReadMsgs -> delivered", "18 DA F1 50 62 A4 5F 04"),
    line("TX (app request)", "00 0F FF FE CB 50 B9 FB"),
    line("P2 D2 read-only recorded frames staged", "CB 50 B9 FB"),
    line("P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE)",
         "00 00 00 01 00 00 00 01 00 00 00 01 00 00 00 00 00 00 00 00"),
    line("P2 D2 strict route rejected (no fixture emitted)", "CB 50 B9 FB"),
    line("P2 D2 command: no recorded ECU fixture for target", "CB 29 B9 F0"),
    line("TX (app request)", "18 DA 50 F1 22 F1 06", pid="DEADBEEF"),
))

assert hex_suffix("TX (app request) 18 DA 50 F1 22 F1 10 ",
                  "TX (app request)") == bytes.fromhex("18 DA 50 F1 22 F1 10")
assert hex_suffix("TX (app request) 18 DA 50 F1 ZZ",
                  "TX (app request)") is None
rows = analyze(sample, "00001828", "cem-ident")
assert "B3A298_PID_LINES_IN_WINDOW=9" in rows
assert "B3A298_UDS_F110_TX=1" in rows
assert "B3A298_UDS_F110_POSITIVE_DELIVERED=0" in rows
assert "B3A298_UDS_22_NRC_31_DELIVERED=1" in rows
assert "B3A298_UDS_A45F_TX=1" in rows
assert "B3A298_UDS_A45F_POSITIVE_DELIVERED=1" in rows
assert "B3A298_UDS_F106_TX=0" in rows
assert "B3A298_D2_CEM50_B9FB_TX=1" in rows
assert "B3A298_D2_CEM50_B9FB_STAGED=1" in rows
assert "B3A298_D2_CEM50_B9FB_ROUTE_REJECTED=1" in rows
assert "B3A298_D2_OTHER_NO_ECU_FIXTURE=1" in rows
assert "B3A298_D2_DELIVERED_FRAME_META=1" in rows
assert "B3A298_GUI_ACCEPTANCE=NEEDS_SEPARATE_SCREENSHOT" in rows
assert "B3A298_RESULT=READ_ONLY_COMPLETE" in rows
print("B3A298_SYNTHETIC_WINDOW_REGRESSION=PASS")
