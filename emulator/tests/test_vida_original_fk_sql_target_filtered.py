"""Synthetic target-side Profile selection: distinguish FK integrity from filter membership."""
from __future__ import annotations

import contextlib
from decimal import Decimal
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from test_vida_original_fk_sql_filtered import FilteringCursor, Connection
import vida_original_fk_sql_probe as probe
import vida_original_table_reader as reader


class TargetFilteringCursor(FilteringCursor):
    def __init__(self, **kwargs):
        target = kwargs.pop('target_columns', None)
        super().__init__(**kwargs)
        self.target_columns = (target if target is not None else
                               ['id_first', 'id_second', 'profile_identifier', 'target]value'])

    def execute(self, sql, *params):
        if sql == probe.FILTER_COLUMNS_SQL and params == ('dbo', 'T161_Profile'):
            self.calls.append((sql, params))
            self.remaining = [(col,) for col in self.target_columns]
            return self
        return super().execute(sql, *params)


class TargetProfileSQLTests(unittest.TestCase):
    def collect(self, target_filters, filters=None, **kwargs):
        cursor = TargetFilteringCursor(**kwargs)
        connection = Connection(cursor)
        report = probe.capture('CarCom', 'dbo', 'T136_InitHw_Profile',
                               'FK_Profile ОРИГИНАЛ', dsn='VIDA_RO', max_rows=5,
                               filters=filters, target_filters=target_filters,
                               connector=lambda *_a, **_kw: connection)
        self.assertTrue(connection.closed)
        return report, cursor

    def test_01_target_profile_filter_sql_is_bound_and_native(self):
        original = "XC90 V8'; SELECT USER_NAME();-- Исходный"
        report, cursor = self.collect(
            [{'column': 'profile_identifier', 'operator': 'eq', 'value': original}],
            rows=[('XC90 V8', 7, 2)])
        sql, params = cursor.calls[-2]
        self.assertEqual(cursor.calls[2][1], ('dbo', 'T161_Profile'))
        self.assertEqual(params, (original,))
        self.assertIn('WHERE t.[id_first] = s.[fk]]first]', sql)
        self.assertIn('AND t.[profile_identifier] = ?) THEN 2', sql)
        self.assertIn('WHEN EXISTS (SELECT 1 FROM [dbo].[T161_Profile]', sql)
        self.assertIn('THEN 1 ELSE 0', sql)
        self.assertNotIn(original, sql)
        self.assertEqual(report['sql_exists_matches'][0]['original_source_key_values'],
                         ['XC90 V8', 7])
        self.assertEqual(report['target_filter_clauses_original_values'][0]['value'], original)
        self.assertFalse(report['vida_runtime_selected_profile_verified'])

    def test_02_four_distinct_native_statuses_are_not_conflated(self):
        rows = [('Выбран', 1, 2), ('Другой профиль', 2, 1),
                ('Нет FK', 3, 0), (None, 4, -1)]
        report, _ = self.collect([{'column': 'profile_identifier',
                                    'operator': 'eq', 'value': 'XC90'}], rows=rows)
        self.assertEqual(len(report['sql_exists_matches']), 2)
        self.assertEqual(report['sql_exists_target_filter_matches'][0]['original_source_key_values'],
                         ['Выбран', 1])
        self.assertEqual(report['sql_exists_matches_outside_target_filter'][0]['original_source_key_values'],
                         ['Другой профиль', 2])
        self.assertEqual(report['sql_exists_unmatched'][0]['original_source_key_values'],
                         ['Нет FK', 3])
        self.assertEqual(report['sql_null_key_rows'][0]['original_source_key_values'],
                         [None, 4])
        self.assertTrue(report['target_filter_does_not_redefine_fk_integrity'])
        self.assertFalse(report['fk_constraint_enforcement_verified'])

    def test_03_target_is_null_has_no_placeholder(self):
        report, cursor = self.collect([{'column': 'profile_identifier',
                                        'operator': 'is_null'}], rows=[('A', 1, 2)])
        sql, params = cursor.calls[-2]
        self.assertIn('AND t.[profile_identifier] IS NULL)', sql)
        self.assertEqual(params, ())
        self.assertEqual(report['sql_exists_target_filter_matches'][0]['original_source_key_values'],
                         ['A', 1])

    def test_04_target_parameters_precede_source_filter_parameters(self):
        tval = 'Профиль конкретной машины'
        sval = 'Конфигурация'
        tflt = [{'column': 'profile_identifier', 'operator': 'eq', 'value': tval}]
        sflt = [{'column': 'optional_col', 'operator': 'eq', 'value': sval}]
        result, cursor = self.collect(tflt, sflt, rows=[('A', 1, 2)])
        sql, params = cursor.calls[-2]
        self.assertEqual(params, (tval, sval))
        self.assertLess(sql.index('t.[profile_identifier] = ?'),
                        sql.index('s.[optional_col] = ?'))
        self.assertEqual(result['source_selection_scope'], 'filtered_subset_only')
        self.assertEqual(result['target_filter_scope'],
                         'referenced_rows_matching_original_filters')
        self.assertFalse(result['source_complete_within_row_limit'])
        self.assertTrue(result['filtered_source_subset_complete_within_row_limit'])

    def test_05_unknown_target_column_fails_before_reading_rows(self):
        cursor = TargetFilteringCursor(target_columns=['id_first', 'id_second'])
        db = Connection(cursor)
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'absent from SQL catalog'):
            probe.capture('CarCom', 'dbo', 'T136_InitHw_Profile', 'FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO', target_filters=[{'column': 'unknown_profile',
                          'operator': 'eq', 'value': 'A'}], connector=lambda *_a, **_kw: db)
        self.assertEqual(len(cursor.calls), 3)
        self.assertTrue(db.closed)

    def test_06_missing_target_fk_key_metadata_fails_closed(self):
        cursor = TargetFilteringCursor(target_columns=['id_first', 'profile_identifier'])
        db = Connection(cursor)
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError,
                                    'inconsistent target column inventory'):
            probe.capture('CarCom', 'dbo', 'T136_InitHw_Profile', 'FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO', target_filters=[{'column': 'profile_identifier',
                          'operator': 'eq', 'value': 'A'}], connector=lambda *_a, **_kw: db)
        self.assertEqual(len(cursor.calls), 3)

    def test_07_duplicate_target_catalog_column_rejected(self):
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError,
                                    'inconsistent target column inventory'):
            self.collect([{'column': 'id_first', 'operator': 'eq', 'value': 1}],
                         target_columns=['id_first', 'id_second', 'id_first'])

    def test_08_target_bracket_escaping_and_value_parameterization(self):
        val = "V8'; DROP TABLE dbo.X;--"
        report, cur = self.collect([{'column': 'target]value', 'operator': 'eq',
                                     'value': val}], rows=[('A', 1, 2)])
        sql, params = cur.calls[-2]
        self.assertIn('t.[target]]value] = ?', sql)
        self.assertNotIn(val, sql)
        self.assertEqual(params, (val,))
        self.assertEqual(report['target_filter_clauses_original_values'][0]['value'], val)

    def test_09_bad_empty_duplicate_or_raw_sql_target_filter_rejected(self):
        invalid = ([], [{'column': 'id_first', 'operator': 'OR 1=1', 'value': 1}],
                   [{'column': 'id_first', 'operator': 'eq', 'value': 1}]*2,
                   [{'column': 'id_first', 'operator': 'eq', 'value': None}],
                   [{'column': 'id_first', 'operator': 'eq', 'value': 1.2}])
        for clauses in invalid:
            with self.subTest(clauses=repr(clauses)[:35]):
                cursor = TargetFilteringCursor()
                db = Connection(cursor)
                with self.assertRaises(probe.OriginalFKSQLProbeError):
                    probe.capture('CarCom', 'dbo', 'T136_InitHw_Profile',
                                  'FK_Profile ОРИГИНАЛ', dsn='VIDA_RO',
                                  target_filters=clauses, connector=lambda *_a, **_kw: db)
                self.assertTrue(db.closed)
                self.assertEqual(len(cursor.calls), 2)

    def test_10_binary_and_decimal_target_filters_keep_types(self):
        opts = [({'format': 'decimal-text', 'value': '12.3400'}, Decimal('12.3400')),
                ({'format': 'binary-base64', 'value': 'AP8='}, bytes([0, 255]))]
        for encoded, expected in opts:
            with self.subTest(type=encoded['format']):
                _, cur = self.collect([{'column': 'profile_identifier', 'operator': 'eq',
                                        'value': encoded}], rows=[('A', 1, 2)])
                self.assertEqual(cur.calls[-2][1], (expected,))

    def test_11_unfiltered_source_scans_with_target_condition_are_explicit(self):
        result, _ = self.collect([{'column': 'profile_identifier',
                                  'operator': 'eq', 'value': 'XC90'}])
        self.assertTrue(result['source_complete_within_row_limit'])
        self.assertNotIn('source_selection_scope', result)
        self.assertIn('target_filter_scope', result)
        self.assertFalse(result['vida_runtime_selected_profile_verified'])

    def test_12_target_filter_unsupported_status_fails_closed(self):
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'invalid SQL FK status'):
            self.collect([{'column': 'id_first', 'operator': 'eq', 'value': 1}],
                         rows=[('A', 1, 3)])
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'invalid SQL FK status'):
            self.collect(None, rows=[('A', 1, 2)])

    def test_13_cli_uses_original_owner_local_target_filter_without_echo(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            filt, out = root/'target-original.json', root/'result.json'
            secret = 'XC90 V8 НЕ_МАСКИРОВАТЬ'
            filt.write_text(json.dumps({'schema_version': reader.FILTER_SCHEMA,
                'clauses':[{'column':'profile_identifier','operator':'eq',
                            'value':secret}]}, ensure_ascii=False), encoding='utf-8')
            original = probe.capture
            def stub(*args, **kwargs):
                self.assertEqual(kwargs['target_filters'][0]['value'], secret)
                cur = TargetFilteringCursor(rows=[('XC90 V8', 1, 2)])
                return original(*args, dsn='VIDA_RO', max_rows=5,
                                target_filters=kwargs['target_filters'],
                                connector=lambda *_a, **_kw: Connection(cur))
            argv = ['--database', 'CarCom', '--schema', 'dbo',
                    '--table', 'T136_InitHw_Profile', '--foreign-key', 'FK_Profile ОРИГИНАЛ',
                    '--target-filters-json', str(filt), '--output', str(out)]
            with patch.object(probe, 'capture', side_effect=stub), \
                 contextlib.redirect_stdout(io.StringIO()) as stdout, \
                 contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(probe.main(argv), 0)
                self.assertEqual(probe.main(argv), 2)
            self.assertIn(secret, out.read_text(encoding='utf-8'))
            self.assertNotIn(secret, stdout.getvalue()+stderr.getvalue())
            self.assertFalse(json.loads(out.read_text())['vida_runtime_selected_profile_verified'])

    def test_14_alias_and_symlink_target_filters_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            filt = root/'target.json'
            filt.write_text(json.dumps({'schema_version': reader.FILTER_SCHEMA,
                'clauses': [{'column': 'id_first', 'operator': 'is_null'}]}))
            base = ['--database','CarCom','--schema','dbo','--table','T136_InitHw_Profile',
                    '--foreign-key','FK_Profile ОРИГИНАЛ','--target-filters-json',str(filt)]
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(probe.main(base+['--output',str(filt)]), 2)
            link = root/'target-link.json'
            try: link.symlink_to(filt)
            except OSError: self.skipTest('symlinks not supported')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(probe.main(base[:-1]+[str(link), '--output',
                                                   str(root/'failed.json')]), 2)
            self.assertFalse((root/'failed.json').exists())

    def test_15_source_and_target_filter_files_must_be_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            filt = root/'same.json'
            filt.write_text(json.dumps({'schema_version': reader.FILTER_SCHEMA,
                'clauses': [{'column': 'fk_second', 'operator': 'is_null'}]}))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(probe.main(['--database','CarCom','--schema','dbo',
                    '--table','T136_InitHw_Profile','--foreign-key','FK_Profile ОРИГИНАЛ',
                    '--filters-json',str(filt),'--target-filters-json',str(filt),
                    '--output',str(root/'result.json')]), 2)

    def test_16_source_key_values_and_fk_names_remain_original(self):
        report, _ = self.collect([{'column': 'profile_identifier',
                                  'operator': 'eq', 'value': 'Вольво'}],
                                 rows=[('Адаптер Дайс', 900, 2)])
        self.assertEqual(report['original_fk_metadata']['fk_name'], 'FK_Profile ОРИГИНАЛ')
        self.assertEqual(report['sql_exists_target_filter_matches'][0]['original_source_key_values'],
                         ['Адаптер Дайс', 900])
        self.assertIn('Вольво', json.dumps(report, ensure_ascii=False))
        self.assertFalse(report['getscript_readvin_runtime_verified'])
        self.assertFalse(report['client_vin_accepted'])
        self.assertFalse(report['physical_j2534_verified'])


if __name__ == '__main__':
    unittest.main()
