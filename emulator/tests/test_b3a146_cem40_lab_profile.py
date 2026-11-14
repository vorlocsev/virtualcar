"""Twelve offline synthetic-only safety and shape checks for B3A146."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_b3a146_cem40_lab_profile as m

TEMPLATE = m.TEMPLATE.read_text(encoding='utf-8')
VIN = 'YV1CZ0003A0000002'
ID = json.dumps({'Vehicle': {'VIN': VIN, 'ModelYear': 2009}})


def frames(cfg):
    return [m._frame(cfg.get('D2_40', f'B9FBFrame{i:X}')) for i in range(13)]


class B3A146SyntheticTests(unittest.TestCase):
    def test_01_13_frame_40_active_and_50_disabled(self):
        cfg = m._cfg(m.build_profile(TEMPLATE, ID))
        self.assertEqual(cfg.get('D2_40', 'B9FBFrameCount'), '13')
        self.assertEqual(cfg.get('D2_50', 'B9FBFrameCount'), '0')
        self.assertFalse(cfg.has_option('D2_50', 'B9FBFrame0'))
        self.assertEqual(tuple(f[0] for f in frames(cfg)), m.FRAME_HEADERS)
        stream = b''.join(f[1:] for f in frames(cfg))
        self.assertEqual(stream[:3], b'\x40\xf9\xfb')
        self.assertEqual(stream[14:31], VIN.encode())

    def test_02_only_target_and_private_vin_change_from_donor_stream(self):
        old = m._cfg(TEMPLATE)
        a = b''.join(m._frame(old.get('D2_50', f'B9FBFrame{i:X}'))[1:] for i in range(13))
        b = b''.join(f[1:] for f in frames(m._cfg(m.build_profile(TEMPLATE, ID))))
        self.assertEqual(b[0], 0x40)
        self.assertEqual(a[1:14], b[1:14])
        self.assertEqual(a[31:], b[31:])
        self.assertEqual(len(a), len(b))

    def test_03_b9f0_default_disabled_and_fc_still_silent(self):
        cfg = m._cfg(m.build_profile(TEMPLATE, ID))
        for sec in ('D2_40_B9F0', 'D2_50_B9F0', 'D2_40_B9FC', 'D2_50_B9FC'):
            self.assertEqual(cfg.get(sec, 'FrameCount'), '0')
        self.assertEqual(cfg.get('P2', 'StrictRouting'), '1')

    def test_04_explicit_synthetic_f0_2_frame_shape(self):
        cfg = m._cfg(m.build_profile(TEMPLATE, ID, enable_synthetic_b9f0=True))
        self.assertEqual(cfg.get('D2_40_B9F0', 'FrameCount'), '2')
        first = m._frame(cfg.get('D2_40_B9F0', 'Frame0'))
        last = m._frame(cfg.get('D2_40_B9F0', 'Frame1'))
        self.assertEqual((first[0],last[0]), (0x8F,0x4F))
        self.assertEqual((first+last)[1:4], b'\x40\xf9\xf0')
        self.assertEqual(first[1:]+last[1:], b'\x40\xf9\xf0SIM-CEM-125')
        self.assertEqual(cfg.get('D2_50_B9F0', 'FrameCount'), '0')

    def test_05_invalid_vin_year_and_ambiguous_layout_rejected(self):
        for sample in ({'Vehicle':{'VIN':'BAD','ModelYear':2009}},
                       {'Vehicle':{'VIN':VIN,'ModelYear':2010}},
                       {'Vehicle':{'VIN':VIN}},
                       {'VIN':VIN,'ModelYear':2009,'Vehicle':{'VIN':VIN,'ModelYear':2009}}):
            with self.subTest(sample=str(sample)[:30]), self.assertRaises(ValueError):
                m.build_profile(TEMPLATE, json.dumps(sample))

    def test_06_case_collision_and_duplicate_vin_json_rejected(self):
        for sample in ('{"VIN":"'+VIN+'","vin":"'+VIN+'","ModelYear":2009}',
                       '{"VIN":"'+VIN+'","VIN":"'+VIN+'","ModelYear":2009}'):
            with self.assertRaises(ValueError):
                m.build_profile(TEMPLATE, sample)

    def test_07_modified_donor_vin_fails_closed(self):
        with self.assertRaises(ValueError):
            m.build_profile(TEMPLATE.replace(m.EXPECTED_TEMPLATE_VIN, VIN), ID)

    def test_08_malformed_or_ambiguous_frames_fail_closed(self):
        for variant in (TEMPLATE.replace('B9FBFrame0 = 8F', 'B9FBFrame0 = ZZ'),
                        TEMPLATE.replace('B9FBFrame2 = 0A', 'B9FBFrame2 = 4F'),
                        TEMPLATE.replace('B9FBFrameCount = 13','B9FBFrameCount = 12'),
                        TEMPLATE.replace('B9FBFrame0 = 8F 50','B9FBFrame0 = 8F 40')):
            with self.assertRaises(ValueError):
                m.build_profile(variant, ID)

    def test_09_extra_active_fixtures_and_loose_routing_fail_closed(self):
        for variant in (TEMPLATE.replace('FrameCount = 0','FrameCount = 1',1),
                        TEMPLATE.replace('StrictRouting = 1','StrictRouting = 0'),
                        TEMPLATE.replace('B9FBFrameCount = 0','B9FBFrameCount = 13',1)):
            with self.assertRaises(ValueError):
                m.build_profile(variant, ID)

    def test_10_exclusive_write_refuses_overwrite_and_active_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'b3a146-cem40-lab.ini'
            value = m.build_profile(TEMPLATE, ID)
            m.write_new(p, value)
            self.assertEqual(p.read_text(encoding='utf-8'), value)
            with self.assertRaises(FileExistsError):
                m.write_new(p, 'unsafe overwrite')
            with self.assertRaises(ValueError):
                m.write_new(Path(tmp) / 'virtualcar.ini', value)

    def test_11_cli_does_not_disclose_private_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'vehicle-identity.json'
            target = Path(tmp) / 'b3a146-cem40-lab.ini'
            path.write_text(ID, encoding='utf-8')
            out,err = io.StringIO(),io.StringIO()
            with redirect_stdout(out),redirect_stderr(err):
                result = m.main(['--identity-json',str(path),'--output',str(target)])
            self.assertEqual(result, 0, err.getvalue())
            self.assertNotIn(VIN, out.getvalue() + err.getvalue())
            self.assertNotIn(str(target), out.getvalue() + err.getvalue())
            self.assertIn('NOT_ACTIVATED', out.getvalue())
            self.assertEqual(m._cfg(target.read_text()).get('Vehicle','VIN'), VIN)

    def test_12_repeat_cli_fails_without_modifying_existing_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            identity = Path(tmp)/'vehicle-identity.json'
            target = Path(tmp)/'b3a146-cem40-lab.ini'
            identity.write_text(ID,encoding='utf-8')
            with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                self.assertEqual(m.main(['--identity-json',str(identity),'--output',str(target)]),0)
            first = target.read_bytes()
            with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                self.assertEqual(m.main(['--identity-json',str(identity),'--output',str(target)]),2)
            self.assertEqual(first,target.read_bytes())

if __name__ == '__main__':
    unittest.main()
