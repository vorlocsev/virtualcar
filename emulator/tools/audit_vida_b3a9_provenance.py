#!/usr/bin/env python3
"""B3A9: fail-closed provenance gate for original Volvo VIDA/DiCE ECU captures.

Never synthesizes/replays ECU messages and never modifies or anonymizes the
original capture. A structurally valid capture remains PENDING HUMAN REVIEW.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

MAX_BYTES = 64 * 1024 * 1024
MAX_FRAMES = 64
B3A8_STATUS = "SOURCE_LOGS_VERIFIED_NO_ECU_REPLY_PROVEN"
REQUESTS = (("726", "22F114"), ("40", "B9FB"), ("50", "B9FB"),
            ("51", "B9F0"))
HEADER = re.compile(rb"\bPassThru(Write|Read)Msgs\(\)\s+msg\[0\]\.Data\s*=\s*\[([^\]]+)\]")
OCTET = re.compile(rb"\s*0x([0-9a-fA-F]{1,2})\s*")
CLOCK = re.compile(rb"^(\d\d):(\d\d):(\d\d),(\d{3})\b")
DIGEST = re.compile(r"^[0-9A-Fa-f]{64}$")

class EvidenceError(ValueError):
    pass

def require(ok, reason):
    if not ok:
        raise EvidenceError(reason)

def sha(raw):
    return hashlib.sha256(raw).hexdigest().upper()

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def gap_report(b3a8):
    require(b3a8.get("status") == B3A8_STATUS and b3a8.get("replay_approved") is False,
            "upstream B3A8 proof boundary is not verified")
    readvin = b3a8.get("readvin", {})
    require(readvin.get("read_timeout_count") == 27 and
            readvin.get("positive_rx_packet_lines") == 0 and
            readvin.get("authentic_ecu_rx") == "NOT_PROVEN", "upstream source RX state changed")
    observed = readvin.get("requests", [])
    require(len(observed) == 8 and all(r.get("verified_ecu_response") is False and
                                          r.get("replay_approved") is False for r in observed),
            "B3A8 requests have received new evidence; re-audit before continuing")
    counts = Counter((r.get("ecu"), r.get("service")) for r in observed)
    require(set(counts) <= set(REQUESTS) and counts == Counter({("726", "22F114"): 1,
                      ("40", "B9FB"): 2, ("50", "B9FB"): 4, ("51", "B9F0"): 1}),
            "B3A8 request scope or route differs")
    return {"stage": "B3A9", "status": "AWAIT_AUTHENTIC_ECU_CAPTURE",
            "source_stage": "B3A8", "original_vida_observed_requests": 8,
            "read_timeouts": 27, "candidate_routes": [
                {"ecu": ecu, "service": service, "attempts": counts[(ecu, service)],
                 "original_b3a7_ecu_rx": "NOT_OBSERVED", "capture_candidate": "NONE",
                 "replay_approved": False} for ecu, service in REQUESTS],
            "vin_acceptance": "NOT_PROVEN", "replay_approved": False}

def clock_ms(line):
    m = CLOCK.match(line)
    if not m:
        return None
    h, n, s, ms = map(int, m.groups())
    require(h < 24 and n < 60 and s < 60, "invalid captured time")
    return ((h * 60 + n) * 60 + s) * 1000 + ms

def parse_event(lines, record, direction):
    require(isinstance(record, dict) and isinstance(record.get("line"), int),
            "missing original line number")
    index = record["line"]
    require(1 <= index <= len(lines), "source line outside original file")
    raw = lines[index - 1]
    require(record.get("line_sha256", "").upper() == sha(raw),
            "original event line SHA256 mismatch")
    m = HEADER.search(raw)
    require(m is not None and m.group(1) == direction, "original J2534 direction mismatch")
    tokens = m.group(2).split(b",")
    if tokens and not tokens[-1].strip():
        tokens.pop()
    require(5 <= len(tokens) <= 4128 and all(OCTET.fullmatch(t) for t in tokens),
            "malformed original J2534 message bytes")
    message = bytes(int(OCTET.fullmatch(t).group(1), 16) for t in tokens)
    return {"line": index, "bytes": message, "ms": clock_ms(raw)}

def evaluate_capture(manifest, raw):
    """Shape checks only. Even a matching shape CANNOT authorize ECU replay."""
    try:
        require(manifest.get("schema_version") == 1, "unknown capture manifest schema")
        src = manifest["source"]
        require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_BYTES,
                "raw file missing or too large")
        require(src.get("sha256", "").upper() == sha(raw) and
                src.get("size_bytes") == len(raw), "original raw capture SHA256/size mismatch")
        require(src.get("raw_unchanged") is True, "original capture must be unchanged")
        require(src.get("origin") == "original_vehicle_dice", "source is not original vehicle DiCE")
        require(src.get("format") == "dice_j2534_text", "unknown source J2534 format")
        require(src.get("transformation") == "none", "source capture was transformed")
        v = manifest["vehicle"]
        require(v.get("make") == "Volvo" and v.get("model") == "XC90" and
                v.get("platform") == "P2" and v.get("model_year") == 2009 and
                v.get("engine") == "V8", "donor or model-year mismatch: not XC90 V8 2009 P2")
        require(v.get("identity_basis") == "original_vehicle_record" and
                DIGEST.fullmatch(v.get("identity_record_sha256", "")),
                "source vehicle identity record absent")
        route = manifest["route"]
        require(route.get("ecu") == "50" and route.get("service") == "B9FB" and
                route.get("protocol") == "CAN" and route.get("baud_bps") in (125000, 250000, 500000),
                "out-of-scope ECU/service/protocol/baud; this gate only checks 50:B9FB CAN")
        events = manifest["events"]
        lines = raw.splitlines(keepends=True)
        tx = parse_event(lines, events["request"], b"Write")
        rx_records = events["responses"]
        require(isinstance(rx_records, list) and 2 <= len(rx_records) <= MAX_FRAMES,
                "not a bounded multi-frame B9FB response")
        rx = [parse_event(lines, obj, b"Read") for obj in rx_records]
        require(all(tx["line"] < x["line"] for x in rx) and
                all(x["line"] < y["line"] for x, y in zip(rx, rx[1:])),
                "request/response source order invalid")
        req = tx["bytes"]
        require(len(req) >= 8 and int.from_bytes(req[:4], "big") == 0x000FFFFE and
                req[4:8] == bytes.fromhex("CB 50 B9 FB"), "captured request isn't 50:B9FB")
        payloads = []
        can_ids = set()
        for event in rx:
            msg = event["bytes"]
            require(len(msg) == 12, "multi-frame D2 CAN RX must have four-byte ID plus eight bytes")
            can_id = int.from_bytes(msg[:4], "big")
            require(can_id in (0x01000003, 0x01200003),
                    "reply response ID not one of observed P2 target-50 candidates")
            can_ids.add(can_id)
            payloads.append(msg[4:])
        require(len(can_ids) == 1, "CAN RX response IDs mixed between frames")
        require(payloads[0][:4] == bytes.fromhex("8F 50 F9 FB"),
                "missing source-backed B9FB response opener")
        require(payloads[-1][0] == 0x4F, "missing final D2 B9FB frame marker")
        for i, frame in enumerate(payloads[1:-1]):
            require(frame[0] == 0x08 + (i + 1) % 8,
                    "missing, reordered or duplicated D2 consecutive frame")
        require(all(x["ms"] is not None for x in [tx] + rx),
                "source timestamps are required for routing review")
        stamps = [x["ms"] for x in [tx] + rx]
        elapsed = [(b - a) % (24*3600*1000) for a, b in zip(stamps, stamps[1:])]
        require(all(delta <= 30000 for delta in elapsed),
                "response timestamps are unrelated or too far apart")
        return {"status": "STRUCTURE_ONLY_PENDING_INDEPENDENT_REVIEW",
                "replay_approved": False, "payload_released": False,
                "original_source_sha256": sha(raw),
                "source_line_count": len(lines),
                "request_line": tx["line"], "reply_frame_count": len(rx),
                "response_can_id": f"0x{next(iter(can_ids)):08X}",
                "vehicle_claim": "XC90 V8 2009 P2 (manifest assertion only)",
                "remaining_evidence": "Independent vehicle/ECU/protocol validation and human approval required"}
    except (KeyError, TypeError, AttributeError, EvidenceError) as e:
        return {"status": "REJECTED", "reason": str(e),
                "replay_approved": False, "payload_released": False}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--b3a8-report", type=Path, required=True)
    p.add_argument("--manifest", type=Path)
    p.add_argument("--raw-capture", type=Path)
    p.add_argument("--out", type=Path)
    args = p.parse_args(argv)
    if bool(args.manifest) != bool(args.raw_capture):
        p.error("--manifest and --raw-capture must be supplied together")
    try:
        upstream = gap_report(load_json(args.b3a8_report))
        if args.manifest:
            capture = args.raw_capture.read_bytes()
            result = {"upstream": upstream, "candidate": evaluate_capture(load_json(args.manifest), capture)}
        else:
            result = upstream
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        p.exit(2, f"B3A9 FAIL-CLOSED: {exc}\n")
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out and args.out.exists():
        p.exit(2, "B3A9 FAIL-CLOSED: refusing to overwrite any existing output or source file\n")
    if args.out:
        with args.out.open("x", encoding="utf-8") as dest:
            dest.write(text)
    print("B3A9", result.get("candidate", result).get("status"), "REPLAY NOT APPROVED")
    if not args.out:
        print(text)
    return 0 if "candidate" not in result or result["candidate"]["status"] != "REJECTED" else 2

if __name__ == "__main__":
    sys.exit(main())
