#!/usr/bin/env python3
"""Synthetic-only B3A312 regression: two original VIDA J2534 Open epochs.

No real VIDA, J2534 driver, registry, DLL, INI, private files or vehicle.
"""
from pathlib import Path
import runpy

tool = runpy.run_path(
    str(Path(__file__).resolve().with_name(
        "B3A312-Audit-Fresh-VIDA-Open-Epochs.py")),
    run_name="b3a312_synthetic",
)
analyze = tool["analyze"]
parse_packet = tool["parse_packet"]
PID = "00001130"


def row(s: str, pid: str = PID) -> bytes:
    return f"[PID={pid} IEXPLORE.EXE] {s}\r\n".encode("ascii")


def hexline(label: str, payload: bytes) -> str:
    return label + " " + payload.hex(" ").upper()


def context():
    return b"".join(
        n.to_bytes(4, "big") for n in (1, 6, 0x140, 500000, 0))


def request(did: str):
    return bytes.fromhex("18da50f122"+did)


def response(did: str):
    return bytes.fromhex("18daf15062"+did+"04")


txctx = "TX context channel/protocol/flags/baud/time-us (BE)"
tx = "TX (app request)"
rx = "PassThruReadMsgs -> delivered"
rows = [
    row(r"Active INI: C:\synthetic\old\virtualcar.ini"),
    row("VirtualCar DLL initialized (synthetic)"),
    row("PassThruOpen -> device 1"),
]
for did in ("A45F", "DD02"):
    rows.extend((
        row(hexline(txctx, context())),
        row(hexline(tx, request(did))),
        row(hexline(rx, response(did))),
    ))
rows.extend((
    row("PassThruClose"),
    row(r"Active INI: C:\synthetic\selected\virtualcar.ini"),
    row("VirtualCar DLL initialized (synthetic)"),
    row("PassThruOpen -> device 1"),
))
for did in ("A45F", "DD02"):
    rows.extend((
        row(hexline(txctx, context())),
        row(hexline(tx, request(did))),
        row("B3A274 LAB CEM50 GGD " + did + " synthetic positive"),
        row(hexline(rx, response(did))),
    ))
for did in ("F110", "F114", "F106"):
    rows.extend((
        row(hexline(txctx, context())),
        row(hexline(tx, request(did))),
        row(hexline(rx, bytes.fromhex("18daf1507f2231"))),
    ))

data = b"".join(rows)
assert parse_packet(hexline(tx, request("F110")).encode(), tx.encode()) == request("F110")
assert parse_packet(b"TX (app request) ZZZ", tx.encode()) is None
found = analyze(
    data, pid=PID, selected_dir=r"c:\synthetic\selected",
    expected_tagged_lines=len(rows),
)
for expected in (
    "B3A312_CENSUS_MATCH=TRUE",
    "B3A312_OPEN_EPOCHS=2",
    "B3A312_EPOCH=1,origin:OTHER,ini_logged:TRUE,init_linked:TRUE,close:1,"
    "cem22_tx:2,tx_iso15765_500k_29bit:2,tx_no_context:0,tx_bad_context:0,"
    "nrc31:0,other_nrc:0",
    "B3A312_EPOCH=2,origin:SELECTED,ini_logged:TRUE,init_linked:TRUE,close:0,"
    "cem22_tx:5,tx_iso15765_500k_29bit:5,tx_no_context:0,tx_bad_context:0,"
    "nrc31:3,other_nrc:0",
    "B3A312_EPOCH_DID=1,did:A45F,tx:1,positive_delivered:1,lab_generated:0",
    "B3A312_EPOCH_DID=2,did:A45F,tx:1,positive_delivered:1,lab_generated:1",
    "B3A312_EPOCH_DID=2,did:DD02,tx:1,positive_delivered:1,lab_generated:1",
    "B3A312_EPOCH_DID=2,did:F110,tx:1,positive_delivered:0,lab_generated:0",
    "B3A312_EPOCH_DID=2,did:F114,tx:1,positive_delivered:0,lab_generated:0",
    "B3A312_EPOCH_DID=2,did:F106,tx:1,positive_delivered:0,lab_generated:0",
    "B3A312_RESULT=READ_ONLY_COMPLETE",
):
    assert expected in found, (expected, found)
assert not any("C:\\synthetic" in line for line in found)
assert not any("18DAF150" in line for line in found)

bad_census = analyze(data, pid=PID, selected_dir=None, expected_tagged_lines=len(rows)+1)
assert "B3A312_CENSUS_MATCH=FALSE" in bad_census
assert "B3A312_RESULT=ERROR_ACTION_CENSUS_OR_PID" in bad_census

unknown = analyze(data, pid=PID, selected_dir=None, expected_tagged_lines=len(rows))
assert "B3A312_OPEN_EPOCHS=2" in unknown
assert any("origin:UNKNOWN" in s for s in unknown)

print("B3A312_SYNTHETIC_FRESH_VIDA_OPEN_EPOCHS_REGRESSION=PASS")
