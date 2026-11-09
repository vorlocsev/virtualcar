#!/usr/bin/env python3
"""Two-stage, read-only operator collection for ONE authorized SectorV GUI run.

This never launches SectorV, loads a DLL, opens J2534, sends CAN, or authenticates
OEM identity. The operator must keep the GUI run isolated and manually observe
its six fixed UI categories; an optional module snapshot remains uncorrelated.
All VIN, raw CAN, paths and digests remain in preexisting private sources.
"""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys

import audit_sectorv_fresh_window as fresh
import audit_sectorv_ui_window_triage as triage
from audit_sectorv_ui_observation import OBSERVATIONS, SCHEMA as GUI_SCHEMA

PRIVATE_MANIFEST = "p0-before.private.json"
WINDOW_REPORT = "p0-window.redacted.json"
TRIAGE_REPORT = "p0-triage.redacted.json"
MAX_MANIFEST = 4096
PRIVATE_SCHEMA = "virtualcar-sectorv-operator-private-source-bindings-v1"
BINDING_KEYS = ("j2534", "backend")


def _source_token(path):
    """Private-only canonical source pathname binding; never report this token.

    The normal log-prefix audit detects rewritten historical bytes, while the
    path binding also prevents swapping an empty or identically prefixed log
    for another file between begin and finish. Neither proves a common GUI
    process/session or that a path was never redirected between calls.
    """
    canonical = os.path.normcase(str(path.resolve()))
    return hashlib.sha256(os.fsencode(canonical)).hexdigest()


def _private_baseline(j2534, backend):
    return {
        "schema_version": PRIVATE_SCHEMA,
        "private_do_not_share": True,
        "source_path_tokens": {
            "j2534": _source_token(j2534),
            "backend": _source_token(backend),
        },
        "bounded_window": fresh._baseline(j2534, backend),
    }


def _verified_private_baseline(raw, j2534, backend):
    if (type(raw) is not dict or set(raw) != {
            "schema_version", "private_do_not_share",
            "source_path_tokens", "bounded_window"}
            or raw["schema_version"] != PRIVATE_SCHEMA
            or raw["private_do_not_share"] is not True):
        raise ValueError("private source binding manifest invalid")
    tokens = raw["source_path_tokens"]
    if type(tokens) is not dict or set(tokens) != set(BINDING_KEYS):
        raise ValueError("private source binding fields invalid")
    for key, path in (("j2534", j2534), ("backend", backend)):
        token = tokens[key]
        if (type(token) is not str or len(token) != 64 or
                any(ch not in "0123456789abcdef" for ch in token) or
                not hmac.compare_digest(token, _source_token(path))):
            raise ValueError("operator source pathname changed")
    bounded = raw["bounded_window"]
    fresh._validate_baseline(bounded)
    return bounded


def _session_folder(path):
    if not path.is_absolute() or str(path).startswith("\\\\"):
        raise ValueError("require absolute local session folder")
    # All outputs must remain outside the checkout, never in the repo.
    resolved = path.resolve()
    if resolved.is_relative_to(fresh.ROOT):
        raise ValueError("session folder inside source checkout or LAB package")
    if path.is_symlink():
        raise ValueError("symlink session folder")
    return resolved


def _gui_observation(args):
    # The operator must affirm isolation instead of inheriting sample JSON.
    if (not args.isolated_read_only_vm or not args.physical_adapter_disconnected):
        raise ValueError("operator isolation confirmations required")
    states = {}
    for field in OBSERVATIONS:
        value = getattr(args, field)
        if value is None:
            raise ValueError("all observed GUI categories required")
        states[field] = value
    value = {
        "schema_version": GUI_SCHEMA,
        "client": "SectorV",
        "scenario": "P2_MY2009_lab",
        "source": "human_ui_observation",
        "run_scope": "single_vm_client_run",
        "read_only": True,
        "physical_adapter_disconnected": True,
        "observations": states,
    }
    # A contradictory human observation is a failure, not "unknown".
    from audit_sectorv_ui_observation import audit
    audit(value)
    return value


def _module_categories(path, sources):
    if path is None:
        return None
    if path.resolve() in {p.resolve() for p in sources} or path.is_symlink():
        raise ValueError("module source conflicts with inputs")
    if path.stat().st_size > triage.MAX_MODULE_FILE:
        raise ValueError("module source too large")
    module = json.loads(path.read_text(encoding="utf-8"))
    triage._check_module_snapshot(module)
    return module


