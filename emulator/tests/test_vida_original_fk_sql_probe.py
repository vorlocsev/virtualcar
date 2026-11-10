"""Synthetic SQL Server native EXISTS checks with original VIDA key values intact."""
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
import vida_original_fk_sql_probe as probe

FK = [
    (101, 'FK_Profile ОРИГИНАЛ', 1, 'dbo', 'T136_InitHw_Profile', 'fk]first',
     'dbo', 'T161_Profile', 'id_first', False, True, 2),
    (101, 'FK_Profile ОРИГИНАЛ', 2, 'dbo', 'T136_InitHw_Profile', 'fk_second',
     'dbo', 'T161_Profile', 'id_second', False, True, 2),
]
VALUES = [('XC90 V8 / ИНДЕКС', 7, 1), ('НЕ НАЙДЕНО', 8, 0), (None, 9, -1)]


class Cursor:
    def __init__(self, *, fk=None, rows=None, changed=None, chunk=1, database='CarCom',
                 col_names=None):
        self.fk = list(FK if fk is None else fk)
        self.changed = changed
        self.rows = list(VALUES if rows is None else rows)
        self.chunk = chunk
        self.database = database
        self.col_names = col_names
        self.remaining = []
        self.description = None
        self.calls = []
        self.metadata_reads = 0

    def execute(self, sql, *params):
        self.calls.append((sql, params))
        if sql == 'SELECT DB_NAME()':
            self.remaining = [(self.database,)]
        elif sql == probe.FK_SQL:
            self.metadata_reads += 1
            self.remaining = list(self.fk if self.metadata_reads == 1 or self.changed is None
                                  else self.changed)
        elif sql.startswith('SELECT TOP ('):
            self.remaining = list(self.rows)
            names = ['fk]first', 'fk_second', probe.STATUS_ALIAS]
            self.description = [(x,) for x in (self.col_names or names)]
        else:
            raise AssertionError('unexpected SQL')
        return self

    def fetchmany(self, n):
        count = min(n, self.chunk)
        result, self.remaining = self.remaining[:count], self.remaining[count:]
        return result


class Connection:
    def __init__(self, cursor):
        self.cur = cursor
        self.closed = False
        self.timeout = None

    def cursor(self):
        return self.cur

    def close(self):
        self.closed = True


