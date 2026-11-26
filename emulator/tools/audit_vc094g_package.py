"""Verify a VC094 package and optionally archive the public demo distribution.

No execution, installation, registry changes, network, or release publication.
The manifest is an integrity inventory, not a signature or runtime attestation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import zipfile

MAX_FILES = 4096
MAX_FILE = 128 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024
MAX_MANIFEST = 2 * 1024 * 1024
PROFILES = {
    "p2": "virtualcar-p2.ini",
    "obd": "virtualcar-default.ini",
    "p2-vin-demo": "virtualcar-p2-b9fb-lab-vin.ini",
}
PRIVATE = "xc90-v8-2009"
RUNTIME = {
    "VirtualCar.exe", "VirtualCar.WinUI.dll", "VirtualCar.Core.dll",
    "VirtualCar.WinUI.deps.json", "VirtualCar.WinUI.runtimeconfig.json",
    "Microsoft.UI.Xaml.dll", "coreclr.dll", "hostfxr.dll", "hostpolicy.dll",
    "driver-tools/VirtualCar.DriverTool.exe", "driver-tools/VirtualCar.DriverTool.dll",
    "driver-tools/VirtualCar.DriverTool.deps.json",
    "driver-tools/VirtualCar.DriverTool.runtimeconfig.json",
    "driver-tools/coreclr.dll", "driver-tools/hostfxr.dll", "driver-tools/hostpolicy.dll",
}
ART = {"artwork/" + name for name in (
    "xc90-v8.jpg", "xc90-v8.sha256", "p2-reference.jpg", "p2-reference.sha256", "credits.txt")}
PRIVATE_FILES = {"configuration.json", "configuration-options.json", "configuration-references.json",
                 "local-profile.json"}
PROFILE_FILES = {"virtualcar.ini", "VirtualCarJ2534.dll", "candidate.sha256"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def hexstr(value, length):
    if type(value) is not str or not re.fullmatch(r"[a-fA-F0-9]{%d}" % length, value):
        raise ValueError("invalid digest")
    return value.lower()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def bad_constant(_):
    raise ValueError("nonfinite JSON")


def parse(raw):
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique,
                      parse_constant=bad_constant)


def safe_name(name):
    if type(name) is not str or not 1 <= len(name) <= 220:
        raise ValueError("invalid file name")
    parts = name.split("/")
    for part in parts:
        if (not re.fullmatch(r"[A-Za-z0-9_().+ -]+", part)
                or part in (".", "..") or part.endswith((" ", "."))
                or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)):
            raise ValueError("unsafe archive path")
    return name


def local_path(path):
    path = Path(path)
    if not path.is_absolute() or str(path).startswith(("\\\\", "//")):
        raise ValueError("absolute local path required")
    for item in (path, *path.parents):
        st = item.lstat()
        if stat.S_ISLNK(st.st_mode) or getattr(st, "st_file_attributes", 0) & 0x400:
            raise ValueError("reparse or symbolic link")
    return path


def frozen(path, cap):
    path = local_path(path)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= cap:
        raise ValueError("invalid file size")
    with path.open("rb") as stream:
        raw = stream.read(cap + 1)
    after = path.stat()
    if len(raw) != before.st_size or (before.st_size, before.st_mtime_ns, before.st_ino) != (
            after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError("file changed")
    return raw


def inventory(entries):
    if type(entries) is not list or not 1 <= len(entries) <= MAX_FILES:
        raise ValueError("invalid inventory")
    result = {}
    seen = set()
    total = 0
    for row in entries:
        if type(row) is not dict or set(row) != {"path", "bytes", "sha256"}:
            raise ValueError("invalid inventory entry")
        name = safe_name(row["path"])
        if name.casefold() in seen or type(row["bytes"]) is not int or not 0 < row["bytes"] <= MAX_FILE:
            raise ValueError("duplicate path or invalid size")
        seen.add(name.casefold())
        result[name] = (row["bytes"], hexstr(row["sha256"], 64))
        total += row["bytes"]
    if total > MAX_TOTAL:
        raise ValueError("package too large")
    return result


def verify_bytes(raw, expected):
    if (len(raw), digest(raw)) != expected:
        raise ValueError("fingerprint mismatch")


def pe(raw, machine, magic):
    if len(raw) < 90 or raw[:2] != b"MZ":
        raise ValueError("invalid PE")
    offset = int.from_bytes(raw[60:64], "little")
    if not 64 <= offset <= len(raw) - 26 or raw[offset:offset+4] != b"PE\0\0" or (
        int.from_bytes(raw[offset+4:offset+6], "little"),
        int.from_bytes(raw[offset+24:offset+26], "little")) != (machine, magic):
        raise ValueError("unexpected PE architecture")


def scan(root):
    names = set()
    for folder, dirs, files in os.walk(local_path(root), followlinks=False):
        for name in dirs:
            local_path(Path(folder) / name)
        for name in files:
            path = local_path(Path(folder) / name)
            relative = safe_name(path.relative_to(root).as_posix())
            names.add(relative)
            if len(names) > MAX_FILES:
                raise ValueError("too many files")
    return names


def verify_preflight(report, manifest, expected_head):
    gates = {"source_and_managed_inventory", "fresh_native_build", "x86_export_contract",
             "native_silence_and_evidence", "synthetic_identity_replay", "can_ms_lifecycle",
             "registry32_preflight", "final_integrity"}
    if (report.get("schema") != "vc090-native-preflight-v1" or report.get("status") != "pass" or
            hexstr(report.get("source_sha"), 40) != hexstr(expected_head, 40) or
            hexstr(report.get("native_dll_sha256"), 64) != hexstr(manifest.get("native_sha256"), 64) or
            set(report["gates"]) != gates or any(v != "pass" for v in report["gates"].values()) or
            report.get("failed_stage") != "" or any(report.get(k) != "not_tested" for k in (
                "registration_install_remove", "vida_provider_selection", "vida_loaded_module_identity",
                "vida_readvin", "vida_t111", "vida_t122", "physical_j2534"))):
        raise ValueError("native preflight mismatch")
    sizes = [row["bytes"] for row in manifest["files"] if row["path"].endswith("/VirtualCarJ2534.dll")]
    if type(report.get("native_dll_bytes")) is not int or not sizes or any(
            size != report["native_dll_bytes"] for size in sizes):
        raise ValueError("native preflight size mismatch")


def verify(root, manifest, build, expected_head, emulator):
    head = hexstr(expected_head, 40)
    if (manifest.get("schema") != "vc094a-package-v1" or
            hexstr(manifest.get("source_sha"), 40) != head or
            build.get("schema") != "vc075-winui-build-v1" or
            hexstr(build.get("source_sha"), 40) != head or build.get("publish") != "pass" or
            build.get("platform") != "win-x64"):
        raise ValueError("source or build mismatch")
    if any(manifest.get(k) != "not_tested" for k in
           ("original_vida", "physical_j2534", "registration", "package_ui")):
        raise ValueError("unexpected acceptance claim")
    private = manifest.get("private_profile_included")
    if type(private) is not bool or manifest.get("artwork") not in ("skipped", "two_reference_photos"):
        raise ValueError("invalid scope")
    native = hexstr(manifest.get("native_sha256"), 64)
    base = inventory(build["files"])
    if "VirtualCar.WinUI.exe" not in base or "VirtualCar.exe" in base:
        raise ValueError("invalid apphost mapping")
    base["VirtualCar.exe"] = base.pop("VirtualCar.WinUI.exe")
    if not RUNTIME <= set(base) or any(n.startswith(("vehicle-data/", "artwork/")) for n in base):
        raise ValueError("incomplete managed runtime")
    expected = inventory(manifest["files"])
    profiles = manifest.get("profiles")
    ids = set(PROFILES) | ({PRIVATE} if private else set())
    if type(profiles) is not list or len(profiles) != len(ids):
        raise ValueError("profile inventory mismatch")
    extra = set()
    seen = set()
    for row in profiles:
        ident = row["id"]
        if ident not in ids or ident in seen or hexstr(row["native_sha256"], 64) != native:
            raise ValueError("profile identity mismatch")
        seen.add(ident)
        prefix = "vehicle-data/" + ident + "/"
        files = PROFILE_FILES | (PRIVATE_FILES if ident == PRIVATE else set())
        extra.update(prefix + f for f in files)
        if row.get("scope") != ("owner_local_private" if ident == PRIVATE else "synthetic_or_historical_demo"):
            raise ValueError("profile scope mismatch")
        if expected[prefix+"virtualcar.ini"][1] != hexstr(row["profile_sha256"], 64):
            raise ValueError("profile digest mismatch")
        if expected[prefix+"VirtualCarJ2534.dll"][1] != native:
            raise ValueError("native digest mismatch")
    if seen != ids:
        raise ValueError("missing profile")
    if manifest["artwork"] == "two_reference_photos":
        extra |= ART
    if set(expected) != set(base) | extra or set(base) & extra:
        raise ValueError("unexpected packaged file")
    if any(expected[n] != item for n, item in base.items()) or scan(root) != set(expected):
        raise ValueError("package differs from published inventory")
    for name, item in expected.items():
        raw = frozen(root / name, MAX_FILE)
        verify_bytes(raw, item)
        if name in {"VirtualCar.exe", "driver-tools/VirtualCar.DriverTool.exe",
                    "Microsoft.UI.Xaml.dll", "coreclr.dll", "hostfxr.dll", "hostpolicy.dll",
                    "driver-tools/coreclr.dll", "driver-tools/hostfxr.dll", "driver-tools/hostpolicy.dll"}:
            pe(raw, 0x8664, 0x20b)
        if name.endswith("/VirtualCarJ2534.dll"):
            pe(raw, 0x14c, 0x10b)
    for ident in ids:
        prefix = "vehicle-data/" + ident + "/"
        side = frozen(root / (prefix+"candidate.sha256"), 128).decode("ascii").strip()
        if hexstr(side, 64) != native:
            raise ValueError("native sidecar mismatch")
        if ident in PROFILES:
            if digest(frozen(emulator / PROFILES[ident], 1024 * 1024)) != expected[prefix+"virtualcar.ini"][1]:
                raise ValueError("tracked profile differs")
        else:
            local = parse(frozen(root / (prefix+"local-profile.json"), 4096))
            if local.get("schema") != "vc094d2-local-profile-v3" or local.get("native_sha256") != native:
                raise ValueError("private profile manifest mismatch")
            for key, filename in (("profile_sha256", "virtualcar.ini"), ("catalog_sha256", "configuration.json"),
                                  ("options_sha256", "configuration-options.json"),
                                  ("references_sha256", "configuration-references.json")):
                if hexstr(local[key], 64) != expected[prefix+filename][1]:
                    raise ValueError("private component mismatch")
    if ART <= extra:
        for name in ("xc90-v8", "p2-reference"):
            if hexstr(frozen(root / ("artwork/"+name+".sha256"), 128).decode("ascii").strip(), 64) != expected["artwork/"+name+".jpg"][1]:
                raise ValueError("artwork sidecar mismatch")
    return expected, private


def archive(root, expected, private, output):
    if private:
        raise ValueError("private package cannot be archived by public packager")
    output = Path(output)
    local_path(output.parent)
    if not output.is_absolute() or output.suffix.lower() != ".zip" or root in output.parents:
        raise ValueError("invalid archive output")
    for parent in output.parents:
        if (parent / ".git").exists():
            raise ValueError("output inside Git")
    # exclusive file creation, no extraction, no overwrite
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, item in sorted(expected.items()):
            raw = frozen(root / name, MAX_FILE)
            verify_bytes(raw, item)
            z.writestr("VirtualCar/" + name, raw)
    with zipfile.ZipFile(output, "r") as z:
        if len(z.infolist()) != len(expected) or set(z.namelist()) != {"VirtualCar/"+n for n in expected}:
            raise ValueError("ZIP inventory mismatch")
        for name, item in expected.items():
            info = z.getinfo("VirtualCar/"+name)
            if info.file_size != item[0]:
                raise ValueError("ZIP size mismatch")
            verify_bytes(z.read(info), item)
    return digest_file(output)


def digest_file(path):
    h = hashlib.sha256()
    with local_path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("package", "manifest", "build-manifest", "native-preflight"):
        p.add_argument("--"+key, type=Path, required=True)
    p.add_argument("--expected-head", required=True)
    p.add_argument("--zip", type=Path)
    a = p.parse_args(argv)
    try:
        root = local_path(a.package)
        mraw = frozen(a.manifest, MAX_MANIFEST)
        braw = frozen(a.build_manifest, MAX_MANIFEST)
        nraw = frozen(a.native_preflight, MAX_MANIFEST)
        manifest = parse(mraw)
        verify_preflight(parse(nraw), manifest, a.expected_head)
        expected, private = verify(root, manifest, parse(braw), a.expected_head,
                                   Path(__file__).resolve().parents[1])
        if (frozen(a.manifest, MAX_MANIFEST) != mraw or frozen(a.build_manifest, MAX_MANIFEST) != braw or
                frozen(a.native_preflight, MAX_MANIFEST) != nraw):
            raise ValueError("manifest changed")
        if a.zip:
            sha = archive(root, expected, private, a.zip)
            print("VC094G_ZIP_SHA256=" + sha)
        print("VC094G_PACKAGE_INTEGRITY=PASS files=" + str(len(expected)))
        print("VC094G_SCOPE=" + ("OWNER_LOCAL_PRIVATE" if private else "PUBLIC_DEMO"))
        print("VC094G_RUNTIME_ACCEPTANCE=NOT_TESTED")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError, zipfile.BadZipFile):
        p.exit(2, "VC094G_PACKAGE=REJECTED; do not distribute partial output\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
