"""VMware distribution safety, architecture, fidelity and privacy gates."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

MODULE = Path(__file__).resolve().parents[1] / "tools" / "package_vmware_lab.py"
spec = importlib.util.spec_from_file_location("package_vmware_lab", MODULE)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
COMMIT = "a" * 40
SOURCE_ROOT = MODULE.parents[1]
PROFILE = (SOURCE_ROOT / "virtualcar-p2.ini").read_text(encoding="utf-8")


def fake_pe(machine=0x014C, magic=0x010B):
    data = bytearray(512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<H", data, 0x84, machine)
    struct.pack_into("<H", data, 0x98, magic)
    return bytes(data)


class VMwarePackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "emulator"
        self.out = Path(self.temp.name) / "out"
        self.root.mkdir()
        self.out.mkdir()
        for rel in tool.FILES.values():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            if rel in tool.APPROVED_INI_SHA256:
                shutil.copyfile(SOURCE_ROOT / rel, path)
            else:
                content = fake_pe() if path.suffix in (".exe", ".dll") else b"BENCH ONLY\n"
                path.write_bytes(content)

    def build(self):
        return tool.create_package(self.root, self.out, COMMIT, "vmware-lab-test")

    def test_01_whitelisted_contents_only(self):
        with zipfile.ZipFile(self.build()) as z:
            expected = set(tool.FILES) | {"virtualcar.ini", "BUILDINFO.json", "SHA256SUMS.txt"}
            self.assertEqual(set(z.namelist()), {tool.PREFIX + "/" + name for name in expected})
            # Read-only J2534 preflight must actually be usable from unpacked LAB.
            self.assertIn(tool.PREFIX + "/tools/audit_j2534_connect.py", z.namelist())
            self.assertIn(tool.PREFIX + "/README_P3TOOL_J2534_PREFLIGHT_RU.md", z.namelist())
            self.assertFalse(any("private" in path.lower() or "dump" in path.lower()
                                 for path in z.namelist()))

    def test_02_p2_strict_default_and_metadata_enabled(self):
        with zipfile.ZipFile(self.build()) as z:
            active = z.read(tool.PREFIX + "/virtualcar.ini").decode("utf-8")
            self.assertIn("[Diagnostics]\nBackendTelemetryEnabled=1", active)
            self.assertIn("StrictRouting = 1", active)
            self.assertIn("ECUCount=1", active)
            self.assertIn("B9FBFrameCount=0", active)
            self.assertNotIn("DIDF1B0Hex=", active)

    def test_03_archive_checksums_match_all_entries(self):
        with zipfile.ZipFile(self.build()) as z:
            checks = z.read(tool.PREFIX + "/SHA256SUMS.txt").decode("ascii").splitlines()
            self.assertEqual(len(checks), len(z.namelist()) - 1)
            for line in checks:
                digest, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256(z.read(tool.PREFIX + "/" + name)).hexdigest(), digest)

    def test_04_outer_checksum_and_source_traceability(self):
        path = self.build()
        line = Path(str(path) + ".sha256").read_text(encoding="ascii")
        self.assertTrue(line.startswith(hashlib.sha256(path.read_bytes()).hexdigest() + "  "))
        with zipfile.ZipFile(path) as z:
            info = json.loads(z.read(tool.PREFIX + "/BUILDINFO.json"))
            self.assertEqual(info["source_commit"], COMMIT)
            self.assertFalse(info["vmware_e2e_verified"])
            self.assertFalse(info["ecu_identity_verified"])
            self.assertTrue(info["backend_telemetry_enabled"])

    def test_05_reject_x64_and_invalid_pe_without_output(self):
        for binary in ("VirtualCarJ2534.dll", "VirtualCarControl.exe"):
            for data in (fake_pe(machine=0x8664, magic=0x020B), b"bad"):
                (self.root / binary).write_bytes(data)
                with self.assertRaises(ValueError):
                    self.build()
                self.assertEqual(list(self.out.iterdir()), [])
                (self.root / binary).write_bytes(fake_pe())

    def test_06_reject_private_vehicle_and_active_d2_fixture(self):
        path = self.root / "virtualcar-p2.ini"
        for profile in (PROFILE.replace(tool.SYNTHETIC_VIN, "PRIVATE_IDENTIFIER"),
                        PROFILE.replace("B9FBFrameCount=0", "B9FBFrameCount=1", 1),
                        PROFILE.replace("StrictRouting = 1", "StrictRouting = 0"),
                        PROFILE + "\n[PassiveTrace]\nEnabled=1\n"):
            path.write_text(profile, encoding="utf-8")
            with self.assertRaises(ValueError):
                self.build()
        self.assertEqual(list(self.out.iterdir()), [])

    def test_07_no_overwrite_and_no_source_mutation(self):
        source = self.root / "virtualcar-p2.ini"
        before = source.read_bytes()
        self.build()
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(len(list(self.out.glob("*.zip"))), 1)

    def test_08_missing_input_invalid_sha_and_symlink_fail_closed(self):
        with self.assertRaises(ValueError):
            tool.create_package(self.root, self.out, "bad", "vmware-lab-test")
        required = self.root / "scripts" / "install.ps1"
        required.unlink()
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual(list(self.out.iterdir()), [])

    def test_09_two_phase_collector_and_every_required_script_bundled(self):
        names = (
            "tools/audit_sectorv_operator_session.py",
            "tools/invoke_sectorv_operator.ps1",
            "tools/audit_sectorv_fresh_window.py",
            "tools/audit_sectorv_ui_window_triage.py",
            "tools/audit_sectorv_ui_observation.py",
            "tools/audit_vmware_provider_provenance.py",
            "tools/audit_vmware_sectorv_process.ps1",
            "native-cpp/tests/verify_pe_exports.py",
            "README_SECTORV_FRESH_WINDOW_RU.md",
        )
        with zipfile.ZipFile(self.build()) as archive:
            for name in names:
                with self.subTest(name=name):
                    self.assertIn(tool.PREFIX + "/" + name, archive.namelist())
            self.assertEqual(len(archive.namelist()), len(set(archive.namelist())))

    def test_10_operator_import_closure_uses_same_relative_paths_as_zip(self):
        # Read the real checked-in scripts, not the fake fixture binaries.
        source = MODULE.parents[1]
        for relative in (
            "tools/audit_sectorv_operator_session.py",
            "tools/audit_sectorv_fresh_window.py",
            "tools/audit_sectorv_ui_window_triage.py",
            "tools/audit_vmware_provider_provenance.py",
        ):
            content = (source / relative).read_text(encoding="utf-8")
            self.assertIn(relative, tool.FILES.values())
            for required in (
                "audit_sectorv_fresh_window",
                "audit_sectorv_ui_window_triage",
                "audit_sectorv_ui_observation",
            ) if relative.endswith("operator_session.py") else ():
                self.assertIn("tools/" + required + ".py", tool.FILES.values())
                self.assertIn(required, content)
        # Provenance's static export parser expects this exact relative tree.
        self.assertIn("native-cpp/tests/verify_pe_exports.py", tool.FILES.values())
        self.assertIn("from verify_pe_exports import EXPORTS",
                      (source / "tools/audit_vmware_provider_provenance.py")
                      .read_text(encoding="utf-8"))

    def test_11_extracted_real_collector_imports_and_displays_help(self):
        # Replace only safe tool stubs with source scripts; test against
        # an extracted archive, never by importing the checkout's sys.path.
        source = MODULE.parents[1]
        for relative in tool.FILES.values():
            if relative.endswith((".py", ".ps1")):
                shutil.copyfile(source / relative, self.root / relative)
        with zipfile.ZipFile(self.build()) as archive:
            extracted = Path(self.temp.name) / "extracted"
            archive.extractall(extracted)
        executable = (extracted / tool.PREFIX / "tools" /
                      "audit_sectorv_operator_session.py")
        run = subprocess.run([sys.executable, str(executable), "--help"],
                             capture_output=True, text=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("begin", run.stdout)
        self.assertIn("finish", run.stdout)
        self.assertIn("--module-snapshot", run.stdout)

    def test_12_extracted_package_preserves_old_audit_cli_entrypoints(self):
        source = MODULE.parents[1]
        for relative in tool.FILES.values():
            if relative.endswith(".py"):
                shutil.copyfile(source / relative, self.root / relative)
        with zipfile.ZipFile(self.build()) as archive:
            extracted = Path(self.temp.name) / "extracted"
            archive.extractall(extracted)
        for script in ("audit_sectorv_fresh_window.py",
                       "audit_sectorv_ui_window_triage.py",
                       "audit_vmware_provider_provenance.py"):
            with self.subTest(script=script):
                path = extracted / tool.PREFIX / "tools" / script
                result = subprocess.run([sys.executable, str(path), "--help"],
                                        capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_13_missing_collector_or_transitive_helper_rejects_package(self):
        for name in ("tools/audit_sectorv_operator_session.py",
                     "tools/audit_sectorv_fresh_window.py",
                     "native-cpp/tests/verify_pe_exports.py",
                     "tools/audit_vmware_sectorv_process.ps1"):
            with self.subTest(name=name):
                target = self.root / name
                data = target.read_bytes()
                target.unlink()
                try:
                    with self.assertRaises(ValueError):
                        self.build()
                    self.assertFalse(any(self.out.iterdir()))
                finally:
                    target.write_bytes(data)

    def test_14_local_lab_manifest_never_claims_gui_acceptance(self):
        with zipfile.ZipFile(self.build()) as archive:
            metadata = json.loads(archive.read(
                tool.PREFIX + "/BUILDINFO.json"))
            self.assertEqual(metadata["source_commit"], COMMIT)
            self.assertEqual(metadata["architecture"], "windows-x86-pe32")
            self.assertTrue(metadata["two_phase_operator_collector_included"])
            self.assertFalse(metadata["operator_gui_acceptance_verified"])
            self.assertFalse(metadata["vmware_e2e_verified"])
            self.assertFalse(metadata["ecu_identity_verified"])
            for word in ("C:\\\\Users", "private-vin", "raw-log"):
                self.assertNotIn(word, json.dumps(metadata).lower())


    def _extracted_real_lab(self):
        source = MODULE.parents[1]
        for relative in tool.FILES.values():
            if relative.endswith((".py", ".ps1")):
                shutil.copyfile(source / relative, self.root / relative)
        with zipfile.ZipFile(self.build()) as archive:
            extracted = Path(self.temp.name) / "extracted"
            archive.extractall(extracted)
        return extracted / tool.PREFIX

    def test_15_extracted_package_detects_its_own_root_not_parent_directory(self):
        lab = self._extracted_real_lab()
        tools_dir = lab / "tools"
        command = ("import sys;sys.path.insert(0,sys.argv[1]);"
                   "import audit_sectorv_fresh_window as fresh;"
                   "print(fresh.ROOT)")
        result = subprocess.run([sys.executable, "-c", command, str(tools_dir)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()).resolve(), lab.resolve())

    def test_16_extracted_collector_can_create_private_baseline_beside_lab(self):
        lab = self._extracted_real_lab()
        private = Path(self.temp.name) / "separate-private"
        private.mkdir()
        j = private / "empty-j2534.log"
        b = private / "empty-backend.jsonl"
        j.write_bytes(b"")
        b.write_bytes(b"")
        session = private / "session-1"
        collector = lab / "tools" / "audit_sectorv_operator_session.py"
        result = subprocess.run([
            sys.executable, str(collector), "begin",
            "--session-dir", str(session), "--j2534", str(j),
            "--backend", str(b)],
            capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((session / "p0-before.private.json").is_file())
        self.assertFalse((session / "p0-triage.redacted.json").exists())
        self.assertFalse((session / "p0-window.redacted.json").exists())

    def test_17_extracted_collector_refuses_outputs_inside_package(self):
        lab = self._extracted_real_lab()
        private = Path(self.temp.name) / "outside"
        private.mkdir()
        j = private / "j2534.log"
        b = private / "backend.jsonl"
        j.write_bytes(b"")
        b.write_bytes(b"")
        forbidden = lab / "forbidden-session"
        collector = lab / "tools" / "audit_sectorv_operator_session.py"
        result = subprocess.run([
            sys.executable, str(collector), "begin",
            "--session-dir", str(forbidden), "--j2534", str(j),
            "--backend", str(b)],
            capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(forbidden.exists())
        self.assertNotIn(str(j), result.stderr)

    def test_18_packaged_powershell_module_report_has_correct_sibling_boundary(self):
        if sys.platform != "win32":
            self.skipTest("requires Windows PowerShell 5.1")
        powershell = shutil.which("powershell.exe")
        if not powershell:
            self.skipTest("PowerShell 5.1 not available")
        lab = self._extracted_real_lab()
        sibling = Path(self.temp.name) / "extracted" / "redacted-module.json"
        script = lab / "tools" / "audit_vmware_sectorv_process.ps1"
        result = subprocess.run([
            powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(script), "-OperatorSession", "-OutputFile", str(sibling)],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(sibling.read_text(encoding="utf-8-sig"))
        self.assertEqual(report["schema_version"],
                         "virtualcar-sectorv-process-binding-operator-v1")
        self.assertEqual(report["accepted_vin_or_ecu"], "not_verified")
        self.assertNotIn(str(self.temp.name), json.dumps(report))
        self.assertFalse((lab / "redacted-module.json").exists())


    def _assert_unreviewed_profile_rejected(self, name, data):
        path = self.root / name
        original = path.read_bytes()
        self.assertNotEqual(data, original)
        try:
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "unreviewed_lab_profile_source"):
                self.build()
            self.assertEqual(list(self.out.iterdir()), [])
        finally:
            path.write_bytes(original)

    def test_19_reviewed_p2_and_default_profiles_match_approved_sha256(self):
        attributes = (SOURCE_ROOT.parent / ".gitattributes").read_text(encoding="utf-8")
        for name in tool.APPROVED_INI_SHA256:
            self.assertIn("emulator/" + name + " text eol=lf", attributes)
        for name, expected in tool.APPROVED_INI_SHA256.items():
            with self.subTest(name=name):
                data = (self.root / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), expected)
        with zipfile.ZipFile(self.build()) as archive:
            for name in tool.APPROVED_INI_SHA256:
                self.assertEqual(archive.read(tool.PREFIX + "/" + name),
                                 (self.root / name).read_bytes())

    def test_20_reject_staged_b9fb_frame_even_with_count_zero(self):
        data = (self.root / "virtualcar-p2.ini").read_bytes()
        self._assert_unreviewed_profile_rejected(
            "virtualcar-p2.ini",
            data.replace(b"B9FBFrameCount=0",
                         b"B9FBFrameCount=0\nB9FBFrame0=10 00 00 00", 1))

    def test_21_reject_donor_like_comment_in_p2_source(self):
        data = (self.root / "virtualcar-p2.ini").read_bytes()
        self._assert_unreviewed_profile_rejected(
            "virtualcar-p2.ini", data + b"; DONOR_PRIVATE_MARKER=do-not-export\n")

    def test_22_reject_p2_unreviewed_ecu_part_number(self):
        data = (self.root / "virtualcar-p2.ini").read_bytes()
        self._assert_unreviewed_profile_rejected(
            "virtualcar-p2.ini",
            data.replace(b"PartNumber=VIRTUAL-ECU",
                         b"PartNumber=UNREVIEWED-PRIVATE"))

    def test_23_reject_p2_disabled_passive_trace_payload(self):
        data = (self.root / "virtualcar-p2.ini").read_bytes()
        self._assert_unreviewed_profile_rejected(
            "virtualcar-p2.ini",
            data + b"\n[PassiveTrace]\nEnabled=0\nFrame0=AA BB\n")

    def test_24_reject_default_did_payload_even_when_inactive(self):
        data = (self.root / "virtualcar-default.ini").read_bytes()
        self._assert_unreviewed_profile_rejected(
            "virtualcar-default.ini",
            data.replace(b"DIDF1B0Hex=", b"DIDF1B0Hex=DEADBEEF", 1))

    def test_25_reject_private_comment_in_default_source(self):
        data = (self.root / "virtualcar-default.ini").read_bytes()
        self._assert_unreviewed_profile_rejected(
            "virtualcar-default.ini", data + b"; DONOR_PRIVATE_MARKER=do-not-export\n")

    def test_26_reject_default_source_vin_change(self):
        data = (self.root / "virtualcar-default.ini").read_bytes()
        self._assert_unreviewed_profile_rejected(
            "virtualcar-default.ini",
            data.replace(tool.SYNTHETIC_VIN.encode(), b"UNREVIEWED-IDENTITY"))


if __name__ == "__main__":
    unittest.main()
