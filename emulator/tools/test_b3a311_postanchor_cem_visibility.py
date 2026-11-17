#!/usr/bin/env python3
"""B3A311 synthetic, privacy-safe test; no registry/files/VIDA touched."""
from pathlib import Path
import runpy

script = Path(__file__).resolve().with_name(
    "B3A311-Audit-PostAnchor-VIDA-CEM-Visibility.py")
mod = runpy.run_path(str(script), run_name="b3a311_synthetic_test")
scan = mod["scan"]
packet = mod["packet"]

def row(pid: str, msg: str) -> bytes:
    return f"[PID={pid} IEXPLORE.EXE] {msg}\r\n".encode("ascii")

def hx(label: str, data: bytes) -> str:
    return label + " " + data.hex(" ").upper()

def context(proto=6, flags=0x140, baud=500000) -> bytes:
    return b"".join(n.to_bytes(4, "big") for n in (1, proto, flags, baud, 0))

txctx = "TX context channel/protocol/flags/baud/time-us (BE)"
tx = "TX (app request)"
rx = "PassThruReadMsgs -> delivered"
p1 = "00002710"
p2 = "00002711"
data = b"".join([
    row(p1, r"Active INI: C:\synthetic\selected\virtualcar.ini"),
    row(p1, "VirtualCar DLL initialized (synthetic)"),
    row(p1, "PassThruOpen -> device 1"),
    row(p1, hx(txctx, context())),
    row(p1, hx(tx, bytes.fromhex("18da50f122a45f"))),
    row(p1, "B3A274 LAB CEM50 GGD A45F synthetic positive"),
    row(p1, hx(rx, bytes.fromhex("18daf15062a45f04"))),
    row(p1, hx(txctx, context())),
    row(p1, hx(tx, bytes.fromhex("18da50f122dd02"))),
    row(p1, "B3A274 LAB CEM50 GGD DD02 synthetic positive"),
    row(p1, hx(rx, bytes.fromhex("18daf15062dd0232"))),
    row(p1, hx(txctx, context())),
    row(p1, hx(tx, bytes.fromhex("18da50f122f110"))),
    row(p1, hx(rx, bytes.fromhex("18daf1507f2231"))),
    row(p2, r"Active INI: C:\synthetic\old\virtualcar.ini"),
    row(p2, "PassThruOpen -> device 1"),
    row(p2, hx(txctx, context(baud=250000))),
    row(p2, "INTERVENING_UNRELATED_LOG_LINE"),
    row(p2, hx(tx, bytes.fromhex("18da50f122f114"))),
    row(p2, hx(rx, bytes.fromhex("18daf1507f2231"))),
])
assert packet(hx(tx, bytes.fromhex("18da50f122f114")).encode(),
              tx.encode()) == bytes.fromhex("18da50f122f114")
assert packet(b"TX (app request) NOTHEX", tx.encode()) is None
rows = scan(data, selected_dir=r"c:\synthetic\selected")
check = (
    "B3A311_IEXPLORE_PID_COUNT=2",
    "B3A311_PID=00002710,lines:14,opens:1,ini_to_open:1,"
    "selected_origin_opens:1,other_origin_opens:0,unknown_origin_opens:0,"
    "cem22_tx:3,cem22_tx_iso15765_500k_29bit:3,nrc31:1",
    "B3A311_PID_DID=00002710,did:A45F,tx:1,positive_delivered:1,lab_generated:1",
    "B3A311_PID_DID=00002710,did:DD02,tx:1,positive_delivered:1,lab_generated:1",
    "B3A311_PID_DID=00002710,did:F110,tx:1,positive_delivered:0,lab_generated:0",
    "B3A311_PID=00002711,lines:6,opens:1,ini_to_open:1,"
    "selected_origin_opens:0,other_origin_opens:1,unknown_origin_opens:0,"
    "cem22_tx:1,cem22_tx_iso15765_500k_29bit:0,nrc31:1",
    "B3A311_NO_PER_REQUEST_NRC_ATTRIBUTION=TRUE",
    "B3A311_CEM_VISIBLE=USER_OBSERVATION_ONLY",
    "B3A311_RESULT=READ_ONLY_COMPLETE",
)
for expected in check:
    assert expected in rows, (expected, rows)
assert not any("C:\\synthetic" in line or "18DA50F1" in line for line in rows)

unknown = scan(data, selected_dir=None)
assert "B3A311_SELECTED_ADAPTER_DIRECTORY_FROM_CURRENT_REGISTRY=UNRESOLVED" in unknown
assert any("unknown_origin_opens:1" in item for item in unknown)
print("B3A311_SYNTHETIC_POSTANCHOR_CEM_REGRESSION=PASS")
