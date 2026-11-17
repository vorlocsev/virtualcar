#!/usr/bin/env python3
"""Synthetic-only B3A313 state recovery regression; no Windows or registry I/O."""
from pathlib import Path
import runpy

script = Path(__file__).resolve().with_name(
    "B3A313-Recover-Prewindow-Active-J2534-Origin.py")
tool = runpy.run_path(str(script), run_name="b3a313_test_import")
recover = tool["resolve_pre_origin"]
p = "00001130"


def row(text: str, pid: str = p) -> bytes:
    return f"[PID={pid} IEXPLORE.EXE] {text}\r\n".encode("ascii")


def hexline(prefix: str, data: bytes) -> str:
    return prefix + " " + data.hex(" ").upper()


provider = [
    ("J2534 Diagnostic Lab CEM Status", r"C:\synthetic\older\VirtualCarJ2534.dll"),
    ("J2534 Diagnostic Lab 277", r"C:\synthetic\selected\VirtualCarJ2534.dll"),
]
pre = b"".join((
    row(r"Active INI: C:\synthetic\older\virtualcar.ini"),
    row("VirtualCar DLL initialized (synthetic)"),
    row("PassThruOpen -> device 1"),
))
action = b"".join((
    row(hexline("TX (app request)", bytes.fromhex("18DA50F122A45F"))),
    row(hexline("PassThruReadMsgs -> delivered", bytes.fromhex("18DAF15062A45F04"))),
    row(hexline("TX (app request)", bytes.fromhex("18DA50F122DD02"))),
    row(hexline("PassThruReadMsgs -> delivered", bytes.fromhex("18DAF15062DD0232"))),
    row(r"Active INI: C:\synthetic\selected\virtualcar.ini"),
    row("PassThruOpen -> device 1"),
    row(hexline("TX (app request)", bytes.fromhex("18DA50F122F110"))),
))
base = 50000
start = base + len(pre)
end = start+len(action)
rows = recover(
    pre+action, data_begin=base, action_start=start,
    action_end=end, pid=p, expected_action_lines=7,
    reg_status="READ_OK", providers=provider,
    selected_label="J2534 Diagnostic Lab 277")
for expected in (
    "B3A313_PREWINDOW_OPEN_COUNT=1",
    "B3A313_PREWINDOW_CLOSE_COUNT=0",
    "B3A313_PREWINDOW_ACTIVE_AT_ACTION_START=OPEN",
    "B3A313_PREWINDOW_LAST_OPEN_INI_RECORDED=TRUE",
    "B3A313_PREWINDOW_LAST_OPEN_INIT_LINKED=TRUE",
    "B3A313_PREWINDOW_CURRENT_REGISTRY_MATCHES=1",
    "B3A313_PREWINDOW_CURRENT_PROVIDER_LABEL=J2534 Diagnostic Lab CEM Status",
    "B3A313_PREWINDOW_SAME_CURRENT_DIRECTORY_AS_SELECTED=FALSE",
    "B3A313_ACTION_CENSUS_MATCH=TRUE",
    "B3A313_ACTION_OPEN_COUNT=1",
    "B3A313_PREFIX_BEFORE_FIRST_ACTION_OPEN_TX_A45F=1",
    "B3A313_PREFIX_BEFORE_FIRST_ACTION_OPEN_TX_DD02=1",
    "B3A313_PREFIX_BEFORE_FIRST_ACTION_OPEN_RX_POS_A45F=1",
    "B3A313_PREFIX_BEFORE_FIRST_ACTION_OPEN_RX_POS_DD02=1",
    "B3A313_RESULT=READ_ONLY_COMPLETE",
):
    assert expected in rows, (expected, rows)
assert not any("C:\\synthetic" in item for item in rows)

# Closed before the BEFORE offset -> never infer an active provider.
closed = recover(pre+row("PassThruClose")+action,
                 data_begin=base, action_start=start+len(row("PassThruClose")),
                 action_end=end+len(row("PassThruClose")),
                 pid=p, expected_action_lines=7, reg_status="READ_OK",
                 providers=provider, selected_label="J2534 Diagnostic Lab 277")
assert "B3A313_PREWINDOW_ACTIVE_AT_ACTION_START=CLOSED" in closed
assert "B3A313_PREWINDOW_CURRENT_PROVIDER_LABEL=UNRESOLVED" in closed
assert "B3A313_RESULT=READ_ONLY_COMPLETE" in closed

# Insufficient lookback -> unknown, not a false negative.
missing = recover(action, data_begin=start, action_start=start,
                  action_end=end, pid=p, expected_action_lines=7,
                  reg_status="READ_OK", providers=provider,
                  selected_label="J2534 Diagnostic Lab 277")
assert "B3A313_PREWINDOW_ACTIVE_AT_ACTION_START=NOT_FOUND_IN_LOOKBACK" in missing

# Exact census mismatch is rejected.
bad = recover(pre+action, data_begin=base, action_start=start,
              action_end=end, pid=p, expected_action_lines=8,
              reg_status="READ_OK", providers=provider,
              selected_label="J2534 Diagnostic Lab 277")
assert "B3A313_ACTION_CENSUS_MATCH=FALSE" in bad
assert "B3A313_RESULT=ERROR_ACTION_CENSUS" in bad

print("B3A313_SYNTHETIC_PREWINDOW_ORIGIN_REGRESSION=PASS")
