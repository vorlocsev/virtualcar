#!/usr/bin/env python3
"""Fail-closed layout and offline-runtime validation of EXTRACTED LAB artifact.

Input: the actual directory created by actions/download-artifact or a user
extracting VirtualCar-*-Windows-x86-LAB.zip. No registry edits, DLL loading,
client launch, input import, or raw trace output. Checks only distribution.
"""
import argparse
import ast
import json
from pathlib import Path
import struct
import sys

REQUIRED_RUNTIME = (
    "VirtualCarJ2534.dll",
    "VirtualCarControl.exe",
    "virtualcar.ini",
    "scripts/install.ps1",
    "scripts/uninstall.ps1",
    "scripts/diagnose.ps1",
    "scripts/Capture-P2ClientRun.ps1",
    "samples/p2-client-ui-observation.template.json",
    "tools/prepare_p2_client_run.py",
    "docs/research/P2_REAL_CLIENT_CAPTURE_WORKFLOW_RU.md",
    "README_CLIENT_CAPTURE_RU.md",
    "scripts/Select-P2ClientTrialProfile.ps1",
    "profiles/p2-trial-00-no-d2.ini",
    "profiles/p2-trial-01-public-b9fb-only.ini",
    "profiles/p2-trial-02-mixed-b9fb-b9f0-locked.ini",
    "tools/compare_p2_client_trials.py",
    "tools/audit_p2_d2_fixture_provenance.py",
    "docs/research/P2_CLIENT_TRIAL_ABC_RU.md",
)
SCRIPT_MODULES = (
    "prepare_p2_client_run",
    "prepare_p2_capture",
    "audit_native_p2_channel_chronology",
    "audit_native_b9f0_response",
    "audit_native_j2534_lifecycle",
    "audit_native_connect_b9fb_channel",
    "audit_d2_followup_window",
    "audit_j2534_connect",
    "audit_j2534_discovery",
    "import_p2_trace",
)


def _pe32_i386(path):
    data = path.read_bytes()[:4096]
    if len(data) < 256 or data[:2] != b"MZ":
        raise ValueError("not_pe_mz")
    offset = struct.unpack_from("<I", data, 0x3c)[0]
    if offset < 64 or offset + 26 > len(data):
        raise ValueError("invalid_pe_offset")
    if data[offset:offset + 4] != b"PE\x00\x00":
        raise ValueError("invalid_pe_signature")
    machine = struct.unpack_from("<H", data, offset + 4)[0]
    optional_magic = struct.unpack_from("<H", data, offset + 24)[0]
    if machine != 0x14c or optional_magic != 0x10b:
        raise ValueError("not_windows_x86_pe32")


