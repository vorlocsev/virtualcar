"""Windows-only synthetic integration for the guided offline SectorV operator helper.

No SectorV launch, J2534 load, registration, CAN writes, donor logs or vehicle data.
Tests run on the trusted Windows CI runner, not the user's guest GUI.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "tools" / "invoke_sectorv_operator.ps1"
STATES = (
    "-AdapterListed", "unknown", "-AdapterSelected", "unknown",
    "-Connection", "unknown", "-EcuList", "unknown",
    "-VehicleIdentity", "unknown", "-ErrorCategory", "unknown",
)


@unittest.skipUnless(os.name == "nt", "requires Windows PowerShell 5.1 runner")
class GuidedSectorVOperatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.session = self.dir / "private-session"
        self.jlog = self.dir / "private-j2534.log"
        self.blog = self.dir / "private-backend.jsonl"
        self.jlog.write_text("", encoding="utf-8")
        self.blog.write_text("", encoding="utf-8")
        self.common = (
            "-SessionDir", str(self.session), "-J2534Log", str(self.jlog),
            "-BackendLog", str(self.blog), "-PythonExe", sys.executable,
            "-IsolatedReadOnlyVm", "-PhysicalAdapterDisconnected",
        )

    def run_helper(self, phase, *extra, input_text=None):
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(WRAPPER), "-Phase", phase, *self.common, *extra],
            input=input_text, capture_output=True, text=True, timeout=35,
        )

    def begin(self):
        proc = self.run_helper("Begin")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.session / "p0-before.private.json").is_file())

    def test_01_real_collector_begin_and_finish_keep_acceptance_unverified(self):
        self.begin()
        run = self.run_helper("Finish", "-NonInteractive",
                              "-SingleRunConfirmed", *STATES)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads((self.session / "p0-triage.redacted.json").read_text())
        self.assertEqual(result["run_pairing"],
                         "operator_asserted_not_independently_verified")
        self.assertEqual(result["client_vehicle_identity_accepted"], "not_verified")
        self.assertFalse(result["oem_vin_and_ecu_verified"])
        self.assertNotIn(str(self.dir), json.dumps(result))

    def test_02_begin_requires_explicit_offline_safety_flags(self):
        args = list(self.common)
        args.remove("-PhysicalAdapterDisconnected")
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(WRAPPER), "-Phase", "Begin", *args],
            capture_output=True, text=True, timeout=35)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(self.session.exists())
        self.assertNotIn(str(self.dir), proc.stderr)

    def test_03_repeated_begin_must_never_overwrite_private_baseline(self):
        self.begin()
        p = self.session / "p0-before.private.json"
        original = p.read_bytes()
        proc = self.run_helper("Begin")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(p.read_bytes(), original)
        self.assertNotIn(str(self.dir), proc.stderr)

    def test_04_noninteractive_finish_requires_each_observation(self):
        self.begin()
        proc = self.run_helper("Finish", "-NonInteractive", "-AdapterListed", "unknown")
        self.assertEqual(proc.returncode, 2)
        self.assertFalse((self.session / "p0-triage.redacted.json").exists())
        self.assertNotIn(str(self.dir), proc.stderr)

    def test_05_changed_source_between_phases_rejected_without_reports(self):
        self.begin()
        alternate = self.dir / "replacement-private.log"
        alternate.write_text("", encoding="utf-8")
        args = list(self.common)
        index = args.index("-J2534Log")
        args[index + 1] = str(alternate)
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(WRAPPER), "-Phase", "Finish", *args,
             "-NonInteractive", *STATES],
            capture_output=True, text=True, timeout=35)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse((self.session / "p0-triage.redacted.json").exists())
        self.assertNotIn(str(self.dir), proc.stderr)

    def test_06_gui_contradictions_not_inferred_as_real_client_evidence(self):
        self.begin()
        inconsistent = list(STATES)
        inconsistent[inconsistent.index("-AdapterSelected") + 1] = "yes"
        proc = self.run_helper("Finish", "-NonInteractive", *inconsistent)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse((self.session / "p0-triage.redacted.json").exists())

    def test_07_unknown_prompt_defaults_keep_same_run_unpaired(self):
        self.begin()
        proc = self.run_helper("Finish", input_text="\n" * 6)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads((self.session / "p0-triage.redacted.json").read_text())
        self.assertEqual(result["run_pairing"], "unpaired")
        self.assertEqual(result["gui_connection_state"], "unknown")
        self.assertEqual(result["client_vehicle_identity_accepted"], "not_verified")

    def test_08_invalid_python_path_does_not_echo_private_arguments(self):
        args = list(self.common)
        args[args.index("-PythonExe") + 1] = str(
            self.dir / "PRIVATE_NONEXISTENT.exe")
        bad = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(WRAPPER), "-Phase", "Begin", *args],
            capture_output=True, text=True, timeout=35)
        self.assertEqual(bad.returncode, 2)
        self.assertFalse(self.session.exists())
        self.assertNotIn(str(self.dir), bad.stderr)


    def test_09_module_requires_begin_not_just_an_existing_folder(self):
        self.session.mkdir()
        proc = self.run_helper("Module")
        self.assertEqual(proc.returncode, 2)
        self.assertFalse((self.session / "p0-module.redacted.json").exists())
        self.assertNotIn(str(self.dir), proc.stderr)

    def test_10_module_after_finish_must_not_create_late_evidence(self):
        self.begin()
        done = self.run_helper("Finish", "-NonInteractive", *STATES)
        self.assertEqual(done.returncode, 0, done.stderr)
        proc = self.run_helper("Module")
        self.assertEqual(proc.returncode, 2)
        self.assertFalse((self.session / "p0-module.redacted.json").exists())
        self.assertNotIn(str(self.dir), proc.stderr)

    def test_11_partial_window_report_blocks_module_snapshot(self):
        self.begin()
        (self.session / "p0-window.redacted.json").write_text("{}", encoding="utf-8")
        proc = self.run_helper("Module")
        self.assertEqual(proc.returncode, 2)
        self.assertFalse((self.session / "p0-module.redacted.json").exists())

    def test_12_existing_triage_report_blocks_module_snapshot(self):
        self.begin()
        (self.session / "p0-triage.redacted.json").write_text("{}", encoding="utf-8")
        proc = self.run_helper("Module")
        self.assertEqual(proc.returncode, 2)
        self.assertFalse((self.session / "p0-module.redacted.json").exists())

    def test_13_active_module_snapshot_is_observation_not_gui_proof(self):
        self.begin()
        proc = self.run_helper("Module")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        module_path = self.session / "p0-module.redacted.json"
        module = json.loads(module_path.read_text(encoding="utf-8"))
        self.assertEqual(module["accepted_vin_or_ecu"], "not_verified")
        finished = self.run_helper("Finish", "-NonInteractive", *STATES)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        result = json.loads((self.session / "p0-triage.redacted.json").read_text())
        self.assertFalse(result["oem_vin_and_ecu_verified"])
        self.assertNotIn(str(self.dir), json.dumps(result))

    def test_14_repeated_module_never_overwrites_first_snapshot(self):
        self.begin()
        first = self.run_helper("Module")
        self.assertEqual(first.returncode, 0, first.stderr)
        path = self.session / "p0-module.redacted.json"
        original = path.read_bytes()
        second = self.run_helper("Module")
        self.assertEqual(second.returncode, 2)
        self.assertEqual(path.read_bytes(), original)
        self.assertNotIn(str(self.dir), second.stderr)

    def test_15_module_requires_offline_safety_flags(self):
        self.begin()
        args = list(self.common)
        args.remove("-PhysicalAdapterDisconnected")
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(WRAPPER), "-Phase", "Module", *args],
            capture_output=True, text=True, timeout=35)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse((self.session / "p0-module.redacted.json").exists())
        self.assertNotIn(str(self.dir), proc.stderr)


    def test_16_finish_surfaces_safe_action_without_private_log_content(self):
        self.begin()
        run = self.run_helper("Finish", "-NonInteractive",
                              "-SingleRunConfirmed", *STATES)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(
            (self.session / "p0-triage.redacted.json").read_text(encoding="utf-8"))
        # The VMware runner can have the canonical x86 J2534 provider
        # registered, whereas local/offline synthetic tests do not. Both
        # outcomes are valid, but the instruction must reflect the gate.
        self.assertIn(result["first_next_gate"], (
            "obtain_provider_endpoint_evidence",
            "verify_j2534_provider_and_connect",
        ))
        self.assertTrue(result["first_next_action_ru"])
        # The operator prints the second instruction line in addition to the
        # original fixed summary, not raw input logs or local source paths.
        self.assertGreaterEqual(len(run.stdout.splitlines()), 2)
        self.assertNotIn(str(self.dir), run.stdout)
        self.assertNotIn("DEADBEEF", run.stdout)
        self.assertEqual(result["client_vehicle_identity_accepted"],
                         "not_verified")
        self.assertFalse(result["oem_vin_and_ecu_verified"])



if __name__ == "__main__":
    unittest.main()
