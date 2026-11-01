"""Failure injection for the synthetic native DLL evidence gate."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_audit_backend_evidence import evt, tool as auditor

MODULE = Path(__file__).resolve().parents[1] / 'tools' / 'verify_native_routes.py'
spec = importlib.util.spec_from_file_location('verify_native_routes', MODULE)
tool = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'audit_backend_evidence': auditor}):
    spec.loader.exec_module(tool)


def synthetic_events():
    # Expected calls of the native runner, entirely synthetic metadata.
    rows = [(5, 500000, 1, 'ECM', None, 'no_response')] * 3
    rows += [(5, 125000, 2, 'ECM', None, 'no_response')] * 3
    rows += [(6, 500000, 3, 'ECM', None, 'no_response'),
             (5, 125000, 2, 'CEM', 'D2_40_B9FB', 'missing_profile'),
             (5, 500000, 1, 'CEM', 'D2_50_B9FB', 'missing_profile'),
             (5, 250000, 4, 'CEM', 'D2_50_B9FB', 'unsupported_bus'),
             (5, 500000, 1, 'UNHANDLED', 'P3_726_F114', 'unhandled_request'),
             (6, 500000, 3, 'CEM', 'P3_726_F114', 'unimplemented_probe'),
             (6, 500000, 3, 'ECU_OTHER', None, 'no_response')]
    events = []
    for rid, (protocol, baud, channel, route, probe, reason) in enumerate(rows, 1):
        context = dict(rid=rid, protocol=protocol, baud=baud, channel=channel)
        events.append(evt('tx_received', **context))
        if probe:
            events.append(evt('probe_classified', probe=probe, **context))
        events.append(evt('route_selected', route=route, **context))
        events.append(evt('request_completed', route=route, reason=reason,
                          outcome='no_response', **context))
    return events


class NativeEvidenceGateTests(unittest.TestCase):
    def test_valid_evidence_keeps_identity_unverified(self):
        report = tool.verify(synthetic_events())
        self.assertTrue(report['native_route_regression_verified'])
        self.assertFalse(report['identity_verified'])
        self.assertFalse(report['client_acceptance_verified'])

    def test_old_route_defect_and_context_mixing_fail(self):
        for changes in ({'route': 'ECU_OTHER'}, {'channel': 2},
                        {'protocol': 6}, {'baud': 125000}):
            with self.subTest(changes=changes):
                events = synthetic_events()
                event = json.loads(events[2])
                event.update(changes)
                events[2] = json.dumps(event)
                with self.assertRaises(ValueError):
                    tool.verify(events)

    def test_missing_duplicate_and_invalid_events_fail(self):
        events = synthetic_events()
        for altered in (events[:-1], events + events[-1:], events + ['not-json']):
            with self.assertRaises(ValueError):
                tool.verify(altered)

    def test_unexpected_rx_cannot_be_reported_as_pass(self):
        events = synthetic_events()
        events.insert(2, evt('rx_queued', route='ECM', rid=1))
        events.insert(3, evt('rx_dequeued', route='ECM', rid=1))
        with self.assertRaises(ValueError):
            tool.verify(events)

    def test_injected_private_fields_never_enter_report(self):
        events = synthetic_events()
        value = json.loads(events[0])
        value['payload'] = 'SYNTHETIC_PRIVATE_SENTINEL'
        value['profile_path'] = 'SYNTHETIC_PRIVATE_SENTINEL'
        events[0] = json.dumps(value)
        self.assertNotIn('SYNTHETIC_PRIVATE_SENTINEL', json.dumps(tool.verify(events)))

    def test_cli_is_read_only_and_refuses_overwrite_or_invalid_report(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / 'synthetic.jsonl', Path(directory) / 'audit.json'
            original = ''.join(synthetic_events())
            source.write_text(original, encoding='utf-8')
            self.assertEqual(tool.main([str(source), '--output', str(output)]), 0)
            saved = output.read_bytes()
            self.assertEqual(tool.main([str(source), '--output', str(output)]), 2)
            self.assertEqual(saved, output.read_bytes())
            self.assertEqual(source.read_text(encoding='utf-8'), original)
            source.write_text('invalid', encoding='utf-8')
            bad_output = Path(directory) / 'must-not-exist.json'
            self.assertEqual(tool.main([str(source), '--output', str(bad_output)]), 2)
            self.assertFalse(bad_output.exists())


if __name__ == '__main__':
    unittest.main()