def begin(args):
    folder = _session_folder(args.session_dir)
    if args.single_run_confirmed or args.module_snapshot or any(
            getattr(args, field) is not None for field in OBSERVATIONS) or (
            args.isolated_read_only_vm or args.physical_adapter_disconnected):
        raise ValueError("begin accepts no client result")
    if args.j2534.resolve() == args.backend.resolve():
        raise ValueError("duplicate log sources")
    folder.mkdir(parents=False, exist_ok=False)
    manifest = folder / PRIVATE_MANIFEST
    try:
        fresh._external_output(manifest, (args.j2534, args.backend))
        baseline = _private_baseline(args.j2534, args.backend)
        with manifest.open("x", encoding="utf-8") as stream:
            json.dump(baseline, stream, indent=2)
            stream.write("\n")
    except Exception:
        # Only remove the new directory if it is still empty. Never delete
        # an existing source log, private manifest or another user's file.
        try:
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
        except OSError:
            pass
        raise
    print("Private SectorV baseline created. Open one isolated read-only GUI run; no client was launched.")


def finish(args):
    folder = _session_folder(args.session_dir)
    if not folder.is_dir():
        raise ValueError("session directory does not exist")
    if args.j2534.resolve() == args.backend.resolve():
        raise ValueError("duplicate log sources")
    manifest = folder / PRIVATE_MANIFEST
    window_path = folder / WINDOW_REPORT
    triage_path = folder / TRIAGE_REPORT
    sources = (args.j2534, args.backend, manifest)
    if manifest.is_symlink() or manifest.stat().st_size > MAX_MANIFEST:
        raise ValueError("invalid private manifest")
    for output in (window_path, triage_path):
        if output.is_symlink() or output.exists():
            raise ValueError("exclusive output already exists")
        fresh._external_output(output, sources)
    if args.module_snapshot is not None and args.module_snapshot.resolve() in {
            p.resolve() for p in (window_path, triage_path, manifest)}:
        raise ValueError("module source overlaps reports")
    # Validate every operator-supplied category BEFORE creating an output.
    gui = _gui_observation(args)
    module = _module_categories(args.module_snapshot,
                                (*sources, window_path, triage_path))
    private = json.loads(manifest.read_text(encoding="utf-8"))
    baseline = _verified_private_baseline(private, args.j2534, args.backend)

    # The shared analyzer verifies historical prefixes, bounds and line
    # boundaries. Never materialize raw CAN, VIN or private text in the bundle.
    jlines, jwindow = fresh._append_lines(args.j2534, baseline["j2534"])
    blines, bwindow = fresh._append_lines(args.backend, baseline["backend"])
    window = fresh.summarize(
        jlines, blines, operator_one_run=args.single_run_confirmed)
    window["windows"] = {"j2534": jwindow, "backend": bwindow}
    window["registered_provider"] = fresh._provider_endpoints(
        baseline["provider"], fresh._provider_snapshot())
    result = triage.triage(
        window, gui, operator_pair_confirmed=args.single_run_confirmed,
        module_snapshot=module)

    # Two new outputs, never overwrite previous evidence. Roll back a new
    # window report if writing the triage report fails.
    created = []
    try:
        for path, report in ((window_path, window), (triage_path, result)):
            with path.open("x", encoding="utf-8") as out:
                created.append(path)
                json.dump(report, out, ensure_ascii=False, indent=2)
                out.write("\n")
    except Exception:
        for path in created:
            try:
                path.unlink()
            except OSError:
                pass
        raise
    print("Two redacted reports created locally; SectorV GUI VIN/ECU acceptance NOT VERIFIED.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("begin", "finish"))
    parser.add_argument("--session-dir", type=Path, required=True,
                        help="New private local directory (begin), same directory (finish)")
    parser.add_argument("--j2534", type=Path, required=True)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--module-snapshot", type=Path,
                        help="Optional redacted operator DLL report captured while GUI was open")
    parser.add_argument("--isolated-read-only-vm", action="store_true")
    parser.add_argument("--physical-adapter-disconnected", action="store_true")
    parser.add_argument("--single-run-confirmed", action="store_true",
                        help="Operator assertion only; not independent pairing proof")
    for field, choices in OBSERVATIONS.items():
        parser.add_argument("--" + field.replace("_", "-"),
                            choices=sorted(choices))
    args = parser.parse_args(argv)
    try:
        if args.phase == "begin":
            begin(args)
        else:
            finish(args)
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        # Never echo private logs, paths, hashes, UI text or exception values.
        print("Operator session collection stopped: invalid or unverified input",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
