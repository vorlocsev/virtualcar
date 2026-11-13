"""Synthetic DB-API paging regressions for DiceTiming metadata, never original VIDA."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import vida_dicetiming_catalog as mod


class PagedCursor:
    def __init__(self, tables, columns, keys=(), chunk=1):
        self.data = {'tables': list(tables), 'columns': list(columns), 'keys': list(keys)}
        self.chunk = chunk
        self.remaining = []
        self.queries = []
        self.fetch_calls = 0

    def execute(self, sql):
        self.queries.append(sql)
        if sql == 'SELECT DB_NAME()':
            self.remaining = [('DiceTiming',)]
        elif 'FROM sys.foreign_key_columns' in sql:
            self.remaining = list(self.data['keys'])
        elif 'FROM sys.columns' in sql:
            self.remaining = list(self.data['columns'])
        elif 'FROM sys.tables' in sql:
            self.remaining = list(self.data['tables'])
        else:
            raise AssertionError('not an allowlisted metadata query')
        return self

    def fetchmany(self, size):
        self.fetch_calls += 1
        take = min(size, self.chunk)
        batch = self.remaining[:take]
        del self.remaining[:take]
        return batch


class FakeDB:
    def __init__(self, cursor):
        self.cur = cursor
        self.timeout = None
        self.closed = False

    def cursor(self):
        return self.cur

    def close(self):
        self.closed = True


class CursorPagingTests(unittest.TestCase):
    TABLES = [('dbo', 'TimingA'), ('dbo', 'TimingB')]
    COLUMNS = [('dbo', 'TimingA', 'id'), ('dbo', 'TimingA', 'ref'),
               ('dbo', 'TimingB', 'id'), ('dbo', 'TimingB', 'timestamp')]
    KEYS = [(17, 1, 'dbo', 'TimingA', 'ref', 'dbo', 'TimingB', 'id', 0, 0, 1)]

    def connect(self, tables=None, columns=None, keys=None, chunk=1):
        cur = PagedCursor(self.TABLES if tables is None else tables,
                          self.COLUMNS if columns is None else columns,
                          self.KEYS if keys is None else keys, chunk=chunk)
        db = FakeDB(cur)
        return db

    def test_01_short_batches_are_drained_across_all_three_catalogs(self):
        db = self.connect(chunk=1)
        result = mod.load_sqlserver('OWNER_LOCAL', connector=lambda *_a, **_kw: db)
        self.assertTrue(db.closed)
        self.assertEqual(result['table_count'], 2)
        self.assertEqual(result['column_count'], 4)
        self.assertEqual(result['declared_fk_column_count'], 1)
        self.assertEqual(result['visible_fk_catalog']['constraint_count'], 1)
        self.assertEqual(len(db.cur.queries), 7)
        self.assertGreater(db.cur.fetch_calls, len(db.cur.queries))
        self.assertFalse(result['original_timing_values_read'])
        self.assertNotIn('TimingA', json.dumps(result))
        self.assertNotIn('TimingB', json.dumps(result))

    def test_02_table_catalog_overflow_across_short_batches_fails_closed(self):
        many_tables = [('dbo', 'Synthetic' + str(i)) for i in range(mod.MAX_TABLES + 1)]
        db = self.connect(tables=many_tables, keys=[], chunk=113)
        with self.assertRaisesRegex(mod.DiceTimingError, 'catalog too large'):
            mod.load_sqlserver('OWNER_LOCAL', connector=lambda *_a, **_kw: db)
        self.assertTrue(db.closed)

    def test_03_column_catalog_overflow_across_short_batches_fails_closed(self):
        many_columns = [('dbo', 'TimingA', 'SyntheticCol' + str(i))
                        for i in range(mod.MAX_COLUMNS + 1)]
        db = self.connect(columns=many_columns, keys=[], chunk=251)
        with self.assertRaisesRegex(mod.DiceTimingError, 'catalog too large'):
            mod.load_sqlserver('OWNER_LOCAL', connector=lambda *_a, **_kw: db)
        self.assertTrue(db.closed)

    def test_04_fk_catalog_overflow_across_short_batches_fails_closed(self):
        # Fake rows need not be semantically valid; must abort before validation.
        many_keys = [self.KEYS[0]] * (mod.MAX_KEYS + 1)
        db = self.connect(keys=many_keys, chunk=61)
        with self.assertRaisesRegex(mod.DiceTimingError, 'catalog too large'):
            mod.load_sqlserver('OWNER_LOCAL', connector=lambda *_a, **_kw: db)
        self.assertTrue(db.closed)

    def test_05_incomplete_columns_still_fail_after_all_pages(self):
        db = self.connect(columns=[('dbo', 'TimingA', 'id')], keys=[], chunk=1)
        with self.assertRaisesRegex(mod.DiceTimingError, 'incomplete metadata inventory'):
            mod.load_sqlserver('OWNER_LOCAL', connector=lambda *_a, **_kw: db)
        self.assertTrue(db.closed)

    def test_06_overlong_cursor_batch_rejected_without_private_echo(self):
        class DisobedientCursor(PagedCursor):
            def fetchmany(self, n):
                if 'FROM sys.tables' in self.queries[-1]:
                    return [('dbo', 'PRIVATE_OWNER_SECRET')] * (n + 1)
                return super().fetchmany(n)
        db = FakeDB(DisobedientCursor(self.TABLES, self.COLUMNS, self.KEYS))
        with self.assertRaises(mod.DiceTimingError) as caught:
            mod.load_sqlserver('OWNER_LOCAL', connector=lambda *_a, **_kw: db)
        self.assertEqual(str(caught.exception), 'invalid metadata cursor batch')
        self.assertTrue(db.closed)


if __name__ == '__main__':
    unittest.main()