class LiveSQLProbeTests(unittest.TestCase):
    def run_probe(self, **options):
        cursor = Cursor(**options)
        db = Connection(cursor)
        result = probe.capture('CarCom', 'dbo', 'T136_InitHw_Profile',
                               'FK_Profile ОРИГИНАЛ', dsn='VIDA_RO',
                               max_rows=5, connector=lambda *_args, **_kwargs: db)
        self.assertTrue(db.closed)
        return result, cursor

    def test_01_native_sql_exists_preserves_unmasked_names_and_values(self):
        report, cursor = self.run_probe()
        self.assertEqual(report['source_database'], 'CarCom')
        self.assertEqual(report['original_fk_metadata']['fk_name'], 'FK_Profile ОРИГИНАЛ')
        self.assertTrue(report['original_fk_metadata']['is_not_trusted'])
        self.assertEqual(report['sql_exists_matches'][0]['original_source_key_values'],
                         ['XC90 V8 / ИНДЕКС', 7])
        self.assertEqual(report['sql_exists_unmatched'][0]['original_source_key_values'],
                         ['НЕ НАЙДЕНО', 8])
        self.assertEqual(report['sql_null_key_rows'][0]['original_source_key_values'],
                         [None, 9])
        self.assertEqual(len(cursor.calls), 4)
        sql, params = cursor.calls[2]
        self.assertIn('EXISTS (SELECT 1', sql)
        self.assertIn('s.[fk]]first]', sql)
        self.assertIn('t.[id_first] = s.[fk]]first]', sql)
        self.assertTrue(report['native_sql_server_exists_evaluated'])
        self.assertFalse(report['transactional_snapshot_verified'])
        self.assertFalse(report['client_vin_accepted'])
        self.assertFalse(report['physical_j2534_verified'])
        self.assertNotIn('VIDA_RO', json.dumps(report, ensure_ascii=False))
        self.assertEqual(cursor.calls[1][1], ('dbo', 'T136_InitHw_Profile', 'FK_Profile ОРИГИНАЛ'))

    def test_02_out_of_order_complete_composite_fk_accepted(self):
        report, _ = self.run_probe(fk=FK[::-1])
        self.assertEqual([c['ordinal'] for c in report['original_fk_metadata']['columns']], [1, 2])

    def test_03_truncated_trailing_composite_fk_member_rejected(self):
        db = Connection(Cursor(fk=[FK[0]]))
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'incomplete'):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO',connector=lambda *_a, **_kw: db)
        self.assertTrue(db.closed)

    def test_04_unknown_or_mismatched_fk_rejected(self):
        for records in ([], [FK[0], FK[1][:1] + ('Other',) + FK[1][2:]]):
            db = Connection(Cursor(fk=records))
            with self.assertRaises(probe.OriginalFKSQLProbeError):
                probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                              dsn='VIDA_RO',connector=lambda *_a, **_kw: db)
            self.assertTrue(db.closed)

    def test_05_changed_fk_after_sql_read_fails_closed(self):
        db = Connection(Cursor(changed=[FK[0][:-3] + (True, True, 2), FK[1][:-3] + (True, True, 2)]))
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'changed'):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO',connector=lambda *_a, **_kw: db)
        self.assertTrue(db.closed)

    def test_06_above_max_rows_fails_not_partial_positive(self):
        db = Connection(Cursor(rows=VALUES * 3))
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'bounded row limit'):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO',max_rows=5,connector=lambda *_a, **_kw: db)
        self.assertTrue(db.closed)

    def test_07_inconsistent_projection_or_sql_status_rejected(self):
        for opts in ({'col_names':['wrong','fk_second',probe.STATUS_ALIAS]},
                     {'rows':[('A',1, True)]},
                     {'rows':[('A',1,8)]}):
            db = Connection(Cursor(**opts))
            with self.assertRaises(probe.OriginalFKSQLProbeError):
                probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                              dsn='VIDA_RO',connector=lambda *_a, **_kw: db)

    def test_08_sql_connection_options_and_dsn_are_safe(self):
        calls=[]
        db=Connection(Cursor())
        def connect(connection,**kwargs):
            calls.append((connection,kwargs))
            return db
        probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                      dsn='VIDA_RO',connector=connect)
        self.assertIn('TrustServerCertificate=No', calls[0][0])
        self.assertIn('ApplicationIntent=ReadOnly', calls[0][0])
        self.assertEqual(calls[0][1], {'autocommit':True,'timeout':8})
        for bad in ('CarCom;PWD=secret','A' * 129, None):
            with self.assertRaises(probe.OriginalFKSQLProbeError):
                probe.capture(bad,'dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                              dsn='VIDA_RO',connector=connect)
        with self.assertRaises(probe.OriginalFKSQLProbeError):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='DSN;PWD=secret',connector=connect)

    def test_09_original_decimal_binary_data_preserved_reversibly(self):
        r, _ = self.run_probe(rows=[(b'\x00\xff', Decimal('12.3400'), 1)])
        values = r['sql_exists_matches'][0]['original_source_key_values']
        self.assertEqual(values, [{'format':'binary-base64','value':'AP8='},
                                  {'format':'decimal-text','value':'12.3400'}])

    def test_10_wrong_database_identity_rejected_before_data(self):
        db=Connection(Cursor(database='DiceTiming'))
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'database identity'):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO',connector=lambda *_a, **_kw: db)
        self.assertEqual(len(db.cur.calls),1)

    def test_11_missing_or_duplicate_ordinals_rejected(self):
        for rows in ([FK[0], FK[1][:2] + (1,) + FK[1][3:]],
                     [FK[0][:2] + (2,) + FK[0][3:], FK[1][:2] + (3,) + FK[1][3:]]):
            db=Connection(Cursor(fk=rows))
            with self.assertRaises(probe.OriginalFKSQLProbeError):
                probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                              dsn='VIDA_RO',connector=lambda *_a, **_kw: db)

    def test_12_local_exclusive_output_no_raw_names_on_stdout(self):
        report, _ = self.run_probe()
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'original_fk.sql-report.json'
            with patch.object(probe,'capture',return_value=report), \
                 contextlib.redirect_stdout(io.StringIO()) as stdout, \
                 contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(probe.main(['--database','CarCom','--schema','dbo',
                    '--table','T136_InitHw_Profile','--foreign-key','FK_Profile ОРИГИНАЛ',
                    '--output',str(out)]),0)
                self.assertEqual(probe.main(['--database','CarCom','--schema','dbo',
                    '--table','T136_InitHw_Profile','--foreign-key','FK_Profile ОРИГИНАЛ',
                    '--output',str(out)]),2)
            self.assertIn('XC90 V8 / ИНДЕКС',out.read_text(encoding='utf-8'))
            self.assertNotIn('XC90 V8',stdout.getvalue())
            self.assertNotIn('XC90 V8',stderr.getvalue())
            if sys.platform!='win32':
                self.assertEqual(out.stat().st_mode & 0o777,0o600)


if __name__ == '__main__':
    unittest.main()