def audit(folder):
    if not folder.is_dir():
        raise ValueError("missing_unpacked_archive_root")
    # 1. Distribution is directly launchable from the extracted root.
    #    No surrounding repository or source checkout is allowed.
    for rel in REQUIRED_RUNTIME:
        if not (folder / rel).is_file():
            raise ValueError("missing_distribution_item")
    # 2. DLL ABI and architecture (not an assertion of actual function
    #    compatibility with a proprietary 32-bit client).
    _pe32_i386(folder / "VirtualCarJ2534.dll")
    # 3. GUI distribution must be Windows x86, not an accidentally
    #    mixed x64 binary.
    _pe32_i386(folder / "VirtualCarControl.exe")
    # 4. Sidecar profile and capture script use the same extracted root.
    ps = (folder / "scripts/Capture-P2ClientRun.ps1").read_text(
        encoding="utf-8-sig")
    if (r"..\VirtualCarJ2534.dll" not in ps or
            r"..\virtualcar.ini" not in ps or
            r"..\tools\prepare_p2_client_run.py" not in ps):
        raise ValueError("capture_paths_not_archive_relative")
    # 5. Install and capture must refer to the same Registry32 adapter
    #    (read-only preflight verifies exact installed path).
    installer = (folder / "scripts/install.ps1").read_text(
        encoding="utf-8-sig")
    removal = (folder / "scripts/uninstall.ps1").read_text(
        encoding="utf-8-sig")
    for source in (installer, removal, ps):
        if r"PassThruSupport.04.04" not in source or (
                "SectorV Virtual Car" not in source or
                "Registry32" not in source):
            raise ValueError("distribution_registry_identity_disagrees")
    # 6. All local imported Python dependencies from capture's entrypoint
    #    must be present and compile; no sys.path from source checkout.
    tool_root = folder / "tools"
    queue = ["prepare_p2_client_run"]
    visited = set()
    while queue:
        name = queue.pop()
        if name in visited:
            continue
        visited.add(name)
        path = tool_root / (name + ".py")
        if not path.is_file():
            raise ValueError("missing_python_import_dependency")
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=path.name)
        compile(tree, path.name, "exec")
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                dependency = node.module
                if dependency in SCRIPT_MODULES:
                    queue.append(dependency)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in SCRIPT_MODULES:
                        queue.append(alias.name)
    if not set(SCRIPT_MODULES).issubset(visited):
        raise ValueError("incomplete_client_analysis_module_graph")
    # 7. UI observation sample must be valid JSON and use safe default
    #    values; never package customer screenshots or local logs.
    template = json.loads((folder / "samples/p2-client-ui-observation.template.json")
                          .read_text(encoding="utf-8-sig"))
    if not isinstance(template, dict) or template.get(
            "same_run_operator_attested") is not False:
        raise ValueError("unsafe_client_observation_sample")
    for key in ("vin_display", "ecu_list"):
        if template.get(key) != "unknown":
            raise ValueError("unsafe_default_client_observation")
    # 8. A local-language runbook must cover both phases and private
    #    report handling, without claiming the live client was executed.
    runbook = (folder / "docs/research/P2_REAL_CLIENT_CAPTURE_WORKFLOW_RU.md"
               ).read_text(encoding="utf-8-sig")
    quickstart = (folder / "README_CLIENT_CAPTURE_RU.md").read_text(
        encoding="utf-8-sig")
    if (not all(k in runbook for k in (
            "Begin", "Finish", "PRIVATE-DO-NOT-SHARE", "SAFE-JSON-REPORTS")) or
            not all(k in quickstart for k in (
                "install.ps1", "Capture-P2ClientRun.ps1", "SectorV", "VDASH"))):
        raise ValueError("incomplete_operator_runbook")
    # 9. Explicit A/B/C variants differ ONLY in source-labeled D2 fields;
    #    the mixed donor replay must remain locked in distributed file.
    from configparser import ConfigParser
    profiles = []
    for basename in (
            "p2-trial-00-no-d2.ini",
            "p2-trial-01-public-b9fb-only.ini",
            "p2-trial-02-mixed-b9fb-b9f0-locked.ini"):
        ini = folder / "profiles" / basename
        p = ConfigParser(interpolation=None)
        p.read_string(ini.read_text(encoding="utf-8-sig"))
        profiles.append(p)
    if (len({tuple(p["Vehicle"].items()) for p in profiles}) != 1
            or len({tuple(p["ECU0"].items()) for p in profiles}) != 1
            or len({tuple(p["ECU1"].items()) for p in profiles}) != 1
            or [p.getint("D2_50", "B9FBFrameCount")
                for p in profiles] != [0, 13, 13]
            or profiles[2].getint("D2_50_B9F0", "FrameCount") != 3
            or profiles[2].get("P2", "FixtureProvenance") !=
            "local_composite_unverified_trace_import"
            or profiles[2].get("P2", "AllowCompositeReplay") != "0"):
        raise ValueError("unsafe_or_noncomparable_trial_profiles")
    selector = (folder / "scripts/Select-P2ClientTrialProfile.ps1"
                ).read_text(encoding="utf-8-sig")
    comparator = (folder / "tools/compare_p2_client_trials.py"
                  ).read_text(encoding="utf-8-sig")
    compile(ast.parse(comparator), "compare_p2_client_trials.py", "exec")
    if (not all(k in selector for k in
                ("IConfirmClientsClosed", "IUnderstandExperimentalDonorData",
                 "EnableCompositeReplay", "TrialProfileBackups"))
            or "Start-Process" in selector):
        raise ValueError("trial_selector_may_not_be_offline_or_explicit")
    trial_guide = (folder / "docs/research/P2_CLIENT_TRIAL_ABC_RU.md"
                   ).read_text(encoding="utf-8-sig")
    if not all(k in trial_guide for k in
               ("A_NoD2", "B_PublicB9FB", "C_MixedB9FB_B9F0",
                "SAFE-JSON-REPORTS")):
        raise ValueError("trial_guide_missing_safety_boundaries")
    return {
        "status": "offline_lab_distribution_structure_valid",
        "checks_passed": 9,
        "script_modules_present": len(visited),
        "source_checkout_required_for_runtime": False,
        "client_executed": False,
        "registry_modified": False,
        "real_ecu_identity_verified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("unpacked_artifact", type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit(args.unpacked_artifact)
    except (OSError, ValueError, SyntaxError, UnicodeError, TypeError,
            json.JSONDecodeError):
        print("FAIL: extracted client lab distribution does not pass "
              "offline readiness checks", file=sys.stderr)
        return 2
    print("PASS: 9/9 offline LAB ZIP layout, A/B/C safety and dependencies; "
          "no proprietary client acceptance implied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
