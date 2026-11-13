"""Synthetic, original-identifier-preserving SQL schema-reader regressions."""
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
import vida_original_schema_reader as original

TABLES = [('dbo', 'T136_InitHw_Profile', 10), ('dbo', 'T161_Profile', 20)]
COLUMNS = [
    (10, 1, 'fk_Profile_A', 'int', 4, 10, 0, False, False, False, None),
    (10, 2, 'fk_Profile_B', 'nvarchar', 100, 0, 0, True, False, False, 'Latin1_General_100_CI_AS'),
    (20, 1, 'id', 'int', 4, 10, 0, False, True, False, None),
    (20, 2, 'original_ИД', 'nvarchar', 100, 0, 0, False, False, False, 'Cyrillic_General_CI_AS'),
]
INDEXES = [(20, 1, 'PK_T161_Profile ОРИГИНАЛ', True, False, 1, 1),
           (20, 1, 'PK_T161_Profile ОРИГИНАЛ', True, False, 2, 2)]
FKS = [(100, 'FK_InitHw_Profile ОРИГИНАЛ', 1, 10, 1, 20, 1, 1, False, True, 'NO_ACTION', 'CASCADE'),
       (100, 'FK_InitHw_Profile ОРИГИНАЛ', 2, 10, 2, 20, 2, 1, False, True, 'NO_ACTION', 'CASCADE')]


class Cursor:
    def __init__(self, tables=TABLES, columns=COLUMNS, indexes=INDEXES, fks=FKS, db='CarCom', chunk=1):
        self.data = {original.TABLES_SQL: list(tables), original.COLUMNS_SQL: list(columns),
                     original.INDEXES_SQL: list(indexes), original.FOREIGN_KEYS_SQL: list(fks)}
        self.db = db
        self.chunk = chunk
        self.current = []
        self.statements = []

    def execute(self, query):
        self.statements.append(query)
        if query == 'SELECT DB_NAME()':
            self.current = [(self.db,)]
        elif query in self.data:
            self.current = list(self.data[query])
        else:
            raise AssertionError('unapproved SQL')
        return self

    def fetchmany(self, size):
        count = min(self.chunk, size)
        batch, self.current = self.current[:count], self.current[count:]
        return batch


class Connection:
    def __init__(self, cursor):
        self.cur = cursor
        self.timeout = None
        self.closed = False

    def cursor(self):
        return self.cur

    def close(self):
        self.closed = True


