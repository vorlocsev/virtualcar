"""Eight synthetic privacy and append-boundary tests. No client, J2534 or CAN writes."""
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


if __name__ == "__main__":
    unittest.main()
