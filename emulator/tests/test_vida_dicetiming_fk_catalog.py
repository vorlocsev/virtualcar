"""Synthetic, owner-private-safe SQL Server DiceTiming FK integrity tests."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import vida_dicetiming_catalog as dt
import vida_evidence_summary as summary

TABLES = [('dbo', 'PrivateTimings'), ('dbo', 'PrivateConfig')]
COLUMNS = [
    ('dbo', 'PrivateTimings', 'id'),
    ('dbo', 'PrivateTimings', 'cfg'),
    ('dbo', 'PrivateTimings', 'cfg_alt'),
    ('dbo', 'PrivateTimings', 'parent'),
    ('dbo', 'PrivateConfig', 'id'),
    ('dbo', 'PrivateConfig', 'id_alt'),
]
KEYS = [
    (100, 1, 'dbo', 'PrivateTimings', 'cfg', 'dbo', 'PrivateConfig', 'id', False, True, 2),
    (100, 2, 'dbo', 'PrivateTimings', 'cfg_alt', 'dbo', 'PrivateConfig', 'id_alt', False, True, 2),
    (101, 1, 'dbo', 'PrivateTimings', 'parent', 'dbo', 'PrivateTimings', 'id', True, False, 1),
]


class FakeCursor:
    def __init__(self, db, rows):
        self.db = db
        self.rows = rows
        self.current = []
        self.queries = []

    def execute(self, sql):
        self.queries.append(sql)
        if sql == 'SELECT DB_NAME()':
            self.current = [('DiceTiming',)]
        elif 'FROM sys.foreign_key_columns' in sql:
            self.current = self.rows
        elif 'FROM sys.columns' in sql:
            self.current = COLUMNS
        elif 'FROM sys.tables' in sql:
            self.current = TABLES
        else:
            raise AssertionError('SQL outside metadata allowlist')
        return self

    def fetchmany(self, count):
        return self.current[:count]


class FakeDB:
    def __init__(self, rows):
        self.cursor_obj = FakeCursor(self, rows)
        self.timeout = None
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


class DiceTimingFKCatalogTests(unittest.TestCase):
    def collect(self, rows):
        db = FakeDB(rows)
        result = dt.load_sqlserver('DiceTimingReadOnly', connector=lambda *_a, **_kw: db)
        self.assertTrue(db.closed)
        self.assertEqual(db.timeout, 8)
        self.assertEqual(len(db.cursor_obj.queries), 4)
        self.assertIn('JOIN sys.foreign_keys', db.cursor_obj.queries[-1])
        self.assertIn('fkc.constraint_column_id', db.cursor_obj.queries[-1])
        self.assertIn('FROM sys.index_columns', db.cursor_obj.queries[-1])
        self.assertIn('ic.key_ordinal > 0', db.cursor_obj.queries[-1])
        self.assertTrue(all('sys.' in q or q == 'SELECT DB_NAME()'
                            for q in db.cursor_obj.queries))
        return result

    def test_01_composite_fk_count_once_and_trust_flags(self):
        result = self.collect(KEYS)
        fks = result['visible_fk_catalog']
        self.assertEqual(result['declared_fk_column_count'], 3)
        self.assertEqual(fks['constraint_count'], 2)
        self.assertEqual(fks['disabled_constraint_count'], 1)
        self.assertEqual(fks['untrusted_constraint_count'], 1)
        self.assertEqual(fks['self_referencing_constraint_count'], 1)
        self.assertIs(fks['complete_metadata_visibility_verified'], False)
        self.assertIs(fks['referential_rows_verified'], False)
        text = json.dumps(result)
        self.assertNotIn('PrivateTimings', text)
        self.assertNotIn('PrivateConfig', text)

    def test_02_no_visible_foreign_keys_distinct_from_complete_visibility(self):
        report = self.collect([])
        self.assertEqual(report['visible_fk_catalog']['constraint_count'], 0)
        self.assertFalse(report['visible_fk_catalog']['complete_metadata_visibility_verified'])
        self.assertFalse(report['timing_profile_link_verified'])

    def test_03_conflicting_same_constraint_identity_rejected(self):
        rows = list(KEYS)
        rows[1] = rows[1][:-3] + (True, True, 2)
        with self.assertRaises(dt.DiceTimingError):
            dt._foreign_key_summary(rows, self._tables())

    def test_04_invalid_noncanonical_fk_id_and_flags_rejected(self):
        for value in (False, '100', 0, -5):
            rows = [tuple([value] + list(KEYS[0][1:]))]
            with self.subTest(value=value), self.assertRaises(dt.DiceTimingError):
                dt._foreign_key_summary(rows, self._tables())
        for value in (2, -1, 'true', None):
            rows = [KEYS[0][:-3] + (value, False, 2)]
            with self.subTest(flag=value), self.assertRaises(dt.DiceTimingError):
                dt._foreign_key_summary(rows, self._tables())

    def test_05_duplicate_component_and_orphan_rejected(self):
        with self.assertRaises(dt.DiceTimingError):
            dt._foreign_key_summary(KEYS + [KEYS[0]], self._tables())
        broken = [KEYS[0][:4] + ('unknown_column',) + KEYS[0][5:]]
        with self.assertRaises(dt.DiceTimingError):
            dt._foreign_key_summary(broken, self._tables())

    def test_06_wrong_row_arity_rejected_without_source_echo(self):
        for invalid in (KEYS[0][:-1], KEYS[0] + ('SECRET_VIN',)):
            with self.assertRaises(dt.DiceTimingError) as ctx:
                dt._foreign_key_summary([invalid], self._tables())
            self.assertNotIn('SECRET', str(ctx.exception))

    def test_07_composite_fk_cannot_invent_verified_row_join(self):
        report = self.collect(KEYS)
        self.assertFalse(report['replay_approved'])
        self.assertFalse(report['original_timing_values_read'])
        self.assertFalse(report['readvin_execution_verified'])
        self.assertFalse(report['physical_j2534_verified'])

    def test_08_sqlite_or_legacy_report_does_not_claim_fk_topology(self):
        report = dt._finish({('dbo', 'one'): {'a'}}, 0, 'sqlite-export')
        self.assertNotIn('visible_fk_catalog', report)
        legacy = dt._finish({('dbo', 'one'): {'a'}}, 0, 'sqlserver')
        self.assertNotIn('visible_fk_catalog', legacy)
        with self.assertRaises(dt.DiceTimingError):
            dt._finish({('dbo', 'one'): {'a'}}, 0, 'sqlite-export', fk_stats={
                'constraint_count': 0, 'disabled_constraint_count': 0,
                'untrusted_constraint_count': 0, 'self_referencing_constraint_count': 0})

    def test_09_fk_summary_count_contradiction_rejected(self):
        too_many = {'constraint_count': 2, 'disabled_constraint_count': 0,
                    'untrusted_constraint_count': 0, 'self_referencing_constraint_count': 0}
        with self.assertRaises(dt.DiceTimingError):
            dt._finish({('dbo', 'one'): {'a'}}, 1, 'sqlserver', fk_stats=too_many)
        bad = {'constraint_count': 1, 'disabled_constraint_count': 2,
               'untrusted_constraint_count': 0, 'self_referencing_constraint_count': 0}
        with self.assertRaises(dt.DiceTimingError):
            dt._finish({('dbo', 'one'): {'a'}}, 1, 'sqlserver', fk_stats=bad)

    def test_10_summary_sqlserver_fk_gate_passes_metadata_only(self):
        report = self.collect(KEYS)
        evidence = summary.assemble(dice_timing=report)
        stages = {item['id']: item['status'] for item in evidence['stages']}
        self.assertEqual(stages['dice_timing_visible_fk_catalog'], 'passed')
        self.assertEqual(evidence['dice_timing_catalog']['visible_fk_catalog']
                         ['constraint_count'], 2)
        self.assertFalse(evidence['dice_timing_profile_mapping_verified'])
        self.assertFalse(evidence['same_installation_provenance_verified'])

    def test_11_summary_sqlite_and_old_reports_keep_gate_not_tested(self):
        for backend in ('sqlite-export', 'sqlserver'):
            legacy = dt._finish({('dbo', 'one'): {'a'}}, 0, backend)
            result = summary.assemble(dice_timing=legacy)
            status = {item['id']: item['status'] for item in result['stages']}
            self.assertEqual(status['dice_timing_visible_fk_catalog'], 'not_tested')

    def test_12_summary_forged_complete_visibility_or_counts_rejected(self):
        original = self.collect(KEYS)
        for field, value in (('complete_metadata_visibility_verified', True),
                             ('referential_rows_verified', True),
                             ('constraint_count', 9),
                             ('untrusted_constraint_count', 4)):
            bad = dict(original)
            bad['visible_fk_catalog'] = dict(original['visible_fk_catalog'])
            bad['visible_fk_catalog'][field] = value
            with self.subTest(field=field), self.assertRaises(summary.EvidenceError):
                summary.assemble(dice_timing=bad)

    def test_13_missing_first_ordinal_rejected(self):
        bad = [KEYS[0][:1] + (2,) + KEYS[0][2:]]
        with self.assertRaisesRegex(dt.DiceTimingError, 'noncontiguous FK ordinals'):
            dt._foreign_key_summary(bad, self._tables())

    def test_14_duplicate_ordinal_rejected(self):
        bad = [KEYS[0], KEYS[1][:1] + (1,) + KEYS[1][2:]]
        with self.assertRaisesRegex(dt.DiceTimingError, 'duplicate FK ordinal'):
            dt._foreign_key_summary(bad, self._tables())

    def test_15_interior_gap_rejected(self):
        bad = [KEYS[0], KEYS[1][:1] + (3,) + KEYS[1][2:]]
        with self.assertRaisesRegex(dt.DiceTimingError, 'noncontiguous FK ordinals'):
            dt._foreign_key_summary(bad, self._tables())

    def test_16_noncanonical_ordinals_rejected(self):
        for value in (True, '1', 0, -1, 33):
            bad = [KEYS[0][:1] + (value,) + KEYS[0][2:]]
            with self.subTest(value=value), self.assertRaisesRegex(
                    dt.DiceTimingError, 'invalid FK ordinal'):
                dt._foreign_key_summary(bad, self._tables())

    def test_17_duplicate_source_or_target_member_rejected(self):
        same_source = [KEYS[0], KEYS[1][:4] + ('cfg',) + KEYS[1][5:]]
        same_target = [KEYS[0], KEYS[1][:7] + ('id',) + KEYS[1][8:]]
        for bad in (same_source, same_target):
            with self.assertRaisesRegex(dt.DiceTimingError, 'duplicate FK member column'):
                dt._foreign_key_summary(bad, self._tables())

    def test_18_out_of_order_but_complete_ordinals_accepted(self):
        data = [KEYS[1], KEYS[2], KEYS[0]]
        report = self.collect(data)
        self.assertEqual(report['visible_fk_catalog']['constraint_count'], 2)
        self.assertEqual(report['declared_fk_column_count'], 3)
        self.assertFalse(report['visible_fk_catalog']['complete_metadata_visibility_verified'])

    def test_19_missing_trailing_fk_member_rejected(self):
        # Existing contiguous ordinal 1 is insufficient when target key has 2 columns.
        with self.assertRaisesRegex(dt.DiceTimingError, 'incomplete referenced key column coverage'):
            dt._foreign_key_summary([KEYS[0]], self._tables())

    def test_20_inconsistent_index_key_sizes_rejected(self):
        bad = [KEYS[0], KEYS[1][:-1] + (3,)]
        with self.assertRaisesRegex(dt.DiceTimingError, 'inconsistent referenced key column count'):
            dt._foreign_key_summary(bad, self._tables())

    def test_21_invalid_independent_index_key_counts_rejected(self):
        for value in (None, True, '2', -1, 0, 33):
            row = KEYS[0][:-1] + (value,)
            with self.subTest(key_size=value), self.assertRaisesRegex(
                    dt.DiceTimingError, 'invalid referenced key column count'):
                dt._foreign_key_summary([row], self._tables())

    def test_22_correct_composite_key_passes_without_runtime_proof(self):
        report = self.collect(KEYS)
        self.assertEqual(report['declared_fk_column_count'], 3)
        self.assertEqual(report['visible_fk_catalog']['constraint_count'], 2)
        self.assertFalse(report['visible_fk_catalog']['complete_metadata_visibility_verified'])
        self.assertFalse(report['d2_baud_verified'])

    def test_23_partial_index_visibility_fails_closed(self):
        # Missing index metadata would return count=0, not a verified empty FK.
        partial = [KEYS[0][:-1] + (0,)]
        with self.assertRaises(dt.DiceTimingError):
            dt._foreign_key_summary(partial, self._tables())

    def test_24_no_fk_does_not_establish_complete_visibility(self):
        report = self.collect([])
        self.assertEqual(report['visible_fk_catalog']['constraint_count'], 0)
        self.assertIs(report['visible_fk_catalog']['complete_metadata_visibility_verified'], False)
        self.assertFalse(report['replay_approved'])

    @staticmethod
    def _tables():
        tables = {}
        for schema, table in TABLES:
            tables[schema.casefold(), table.casefold()] = set()
        for schema, table, col in COLUMNS:
            tables[schema.casefold(), table.casefold()].add(col.casefold())
        return tables


if __name__ == '__main__':
    unittest.main()
