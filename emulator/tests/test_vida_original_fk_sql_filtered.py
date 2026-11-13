"""Synthetic-only native SQL FK probe restricted to original source-profile rows."""
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
from test_vida_original_fk_sql_probe import Cursor, Connection, FK, VALUES
import vida_original_fk_sql_probe as probe
import vida_original_table_reader as row_reader


class FilteringCursor(Cursor):
    def __init__(self, *, source_columns=None, **kwargs):
        super().__init__(**kwargs)
        self.source_columns = (source_columns if source_columns is not None
                               else ['fk]first', 'fk_second', 'profile_identifier', 'optional_col'])

    def execute(self, sql, *params):
        if sql == probe.FILTER_COLUMNS_SQL:
            self.calls.append((sql, params))
            self.remaining = [(name,) for name in self.source_columns]
            return self
        return super().execute(sql, *params)


class OriginalFKFilteredProbeTests(unittest.TestCase):
    def capture(self, filters, **kwargs):
        cursor = FilteringCursor(**kwargs)
        connection = Connection(cursor)
        result = probe.capture('CarCom', 'dbo', 'T136_InitHw_Profile',
                               'FK_Profile ОРИГИНАЛ', dsn='VIDA_RO', max_rows=5,
                               filters=filters, connector=lambda *_a, **_kw: connection)
        self.assertTrue(connection.closed)
        return result, cursor

    def test_01_original_unicode_filter_values_bound_not_in_sql(self):
        value = "XC90'; DROP TABLE dbo.X;-- Модель"
        result, cursor = self.capture([{'column':'profile_identifier', 'operator':'eq', 'value':value}])
        sql, params = cursor.calls[3]
        self.assertEqual(params, (value,))
        self.assertIn('FROM [dbo].[T136_InitHw_Profile] AS s WHERE s.[profile_identifier] = ?', sql)
        self.assertNotIn(value, sql)
        self.assertEqual(result['original_filter_clauses'][0]['value'], value)
        self.assertEqual(result['source_selection_scope'], 'filtered_subset_only')
        self.assertFalse(result['source_complete_within_row_limit'])
        self.assertTrue(result['filtered_source_subset_complete_within_row_limit'])
        self.assertFalse(result['full_source_table_row_count_verified'])
        self.assertFalse(result['selected_ecu_profile_verified'])
        self.assertEqual(len(cursor.calls), 5)

    def test_02_filter_can_reference_non_fk_column_confirmed_by_catalog(self):
        result, cursor = self.capture([{'column':'optional_col','operator':'is_null'}])
        sql, params = cursor.calls[3]
        self.assertIn('WHERE s.[optional_col] IS NULL', sql)
        self.assertEqual(params, ())
        self.assertEqual(result['original_filter_clauses'],
                         [{'column':'optional_col','operator':'is_null'}])

    def test_03_two_filters_keep_original_typed_values_and_parameter_order(self):
        criteria = [{'column':'fk]first','operator':'eq','value':'XC90 V8'},
                    {'column':'fk_second','operator':'eq',
                     'value':{'format':'decimal-text','value':'12.3400'}}]
        result, cursor = self.capture(criteria)
        sql, params = cursor.calls[3]
        self.assertIn('WHERE s.[fk]]first] = ? AND s.[fk_second] = ?', sql)
        self.assertEqual(params, ('XC90 V8', Decimal('12.3400')))
        self.assertEqual(result['original_filter_clauses'], criteria)
        self.assertEqual(result['sql_exists_matches'][0]['original_source_key_values'],
                         ['XC90 V8 / ИНДЕКС', 7])

    def test_04_missing_filter_column_rejected_before_selecting_user_rows(self):
        cur = FilteringCursor(source_columns=['fk]first','fk_second'])
        db = Connection(cur)
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'absent from SQL catalog'):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO', filters=[{'column':'private_missing',
                                                    'operator':'eq','value':'A'}],
                          connector=lambda *_a, **_kw: db)
        self.assertEqual(len(cur.calls), 3)
        self.assertTrue(db.closed)

    def test_05_catalog_drift_missing_fk_column_fails_closed(self):
        cur = FilteringCursor(source_columns=['fk]first','profile_identifier'])
        db = Connection(cur)
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'inconsistent source column'):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO',filters=[{'column':'profile_identifier',
                                                  'operator':'eq','value':'A'}],
                          connector=lambda *_a, **_kw: db)
        self.assertEqual(len(cur.calls), 3)

    def test_06_duplicate_catalog_columns_rejected(self):
        cur = FilteringCursor(source_columns=['fk]first','fk_second','fk_second'])
        db = Connection(cur)
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'inconsistent source column'):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO', filters=[{'column':'fk_second','operator':'eq','value':3}],
                          connector=lambda *_a, **_kw: db)

    def test_07_case_mismatch_is_not_silent_aliasing(self):
        with self.assertRaises(probe.OriginalFKSQLProbeError):
            self.capture([{'column':'PROFILE_IDENTIFIER','operator':'eq','value':'XC90'}])

    def test_08_typed_binary_filter_stays_parameterized(self):
        criteria = [{'column':'profile_identifier','operator':'eq',
                     'value':{'format':'binary-base64','value':'AP8='}}]
        report, cur = self.capture(criteria)
        self.assertEqual(cur.calls[3][1], (bytes([0,255]),))
        self.assertEqual(report['original_filter_clauses'],criteria)

    def test_09_malformed_empty_or_sql_operator_injection_rejected(self):
        invalid = ([], [{'column':'fk_second','operator':'OR 1=1','value':'x'}],
                   [{'column':'fk_second','operator':'eq','value':None}],
                   [{'column':'fk_second','operator':'eq','value':5.5}],
                   [{'column':'fk_second','operator':'eq','value':'A'}]*2,
                   [{'column':'fk_second','operator':'eq','value':'A'}]*5)
        for clauses in invalid:
            with self.subTest(clauses=str(clauses)[:40]):
                cur = FilteringCursor()
                db = Connection(cur)
                with self.assertRaises(probe.OriginalFKSQLProbeError):
                    probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                                  dsn='VIDA_RO', filters=clauses,
                                  connector=lambda *_a, **_kw: db)
                self.assertTrue(db.closed)
                self.assertEqual(len(cur.calls),2) # verified identity and FK before filters

    def test_10_filtered_row_overflow_fails_no_partial_success(self):
        cur = FilteringCursor(rows=VALUES*3)
        db = Connection(cur)
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'bounded row limit'):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO', max_rows=5,
                          filters=[{'column':'profile_identifier','operator':'eq','value':'X'}],
                          connector=lambda *_a, **_kw: db)
        self.assertTrue(db.closed)

    def test_11_original_fk_metadata_and_non_runtime_claims_unchanged(self):
        report, _ = self.capture([{'column':'profile_identifier','operator':'eq','value':'XC90'}])
        self.assertEqual(report['original_fk_metadata']['fk_name'],'FK_Profile ОРИГИНАЛ')
        self.assertFalse(report['transactional_snapshot_verified'])
        self.assertFalse(report['getscript_readvin_runtime_verified'])
        self.assertFalse(report['client_vin_accepted'])
        self.assertFalse(report['physical_j2534_verified'])
        self.assertEqual(report['sql_exists_unmatched'][0]['original_source_key_values'],['НЕ НАЙДЕНО',8])

    def test_12_unfiltered_legacy_query_and_report_unchanged(self):
        result, cursor = self.capture(None)
        self.assertEqual(len(cursor.calls),4)
        self.assertNotIn(' WHERE s.',cursor.calls[2][0])
        self.assertTrue(result['source_complete_within_row_limit'])
        self.assertNotIn('original_filter_clauses',result)
        self.assertNotIn('source_selection_scope',result)

    def test_13_main_cli_uses_original_private_json_with_no_value_echo(self):
        with tempfile.TemporaryDirectory() as folder:
            private = Path(folder)
            config = private/'profile.json'
            result = private/'probe.json'
            secret = "XC90 PRIV_НЕ_МАСКИРОВАТЬ"
            config.write_text(json.dumps({'schema_version':row_reader.FILTER_SCHEMA,
                'clauses':[{'column':'profile_identifier','operator':'eq','value':secret}]}),
                encoding='utf-8')
            real_capture = probe.capture
            def fake_capture(*args, **kwargs):
                self.assertEqual(kwargs['filters'][0]['value'], secret)
                cursor = FilteringCursor()
                db = Connection(cursor)
                return real_capture(*args, dsn='VIDA_RO', max_rows=5,
                                    filters=kwargs['filters'],
                                    connector=lambda *_a, **_kw: db)
            with patch.object(probe,'capture',side_effect=fake_capture), \
                 contextlib.redirect_stdout(io.StringIO()) as stdout, \
                 contextlib.redirect_stderr(io.StringIO()) as stderr:
                argv=['--database','CarCom','--schema','dbo','--table','T136_InitHw_Profile',
                      '--foreign-key','FK_Profile ОРИГИНАЛ', '--filters-json',str(config),
                      '--output',str(result)]
                self.assertEqual(probe.main(argv),0)
                self.assertEqual(probe.main(argv),2)
            self.assertIn(secret,result.read_text(encoding='utf-8'))
            self.assertNotIn(secret,stdout.getvalue()+stderr.getvalue())
            self.assertTrue(result.exists())
            if sys.platform!='win32':
                self.assertEqual(result.stat().st_mode & 0o777,0o600)

    def test_14_invalid_json_source_fails_without_creating_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            filt=root/'invalid.json'; out=root/'out.json'
            filt.write_text('{"a":1,"a":2}',encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()):
                code=probe.main(['--database','CarCom','--schema','dbo',
                         '--table','T136_InitHw_Profile','--foreign-key','FK_Profile ОРИГИНАЛ',
                         '--filters-json',str(filt),'--output',str(out)])
            self.assertEqual(code,2)
            self.assertFalse(out.exists())

    def test_15_filters_json_output_alias_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            filt=root/'f.json'
            filt.write_text('{"schema_version":"'+row_reader.FILTER_SCHEMA+\
                '","clauses":[{"column":"fk_second","operator":"is_null"}]}')
            with contextlib.redirect_stderr(io.StringIO()):
                result=probe.main(['--database','CarCom','--schema','dbo',
                         '--table','T136_InitHw_Profile','--foreign-key','FK_Profile ОРИГИНАЛ',
                         '--filters-json',str(filt),'--output',str(filt)])
            self.assertEqual(result,2)
            linked=root/'link.json'
            try:
                linked.symlink_to(filt)
            except OSError:
                self.skipTest('symlinks unsupported')
            with self.assertRaises(row_reader.OriginalCaptureError):
                row_reader._load_filters(linked)

    def test_16_bracket_escaped_catalog_column_not_executable_sql(self):
        original="X'; DELETE FROM dbo.Users;--"
        value = "VIN' UNION SELECT * FROM private"
        _, cur = self.capture([{'column':original,'operator':'eq','value':value}],
                              source_columns=['fk]first','fk_second',original])
        sql,params=cur.calls[3]
        self.assertIn('s.[X\'; DELETE FROM dbo.Users;--] = ?',sql)
        self.assertEqual(params,(value,))
        self.assertNotIn(value,sql)


if __name__=='__main__':
    unittest.main()
