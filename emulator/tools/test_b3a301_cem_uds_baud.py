#!/usr/bin/env python3
"""B3A301 pure offline synthetic regression: J2534 TX context vs CEM DID baud.

No private logs, original VIDA, CarCom, DLL invocation or file writes.
"""
from pathlib import Path
import runpy

analyze = runpy.run_path(
    str(Path(__file__).resolve().with_name(
        "B3A301-Audit-CEM-GGD-UDS-Baud-Window.py")),
    run_name="b3a301_test_import",
)["audit"]


def hexes(raw: bytes) -> str:
    # Native DLL emits one ASCII space after every output byte.
    return " ".join(f"{x:02X}" for x in raw) + " "


def line(message: str, data: bytes | None = None, pid: str = "00002710") -> str:
    suffix = (" " + hexes(data)) if data is not None else ""
    return f"[PID={pid} IEXPLORE.EXE] {message}{suffix}\r\n"


def be32(x: int) -> bytes:
    return x.to_bytes(4, "big")


def ctx(baud: int, flags: int = 0x100, protocol: int = 6) -> str:
    meta = b"".join(map(be32, (1, protocol, flags, baud, 123456)))
    return line("TX context channel/protocol/flags/baud/time-us (BE)", meta)


def tx(did: str) -> str:
    return line("TX (app request)", bytes.fromhex("18 DA 50 F1 22 " +
                                                  did[:2] + " " + did[2:]))


def rx(data: str) -> str:
    return line("PassThruReadMsgs -> delivered",
                bytes.fromhex("18 DA F1 50 " + data))


sample = "".join((
    ctx(500000), tx("A45F"),
    line("B3A274 LAB CEM50 GGD A45F synthetic positive"),
    rx("62 A4 5F 04"),
    ctx(250000), tx("A45F"), rx("7F 22 31"),
    ctx(500000), tx("F110"), rx("7F 22 31"),
    ctx(250000), tx("DD02"), rx("7F 22 31"),
    ctx(500000), tx("F114"), rx("7F 22 31"),
    ctx(500000), tx("F106"), rx("7F 22 31"),
    ctx(500000), tx("DD02"),
    line("B3A274 LAB CEM50 GGD DD02 synthetic positive"),
    rx("62 DD 02 32"),
    ctx(500000), tx("F110").replace("00002710", "00001828"),
))
out = analyze(sample, "00002710")
for expected in (
    "B3A301_CEM22_TOTAL_TX=7",
    "B3A301_CEM22_TX_WITHOUT_CONTEXT=0",
    "B3A301_INVALID_TX_CONTEXT=0",
    "B3A301_TX=did:A45F,baud:250000,proto:6,flag29:TRUE,count:1",
    "B3A301_TX=did:A45F,baud:500000,proto:6,flag29:TRUE,count:1",
    "B3A301_DID=A45F,tx:2,positive_delivered:1",
    "B3A301_DID=DD02,tx:2,positive_delivered:1",
    "B3A301_DID=F110,tx:1,positive_delivered:0",
    "B3A301_DID=F114,tx:1,positive_delivered:0",
    "B3A301_DID=F106,tx:1,positive_delivered:0",
    "B3A301_NRC=service:22,code:31,delivered:5",
    "B3A301_A45F_LAB_POSITIVE_GENERATED=1",
    "B3A301_DD02_LAB_POSITIVE_GENERATED=1",
    "B3A301_NRC_TO_DID_ATTRIBUTION=NOT_PROVEN",
    "B3A301_RESULT=READ_ONLY_COMPLETE",
):
    assert expected in out, (expected, out)
print("B3A301_SYNTHETIC_BAUD_REGRESSION=PASS")
