"""Synthetic SQL metadata double-scan tests, no original VIDA access."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import vida_dicetiming_catalog as dt

TABLES = [('dbo', 'SecretTiming'), ('dbo', 'SecretSettings')]
COLUMNS = [('dbo', 'SecretTiming', 'id'), ('dbo', 'SecretTiming', 'config'),
           ('dbo', 'SecretSettings', 'id')]
KEYS = [(91, 1, 'dbo', 'SecretTiming', 'config', 'dbo',
         'SecretSettings', 'id', False, False, 1)]


class ChangingCursor:
    def __init__(self, second=None, reverse=False, chunk=2):
        self.second = second or {}
        self.reverse = reverse
        self.chunk = chunk
        self.remaining = []
        self.calls = {'tables': 0, 'columns': 0, 'keys': 0}
        self.queries = []

    def execute(self, sql):
        self.queries.append(sql)
        if sql == 'SELECT DB_NAME()':
            self.remaining = [('DiceTiming',)]
        else:
            by_sql = {dt.SQL_TABLES: ('tables', TABLES),
                      dt.SQL_COLUMNS: ('columns', COLUMNS),
                      dt.SQL_KEYS: ('keys', KEYS)}
            if sql not in by_sql:
                raise AssertionError('noncatalog SQL issued')
            category, default = by_sql[sql]
            self.calls[category] += 1
            values = self.second.get(category, default) if self.calls[category] == 2 else default
            self.remaining = list(reversed(values)) if self.reverse else list(values)
        return self

    def fetchmany(self, requested):
        batch = self.remaining[:min(requested, self.chunk)]
        self.remaining = self.remaining[len(batch):]
        return batch


class FakeConnection:
    def __init__(self, cursor):
        self.cur = cursor
        self.timeout = None
        self.closed = False

    def cursor(self):
        return self.cur

    def close(self):
        self.closed = True


class DiceTimingCatalogStabilityTests(unittest.TestCase):
    def collect(self, second=None, reverse=False):
        conn = FakeConnection(ChangingCursor(second=second, reverse=reverse))
        try:
            result = dt.load_sqlserver('owner_dsn', connector=lambda *_a, **_kw: conn)
            return result, conn
        finally:
            self.assertTrue(conn.closed)

    def test_01_all_catalogs_are_read_twice(self):
        report, conn = self.collect()
        self.assertEqual(conn.cur.calls, {'tables': 2, 'columns': 2, 'keys': 2})
        self.assertEqual(len(conn.cur.queries), 7)
        self.assertEqual(report['declared_fk_column_count'], 1)
        self.assertFalse(report['cross_database_snapshot_verified'])

    def test_02_changed_table_catalog_rejected(self):
        with self.assertRaisesRegex(dt.DiceTimingError, 'changed between scans'):
            self.collect(second={'tables': [('dbo', 'SecretOther'), TABLES[1]]})

    def test_03_changed_column_catalog_rejected(self):
        changed = [COLUMNS[0], ('dbo', 'SecretTiming', 'other'), COLUMNS[2]]
        with self.assertRaisesRegex(dt.DiceTimingError, 'changed between scans'):
            self.collect(second={'columns': changed})

    def test_04_changed_foreign_key_catalog_rejected(self):
        changed = [KEYS[0][:-3] + (True, False, 1)]
        with self.assertRaisesRegex(dt.DiceTimingError, 'changed between scans'):
            self.collect(second={'keys': changed})

    def test_05_duplicate_catalog_item_on_rescan_rejected(self):
        with self.assertRaisesRegex(dt.DiceTimingError, 'changed between scans'):
            self.collect(second={'tables': TABLES + [TABLES[0]]})

    def test_06_different_row_order_is_not_structural_change(self):
        report, conn = self.collect(reverse=True)
        self.assertEqual(report['table_count'], 2)
        self.assertEqual(conn.cur.calls['columns'], 2)

    def test_07_malformed_catalog_width_rejected(self):
        with self.assertRaisesRegex(dt.DiceTimingError, 'row width'):
            self.collect(second={'columns': [COLUMNS[0][:-1]] + COLUMNS[1:]})

    def test_08_second_scan_respects_bounded_catalog_limit(self):
        with patch.object(dt, 'MAX_TABLES', 2):
            with self.assertRaisesRegex(dt.DiceTimingError, 'catalog too large'):
                self.collect(second={'tables': TABLES + [('dbo', 'SecretThird')]})

    def test_09_private_data_and_runtime_evidence_never_leak(self):
        report, _ = self.collect()
        data = json.dumps(report)
        self.assertNotIn('SecretTiming', data)
        self.assertNotIn('SecretSettings', data)
        self.assertFalse(report['client_vin_accepted'])
        self.assertFalse(report['replay_approved'])

    def test_10_unequal_multiplicity_rejected_even_same_unique_names(self):
        changed = [COLUMNS[0], COLUMNS[1], COLUMNS[2], COLUMNS[0]]
        with self.assertRaisesRegex(dt.DiceTimingError, 'changed between scans'):
            self.collect(second={'columns': changed})


if __name__ == '__main__':
    unittest.main()
