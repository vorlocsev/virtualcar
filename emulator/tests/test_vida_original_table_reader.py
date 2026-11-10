"""Synthetic-only tests for fully named/value-preserving local VIDA SQL capture."""
from __future__ import annotations

import base64
import datetime
from decimal import Decimal
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch
import contextlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import vida_original_table_reader as capture


class Cursor:
    def __init__(self, rows, cols=None, table='T161_Profile', dbname='CarCom', chunk=2):
        self.rows = rows
        self.cols = cols if cols is not None else [
            (1, 'identifier', 'nvarchar'), (2, 'original_value', 'varbinary')]
        self.table = table
        self.dbname = dbname
        self.chunk = chunk
        self.queries = []
        self.args = []
        self.remaining = []
        self.description = None

    def execute(self, sql, *params):
        self.queries.append(sql)
        self.args.append(params)
        if sql == 'SELECT DB_NAME()':
            self.remaining = [(self.dbname,)]
        elif sql == capture.COLUMNS_SQL:
            self.remaining = list(self.cols)
        elif sql.startswith('SELECT TOP ('):
            self.remaining = list(self.rows)
            self.description = [(x[1],) for x in self.cols]
        else:
            raise AssertionError('unexpected command')
        return self

    def fetchmany(self, n):
        count = min(n, self.chunk)
        res, self.remaining = self.remaining[:count], self.remaining[count:]
        return res


class Connection:
    def __init__(self, cursor):
        self.cur = cursor
        self.closed = False
        self.timeout = None

    def cursor(self):
        return self.cur

    def close(self):
        self.closed = True


