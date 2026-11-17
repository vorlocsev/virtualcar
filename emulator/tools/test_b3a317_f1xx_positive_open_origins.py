#!/usr/bin/env python3
"""B3A317 in-memory synthetic regression: no real VIDA, registry, DLL or private log."""
from pathlib import Path
import runpy

mod = runpy.run_path(str(Path(__file__).resolve().with_name(
    "B3A317-Audit-F1xx-Positive-Open-Origins.py")),run_name="b3a317_test")
audit = mod["audit"]


def row(msg, pid):
    return f"[PID={pid} IEXPLORE.EXE] {msg}\r\n".encode("ascii")


def frame(prefix, address, uds):
    b = address.to_bytes(4,"big")+bytes.fromhex(uds)
    return prefix+" "+b.hex(" ").upper()


p1, p2 = "00000010","00000011"
pre_rows = [
    row(r"Active INI: C:\synthetic\old\virtualcar.ini",p1),
    row("VirtualCar DLL initialized",p1),
    row("PassThruOpen -> device 1",p1),
    row(frame("TX (app request)",0x18DA50F1,"22F110"),p1),
    row("Read-only configured ECU DID reply (not OEM verified) F1 10",p1),
    row(frame("PassThruReadMsgs -> delivered",0x18DAF150,"62F110AABB"),p1),
    row("PassThruClose",p1),
]
action_rows = [
    row(r"Active INI: C:\synthetic\f114\virtualcar.ini",p2),
    row("VirtualCar DLL initialized",p2),
    row("PassThruOpen -> device 1",p2),
    row(frame("TX (app request)",0x18DA50F1,"22F114"),p2),
    row(frame("TX (app request)",0x726,"22F114"),p2),
    row("P3 CEM F114 VIN reply (synthetic lab data)",p2),
    row(frame("PassThruReadMsgs -> delivered",0x18DAF150,"62F114AABB"),p2),
    row(frame("PassThruReadMsgs -> delivered",0x72E,"62F114111213"),p2),
]
pre=b"".join(pre_rows)
action=b"".join(action_rows)
data=pre+action
source_dirs={
    r"c:\synthetic\old":"UNREGISTERED_OR_CHANGED",
    r"c:\synthetic\f114":"J2534 Diagnostic Lab F114",
}
expected={
    ("CEM29","F110"):1, ("CEM29","F106"):0, ("CEM29","F114"):1,
    ("CEM11","F110"):0, ("CEM11","F106"):0, ("CEM11","F114"):1,
}
results=audit(
    data.splitlines(keepends=True),source_dirs=source_dirs,
    end=len(data),before=len(pre),anchor_pid=p2,
    anchor_lines=len(action_rows),expected=expected)
for needed in (
    "B3A317_ANCHOR_CENSUS_MATCH=TRUE",
    "B3A317_FULL_LOG_POSITIVE_CENSUS_MATCH=TRUE",
    "B3A317_POSITIVE_EPOCH_GROUPS=3",
    "B3A317_POS_EPOCH=pid:00000010,epoch:1,origin:UNREGISTERED_OR_CHANGED,route:CEM29,did:F110,tx_in_epoch:1,positive_in_epoch:1,data_len_min:2,data_len_max:2,configured_did_marker_in_epoch:1,synthetic_f114_marker_in_epoch:0",
    "B3A317_POS_EPOCH=pid:00000011,epoch:1,origin:J2534 Diagnostic Lab F114,route:CEM29,did:F114,tx_in_epoch:1,positive_in_epoch:1,data_len_min:2,data_len_max:2,configured_did_marker_in_epoch:0,synthetic_f114_marker_in_epoch:1",
    "B3A317_POS_EPOCH=pid:00000011,epoch:1,origin:J2534 Diagnostic Lab F114,route:CEM11,did:F114,tx_in_epoch:1,positive_in_epoch:1,data_len_min:3,data_len_max:3,configured_did_marker_in_epoch:0,synthetic_f114_marker_in_epoch:1",
    "B3A317_RESULT=READ_ONLY_COMPLETE"
):
    assert needed in results,(needed,results)
assert not any("C:\\synthetic" in item or "AABB" in item for item in results)

wrong_anchor=audit(data.splitlines(keepends=True),source_dirs=source_dirs,
    end=len(data),before=len(pre),anchor_pid=p2,
    anchor_lines=len(action_rows)+1,expected=expected)
assert "B3A317_ANCHOR_CENSUS_MATCH=FALSE" in wrong_anchor
assert "B3A317_RESULT=ERROR_CENSUS_OR_TRUNCATED_LOG" in wrong_anchor
assert not any(s.startswith("B3A317_POS_EPOCH=") for s in wrong_anchor)

wrong_positive=audit(data.splitlines(keepends=True),source_dirs=source_dirs,
    end=len(data),before=len(pre),anchor_pid=p2,
    anchor_lines=len(action_rows),expected={**expected,("CEM29","F106"):1})
assert "B3A317_FULL_LOG_POSITIVE_CENSUS_MATCH=FALSE" in wrong_positive
assert "B3A317_RESULT=ERROR_CENSUS_OR_TRUNCATED_LOG" in wrong_positive

truncated=audit(data.splitlines(keepends=True),source_dirs=source_dirs,
    end=len(data)-1,before=len(pre),anchor_pid=p2,
    anchor_lines=len(action_rows),expected=expected)
assert "B3A317_ANCHOR_CENSUS_MATCH=FALSE" in truncated
assert "B3A317_RESULT=ERROR_CENSUS_OR_TRUNCATED_LOG" in truncated

print("B3A317_SYNTHETIC_F1XX_OPEN_PROVENANCE_REGRESSION=PASS")
