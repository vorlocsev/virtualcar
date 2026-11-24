#!/usr/bin/env python3
"""PR #418 exact-head native J2534-2 CEM50 validation on the owner's Windows PC.

Works in a fresh local clone. No registry, installed VIDA, SQL, physical J2534
or persistent CI interaction. Artifacts stay under one NEW output directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

BRANCH = "feature/cem50-j2534-2-ps-protocol-20261121"
VIN = "YV1CR855691511566"


def command(args, *, cwd=None, log=None, env=None):
    result = subprocess.run(
        [str(x) for x in args],
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if log:
        log.write_text(result.stdout, encoding="utf-8")
    tail = result.stdout.splitlines()[-12:]
    for line in tail:
        print(line)
    if result.returncode:
        raise RuntimeError("Command failed with exit code %s: %s" %
                           (result.returncode, " ".join(map(str, args[:4]))))
    return result.stdout.strip()


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1048576), b""):
            sha.update(block)
    return sha.hexdigest().upper()


def main():
    if sys.platform != "win32":
        raise RuntimeError("Run this workflow on Windows; no fake native PASS")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New, nonexistent evidence directory")
    options = parser.parse_args()
    origin = Path(__file__).resolve().parents[3]
    for tool in ("git", "clang", "lld-link", "bash", "llvm-readobj"):
        if not shutil.which(tool):
            raise RuntimeError("Required program not found: " + tool)

    branch = command(["git", "-C", origin, "symbolic-ref", "--short", "HEAD"])
    if branch != BRANCH:
        raise RuntimeError("PR branch mismatch: " + branch)
    head = command(["git", "-C", origin, "rev-parse", "HEAD"])
    if len(head) != 40 or any(x not in "0123456789abcdef" for x in head.lower()):
        raise RuntimeError("Invalid git SHA")
    dirty = command(["git", "-C", origin, "status", "--porcelain"])
    if dirty:
        raise RuntimeError("Source checkout is modified; exact HEAD required")

    output = (options.output or
              Path(tempfile.gettempdir()) /
              ("CEM50-PS-PR418-" + uuid.uuid4().hex)).resolve()
    if output.exists():
        raise RuntimeError("Evidence output directory already exists")
    output.mkdir(parents=True)
    tree = output / "exact-head"
    summary = {
        "audit": "CEM50_PS_PR418_exact_head_owner_windows_v1",
        "source_sha": head,
        "branch": branch,
        "vin": VIN,
        "python_suite": "NOT_RUN",
        "c_host_suite": "NOT_RUN",
        "route_evidence_suite": "NOT_RUN",
        "windows_x86_build": "NOT_RUN",
        "can_ps_native": "NOT_RUN",
        "vida_readvin_verified": False,
        "ecu_identification_verified": False,
        "installed_provider_modified": False,
        "physical_adapter_used": False,
    }
    env = dict(os.environ)
    env["LOCALAPPDATA"] = str(output)
    env["TEMP"] = str(output)
    env["TMP"] = str(output)
    # Python suite runs before C emitter; stale/inherited evidence must not enable its integration gate.
    env.pop("VIRTUALCAR_ROUTE_EVIDENCE", None)
    try:
        print("SOURCE_HEAD", head)
        command(["git", "clone", "--no-local", "--no-checkout", "--", origin, tree],
                log=output / "clone.log")
        command(["git", "-C", tree, "checkout", "--detach", head],
                log=output / "checkout.log")
        if command(["git", "-C", tree, "rev-parse", "HEAD"]) != head:
            raise RuntimeError("Cloned source does not match exact HEAD")

        print("RUN full Python suite")
        summary["python_suite"] = "RUNNING"
        command([sys.executable, "-m", "unittest", "discover",
                 "-s", "emulator/tests", "-p", "test_*.py", "-v"],
                cwd=tree, log=output / "python.log", env=env)
        summary["python_suite"] = "PASS"
        print("PYTHON_PASS")

        print("COMPILE AND RUN C host suite")
        summary["c_host_suite"] = "RUNNING"
        host = output / "virtualcar-host-test.exe"
        core = tree / "emulator" / "src" / "p2core"
        sources = [tree / "emulator/tests/virtualcar_test.c"] + [
            core / (name + ".c")
            for name in ("p2_cem_router", "p2_ls_observer", "p2_vehicle_core",
                         "p2_j2534_bridge")
        ]
        command(["clang", "-std=c11", "-O2", "-Wall", "-Wextra",
                 "-D_CRT_SECURE_NO_WARNINGS", "-o", host] + sources,
                cwd=tree, log=output / "clang-host.log", env=env)
        evidence = output / "host-evidence.jsonl"
        env["VIRTUALCAR_ROUTE_EVIDENCE"] = str(evidence)
        host_output = command([host], cwd=tree, log=output / "c-host.log", env=env)
        if "PASS J2534-2 PS: explicit pins, 13/13 CEM50" not in host_output:
            raise RuntimeError("CEM50 PS host C test success marker absent")
        summary["c_host_suite"] = "PASS"
        print("C_HOST_PASS")

        if not evidence.is_file() or evidence.stat().st_size == 0:
            raise RuntimeError("C host did not produce nonempty route evidence")
        print("RUN C emitter -> Python route evidence integration")
        summary["route_evidence_suite"] = "RUNNING"
        command([sys.executable, "-m", "unittest", "discover",
                 "-s", "emulator/tests", "-p", "test_vmware_route_evidence.py", "-v"],
                cwd=tree, log=output / "route-evidence-test.log", env=env)
        summary["route_evidence_suite"] = "PASS"
        print("ROUTE_EVIDENCE_PASS")

        print("CROSS BUILD Windows x86 J2534 DLL")
        summary["windows_x86_build"] = "RUNNING"
        command(["bash", "./build-cross.sh"], cwd=tree / "emulator",
                log=output / "cross-build.log", env=env)
        dll = tree / "emulator" / "VirtualCarJ2534.dll"
        if not dll.is_file():
            raise RuntimeError("Windows x86 DLL not built")
        command(["llvm-readobj", "--file-headers", "--coff-exports", dll],
                log=output / "pe-exports.txt", env=env)
        sha = digest(dll)
        summary["windows_x86_build"] = "PASS"
        summary["dll_sha256"] = sha
        print("X86_BUILD_PASS sha256=" + sha)

        print("RUN isolated x86 J2534 CAN_PS native smoke")
        summary["can_ps_native"] = "RUNNING"
        win = Path(os.environ.get("WINDIR", "C:/Windows"))
        ps32 = win / "SysWOW64/WindowsPowerShell/v1.0/powershell.exe"
        if not ps32.is_file():
            raise RuntimeError("Windows x86 PowerShell 5.1 missing")
        smoke = tree / "emulator/adapters/cem50/Verify-J2534CEM50-PS.ps1"
        output_smoke = output / "native-ps"
        command([ps32, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-File", smoke, "-DllPath", dll, "-ExpectedSha256", sha,
                 "-OutputDirectory", output_smoke],
                cwd=tree, log=output / "native-ps.log", env=env)
        report = output_smoke / "ps-native-check.json"
        if not report.is_file():
            raise RuntimeError("Missing ps-native-check.json")
        result = json.loads(report.read_text(encoding="utf-8-sig"))
        if (result.get("status") != "CEM50_PS_NATIVE_PASS"
                or result.get("published_vin") != VIN
                or result.get("matched_frames") != 13
                or result.get("protocol_id") != "0x8004"
                or result.get("iso15765_ps_f190_verified") is not True
                or result.get("dll_sha256", "").upper() != sha
                or result.get("vida_readvin_verified") is not False
                or result.get("ecu_identification_verified") is not False
                or result.get("physical_adapter_used") is not False):
            raise RuntimeError("Native PS evidence contract mismatch")
        summary["can_ps_native"] = "PASS"
        print("CEM50_PS_ALL_PASS: 13/13 exact frames, SHA=" + head)
    except Exception as exc:
        for stage in ("python_suite", "c_host_suite", "route_evidence_suite",
                      "windows_x86_build", "can_ps_native"):
            if summary[stage] == "RUNNING":
                summary[stage] = "FAILED"
        summary["error"] = str(exc)
        print("FAILED:", exc, file=sys.stderr)
        raise
    finally:
        (output / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print("EVIDENCE:", output / "summary.json")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(1)
