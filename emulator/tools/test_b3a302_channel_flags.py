#!/usr/bin/env python3
"""Synthetic B3A302 regression: CONNECT flags are distinct from TX flags.

Runs on in-memory synthetic log lines, no VIN, original VIDA, CAN trace,
private profile, CarCom, file modification or external process interaction.
"""
from pathlib import Path
import runpy

audit = runpy.run_path(
    str(Path(__file__).resolve().with_name(
        "B3A302-Audit-CEM-GGD-Channel-Flags.py")), run_name="b3a302_test_import"
)["audit"]


def be32(*values: int) -> bytes:
    return b"".join(v.to_bytes(4, "big") for v in values)


def line(label: str, body: bytes | None = None, pid: str = "00002710") -> str:
    hx = "" if body is None else " " + " ".join(f"{b:02X}" for b in body) + " "
    return f"[PID={pid} IEXPLORE.EXE] {label}{hx}\r\n"


def connect(ch: int, serial: int, flags: int) -> str:
    return line("J2534 scope channel_connect (BE)",
                be32(ch, 0, serial, 6, 500000, flags, 0, 0))


def disconnect(ch: int, serial: int, flags: int) -> str:
    return line("J2534 scope channel_disconnect (BE)",
                be32(ch, 0, serial, 6, 500000, flags, 0, 0))


def ctx(ch: int, flags: int = 0x100) -> str:
    return line("TX context channel/protocol/flags/baud/time-us (BE)",
                be32(ch, 6, flags, 500000, 500))


def tx(did: str) -> str:
    return line("TX (app request)", bytes.fromhex(
        f"18 DA 50 F1 22 {did[:2]} {did[2:]}"))


log = "".join((
    # CONNECT allows GGD lab; same TX flag in each path.
    connect(1, 6, 0x100),
    ctx(1), tx("A45F"),
    line("B3A274 LAB CEM50 GGD A45F synthetic positive",
         bytes.fromhex("22 A4 5F")),
    ctx(1), tx("DD02"),
    line("B3A274 LAB CEM50 GGD DD02 synthetic positive",
         bytes.fromhex("22 DD 02")),
    disconnect(1, 6, 0x100),

    # Same channel ID and TX flags, but CONNECT *lacks* 29-bit bit.
    connect(1, 7, 0),
    ctx(1), tx("A45F"),
    ctx(1), tx("DD02"),
    line("Unmatched request ID / protocol, no response",
         bytes.fromhex("18 DA 50 F1 22 DD 02")),
    disconnect(1, 7, 0),

    # Same channel id, CONNECT flags include forbidden extra bits.
    connect(1, 8, 0x300),
    ctx(1), tx("A45F"),
    disconnect(1, 8, 0x300),

    # Window begins mid-connection for channel2: do NOT assume from TxFlags.
    ctx(2), tx("A45F"),
    # Background log from another PID must not contaminate counts.
    line("B3A274 LAB CEM50 GGD A45F synthetic positive", pid="00001828"),
))
out = audit(log, "00002710")
assert "B3A302_DID_A45F_TX=4" in out
assert "B3A302_DID_DD02_TX=2" in out
assert "B3A302_LAB_A45F_GENERATED=1" in out
assert "B3A302_LAB_DD02_GENERATED=1" in out
assert "B3A302_UNKNOWN_CONNECT_CONTEXT=1" in out
assert "B3A302_CHANNEL_CONTEXT_CONTRADICTION=0" in out
assert "B3A302_CONNECT=3" in out
assert "B3A302_DISCONNECT=3" in out
assert any("did:A45F,channel:1,serial:6,connect_flags:0x00000100,"
           "tx_flags:0x00000100,baud:500000,protocol:6,lab_guard:TRUE,"
           "tx:1,lab_generated:1" in s for s in out)
assert any("did:A45F,channel:1,serial:7,connect_flags:0x00000000,"
           "tx_flags:0x00000100,baud:500000,protocol:6,lab_guard:FALSE,"
           "tx:1,lab_generated:0" in s for s in out)
assert any("did:A45F,channel:1,serial:8,connect_flags:0x00000300,"
           "tx_flags:0x00000100,baud:500000,protocol:6,lab_guard:FALSE,"
           "tx:1,lab_generated:0" in s for s in out)
assert any("did:A45F,channel:2,serial:UNKNOWN,connect_flags:UNKNOWN,"
           "tx_flags:0x00000100,baud:500000,protocol:6,lab_guard:UNKNOWN,"
           "tx:1,lab_generated:0" in s for s in out)
assert "B3A302_GUARD=CHANNEL_CONNECT_FLAGS_NOT_TX_FLAGS" in out
assert "B3A302_RESULT=READ_ONLY_COMPLETE" in out
print("B3A302_SYNTHETIC_CHANNEL_FLAGS_REGRESSION=PASS")
