"""Synthetic SQL Server transaction snapshot safety regressions for original VIDA values."""
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
from test_vida_original_fk_sql_unique_target import UniqueTargetCursor, Connection
import vida_original_fk_sql_probe as probe
import vida_original_table_reader as reader


class SnapshotCursor(UniqueTargetCursor):
    def __init__(self, *, state=1, trancount=1, fail_on=None, **kwargs):
        super().__init__(**kwargs)
        self.state = state
        self.trancount = trancount
        self.fail_on = fail_on
        self.in_transaction = False
        self.committed = False
        self.rolled_back = False

    def execute(self, sql, *params):
        if sql == probe.SNAPSHOT_TRANCOUNT_SQL:
            self.calls.append((sql, params))
            self.remaining = [(self.trancount,)] if self.trancount is not None else []
            return self
        if sql == probe.SNAPSHOT_STATE_SQL:
            self.calls.append((sql, params))
            self.remaining = [(self.state,)] if self.state is not None else []
            return self
        if sql in ('SET TRANSACTION ISOLATION LEVEL SNAPSHOT',
                   'BEGIN TRANSACTION', 'COMMIT TRANSACTION', 'ROLLBACK TRANSACTION'):
            self.calls.append((sql, params))
            if self.fail_on == sql:
                raise RuntimeError('synthetic SQL failure')
            if sql == 'BEGIN TRANSACTION':
                self.in_transaction = True
            elif sql == 'COMMIT TRANSACTION':
                if not self.in_transaction:
                    raise AssertionError('COMMIT without BEGIN')
                self.in_transaction = False
                self.committed = True
            elif sql == 'ROLLBACK TRANSACTION':
                self.in_transaction = False
                self.rolled_back = True
            return self
        if self.fail_on == sql or (self.fail_on == 'main SELECT' and sql.startswith('SELECT TOP (') and 'CASE WHEN (' in sql):
            raise RuntimeError('synthetic SQL failure')
        return super().execute(sql, *params)


