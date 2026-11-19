"""Eight offline synthetic verification groups for B3A9 source provenance.

No original OEM VIN, ECU response, access token, or real vehicle capture.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'tools' / 'audit_vida_b3a9_provenance.py'
spec = importlib.util.spec_from_file_location('b3a9_audit', path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def hash_bytes(data):
    return hashlib.sha256(data).hexdigest().upper()


def fixture():
    source = []
    tx = bytes.fromhex('00 0F FF FE CB 50 B9 FB 00 00 00 00')
    first = bytes.fromhex('01 20 00 03 8F 50 F9 FB 57 00 30 66')
    remaining = []
    for i in range(11):
        remaining.append(bytes([1, 32, 0, 3, 8 + (i + 1) % 8]) + b'SYNTHET')
    remaining.append(bytes([1, 32, 0, 3, 0x4F]) + b'SYNTHET')
    all_msgs = [(b'Write', tx)] + [(b'Read', msg) for msg in [first] + remaining]
    for i, (direction, data) in enumerate(all_msgs):
        hh, mm, ss, millis = 2, 42, 50, 500 + i * 15
        line = (f'{hh:02d}:{mm:02d}:{ss:02d},{millis:03d} 0100 000004 '.encode()
                + b'PassThru' + direction + b'Msgs() msg[0].Data = ['
                + b', '.join((b'0x%02X' % x) for x in data) + b']\r\n')
        source.append(line)
    raw = b''.join(source)
    events = {'request': {'line': 1, 'line_sha256': hash_bytes(source[0])},
              'responses': [{'line': i + 2, 'line_sha256': hash_bytes(line)}
                            for i, line in enumerate(source[1:])]}
    manifest = {
        'schema_version': 1,
        'source': {'sha256': hash_bytes(raw), 'size_bytes': len(raw), 'raw_unchanged': True,
                   'origin': 'original_vehicle_dice', 'format': 'dice_j2534_text',
                   'transformation': 'none'},
        'vehicle': {'make': 'Volvo', 'model': 'XC90', 'platform': 'P2',
                    'model_year': 2009, 'engine': 'V8',
                    'identity_basis': 'original_vehicle_record',
                    'identity_record_sha256': 'A' * 64},
        'route': {'ecu': '50', 'service': 'B9FB', 'protocol': 'CAN', 'baud_bps': 125000},
        'events': events
    }
    return raw, manifest


class B3A9Tests(unittest.TestCase):
    def test_01_b3a8_upstream_does_not_prove_rx(self):
        source = {'status': audit.B3A8_STATUS, 'replay_approved': False,
                  'readvin': {'read_timeout_count': 27, 'positive_rx_packet_lines': 0,
                              'authentic_ecu_rx': 'NOT_PROVEN', 'requests': [
                                  {'ecu': a, 'service': b, 'verified_ecu_response': False,
                                   'replay_approved': False} for a,b in
                                  [('726','22F114'),('40','B9FB'),('50','B9FB'),
                                   ('50','B9FB'),('50','B9FB'),('40','B9FB'),
                                   ('50','B9FB'),('51','B9F0')]]}}
        r = audit.gap_report(source)
        self.assertEqual(r['status'], 'AWAIT_AUTHENTIC_ECU_CAPTURE')
        self.assertFalse(r['replay_approved'])
        self.assertEqual([x['attempts'] for x in r['candidate_routes']], [1,2,4,1])
        print('PASS VIDA B3A9 1: original B3A8 has no authentic ECU RX')

    def test_02_valid_shape_only_never_approves_reply_replay(self):
        raw, manifest = fixture()
        r = audit.evaluate_capture(manifest, raw)
        self.assertEqual(r['status'], 'STRUCTURE_ONLY_PENDING_INDEPENDENT_REVIEW')
        self.assertEqual(r['reply_frame_count'], 13)
        self.assertFalse(r['replay_approved'])
        self.assertNotIn('SYNTHET', json.dumps(r))
        self.assertFalse(r['payload_released'])
        print('PASS VIDA B3A9 2: synthetic D2 shape is manual-review-only')

    def test_03_wrong_vehicle_year_platform_engine_rejected(self):
        raw, base = fixture()
        for key, val in [('model', 'V50'), ('platform', 'P3'),
                         ('engine', 'D4164T'), ('model_year', 2005)]:
            m = copy.deepcopy(base); m['vehicle'][key] = val
            self.assertEqual(audit.evaluate_capture(m, raw)['status'], 'REJECTED')
        print('PASS VIDA B3A9 3: V50/P3/diesel/old-year donors rejected')

    def test_04_protocol_target_service_guard(self):
        raw, base = fixture()
        for key, val in [('ecu', '51'), ('service', 'B9F0'),
                         ('protocol', 'ISO9141'), ('baud_bps', 10400)]:
            m = copy.deepcopy(base); m['route'][key] = val
            self.assertEqual(audit.evaluate_capture(m, raw)['status'], 'REJECTED')
        print('PASS VIDA B3A9 4: CAN 50 B9FB is not K-Line 51 B9F0')

    def test_05_original_capture_checksum_and_immutability(self):
        raw, base = fixture()
        self.assertEqual(audit.evaluate_capture(base, raw + b'!')['status'], 'REJECTED')
        m = copy.deepcopy(base); m['source']['raw_unchanged'] = False
        self.assertEqual(audit.evaluate_capture(m, raw)['status'], 'REJECTED')
        m = copy.deepcopy(base); m['source']['sha256'] = 'B' * 64
        self.assertEqual(audit.evaluate_capture(m, raw)['status'], 'REJECTED')
        print('PASS VIDA B3A9 5: tampered original and hash rejected')

    def test_06_source_origin_and_vehicle_document_required(self):
        raw, base = fixture()
        for origin in ('historical_public', 'virtualcar_lab', 'unknown'):
            m = copy.deepcopy(base); m['source']['origin'] = origin
            self.assertEqual(audit.evaluate_capture(m, raw)['status'], 'REJECTED')
        m = copy.deepcopy(base); m['vehicle']['identity_record_sha256'] = ''
        self.assertEqual(audit.evaluate_capture(m, raw)['status'], 'REJECTED')
        print('PASS VIDA B3A9 6: no historical/synthetic provenance promotion')

    def test_07_gaps_order_replayed_frames_and_event_hashes(self):
        raw, base = fixture()
        m = copy.deepcopy(base); m['events']['responses'].pop(4)
        self.assertEqual(audit.evaluate_capture(m, raw)['status'], 'REJECTED')
        m = copy.deepcopy(base); m['events']['responses'][0]['line_sha256'] = '0' * 64
        self.assertEqual(audit.evaluate_capture(m, raw)['status'], 'REJECTED')
        m = copy.deepcopy(base); m['events']['responses'].reverse()
        self.assertEqual(audit.evaluate_capture(m, raw)['status'], 'REJECTED')
        print('PASS VIDA B3A9 7: missing CF, bad source line SHA, order rejected')

    def test_08_wrong_or_duplicate_payload_id_cannot_be_accepted(self):
        raw, base = fixture()
        parts = raw.splitlines(keepends=True)
        parts[0] = parts[0].replace(b'0x50, 0xB9, 0xFB', b'0x40, 0xB9, 0xFB')
        altered = b''.join(parts)
        m = copy.deepcopy(base)
        m['source']['sha256'] = hash_bytes(altered); m['source']['size_bytes'] = len(altered)
        m['events']['request']['line_sha256'] = hash_bytes(parts[0])
        self.assertEqual(audit.evaluate_capture(m, altered)['status'], 'REJECTED')
        parts = raw.splitlines(keepends=True)
        parts[1] = parts[1].replace(b'0xF9, 0xFB', b'0xF9, 0xF0')
        altered = b''.join(parts)
        m = copy.deepcopy(base)
        m['source']['sha256'] = hash_bytes(altered); m['source']['size_bytes'] = len(altered)
        m['events']['responses'][0]['line_sha256'] = hash_bytes(parts[1])
        self.assertEqual(audit.evaluate_capture(m, altered)['status'], 'REJECTED')
        print('PASS VIDA B3A9 8: request target and F9FB response service must match')


if __name__ == '__main__':
    unittest.main(verbosity=2)
