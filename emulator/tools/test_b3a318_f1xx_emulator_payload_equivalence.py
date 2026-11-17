#!/usr/bin/env python3
"""Synthetic-only B3A318 regression: no VIDA, J2534, DLL, registry or logs."""
from pathlib import Path
import runpy

tool=runpy.run_path(str(Path(__file__).resolve().with_name(
    "B3A318-Audit-F1xx-Emulator-Payload-Equivalence.py")),
    run_name="b3a318_test_import")
analyze=tool["analyze"]
p1="00000420"
p2="00001130"


def row(value,pid):
    return f"[PID={pid} IEXPLORE.EXE] {value}\r\n".encode("ascii")


def positive(id,did,data,pid):
    pkt=id.to_bytes(4,"big")+bytes.fromhex("62"+did)+data
    return row("PassThruReadMsgs -> delivered "+pkt.hex(" ").upper(),pid)


a=b"A"*45
b=b"B"*45
c=b"C"*17
d=b"D"*24
pre=[
    row(r"Active INI: C:\synthetic\older\virtualcar.ini",p1),
    row("PassThruOpen -> device 1",p1),
    positive(0x18DAF150,"F110",d,p1),
    positive(0x18DAF150,"F110",d,p1),
    row("PassThruClose",p1),
]
action=[
    row(r"Active INI: C:\synthetic\f114\virtualcar.ini",p2),
    row("PassThruOpen -> device 1",p2),
    positive(0x18DAF150,"F114",a,p2),
    positive(0x18DAF150,"F114",a,p2),
    positive(0x72E,"F114",a,p2),
    positive(0x72E,"F114",b,p2),
    positive(0x72E,"F114",c,p2),
]
data=b"".join(pre+action)
start=len(b"".join(pre))
source_dirs={
    r"c:\synthetic\older":"UNREGISTERED_OR_CHANGED",
    r"c:\synthetic\f114":"J2534 Diagnostic Lab F114",
}
expected={
    ("CEM29","F110"):2,("CEM29","F106"):0,("CEM29","F114"):2,
    ("CEM11","F110"):0,("CEM11","F106"):0,("CEM11","F114"):3,
}
got=analyze(data.splitlines(keepends=True),end=len(data),
            before=start,anchor_pid=p2,anchor_lines=len(action),
            expected=expected,source_dirs=source_dirs)
for result in (
    "B3A318_ANCHOR_CENSUS_MATCH=TRUE",
    "B3A318_POSITIVE_CENSUS_MATCH=TRUE",
    "B3A318_PAYLOAD_GROUP=route:CEM29,did:F110,data_len:24,origin:UNREGISTERED_OR_CHANGED,positive_count:2,distinct_byte_patterns:1,most_repeated_pattern_count:2,all_fields_identical:TRUE",
    "B3A318_PAYLOAD_GROUP=route:CEM29,did:F114,data_len:45,origin:J2534 Diagnostic Lab F114,positive_count:2,distinct_byte_patterns:1,most_repeated_pattern_count:2,all_fields_identical:TRUE",
    "B3A318_PAYLOAD_GROUP=route:CEM11,did:F114,data_len:45,origin:J2534 Diagnostic Lab F114,positive_count:2,distinct_byte_patterns:2,most_repeated_pattern_count:1,all_fields_identical:FALSE",
    "B3A318_PAYLOAD_GROUP=route:CEM11,did:F114,data_len:17,origin:J2534 Diagnostic Lab F114,positive_count:1,distinct_byte_patterns:1,most_repeated_pattern_count:1,all_fields_identical:TRUE",
    "B3A318_F114_CROSSROUTE_LENGTH=45,CEM29_variants:1,CEM11_variants:2,shared_exact_byte_patterns:1",
    "B3A318_RESULT=READ_ONLY_COMPLETE",
):
    assert result in got, (result,got)
assert not any("C:\\synthetic" in line or "AAAA" in line or "BBBB" in line for line in got)

bad=analyze(data.splitlines(keepends=True),end=len(data),
            before=start,anchor_pid=p2,anchor_lines=len(action)+1,
            expected=expected,source_dirs=source_dirs)
assert "B3A318_ANCHOR_CENSUS_MATCH=FALSE" in bad
assert "B3A318_RESULT=ERROR_ANCHOR_OR_POSITIVE_CENSUS" in bad
assert not any(x.startswith("B3A318_PAYLOAD_GROUP") for x in bad)

mismatched=analyze(data.splitlines(keepends=True),end=len(data),
            before=start,anchor_pid=p2,anchor_lines=len(action),
            expected={**expected,("CEM29","F110"):3},source_dirs=source_dirs)
assert "B3A318_POSITIVE_CENSUS_MATCH=FALSE" in mismatched

truncated=analyze(data.splitlines(keepends=True),end=len(data)-1,
            before=start,anchor_pid=p2,anchor_lines=len(action),
            expected=expected,source_dirs=source_dirs)
assert "B3A318_RESULT=ERROR_ANCHOR_OR_POSITIVE_CENSUS" in truncated

print("B3A318_SYNTHETIC_EMULATOR_PAYLOAD_EQUIVALENCE_REGRESSION=PASS")