class OriginalSchemaReaderTests(unittest.TestCase):
    def fake(self, **kw):
        connection = Connection(Cursor(**kw))
        return connection, lambda *_args, **_kwargs: connection

    def test_01_original_table_column_fk_index_names_not_masked(self):
        db, connector = self.fake()
        result = original.capture('CarCom', dsn='VIDA_RO', connector=connector)
        self.assertTrue(db.closed)
        self.assertEqual(db.timeout, 8)
        self.assertEqual(len(db.cur.statements), 5)
        self.assertTrue(all(s == 'SELECT DB_NAME()' or 'sys.' in s for s in db.cur.statements))
        self.assertEqual(result['source_database'], 'CarCom')
        self.assertEqual(result['tables'][1]['columns'][1]['name'], 'original_ИД')
        self.assertEqual(result['tables'][1]['unique_indexes'][0]['name'], 'PK_T161_Profile ОРИГИНАЛ')
        self.assertEqual(result['foreign_keys'][0]['name'], 'FK_InitHw_Profile ОРИГИНАЛ')
        self.assertEqual(result['foreign_keys'][0]['columns'][1]['referenced'], 'original_ИД')
        self.assertTrue(result['foreign_keys'][0]['is_not_trusted'])
        self.assertFalse(result['actual_row_joins_verified'])
        self.assertFalse(result['complete_catalog_visibility_verified'])
        self.assertFalse(result['original_user_rows_read'])
        self.assertIn('ОРИГИНАЛ', json.dumps(result, ensure_ascii=False))

    def test_02_composite_key_order_not_cursor_order(self):
        result = original.parse('CarCom', TABLES[::-1], COLUMNS[::-1], INDEXES[::-1], FKS[::-1])
        fk = result['foreign_keys'][0]
        self.assertEqual([c['ordinal'] for c in fk['columns']], [1, 2])
        self.assertEqual([c['source'] for c in fk['columns']], ['fk_Profile_A', 'fk_Profile_B'])

    def test_03_fk_missing_trailing_index_column_rejected(self):
        with self.assertRaisesRegex(original.OriginalSchemaError, 'referenced SQL unique index'):
            original.parse('CarCom', TABLES, COLUMNS, INDEXES, FKS[:1])

    def test_04_fk_duplicate_and_missing_ordinal_rejected(self):
        duplicate = [FKS[0], FKS[1][:2] + (1,) + FKS[1][3:]]
        with self.assertRaisesRegex(original.OriginalSchemaError, 'ordinal'):
            original.parse('CarCom', TABLES, COLUMNS, INDEXES, duplicate)
        gap = [FKS[0][:2] + (2,) + FKS[0][3:], FKS[1][:2] + (3,) + FKS[1][3:]]
        with self.assertRaisesRegex(original.OriginalSchemaError, 'ordinal'):
            original.parse('CarCom', TABLES, COLUMNS, INDEXES, gap)

    def test_05_index_member_missing_or_duplicate_ordinal_rejected(self):
        with self.assertRaisesRegex(original.OriginalSchemaError, 'ordinal'):
            original.parse('CarCom', TABLES, COLUMNS, [INDEXES[0][:5] + (2, 1)], FKS)
        with self.assertRaisesRegex(original.OriginalSchemaError, 'ordinal'):
            original.parse('CarCom', TABLES, COLUMNS, [INDEXES[0], INDEXES[1][:5] + (1, 2)], FKS)

    def test_06_missing_columns_or_invalid_fk_reference_rejected(self):
        with self.assertRaisesRegex(original.OriginalSchemaError, 'incomplete'):
            original.parse('CarCom', TABLES, COLUMNS[2:], INDEXES, FKS)
        with self.assertRaisesRegex(original.OriginalSchemaError, 'unresolved'):
            original.parse('CarCom', TABLES, COLUMNS, INDEXES, [FKS[0][:4] + (88,) + FKS[0][5:]])

    def test_07_column_names_and_types_with_unicode_preserved(self):
        result = original.parse('CarCom', TABLES, COLUMNS, INDEXES, FKS)
        self.assertEqual(result['tables'][0]['columns'][1]['collation_name'], 'Latin1_General_100_CI_AS')
        self.assertEqual(result['tables'][1]['columns'][1]['name'], 'original_ИД')
        self.assertEqual(result['tables'][0]['columns'][0]['sql_type'], 'int')
        self.assertEqual(result['foreign_keys'][0]['on_update'], 'CASCADE')

    def test_08_wrong_db_identity_rejected_no_sql_catalog_read(self):
        db, connector = self.fake(db='DiceTiming')
        with self.assertRaisesRegex(original.OriginalSchemaError, 'wrong original'):
            original.capture('CarCom', dsn='VIDA_RO', connector=connector)
        self.assertTrue(db.closed)
        self.assertEqual(db.cur.statements, ['SELECT DB_NAME()'])

    def test_09_bounded_read_rejects_extra_rows_across_short_batches(self):
        c = Cursor(chunk=1)
        c.current = [('x',)] * 4
        with self.assertRaisesRegex(original.OriginalSchemaError, 'exceeds limit'):
            original._read_bounded(c, 3)

    def test_10_sql_dsn_not_exposed_in_output_and_invalid_input_rejected(self):
        tracking = []
        db, _ = self.fake()
        def connector(connection, **options):
            tracking.append((connection, options))
            return db
        doc = original.capture('CarCom', dsn='VIDA_RO', connector=connector)
        self.assertNotIn('VIDA_RO', json.dumps(doc))
        self.assertIn('TrustServerCertificate=No', tracking[0][0])
        self.assertIn('ApplicationIntent=ReadOnly', tracking[0][0])
        self.assertEqual(tracking[0][1], {'autocommit': True, 'timeout': 8})
        for dsn in ('', 'VIDA_RO;PWD=secret', None):
            with self.assertRaises(original.OriginalSchemaError):
                original.capture('CarCom', dsn=dsn, connector=connector)

    def test_11_cli_original_json_local_and_exclusive_no_stdout_names(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'original_schema.json'
            with patch.object(original, 'capture', return_value=original.parse('CarCom', TABLES, COLUMNS, INDEXES, FKS)):
                with contextlib.redirect_stdout(io.StringIO()) as stream:
                    self.assertEqual(original.main(['--database', 'CarCom', '--output', str(out)]), 0)
                    self.assertEqual(original.main(['--database', 'CarCom', '--output', str(out)]), 2)
                self.assertNotIn('ОРИГИНАЛ', stream.getvalue())
            self.assertIn('ОРИГИНАЛ', out.read_text())
            if sys.platform != 'win32':
                self.assertEqual(out.stat().st_mode & 0o777, 0o600)

    def test_12_conflicting_fk_identity_rejected_and_no_private_error_echo(self):
        wrong = [FKS[0], FKS[1][:1] + ('SECRET_ORIGINAL_NAME',) + FKS[1][2:]]
        with self.assertRaises(original.OriginalSchemaError) as caught:
            original.parse('CarCom', TABLES, COLUMNS, INDEXES, wrong)
        self.assertNotIn('SECRET_ORIGINAL_NAME', str(caught.exception))

    def test_13_database_name_rejects_connection_string_property_injection(self):
        for bad in ('CarCom;PWD=secret', 'CarCom}UID=sa', 'CarCom\\TrustServerCertificate=Yes',
                    'CarCom\nInjected', 'X'*129):
            with self.subTest(value=bad[:15]), self.assertRaises(original.OriginalSchemaError):
                original.capture(bad, dsn='VIDA_RO',
                                 connector=lambda *_a, **_kw: self.fail('connector invoked'))


if __name__ == '__main__':
    unittest.main()
