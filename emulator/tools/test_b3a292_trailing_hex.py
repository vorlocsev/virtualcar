#!/usr/bin/env python3
"""Regression for native VirtualCar hex_bytes() trailing ASCII space.

Pure offline synthetic log only; no VIDA, VIN, SQL, J2534, or private fixtures.
Run: py -3 emulator/tools/test_b3a292_trailing_hex.py
"""
from pathlib import Path
import runpy

audit_module = runpy.run_path(
    str(Path(__file__).resolve().with_name("B3A292-Audit-VIDA-D2-Route-Outcomes.py")),
    run_name="b3a292_imported_for_tests",
)
audit = audit_module["audit"]
bytes_if_hex = audit_module["bytes_if_hex"]

def h(data: bytes) -> str:
    # Exactly mimic hex_bytes: one trailing space after EVERY emitted byte.
    return " ".join(f"{b:02X}" for b in data) + " "

def line(label: str, data: bytes) -> str:
    return "[PID=00001828 IEXPLORE.EXE] " + label + " " + h(data) + "\r\n"

def be32(v: int) -> bytes:
    return v.to_bytes(4, "big")

def context(target: int, opcode: int, baud: int) -> bytes:
    return b"".join(map(be32, (1, target, 0xB9, opcode, baud)))

scope = b"".join(map(be32, (1, 0, 6, 5, 500000, 0x100, 0, 0)))
logs = [
    line("J2534 scope channel_connect (BE)", scope),
    line("P2 D2 service context channel/target/service/opcode/baud (BE)", context(0x50, 0xFB, 500000)),
    line("P2 D2 read-only recorded frames staged", bytes.fromhex("CB 50 B9 FB")),
    line("P2 D2 service context channel/target/service/opcode/baud (BE)", context(0x40, 0xFB, 125000)),
    line("P2 D2 read command: no validated response fixture", bytes.fromhex("CB 40 B9 FB")),
    line("P2 D2 service context channel/target/service/opcode/baud (BE)", context(0x50, 0xFB, 125000)),
    line("P2 D2 strict route rejected (no fixture emitted)", bytes.fromhex("CB 50 B9 FB")),
    line("P2 D2 service context channel/target/service/opcode/baud (BE)", context(0x67, 0xF0, 125000)),
    line("P2 D2 command: no recorded ECU fixture for target", bytes.fromhex("CB 67 B9 F0")),
]

assert bytes_if_hex("CB 40 B9 FB ", 4) == bytes.fromhex("CB 40 B9 FB")
assert bytes_if_hex("CB 40 B9 FB Z", 4) is None
assert bytes_if_hex("CB 40 B9", 4) is None
out = audit(logs, "00001828")
assert "B3A292_PID_LINES=9" in out
for kind in ("STAGED", "NO_FIXTURE", "ROUTE_REJECTED", "NO_ECU_FIXTURE"):
    assert f"B3A292_{kind}_TOTAL=1" in out, (kind, out)
assert "B3A292_INVALID_CONTEXT=0" in out
assert "B3A292_MALFORMED_OUTCOME=0" in out
assert "B3A292_OUTCOME_WITHOUT_MATCHING_CONTEXT=0" in out
assert any("B3A292_STAGED=target:50,service:B9,opcode:FB,baud:500000,serial:6,count:1" == s for s in out)
assert any("B3A292_NO_FIXTURE=target:40,service:B9,opcode:FB,baud:125000,serial:6,count:1" == s for s in out)
assert any("B3A292_ROUTE_REJECTED=target:50,service:B9,opcode:FB,baud:125000,serial:6,count:1" == s for s in out)
print("B3A292_TRAILING_HEX_REGRESSION=PASS")
