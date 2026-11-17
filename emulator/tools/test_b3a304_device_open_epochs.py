#!/usr/bin/env python3
"""B3A304 synthetic regression: original VIDA PassThruOpen/Close epochs.

No external processes, proprietary traffic, VIN, or filesystem writes.
"""
from pathlib import Path
import runpy

audit = runpy.run_path(
    str(Path(__file__).resolve().with_name(
        "B3A304-Audit-GGD-Device-Open-Epochs.py")),
    run_name="b3a304_synthetic_import",
)["analyze"]


def words(*vals: int) -> bytes:
    return b"".join(v.to_bytes(4, "big") for v in vals)


def entry(label: str, payload: bytes | None = None, pid: str = "00002710") -> bytes:
    hx = "" if payload is None else " " + " ".join(f"{x:02X}" for x in payload) + " "
    return f"[PID={pid} IEXPLORE.EXE] {label}{hx}\r\n".encode("ascii")


def connect(channel: int, serial: int, flags: int = 0x100) -> bytes:
    return entry("J2534 scope channel_connect (BE)",
                 words(channel, 0, serial, 6, 500000, flags, 0, 0))


def ctx(channel: int) -> bytes:
    return entry("TX context channel/protocol/flags/baud/time-us (BE)",
                 words(channel, 6, 0x140, 500000, 123))


def tx(did: str) -> bytes:
    return entry("TX (app request)",
                 bytes.fromhex(f"18 DA 50 F1 22 {did[:2]} {did[2:]}"))


def pos(did: str) -> bytes:
    return entry(f"B3A274 LAB CEM50 GGD {did} synthetic positive",
                 bytes.fromhex(f"22 {did[:2]} {did[2:]}"))


def verify(prelude: bytes, window: bytes, expected: list[str]) -> None:
    start = 500 + len(prelude)
    items = audit(prelude + window, start_offset=500,
                  action_start=start, action_end=start+len(window),
                  pid="00002710", expected_action_lines=len(window.splitlines()))
    for line in expected:
        assert line in items, (line, items)
    assert "B3A304_ACTION_CENSUS_MATCH=TRUE" in items
    assert "B3A304_RESULT=READ_ONLY_COMPLETE" in items
    corrupted = audit(prelude + window, start_offset=500,
                      action_start=start, action_end=start+len(window),
                      pid="00002710", expected_action_lines=900)
    assert "B3A304_RESULT=ERROR_ACTION_CENSUS_MISMATCH" in corrupted
    assert not any(x.startswith("B3A304_GROUP=") for x in corrupted)


# Case 1: different open epochs could explain the contrast if private
# EnableGGDCemLab changed before PassThruOpen reload (not directly logged).
prelude = b"".join((entry("PassThruOpen -> device 1"), connect(1, 9)))
window = b"".join((
    ctx(1), tx("A45F"),
    entry("PassThruClose"),
    entry("PassThruOpen -> device 1"),
    connect(2, 12),
    ctx(2), tx("A45F"), pos("A45F")
))
verify(prelude, window, [
    "B3A304_ACTION_OPEN_EVENTS=1",
    "B3A304_ACTION_CLOSE_EVENTS=1",
    "B3A304_PREWINDOW_OPEN_EVENTS=1",
    "B3A304_ACTION_UNKNOWN_CHANNEL=0",
    "B3A304_DID_A45F_TX=2",
    "B3A304_LAB_A45F_ACTION=1",
    "B3A304_GROUP=epoch:1,channel:1,serial:9,connect_flags:0x00000100,"
    "did:A45F,proto:6,baud:500000,tx_flags:0x00000140,"
    "connect_only_guard:TRUE,tx:1,lab_generated:0",
    "B3A304_GROUP=epoch:2,channel:2,serial:12,connect_flags:0x00000100,"
    "did:A45F,proto:6,baud:500000,tx_flags:0x00000140,"
    "connect_only_guard:TRUE,tx:1,lab_generated:1",
])

# Case 2: single Open epoch, both channels valid. If real data look like
# this, difference cannot be explained by a config reload at PassThruOpen.
prelude = b"".join((entry("PassThruOpen -> device 1"), connect(1, 9)))
window = b"".join((ctx(1), tx("DD02"), connect(2, 12),
                   ctx(2), tx("DD02"), pos("DD02")))
verify(prelude, window, [
    "B3A304_ACTION_OPEN_EVENTS=0",
    "B3A304_ACTION_CLOSE_EVENTS=0",
    "B3A304_DID_DD02_TX=2",
    "B3A304_LAB_DD02_ACTION=1",
    "B3A304_GROUP=epoch:1,channel:1,serial:9,connect_flags:0x00000100,"
    "did:DD02,proto:6,baud:500000,tx_flags:0x00000140,"
    "connect_only_guard:TRUE,tx:1,lab_generated:0",
    "B3A304_GROUP=epoch:1,channel:2,serial:12,connect_flags:0x00000100,"
    "did:DD02,proto:6,baud:500000,tx_flags:0x00000140,"
    "connect_only_guard:TRUE,tx:1,lab_generated:1",
])
print("B3A304_SYNTHETIC_DEVICE_EPOCH_REGRESSION=PASS")
