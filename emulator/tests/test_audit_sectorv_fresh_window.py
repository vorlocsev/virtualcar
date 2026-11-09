"""Synthetic read-only append-window and complete GUI-triage CLI regressions."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_sectorv_fresh_window as gate
import audit_sectorv_ui_window_triage as triage
from audit_sectorv_ui_observation import SCHEMA as GUI_SCHEMA


def be(*words):
    return " ".join(f"{byte:02X}" for word in words for byte in word.to_bytes(4, "big"))


def log_event(message, *, pid="DEADBEEF"):
    return "[PID=" + pid + " SyntheticClient.exe] " + message + "\n"


def b9fb_no_fixture():
    return "".join([
        log_event("TX context channel/protocol/flags/baud/time-us (BE) " +
                  be(1, 5, 0, 500000, 100000)),
        log_event("TX (app request) 00 0F FF FE CB 50 B9 FB 00 00 00 00"),
        log_event("P2 D2 read command: no validated response fixture"),
    ])


def backend_evt(kind, *, rid=1, tick=1000000, route="CEM",
                reason="none", outcome="unknown", probe=None):
    obj = {
        "format": "virtualcar-backend-v1", "session_id": "0123456789abcdef",
        "request_id": rid, "kind": kind, "tick": tick, "freq": 1000000,
        "channel": 1, "protocol": 5, "baud": 500000, "route": route,
        "reason": reason, "outcome": outcome
    }
    if probe:
        obj["probe"] = probe
    return json.dumps(obj) + "\n"


class FreshWindowTests(unittest.TestCase):
    def test_01_new_b9fb_no_fixture_distinct_from_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            j, b = root / "private-j2534.log", root / "private-backend.jsonl"
            j.write_text("historical unreadable preamble\n", encoding="utf-8")
            b.write_text("historical invalid record\n", encoding="utf-8")
            baseline = gate._baseline(j, b)
            with j.open("a", encoding="utf-8") as out:
                out.write(b9fb_no_fixture())
            with b.open("a", encoding="utf-8") as out:
                out.write("".join([
                backend_evt("tx_received"),
                backend_evt("probe_classified", probe="D2_50_B9FB"),
                backend_evt("request_completed", reason="missing_profile",
                            outcome="no_response", tick=1001000),
                ]))
            j_lines, jm = gate._append_lines(j, baseline["j2534"])
            b_lines, bm = gate._append_lines(b, baseline["backend"])
            self.assertEqual((jm["complete_lines"], bm["complete_lines"]), (3, 3))
            # Production project auditors process the in-memory suffix only.
            report = gate.summarize(j_lines, b_lines, operator_one_run=True)
            target = report["discovery"]["d2"]["0x50"]["B9FB"]
            self.assertEqual(target["requests"], 1)
            self.assertEqual(target["statuses"], {"no_fixture": 1})
            self.assertEqual(target["rx_frame_buckets"]["zero"], 1)
            self.assertEqual(report["backend"]["d2_probe_coverage"]
                             ["D2_50_B9FB"]["requests"], 1)
            self.assertEqual(report["client_vehicle_identity_accepted"], "not_verified")
            self.assertEqual(report["cross_log_transaction_attribution"],
                             "not_established")
            self.assertFalse(report["replay_approved"])

    def test_02_historical_prefix_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "private.log"
            f.write_bytes(b"OLD prefix\n")
            base = gate._snapshot(f)
            f.write_bytes(b"NEW prefix\n" + b"fresh\n")
            with self.assertRaises(ValueError):
                gate._append_lines(f, base)

    def test_03_absent_baseline_and_absent_post_are_not_failures(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "missing.log"
            base = gate._snapshot(f)
            self.assertFalse(base["present"])
            lines, meta = gate._append_lines(f, base)
            self.assertEqual(lines, [])
            self.assertFalse(meta["source_present"])
            f.write_bytes(b"FIRST complete\nSECOND complete\n")
            lines, meta = gate._append_lines(f, base)
            self.assertEqual(len(lines), 2)
            self.assertFalse(meta["prefix_verified"])

    def test_04_incomplete_old_and_new_lines_are_discarded(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "log.txt"
            f.write_bytes(b"old partial")
            base = gate._snapshot(f)
            with f.open("ab") as out:
                out.write(b" continuation\naccepted\nlast incomplete")
            lines, meta = gate._append_lines(f, base)
            self.assertEqual(lines, ["accepted\n"])
            self.assertTrue(meta["dropped_first"])
            self.assertTrue(meta["dropped_last"])
            self.assertEqual(meta["complete_lines"], 1)

    def test_05_truncation_and_excessive_growth_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "log.txt"
            f.write_bytes(b"baseline\n" * 3)
            base = gate._snapshot(f)
            f.write_bytes(b"short\n")
            with self.assertRaises(ValueError):
                gate._append_lines(f, base)
            f.write_bytes(b"baseline\n" * 3 + b"new\n")
            current = gate.MAX_APPEND
            try:
                gate.MAX_APPEND = 2
                with self.assertRaises(ValueError):
                    gate._append_lines(f, base)
            finally:
                gate.MAX_APPEND = current

    def test_06_manifest_is_private_and_exclusive(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            j, b, manifest = root / "input.log", root / "events.jsonl", root / "baseline.json"
            j.write_bytes(b"initial\n")
            b.write_bytes(b"")
            self.assertEqual(gate.main(["baseline", "--j2534", str(j), "--backend",
                                        str(b), "--manifest", str(manifest)]), 0)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertTrue(data["private_do_not_share"])
            self.assertEqual(data["j2534"]["bytes"], 8)
            self.assertEqual(data["j2534"]["sha256"],
                             hashlib.sha256(b"initial\n").hexdigest())
            self.assertNotIn(str(j), manifest.read_text(encoding="utf-8"))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(gate.main(["baseline", "--j2534", str(j),
                                            "--backend", str(b), "--manifest",
                                            str(manifest)]), 2)
            self.assertEqual(j.read_bytes(), b"initial\n")

    def test_07_refuse_private_paths_and_invalid_manifests(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inputfile = root / "in.log"
            inputfile.write_bytes(b"")
            with self.assertRaises(ValueError):
                gate._external_output(inputfile, (inputfile,))
            with self.assertRaises(ValueError):
                gate._validate_baseline({
                    "schema_version": gate.BASELINE_SCHEMA, "private_do_not_share": True,
                    "j2534": {"present": True, "bytes": True,
                              "sha256": "f" * 64, "ended_newline": True},
                    "backend": gate._snapshot(root / "missing.jsonl")
                })
            with self.assertRaises(ValueError):
                gate._external_output(gate.ROOT / "not-safe-report.json", (inputfile,))

    def test_08_reject_run_claim_from_unverified_or_malformed_input(self):
        with self.assertRaises(ValueError):
            gate.summarize([], [], operator_one_run=1)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            j, b, manifest, output = (root / x for x in
                                      ("j.log", "b.jsonl", "manifest.json", "out.json"))
            j.write_text("", encoding="utf-8")
            b.write_text("", encoding="utf-8")
            manifest.write_text("{}", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(gate.main(["analyze", "--j2534", str(j),
                                            "--backend", str(b), "--manifest", str(manifest),
                                            "--output", str(output)]), 2)
            self.assertFalse(output.exists())


    @staticmethod
    def _registered_provider(path_byte="a", file_byte="b"):
        return {
            "state": "installed_library_x86",
            "path_sha256": path_byte * 64,
            "file_sha256": file_byte * 64,
            "bytes": 512,
        }

    def test_09_same_x86_provider_only_proves_endpoint_stability(self):
        before = self._registered_provider()
        result = gate._provider_endpoints(before, dict(before))
        self.assertEqual(result["binary_endpoint_consistency"], "same_at_endpoints_only")
        self.assertEqual(result["loaded_in_sectorv_client"], "not_observed")
        self.assertEqual(result["during_run_immutability"], "not_verified")
        self.assertFalse(result["same_guest_independently_attested"])

    def test_10_changed_binary_or_registered_path_not_a_stable_run(self):
        before = self._registered_provider()
        for after in (self._registered_provider(file_byte="c"),
                      self._registered_provider(path_byte="d")):
            with self.subTest(kind=after):
                result = gate._provider_endpoints(before, after)
                self.assertEqual(result["binary_endpoint_consistency"],
                                 "changed_between_endpoints")

    def test_11_missing_and_changing_provider_cannot_claim_identity(self):
        absent = {key: None for key in ("path_sha256", "file_sha256", "bytes")}
        absent["state"] = "canonical_provider_absent"
        unchanged = gate._provider_endpoints(absent, dict(absent))
        self.assertEqual(unchanged["binary_endpoint_consistency"], "not_verified")
        changed = gate._provider_endpoints(absent, self._registered_provider())
        self.assertEqual(changed["binary_endpoint_consistency"], "provider_state_changed")

    def test_12_private_manifest_fingerprint_strictly_validated(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = gate._baseline(root / "missing-j2534.log", root / "missing-backend.jsonl")
            manifest["provider"] = self._registered_provider()
            gate._validate_baseline(manifest)
            for bad in (
                    {**self._registered_provider(), "path_sha256": "secret-private"},
                    {**self._registered_provider(), "bytes": True},
                    {**self._registered_provider(), "binary_path": "C:/private/fixture.dll"},
                    {**self._registered_provider(), "file_sha256": "A" * 64},
            ):
                altered = dict(manifest)
                altered["provider"] = bad
                with self.subTest(bad=list(bad)), self.assertRaises(ValueError):
                    gate._validate_baseline(altered)
            original = dict(manifest)
            original["schema_version"] = "virtualcar-private-log-baseline-v1"
            with self.assertRaises(ValueError):
                gate._validate_baseline(original)

    def test_13_cli_redacts_provider_hashes_with_real_append_window(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            logs = root / "private-j2534.log"
            backend = root / "private-backend.jsonl"
            baseline = root / "PRIVATE-before.json"
            report = root / "safe-report.json"
            logs.write_text("historical private VIN YV1UNKNOWN\n", encoding="utf-8")
            backend.write_text("", encoding="utf-8")
            fingerprint = self._registered_provider()
            with mock.patch.object(gate, "_provider_snapshot", return_value=fingerprint):
                self.assertEqual(gate.main([
                    "baseline", "--j2534", str(logs), "--backend", str(backend),
                    "--manifest", str(baseline)]), 0)
            with logs.open("a", encoding="utf-8") as source:
                source.write(b9fb_no_fixture())
            with backend.open("a", encoding="utf-8") as source:
                source.write(backend_evt("tx_received"))
            with mock.patch.object(gate, "_provider_snapshot", return_value=dict(fingerprint)):
                self.assertEqual(gate.main([
                    "analyze", "--j2534", str(logs), "--backend", str(backend),
                    "--manifest", str(baseline), "--output", str(report),
                    "--operator-one-run-confirmed"]), 0)
            out = report.read_text(encoding="utf-8")
            result = json.loads(out)
            self.assertEqual(result["registered_provider"]["binary_endpoint_consistency"],
                             "same_at_endpoints_only")
            self.assertEqual(result["operator_one_run_confirmed"], True)
            self.assertEqual(result["client_vehicle_identity_accepted"], "not_verified")
            self.assertNotIn("YV1UNKNOWN", out)
            self.assertNotIn("PRIVATE-before", out)
            self.assertNotIn("a" * 64, out)
            self.assertNotIn("b" * 64, out)
            self.assertNotIn(str(logs), out)

    def test_14_changed_provider_requires_a_categorical_result_not_success(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            logs = root / "j.log"
            backend = root / "b.jsonl"
            before = root / "manifest.json"
            after = root / "report.json"
            with mock.patch.object(gate, "_provider_snapshot",
                                   return_value=self._registered_provider()):
                self.assertEqual(gate.main([
                    "baseline", "--j2534", str(logs), "--backend", str(backend),
                    "--manifest", str(before)]), 0)
            with mock.patch.object(gate, "_provider_snapshot",
                                   return_value=self._registered_provider(file_byte="c")):
                self.assertEqual(gate.main([
                    "analyze", "--j2534", str(logs), "--backend", str(backend),
                    "--manifest", str(before), "--output", str(after)]), 0)
            result = json.loads(after.read_text())
            self.assertEqual(result["registered_provider"]["binary_endpoint_consistency"],
                             "changed_between_endpoints")
            self.assertEqual(result["client_vehicle_identity_accepted"], "not_verified")



    def test_15_bounded_window_counts_scheduled_and_direct_b9fb_separately(self):
        # Two real request origins; neither counts as accepted vehicle identity.
        periodic = "".join((
            log_event("Periodic TX context channel/protocol/flags/baud/time-us (BE) "
                      + be(1, 5, 0, 500000, 103000)),
            log_event("J2534 periodic TX (read-only simulator) "
                      "00 0F FF FE CB 50 B9 FB 00 00 00 00"),
            log_event("P2 D2 read command: no validated response fixture"),
        ))
        history = b9fb_no_fixture() + periodic
        backend = "".join((
            backend_evt("tx_received", rid=1, tick=1000000),
            backend_evt("probe_classified", rid=1, probe="D2_50_B9FB",
                        tick=1001000),
            backend_evt("request_completed", rid=1, reason="missing_profile",
                        outcome="no_response", tick=1002000),
            backend_evt("tx_received", rid=2, tick=1003000),
            backend_evt("probe_classified", rid=2, probe="D2_50_B9FB",
                        tick=1004000),
            backend_evt("request_completed", rid=2, reason="missing_profile",
                        outcome="no_response", tick=1005000),
        ))
        result = gate.summarize(history.splitlines(True), backend.splitlines(True),
                                operator_one_run=True)
        d2 = result["discovery"]["d2"]["0x50"]["B9FB"]
        self.assertEqual(d2["requests"], 2)
        self.assertEqual(d2["statuses"], {"no_fixture": 2})
        self.assertEqual(result["backend"]["d2_probe_coverage"]
                         ["D2_50_B9FB"]["requests"], 2)
        self.assertEqual(result["cross_log_transaction_attribution"],
                         "not_established")
        self.assertEqual(result["client_vehicle_identity_accepted"],
                         "not_verified")
        raw = json.dumps(result)
        self.assertNotIn("YV1LAB", raw)
        self.assertNotIn("DEADBEEF", raw)

    def test_16_bounded_window_refuses_unscoped_periodic_as_gui_request(self):
        marker = log_event("J2534 periodic TX (read-only simulator) "
                           "00 0F FF FE CB 50 B9 FB 00 00 00 00")
        backend = "".join((
            backend_evt("tx_received", rid=3, tick=1100000),
            backend_evt("probe_classified", rid=3, probe="D2_50_B9FB",
                        tick=1101000),
            backend_evt("request_completed", rid=3, reason="missing_profile",
                        outcome="no_response", tick=1102000),
        ))
        result = gate.summarize(marker.splitlines(True), backend.splitlines(True))
        self.assertEqual(result["discovery"]["d2"]["0x50"]["B9FB"]["requests"], 0)
        self.assertEqual(result["backend"]["d2_probe_coverage"]
                         ["D2_50_B9FB"]["requests"], 1)
        self.assertEqual(result["client_vehicle_identity_accepted"],
                         "not_verified")
        self.assertEqual(result["cross_log_transaction_attribution"],
                         "not_established")



    def test_17_bounded_window_marks_byte_short_b9_final_partial(self):
        # End-to-end audit: a single 0x4F byte cannot finish a B9 CAN RX.
        private_j2534 = "".join((
            log_event("TX context channel/protocol/flags/baud/time-us (BE) "
                      + be(1, 5, 0, 500000, 100000)),
            log_event("TX (app request) 00 0F FF FE CB 50 B9 FB 00 00 00 00"),
            log_event("RX context channel/protocol/status/baud/time-us (BE) "
                      + be(1, 5, 0, 500000, 102000)),
            log_event("PassThruReadMsgs -> delivered "
                      "01 20 00 03 8F 50 F9 FB 57 00 30 66"),
            log_event("RX context channel/protocol/status/baud/time-us (BE) "
                      + be(1, 5, 0, 500000, 103000)),
            log_event("PassThruReadMsgs -> delivered 01 20 00 03 4F"),
        ))
        result = gate.summarize(private_j2534.splitlines(True), [],
                                operator_one_run=True)
        target = result["discovery"]["d2"]["0x50"]["B9FB"]
        self.assertEqual(target["requests"], 1)
        self.assertEqual(target["statuses"], {"partial_rx": 1})
        self.assertEqual(target["rx_frame_buckets"]["one_to_twelve"], 1)
        self.assertEqual(result["cross_log_transaction_attribution"],
                         "not_established")
        self.assertEqual(result["client_vehicle_identity_accepted"],
                         "not_verified")
        report = json.dumps(result)
        for secret in ("DEADBEEF", "SyntheticClient.exe", "YV1LAB",
                       "01 20 00 03 4F"):
            self.assertNotIn(secret, report)



class FreshToGuiPipelineTests(unittest.TestCase):
    """CLI-to-CLI synthetic checks: raw private text -> redacted window -> GUI triage.

    No real client was observed. The human-ui provenance fixture below is
    simulated solely to test the shape gate; it is not evidence of a VM session.
    """

    @staticmethod
    def _provider(byte="b"):
        return {
            "state": "installed_library_x86", "path_sha256": "a" * 64,
            "file_sha256": byte * 64, "bytes": 512,
        }

    @staticmethod
    def _gui():
        return {
            "schema_version": GUI_SCHEMA, "client": "SectorV",
            "scenario": "P2_MY2009_lab", "source": "human_ui_observation",
            "run_scope": "single_vm_client_run",
            "read_only": True, "physical_adapter_disconnected": True,
            "observations": {
                "adapter_listed": "yes", "adapter_selected": "yes",
                "connection": "connected", "ecu_list": "empty",
                "vehicle_identity": "not_displayed",
                "error_category": "vin_read_failed",
            },
        }

    @staticmethod
    def _backend_no_fixture():
        return "".join([
            backend_evt("tx_received"),
            backend_evt("probe_classified", probe="D2_50_B9FB"),
            backend_evt("request_completed", reason="missing_profile",
                        outcome="no_response", tick=1001000),
        ]).encode("utf-8")

    def _run_pipeline(self, *, j_append=b"", b_append=b"",
                      j_initial=b"historical text\n", changed_provider=False,
                      pair=True, edit_gui=None):
        """Exercise all three production CLIs with local, synthetic files."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            j = root / "private-j2534.log"
            b = root / "private-backend.jsonl"
            manifest = root / "private-manifest.json"
            report = root / "redacted-window.json"
            gui = root / "private-gui.json"
            final = root / "redacted-gui-triage.json"
            if j_initial is not None:
                j.write_bytes(j_initial)
            b.write_bytes(b"historical backend\n")

            common = ["--j2534", str(j), "--backend", str(b),
                      "--manifest", str(manifest)]
            with contextlib.redirect_stdout(io.StringIO()):
                with mock.patch.object(gate, "_provider_snapshot",
                                       return_value=self._provider()):
                    self.assertEqual(gate.main(["baseline", *common]), 0)
                if j_append:
                    with j.open("ab") as out:
                        out.write(j_append)
                if b_append:
                    with b.open("ab") as out:
                        out.write(b_append)
                with mock.patch.object(gate, "_provider_snapshot",
                                       return_value=self._provider(
                                           "c" if changed_provider else "b")):
                    args = ["analyze", *common, "--output", str(report)]
                    if pair:
                        args.append("--operator-one-run-confirmed")
                    self.assertEqual(gate.main(args), 0)

            observation = self._gui()
            if edit_gui is not None:
                edit_gui(observation)
            gui.write_text(json.dumps(observation), encoding="utf-8")
            args = ["--window-report", str(report),
                    "--ui-observation", str(gui), "--output", str(final)]
            if pair:
                args.append("--operator-same-run-confirmed")
            with contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(io.StringIO()):
                code = triage.main(args)
            window_text = report.read_text(encoding="utf-8")
            final_text = final.read_text(encoding="utf-8") if final.exists() else ""
            return (json.loads(window_text),
                    json.loads(final_text) if final_text else None,
                    window_text, final_text, code)

    def _assert_unverified(self, result):
        self.assertEqual(result["client_vehicle_identity_accepted"], "not_verified")
        self.assertFalse(result["oem_vin_and_ecu_verified"])
        self.assertEqual(result["transaction_level_correlation"], "not_established")
        self.assertFalse(result["replay_approved"])

    def test_15_cli_pipeline_b9fb_no_fixture_not_vin_failure_proof(self):
        w, r, raw_w, raw_r, code = self._run_pipeline(
            j_append=b9fb_no_fixture().encode("utf-8"),
            b_append=self._backend_no_fixture())
        self.assertEqual(code, 0)
        self.assertEqual(w["discovery"]["d2"]["0x50"]["B9FB"]["statuses"],
                         {"no_fixture": 1})
        self.assertEqual(w["backend"]["d2_probe_coverage"]["D2_50_B9FB"],
                         {"requests": 1, "statuses": {"no_fixture": 1}})
        self.assertEqual(r["b9fb_request_count_in_window"], 1)
        self.assertEqual(r["b9fb_requests_with_nonzero_rx_in_window"], 0)
        self.assertEqual(r["first_next_gate"], "review_b9fb_without_observed_rx")
        self._assert_unverified(r)
        for secret in ("0123456789abcdef", "DEADBEEF", "private-j2534",
                       "PassThruReadMsgs", "00 0F FF FE", "a" * 64):
            self.assertNotIn(secret, raw_w + raw_r)

    def test_16_cli_complete_unrelated_log_only_b9fb_absence_is_bounded(self):
        w, r, _, _, code = self._run_pipeline(
            j_append=log_event("unrelated synthetic diagnostic marker").encode())
        self.assertEqual(code, 0)
        self.assertEqual(w["windows"]["j2534"]["complete_lines"], 1)
        self.assertEqual(r["b9fb_request_count_in_window"], 0)
        self.assertEqual(r["first_next_gate"],
                         "review_absent_b9fb_in_bounded_j2534_window")
        self._assert_unverified(r)

    def test_17_cli_discarded_first_line_downgrades_absence(self):
        _, r, _, _, code = self._run_pipeline(
            j_initial=b"old incomplete",
            j_append=b" continued\n" +
                     log_event("unrelated synthetic marker").encode())
        self.assertEqual(code, 0)
        self.assertTrue(r["j2534_discarded_partial_boundary_lines"])
        self.assertEqual(r["first_next_gate"],
                         "review_discarded_j2534_line_boundaries")
        self._assert_unverified(r)

    def test_18_cli_discarded_last_line_downgrades_absence(self):
        _, r, _, _, code = self._run_pipeline(
            j_append=log_event("unrelated synthetic marker").encode()
                     + b"final incomplete")
        self.assertEqual(code, 0)
        self.assertTrue(r["j2534_discarded_partial_boundary_lines"])
        self.assertEqual(r["first_next_gate"],
                         "review_discarded_j2534_line_boundaries")
        self._assert_unverified(r)

    def test_19_cli_no_new_lines_is_missing_window_evidence(self):
        _, r, _, _, code = self._run_pipeline()
        self.assertEqual(code, 0)
        self.assertEqual(r["first_next_gate"],
                         "obtain_bounded_j2534_window_evidence")
        self._assert_unverified(r)

    def test_20_cli_provider_changed_before_vin_classification(self):
        _, r, _, _, code = self._run_pipeline(
            changed_provider=True,
            j_append=b9fb_no_fixture().encode("utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(r["provider_endpoint_consistency"],
                         "changed_between_endpoints")
        self.assertEqual(r["first_next_gate"],
                         "resolve_provider_endpoint_change")
        self._assert_unverified(r)

    def test_21_cli_without_operator_pairing_stays_unpaired(self):
        _, r, _, _, code = self._run_pipeline(
            pair=False, j_append=b9fb_no_fixture().encode("utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(r["run_pairing"], "unpaired")
        self.assertEqual(r["first_next_gate"],
                         "establish_isolated_same_run_evidence")
        self._assert_unverified(r)

    def test_22_cli_rejects_private_gui_free_text_without_final_report(self):
        def inject_private_text(gui):
            gui["observations"]["raw_vin"] = "YV1SYNTHETIC01234"

        w, r, window_text, final_text, code = self._run_pipeline(
            j_append=b9fb_no_fixture().encode("utf-8"),
            edit_gui=inject_private_text)
        self.assertEqual(code, 2)
        self.assertIsNone(r)
        self.assertEqual(final_text, "")
        self.assertEqual(w["client_vehicle_identity_accepted"], "not_verified")
        self.assertNotIn("YV1SYNTHETIC01234", window_text)


if __name__ == "__main__":
    unittest.main()
