"""Synthetic gated DiceTiming HMAC comparison; never accesses original VIDA data."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import vida_dicetiming_catalog as dt
import compare_vida_dicetiming_catalog as comparison
import vida_evidence_summary as summary

KEY = 'a1' * 32
OTHER_KEY = 'b2' * 32


def schema(rows=(('dbo', 'one', ('alpha', 'beta')),
                 ('dbo', 'two', ('gamma',)))):
    return {(namespace, table): set(columns) for namespace, table, columns in rows}


def fingerprint_pair(a=None, b=None, key=KEY, other_key=KEY):
    a = schema() if a is None else a
    b = schema() if b is None else b
    return (dt._finish(a, 0, 'sqlite-export', key),
            dt._finish(b, 0, 'sqlserver', other_key))


class DiceTimingHmacTests(unittest.TestCase):
    def test_01_opt_in_only_and_no_original_names(self):
        plain = dt._finish(schema(), 0, 'sqlite-export')
        self.assertNotIn('visible_schema_hmac_sha256', plain)
        redacted = dt._finish(schema(), 0, 'sqlite-export', KEY)
        self.assertEqual(redacted['visible_schema_hmac_scope'], dt.SHAPE_SCOPE)
        self.assertEqual(len(redacted['visible_schema_hmac_sha256']), 64)
        serial = json.dumps(redacted)
        self.assertNotIn(KEY, serial)
        self.assertNotIn('alpha', serial)
        self.assertNotIn('gamma', serial)

    def test_02_canonical_order_of_metadata_does_not_change_hmac(self):
        left = schema()
        right = schema((('dbo', 'two', ('gamma',)),
                        ('dbo', 'one', ('beta', 'alpha'))))
        self.assertEqual(dt._shape_hmac(left, KEY), dt._shape_hmac(right, KEY))

    def test_03_distinct_schemas_same_counts_have_distinct_hmac(self):
        different = schema((('dbo', 'one', ('alpha', 'delta')),
                            ('dbo', 'two', ('gamma',))))
        left, right = fingerprint_pair(b=different)
        report = comparison.compare(left, right)
        self.assertTrue(report['aggregate_counts_equal'])
        self.assertEqual(report['visible_schema_hmac_comparison'], 'mismatched')
        self.assertFalse(report['visible_schema_hmac_equal'])
        self.assertFalse(report['schema_equivalence_verified'])

    def test_04_same_visible_metadata_and_key_matches_without_provenance(self):
        left, right = fingerprint_pair()
        report = comparison.compare(left, right)
        self.assertEqual(report['visible_schema_hmac_comparison'], 'matched')
        self.assertTrue(report['visible_schema_hmac_equal'])
        self.assertFalse(report['same_installation_provenance_verified'])
        result = summary.assemble(dice_timing_comparison=report)
        gates = {item['id']: item['status'] for item in result['stages']}
        self.assertEqual(gates['dice_timing_visible_schema_hmac'], 'passed')
        self.assertFalse(result['actual_getscript_selected'])
        self.assertFalse(result['client_vin_accepted'])

    def test_05_different_key_cannot_be_mistaken_for_matched_shape(self):
        left, right = fingerprint_pair(other_key=OTHER_KEY)
        self.assertEqual(comparison.compare(left, right)['visible_schema_hmac_comparison'],
                         'mismatched')

    def test_06_keyless_backward_compatible_and_partial_pair_rejected(self):
        left, right = dt._finish(schema(), 0, 'sqlite-export'), dt._finish(schema(), 0, 'sqlserver')
        report = comparison.compare(left, right)
        self.assertEqual(report['visible_schema_hmac_comparison'], 'not_tested')
        result = summary.assemble(dice_timing_comparison=report)
        gate = next(item for item in result['stages'] if item['id'] == 'dice_timing_visible_schema_hmac')
        self.assertEqual(gate['status'], 'not_tested')
        right['visible_schema_hmac_sha256'] = dt._shape_hmac(schema(), KEY)
        right['visible_schema_hmac_scope'] = dt.SHAPE_SCOPE
        with self.assertRaises(comparison.CompareError):
            comparison.compare(left, right)

    def test_07_invalid_hmac_formats_and_wrong_scope_rejected(self):
        for invalid in ('A' * 64, 'a' * 63, True, 23):
            left, right = fingerprint_pair()
            left['visible_schema_hmac_sha256'] = invalid
            with self.subTest(value=str(invalid)[:10]), self.assertRaises(comparison.CompareError):
                comparison.compare(left, right)
        left, right = fingerprint_pair()
        left['visible_schema_hmac_scope'] = 'not_matching'
        with self.assertRaises(comparison.CompareError):
            comparison.compare(left, right)

    def test_08_forged_positive_output_cannot_promote_identity(self):
        left, right = fingerprint_pair()
        report = comparison.compare(left, right)
        report['schema_equivalence_verified'] = True
        with self.assertRaises(summary.EvidenceError):
            summary.assemble(dice_timing_comparison=report)
        report['schema_equivalence_verified'] = False
        report['visible_schema_hmac_equal'] = False
        with self.assertRaises(summary.EvidenceError):
            summary.assemble(dice_timing_comparison=report)

    def test_09_mismatched_hmac_is_failed_gate_even_equal_counts(self):
        changed = schema((('dbo', 'one', ('alpha', 'delta')),
                          ('dbo', 'two', ('gamma',))))
        report = comparison.compare(*fingerprint_pair(b=changed))
        result = summary.assemble(dice_timing_comparison=report)
        gates = {item['id']: item['status'] for item in result['stages']}
        self.assertEqual(gates['dice_timing_count_comparison'], 'passed')
        self.assertEqual(gates['dice_timing_visible_schema_hmac'], 'failed')
        self.assertIn('dice_timing_visible_schema_hmac', result['open_blockers'])

    def test_10_invalid_private_key_is_redacted_and_rejected(self):
        for key in ('a' * 63, 'G' * 64, '', None, 1):
            if key is None:
                continue
            with self.subTest(key=str(key)[:3]), self.assertRaises(dt.DiceTimingError) as caught:
                dt._finish(schema(), 0, 'sqlserver', key)
            if key:
                self.assertNotIn(str(key), str(caught.exception))

    def test_11_cli_does_not_write_secret_or_source_name(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            dbpath = folder / 'DiceTiming.sqlite'
            with contextlib.closing(sqlite3.connect(dbpath)) as db:
                db.executescript('''
                    CREATE TABLE _vida_meta ("key" TEXT,"value" TEXT);
                    CREATE TABLE _vida_tables (schema_name TEXT,table_name TEXT,rows_exported INT);
                    CREATE TABLE _vida_columns (schema_name TEXT,table_name TEXT,column_name TEXT,system_type_id INT);
                ''')
                for k, v in (('schema_version', dt.EXPORT_SCHEMA), ('source_database', dt.DATABASE),
                             ('scope', 'all_user_tables')):
                    db.execute('INSERT INTO _vida_meta VALUES(?,?)', (k,v))
                db.execute('INSERT INTO _vida_tables VALUES(?,?,?)', ('dbo','SECRET_TABLE',1))
                db.execute('INSERT INTO _vida_columns VALUES(?,?,?,?)', ('dbo','SECRET_TABLE','PRIVATE_COL',56))
                db.commit()
            out = folder / 'out.json'
            with patch.dict(os.environ, {dt.SHAPE_KEY_ENV: KEY}):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(dt.main(['--backend','sqlite-export','--folder',str(folder),
                                              '--output',str(out)]), 0)
            text = out.read_text()
            self.assertNotIn('SECRET_TABLE', text)
            self.assertNotIn('PRIVATE_COL', text)
            self.assertNotIn(KEY, text)
            self.assertEqual(len(json.loads(text)['visible_schema_hmac_sha256']), 64)

    def test_12_matching_digest_with_conflicting_totals_fails_closed(self):
        left, right = fingerprint_pair()
        right['column_count'] += 1
        with self.assertRaises(comparison.CompareError):
            comparison.compare(left, right)


if __name__ == '__main__':
    unittest.main()
