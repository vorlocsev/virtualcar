"""B3A318: request enumeration != ECU response/identity acceptance."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'tools' / 'audit_b3a318_p2_ecu_requests.py'
spec = importlib.util.spec_from_file_location('b3a318', SRC)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
P1 = '[PID=DEADBEEF SectorV.exe] '
P2 = '[PID=01020304 SectorV.exe] '


def req(pid, target, op=0xF0, baud=125000, flags=0x100):
    raw = b''.join(x.to_bytes(4, 'big') for x in (target, op, baud, flags))
    return pid + audit.REQUEST + raw.hex(' ').upper()


def missing(pid, target, op=0xF0):
    return pid + f'P2 D2 command: no recorded ECU fixture for target CB {target:02X} B9 {op:02X}'


class B3A318Tests(unittest.TestCase):
    def test_01_six_ecu_nodes_are_requests_not_identities(self):
        nodes = (0x64, 0x67, 0x71, 0x72, 0x75, 0x7B)
        report = audit.analyze([req(P1, t) for t in nodes] +
                               [missing(P1, t) for t in nodes])
        g = report['groups'][0]
        self.assertEqual(g['b9f0_request_count'], 6)
        self.assertEqual(g['b9f0_target_count'], 6)
        self.assertEqual(g['b9f0_no_recorded_fixture_count'], 6)
        self.assertFalse(g['ecu_identity_accepted_verified'])

    def test_02_native_process_groups_not_authenticated_sessions(self):
        r = audit.analyze([req(P1, 0x64), req(P2, 0x72)])
        self.assertEqual(r['group_count'], 2)
        self.assertFalse(r['cross_process_correlation_verified'])
        self.assertFalse(r['groups'][0]['group_is_verified_session'])

    def test_03_duplicate_requests_are_counted_not_collapsed(self):
        r = audit.analyze([req(P1, 0x50), req(P1, 0x50)])
        self.assertEqual(r['groups'][0]['b9f0_request_count'], 2)
        self.assertEqual(r['groups'][0]['b9f0_target_count'], 1)

    def test_04_b9fb_and_staged_do_not_count_as_b9f0(self):
        r = audit.analyze([req(P1, 0x50, 0xFB), P1 + audit.STAGED_B9FB])
        self.assertEqual(r['groups'][0]['b9f0_request_count'], 0)
        self.assertEqual(r['groups'][0]['b9fb_request_count'], 1)
        self.assertEqual(r['groups'][0]['b9fb_50_staged_count'], 1)

    def test_05_a3_failure_is_separate_evidence(self):
        r = audit.analyze([req(P1, 0x40, 0xFB), P1 + audit.A3_NO_REPLY])
        self.assertEqual(r['groups'][0]['a3_a6_no_verified_response_count'], 1)
        self.assertFalse(r['oem_cem_response_provenance_verified'])

    def test_06_bad_prefix_ignored(self):
        self.assertEqual(audit.analyze(['[PID=FOO SectorV.exe] ' + audit.A3_NO_REPLY])['group_count'], 0)

    def test_07_corrupt_payload_is_not_counted(self):
        r = audit.analyze([P1 + audit.REQUEST + '00 0G 03'])
        self.assertEqual(r['malformed_request_metadata'], 1)
        self.assertEqual(r['groups'][0]['b9f0_request_count'], 0)

    def test_08_invalid_opcode_and_baud(self):
        r = audit.analyze([req(P1, 0x50, 0xAB), req(P1, 0x50, 0xF0, 0)])
        self.assertEqual(r['malformed_request_metadata'], 2)

    def test_09_bounded_rows(self):
        with self.assertRaisesRegex(ValueError, 'bounded_native_rows_exceeded'):
            audit.analyze(('ignored' for _ in range(audit.MAX_ROWS + 1)))

    def test_10_oversized_rows_are_ignored(self):
        r = audit.analyze(['x' * (audit.MAX_LINE + 1)])
        self.assertEqual(r['oversized_rows_ignored'], 1)

    def test_11_never_export_raw_vin_pid_or_flags(self):
        secret = 'PRIVATE_VIN_EXAMPLE_NEVER_EXPORT'
        r = audit.analyze([req(P1, 0x50, flags=0xBADC0DE), P1 + 'Active INI: ' + secret])
        exported = json.dumps(r)
        for private in (secret, 'DEADBEEF', 'BADC0DE', 'SectorV.exe'):
            self.assertNotIn(private, exported)

    def test_12_target_and_baud_remain_separate(self):
        r = audit.analyze([req(P1, 0x50, baud=500000), req(P1, 0x40, baud=125000)])
        data = r['groups'][0]['b9f0_target_baud']
        self.assertEqual(len(data), 2)
        self.assertEqual({(x['node'], x['baud_bps']) for x in data},
                         {('0x50', 500000), ('0x40', 125000)})

    def test_13_no_made_up_success_from_missing_fixture(self):
        r = audit.analyze([req(P1, 0x43), missing(P1, 0x43)])
        self.assertFalse(r['sectorv_ecu_identification_accepted'])
        self.assertFalse(r['groups'][0]['b9f0_response_delivered_verified'])

    def test_14_cli_sanitizes_input_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'PRIVATE_LOCAL_PATH.log'
            log.write_text(req(P1, 0x50), encoding='utf-8')
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(audit.main(['--native', str(log)]), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report['group_count'], 1)
            self.assertNotIn(str(log), output.getvalue())

    def test_16_cli_scans_past_150k_unrelated_rows_without_truncation(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'native-big-unrelated-private.log'
            with log.open('w', encoding='utf-8') as out:
                out.write('unrelated native log line\n' * (audit.MAX_ROWS + 3))
                out.write(req(P1, 0x50, op=0xFB, baud=500000) + '\n')
                out.write(req(P1, 0x64) + '\n')
                out.write(missing(P1, 0x64) + '\n')
            capture = io.StringIO()
            with redirect_stdout(capture):
                self.assertEqual(audit.main(['--native', str(log)]), 0)
            result = json.loads(capture.getvalue())
            self.assertTrue(result['complete_source_scan'])
            self.assertEqual(result['source_scan_counts']['source_rows_scanned'],
                             audit.MAX_ROWS + 6)
            self.assertEqual(result['source_scan_counts']['relevant_d2_rows_seen'], 3)
            self.assertEqual(result['groups'][0]['b9f0_request_count'], 1)
            self.assertEqual(result['groups'][0]['b9fb_request_count'], 1)
            self.assertNotIn(str(log), capture.getvalue())

    def test_17_cli_refuses_excessive_source_without_partial_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'source-too-large-private.log'
            log.write_text(req(P1, 0x50), encoding='utf-8')
            with patch.object(audit, 'MAX_SOURCE_BYTES', 1):
                with self.assertRaises(SystemExit) as failed:
                    audit.main(['--native', str(log)])
            self.assertEqual(failed.exception.code, 2)

    def test_18_long_relevant_event_is_counted_not_parsed(self):
        scan = {'source_rows_scanned': 0, 'relevant_d2_rows_seen': 0}
        lines = [req(P1, 0x50) + ' X' * 250, req(P1, 0x64)]
        result = audit.analyze(audit._relevant_rows(lines, scan))
        self.assertEqual(result['oversized_rows_ignored'], 1)
        self.assertEqual(result['groups'][0]['b9f0_request_count'], 1)
        self.assertEqual(scan['source_rows_scanned'], 2)


    def test_15_public_catalog_keeps_d2_ggd_and_modules_distinct(self):
        registry = ROOT / 'tools' / 'data' / 'b3a318_xc90_v8_cem_candidates.json'
        entries = json.loads(registry.read_text(encoding='utf-8'))['candidates']
        self.assertEqual(len(entries), 3)
        self.assertEqual({(v['module'], v['protocol']) for v in entries},
                         {('CEM', 'D2 v7'), ('CEM', 'GGD v2'), ('ECM', 'GGD v2')})
        self.assertTrue(all(v['confidence'] == 'catalog_candidate_not_live_vehicle' for v in entries))
        self.assertTrue(all(not v['source_proves_live_response'] for v in entries))


if __name__ == '__main__':
    unittest.main()
