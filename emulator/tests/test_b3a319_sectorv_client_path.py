"""Synthetic regressions for B3A319: no false Hardware or alternate-route PASS."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tools' / 'audit_b3a319_sectorv_client_path.py'
spec = importlib.util.spec_from_file_location('b3a319', SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
PRE = '2026-11-19 03:27:02.084 +03:00 [client] '


def lines(*x):
    return [PRE + a for a in x]


class PathTests(unittest.TestCase):
    def test_01_unique_marker_attributes_client_method(self):
        r = audit.classify(lines('P2 hardware CAN 500k comm=0x50 protocol=0x5 flags=0x100 connect=0'))
        self.assertTrue(r['source_binding']['client_path_observed'])
        self.assertEqual(r['source_binding']['il_token'], '0x060012FA')

    def test_02_absence_never_proves_alternate_path(self):
        r = audit.classify(lines('P2 hardware-session RX v3 comm=0x50: result=no-reply, observed=0, ignored=0, matched=0, elapsedMs=5003.'))
        self.assertEqual(r['source_binding']['confidence'], 'not_attributable')
        self.assertEqual(r['source_binding']['m30855f_path_executed'], 'unknown')

    def test_03_fallback_iso_failure_and_raw_success_are_distinct(self):
        r = audit.classify(lines('P2 hardware CAN 500k comm=0x50 protocol=0x8004 flags=0x100 connect=25', 'P2 hardware CAN 500k comm=0x50 protocol=0x5 flags=0x100 connect=0'))
        values = {(v['protocol'], v['result']) for v in r['route_connect_counts']}
        self.assertEqual(values, {('0x8004','connect_25'),('0x5','connect_0')})
        self.assertFalse(r['hardware_session_accepted'])

    def test_04_route_40_and_50_separate(self):
        r = audit.classify(lines('P2 hardware CAN 125k comm=0x40 protocol=0x5 flags=0x100 connect=0', 'P2 hardware CAN 500k comm=0x50 protocol=0x5 flags=0x100 connect=0'))
        self.assertEqual({x['route'] for x in r['route_connect_counts']}, {'0x40','0x50'})

    def test_05_no_reply_client_does_not_accept_hardware(self):
        r = audit.classify(lines('P2 hardware-session RX v3 comm=0x50: result=no-reply, observed=0, ignored=0, matched=0, elapsedMs=5015.'))
        self.assertFalse(r['hardware_session_accepted'])
        self.assertEqual(r['client_rx_counts'][0]['phase'], 'hardware-session')

    def test_06_vin_received_is_transport_only(self):
        r = audit.classify(lines('P2 VIN RX v3 comm=0x50: result=received, observed=13, ignored=0, matched=13, elapsedMs=147.'))
        self.assertFalse(r['oem_hardware_identity_verified'])
        self.assertEqual(r['client_rx_counts'][0]['phase'], 'VIN')

    def test_07_hardware_received_still_not_proof_oem(self):
        r = audit.classify(lines('P2 hardware-session RX v3 comm=0x50: result=received, observed=1, ignored=0, matched=1, elapsedMs=35.'))
        self.assertFalse(r['hardware_session_accepted'])
        self.assertFalse(r['ecu_identification_verified'])

    def test_08_no_route_from_agent_line(self):
        r = audit.classify(['2026-11-19 03:27:02.084 +03:00 [agent] P2 hardware CAN 500k comm=0x50 protocol=0x5 flags=0x100 connect=0'])
        self.assertFalse(r['source_binding']['client_path_observed'])

    def test_09_reject_malformed_line(self):
        r = audit.classify(lines('P2 hardware CAN 500k comm=0x50 protocol=0x5 flags=SECRET connect=0'))
        self.assertEqual(r['unmatched_hardware_connect_lines'], 1)
        self.assertFalse(r['source_binding']['client_path_observed'])

    def test_10_fallback_not_a_success(self):
        r = audit.classify(lines(audit.FALLBACK, 'P2 automatic identification failed at Hardware: TimeoutException'))
        self.assertEqual(r['fallback_50_to_40_log_count'], 1)
        self.assertEqual(r['hardware_failure_log_count'], 1)
        self.assertFalse(r['hardware_session_accepted'])

    def test_11_do_not_export_pids_vins_flags_timestamps(self):
        secret = 'PRIVATE_FAKE_KEY_ABCDEFGHI'
        r = audit.classify(lines('P2 hardware CAN 500k comm=0x50 protocol=0x5 flags=0xDEADBEEF connect=0', secret))
        output = json.dumps(r)
        for value in ('DEADBEEF', secret, '2026-11-19', '03:27:02.084'):
            self.assertNotIn(value, output)

    def test_12_bounded_rows(self):
        with self.assertRaisesRegex(ValueError, 'too_many_rows'):
            audit.classify(('ignore' for _ in range(audit.MAX_ROWS+1)))

    def test_13_oversized_rows_safely_ignored(self):
        r = audit.classify(['z'*(audit.MAX_LINE+1)])
        self.assertEqual(r['oversized_rows_ignored'],1)

    def test_14_cli_output_does_not_echo_input_path(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'private_fakedata.log'
            path.write_text(PRE+'P2 hardware CAN 500k comm=0x50 protocol=0x5 flags=0x100 connect=0',encoding='utf-8')
            out=io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(audit.main(['--client',str(path)]),0)
            self.assertTrue(json.loads(out.getvalue())['source_binding']['client_path_observed'])
            self.assertNotIn(str(path),out.getvalue())

    def test_15_cross_process_evidence_unverified(self):
        r = audit.classify(lines('P2 hardware CAN 500k comm=0x50 protocol=0x5 flags=0x100 connect=0'))
        self.assertFalse(r['native_and_client_cross_process_link_verified'])


if __name__ == '__main__':
    unittest.main()
