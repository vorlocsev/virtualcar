"""B3A142: synthetic event-correlation regression tests only."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_vida_b3a142_cem_d2_window import audit_lines, tail_lines

PREFIX = '[PID=00000001 IEXPLORE.EXE] '
OTHER = '[PID=00000002 OTHER.EXE] '
REQ_40_F0 = ('P2 D2 request target/opcode/baud/flags (BE) '
             '00 00 00 40 00 00 00 F0 00 01 E8 48 00 00 10 00')
REQ_40_FB = REQ_40_F0.replace('00 00 00 F0', '00 00 00 FB')
REQ_29_F0 = REQ_40_F0.replace('00 00 00 40', '00 00 00 29')
REQ_50_F0 = REQ_40_F0.replace('00 00 00 40', '00 00 00 50').replace('00 01 E8 48', '00 07 A1 20')
NO_FIXTURE = 'P2 D2 read command: no validated response fixture CB 40 B9 F0'
DELIVERED = ('P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE) '
             '00 00 00 01 00 00 00 01 00 00 00 01 00 01 00 00 00 02 00 00')


def run(*events):
    return audit_lines(events)


def row(summary, name='CEM_40/B9F0/125k'):
    return summary['cem_routes'][name]


class AuditB3A142Tests(unittest.TestCase):
    def test_01_cem_no_fixture(self):
        s = run(PREFIX+REQ_40_F0, PREFIX+NO_FIXTURE)
        self.assertEqual(row(s)['request_count'], 1)
        self.assertEqual(row(s)['categorized_outcomes'], {'missing_validated_fixture': 1})

    def test_02_b9fb_is_separate(self):
        s = run(PREFIX+REQ_40_FB, PREFIX+NO_FIXTURE)
        self.assertEqual(row(s, 'CEM_40/B9FB/125k')['request_count'], 1)
        self.assertEqual(row(s)['request_count'], 0)

    def test_03_other_target_closes_cem_window(self):
        s = run(PREFIX+REQ_40_F0, PREFIX+REQ_29_F0, PREFIX+DELIVERED)
        self.assertEqual(s['other_target_d2_request_count'], 1)
        self.assertEqual(row(s)['categorized_outcomes'], {'no_categorized_outcome': 1})
        self.assertNotIn('d2_delivered', row(s)['bounded_same_logger_prefix_markers'])

    def test_04_other_process_cannot_supply_outcome(self):
        s = run(PREFIX+REQ_40_F0, OTHER+NO_FIXTURE)
        self.assertEqual(row(s)['categorized_outcomes'], {'no_categorized_outcome': 1})

    def test_05_staged_is_not_delivered(self):
        s = run(PREFIX+REQ_40_F0, PREFIX+'P2 D2 read-only recorded frames staged')
        self.assertEqual(row(s)['categorized_outcomes'],
                         {'staged_not_delivered_in_bounded_span': 1})

    def test_06_staged_and_native_delivered_not_vida(self):
        s = run(PREFIX+REQ_40_F0, PREFIX+'P2 D2 read-only recorded frames staged', PREFIX+DELIVERED)
        self.assertEqual(row(s)['categorized_outcomes'],
                         {'native_d2_delivered_not_vida_accepted': 1})
        self.assertEqual(s['actual_vida_network_or_ecu_identification'], 'NOT_PROVEN')

    def test_07_generic_rx_is_not_d2(self):
        s = run(PREFIX+REQ_40_F0, PREFIX+'PassThruReadMsgs -> delivered 00 00 00 00')
        self.assertEqual(row(s)['categorized_outcomes'], {'no_categorized_outcome': 1})
        self.assertEqual(row(s)['bounded_same_logger_prefix_markers']['generic_rx_delivered'], 1)

    def test_08_clear_rx_does_not_prove_cause(self):
        s = run(PREFIX+REQ_40_F0, PREFIX+'P2 D2 read-only recorded frames staged',
                PREFIX+'J2534 CLEAR_RX_BUFFER: queued D2/raw ISO-TP and staged CF dropped')
        self.assertEqual(row(s)['categorized_outcomes'],
                         {'staged_then_clear_rx_seen_not_causal_proof': 1})

    def test_09_bus_reject_precedence(self):
        s = run(PREFIX+REQ_40_F0,
                PREFIX+'P2 D2 strict route rejected (no fixture emitted) CB 40 B9 F0',
                PREFIX+NO_FIXTURE)
        self.assertEqual(row(s)['categorized_outcomes'], {'strict_bus_rejected': 1})

    def test_10_malformed_marker_sanitized(self):
        s = run(PREFIX+REQ_40_F0, PREFIX+REQ_40_F0[:-3])
        self.assertEqual(s['malformed_request_metadata'], 1)
        self.assertEqual(row(s)['request_count'], 1)

    def test_11_data_privacy(self):
        s = run(PREFIX+REQ_40_F0, PREFIX+NO_FIXTURE+' SECRET_VIN_12345 PRIVATE_PATH')
        j = json.dumps(s)
        for secret in ('00000001', 'IEXPLORE.EXE', 'SECRET_VIN_12345', 'PRIVATE_PATH',
                       'CB 40 B9 F0', '00 00 00 F0'):
            self.assertNotIn(secret, j)
        self.assertFalse(s['has_private_paths_vin_pid_can_frames_or_response_ids'])

    def test_12_50_baud(self):
        s = run(PREFIX+REQ_50_F0)
        self.assertEqual(row(s, 'CEM_50/B9F0/500k')['request_count'], 1)

    def test_13_timeout_is_only_sample(self):
        s = run(PREFIX+REQ_40_F0,
                PREFIX+'PassThruReadMsgs timeout: channel / wait-ms / consecutive-count (BE)')
        self.assertEqual(row(s)['bounded_same_logger_prefix_markers']['timeout_sample'], 1)
        self.assertFalse(s['client_return_status_verified'])

    def test_14_truncated_window(self):
        s = audit_lines([PREFIX+REQ_40_F0], tail_truncated=True)
        self.assertTrue(s['source_tail_truncated'])
        self.assertEqual(row(s)['end_of_tail_or_span_censored_requests'], 1)

    def test_15_tail_drops_partial_first_line(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'private.log'
            path.write_bytes(b'partial bytes without newline\n' + (PREFIX+REQ_40_F0+'\n').encode())
            lines, truncated = tail_lines(path, len((PREFIX+REQ_40_F0+'\n').encode())+12)
            self.assertTrue(truncated)
            self.assertEqual(len(lines), 1)
            self.assertTrue(lines[0].startswith(PREFIX))

    def test_16_cli_json_and_no_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'private.log'
            data = (PREFIX+REQ_40_F0+'\n'+PREFIX+NO_FIXTURE+'\n').encode()
            path.write_bytes(data)
            tool = Path(__file__).resolve().parents[1] / 'tools' / 'audit_vida_b3a142_cem_d2_window.py'
            p = subprocess.run([sys.executable, str(tool), '--native-log', str(path),
                                '--tail-bytes', '1024'], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(json.loads(p.stdout)['cem_routes']['CEM_40/B9F0/125k']['request_count'], 1)


if __name__ == '__main__':
    unittest.main()
