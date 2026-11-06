"""Eight synthetic evidence-only regression groups for SectorV CEM gate.

These are NOT a SectorV binary analysis or a real client log replay.
"""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_sectorv_gate import SCHEMA, audit, main


def example():
    return {
        "schema_version": SCHEMA,
        "client": "SectorV",
        "version": "1.1.0.0",
        "scenario": "P2_MY2005_lab",
        "run_scope": "same_client_run",
        "observations": [
            {"event": "b9fb_matcher", "source": "client_log",
             "observed": 13, "matched": 13, "ignored": 0},
            {"event": "hardware_a3", "source": "client_log",
             "target": "50", "outcome": "timeout", "elapsed_ms": 5000},
            {"event": "hardware_a3", "source": "client_log",
             "target": "40", "outcome": "timeout", "elapsed_ms": 5001},
            {"event": "normal_mode_warning", "source": "client_ui"},
            {"event": "ecu_reachable", "source": "client_ui", "count": 0},
        ],
    }


class SectorVGateEvidenceTests(unittest.TestCase):
    def test_01_b9fb_matcher_then_hardware_timeout_is_not_ecu_identity(self):
        result = audit(example())
        self.assertEqual(result["b9fb_client_matcher"]["matched"], 13)
        self.assertTrue(result["b9fb_client_matcher"]["frame_matcher_complete"])
        self.assertEqual(result["hardware_a3"]["50"]["outcome"], "timeout")
        self.assertEqual(result["hardware_a3"]["40"]["elapsed_ms"], 5001)
        self.assertEqual(result["ecu_reachable_observed"], 0)
        self.assertTrue(result["normal_mode_warning_observed"])
        self.assertEqual(result["b9fb_vehicle_identity_accepted"], "unknown")
        self.assertEqual(result["client_ecu_identification_accepted"], "unknown")
        self.assertFalse(result["replay_approved"])

    def test_02_matcher_alone_does_not_infer_normal_mode(self):
        case = example()
        case["observations"] = case["observations"][:1]
        result = audit(case)
        self.assertEqual(result["normal_mode_predicate"], "unknown")
        self.assertFalse(result["normal_mode_warning_observed"])
        self.assertEqual(result["hardware_a3"], {})
        self.assertIsNone(result["ecu_reachable_observed"])

    def test_03_rx_seen_after_a3_does_not_prove_authorization(self):
        case = example()
        case["observations"][1]["outcome"] = "rx_seen"
        result = audit(case)
        self.assertEqual(result["hardware_a3"]["50"]["outcome"], "rx_seen")
        self.assertEqual(result["a3_security_access_authorized"], "unknown")
        self.assertEqual(result["expected_e3_response_bytes"], "unknown")

    def test_04_partial_matcher_and_missing_hardware_stay_unverified(self):
        case = example()
        case["observations"] = [
            {"event": "b9fb_matcher", "source": "client_log",
             "observed": 13, "matched": 12, "ignored": 1},
            {"event": "normal_mode_warning", "source": "client_ui"},
        ]
        result = audit(case)
        self.assertFalse(result["b9fb_client_matcher"]["frame_matcher_complete"])
        self.assertEqual(result["hardware_a3"], {})
        self.assertEqual(result["normal_mode_predicate"], "unknown")

    def test_05_mixed_runs_and_incorrect_client_versions_rejected(self):
        for key, value in [
            ("run_scope", "cross_log_inferred"),
            ("version", "SectorV.exe /users/private"),
            ("scenario", "private-vin-serial"),
            ("client", "VDASH"),
        ]:
            case = example()
            case[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit(case)

    def test_06_private_payload_fields_and_fake_e3_predicates_rejected(self):
        for name, payload in [
            ("vin", "YV1CZ0002A0000001"),
            ("a3_operands", "PRIVATE"),
            ("expected_reply", "E3 02"),
            ("source_path", "C:/private/sectorv.log"),
        ]:
            case = example()
            case["observations"][1][name] = payload
            with self.subTest(name=name), self.assertRaises(ValueError):
                audit(case)
        case = example()
        case["private_ini"] = "path"
        with self.assertRaises(ValueError):
            audit(case)

    def test_07_duplicate_conflicting_events_and_noninteger_counts(self):
        case = example()
        case["observations"].append(copy.deepcopy(case["observations"][1]))
        with self.assertRaises(ValueError):
            audit(case)
        case = example()
        case["observations"][0]["observed"] = 4
        with self.assertRaises(ValueError):
            audit(case)
        case = example()
        case["observations"][0]["ignored"] = True
        with self.assertRaises(ValueError):
            audit(case)
        case = example()
        case["observations"][1]["elapsed_ms"] = "5000ms"
        with self.assertRaises(ValueError):
            audit(case)

    def test_08_cli_redacted_output_new_file_only(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "private-sectorv-events.json"
            output = Path(d) / "public-gate-summary.json"
            source.write_text(json.dumps(example()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(source), "--output", str(output)])
            raw = output.read_text(encoding="utf-8")
            result = json.loads(raw)
            self.assertEqual(result["normal_mode_predicate"], "unknown")
            for banned in ("YV1CZ0002A0000001", "private-sectorv-events",
                           "E3 02", "A5 A5", "C:/private", "sectorv.log"):
                self.assertNotIn(banned, raw)
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main([str(source), "--output", str(output)])
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), result)


if __name__ == "__main__":
    unittest.main()
