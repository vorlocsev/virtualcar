"""B3A53: eight synthetic native-source B9FB loader parity gates."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_b3a53_b9fb_loader as mod
sys.path.pop(0)


def state(text, target='CEM_40'):
    return mod.audit_text(text)['b9fb'][target]


def frame(prefix='CB 40 F9 FB', suffix='00 00 00 00'):
    return prefix + ' ' + suffix


class B3A53Tests(unittest.TestCase):
    def test_single_frame_declared_length_bounds_echo_and_nrc(self):
        for header in range(0xC8, 0xD0):
            for echo, minimum in (('F9 FB 00 00 00 00', 3),
                                  ('7F B9 11 00 00 00', 4)):
                with self.subTest(header=header, echo=echo):
                    text = (f'[D2_40]\nFrameCount=1\n'
                            f'Frame0={header:02X} 40 {echo}\n')
                    result = state(text)['static_loader_class']
                    if header - 0xC8 < minimum:
                        self.assertEqual(result, 'invalid_d2_frame_sequence')
                    else:
                        self.assertTrue(result.startswith('locally_structural_'))

    def test_01_missing_count_and_explicit_zero(self):
        self.assertEqual(state('[Vehicle]\nVIN=YV1CZ0002A0000001\n')['static_loader_class'],
                         'no_frame_count_declared')
        self.assertEqual(state('[D2_40]\nB9FBFrameCount=0\n')['static_loader_class'],
                         'zero_frame_count')

    def test_02_invalid_and_out_of_bounds_counts(self):
        self.assertEqual(state('[D2_40]\nFrameCount=wrong\nB9FBFrameCount=1\n')['static_loader_class'],
                         'invalid_frame_count_falls_back_to_zero')
        self.assertEqual(state('[D2_40]\nFrameCount=65\n')['static_loader_class'],
                         'frame_count_exceeds_native_limit')

    def test_03_missing_index_and_first_failure(self):
        out = state('[D2_40]\nFrameCount=2\nB9FBFrame0=' + frame() + '\n')
        self.assertEqual((out['static_loader_class'], out['first_failed_frame_index']),
                         ('missing_declared_frame', 1))

    def test_04_first_key_precedence_and_malformed_hex(self):
        out = state('[D2_40]\nFrameCount=1\nB9FBFrame0=INVALID\nFrame0=' + frame() + '\n')
        self.assertEqual(out['static_loader_class'], 'invalid_eight_byte_frame')
        self.assertEqual(state('[D2_40]\nFrameCount=1\nFrame0=CB40F9FB00000000\n')['static_loader_class'],
                         'locally_structural_reply_not_oem_verified')

    def test_05_response_id_limit_and_prefix(self):
        out = state('[D2_40]\nFrameCount=1\nResponseId=FFFFFFFF\nB9FBFrame0=' + frame() + '\n')
        self.assertEqual(out['static_loader_class'], 'response_id_outside_29bit_range')
        self.assertEqual(state('[D2_40]\nFrameCount=1\nResponseId=0x00800003\nFrame0=' + frame() + '\n')['static_loader_class'],
                         'locally_structural_reply_not_oem_verified')

    def test_06_wrong_target_and_native_negative_reply(self):
        self.assertEqual(state('[D2_40]\nFrameCount=1\nFrame0=' + frame('CB 50 F9 FB') + '\n')['static_loader_class'],
                         'invalid_d2_frame_sequence')
        self.assertEqual(state('[D2_40]\nFrameCount=1\nFrame0=' + frame('CC 40 7F B9', '11 00 00 00') + '\n')['static_loader_class'],
                         'locally_structural_negative_reply_not_vin')

    def test_07_multiframe_native_sequence_and_terminal(self):
        cfg = ('[D2_50]\nFrameCount=2\n'
               'Frame0=8F 50 F9 FB 00 00 00 00\n'
               'Frame1=4F 00 00 00 00 00 00 00\n')
        self.assertEqual(state(cfg,'CEM_50')['static_loader_class'],
                         'locally_structural_reply_not_oem_verified')
        self.assertEqual(state(cfg.replace('Frame1=4F', 'Frame1=08'),'CEM_50')['static_loader_class'],
                         'invalid_d2_frame_sequence')

    def test_08_privacy_and_unsupported_input(self):
        out = mod.audit_text('[Vehicle]\nVIN=PRIVATE_VIN_12345\n[D2_40]\nFrameCount=1\nFrame0=' + frame() + '\n')
        serialized = json.dumps(out)
        for fragment in ('PRIVATE_VIN', 'C840F9FB', 'YV1CZ', '1234ABCD'):
            self.assertNotIn(fragment, serialized)
        self.assertFalse(out['vida_vin_accepted'])
        self.assertFalse(out['authentic_oem_cem_response'])
        with self.assertRaises(ValueError):
            mod.audit_text('[D2_40]\nFrameCount=1\n[d2_40]\nFrameCount=2\n')


if __name__ == '__main__':
    unittest.main()
