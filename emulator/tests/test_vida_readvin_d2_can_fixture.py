"""Synthetic-only D2-on-CAN byte-layout checks, NOT live VIDA acceptance."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import vida_readvin_d2_can_fixture as fixture


class ReadVinSyntheticD2CanFixtureTests(unittest.TestCase):
    def test_01_first_cem_d2_candidate_has_source_derived_request_bytes(self):
        result = fixture.make_d2_single_frame(0x40, bytes.fromhex('B9 FB'))
        self.assertEqual(result['protocol_id'], 5)
        self.assertEqual(result['tx_flags'], 0x100)
        self.assertEqual(result['data_size'], 12)
        self.assertEqual(result['data'], bytes.fromhex(
            '00 0F FF FE CB 40 B9 FB 00 00 00 00'))
        self.assertEqual(len(result['data']), 12)

    def test_02_different_logical_address_changes_only_d2_address_byte(self):
        a = fixture.make_d2_single_frame(0x40, bytes.fromhex('B9 FB'))
        b = fixture.make_d2_single_frame(0x50, bytes.fromhex('B9 FB'))
        self.assertEqual(a['data'][:5], b['data'][:5])
        self.assertEqual(a['data'][6:], b['data'][6:])
        self.assertEqual(b['data'][5], 0x50)

    def test_03_single_frame_last_supported_size_is_seven_addressed_bytes(self):
        result = fixture.make_d2_single_frame(
            0x40, bytes.fromhex('01 02 03 04 05 06'))
        self.assertEqual(result['data'], bytes.fromhex(
            '00 0F FF FE CF 40 01 02 03 04 05 06'))

    def test_04_reject_invalid_address_type_and_out_of_range(self):
        for address in (-1, 256, True, '40', None):
            with self.subTest(address=address), self.assertRaises(ValueError):
                fixture.make_d2_single_frame(address, b'\xB9\xFB')

    def test_05_reject_invalid_service_type_or_size(self):
        for request in (b'', b'\x01'*7, bytearray(b'\xB9'), 'B9 FB', None):
            with self.subTest(request=request), self.assertRaises(ValueError):
                fixture.make_d2_single_frame(0x40, request)

    def test_06_positive_b9_response_requires_correct_ecu_and_offset(self):
        # Response CAN-ID is unspecified in this synthetic test, and the
        # original interpreter checks address/service/offset in data.
        response = bytes.fromhex('00 00 00 00 CB 40 F9 FB 00 00 00 00')
        self.assertTrue(fixture.matches_b9_positive_single_frame(
            response, 0x40, 0xFB))
        self.assertFalse(fixture.matches_b9_positive_single_frame(
            response, 0x50, 0xFB))
        self.assertFalse(fixture.matches_b9_positive_single_frame(
            response, 0x40, 0xF0))
        negative = bytes.fromhex('00 00 00 00 CB 40 7F B9 00 00 00 00')
        self.assertFalse(fixture.matches_b9_positive_single_frame(
            negative, 0x40, 0xFB))

    def test_07_fixture_never_claims_real_j2534_or_vida_accepted(self):
        result = fixture.make_d2_single_frame(0x40, b'\xB9\xFB')
        self.assertIs(result['vida_runtime_accepted'], False)
        self.assertIs(result['physical_j2534_tested'], False)
        self.assertEqual(result['source_evidence'],
                         'owner_original_vida_static_il_only')
        self.assertFalse(fixture.matches_b9_positive_single_frame(b'', 0x40, 0xFB))


if __name__ == '__main__':
    unittest.main()
