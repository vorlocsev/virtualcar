"""Synthetic contract gates; none assert original VIDA acceptance."""
import configparser
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_b3a146_cem40_lab_profile as lab
import audit_backend_evidence as backend
sys.path.pop(0)

IDENTITY = json.dumps({'Vehicle': {'VIN': 'YV1CZ000290000001', 'ModelYear': 2009}})


class ContractTests(unittest.TestCase):
    def test_ae1b_opt_in_and_exact_original_empty_list_shape(self):
        for f0 in (False, True):
            for ae in (False, True):
                text = lab.build_profile(IDENTITY, enable_synthetic_b9f0=f0, enable_synthetic_ae1b=ae)
                self.assertEqual(lab.validate_profile(text, IDENTITY)['ae1b_frames'], int(ae))
                cfg = configparser.ConfigParser()
                cfg.read_string(text)
                self.assertEqual(cfg['D2_40_AE1B']['Enabled'], str(int(ae)))
                if ae:
                    self.assertEqual(bytes.fromhex(cfg['D2_40_AE1B']['Frame0']),
                                     bytes.fromhex('CB 40 EE 1B 00 00 00 00'))

    def test_ae1b_cannot_silently_change_mode_echo_length_or_enable(self):
        text = lab.build_profile(IDENTITY, enable_synthetic_ae1b=True)
        for replacement in ('CA 40 EE 1B', 'CB 50 EE 1B', 'CB 40 F9 1B', 'CB 40 EE 1A'):
            with self.assertRaises(ValueError):
                lab.validate_profile(text.replace('CB 40 EE 1B', replacement), IDENTITY)
        with self.assertRaises(ValueError):
            lab.validate_profile(text.replace('FrameCount = 1', 'FrameCount = 0'), IDENTITY)

    def test_private_identity_consistency(self):
        text = lab.build_profile(IDENTITY)
        report = lab.validate_profile(text, IDENTITY)
        self.assertEqual(report['b9fb_frames'], 13)
        self.assertNotIn('YV1', json.dumps(report))
        self.assertEqual(report['vida_acceptance'], 'NOT_VERIFIED')

    def test_f0_has_fifteen_explicit_zero_placeholder_bytes(self):
        cfg = configparser.ConfigParser()
        cfg.read_string(lab.build_profile(IDENTITY, enable_synthetic_b9f0=True))
        f = [bytes.fromhex(cfg['D2_40_B9F0'][f'Frame{i:X}']) for i in range(3)]
        self.assertEqual(lab.decode_d2(f, service=0xF9, selector=0xF0)[3:], bytes(15))

    def test_no_historical_engine_type_or_date_claim(self):
        data = lab._b9fb(lab._identity(IDENTITY))[3:]
        self.assertEqual(data[11:28], lab._identity(IDENTITY).encode())
        self.assertEqual(data[46:52], b'000001')
        self.assertEqual(data[30:39], b'000000000')
        self.assertEqual(data[58:64], b'000000')
        self.assertNotIn(b'200512', data)

    def test_bad_identity_and_ambiguous_json(self):
        for value in (IDENTITY.replace('2009', '2008'),
                      IDENTITY.replace('290000001', '2A0000001'),
                      '{"VIN":"x","VIN":"y"}'):
            with self.assertRaises(ValueError): lab.build_profile(value)

    def test_mutation_or_extra_fixture_rejected(self):
        text = lab.build_profile(IDENTITY)
        for altered in (text.replace('StrictRouting = 1', 'StrictRouting = 0'),
                        text + '\n[D2_Node0]\nEnabled=1\n',
                        text.replace('8F 40 F9 FB', '8F 50 F9 FB')):
            with self.assertRaises(ValueError): lab.validate_profile(altered, IDENTITY)

    def test_transport_lengths_and_sequence(self):
        for length in (3, 7, 8, 18, 91):
            data = b'\x40\xf9\xfb' + bytes(length - 3)
            frames = lab.encode_d2(data)
            self.assertEqual(lab.decode_d2(frames, service=0xF9, selector=0xFB), data)
        with self.assertRaises(ValueError):
            lab.decode_d2([bytes.fromhex('C8 40 F9 FB 00 00 00 00')], service=0xF9, selector=0xFB)

    def test_exclusive_output_and_no_active_overwrite(self):
        with tempfile.TemporaryDirectory(prefix='cem-lab-') as directory:
            p = Path(directory) / lab.OUTPUT_NAME
            lab.write_new(p, lab.build_profile(IDENTITY))
            original = p.read_bytes()
            with self.assertRaises(FileExistsError): lab.write_new(p, 'changed')
            self.assertEqual(p.read_bytes(), original)
            with self.assertRaises(ValueError): lab.write_new(p.with_name('virtualcar.ini'), '')

    def test_ae1b_probe_is_distinct_from_b9(self):
        self.assertEqual(backend.PROBES['D2_40_AE1B']['service'], 'AE1B')
        self.assertNotIn('D2_50_AE1B', backend.PROBES)

    def test_audit_does_not_count_out_of_length_echo_as_delivered(self):
        from test_audit_j2534_discovery import tool, tx, rx
        for header in (0xC8, 0xC9, 0xCA, 0xCB):
            lines = tx(0xFFFFE, bytes.fromhex('CB 40 B9 F0 00 00 00 00'), ch=1, baud=125000)
            lines += rx(0x800003, bytes((header, 0x40, 0xF9, 0xF0, 0, 0, 0, 0)), ch=1, baud=125000)
            expected = 'delivered' if header == 0xCB else 'partial_rx'
            self.assertEqual(tool.audit(lines)['transactions'][0]['status'], expected)


if __name__ == '__main__': unittest.main()
