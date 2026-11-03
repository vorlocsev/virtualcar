"""Eight synthetic failure-injection tests of native B9FB -> A3 evidence gate."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_audit_backend_evidence import evt, tool as auditor

FILE = Path(__file__).resolve().parents[1] / "tools" / "verify_native_b9fb_a3.py"
spec = importlib.util.spec_from_file_location("verify_native_b9fb_a3", FILE)
tool = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"audit_backend_evidence": auditor}):
    spec.loader.exec_module(tool)

ROWS = (
    (1, 500000, "D2_50_B9FB", "none", "responded", 13),
    (1, 500000, "D2_50_A3", "unimplemented_probe", "no_response", 0),
    (2, 125000, "D2_40_A3", "unimplemented_probe", "no_response", 0),
    (1, 500000, "D2_40_A3", "unsupported_bus", "no_response", 0),
    (2, 125000, "D2_40_B9FB", "missing_profile", "no_response", 0),
)


def synthetic_events():
    result = []
    for i, (channel, baud, probe, reason, outcome, count) in enumerate(ROWS, 1):
        t = 1_000_000 + i * 100_000
        args = dict(rid=i, channel=channel, baud=baud)
        result.append(evt("tx_received", tick=t, **args))
        result.append(evt("probe_classified", probe=probe, tick=t+100, **args))
        result.append(evt("route_selected", route="CEM", tick=t+150, **args))
        if count:
            result.append(evt("response_generated", route="CEM", tick=t+160, **args))
        for frame in range(count):
            result.append(evt("filter_pass", tick=t+1000+frame*1000, **args))
            result.append(evt("rx_queued", tick=t+1100+frame*1000, **args))
            result.append(evt("rx_dequeued", tick=t+1200+frame*1000, **args))
        result.append(evt("request_completed", route="CEM", reason=reason,
                          outcome=outcome, tick=t+2000+count*1000, **args))
    return result


class NativeB9FBA3EvidenceTests(unittest.TestCase):
    def test_01_valid_single_run_reports_delivery_without_client_acceptance(self):
        report = tool.verify(synthetic_events())
        self.assertTrue(report["native_synthetic_b9fb_a3_verified"])
        self.assertEqual(report["summary"]["requests"], 5)
        self.assertEqual(report["transactions"][0]["rx_dequeued"], 13)
        self.assertFalse(report["client_acceptance_verified"])
        self.assertFalse(report["identity_verified"])
        self.assertFalse(report["a3_positive_reply_verified"])
        self.assertFalse(report["xc90_v8_my2009_verified"])

    def test_02_partial_b9fb_is_not_success(self):
        original = synthetic_events()
        rows = [json.loads(x) for x in original]
        idx = next(i for i, x in enumerate(rows) if x["kind"] == "rx_dequeued"
                   and x["request_id"] == 1)
        rows.pop(idx)
        with self.assertRaises(ValueError):
            tool.verify(json.dumps(x) for x in rows)

    def test_03_injected_positive_a3_rx_is_forbidden(self):
        raw = synthetic_events()
        events = [json.loads(x) for x in raw]
        idx = next(i for i, x in enumerate(events) if
                   x["request_id"] == 2 and x["kind"] == "request_completed")
        extras = [json.loads(evt(kind, rid=2, route="CEM", tick=1_204_000))
                  for kind in ("filter_pass", "rx_queued", "rx_dequeued")]
        with self.assertRaises(ValueError):
            tool.verify(json.dumps(x) for x in events[:idx] + extras + events[idx:])

    def test_04_wrong_bus_and_unimplemented_reasons_not_interchangeable(self):
        rows = [json.loads(x) for x in synthetic_events()]
        for target in (2, 4):
            altered = [dict(x) for x in rows]
            for e in altered:
                if e["request_id"] == target and e["kind"] == "request_completed":
                    e["reason"] = ("unsupported_bus" if target == 2
                                   else "unimplemented_probe")
            with self.subTest(target=target), self.assertRaises(ValueError):
                tool.verify(json.dumps(x) for x in altered)

    def test_05_wrong_channel_or_wrong_protocol_refused(self):
        rows = [json.loads(x) for x in synthetic_events()]
        for change in ({"channel": 9}, {"protocol": 6}, {"baud": 125000}):
            altered = [dict(x) for x in rows]
            for e in altered:
                if e["request_id"] == 1 and e["kind"] == "probe_classified":
                    e.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                tool.verify(json.dumps(x) for x in altered)

    def test_06_invalid_duplicate_or_missing_terminal_refused(self):
        values = synthetic_events()
        for bad in (values + ["not JSON"],
                    values + [values[-1]],
                    values[:-1]):
            with self.subTest(length=len(bad)), self.assertRaises(ValueError):
                tool.verify(bad)

    def test_07_private_untrusted_fields_cannot_enter_audit(self):
        rows = [json.loads(x) for x in synthetic_events()]
        secret = "SYNTHETIC_PRIVATE_VIN_AND_LOCAL_PATH_SENTINEL"
        rows[0]["payload"] = secret
        rows[0]["source_path"] = secret
        report = tool.verify(json.dumps(x) for x in rows)
        self.assertNotIn(secret, json.dumps(report))
        self.assertFalse(report["contains_payload_data"])

    def test_08_cli_exclusive_output_rejects_bad_input(self):
        with tempfile.TemporaryDirectory() as d:
            source, out = Path(d)/"source.jsonl", Path(d)/"result.json"
            original = "".join(synthetic_events())
            source.write_text(original, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main([str(source), "--output", str(out)]), 0)
            saved = out.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main([str(source), "--output", str(out)]), 2)
                self.assertEqual(tool.main([str(source), "--output", str(source)]), 2)
            self.assertEqual(saved, out.read_bytes())
            self.assertEqual(original, source.read_text(encoding="utf-8"))
            source.write_text("invalid", encoding="utf-8")
            next_out = Path(d)/"unwritten.json"
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main([str(source), "--output", str(next_out)]), 2)
            self.assertFalse(next_out.exists())


if __name__ == "__main__":
    unittest.main()
