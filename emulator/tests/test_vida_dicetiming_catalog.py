"""Synthetic-only coverage of DiceTiming metadata scope and summary integration."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import vida_dicetiming_catalog as dt
import vida_evidence_summary as summary


class FakeCursor:
    def __init__(self, wrong=False, incomplete=False):
        self.current = []
        self.queries = []
        self.wrong = wrong
        self.incomplete = incomplete

    def execute(self, sql):
        self.queries.append(sql)
        if sql == 'SELECT DB_NAME()':
            self.current = [('Wrong',)] if self.wrong else [('DiceTiming',)]
        elif 'FROM sys.foreign_key_columns' in sql:
            self.current = []
        elif 'FROM sys.columns' in sql:
            self.current = [] if self.incomplete else [('dbo', 'PROPRIETARY_TIMING', 'SECRET_BYTE')]
        elif 'FROM sys.tables' in sql:
            self.current = [('dbo', 'PROPRIETARY_TIMING')]
        else:
            raise AssertionError('Unexpected SQL')
        return self

    def fetchmany(self, n):
        return self.current[:n]


class FakeDb:
    def __init__(self, wrong=False, incomplete=False):
        self.cursor_obj = FakeCursor(wrong, incomplete)
        self.timeout = 0
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


class DiceTimingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def create(self, db_name='DiceTiming', include_column=True):
        path = self.folder / 'DiceTiming.sqlite'
        if path.exists():
            path.unlink()
        with contextlib.closing(sqlite3.connect(path)) as conn:
            conn.executescript('''
                CREATE TABLE _vida_meta ("key" TEXT, "value" TEXT);
                CREATE TABLE _vida_tables (schema_name TEXT, table_name TEXT, rows_exported INTEGER);
                CREATE TABLE _vida_columns (schema_name TEXT, table_name TEXT, column_name TEXT, system_type_id INTEGER);
                CREATE TABLE SECRET_TIMING (private_value TEXT);
                INSERT INTO SECRET_TIMING VALUES ('OWNER_ONLY_TIMING_BYTES');
            ''')
            for key, val in (('schema_version', dt.EXPORT_SCHEMA),
                             ('source_database', db_name), ('scope', 'all_user_tables')):
                conn.execute('INSERT INTO _vida_meta VALUES (?, ?)', (key, val))
            conn.execute('INSERT INTO _vida_tables VALUES (?,?,?)', ('dbo', 'SECRET_TIMING', 1))
            if include_column:
                conn.execute('INSERT INTO _vida_columns VALUES (?,?,?,?)',
                             ('dbo', 'SECRET_TIMING', 'SECRET_BYTE', 165))
            conn.commit()
        return path

    def test_01_sqlite_reads_only_metadata_and_hides_identifiers(self):
        src = self.create()
        initial = src.read_bytes()
        out = dt.load_sqlite_export(self.folder)
        self.assertEqual(out['table_count'], 1)
        self.assertEqual(out['column_count'], 1)
        self.assertEqual(out['declared_fk_column_count'], 0)
        self.assertFalse(out['d2_baud_verified'])
        self.assertNotIn('SECRET', json.dumps(out))
        self.assertEqual(src.read_bytes(), initial)

    def test_02_sqlite_wrong_source_identity_fails(self):
        self.create('CarCom')
        with self.assertRaises(dt.DiceTimingError):
            dt.load_sqlite_export(self.folder)

    def test_03_sqlite_missing_file_missing_column_fails_closed(self):
        with self.assertRaises(dt.DiceTimingError):
            dt.load_sqlite_export(self.folder)
        self.create(include_column=False)
        with self.assertRaises(dt.DiceTimingError):
            dt.load_sqlite_export(self.folder)

    def test_04_sqlite_rejects_live_sidecar_or_redirect(self):
        src = self.create()
        sidecar = self.folder / 'DiceTiming.sqlite-wal'
        sidecar.write_bytes(b'synthetic')
        with self.assertRaises(dt.DiceTimingError):
            dt.load_sqlite_export(self.folder)
        sidecar.unlink()
        renamed = self.folder / 'other.sqlite'
        src.rename(renamed)
        try:
            src.symlink_to(renamed)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaises(dt.DiceTimingError):
            dt.load_sqlite_export(self.folder)

    def test_05_sqlite_rejects_exporter_view(self):
        src = self.create()
        with contextlib.closing(sqlite3.connect(src)) as conn:
            conn.execute('ALTER TABLE _vida_tables RENAME TO _old_tables')
            conn.execute('CREATE VIEW _vida_tables AS SELECT * FROM _old_tables')
            conn.commit()
        with self.assertRaises(dt.DiceTimingError):
            dt.load_sqlite_export(self.folder)

    def test_06_sqlserver_uses_fixed_sys_queries_and_trusted_auth(self):
        connections = []
        def connect(connstring, autocommit=False, timeout=0):
            self.assertIn('DATABASE=DiceTiming;', connstring)
            self.assertIn('Trusted_Connection=Yes;', connstring)
            self.assertIn('Encrypt=Yes;TrustServerCertificate=No;', connstring)
            self.assertTrue(autocommit)
            self.assertEqual(timeout, 8)
            d = FakeDb()
            connections.append(d)
            return d
        result = dt.load_sqlserver('LOCAL_DSN', connect)
        self.assertEqual(result['backend'], 'sqlserver')
        self.assertEqual(result['table_count'], 1)
        self.assertTrue(connections[0].closed)
        self.assertEqual(connections[0].timeout, 8)
        self.assertEqual(len(connections[0].cursor_obj.queries), 4)
        self.assertTrue(all(q == 'SELECT DB_NAME()' or 'sys.' in q
                            for q in connections[0].cursor_obj.queries))
        self.assertNotIn('PROPRIETARY', json.dumps(result))

    def test_07_sqlserver_wrong_db_or_missing_column_rejected(self):
        for kwargs in ({'wrong': True}, {'incomplete': True}):
            d = FakeDb(**kwargs)
            with self.assertRaises(dt.DiceTimingError):
                dt.load_sqlserver('local', connector=lambda *_a, **_k: d)
            self.assertTrue(d.closed)

    def test_08_reject_dsn_injection_and_no_secret_echo(self):
        for bad in ('', 'SERVER=secret;PWD=password', 'bad name', 'X' * 129):
            with self.assertRaises(dt.DiceTimingError):
                dt.load_sqlserver(bad, connector=lambda *_a, **_k: None)
        def fail(*args, **kw):
            raise RuntimeError('SECRET_PASSWORD')
        with self.assertRaises(dt.DiceTimingError) as caught:
            dt.load_sqlserver('valid', connector=fail)
        self.assertNotIn('SECRET_PASSWORD', str(caught.exception))

    def test_09_summary_accepts_dice_only_without_transport_promotion(self):
        self.create()
        evidence = dt.load_sqlite_export(self.folder)
        result = summary.assemble(dice_timing=evidence)
        stages = {s['id']: s['status'] for s in result['stages']}
        self.assertEqual(stages['dice_timing_metadata'], 'passed')
        self.assertEqual(stages['getscript_runtime_selection'], 'not_tested')
        self.assertFalse(result['dice_timing_profile_mapping_verified'])
        self.assertFalse(result['physical_j2534_verified'])

    def test_10_summary_rejects_forged_baud_or_identity(self):
        self.create()
        evidence = dt.load_sqlite_export(self.folder)
        for key in ('d2_baud_verified', 'original_timing_values_read', 'client_vin_accepted'):
            bad = dict(evidence)
            bad[key] = True
            with self.subTest(key=key), self.assertRaises(summary.EvidenceError):
                summary.assemble(dice_timing=bad)

    def test_11_cli_summary_with_dicetiming_and_hash_bundle(self):
        self.create()
        src = self.folder / 'dt.json'
        out = self.folder / 'result.json'
        summary_out = self.folder / 'summary.json'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(dt.main(['--backend', 'sqlite-export', '--folder', str(self.folder),
                                      '--output', str(out)]), 0)
            self.assertEqual(summary.main(['--dicetiming-report', str(out),
                                           '--output', str(summary_out)]), 0)
        report = json.loads(summary_out.read_text())
        self.assertEqual(report['dice_timing_catalog']['table_count'], 1)
        self.assertFalse(report['client_vin_accepted'])
        self.assertFalse(report['replay_approved'])
        self.assertNotIn('SECRET', summary_out.read_text())

    def test_12_cli_no_overwrite_or_source_alias(self):
        src = self.create()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(dt.main(['--backend', 'sqlite-export', '--folder', str(self.folder),
                                      '--output', str(src)]), 2)
        after = src.read_bytes()
        target = self.folder / 'dicetiming.json'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(dt.main(['--backend', 'sqlite-export', '--folder', str(self.folder),
                                      '--output', str(target)]), 0)
            self.assertEqual(dt.main(['--backend', 'sqlite-export', '--folder', str(self.folder),
                                      '--output', str(target)]), 2)
        self.assertEqual(src.read_bytes(), after)

    def test_13_bundle_manifest_with_dicetiming_hash(self):
        self.create()
        source = self.folder / 'dicetiming.json'
        source.write_text(json.dumps(dt.load_sqlite_export(self.folder)), encoding='utf-8')
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        manifest = self.folder / 'manifest.json'
        manifest.write_text(json.dumps({
            'schema_version': summary.BUNDLE_SCHEMA,
            'scope': 'redacted_report_bytes_only',
            'reports': {'dicetiming': digest},
            'same_installation_provenance_verified': False,
            'runtime_evidence_verified': False,
        }), encoding='utf-8')
        out = self.folder / 'summary.json'
        args = ['--dicetiming-report', str(source), '--bundle-manifest', str(manifest),
                '--output', str(out)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(summary.main(args), 0)
        result = json.loads(out.read_text())
        self.assertTrue(result['redacted_report_bytes_bound'])
        self.assertFalse(result['same_installation_provenance_verified'])
        self.assertNotIn(digest, out.read_text())
        bad = self.folder / 'wrong.json'
        bad.write_text(source.read_text() + '\n', encoding='utf-8')
        failed_output = self.folder / 'failed-summary.json'
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(summary.main(['--dicetiming-report', str(bad),
                                           '--bundle-manifest', str(manifest),
                                           '--output', str(failed_output)]), 2)
        self.assertFalse(failed_output.exists())



if __name__ == '__main__':
    unittest.main()
