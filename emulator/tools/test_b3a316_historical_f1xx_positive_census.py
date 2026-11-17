#!/usr/bin/env python3
"""Synthetic-only B3A316 F1xx positive inventory, no original file or registry."""
from pathlib import Path
import runpy

tool = runpy.run_path(str(Path(__file__).resolve().with_name(
    "B3A316-Audit-VIDA-F1xx-Historical-Positives.py")),
    run_name="b3a316_synthetic_import")
analyze = tool["analyze_lines"]
pid = "00001130"
otherpid = "00002710"


def row(text, proc=pid):
    return f"[PID={proc} IEXPLORE.EXE] {text}\r\n".encode("ascii")


def hx(prefix, data):
    return prefix + " " + data.hex(" ").upper()


def j2534_tx(identifier, did):
    return hx("TX (app request)", identifier.to_bytes(4, "big") +
              bytes.fromhex("22" + did))


def j2534_rx(identifier, body):
    return hx("PassThruReadMsgs -> delivered",
              identifier.to_bytes(4, "big") + bytes.fromhex(body))


# Old emulator epoch, separate 11-bit CEM. This is not physical ECU evidence.
pre = b"".join((
    row(r"Active INI: C:\synthetic\old\virtualcar.ini", otherpid),
    row("PassThruOpen -> device 1", otherpid),
    row(j2534_tx(0x726, "F110"), otherpid),
    row(j2534_rx(0x72E, "62F1101234"), otherpid),
    row("PassThruClose", otherpid),
    row(r"Active INI: C:\synthetic\lab277\virtualcar.ini"),
    row("PassThruOpen -> device 1"),
))
action = b"".join((
    row(j2534_tx(0x18DA50F1, "F110")),
    row(j2534_rx(0x18DAF150, "7F2231")),
    row(j2534_tx(0x18DA50F1, "F114")),
    row(j2534_rx(0x18DAF150, "62F114AABB")),
    row(j2534_tx(0x18DA50F1, "F106")),
    row(j2534_rx(0x18DAF150, "62F106123456")),
    row(j2534_rx(0x18DAF150, "62F11000")),
    row("PassThruReadMsgs -> delivered XX"),
))
data = pre + action
origins = {
    r"c:\synthetic\lab277": "J2534 Diagnostic Lab 277",
    r"c:\synthetic\old": "J2534 Diagnostic Lab",
}
result = analyze(
    data.splitlines(keepends=True), end=len(data), source_dirs=origins,
    anchor_before=len(pre), anchor_after=len(data), anchor_pid=pid,
    expected_anchor_lines=8)
for expected in (
    "B3A316_ANCHOR_CENSUS_MATCH=TRUE",
    "B3A316_DID=route:CEM29,did:F110,tx:1,positive_delivered:1",
    "B3A316_DID=route:CEM29,did:F106,tx:1,positive_delivered:1",
    "B3A316_DID=route:CEM29,did:F114,tx:1,positive_delivered:1",
    "B3A316_DID=route:CEM11,did:F110,tx:1,positive_delivered:1",
    "B3A316_DID=route:CEM11,did:F106,tx:0,positive_delivered:0",
    "B3A316_ROUTE=route:CEM29,nrc31_delivered:1,nrc_did_attribution:NOT_PROVEN",
    "B3A316_POSITIVE_GROUP=route:CEM29,did:F114,origin:J2534 Diagnostic Lab 277,count:1",
    "B3A316_POSITIVE_GROUP=route:CEM11,did:F110,origin:J2534 Diagnostic Lab,count:1",
    "B3A316_RESULT=READ_ONLY_COMPLETE",
):
    assert expected in result, (expected, result)
assert not any("C:\\synthetic" in item or "62F114AABB" in item for item in result)

failed = analyze(
    data.splitlines(keepends=True), end=len(data), source_dirs=origins,
    anchor_before=len(pre), anchor_after=len(data), anchor_pid=pid,
    expected_anchor_lines=9)
assert "B3A316_ANCHOR_CENSUS_MATCH=FALSE" in failed
assert "B3A316_RESULT=ERROR_ANCHOR_CENSUS" in failed
assert not any(item.startswith("B3A316_POSITIVE_GROUP") for item in failed)

# A read ending within the final line is invalid, rather than a hidden partial.
truncated = analyze(
    data.splitlines(keepends=True), end=len(data)-1, source_dirs=origins,
    anchor_before=len(pre), anchor_after=len(data), anchor_pid=pid,
    expected_anchor_lines=8)
assert "B3A316_RESULT=ERROR_ANCHOR_CENSUS" in truncated

print("B3A316_SYNTHETIC_F1XX_HISTORICAL_CENSUS_REGRESSION=PASS")
