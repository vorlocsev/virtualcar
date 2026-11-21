"""Synthetic-only tests for B3A141 D2 B9F0 static loader parity."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_vida_b3a141_d2_b9f0 import audit_text


def probe(lines='', section='D2_40_B9F0'):
    content = '['+section+']\n'+lines
    target = 'CEM_40' if section == 'D2_40_B9F0' else 'CEM_50'
    return audit_text(content)['routes'][target]


def fixture(*frames, section='D2_40_B9F0', response_id=None):
    lines = ['FrameCount='+str(len(frames))]
    if response_id is not None:
        lines.append('ResponseId='+response_id)
    lines.extend('Frame'+format(i, 'X')+'='+f for i,f in enumerate(frames))
    return probe('\n'.join(lines), section=section)


class B3A141Tests(unittest.TestCase):
    def test_01_absent_count(self):
        self.assertEqual(probe()['static_loader_class'], 'no_frame_count_declared')

    def test_02_zero_count(self):
        self.assertEqual(probe('FrameCount=0')['static_loader_class'], 'zero_frame_count')

    def test_03_single_positive_structural_not_identity(self):
        row = fixture('C8 40 F9 F0 00 00 00 00')
        self.assertEqual(row['static_loader_class'], 'structural_positive_not_oem_verified')
        self.assertFalse(row['actual_rx_or_filter_verification'])

    def test_04_native_50_is_separate_route(self):
        row = fixture('C8 50 F9 F0 00 00 00 00', section='D2_50_B9F0')
        self.assertEqual(row['native_baud_bps'], 500000)
        self.assertEqual(row['static_loader_class'], 'structural_positive_not_oem_verified')

    def test_05_wrong_target_fails(self):
        self.assertEqual(fixture('C8 50 F9 F0 00 00 00 00')['static_loader_class'],
                         'invalid_d2_frame_sequence')

    def test_06_missing_terminal_in_two_frame_capture(self):
        row = fixture('8F 40 F9 F0 00 00 00 00', '09 00 00 00 00 00 00 00')
        self.assertEqual(row['static_loader_class'], 'missing_terminal_frame')

    def test_07_complete_multiframe_shape(self):
        row = fixture('8F 40 F9 F0 00 00 00 00', '09 00 00 00 00 00 00 00',
                      '4F 00 00 00 00 00 00 00')
        self.assertEqual(row['static_loader_class'], 'structural_positive_not_oem_verified')

    def test_08_terminal_must_be_last(self):
        row = fixture('8F 40 F9 F0 00 00 00 00', '4F 00 00 00 00 00 00 00',
                      '09 00 00 00 00 00 00 00')
        self.assertEqual(row['static_loader_class'], 'invalid_d2_frame_sequence')

    def test_09_negative_reply_not_identity(self):
        row = fixture('C8 40 7F B9 00 00 00 00')
        self.assertEqual(row['static_loader_class'], 'structural_negative_not_ecu_identity')

    def test_10_count_and_missing_frame_gates(self):
        self.assertEqual(probe('FrameCount=bad')['static_loader_class'], 'invalid_frame_count')
        self.assertEqual(probe('FrameCount=65')['static_loader_class'], 'frame_count_above_native_limit')
        self.assertEqual(probe('FrameCount=1')['static_loader_class'], 'missing_declared_frame')
        self.assertEqual(probe('FrameCount=1\nFrame0=oops')['static_loader_class'], 'invalid_eight_byte_frame')

    def test_11_response_id_candidate_not_vida_proof(self):
        candidate = fixture('C8 40 F9 F0 00 00 00 00', response_id='00600005')
        self.assertEqual(candidate['response_id_evidence_class'],
                         'cross_vehicle_capture_candidate_not_xc90_proven')
        self.assertFalse(candidate['actual_rx_or_filter_verification'])
        default = fixture('C8 40 F9 F0 00 00 00 00')
        self.assertEqual(default['response_id_evidence_class'], 'native_default_unverified')
        even = fixture('C8 40 F9 F0 00 00 00 00', response_id='00600004')
        self.assertEqual(even['response_id_evidence_class'],
                         'even_id_may_miss_documented_odd_mask')

    def test_12_out_of_range_response_id(self):
        row = fixture('C8 40 F9 F0 00 00 00 00', response_id='20000000')
        self.assertEqual(row['static_loader_class'], 'response_id_outside_29bit_range')

    def test_13_private_values_not_exported(self):
        data = '[Vehicle]\nVIN=SECRET_TEST_VALUE\n[D2_40_B9F0]\n' + (
            'FrameCount=1\nResponseId=00600005\nFrame0=C840F9F001020304\n')
        output = json.dumps(audit_text(data))
        for forbidden in ('SECRET_TEST_VALUE', '00600005', 'C840F9F0', '01020304', 'VIN='):
            self.assertNotIn(forbidden, output)
        self.assertEqual(audit_text(data)['oem_ecu_identity_or_vida_acceptance'], 'NOT_PROVEN')

    def test_14_duplicate_section_is_rejected(self):
        with self.assertRaises(ValueError):
            audit_text('[D2_40_B9F0]\nFrameCount=0\n[d2_40_b9f0]\nFrameCount=1\n')

    def test_15_13_frame_special_terminal_native_parity(self):
        frames = ['8F 40 F9 F0 00 00 00 00']
        frames += [format(0x08 | ((i % 8)+1), '02X')+' 00 00 00 00 00 00 00' for i in range(11)]
        frames += ['48 00 00 00 00 00 00 00']
        self.assertEqual(fixture(*frames)['static_loader_class'], 'invalid_d2_frame_sequence')
        frames[-1] = '4F 00 00 00 00 00 00 00'
        self.assertEqual(fixture(*frames)['static_loader_class'], 'structural_positive_not_oem_verified')


    def test_16_native_acceptance_does_not_mean_wire_length_accepted(self):
        row = fixture('C8 40 F9 F0 00 00 00 00')
        self.assertEqual(row['static_loader_class'], 'structural_positive_not_oem_verified')
        self.assertEqual(row['vida_d2_single_frame_wire_candidate'],
                         'declared_length_shorter_than_target_and_echo')

    def test_17_minimal_echo_without_identity_data(self):
        row = fixture('CB 40 F9 F0 00 00 00 00')
        self.assertEqual(row['vida_d2_single_frame_wire_candidate'],
                         'positive_echo_only_no_identity_payload')

    def test_18_valid_length_and_zero_padding_only_candidate(self):
        row = fixture('CC 40 F9 F0 55 00 00 00')
        self.assertEqual(row['vida_d2_single_frame_wire_candidate'],
                         'single_frame_length_and_padding_candidate')
        self.assertFalse(row['actual_rx_or_filter_verification'])

    def test_19_nonzero_ignored_tail_is_not_a_wire_failure(self):
        row = fixture('CC 40 F9 F0 55 02 00 00')
        self.assertEqual(row['vida_d2_single_frame_wire_candidate'],
                         'single_frame_nonzero_tail_ignored_candidate')

    def test_22_nonzero_residue_does_not_make_empty_echo_identity(self):
        row = fixture('CB 40 F9 F0 41 41 41 41')
        self.assertEqual(row['vida_d2_single_frame_wire_candidate'],
                         'positive_echo_only_no_identity_payload')

    def test_23_negative_reply_with_nonzero_tail_is_still_not_identity(self):
        row = fixture('CC 40 7F B9 12 91 80 01')
        self.assertEqual(row['vida_d2_single_frame_wire_candidate'],
                         'single_frame_nonzero_tail_ignored_candidate')
        self.assertEqual(row['static_loader_class'],
                         'structural_negative_not_ecu_identity')

    def test_20_multiframe_is_not_mistaken_for_single_frame(self):
        row = fixture('8F 40 F9 F0 00 00 00 00',
                      '09 00 00 00 00 00 00 00',
                      '4F 00 00 00 00 00 00 00')
        self.assertEqual(row['vida_d2_single_frame_wire_candidate'],
                         'multiframe_native_shape_only')

    def test_21_invalid_frame_does_not_claim_wire_eligibility(self):
        row = fixture('CC 50 F9 F0 55 00 00 00')
        self.assertEqual(row['vida_d2_single_frame_wire_candidate'], 'not_evaluated')


if __name__ == '__main__':
    unittest.main()
