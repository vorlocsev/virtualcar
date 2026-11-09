#!/usr/bin/env python3
"""Bound a *new* local SectorV J2534/backend append window without exporting raw logs.

Two calls: baseline BEFORE starting one isolated client, summarize AFTER it exits.
Never starts the client, loads a J2534 DLL, writes a CAN frame or stores a raw slice.
The private baseline contains SHA-256 of historical log prefixes; DO NOT SHARE it.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys

BASELINE_SCHEMA = "virtualcar-private-log-baseline-v2"
REPORT_SCHEMA = "virtualcar-sectorv-append-window-report-v2"
MAX_PREFIX = 2 * 1024 * 1024 * 1024
MAX_APPEND = 16 * 1024 * 1024
SERVICES = ("A3", "A6", "B9F0", "B9FB", "B9FC")
STATUSES = ("delivered", "no_fixture", "unsupported", "timeout",
            "partial_rx", "negative_response", "unverified")
# The source tree uses repo/emulator/tools, while the standalone
# VMware LAB uses LAB/tools. Refuse outputs inside the *actual* script
# distribution, not the package's entire parent drive or user directory.
_TOOLS_DIR = Path(__file__).resolve().parent
_LAB_ROOT = _TOOLS_DIR.parent
ROOT = (_LAB_ROOT if (_LAB_ROOT / "BUILDINFO.json").is_file()
        and (_LAB_ROOT / "VirtualCarJ2534.dll").is_file()
        else _TOOLS_DIR.parent.parent)


def _external_output(path, sources):
    dest = path.resolve()
    if dest.is_relative_to(ROOT) or any(dest == src.resolve() for src in sources):
        raise ValueError("output location not permitted")


def _prefix_digest(handle, count):
    digest = hashlib.sha256()
    remaining = count
    while remaining:
        part = handle.read(min(1024 * 1024, remaining))
        if not part:
            raise ValueError("log changed while reading its prefix")
        digest.update(part)
        remaining -= len(part)
    return digest.hexdigest()


def _snapshot(path):
    if not path.is_file():
        return {"present": False, "bytes": 0, "sha256": None,
                "ended_newline": True}
    before = path.stat()
    if not 0 <= before.st_size <= MAX_PREFIX:
        raise ValueError("invalid source length")
    with path.open("rb") as handle:
        digest = _prefix_digest(handle, before.st_size)
        if before.st_size:
            handle.seek(before.st_size - 1)
            ended = handle.read(1) == b"\n"
        else:
            ended = True
    after = path.stat()
    if (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
        raise ValueError("source modified during baseline")
    return {"present": True, "bytes": before.st_size,
            "sha256": digest, "ended_newline": ended}



# This audit runs on the same Windows guest as the private log-baseline command,
# not in CI where an unrelated J2534 provider may be installed. Read only.
PROVIDER_STATES = frozenset((
    "installed_library_x86", "canonical_provider_absent",
    "library_value_missing", "installed_library_missing",
    "installed_library_not_x86", "installed_library_unverifiable",
    "registry_read_unavailable", "runner_not_windows",
    "nonlocal_or_relative_path", "comparison_unverifiable"
))


def _provider_snapshot():
    """Private endpoint fingerprint of one canonical Registry32 J2534 provider.

    The private baseline holds hashed path and file bytes, NOT the source path.
    A stable pair of snapshots does NOT prove the DLL stayed loaded throughout
    an intervening GUI session or was selected by SectorV.
    """
    from audit_vmware_provider_provenance import (
        read_registry32, _file_digest, _pe_machine,
    )
    present, library, error = read_registry32()
    result = {"state": "comparison_unverifiable",
              "path_sha256": None, "file_sha256": None, "bytes": None}
    if error:
        result["state"] = error if error in PROVIDER_STATES else "comparison_unverifiable"
    elif present is False:
        result["state"] = "canonical_provider_absent"
    elif not isinstance(library, str) or not library.strip():
        result["state"] = "library_value_missing"
    else:
        value = os.path.expandvars(library.strip().strip('"'))
        if not value or value.startswith("\\\\") or not Path(value).is_absolute():
            result["state"] = "nonlocal_or_relative_path"
        else:
            candidate = Path(value)
            kind = _pe_machine(candidate)
            if kind == "missing":
                result["state"] = "installed_library_missing"
            elif kind == "other_pe":
                result["state"] = "installed_library_not_x86"
            elif kind != "x86":
                result["state"] = "installed_library_unverifiable"
            else:
                try:
                    digest, length = _file_digest(candidate)
                    result = {
                        "state": "installed_library_x86",
                        "path_sha256": hashlib.sha256(
                            os.path.normpath(value).casefold().encode("utf-8")
                        ).hexdigest(),
                        "file_sha256": digest.hex(),
                        "bytes": length,
                    }
                except (OSError, ValueError):
                    result["state"] = "comparison_unverifiable"
    return result


def _validate_provider(state):
    if type(state) is not dict or set(state) != {
            "state", "path_sha256", "file_sha256", "bytes"}:
        raise ValueError("invalid private provider snapshot shape")
    if state["state"] not in PROVIDER_STATES:
        raise ValueError("invalid private provider state")
    found = state["state"] == "installed_library_x86"
    if found:
        for key in ("path_sha256", "file_sha256"):
            value = state[key]
            if type(value) is not str or len(value) != 64 or any(
                    c not in "0123456789abcdef" for c in value):
                raise ValueError("invalid private provider fingerprint")
        if type(state["bytes"]) is not int or not 96 <= state["bytes"] <= 64 * 1024 * 1024:
            raise ValueError("invalid private provider length")
    elif any(state[key] is not None for key in ("path_sha256", "file_sha256", "bytes")):
        raise ValueError("unavailable provider must not carry fingerprints")


def _provider_endpoints(before, after):
    _validate_provider(before)
    _validate_provider(after)
    if before["state"] == after["state"] == "installed_library_x86":
        state = ("same_at_endpoints_only" if all(
            before[key] == after[key] for key in
            ("path_sha256", "file_sha256", "bytes")
        ) else "changed_between_endpoints")
    elif before["state"] != after["state"]:
        state = "provider_state_changed"
    else:
        state = "not_verified"
    return {
        "baseline_category": before["state"],
        "postrun_category": after["state"],
        "binary_endpoint_consistency": state,
        "loaded_in_sectorv_client": "not_observed",
        "during_run_immutability": "not_verified",
        "same_guest_independently_attested": False,
    }


def _baseline(j2534, backend):
    return {
        "schema_version": BASELINE_SCHEMA,
        "private_do_not_share": True,
        "provider": _provider_snapshot(),
        "j2534": _snapshot(j2534),
        "backend": _snapshot(backend),
    }


def _validate_baseline(base):
    if type(base) is not dict or set(base) != {
            "schema_version", "private_do_not_share", "provider", "j2534", "backend"}:
        raise ValueError("baseline schema invalid")
    if base["schema_version"] != BASELINE_SCHEMA or base["private_do_not_share"] is not True:
        raise ValueError("baseline provenance invalid")
    _validate_provider(base["provider"])
    for key in ("j2534", "backend"):
        state = base[key]
        if type(state) is not dict or set(state) != {
                "present", "bytes", "sha256", "ended_newline"}:
            raise ValueError("baseline entry invalid")
        if (type(state["present"]) is not bool or type(state["bytes"]) is not int
                or not 0 <= state["bytes"] <= MAX_PREFIX
                or type(state["ended_newline"]) is not bool):
            raise ValueError("baseline values invalid")
        if state["present"]:
            val = state["sha256"]
            if type(val) is not str or len(val) != 64 or any(c not in "0123456789abcdef" for c in val):
                raise ValueError("baseline fingerprint invalid")
        elif state != {"present": False, "bytes": 0, "sha256": None,
                       "ended_newline": True}:
            raise ValueError("missing-source baseline invalid")


def _append_lines(path, baseline):
    if not path.is_file():
        if baseline["present"]:
            raise ValueError("previously observed log disappeared")
        return [], {"new_bytes": 0, "complete_lines": 0, "dropped_first": False,
                    "dropped_last": False, "source_present": False, "prefix_verified": False}
    before = path.stat()
    offset = baseline["bytes"]
    if before.st_size < offset or before.st_size - offset > MAX_APPEND:
        raise ValueError("source truncated or append exceeds configured limit")
    with path.open("rb") as handle:
        current = _prefix_digest(handle, offset)
        if baseline["present"] and current != baseline["sha256"]:
            raise ValueError("historical log prefix changed; cannot attribute window")
        suffix = handle.read(before.st_size - offset)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("source changed during analysis; close client and retry")
    new_bytes = len(suffix)
    first = False
    last = False
    if suffix and offset and not baseline["ended_newline"]:
        first = True
        cut = suffix.find(b"\n")
        suffix = suffix[cut + 1:] if cut >= 0 else b""
    if suffix and not suffix.endswith(b"\n"):
        last = True
        cut = suffix.rfind(b"\n")
        suffix = suffix[:cut + 1] if cut >= 0 else b""
    lines = suffix.decode("utf-8-sig" if offset == 0 else "utf-8",
                          errors="replace").splitlines(keepends=True)
    return lines, {"new_bytes": new_bytes, "complete_lines": len(lines),
                   "dropped_first": first, "dropped_last": last,
                   "source_present": True, "prefix_verified": baseline["present"]}


def _restricted_counts(values):
    counts = Counter(v for v in values if v in STATUSES)
    return {k: counts[k] for k in STATUSES if counts[k]}


def _d2_group(transactions, target, service):
    items = [x for x in transactions if x["route"] == "D2"
             and x["target"] == target and x["service"] == service]
    counts = _restricted_counts(x["status"] for x in items)
    return {
        "requests": len(items),
        "statuses": counts,
        "rx_frame_buckets": {
            "zero": sum(x["rx_frames"] == 0 for x in items),
            "one_to_twelve": sum(1 <= x["rx_frames"] <= 12 for x in items),
            "thirteen": sum(x["rx_frames"] == 13 for x in items),
            "fourteen_plus": sum(x["rx_frames"] >= 14 for x in items),
        },
        "known_can_500k": sum(x["protocol"] == "CAN" and x["baud_bps"] == 500000
                              for x in items),
        "unknown_protocol_or_baud": sum(x["protocol"] == "unknown"
                                        or x["baud_bps"] is None for x in items),
    }


def summarize(j2534_lines, backend_lines, *, operator_one_run=False):
    if type(operator_one_run) is not bool:
        raise ValueError("operator flag must be boolean")
    # Reuse project-reviewed validators, never invent CAN/VIDA semantics.
    from audit_j2534_connect import audit as connect_audit
    from audit_j2534_discovery import audit as discovery_audit
    from audit_backend_evidence import audit as backend_audit
    connect = connect_audit(j2534_lines)
    discovery = discovery_audit(j2534_lines)
    backend = backend_audit(backend_lines)
    tx = discovery["transactions"]
    targets = {target: {service: _d2_group(tx, target, service)
                        for service in SERVICES} for target in ("0x40", "0x50")}
    backend_probe = {x["probe"]: x for x in backend["coverage"]["probes"]}
    known = {}
    for target in ("40", "50"):
        for service in SERVICES:
            key = "D2_" + target + "_" + service
            item = backend_probe.get(key)
            known[key] = {"requests": item["observed_requests"],
                          "statuses": _restricted_counts(
                              status for status, n in item["status_counts"].items()
                              for _ in range(n))} if item is not None else {
                                  "requests": 0, "statuses": {}}
    return {
        "schema_version": REPORT_SCHEMA,
        "source": "local_bounded_append_only",
        "read_only_audit": True,
        "contains_raw_can_or_vin": False,
        "operator_one_run_confirmed": operator_one_run,
        "cross_log_transaction_attribution": "not_established",
        "client_ui_result": "not_observed_by_this_tool",
        "client_vehicle_identity_accepted": "not_verified",
        "replay_approved": False,
        "connect": {"attempts": connect["connect"]["attempts"],
                    "statuses": dict(sorted(connect["connect"]["statuses"].items()))},
        "discovery": {"transactions": len(tx),
                      "statuses": dict(sorted(discovery["counts"].items())),
                      "d2": targets,
                      "p3_count": sum(x["route"] == "P3" for x in tx),
                      # The same already-bounded J2534 source was checked by
                      # the independent generation-tag analyzer. Never infer
                      # a cross-log TX, actual GUI acceptance, or OEM VIN.
                      "native_d2_delivery_tags": discovery["native_d2_delivery_tags"]},
        "backend": {"requests": backend["summary"]["requests"],
                    "invalid_lines": backend["summary"]["invalid_lines"],
                    "statuses": dict(sorted(backend["summary"]["statuses"].items())),
                    "d2_probe_coverage": known},
        "next_gate": (
            "review_operator_single_run_provenance" if not operator_one_run else
            "review_b9fb_d2_transport_and_client_ui_independently"),
        "note": "These are separate text/backend parsers over bounded local windows. "
                "Counts cannot be joined by timestamps. RX delivery is not VIN acceptance.",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Offline fresh-window, no raw log export")
    p.add_argument("mode", choices=("baseline", "analyze"))
    p.add_argument("--j2534", type=Path, required=True)
    p.add_argument("--backend", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path)
    p.add_argument("--operator-one-run-confirmed", action="store_true")
    args = p.parse_args(argv)
    try:
        sources = (args.j2534, args.backend)
        if args.j2534.resolve() == args.backend.resolve():
            raise ValueError("sources must be distinct")
        _external_output(args.manifest, sources)
        if args.mode == "baseline":
            if args.output is not None or args.operator_one_run_confirmed:
                raise ValueError("baseline accepts neither report nor run assertion")
            content = _baseline(*sources)
            with args.manifest.open("x", encoding="utf-8") as out:
                json.dump(content, out, indent=2)
                out.write("\n")
            print("Private baseline created locally; never share manifest or raw log.")
            return 0
        if args.output is None:
            raise ValueError("summary output required")
        _external_output(args.output, (*sources, args.manifest))
        if args.manifest.stat().st_size > 4096:
            raise ValueError("private manifest too large")
        baseline = json.loads(args.manifest.read_text(encoding="utf-8"))
        _validate_baseline(baseline)
        j_lines, j_window = _append_lines(args.j2534, baseline["j2534"])
        b_lines, b_window = _append_lines(args.backend, baseline["backend"])
        report = summarize(j_lines, b_lines,
                           operator_one_run=args.operator_one_run_confirmed)
        report["windows"] = {"j2534": j_window, "backend": b_window}
        report["registered_provider"] = _provider_endpoints(
            baseline["provider"], _provider_snapshot())
        with args.output.open("x", encoding="utf-8") as out:
            json.dump(report, out, indent=2, ensure_ascii=False)
            out.write("\n")
        print("Redacted append-window report created; VIN acceptance remains unverified.")
        return 0
    except (OSError, ValueError, TypeError, UnicodeError, KeyError) as exc:
        # Never print a private path, log, manifest digest or raw line.
        print("Offline audit stopped: " + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
