"""Eight offline evidence/privilege/privacy gates for the backend JSONL auditor."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "tools" / "audit_backend_evidence.py"
spec = importlib.util.spec_from_file_location("audit_backend_evidence", MODULE)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def evt(kind, *, sid="0123456789abcdef", rid=1001, tick=1000000, channel=1,
        protocol=5, baud=500000, route="UNKNOWN", reason="none",
        outcome="unknown", **extra):
    value = {
        "format": "virtualcar-backend-v1", "session_id": sid,
        "request_id": rid, "kind": kind, "tick": tick, "freq": 1000000,
        "channel": channel, "protocol": protocol, "baud": baud,
        "route": route, "reason": reason, "outcome": outcome,
    }
    value.update(extra)
    return json.dumps(value) + "\n"


def audit(*events):
    return tool.audit(events)


class BackendEvidenceTests(unittest.TestCase):
    def test_01_delivered_is_not_ecu_identification(self):
        r = audit(evt("tx_received"), evt("route_selected", route="CEM"),
                  evt("response_generated"), evt("rx_queued"),
                  evt("rx_dequeued", tick=1025000),
                  evt("request_completed", outcome="responded", tick=1025000))
        one = r["transactions"][0]
        self.assertEqual((one["status"], one["reason"]), ("delivered", "j2534_rx_only"))
        self.assertEqual((one["channel"], one["protocol"], one["baud_bps"]), (1, "CAN", 500000))
        self.assertEqual(one["elapsed_ms"], 25)
        self.assertIsNone(one["service"])
        self.assertIsNone(one["can_id"])
        self.assertEqual(one["id_format"], "unknown")
        self.assertFalse(r["client_acceptance_verified"])

    def test_02_missing_fixture_and_unsupported_are_distinct(self):
        r = audit(evt("tx_received", rid=1),
                  evt("request_completed", rid=1, route="CEM",
                      reason="missing_profile", outcome="no_response"),
                  evt("tx_received", rid=2),
                  evt("request_completed", rid=2, route="CEM",
                      reason="unsupported_bus", outcome="no_response"),
                  evt("tx_received", rid=3),
                  evt("request_completed", rid=3, route="UNHANDLED",
                      reason="unhandled_request", outcome="no_response"))
        self.assertEqual([x["status"] for x in r["transactions"]],
                         ["no_fixture", "unsupported", "unsupported"])

    def test_03_partial_delivery_abort_and_pre_delivery_abort(self):
        r = audit(evt("tx_received", rid=1), evt("rx_queued", rid=1),
                  evt("rx_dequeued", rid=1),
                  evt("response_aborted", rid=1, reason="flow_overflow"),
                  evt("request_completed", rid=1, reason="flow_overflow",
                      outcome="aborted"),
                  evt("tx_received", rid=2), evt("rx_queued", rid=2),
                  evt("request_completed", rid=2, reason="clear_rx_buffer",
                      outcome="aborted"))
        self.assertEqual([(t["status"], t["reason"]) for t in r["transactions"]],
                         [("partial_rx", "rx_delivery_interrupted"),
                          ("unverified", "aborted_or_dropped_before_rx")])

    def test_04_sessions_and_channels_are_not_mixed_or_leaked(self):
        second_sid = "fedcba9876543210"
        r = audit(evt("tx_received", rid=7, channel=1),
                  evt("tx_received", rid=7, channel=2, sid=second_sid),
                  evt("rx_queued", rid=7, channel=2, sid=second_sid),
                  evt("rx_dequeued", rid=7, channel=2, sid=second_sid),
                  evt("request_completed", rid=7, channel=2, sid=second_sid,
                      outcome="responded"),
                  evt("request_completed", rid=7, channel=1, outcome="no_response",
                      reason="no_response"))
        self.assertEqual(r["summary"]["sessions"], 2)
        self.assertEqual([x["status"] for x in r["transactions"]],
                         ["unverified", "delivered"])
        s = json.dumps(r)
        self.assertNotIn(second_sid, s)
        self.assertNotIn("0123456789abcdef", s)
        self.assertNotIn('"request_id"', s)

    def test_05_double_terminal_and_conflicting_route_cannot_succeed(self):
        r = audit(evt("tx_received", rid=1),
                  evt("route_selected", rid=1, route="CEM"),
                  evt("route_selected", rid=1, route="ECM"),
                  evt("rx_dequeued", rid=1),
                  evt("request_completed", rid=1, outcome="responded"),
                  evt("tx_received", rid=2), evt("rx_dequeued", rid=2),
                  evt("request_completed", rid=2, outcome="responded"),
                  evt("request_completed", rid=2, outcome="responded"))
        self.assertEqual([t["reason"] for t in r["transactions"]],
                         ["inconsistent_route_or_channel", "inconsistent_event_lifecycle"])

    def test_06_fail_closed_privacy_and_untrusted_extra_fields(self):
        marker = "YV1CZ0002A0000001"  # Synthetic, never a vehicle source.
        r = audit(evt("tx_received", private_vin=marker,
                      raw_can=marker, source_path="C:/private/secret"),
                  evt("request_completed", outcome="responded",
                      private_vin=marker),
                  '{"format":"virtualcar-backend-v1","kind":"wrong","VIN":"' + marker + '"}\n',
                  evt("tx_received", reason=marker),
                  evt("tx_received", route=[marker]),
                  marker * 300 + "\n")
        data = json.dumps(r)
        self.assertNotIn(marker, data)
        self.assertNotIn("secret", data)
        self.assertEqual(r["summary"]["invalid_lines"], 4)
        self.assertEqual(r["transactions"][0]["status"], "unverified")

    def test_07_no_timeout_inference_and_explicit_timeout(self):
        r = audit(evt("tx_received", rid=1),
                  evt("tx_received", rid=2),
                  evt("request_completed", rid=2, reason="device_close",
                      outcome="aborted"),
                  evt("tx_received", rid=3),
                  evt("request_completed", rid=3, reason="read_timeout",
                      outcome="no_response"),
                  evt("tx_received", rid=4), evt("rx_dequeued", rid=4))
        self.assertEqual([x["status"] for x in r["transactions"]],
                         ["unverified", "unverified", "timeout", "unverified"])

    def test_08_cli_creates_only_new_report_without_modifying_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "private.jsonl"
            dest = Path(directory) / "report.json"
            original = evt("tx_received") + evt("rx_dequeued") + evt(
                "request_completed", outcome="responded")
            source.write_text(original, encoding="utf-8")
            self.assertEqual(tool.main([str(source), "--output", str(dest)]), 0)
            self.assertEqual(source.read_text(encoding="utf-8"), original)
            self.assertEqual(json.loads(dest.read_text(encoding="utf-8"))[
                "transactions"][0]["status"], "delivered")
            self.assertEqual(tool.main([str(source), "--output", str(dest)]), 2)
            self.assertEqual(tool.main([str(source), "--output", str(source)]), 2)
            self.assertEqual(source.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
