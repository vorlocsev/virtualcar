#!/usr/bin/env python3
"""B3A305 in-memory synthetic tests: epoch RX and hidden INI path comparison."""
from pathlib import Path
import runpy

audit = runpy.run_path(
    str(Path(__file__).resolve().with_name(
        "B3A305-Audit-GGD-Epoch-RX-And-Profile.py")),
    run_name="b3a305_test_import",
)["audit"]


def be(*vals: int) -> bytes:
    return b"".join(i.to_bytes(4, "big") for i in vals)


def line(label: str, data: bytes | None = None, pid: str = "00002710") -> bytes:
    suffix = "" if data is None else " " + " ".join(f"{b:02X}" for b in data) + " "
    return f"[PID={pid} IEXPLORE.EXE] {label}{suffix}\r\n".encode("ascii")


def connect(ch: int, serial: int) -> bytes:
    return line("J2534 scope channel_connect (BE)",
                be(ch, 0, serial, 6, 500000, 0x100, 0, 0))


def rx(channel: int, payload: str) -> bytes:
    return b"".join((
        line("RX context channel/protocol/status/baud/time-us (BE)",
             be(channel, 6, 0x100, 500000, 100)),
        line("PassThruReadMsgs -> delivered",
             bytes.fromhex("18 DA F1 50 " + payload)),
    ))


def initialization(config: str) -> bytes:
    return b"".join((
        line("VirtualCar DLL initialized (synthetic regression only)"),
        line("Active INI: " + config),
        line("PassThruOpen -> device 1"),
    ))


# Two independent Open epochs before original CEM_IDENT, then a third.
# The active path can be identical even if configuration *contents* changed
# while VIDA was running; a positive cannot validate original OEM semantics.
private_name = r"C:\synthetic\virtualcar.ini"
prelude = b"".join((
    initialization(private_name),
    line("PassThruClose"),
    initialization(private_name),
    connect(1, 9),
))
window = b"".join((
    rx(1, "7F 22 31"),
    line("PassThruClose"),
    initialization(private_name),
    connect(2, 12),
    rx(2, "62 A4 5F 04"),
    rx(2, "62 DD 02 32"),
    rx(2, "7F 22 31"),
))
start = 128 + len(prelude)
result = audit(prelude + window, start_offset=128, action_start=start,
               action_end=start+len(window), pid="00002710",
               expected_action_lines=len(window.splitlines()))
for expected in (
    "B3A305_ACTION_CENSUS_MATCH=TRUE",
    "B3A305_PREWINDOW_OPENS=2",
    "B3A305_ACTION_OPENS=1",
    "B3A305_ACTION_CLOSES=1",
    "B3A305_EPOCH2_VS_EPOCH3_ACTIVE_INI_PATH=SAME",
    "B3A305_CEM22_NRC31_TOTAL=2",
    "B3A305_CEM22_POS_A45F_TOTAL=1",
    "B3A305_CEM22_POS_DD02_TOTAL=1",
    "B3A305_CEM22_RX_MISSING_CONTEXT=0",
    "B3A305_RX=epoch:2,channel:1,serial:9,proto:6,baud:500000,type:NRC31,count:1",
    "B3A305_RX=epoch:3,channel:2,serial:12,proto:6,baud:500000,type:NRC31,count:1",
    "B3A305_RX=epoch:3,channel:2,serial:12,proto:6,baud:500000,type:POS_A45F,count:1",
    "B3A305_RESULT=READ_ONLY_COMPLETE",
):
    assert expected in result, (expected, result)

changed = window.replace(
    ("Active INI: " + private_name).encode("ascii"),
    b"Active INI: C:\\synthetic\\another\\virtualcar.ini",
)
changed_res = audit(prelude + changed, start_offset=128, action_start=start,
                    action_end=start+len(changed), pid="00002710",
                    expected_action_lines=len(changed.splitlines()))
assert "B3A305_EPOCH2_VS_EPOCH3_ACTIVE_INI_PATH=DIFFERENT" in changed_res
assert not any(private_name in x for x in result + changed_res)

invalid = audit(prelude + window, start_offset=128, action_start=start,
                action_end=start+len(window), pid="00002710",
                expected_action_lines=999)
assert "B3A305_RESULT=ERROR_ACTION_CENSUS_MISMATCH" in invalid
assert not any(x.startswith("B3A305_RX=epoch:") for x in invalid)
print("B3A305_SYNTHETIC_EPOCH_RX_PROFILE_REGRESSION=PASS")
