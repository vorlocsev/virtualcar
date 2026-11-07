"""Synthetic-only tests, no donor VIN and no original DLL execution."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from vida_vin_shape_ascii import matches_vida_legacy_ascii_shape, LEGACY_PREFIXES


class LegacyVidaAsciiVinShapeTests(unittest.TestCase):
    def test_01_reject_missing_and_non_string(self):
        for candidate in (None, '', b'YV' + b'X' * 9 + b'123456', 12, []):
            self.assertFalse(matches_vida_legacy_ascii_shape(candidate))

    def test_02_exact_length_only(self):
        for n in (8, 16, 18, 20):
            self.assertFalse(matches_vida_legacy_ascii_shape('YV' + 'X' * max(0, n-8) + '123456'))
        self.assertTrue(matches_vida_legacy_ascii_shape('YV' + 'X' * 9 + '123456'))

    def test_03_six_trailing_decimal_digits(self):
        self.assertTrue(matches_vida_legacy_ascii_shape('YV' + 'X' * 9 + '000000'))
        self.assertFalse(matches_vida_legacy_ascii_shape('YV' + 'X' * 9 + '12A456'))
        self.assertFalse(matches_vida_legacy_ascii_shape('YV' + 'X' * 9 + '------'))

    def test_04_all_four_allowlisted_prefixes(self):
        self.assertEqual(LEGACY_PREFIXES, ('YV', 'PN', 'LV', 'LY'))
        for prefix in LEGACY_PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertTrue(matches_vida_legacy_ascii_shape(prefix + 'X' * 9 + '123456'))

    def test_05_nonallowlisted_prefix(self):
        for prefix in ('ZZ', 'AA', 'YP', 'PP'):
            self.assertFalse(matches_vida_legacy_ascii_shape(prefix + 'X' * 9 + '123456'))

    def test_06_prefix_is_not_case_insensitive(self):
        for prefix in ('yv', 'Yv', 'pn', 'lv', 'ly'):
            self.assertFalse(matches_vida_legacy_ascii_shape(prefix + 'X' * 9 + '123456'))

    def test_07_middle_has_no_iso_check_digit_gate(self):
        for middle in ('X' * 9, '@' * 9, 'IOQ' * 3, '0' * 9):
            self.assertTrue(matches_vida_legacy_ascii_shape('YV' + middle + '123456'))

    def test_08_fail_closed_nonascii_input(self):
        self.assertFalse(matches_vida_legacy_ascii_shape('YV' + 'X' * 9 + '١٢٣٤٥٦'))
        self.assertFalse(matches_vida_legacy_ascii_shape('YV' + 'é' + 'X' * 8 + '123456'))


if __name__ == '__main__':
    unittest.main()
