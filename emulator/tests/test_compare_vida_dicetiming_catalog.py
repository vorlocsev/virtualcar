"""Synthetic privacy and fail-closed tests for aggregate-only DiceTiming comparison."""
from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import vida_dicetiming_catalog as source
import compare_vida_dicetiming_catalog as mod


def report(backend='sqlite-export', tables=2, columns=3, fks=0):
    result = source._finish({('dbo', 'private_a'): {'one', 'two'},
                             ('dbo', 'private_b'): {'one'}}, fks, backend)
    result['table_count'] = tables
    result['column_count'] = columns
    return result


class DiceTimingCompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def test_01_matching_counts_are_not_schema_equivalence(self):
        item = mod.compare(report(), report('sqlserver', fks=3))
        self.assertTrue(item['aggregate_counts_equal'])
        self.assertFalse(item['schema_equivalence_verified'])
        self.assertFalse(item['timing_profile_link_verified'])
        self.assertFalse(item['d2_baud_verified'])
        self.assertEqual(item['sqlserver_declared_fk_column_count'], 3)

    def test_02_different_table_count_marks_mismatch(self):
        item = mod.compare(report(), report('sqlserver', tables=3))
        self.assertFalse(item['aggregate_counts_equal'])
        self.assertFalse(item['table_counts_equal'])
        self.assertTrue(item['column_counts_equal'])

    def test_03_different_column_count_marks_mismatch(self):
        item = mod.compare(report(), report('sqlserver', columns=4))
        self.assertFalse(item['aggregate_counts_equal'])
        self.assertFalse(item['column_counts_equal'])

    def test_04_missing_wrong_schema_and_wrong_backends_rejected(self):
        a, b = report(), report('sqlserver')
        a['database'] = 'PRIVATE_OTHER_DB'
        with self.assertRaises(mod.CompareError):
            mod.compare(a, b)
        a = report('sqlserver')
        with self.assertRaises(mod.CompareError):
            mod.compare(a, b)
        a = report()
        b['schema_version'] = 'invalid'
        with self.assertRaises(mod.CompareError):
            mod.compare(a, b)

    def test_05_negative_runtime_flags_required(self):
        for flag in mod.NEGATIVE:
            a = report()
            del a[flag]
            with self.subTest(flag=flag), self.assertRaises(mod.CompareError):
                mod.compare(a, report('sqlserver'))
            a[flag] = True
            with self.subTest(forged=flag), self.assertRaises(mod.CompareError):
                mod.compare(a, report('sqlserver'))

    def test_06_boolean_negative_missing_or_overflow_counts_rejected(self):
        for name, value in (('table_count', True), ('column_count', -1),
                            ('table_count', 2001), ('column_count', 30001),
                            ('declared_fk_column_count', False)):
            a = report()
            a[name] = value
            with self.subTest(name=name, val=value), self.assertRaises(mod.CompareError):
                mod.compare(a, report('sqlserver'))

    def test_07_sqlite_fk_metadata_cannot_be_claimed(self):
        a = report(fks=1)
        with self.assertRaises(mod.CompareError):
            mod.compare(a, report('sqlserver'))

    def test_08_incomplete_catalog_rejected(self):
        for a in (report(tables=0), report(columns=1)):
            with self.assertRaises(mod.CompareError):
                mod.compare(a, report('sqlserver'))

    def test_09_private_extra_fields_never_transferred(self):
        a, b = report(), report('sqlserver')
        a['proprietary_thing'] = 'SECRET_CUSTOMER_VIN_123'
        b['secret'] = 'PRIVATE_SCHEMA_NAME'
        output = json.dumps(mod.compare(a, b))
        self.assertNotIn('SECRET', output)
        self.assertNotIn('PRIVATE', output)

    def test_10_duplicate_keys_nonfinite_and_oversize_rejected(self):
        source_path = self.folder / 'source.json'
        for invalid in ('{"x":1,"x":2}', '{"x":NaN}'):
            source_path.write_text(invalid, encoding='utf-8')
            with self.assertRaises(mod.CompareError):
                mod._read(source_path)
        source_path.write_bytes(b'X' * (mod.MAX_BYTES + 1))
        with self.assertRaises(mod.CompareError):
            mod._read(source_path)

    def test_11_cli_output_exclusive_no_secret_echo(self):
        a, b, out = (self.folder / p for p in ('sqlite.json', 'sqlserver.json', 'summary.json'))
        src = report()
        src['private'] = 'VIN_SECRET'
        a.write_text(json.dumps(src), encoding='utf-8')
        b.write_text(json.dumps(report('sqlserver')), encoding='utf-8')
        args = ['--sqlite-report', str(a), '--sqlserver-report', str(b), '--output', str(out)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(mod.main(args), 0)
            self.assertEqual(mod.main(args), 2)
        self.assertTrue(json.loads(out.read_text())['aggregate_counts_equal'])
        self.assertNotIn('VIN_SECRET', out.read_text())
        self.assertNotIn(str(a), stderr.getvalue())

    def test_12_input_aliases_and_symlink_rejected(self):
        a = self.folder / 'a.json'
        a.write_text(json.dumps(report()), encoding='utf-8')
        b = self.folder / 'link.json'
        try:
            b.symlink_to(a)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaises(mod.CompareError):
            mod._read(b)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(mod.main(['--sqlite-report', str(a), '--sqlserver-report',
                                       str(a), '--output', str(self.folder / 'out.json')]), 2)


if __name__ == '__main__':
    unittest.main()
