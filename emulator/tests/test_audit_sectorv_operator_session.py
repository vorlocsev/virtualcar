"""Offline synthetic tests for the two-stage authorized SectorV operator collector."""
import contextlib
import io
import json
from pathlib import Path
from unittest import mock
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_sectorv_operator_session as collector


def operator_module():
    return {
        "schema_version": "virtualcar-sectorv-process-binding-operator-v1",
        "scope": "operator_requested_current_host_snapshot_only",
        "observation": "client_not_observed_in_local_snapshot",
        "installed_vs_reference_dll": "not_compared",
        "next_safe_gate": "observe_client_with_gui_open",
        "name_matched_executable_authenticity": "not_verified",
        "operator_same_run_pairing": "not_independently_attested",
        "registered_provider_unchanged_during_run": "not_verified",
        "reference_dll_pe32": "not_assessed_by_this_tool",
        "client_was_launched_by_audit": False,
        "accepted_vin_or_ecu": "not_verified",
    }


def cli(args):
    stdout, stderr = io.StringIO(), io.StringIO()
    # Prevent machine-local registry reads while testing synthetically.
    with mock.patch.object(collector.fresh, "_provider_snapshot",
                           return_value={"state": "runner_not_windows",
                                         "path_sha256": None,
                                         "file_sha256": None,
                                         "bytes": None}):
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = collector.main(args)
    return status, stdout.getvalue(), stderr.getvalue()


class OperatorOneSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.j = self.root / "private-j2534.log"
        self.b = self.root / "private-backend.jsonl"
        self.j.write_bytes(b"")
        self.b.write_bytes(b"")
        self.session = self.root / "lab-run-01"
        self.base = ["--j2534", str(self.j), "--backend", str(self.b),
                     "--session-dir", str(self.session)]
        self.ui = [
            "--isolated-read-only-vm", "--physical-adapter-disconnected",
            "--adapter-listed", "yes", "--adapter-selected", "yes",
            "--connection", "connected", "--ecu-list", "empty",
            "--vehicle-identity", "not_displayed",
            "--error-category", "vin_read_failed",
        ]

    def begin(self):
        result, out, err = cli(["begin", *self.base])
        self.assertEqual(result, 0, err)
        self.assertIn("Private SectorV baseline created", out)
        self.assertTrue((self.session / collector.PRIVATE_MANIFEST).is_file())

    def finish(self, extra=()):
        return cli(["finish", *self.base, *self.ui, *extra])

    def test_01_begin_is_private_exclusive_and_no_ui_inferred(self):
        self.begin()
        files = sorted(p.name for p in self.session.iterdir())
        self.assertEqual(files, [collector.PRIVATE_MANIFEST])
        manifest = json.loads((self.session / files[0]).read_text())
        self.assertTrue(manifest["private_do_not_share"])
        self.assertNotIn("observations", json.dumps(manifest))
        self.assertEqual(cli(["begin", *self.base])[0], 2)

    def test_02_duplicate_sources_fail_before_creating_session(self):
        changed = list(self.base)
        changed[3] = str(self.j)  # --backend path is 4th argument
        result, out, err = cli(["begin", *changed])
        self.assertEqual(result, 2)
        self.assertFalse(self.session.exists())
        self.assertNotIn(str(self.root), err)

    def test_03_finish_without_operator_pairing_is_conservative(self):
        self.begin()
        status, out, err = self.finish()
        self.assertEqual(status, 0, err)
        win = json.loads((self.session / collector.WINDOW_REPORT).read_text())
        result = json.loads((self.session / collector.TRIAGE_REPORT).read_text())
        self.assertFalse(win["operator_one_run_confirmed"])
        self.assertEqual(result["run_pairing"], "unpaired")
        self.assertEqual(result["client_vehicle_identity_accepted"], "not_verified")
        self.assertEqual(result["j2534_binary_loaded_in_gui_client"], "not_verified")
        self.assertEqual(result["first_next_gate"], "establish_isolated_same_run_evidence")
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_04_single_run_is_operator_asserted_not_independently_attested(self):
        self.begin()
        status, _, err = self.finish(["--single-run-confirmed"])
        self.assertEqual(status, 0, err)
        result = json.loads((self.session / collector.TRIAGE_REPORT).read_text())
        self.assertEqual(result["run_pairing"],
                         "operator_asserted_not_independently_verified")
        self.assertFalse(result["same_guest_independently_attested"])
        self.assertEqual(result["transaction_level_correlation"], "not_established")
        # Synthetic platform has no registered x86 provider: that missing
        # provenance takes precedence over an otherwise empty J2534 window.
        self.assertEqual(result["first_next_gate"],
                         "obtain_provider_endpoint_evidence")

    def test_05_optional_local_module_is_never_promoted_to_gui_or_vin(self):
        self.begin()
        module_path = self.root / "operator-module.redacted.json"
        module_path.write_text(json.dumps(operator_module()), encoding="utf-8")
        status, _, err = self.finish([
            "--single-run-confirmed", "--module-snapshot", str(module_path)])
        self.assertEqual(status, 0, err)
        result = json.loads((self.session / collector.TRIAGE_REPORT).read_text())
        m = result["operator_module_snapshot"]
        self.assertEqual(m["observation"], "client_not_observed_in_local_snapshot")
        self.assertFalse(m["same_guest_or_run_attested"])
        self.assertEqual(m["module_used_for_j2534_requests"], "not_verified")
        self.assertFalse(result["oem_vin_and_ecu_verified"])
        self.assertNotIn(str(module_path), json.dumps(result))

    def test_06_missing_isolation_and_unanswered_ui_fields_fail_closed(self):
        self.begin()
        no_hardware = [x for x in self.ui if x != "--physical-adapter-disconnected"]
        status, _, _ = cli(["finish", *self.base, *no_hardware])
        self.assertEqual(status, 2)
        incomplete = self.ui[:-2]
        status, _, _ = cli(["finish", *self.base, *incomplete])
        self.assertEqual(status, 2)
        self.assertFalse((self.session / collector.WINDOW_REPORT).exists())
        self.assertFalse((self.session / collector.TRIAGE_REPORT).exists())

    def test_07_contradictory_gui_observation_fails_before_any_report(self):
        self.begin()
        tokens = list(self.ui)
        tokens[tokens.index("--adapter-listed") + 1] = "no"
        status, _, err = cli(["finish", *self.base, *tokens])
        self.assertEqual(status, 2)
        self.assertFalse((self.session / collector.WINDOW_REPORT).exists())
        self.assertNotIn(str(self.root), err)

    def test_08_raw_paths_and_forged_provenance_never_leak_from_module(self):
        self.begin()
        module_path = self.root / "unsafe-module.json"
        fake = operator_module()
        fake["private_path"] = r"C:\Users\private\VIN-J2534.dll"
        module_path.write_text(json.dumps(fake))
        status, _, err = self.finish(["--module-snapshot", str(module_path)])
        self.assertEqual(status, 2)
        self.assertNotIn("private", err)
        self.assertFalse((self.session / collector.TRIAGE_REPORT).exists())
        self.assertFalse((self.session / collector.WINDOW_REPORT).exists())

    def test_09_historical_log_mutation_is_not_a_new_window(self):
        self.j.write_bytes(b"historical\n")
        self.begin()
        self.j.write_bytes(b"changed!!!\n")
        status, _, err = self.finish(["--single-run-confirmed"])
        self.assertEqual(status, 2)
        self.assertNotIn("historical", err)
        self.assertFalse((self.session / collector.TRIAGE_REPORT).exists())

    def test_10_completion_never_overwrites_evidence(self):
        self.begin()
        self.assertEqual(self.finish()[0], 0)
        before = (self.session / collector.WINDOW_REPORT).read_bytes()
        also = (self.session / collector.TRIAGE_REPORT).read_bytes()
        status, _, err = self.finish()
        self.assertEqual(status, 2)
        self.assertEqual((self.session / collector.WINDOW_REPORT).read_bytes(), before)
        self.assertEqual((self.session / collector.TRIAGE_REPORT).read_bytes(), also)
        self.assertNotIn(str(self.root), err)


if __name__ == "__main__":
    unittest.main()
