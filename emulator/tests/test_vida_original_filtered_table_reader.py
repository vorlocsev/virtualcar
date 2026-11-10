"""Synthetic tests for precise, unmasked, parameter-bound VIDA row selection."""
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
from test_vida_original_table_reader import Cursor, Connection
import vida_original_table_reader as reader
import vida_original_fk_value_audit as fk_audit


class FilteredVIDAReaderTests(unittest.TestCase):
    def collect(self, clauses, *, cols=None, rows=None, max_rows=5):
        cur = Cursor(rows if rows is not None else [('XC90 V8', b'\x00\xff')], cols=cols)
        db = Connection(cur)
        report = reader.capture('CarCom', 'dbo', 'T161_Profile',
                                dsn='VIDA_RO', filters=clauses,
                                connector=lambda *_a, **_k: db,
                                max_rows=max_rows)
        self.assertTrue(db.closed)
        return report, cur

    def test_01_unmasked_unicode_eq_parameter_without_sql_interpolation(self):
        original = 'XC90 V8 / Проба; UID=sa'
        clauses = [{'column': 'identifier', 'operator': 'eq', 'value': original}]
        result, cursor = self.collect(clauses, rows=[(original, b'\x10')])
        sql, params = cursor.queries[-1], cursor.args[-1]
        self.assertEqual(params, (original,))
        self.assertIn('WHERE [identifier] = ?', sql)
        self.assertNotIn(original, sql)
        self.assertEqual(result['selection_clauses_original_values'][0]['value'], original)
        self.assertEqual(result['rows'][0][0], original)
        self.assertEqual(result['rows'][0][1], {'format':'binary-base64','value':'EA=='})
        self.assertFalse(result['full_table_extracted_within_row_limit'])
        self.assertTrue(result['filtered_subset_complete_within_row_limit'])
        self.assertFalse(result['full_table_row_count_verified'])

    def test_02_two_eq_and_null_operator_without_freeform_sql(self):
        clauses = [
            {'column': 'identifier','operator':'eq','value':'VIN_TEST'},
            {'column': 'original_value','operator':'is_null'}]
        report, cur = self.collect(clauses, rows=[('VIN_TEST', None)])
        self.assertEqual(cur.args[-1], ('VIN_TEST',))
        self.assertIn('WHERE [identifier] = ? AND [original_value] IS NULL', cur.queries[-1])
        self.assertEqual(report['rows'], [['VIN_TEST',None]])
        self.assertEqual(report['selection_scope'], 'filtered_subset_only')

    def test_03_sql_identifier_requires_actual_catalog_column(self):
        cursor = Cursor([('A',b'1')])
        db = Connection(cursor)
        with self.assertRaisesRegex(reader.OriginalCaptureError,'absent from SQL catalog'):
            reader.capture('CarCom','dbo','T161_Profile',dsn='VIDA_RO',
                           filters=[{'column':'NOT_A_REAL_COLUMN','operator':'eq','value':'A'}],
                           connector=lambda *_a,**_k:db)
        self.assertTrue(db.closed)
        self.assertEqual(len(cursor.queries),2)  # identity, metadata; no user table SQL

    def test_04_catalog_confirmed_quoted_identifier_is_escaped(self):
        col = 'profile]; EXEC sp_executesql'
        cols = [(1,col,'nvarchar'),(2,'original_value','varbinary')]
        report,cur=self.collect([{'column':col,'operator':'eq','value':'ok'}],cols=cols)
        self.assertIn('[profile]]; EXEC sp_executesql] = ?',cur.queries[-1])
        self.assertEqual(cur.args[-1],('ok',))
        self.assertEqual(report['selection_clauses_original_values'][0]['column'],col)

    def test_05_reject_injected_operator_duplicate_and_empty_filters(self):
        invalid = [[],
                   [{'column':'identifier','operator':'OR 1=1','value':'x'}],
                   [{'column':'identifier','operator':'eq','value':'x'},
                    {'column':'identifier','operator':'eq','value':'y'}],
                   [{'column':'identifier','operator':'is_null','value':None}],
                   [{'column':'identifier','operator':'eq','value':None}],
                   [{'column':'identifier','operator':'eq','value':4.5}],
                   [{'column':'identifier','operator':'eq','value':2**80}],
                   [{'column':'identifier','operator':'eq','value':''}]*5]
        for clauses in invalid:
            with self.subTest(clauses=str(clauses)[:40]), self.assertRaises(reader.OriginalCaptureError):
                reader.capture('CarCom','dbo','T161_Profile',dsn='VIDA_RO',filters=clauses,
                               connector=lambda *_a,**_k:self.fail('connector invoked'))

    def test_06_typed_decimal_binary_and_guid_parameter_bindings(self):
        cases = [({'format':'decimal-text','value':'1.2300'}, Decimal('1.2300')),
                 ({'format':'binary-base64','value':'AP8='}, bytes([0,255])),
                 ({'format':'uuid-raw-hex','value':'12345678123456789abcdef012345678'},
                  '12345678-1234-5678-9abc-def012345678')]
        for value,bound in cases:
            with self.subTest(value=value['format']):
                report,cur = self.collect([{'column':'identifier','operator':'eq','value':value}])
                self.assertEqual(cur.args[-1],(bound,))
                self.assertEqual(report['selection_clauses_original_values'][0]['value'],value)

    def test_07_invalid_typed_values_fail_closed(self):
        invalid = [
            {'format':'binary-base64','value':'!!!'},
            {'format':'decimal-text','value':'NaN'},
            {'format':'decimal-text','value':'banana'},
            {'format':'uuid-raw-hex','value':'not-a-uuid'},
            {'format':'binary-base64','value':'QUJD','extra':'not allowed'},
        ]
        for val in invalid:
            with self.subTest(value=val), self.assertRaises(reader.OriginalCaptureError):
                reader._validate_filters([{'column':'identifier','operator':'eq','value':val}])

    def test_08_filter_json_preserves_unmasked_values_and_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'filter.json'
            raw={'schema_version':reader.FILTER_SCHEMA,
                 'clauses':[{'column':'identifier','operator':'eq','value':'VIN_НЕ_МАСКИРОВАТЬ'}]}
            p.write_text(json.dumps(raw,ensure_ascii=False),encoding='utf-8')
            loaded=reader._load_filters(p)
            self.assertEqual(loaded[0][0]['value'],'VIN_НЕ_МАСКИРОВАТЬ')
            p.write_text('{"schema_version":"x","schema_version":"y","clauses":[]}',encoding='utf-8')
            with self.assertRaises(reader.OriginalCaptureError):
                reader._load_filters(p)
            p.write_text('{"schema_version":"'+reader.FILTER_SCHEMA+'","clauses":[{"column":"identifier","operator":"eq","value":NaN}]}')
            with self.assertRaises(reader.OriginalCaptureError):
                reader._load_filters(p)

    def test_09_cli_original_filters_and_original_values_no_stdout(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); cfg=root/'filters.json'; out=root/'selected.json'
            cfg.write_text(json.dumps({'schema_version':reader.FILTER_SCHEMA,'clauses':[
                {'column':'identifier','operator':'eq','value':'SECRET_VIN_NO_MASK'}]}))
            fake=[('SECRET_VIN_NO_MASK', b'123')]
            real_capture = reader.capture
            def simulate(database,schema,table,*,dsn,max_rows,filters):
                self.assertEqual(filters[0]['value'],'SECRET_VIN_NO_MASK')
                db = Connection(Cursor(fake))
                result = real_capture(database, schema, table, dsn='VIDA_RO',
                                      max_rows=max_rows, filters=filters,
                                      connector=lambda *_a, **_k: db)
                self.assertTrue(db.closed)
                return result
            argv=['--database','CarCom','--schema','dbo','--table','T161_Profile',
                  '--filters-json',str(cfg),'--output',str(out)]
            with patch.object(reader,'capture',side_effect=simulate), \
                 contextlib.redirect_stdout(io.StringIO()) as stdout, \
                 contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(reader.main(argv),0)
                self.assertEqual(reader.main(argv),2)
            self.assertIn('SECRET_VIN_NO_MASK',out.read_text())
            self.assertNotIn('SECRET_VIN_NO_MASK',stdout.getvalue()+stderr.getvalue())
            self.assertEqual(json.loads(out.read_text())['full_table_extracted_within_row_limit'],False)
            if sys.platform!='win32':
                self.assertEqual(out.stat().st_mode & 0o777,0o600)

    def test_10_filter_path_alias_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); cfg=root/'filter.json'
            cfg.write_text(json.dumps({'schema_version':reader.FILTER_SCHEMA,'clauses':[
                {'column':'identifier','operator':'is_null'}]}))
            base=['--database','CarCom','--schema','dbo','--table','T161_Profile',
                  '--filters-json',str(cfg),'--output',str(cfg)]
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(reader.main(base),2)
            saved=cfg.read_bytes()
            self.assertEqual(cfg.read_bytes(),saved)
            link=root/'link.json'
            try:
                link.symlink_to(cfg)
            except OSError:
                self.skipTest('symlinks unsupported')
            with self.assertRaises(reader.OriginalCaptureError):
                reader._load_filters(link)

    def test_11_filtered_subset_limit_fails_without_claiming_complete(self):
        cur=Cursor([('A',b'0'),('A',b'1'),('A',b'2')])
        db=Connection(cur)
        with self.assertRaisesRegex(reader.OriginalCaptureError,'row limit'):
            reader.capture('CarCom','dbo','T161_Profile',dsn='VIDA_RO',max_rows=2,
                           filters=[{'column':'identifier','operator':'eq','value':'A'}],
                           connector=lambda *_a,**_k:db)
        self.assertTrue(db.closed)

    def test_12_legacy_unfiltered_full_table_claim_unchanged(self):
        report,cur=self.collect(None)
        self.assertTrue(report['full_table_extracted_within_row_limit'])
        self.assertNotIn('selection_scope',report)
        self.assertNotIn('WHERE',cur.queries[-1])
        self.assertEqual(cur.args[-1],())

    def test_13_filtered_subset_is_rejected_by_full_table_fk_audit(self):
        report,_=self.collect([{'column':'identifier','operator':'eq','value':'X'}])
        with self.assertRaises(fk_audit.OriginalFKError):
            fk_audit._table_capture(report,{'source_database':'CarCom'},
                {('dbo','T161_Profile'):{'identifier':{'column_id':1,'sql_type':'nvarchar'},
                                        'original_value':{'column_id':2,'sql_type':'varbinary'}}})

    def test_14_text_value_contains_sql_comment_but_is_only_a_parameter(self):
        value="one'; DROP TABLE dbo.T161_Profile;--"
        report,cur=self.collect([{'column':'identifier','operator':'eq','value':value}])
        self.assertNotIn(value,cur.queries[-1])
        self.assertEqual(cur.args[-1],(value,))
        self.assertEqual(report['selection_clauses_original_values'][0]['value'],value)


if __name__ == '__main__':
    unittest.main()
