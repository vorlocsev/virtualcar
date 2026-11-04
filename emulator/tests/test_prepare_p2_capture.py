"""Eight synthetic local-capture preparation and non-disclosure regressions."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from test_audit_d2_followup_window import A3, D2FB, marker, response, tx

spec = importlib.util.spec_from_file_location(
    "prepare_p2_capture", ROOT / "tools" / "prepare_p2_capture.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

A3_40 = bytes.fromhex("CF 40 A3 02 03 A5 A5 00")


def complete(*, close=True):
    lines = tx(D2FB) + response() + tx(A3, at=1_132_000)
    if close:
        lines.append(marker("PassThruClose"))
    return "\n".join(lines)


class P2CapturePreparationTests(unittest.TestCase):
    def test_01_complete_synthetic_native_capture_reports_closed_boundary(self):
        reports = tool.prepare(complete())
        self.assertEqual(set(reports), set(tool.OUTPUT_FILES))
        summary = reports["capture-summary.json"]
        self.assertTrue(summary["all_native_epochs_closed"])
        self.assertTrue(summary["native_tx_rx_context_complete"])
        self.assertEqual(summary["b9fb_transport_completions_observed"], 1)
        self.assertEqual(summary["a3_requests_observed"], 1)
        self.assertFalse(summary["safe_to_infer_complete_client_session"])
        self.assertFalse(summary["last_b9fb_to_first_a3_client_acceptance_verified"])

    def test_02_truncated_log_is_observed_not_validated_as_closed(self):
        reports = tool.prepare(complete(close=False))
        self.assertFalse(reports["capture-summary.json"]["all_native_epochs_closed"])
        self.assertEqual(reports["channel-chronology.json"]["epochs"][0]["boundary"],
                         "end_of_log")
        self.assertFalse(reports["capture-summary.json"]["safe_to_infer_complete_client_session"])

    def test_03_a3_before_b9fb_not_turned_into_post_b9fb(self):
        source = "\n".join(tx(A3, at=900_000)
                           + tx(D2FB, at=1_000_000)
                           + response() + [marker("PassThruClose")])
        reports = tool.prepare(source)
        self.assertEqual(reports["capture-summary.json"]["a3_requests_observed"], 1)
        self.assertEqual(reports["capture-summary.json"]["b9fb_transport_completions_observed"], 1)
        epoch = reports["channel-chronology.json"]["epochs"][0]
        self.assertEqual(epoch["outcome"], "a3_before_b9fb_request")
        self.assertEqual(epoch["first_completed_b9fb_to_later_a3"]["status"],
                         "no_later_a3_observed")

    def test_04_unanswered_or_partial_b9fb_still_gives_useful_report(self):
        source = "\n".join(tx(D2FB)
                           + response(include_final=False)
                           + [marker("PassThruClose")])
        data = tool.prepare(source)
        s = data["capture-summary.json"]
        self.assertEqual(s["b9fb_transport_completions_observed"], 0)
        self.assertEqual(s["b9fb_requests_observed"], 1)
        self.assertEqual(data["channel-chronology.json"]["epochs"][0]
                         ["b9fb_incomplete"], 1)
        self.assertFalse(s["same_run_with_sectorv_client_verified"])

    def test_05_different_pid_kept_in_separate_source_epochs(self):
        source = "\n".join(tx(D2FB) + response()
                           + [marker("PassThruClose")]
                           + tx(A3_40, pid="FEEDBEEF", channel=2, baud=125000,
                                at=1_200_000)
                           + [marker("PassThruClose", pid="FEEDBEEF")])
        reports = tool.prepare(source)
        s = reports["capture-summary.json"]
        self.assertEqual(s["native_epochs"], 2)
        self.assertTrue(s["all_native_epochs_closed"])
        self.assertEqual(s["a3_requests_observed"], 1)
        self.assertEqual(s["b9fb_transport_completions_observed"], 1)
        self.assertNotIn("FEEDBEEF", json.dumps(reports))

    def test_06_bad_tx_context_is_reported_as_incomplete(self):
        bad = (tx(D2FB) + response()
               + [marker("TX (app request) NOT_VALID_CAN"),
                  marker("PassThruClose")])
        reports = tool.prepare("\n".join(bad))
        self.assertFalse(reports["capture-summary.json"]["native_tx_rx_context_complete"])
        self.assertEqual(reports["capture-summary.json"]["native_chronology_parse_errors"]
                         ["unattributed_or_bad_tx"], 1)

    def test_07_private_identifiers_not_copied_even_with_sectorv_label(self):
        secret = "PRIVATE_VIN_SERIAL_AND_ABSOLUTE_PATH_NEVER_EXPORT"
        raw = complete().replace("PRIVATE_CLIENT", "SectorV.exe")
        data = tool.prepare(raw + "\n" + secret)
        output = json.dumps(data)
        self.assertNotIn(secret, output)
        self.assertNotIn("ABCDEF12", output)
        self.assertNotIn("SectorV.exe", output)
        self.assertNotIn("CF 50 A3 02", output)
        self.assertTrue(data["capture-summary.json"]
                        ["sectorv_process_label_observed_unverified"])
        self.assertFalse(data["capture-summary.json"]["a3_security_access_verified"])

    def test_08_cli_exclusive_directory_and_source_preservation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source, target = root/"PRIVATE-native.log", root/"safe-json"
            raw = complete()
            source.write_text(raw, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main([str(source), "--output-dir", str(target)]), 0)
            self.assertEqual(set(p.name for p in target.iterdir()),
                             set(tool.OUTPUT_FILES))
            data = json.loads((target/"capture-summary.json").read_text(encoding="utf-8"))
            self.assertTrue(data["all_native_epochs_closed"])
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main([str(source), "--output-dir", str(target)]), 2)
                self.assertEqual(tool.main([str(source), "--output-dir", str(source)]), 2)
            self.assertEqual(source.read_text(encoding="utf-8"), raw)
            self.assertFalse(any(p.suffix == ".log" for p in target.iterdir()))
            bad = root/"no-output"
            source.write_text("invalid or empty native source", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main([str(source), "--output-dir", str(bad)]), 2)
            self.assertFalse(bad.exists())


if __name__ == "__main__":
    unittest.main()
