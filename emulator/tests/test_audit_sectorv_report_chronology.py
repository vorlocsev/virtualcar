"""Eight synthetic tests of old SectorV report chronology and non-attribution."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sectorv_report_chronology", ROOT / "tools" / "audit_sectorv_report_chronology.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def session():
    return {"route": "0x50", "frames_delivered": 13,
            "expected_frames": 13, "status": "ordered_frames_complete"}


def event(number, name, window):
    return {"order": number, "event": name, "connection_window": window}


def make_report(*, source_version="0.3.6.7-dev10", timeline=None):
    if timeline is None:
        # Actual dev10 high-level order as recorded in the historic
        # redacted report; values here are synthetic test data.
        timeline = [
            event(1, "run_start", 0),
            event(2, "can_connect_500k", 1),
            event(3, "a3_request", 1),
            event(4, "a3_unmatched", 1),
            event(5, "can_connect_125k", 2),
            event(6, "b9fb_request", 2),
            event(7, "b9fb_ordered_complete", 2),
            event(8, "disconnect", 2),
            event(9, "close", 2),
        ]
    run = {
        "run_index": 188, "a3_requests": 1, "a3_requests_unmatched": 1,
        "b9fb_requests": 1, "a3_after_b9fb_same_process_run": 0,
        "sessions": [session()],
        "timeline": timeline,
    }
    return {
        "analyzer_version": source_version, "process_filter": "SectorV.exe",
        "route": "0x50", "expected_frames": 13, "source_runs": 31,
        "runs": [run], "client_vin_accepted": "unknown",
        "ecu_identified": "unknown", "security_access_succeeded": "unknown",
    }


class HistoricalSectorvChronologyTests(unittest.TestCase):
    def test_01_historical_dev10_a3_before_b9fb_and_different_window(self):
        report = tool.audit(make_report())
        self.assertEqual(report["chronology_counts"],
                         {"a3_before_completed_b9fb": 1})
        self.assertEqual(report["b9fb_complete_sessions"], 1)
        self.assertEqual(report["observations"][0]["a3_requests_reported"], 1)
        self.assertFalse(report["tx_channel_binding_verified"])
        self.assertFalse(report["native_clock_join_verified"])
        self.assertFalse(report["b9fb_semantic_acceptance_verified"])

    def test_02_old_dev8_aggregate_without_timeline_is_unknown(self):
        data = make_report(source_version="0.3.6.7-dev8-standalone")
        data.pop("runs")
        data["sessions"] = [session()] * 23 + [
            {"route": "0x50", "frames_delivered": 0,
             "expected_frames": 13, "status": "incomplete_disconnect"}] * 8
        data["a3_requests"] = 4
        data["a3_requests_unmatched"] = 4
        report = tool.audit(data)
        self.assertEqual(report["b9fb_complete_sessions"], 23)
        self.assertEqual(report["b9fb_incomplete_disconnect_sessions"], 8)
        self.assertEqual(report["chronology_counts"], {"timeline_unavailable": 1})
        self.assertFalse(report["tx_channel_binding_verified"])

    def test_03_later_a3_in_same_window_is_order_only_not_channel_binding(self):
        data = make_report(timeline=[
            event(1, "run_start", 0), event(2, "can_connect_500k", 1),
            event(3, "b9fb_request", 1), event(4, "b9fb_ordered_complete", 1),
            event(5, "a3_request", 1), event(6, "a3_unmatched", 1),
        ])
        data["runs"][0]["a3_after_b9fb_same_process_run"] = 1
        report = tool.audit(data)
        self.assertEqual(report["chronology_counts"],
                         {"a3_after_b9fb_order_in_same_connection_window": 1})
        self.assertFalse(report["observations"][0]["a3_after_completed_b9fb_same_channel_verified"])

    def test_04_after_b9fb_but_different_window_does_not_link_channels(self):
        data = make_report(timeline=[
            event(1, "run_start", 0), event(2, "can_connect_125k", 1),
            event(3, "b9fb_request", 1), event(4, "b9fb_ordered_complete", 1),
            event(5, "can_connect_500k", 2), event(6, "a3_request", 2),
            event(7, "a3_unmatched", 2),
        ])
        report = tool.audit(data)
        self.assertEqual(report["chronology_counts"],
                         {"a3_after_b9fb_in_different_connection_window": 1})
        self.assertFalse(report["native_clock_join_verified"])

    def test_05_reported_after_count_conflict_must_fail(self):
        data = make_report(timeline=[
            event(1, "run_start", 0), event(2, "b9fb_request", 1),
            event(3, "b9fb_ordered_complete", 1),
            event(4, "a3_request", 1), event(5, "a3_unmatched", 1),
        ])
        # Reports zero after but the timeline shows a same-window A3 later.
        with self.assertRaises(ValueError):
            tool.audit(data)

    def test_06_missing_final_frame_or_conflicting_counts_fail(self):
        baseline = make_report()
        for bad in ("partial_delivery", "missing_event", "duplicate_order", "count_conflict"):
            data = json.loads(json.dumps(baseline))
            run = data["runs"][0]
            if bad == "partial_delivery":
                run["sessions"][0]["frames_delivered"] = 12
            if bad == "missing_event":
                run["timeline"].pop(6)
            if bad == "duplicate_order":
                run["timeline"][4]["order"] = 4
            if bad == "count_conflict":
                run["a3_requests"] = 2
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                tool.audit(data)

    def test_07_private_fields_not_echoed_and_unauthorized_claim_refused(self):
        data = make_report()
        private = "PRIVATE_VIN_OR_TOKEN_DO_NOT_EMIT"
        data["profile_path"] = private
        data["runs"][0]["source_private"] = private
        data["runs"][0]["timeline"][0]["raw_can_payload"] = private
        report = tool.audit(data)
        self.assertNotIn(private, json.dumps(report))
        self.assertNotIn("run_index", json.dumps(report))
        self.assertNotIn("CAN", report["evidence_scope"])
        data["client_vin_accepted"] = True
        with self.assertRaises(ValueError):
            tool.audit(data)

    def test_08_cli_exclusive_output_failure_and_source_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            source = path / "old-private-summary.json"
            out = path / "safe-audit.json"
            raw = json.dumps(make_report())
            source.write_text(raw, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main([str(source), "--output", str(out)]), 0)
            saved = out.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main([str(source), "--output", str(out)]), 2)
                self.assertEqual(tool.main([str(source), "--output", str(source)]), 2)
            self.assertEqual(out.read_bytes(), saved)
            self.assertEqual(source.read_text(encoding="utf-8"), raw)
            bad = path / "bad-output.json"
            source.write_text("{broken", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main([str(source), "--output", str(bad)]), 2)
            self.assertFalse(bad.exists())


if __name__ == "__main__":
    unittest.main()
