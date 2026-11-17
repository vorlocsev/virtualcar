#!/usr/bin/env python3
"""B3A306 fully synthetic regression; no private paths, files, or writes."""
from pathlib import Path
import runpy

tool = runpy.run_path(
    str(Path(__file__).resolve().with_name(
        "B3A306-Audit-Active-GGD-Profile-Origins.py")),
    run_name="b3a306_test_import",
)
scan = tool["scan"]
path_comparison = tool["path_comparison"]
evaluate = tool["evaluate_current"]
source_num = tool["source_num"]
source_hex = tool["source_hex"]


def row(label: str, pid: str = "00002710") -> bytes:
    return f"[PID={pid} IEXPLORE.EXE] {label}\r\n".encode("ascii")


def init_ini(path: str) -> bytes:
    return b"".join((
        row("VirtualCar DLL initialized (synthetic)"),
        row("Active INI: " + path),
        row("PassThruOpen -> device 1"),
    ))


ep2 = r"C:\virtual\alpha\virtualcar.ini"
ep3 = r"C:\virtual\beta\virtualcar.ini"
pre = init_ini(ep2) + row("PassThruClose") + init_ini(ep2)
action = init_ini(ep3) + row("TX (app request)", pid="00F00F00")
start = 1000 + len(pre)
paths, report = scan(
    pre + action, begin=1000, action_start=start,
    action_end=start+len(action), pid="00002710",
    expected_action_lines=3,
)
assert "B3A306_ACTION_CENSUS_MATCH=TRUE" in report
assert "B3A306_PREWINDOW_OPENS=2" in report
assert "B3A306_ACTION_OPENS=1" in report
assert "B3A306_INIT_LINKED_TO_OPEN=3" in report
assert "B3A306_EPOCH=2,path_logged:TRUE" in report
assert path_comparison(paths) == "DIFFERENT"
assert not any(ep2 in value or ep3 in value for value in report)
assert path_comparison({
    2: r"C:\VIRTUAL\ALPHA\VIRTUALCAR.INI".encode("ascii"),
    3: r"c:/virtual/alpha/virtualcar.ini".encode("ascii"),
}) == "SAME"

missing_paths, error_report = scan(
    pre + action, begin=1000, action_start=start,
    action_end=start+len(action), pid="00002710",
    expected_action_lines=4,
)
assert missing_paths == {}
assert "B3A306_RESULT=ERROR_ACTION_CENSUS_MISMATCH" in error_report

# Same exact C/INI defaults and hex vs decimal semantics; never print values.
default = evaluate(lambda section, key, fallback: fallback)
assert default == {
    "lab_enabled": "FALSE",
    "cem29_route_present": "FALSE",
    "matching_route_count": "0",
    "lab_and_route_ready": "FALSE",
}
values = {
    ("Diagnostics", "EnableGGDCemLab"): "1",
    ("Vehicle", "ECUCount"): "2",
    ("ECU1", "RequestId"): "18DA50F1",
    ("ECU1", "ResponseId"): "18DAF150",
}
getter = lambda section, key, fallback: values.get((section, key), fallback)
ready = evaluate(getter)
assert ready["lab_enabled"] == "TRUE"
assert ready["cem29_route_present"] == "TRUE"
assert ready["matching_route_count"] == "1"
assert ready["lab_and_route_ready"] == "TRUE"
assert source_num("0x20", 0) == 32
assert source_num("20", 0) == 20
assert source_num("0xZZ", 7) == 7
assert source_hex("18DA50F1", 0) == 0x18DA50F1
assert source_hex("0x18DA50F1", 0) == 0x18DA50F1
assert source_hex("ZZ", 9) == 9
print("B3A306_SYNTHETIC_ACTIVE_PROFILE_ORIGINS_REGRESSION=PASS")
