#!/usr/bin/env python3
"""Read-only verification of an original VIDA 2014D B3A7 ZIP for B3A8.

Does not alter the ZIP, touch VIDA/Registry/J2534, publish raw logs, or
synthesize VIN, ECU replies, FIVE_BAUD_INIT keywords or replay fixtures.
Emits only aggregate metadata, request identifiers, timings and hashes.
"""
from __future__ import annotations
import argparse
from collections import Counter
import configparser
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

EXPECTED_HEAD = "0722b530aa48a7f1790d5f0dd1dddbe790518705"
EXPECTED_DLL_SHA256 = "AFB19B26C3BA6BE11D3ADD321EC7A90BEF4E005F36EC7B963AC0C8F25E4EF210"
EXPECTED_SEQUENCE = [
    ("726", "22F114"), ("40", "B9FB"), ("50", "B9FB"),
    ("50", "B9FB"), ("50", "B9FB"), ("40", "B9FB"),
    ("50", "B9FB"), ("51", "B9F0"),
]
REQUIRED_MEMBERS = {
    "b3a7-arm.json", "b3a7-manifest.json", "B3A7-acceptance.json",
    "virtualcar-exact.ini", "VIDA-original-full.log", "VIDA-since-arm.raw",
    "VirtualCar-original-full.log", "VirtualCar-since-arm.raw",
}
VIDA_REQUEST = re.compile(r"VehComm request: Ecu '([0-9A-F]+)', Message '([0-9A-F]+)'", re.I)
READ_CALL = re.compile(r"PassThruReadMsgs\(\d+, PASSTHRU_MSG, \d+,\s*(\d+)\s*\)")
READ_TIMEOUT = re.compile(r"J2534 function:PassThruReadMsgs failed with return value:ERR_TIMEOUT\b")
PID_LINE = re.compile(r"^\[PID=([0-9A-Fa-f]{8}) ([^\]]+)\] ", re.M)
ABI = re.compile(r"VIDA B3A7 FIVE_BAUD_INIT ABI [^\r\n]*\(BE\) ((?:[0-9A-F]{2} ){47}[0-9A-F]{2})\s*$", re.M)
RX_PACKET = re.compile(r"^.*\[J2534ChannelMana\][^\r\n]*<---", re.M)


