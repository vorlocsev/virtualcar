#!/usr/bin/env python3
"""B3A303 synthetic-only regression: pre-window J2534 ConnectFlags history.

No real VIDA, raw vehicle frames, personal data, external processes or writes.
"""
from pathlib import Path
import io
import runpy

root = Path(__file__).resolve().parent
mod = runpy.run_path(
    str(root / "B3A303-Recover-Prewindow-J2534-Connect.py"),
    run_name="b3a303_test_import",
)
capture = runpy.run_path(
    str(root / "B3A300-Recover-VIDA-Gate-Window.py"),
    run_name="b3a303_capture_import",
)["capture_historic"]
scan = mod["scan"]


def be(*numbers: int) -> bytes:
    return b"".join(v.to_bytes(4, "big") for v in numbers)


def entry(label: str, payload: bytes, pid: str = "00002710") -> bytes:
    return (
        f"[PID={pid} IEXPLORE.EXE] {label} "
        + " ".join(f"{x:02X}" for x in payload) + " \r\n"
    ).encode("ascii")


def conn(ch: int, serial: int, flags: int) -> bytes:
    return entry("J2534 scope channel_connect (BE)",
                 be(ch, 0, serial, 6, 500000, flags, 0, 0))


def disc(ch: int, serial: int, flags: int) -> bytes:
    return entry("J2534 scope channel_disconnect (BE)",
                 be(ch, 0, serial, 6, 500000, flags, 0, 0))


# Channel 1 created *before* the original action window. It is reused under
# a new serial and different ConnectFlags. A fresh unrelated channel 2 is
# opened and closed; previous PID must not alter this host's session record.
prelude = b"".join((
    conn(1, 3, 0x100),
    disc(1, 3, 0x100),
    conn(1, 11, 0),
    conn(2, 12, 0x100),
    disc(2, 12, 0x100),
    conn(1, 99, 0x100).replace(b"00002710", b"00001828"),
))

result = scan(prelude.decode("latin-1"), "00002710", 1)
for expected in (
    "B3A303_PREWINDOW_PID_LINES=5",
    "B3A303_SELECTED_CONNECT_EVENTS=2",
    "B3A303_SELECTED_DISCONNECT_EVENTS=1",
    "B3A303_LAST_SELECTED_EVENT=CONNECT",
    "B3A303_LAST_SELECTED_SERIAL=11",
    "B3A303_SELECTED_CHANNEL_ACTIVE_AT_WINDOW_START=TRUE",
    "B3A303_SELECTED_PROTOCOL=6",
    "B3A303_SELECTED_BAUD=500000",
    "B3A303_SELECTED_CONNECT_FLAGS=0x00000000",
    "B3A303_CONNECT_ONLY_GGD_GUARD=FALSE",
    "B3A303_OUTCOME=LIVE_CONNECT_FOUND",
    "B3A303_RESULT=READ_ONLY_COMPLETE",
):
    assert expected in result, (expected, result)

# A later matching disconnect must invalidate the prior session.
closed = scan((prelude + disc(1, 11, 0)).decode("latin-1"),
              "00002710", 1)
assert "B3A303_OUTCOME=NO_LIVE_CONNECT_IN_SCANNED_PREWINDOW" in closed
assert "B3A303_CONNECT_ONLY_GGD_GUARD=UNKNOWN" in closed

# Missing earlier CONNECT must stay unknown, not inherit TxFlags.
missing = scan(entry("TX context channel/protocol/flags/baud/time-us (BE)",
                     be(1, 6, 0x100, 500000, 0)).decode("latin-1"),
               "00002710", 1)
assert "B3A303_SELECTED_CONNECT_FLAGS=UNKNOWN" in missing

# The historical boundary can split a log record; discard its incomplete
# last line. Future append bytes must not affect the anchored prior window.
partial = b"[PID=00002710 IEXPLORE.EXE] deliberately split"
append_after = b"later unrelated appended data\r\n"
full = prelude + partial + append_after
prior, full_end, dropped, start = capture(
    io.BytesIO(full), end_offset=len(prelude) + len(partial),
    window_bytes=len(prelude) + len(partial),
)
assert prior == prelude
assert dropped == len(partial)
assert start == 0
assert full_end == len(full)
print("B3A303_SYNTHETIC_PREWINDOW_CONNECT_REGRESSION=PASS")
