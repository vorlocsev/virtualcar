"""Synthetic owner-local unique target profile selection; no original VIDA DB."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from test_vida_original_fk_sql_target_filtered import TargetFilteringCursor, Connection
import vida_original_fk_sql_probe as probe
import vida_original_table_reader as reader


class UniqueTargetCursor(TargetFilteringCursor):
    def __init__(self, *, selected_rows=None, selected_cols=None, **kwargs):
        super().__init__(**kwargs)
        self.selected_rows = ([('XC90 ОРИГИНАЛ', 88)] if selected_rows is None
                              else selected_rows)
        self.selected_cols = (['id_first', 'id_second'] if selected_cols is None
                              else selected_cols)

    def execute(self, sql, *params):
        if sql.startswith('SELECT TOP (2) ') and 'FROM [dbo].[T161_Profile] AS t WHERE' in sql:
            self.calls.append((sql, params))
            self.remaining = list(self.selected_rows)
            self.description = [(col,) for col in self.selected_cols]
            return self
        return super().execute(sql, *params)


class UnambiguousProfileTargetTests(unittest.TestCase):
    TARGET_FILTER = [{'column': 'profile_identifier', 'operator': 'eq',
                      'value': 'Вольво XC90 V8'}]

    def probe(self, *, target_filters=None, source_filters=None, **cursor_kw):
        c = UniqueTargetCursor(**cursor_kw)
        conn = Connection(c)
        report = probe.capture('CarCom', 'dbo', 'T136_InitHw_Profile',
                               'FK_Profile ОРИГИНАЛ', dsn='VIDA_RO', max_rows=5,
                               target_filters=target_filters if target_filters is not None else self.TARGET_FILTER,
                               filters=source_filters, require_unique_target=True,
                               connector=lambda *_a, **_kw: conn)
        self.assertTrue(conn.closed)
        return report, c

    def test_01_single_target_returns_original_full_composite_key(self):
        result, cursor = self.probe()
        self.assertTrue(result['target_unique_selector_checked'])
        self.assertEqual(result['target_unique_row_count_at_probe'], 1)
        self.assertEqual(result['selected_target_original_key_values'], ['XC90 ОРИГИНАЛ', 88])
        self.assertTrue(result['target_key_selected_at_query_time_only'])
        self.assertFalse(result['transactional_snapshot_verified'])
        self.assertFalse(result['vida_runtime_selected_profile_verified'])
        self.assertEqual(result['original_fk_metadata']['fk_name'], 'FK_Profile ОРИГИНАЛ')
        self.assertEqual(len(cursor.calls), 6)  # DB, FK, target schema, unique, row scan, FK

    def test_02_zero_matches_rejected_without_scanning_source(self):
        conn = Connection(UniqueTargetCursor(selected_rows=[]))
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'exactly one row'):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO', require_unique_target=True,
                          target_filters=self.TARGET_FILTER,connector=lambda *_a, **_k: conn)
        self.assertTrue(conn.closed)
        self.assertEqual(len(conn.cur.calls),4)

    def test_03_multiple_target_rows_rejected_even_matching_original_values(self):
        dup = [('XC90 ОРИГИНАЛ', 88), ('XC90 ОРИГИНАЛ', 89)]
        conn = Connection(UniqueTargetCursor(selected_rows=dup))
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'exactly one row'):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO', require_unique_target=True,
                          target_filters=self.TARGET_FILTER,connector=lambda *_a, **_k: conn)
        self.assertTrue(conn.closed)
        self.assertEqual(len(conn.cur.calls),4)

    def test_04_null_target_fk_key_not_a_valid_selected_key(self):
        conn=Connection(UniqueTargetCursor(selected_rows=[(None,88)]))
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'contains NULL'):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO',require_unique_target=True,
                          target_filters=self.TARGET_FILTER,connector=lambda *_a,**_k:conn)

    def test_05_incorrect_projection_metadata_rejected(self):
        conn=Connection(UniqueTargetCursor(selected_cols=['id_second','id_first']))
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'projection changed'):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO',require_unique_target=True,
                          target_filters=self.TARGET_FILTER,connector=lambda *_a,**_k:conn)

    def test_06_unique_switch_requires_target_filter_and_bool(self):
        for filters, flag in ((None, True), (self.TARGET_FILTER, 'yes'),
                              (self.TARGET_FILTER, 1)):
            with self.subTest(flag=flag), self.assertRaises(probe.OriginalFKSQLProbeError):
                probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                              dsn='VIDA_RO',require_unique_target=flag,
                              target_filters=filters,
                              connector=lambda *_a,**_k:self.fail('connector invoked'))

    def test_07_unique_target_select_is_parameterized_and_does_not_expose_in_sql(self):
        secret = "Реальный V8'; DROP TABLE dbo.Cars;--"
        filt = [{'column':'profile_identifier','operator':'eq','value':secret}]
        result,cursor = self.probe(target_filters=filt)
        sql,params = cursor.calls[3]
        self.assertIn('SELECT TOP (2) t.[id_first], t.[id_second]',sql)
        self.assertIn('WHERE t.[profile_identifier] = ?',sql)
        self.assertNotIn(secret,sql)
        self.assertEqual(params,(secret,))
        self.assertEqual(result['target_filter_clauses_original_values'][0]['value'],secret)

    def test_08_source_filter_parameters_remain_correctly_ordered(self):
        source = [{'column':'optional_col','operator':'eq','value':'Кузов'}]
        result,cursor = self.probe(source_filters=source)
        self.assertEqual(cursor.calls[5][1], ('Вольво XC90 V8','Кузов'))
        self.assertEqual(cursor.calls[4][1], ('Вольво XC90 V8',))
        self.assertFalse(result['source_complete_within_row_limit'])
        self.assertEqual(result['selected_target_original_key_values'][1],88)

    def test_09_target_is_null_query_does_not_bind_parameter(self):
        filters = [{'column':'profile_identifier','operator':'is_null'}]
        result,cursor = self.probe(target_filters=filters)
        self.assertEqual(cursor.calls[3][1], ())
        self.assertIn('t.[profile_identifier] IS NULL',cursor.calls[3][0])
        self.assertIn('t.[profile_identifier] IS NULL',cursor.calls[4][0])

    def test_10_no_matching_source_records_does_not_invalidate_selected_profile(self):
        result, _ = self.probe(rows=[])
        self.assertEqual(result['source_rows_examined'],0)
        self.assertEqual(result['target_unique_row_count_at_probe'],1)
        self.assertEqual(result['sql_exists_matches'],[])
        self.assertFalse(result['selected_ecu_profile_verified'] if 'selected_ecu_profile_verified' in result else result['vida_runtime_selected_profile_verified'])

    def test_11_binary_target_key_retains_exact_bytes_in_base64(self):
        result,_=self.probe(selected_rows=[(bytes([0,255]),88)])
        self.assertEqual(result['selected_target_original_key_values'][0],
                         {'format':'binary-base64','value':'AP8='})

    def test_12_corrupt_target_key_type_fails_closed(self):
        conn=Connection(UniqueTargetCursor(selected_rows=[(object(),88)]))
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'original SQL read failed'):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO',require_unique_target=True,
                          target_filters=self.TARGET_FILTER,connector=lambda *_a,**_k:conn)
        self.assertTrue(conn.closed)

    def test_13_strict_mode_does_not_change_normal_existing_path(self):
        c = UniqueTargetCursor()
        conn = Connection(c)
        result=probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                             dsn='VIDA_RO',target_filters=self.TARGET_FILTER,
                             connector=lambda *_a,**_k:conn)
        self.assertNotIn('selected_target_original_key_values',result)
        self.assertFalse(any('SELECT TOP (2)' in statement for statement,_ in c.calls))
        self.assertEqual(len(c.calls),5)

    def test_14_cli_owner_local_output_original_key_and_no_stdout_echo(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            filt=root/'original.json'; out=root/'result.json'
            filt.write_text(json.dumps({'schema_version':reader.FILTER_SCHEMA,
                'clauses':self.TARGET_FILTER},ensure_ascii=False),encoding='utf-8')
            real_capture=probe.capture
            def stub(*args,**kwargs):
                self.assertTrue(kwargs['require_unique_target'])
                cur=UniqueTargetCursor()
                return real_capture(*args,dsn='VIDA_RO',max_rows=5,
                                    target_filters=kwargs['target_filters'],
                                    require_unique_target=True,
                                    connector=lambda *_a,**_k:Connection(cur))
            args=['--database','CarCom','--schema','dbo','--table','T136_InitHw_Profile',
                  '--foreign-key','FK_Profile ОРИГИНАЛ','--target-filters-json',str(filt),
                  '--require-unique-target','--output',str(out)]
            with patch.object(probe,'capture',side_effect=stub), \
                 contextlib.redirect_stdout(io.StringIO()) as stdout, \
                 contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(probe.main(args),0)
                self.assertEqual(probe.main(args),2)
            self.assertEqual(json.loads(out.read_text())['selected_target_original_key_values'],
                             ['XC90 ОРИГИНАЛ',88])
            self.assertNotIn('XC90 ОРИГИНАЛ',stdout.getvalue()+stderr.getvalue())
            self.assertNotIn('Вольво XC90 V8',stdout.getvalue()+stderr.getvalue())

    def test_15_cli_strict_requires_target_filter_file(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'never.json'
            args=['--database','CarCom','--schema','dbo','--table','T136_InitHw_Profile',
                  '--foreign-key','FK_Profile ОРИГИНАЛ', '--require-unique-target',
                  '--output',str(out)]
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(probe.main(args),2)
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