class OriginalSnapshotFKTests(unittest.TestCase):
    target_filters = [{'column': 'profile_identifier', 'operator': 'eq',
                       'value': 'Вольво XC90 V8 оригинал'}]

    def attempt(self, *, filters=None, source_filters=None, require_snapshot=True, require_unique_target=True,
                **cursor_args):
        cursor = SnapshotCursor(**cursor_args)
        db = Connection(cursor)
        try:
            result = probe.capture('CarCom', 'dbo', 'T136_InitHw_Profile',
                                   'FK_Profile ОРИГИНАЛ', dsn='VIDA_RO', max_rows=5,
                                   target_filters=self.target_filters if filters is None else filters,
                                   filters=source_filters,
                                   require_unique_target=require_unique_target,
                                   require_snapshot=require_snapshot,
                                   connector=lambda *_a, **_kw: db)
            return result, cursor, db
        finally:
            self.assertTrue(db.closed)

    def test_01_snapshot_isolation_one_transaction_for_unique_and_exists(self):
        out, c, _ = self.attempt()
        commands = [q for q, _ in c.calls]
        self.assertEqual(commands[0], 'SELECT DB_NAME()')
        self.assertEqual(commands[1], probe.SNAPSHOT_STATE_SQL)
        self.assertEqual(commands[2], 'SET TRANSACTION ISOLATION LEVEL SNAPSHOT')
        self.assertEqual(commands[3], 'BEGIN TRANSACTION')
        self.assertEqual(commands[4], probe.SNAPSHOT_TRANCOUNT_SQL)
        self.assertEqual(commands[-1], 'COMMIT TRANSACTION')
        self.assertTrue(c.committed)
        self.assertFalse(c.rolled_back)
        self.assertFalse(c.in_transaction)
        self.assertLess(commands.index('BEGIN TRANSACTION'),
                        next(i for i, q in enumerate(commands) if q.startswith('SELECT TOP (2)')))
        self.assertGreater(commands.index('COMMIT TRANSACTION'),
                           next(i for i, q in enumerate(commands) if q.startswith('SELECT TOP (6)')))
        self.assertTrue(out['transactional_snapshot_verified'])
        self.assertTrue(out['sql_snapshot_isolation_required'])
        self.assertTrue(out['sql_snapshot_transaction_committed'])
        self.assertEqual(out['selected_target_original_key_values'], ['XC90 ОРИГИНАЛ', 88])
        self.assertFalse(out['vida_runtime_selected_profile_verified'])
        self.assertFalse(out['physical_j2534_verified'])
        self.assertNotIn('ROLLBACK TRANSACTION', commands)

    def test_02_database_snapshot_off_refuses_before_any_transaction(self):
        for state in (0, 2, 3, None):
            with self.subTest(state=state):
                c = SnapshotCursor(state=state)
                db = Connection(c)
                with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'SNAPSHOT isolation unavailable'):
                    probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                                  dsn='VIDA_RO', target_filters=self.target_filters,
                                  require_unique_target=True, require_snapshot=True,
                                  connector=lambda *_a, **_kw: db)
                self.assertTrue(db.closed)
                self.assertFalse(c.committed)
                self.assertFalse(c.in_transaction)
                self.assertFalse(any(q == 'BEGIN TRANSACTION' for q, _ in c.calls))

    def test_03_strict_snapshot_requires_uniqueness_and_correct_bool(self):
        for kwargs in ({'require_snapshot': True, 'require_unique_target': False},
                       {'require_snapshot': 1, 'require_unique_target': True},
                       {'require_snapshot': 'true', 'require_unique_target': True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(probe.OriginalFKSQLProbeError):
                probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                              dsn='VIDA_RO', target_filters=self.target_filters,
                              connector=lambda *_a,**_kw: self.fail('SQL must not connect'),
                              **kwargs)

    def test_04_ambiguous_selector_causes_rollback_not_commit(self):
        c = SnapshotCursor(selected_rows=[('A',1), ('B',2)])
        db = Connection(c)
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'exactly one row'):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO', target_filters=self.target_filters,
                          require_unique_target=True, require_snapshot=True,
                          connector=lambda *_a,**_kw: db)
        self.assertTrue(db.closed)
        self.assertTrue(c.rolled_back)
        self.assertFalse(c.committed)
        self.assertFalse(c.in_transaction)

    def test_05_sql_error_after_begin_causes_rollback_and_sanitized_error(self):
        c = SnapshotCursor(fail_on='main SELECT')
        db = Connection(c)
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'original SQL read failed') as ctx:
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO', target_filters=self.target_filters,
                          require_unique_target=True, require_snapshot=True,
                          connector=lambda *_a,**_kw: db)
        self.assertNotIn('synthetic SQL failure', str(ctx.exception))
        self.assertTrue(db.closed)
        self.assertTrue(c.rolled_back)
        self.assertFalse(c.committed)

    def test_06_begin_failure_has_no_rollback_or_commit(self):
        c = SnapshotCursor(fail_on='BEGIN TRANSACTION')
        db = Connection(c)
        with self.assertRaises(probe.OriginalFKSQLProbeError):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO', target_filters=self.target_filters,
                          require_unique_target=True, require_snapshot=True,
                          connector=lambda *_a,**_kw: db)
        self.assertTrue(db.closed)
        self.assertFalse(c.rolled_back)
        self.assertFalse(c.committed)

    def test_07_commit_failure_attempts_rollback(self):
        c = SnapshotCursor(fail_on='COMMIT TRANSACTION')
        db = Connection(c)
        with self.assertRaises(probe.OriginalFKSQLProbeError):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO', target_filters=self.target_filters,
                          require_unique_target=True, require_snapshot=True,
                          connector=lambda *_a,**_kw: db)
        self.assertTrue(db.closed)
        self.assertTrue(c.rolled_back)
        self.assertFalse(c.committed)

    def test_08_rollback_failure_is_sanitized_and_connection_closed(self):
        c = SnapshotCursor(selected_rows=[], fail_on='ROLLBACK TRANSACTION')
        db = Connection(c)
        with self.assertRaisesRegex(probe.OriginalFKSQLProbeError, 'SNAPSHOT rollback failed'):
            probe.capture('CarCom','dbo','T136_InitHw_Profile','FK_Profile ОРИГИНАЛ',
                          dsn='VIDA_RO', target_filters=self.target_filters,
                          require_unique_target=True, require_snapshot=True,
                          connector=lambda *_a,**_kw: db)
        self.assertTrue(db.closed)
        self.assertFalse(c.committed)

    def test_09_legacy_strict_unique_target_has_no_transaction(self):
        out, c, _ = self.attempt(require_snapshot=False)
        self.assertFalse(out['transactional_snapshot_verified'])
        self.assertFalse(out['sql_snapshot_isolation_required'])
        self.assertFalse(out['sql_snapshot_transaction_committed'])
        self.assertFalse(c.committed)
        self.assertFalse(c.rolled_back)
        self.assertNotIn(probe.SNAPSHOT_STATE_SQL, [q for q, _ in c.calls])

    def test_10_snapshot_preserves_original_filtered_source_values(self):
        out, c, _ = self.attempt(source_filters=[{'column': 'profile_identifier',
                                          'operator': 'eq', 'value': 'VIN_НЕ_МАСКИРОВАТЬ'}])
        self.assertIn('VIN_НЕ_МАСКИРОВАТЬ', json.dumps(out, ensure_ascii=False))
        self.assertEqual(out['sql_exists_matches'][0]['original_source_key_values'],
                         ['XC90 V8 / ИНДЕКС', 7])
        self.assertTrue(out['transactional_snapshot_verified'])
        for q, params in c.calls:
            if q.startswith('SELECT TOP (6)'):
                self.assertNotIn('VIN_НЕ_МАСКИРОВАТЬ', q)
                self.assertEqual(params, ('Вольво XC90 V8 оригинал', 'VIN_НЕ_МАСКИРОВАТЬ'))

    def test_11_snapshot_cli_flag_wires_through_no_leaks(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            flt = d / 'original_filter.json'
            out = d / 'result.json'
            flt.write_text(json.dumps({'schema_version': reader.FILTER_SCHEMA,
               'clauses': self.target_filters}, ensure_ascii=False), encoding='utf-8')
            original_capture = probe.capture
            def stub(*args, **kwargs):
                self.assertTrue(kwargs['require_snapshot'])
                self.assertTrue(kwargs['require_unique_target'])
                cur = SnapshotCursor()
                return original_capture(*args, dsn='VIDA_RO', max_rows=5,
                                        require_snapshot=True, require_unique_target=True,
                                        target_filters=kwargs['target_filters'],
                                        connector=lambda *_a, **_kw: Connection(cur))
            argv = ['--database','CarCom','--schema','dbo','--table','T136_InitHw_Profile',
                    '--foreign-key','FK_Profile ОРИГИНАЛ','--target-filters-json',str(flt),
                    '--require-unique-target','--require-snapshot','--output',str(out)]
            with patch.object(probe, 'capture', side_effect=stub), \
                 contextlib.redirect_stdout(io.StringIO()) as stdout, \
                 contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(probe.main(argv), 0)
            report = json.loads(out.read_text())
            self.assertTrue(report['transactional_snapshot_verified'])
            self.assertNotIn('Вольво XC90 V8 оригинал',stdout.getvalue()+stderr.getvalue())
            self.assertIn('Вольво XC90 V8 оригинал',out.read_text())

    def test_12_transaction_count_must_be_one_not_zero_or_nested(self):
        for count in (0, 2, None):
            with self.subTest(count=count):
                c = SnapshotCursor(trancount=count)
                db = Connection(c)
                with self.assertRaisesRegex(probe.OriginalFKSQLProbeError,
                                            'SNAPSHOT transaction not active'):
                    probe.capture('CarCom','dbo','T136_InitHw_Profile',
                                  'FK_Profile ОРИГИНАЛ', dsn='VIDA_RO',
                                  target_filters=self.target_filters,
                                  require_unique_target=True,
                                  require_snapshot=True,
                                  connector=lambda *_a, **_kw: db)
                self.assertTrue(db.closed)
                self.assertTrue(c.rolled_back)
                self.assertFalse(c.committed)

    def test_13_snapshot_never_claims_getscript_readvin_or_physical_can(self):
        out, _, _ = self.attempt()
        self.assertFalse(out['getscript_readvin_runtime_verified'])
        self.assertFalse(out['client_vin_accepted'])
        self.assertFalse(out['physical_j2534_verified'])
        self.assertFalse(out['full_catalog_visibility_verified'])
        self.assertFalse(out['fk_constraint_enforcement_verified'])


if __name__ == '__main__':
    unittest.main()
