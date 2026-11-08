"""Eight synthetic privacy and append-boundary tests. No client, J2534 or CAN writes."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