class EvidenceError(ValueError):
    """A reproducibility or fail-closed evidence check did not pass."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest().upper()


def _basename(name: str) -> str:
    return name.replace("\\", "/").rsplit("/", 1)[-1]


def _members(z: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    by_name: dict[str, zipfile.ZipInfo] = {}
    for info in z.infolist():
        name = _basename(info.filename)
        if not name:
            continue
        require(name not in by_name, "duplicate archive basename: " + name)
        by_name[name] = info
    require(REQUIRED_MEMBERS <= by_name.keys(), "required original evidence files are missing")
    return by_name


def _abi_fields(text: str) -> list[int]:
    raw = ABI.findall(text)
    require(len(raw) == 1, "exactly one original B3A7 ABI marker required")
    items = bytes.fromhex(raw[0].strip())
    require(len(items) == 48, "invalid B3A7 ABI metadata length")
    return [int.from_bytes(items[i:i + 4], "big") for i in range(0, 48, 4)]


def audit_zip(zip_path: Path) -> dict:
    zip_path = Path(zip_path)
    require(zip_path.is_file(), "ZIP is missing")
    zip_bytes = zip_path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        require(z.testzip() is None, "ZIP CRC failure")
        members = _members(z)
        get = lambda name: z.read(members[name])
        manifest = json.loads(get("b3a7-manifest.json"))
        accepted = json.loads(get("B3A7-acceptance.json"))
        arm = json.loads(get("b3a7-arm.json"))
        require(manifest.get("sourceCommit") == EXPECTED_HEAD, "manifest HEAD mismatch")
        require(accepted.get("sourceHead") == EXPECTED_HEAD and arm.get("head") == EXPECTED_HEAD,
                "acceptance/arm HEAD mismatch")
        require(all(x.get("dllSha256", "").upper() == EXPECTED_DLL_SHA256 for x in
                    (manifest, accepted, arm)), "exact native DLL SHA256 provenance mismatch")
        require(accepted.get("runtimeIdentity") == "CONFIRMED" and
                accepted.get("b3a7ObserverGate") == "B3A7_OBSERVER_CONFIRMED" and
                accepted.get("result") == "OBSERVATION_ONLY_NO_ECU_RX_PROOF", "observer acceptance mismatch")
        require(accepted.get("VIDAReadVinEvent") is True and
                accepted.get("vidaLoadsExactDll") is True and
                accepted.get("unredacted") is True, "original VIDA source identity not confirmed")
        ini = configparser.ConfigParser(interpolation=None, strict=True)
        ini.read_string(get("virtualcar-exact.ini").decode("utf-8-sig"))
        require(all(ini.get("Diagnostics", key, fallback="0").strip() == "1" for key in
                    ("EnableVidaIso9141Lab", "EnableVidaKlineTxAckLab",
                     "EnableVidaFiveBaudObserverLab")), "one of three exact LAB INI gates is off")
        require(ini.getint("D2_40", "B9FBFrameCount", fallback=-1) == 0 and
                ini.getint("D2_50", "B9FBFrameCount", fallback=-1) == 0,
                "tested profile unexpectedly contains D2 B9FB reply fixtures")
        vf, va = get("VIDA-original-full.log"), get("VIDA-since-arm.raw")
        ef, ea = get("VirtualCar-original-full.log"), get("VirtualCar-since-arm.raw")
        require(vf.endswith(va) and ef.endswith(ea), "captured suffix differs from full original log")
        require(len(vf) - len(va) == arm.get("vidaOffset") and
                len(ef) - len(ea) == arm.get("virtualOffset"), "original arm offsets mismatch")
        require(len(va) == accepted.get("newVidaBytes") and
                len(ea) == accepted.get("newVirtualBytes"), "operator byte count mismatch")
        vida, virt = va.decode("utf-8-sig"), ea.decode("utf-8-sig")
        pid_lines = PID_LINE.findall(virt)
        require(len(pid_lines) == len(virt.splitlines()), "unattributed VirtualCar log line")
        pids = {pid for pid, host in pid_lines if host.upper() == "IEXPLORE.EXE"}
        require(len(pids) == 1 and len(pid_lines) == sum(1 for _, host in pid_lines if host.upper() == "IEXPLORE.EXE"),
                "multiple PID/host instances in original VIDA evidence")
        pid = next(iter(pids))
        require([pid] == accepted.get("activeVidaPidHex") and
                len(pid_lines) == accepted.get("selectedSamePidLines"), "same PID evidence mismatch")
        requests = [(a.upper(), b.upper()) for a, b in VIDA_REQUEST.findall(vida)]
        require(requests == EXPECTED_SEQUENCE, "original VIDA request order/count differs from B3A7")
        waits = [int(x) for x in READ_CALL.findall(vida)]
        require(Counter(waits) == Counter({5000: 20, 50: 3, 60: 2, 75: 1, 100: 1}),
                "J2534 ReadMsgs wait histogram mismatch")
        timeouts = len(READ_TIMEOUT.findall(vida))
        require(timeouts == len(waits) == 27, "a read may have succeeded or timeout evidence is incomplete")
        require(not RX_PACKET.search(vida) and "VehComm response:" not in vida,
                "a possible received ECU response requires manual re-review")
        fields = _abi_fields(virt)
        require(fields == [1, 3, 10400, 0, 1, 1, 1, 1, 1, 2, 1, 1],
                "original B3A7 ISO9141 ABI differs from expected source evidence")
        require(virt.count("VIDA B3A7 FIVE_BAUD_INIT original target (1 byte) 51") == 1 and
                virt.count("ISO9141 LAB FIVE_BAUD_INIT: no verified ECU keywords; unsupported") == 1,
                "FIVE_BAUD_INIT target/unsupported status not corroborated")
        ack = {
            "relay_close": virt.count("LOCAL ACK ONLY (NO BUS/ECU TX/RX) 84 40 13 B2 F0 00"),
            "read_b9f0": virt.count("LOCAL ACK ONLY (NO BUS/ECU TX/RX) 83 51 13 B9 F0"),
            "teardown": virt.count("LOCAL ACK ONLY (NO BUS/ECU TX/RX) 82 51 13 A0"),
        }
        require(ack == {"relay_close": 3, "read_b9f0": 1, "teardown": 1},
                "B3A6 original local ACK counts changed")
        require("Could not retrieve VIN from vehicle" in vida and
                accepted.get("originalVidaVinError") is True and
                accepted.get("VINReadSucceeded") == "NOT_PROVEN" and
                accepted.get("authenticECURx") == "NOT_PROVEN",
                "VIN failure or ECU RX status was not confirmed")
        blockers = {
            "p3_f114_no_fixture": virt.count("P3 CEM F114 probe: no configured CEM fixture; no response"),
            "d2_no_validated_fixture": virt.count("P2 D2 read command: no validated response fixture"),
            "d2_strict_route_rejected": virt.count("P2 D2 strict route rejected (no fixture emitted)"),
        }
        require(blockers == {"p3_f114_no_fixture": 1,
                             "d2_no_validated_fixture": 3,
                             "d2_strict_route_rejected": 3},
                "original ECU reply fixture audit has changed")
        return {
            "stage": "B3A8-source-evidence-verification",
            "status": "SOURCE_LOGS_VERIFIED_NO_ECU_REPLY_PROVEN",
            "immutable_source": {"zip_sha256": sha256(zip_bytes),
                                 "original_vida_sha256": sha256(vf),
                                 "original_virtualcar_sha256": sha256(ef),
                                 "vida_since_arm_sha256": sha256(va),
                                 "virtualcar_since_arm_sha256": sha256(ea),
                                 "original_logs_modified": False},
            "runtime": {"head": EXPECTED_HEAD, "staged_dll_sha256_reported": EXPECTED_DLL_SHA256,
                        "pid_hex": pid, "virtualcar_same_pid_lines": len(pid_lines),
                        "dll_binary_present_in_zip": False},
            "readvin": {"requests": [{"ecu": a, "service": b,
                                       "verified_ecu_response": False,
                                       "replay_approved": False} for a, b in requests],
                        "read_calls": len(waits), "read_timeout_count": timeouts,
                        "wait_ms_histogram": {str(k): n for k, n in sorted(Counter(waits).items())},
                        "positive_rx_packet_lines": 0,
                        "five_baud_target": "0x51", "five_baud_output_capacity": fields[9],
                        "five_baud_unsupported": True,
                        "local_j2534_ack_only": ack,
                        "missing_fixture_markers": blockers,
                        "vin_read": "FAILED", "authentic_ecu_rx": "NOT_PROVEN"},
            "conclusion": "Cannot validate original XC90 V8 VIN; no reply bytes or keywords were obtained.",
            "replay_approved": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_zip", type=Path)
    parser.add_argument("--out", type=Path, help="write aggregate JSON, never original OEM bytes")
    args = parser.parse_args()
    try:
        report = audit_zip(args.evidence_zip)
    except (EvidenceError, OSError, ValueError, zipfile.BadZipFile, UnicodeError) as e:
        parser.exit(2, f"B3A8 EVIDENCE FAIL: {e}\n")
    result = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.write_text(result, encoding="utf-8")
    print("B3A8 PASS: source ZIP/offsets/PID/8 requests/27 timeouts/5 ACKs; ECU RX NOT PROVEN")
    if not args.out:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
