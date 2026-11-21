#!/usr/bin/env python3
"""Read-only, paired append-window evidence for original VIDA and virtual J2534.

No VIDA/J2534 execution, raw line export, vehicle identity assertion or DLL load.
Run baseline before one owner-controlled GUI attempt and delta afterwards.
Keep the private baseline and report OUTSIDE the repository.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from audit_j2534_connect import audit as audit_connect
from audit_j2534_discovery import audit as audit_discovery

SCHEMA = "virtualcar-private-vida-j2534-window-v1"
REPORT = "virtualcar-vida-j2534-append-evidence-v1"
MAX_SOURCE = 2 * 1024 ** 3
MAX_APPEND = 16 * 1024 ** 2
MAX_LINE = 512
def _repository_root(script_path):
    """Protect a real checkout, not an arbitrary standalone Downloads copy."""
    script = Path(script_path).resolve()
    if script.parent.name != "tools" or script.parent.parent.name != "emulator":
        return None
    root = script.parent.parent.parent
    return root if (root / "README.md").is_file() else None


ROOT = _repository_root(__file__)
PREFIX = re.compile(r"^\[PID=[0-9a-fA-F]{8} ([A-Za-z0-9_.-]{1,48})\] ")
VIDA_TERMS = {
    "passthru_open": "PassThruOpen".lower(),
    "passthru_connect": "PassThruConnect".lower(),
    "passthru_write": "PassThruWriteMsgs".lower(),
    "passthru_read": "PassThruReadMsgs".lower(),
    "get_script": "GetScript".lower(),
    "read_vin_literal": "ReadVin".lower(),
    "tx_arrow": "--->", "rx_arrow": "<---",
}
VIRTUAL_TERMS = {
    "dll_initialized": "VirtualCar DLL initialized",
    "open_success": "PassThruOpen -> device 1",
    "close": "PassThruClose",
    "app_tx_logged": "TX (app request)",
    "rx_delivered_logged": "PassThruReadMsgs -> delivered",
    "kline_local_ack": "VIDA B3A6 KLINE exact original write LOCAL ACK ONLY (NO BUS/ECU TX/RX)",
}


def _file_id(path):
    return hashlib.sha256(str(path.resolve()).casefold().encode("utf-8")).hexdigest()


def _digest(handle, length):
    h = hashlib.sha256()
    while length:
        chunk = handle.read(min(length, 1024 * 1024))
        if not chunk:
            raise ValueError("source changed while hashing")
        h.update(chunk)
        length -= len(chunk)
    return h.hexdigest()


def _snapshot(path):
    if not path.is_file():
        return {"present": False, "bytes": 0, "sha256": None, "newline": True,
                "source_id": _file_id(path)}
    before = path.stat()
    if not 0 <= before.st_size <= MAX_SOURCE:
        raise ValueError("source too large")
    with path.open("rb") as stream:
        digest = _digest(stream, before.st_size)
        stream.seek(max(0, before.st_size - 1))
        newline = not before.st_size or stream.read(1) == b"\n"
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("source changed during baseline")
    return {"present": True, "bytes": before.st_size, "sha256": digest,
            "newline": newline, "source_id": _file_id(path)}


def _append(path, state):
    if set(state) != {"present", "bytes", "sha256", "newline", "source_id"}:
        raise ValueError("invalid source baseline")
    if state["source_id"] != _file_id(path) or type(state["bytes"]) is not int:
        raise ValueError("source path changed")
    if type(state["present"]) is not bool or type(state["newline"]) is not bool:
        raise ValueError("invalid source types")
    if state["present"] and (type(state["sha256"]) is not str
                             or len(state["sha256"]) != 64):
        raise ValueError("invalid source digest")
    if not state["present"] and (state["bytes"] != 0 or state["sha256"] is not None):
        raise ValueError("invalid absent-source baseline")
    if not path.is_file():
        if state["present"]:
            raise ValueError("source disappeared")
        return [], 0, 0
    before = path.stat()
    size = before.st_size
    if size < state["bytes"] or size - state["bytes"] > MAX_APPEND:
        raise ValueError("source truncated or appended beyond bound")
    with path.open("rb") as stream:
        if state["present"] and _digest(stream, state["bytes"]) != state["sha256"]:
            raise ValueError("historical log prefix changed")
        if not state["present"]:
            stream.seek(0)
        content = stream.read(size - state["bytes"])
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("source changed during delta")
    raw = content
    dropped = 0
    if raw and not state["newline"]:
        pos = raw.find(b"\n")
        raw = raw[pos + 1:] if pos >= 0 else b""
        dropped += 1
    if raw and not raw.endswith(b"\n"):
        pos = raw.rfind(b"\n")
        raw = raw[:pos + 1] if pos >= 0 else b""
        dropped += 1
    lines = [item.rstrip("\r\n") for item in
             raw.decode("utf-8", errors="replace").splitlines()
             if len(item) <= MAX_LINE]
    return lines, len(content), dropped


def _candidate_log(manifest, index):
    """Require explicit, validated 1-based selection; do not infer a VIDA host."""
    if not manifest.is_file() or manifest.stat().st_size > 128 * 1024:
        raise ValueError("invalid private candidate manifest")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if (type(data) is not dict or set(data) != {
            "schema_version", "private_do_not_upload",
            "paths_are_not_process_attribution", "candidates"}
            or data["schema_version"] != "virtualcar-b3a46-source-inventory-v1"
            or data["private_do_not_upload"] is not True
            or data["paths_are_not_process_attribution"] is not True
            or type(data["candidates"]) is not list
            or not 1 <= len(data["candidates"]) <= 12):
        raise ValueError("invalid private candidate manifest schema")
    if type(index) is not int or not 1 <= index <= len(data["candidates"]):
        raise ValueError("invalid candidate index")
    record = data["candidates"][index - 1]
    if (type(record) is not dict or set(record) !=
            {"path", "status", "bytes", "markers_in_tail"}
            or record["status"] != "native_marker_in_tail"
            or type(record["markers_in_tail"]) is not int
            or record["markers_in_tail"] < 1
            or type(record["bytes"]) is not int or record["bytes"] < 0
            or type(record["path"]) is not str or not record["path"]):
        raise ValueError("candidate not backed by a native marker")
    path = Path(record["path"])
    if (not path.is_absolute()
            or path.name.casefold() != "sectorvvirtualcar.log"
            or path.is_symlink()):
        raise ValueError("invalid candidate native log path")
    return path


def _external(path, sources):
    resolved = path.resolve()
    if ((ROOT is not None and resolved.is_relative_to(ROOT))
            or any(resolved == s.resolve() for s in sources)):
        raise ValueError("private output must be outside source tree and logs")


def cem_transport_summary(native_lines):
    """Group only fixed CEM services on the existing channel-aware audit path."""
    counts = {}
    result = audit_discovery(native_lines)
    for item in result["transactions"]:
        if item["route"] != "D2" or item["target"] not in ("0x40", "0x50"):
            continue
        key = (item["target"], item["service"], item["baud_bps"] or 0)
        counts.setdefault(key, Counter())[item["status"]] += 1
    return {
        "scope": "native_j2534_append_window_transport",
        "client_acceptance_verified": False,
        "routes": [
            {"target": target, "service": service, "baud_bps": baud or None,
             "requests": sum(group.values()), "statuses": dict(sorted(group.items()))}
            for (target, service, baud), group in sorted(counts.items())
        ],
        "parse_errors": result["parse_errors"],
    }


def summarize(vida_lines, virtual_lines, vida_bytes, virtual_bytes, dropped):
    vida_count = Counter()
    for line in vida_lines:
        text = line.lower()
        for key, needle in VIDA_TERMS.items():
            if needle in text:
                vida_count[key] += 1
    virtual_count = Counter()
    hosts = Counter()
    accepted = []
    for line in virtual_lines:
        match = PREFIX.match(line)
        if match is None:
            continue
        hostname = match.group(1).lower()
        kind = (hostname[:-4] if hostname.endswith(".exe") else hostname)
        hosts[kind if kind in {"iexplore", "java", "vidamonitor"} else "other"] += 1
        event = line[match.end():]
        for key, marker in VIRTUAL_TERMS.items():
            if event.startswith(marker):
                virtual_count[key] += 1
        accepted.append(line + "\n")
    mode = audit_connect(accepted)
    return {
        "schema_version": REPORT,
        "source_scope": "owner_local_two_logs_unattributed_lexical_window",
        "prefix_integrity": "verified",
        "appended_bytes": {"original_vida": vida_bytes,
                           "virtual_j2534": virtual_bytes},
        "incomplete_edge_fragments_ignored": dropped,
        "vida_literal_counts": {k: vida_count[k] for k in VIDA_TERMS},
        "virtual_marker_counts": {k: virtual_count[k] for k in VIRTUAL_TERMS},
        "virtual_host_class_line_counts": dict(sorted(hosts.items())),
        "connect_modes": mode["connect"],
        "set_config_modes": mode["set_config"],
        "cem_transport": cem_transport_summary(accepted),
        "original_vida_selected_driver_verified": False,
        "original_vida_dll_loaded_verified": False,
        "physical_ecu_rx_verified": False,
        "vin_accepted_verified": False,
        "limitations": [
            "These are append-only lexical counts, not an attested single GUI session.",
            "A VirtualCar log may contain other callers; process names are not PID attribution.",
            "Native TX/RX log markers can describe synthetic transport or local K-Line ACK.",
            "No raw VIN, CAN payload, client log line, private path, PID or file hash is exported.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("baseline", "delta"))
    parser.add_argument("--vida-log", required=True, type=Path)
    parser.add_argument("--virtual-log", type=Path,
                        help="Explicit native log path; mutually exclusive with candidate manifest")
    parser.add_argument("--candidate-manifest", type=Path,
                        help="Private B3A46 manifest, not exported")
    parser.add_argument("--candidate-index", type=int,
                        help="Explicit 1-based native marker candidate from B3A46")
    parser.add_argument("--private-baseline", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="New sanitized JSON; delta only")
    args = parser.parse_args(argv)
    if args.candidate_manifest is not None:
        if args.virtual_log is not None or args.candidate_index is None:
            parser.error("choose either --virtual-log or candidate manifest plus index")
        args.virtual_log = _candidate_log(args.candidate_manifest,
                                          args.candidate_index)
    elif args.virtual_log is None or args.candidate_index is not None:
        parser.error("choose either --virtual-log or candidate manifest plus index")
    sources = (args.vida_log, args.virtual_log)
    protected = (*sources, args.candidate_manifest) if args.candidate_manifest else sources
    if sources[0].resolve() == sources[1].resolve():
        parser.error("VIDA and virtual J2534 source files must differ")
    _external(args.private_baseline, protected)
    if args.mode == "baseline":
        if args.output is not None:
            parser.error("--output is valid only for delta")
        data = {"schema_version": SCHEMA, "private_do_not_publish": True,
                "original_vida": _snapshot(sources[0]),
                "virtual_j2534": _snapshot(sources[1])}
        args.private_baseline.parent.mkdir(parents=True, exist_ok=True)
        with args.private_baseline.open("x", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        print("B3A45 Baseline: CREATED; private file retained locally")
        return
    if args.output is None:
        parser.error("--output is required for delta")
    _external(args.output, (*protected, args.private_baseline))
    data = json.loads(args.private_baseline.read_text(encoding="utf-8"))
    if (type(data) is not dict or set(data) !=
            {"schema_version", "private_do_not_publish",
             "original_vida", "virtual_j2534"} or
            data["schema_version"] != SCHEMA or
            data["private_do_not_publish"] is not True):
        raise ValueError("private baseline schema invalid")
    vida, vbytes, vdrop = _append(sources[0], data["original_vida"])
    virtual, jbytes, jdrop = _append(sources[1], data["virtual_j2534"])
    report = summarize(vida, virtual, vbytes, jbytes, vdrop + jdrop)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
    print("B3A45 Delta: ANALYZED")
    print("Original VIDA appended bytes:", vbytes)
    print("Virtual J2534 appended bytes:", jbytes)
    print("Virtual PassThruOpen markers:", report["virtual_marker_counts"]["open_success"])
    print("Virtual J2534 connect attempts:", report["connect_modes"]["attempts"])
    print("Virtual local K-Line ACK:", report["virtual_marker_counts"]["kline_local_ack"])
    print("VIDA-selected driver / ECU RX / VIN: NOT_VERIFIED")
    print("Private source logs, baseline and JSON retained locally")


if __name__ == "__main__":
    main()