class OriginalTableTests(unittest.TestCase):
    def get(self, rows=None, cols=None, table='T161_Profile', max_rows=10, dbname='CarCom'):
        cursor = Cursor([('XC90 V8 МОДЕЛЬ', bytes([0, 255, 7]))] if rows is None else rows,
                        cols=cols, table=table, dbname=dbname)
        conn = Connection(cursor)
        report = capture.capture('CarCom', 'dbo', table, dsn='VIDA_RO',
                                 max_rows=max_rows, connector=lambda *_a, **_k: conn)
        self.assertTrue(conn.closed)
        self.assertEqual(conn.timeout, 8)
        return report, cursor

    def test_01_raw_names_and_values_are_preserved(self):
        doc, c = self.get()
        self.assertEqual(doc['source_table'], 'T161_Profile')
        self.assertEqual(doc['columns'][0]['name'], 'identifier')
        self.assertEqual(doc['rows'][0][0], 'XC90 V8 МОДЕЛЬ')
        self.assertEqual(base64.b64decode(doc['rows'][0][1]['value']), bytes([0,255,7]))
        self.assertTrue(doc['original_names_and_driver_values_not_anonymized'])
        self.assertFalse(doc['raw_sql_server_type_roundtrip_verified'])
        self.assertTrue(all('SELECT ' in q for q in c.queries))
        self.assertEqual(c.args[1], ('dbo', 'T161_Profile'))
        self.assertTrue('Trusted_Connection' not in json.dumps(doc))

    def test_02_sql_identifier_escaped_not_stripped(self):
        doc, c = self.get(table='T weird].Name')
        self.assertEqual(doc['source_table'], 'T weird].Name')
        self.assertIn('FROM [dbo].[T weird]].Name]', c.queries[-1])
        self.assertEqual(len(c.queries), 3)

    def test_03_row_limit_detects_truncation_not_partial_success(self):
        conn = Connection(Cursor([('a',b'x'), ('b', b'y'), ('c', b'z')], chunk=1))
        with self.assertRaisesRegex(capture.OriginalCaptureError, 'row limit'):
            capture.capture('CarCom','dbo','T161_Profile',dsn='VIDA_RO',max_rows=2,
                            connector=lambda *_a,**_k:conn)
        self.assertTrue(conn.closed)

    def test_04_database_identity_fail_closed(self):
        conn = Connection(Cursor([],dbname='Other'))
        with self.assertRaisesRegex(capture.OriginalCaptureError, 'database identity'):
            capture.capture('CarCom','dbo','T161_Profile',dsn='VIDA_RO',
                            connector=lambda *_a,**_k:conn)
        self.assertTrue(conn.closed)
        self.assertEqual(len(conn.cur.queries), 1)

    def test_05_raw_native_types_are_explicit_and_reversible(self):
        cells=(Decimal('12.3400'), 1.5, datetime.datetime(2020,1,2,3,4,5),
               datetime.date(2020,1,2), datetime.time(5,4,3),
               uuid.UUID('12345678-1234-5678-9abc-def012345678'), True, 17, None)
        encoded=[capture._encode(x) for x in cells]
        self.assertEqual(encoded[0], {'format':'decimal-text','value':'12.3400'})
        self.assertEqual(float.fromhex(encoded[1]['value']), 1.5)
        self.assertEqual(encoded[2]['value'], '2020-01-02T03:04:05')
        self.assertEqual(encoded[3]['value'], '2020-01-02')
        self.assertEqual(encoded[4]['value'], '05:04:03')
        self.assertEqual(encoded[5]['value'], '12345678123456789abcdef012345678')
        self.assertEqual(encoded[6:], [True,17,None])

    def test_06_unsupported_type_and_nonfinite_values_fail_closed(self):
        for value in (object(), float('nan'), float('inf'), Decimal('NaN')):
            with self.subTest(kind=type(value)), self.assertRaises(capture.OriginalCaptureError):
                capture._encode(value)

    def test_07_overly_broad_or_control_name_rejected(self):
        for bad in ('', 'a'*129, 'bad\nname', True, 123):
            with self.subTest(name=str(bad)[:10]), self.assertRaises(capture.OriginalCaptureError):
                capture._identifier(bad)

    def test_08_column_drift_or_missing_table_rejected(self):
        for cols in ([],[(1,'x','nvarchar'), (2,'x','nvarchar')]):
            conn=Connection(Cursor([],cols=cols))
            with self.assertRaises(capture.OriginalCaptureError):
                capture.capture('CarCom','dbo','T161_Profile',dsn='VIDA_RO',
                                connector=lambda *_a,**_k:conn)
            self.assertTrue(conn.closed)

    def test_09_connection_sql_read_only_and_typed_options(self):
        track=[]
        def connector(connstr,**kw):
            track.append((connstr,kw))
            return Connection(Cursor([]))
        capture.capture('CarCom','dbo','T161_Profile',dsn='VIDA_RO',connector=connector)
        self.assertIn('TrustServerCertificate=No',track[0][0])
        self.assertIn('ApplicationIntent=ReadOnly',track[0][0])
        self.assertEqual(track[0][1],{'autocommit':True,'timeout':8})
        for bad in ('RO;PWD=secret', '', None):
            with self.assertRaises(capture.OriginalCaptureError):
                capture.capture('CarCom','dbo','T161_Profile',dsn=bad,connector=connector)

    def test_10_no_automatic_data_upload_and_output_is_local_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'raw.json'
            fake=Connection(Cursor([('VIN_DO_NOT_SHARE',b'123')]))
            with patch.dict(capture.os.environ, {'VIDA_SQLSERVER_DSN':'VIDA_RO'}), \
                 patch.object(capture,'capture',return_value={'unmasked':'VIN_DO_NOT_SHARE'}), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                code=capture.main(['--database','CarCom','--schema','dbo','--table',
                                   'T161_Profile','--output',str(p)])
            self.assertEqual(code,0)
            self.assertEqual(json.loads(p.read_text())['unmasked'],'VIN_DO_NOT_SHARE')
            self.assertNotIn('VIN_DO_NOT_SHARE', output.getvalue())
            self.assertEqual(capture.main(['--database','CarCom','--schema','dbo',
                                           '--table','T161_Profile','--output',str(p)]),2)
            if sys.platform != 'win32':
                self.assertEqual(p.stat().st_mode & 0o777,0o600)

    def test_11_no_partial_output_if_source_too_large(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'raw.json'
            with patch.dict(capture.os.environ, {'VIDA_SQLSERVER_DSN':'VIDA_RO'}), \
                 patch.object(capture,'capture',return_value={'value':'x'*50}), \
                 patch.object(capture,'MAX_OUTPUT_BYTES',20), \
                 contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(capture.main(['--database','CarCom','--schema','dbo',
                       '--table','T161_Profile','--output',str(p)]),2)
            self.assertFalse(p.exists())

    def test_12_actual_row_count_and_original_null_preserved(self):
        report,_=self.get(rows=[(None, b''), ('é 🧪', bytes(range(5)))],max_rows=2)
        self.assertEqual(report['row_count'],2)
        self.assertEqual(report['rows'][0][0],None)
        self.assertEqual(report['rows'][1][0],'é 🧪')
        self.assertEqual(base64.b64decode(report['rows'][1][1]['value']),bytes(range(5)))


if __name__=='__main__':
    unittest.main()
