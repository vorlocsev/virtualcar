"""Synthetic-only tests of owner-local, non-attesting VIDA report manifest tool."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_vida_redacted_manifest as mod
import vida_dicetiming_catalog as catalog
import vida_evidence_summary as summary


class RedactedManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.report_path = self.folder / 'dicetiming.redacted.json'
        self.report = catalog._finish({('dbo', 'SecretName'): {'SecretColumn'}},
                                      0, 'sqlite-export')
        self.report_path.write_text(json.dumps(self.report, indent=2), encoding='utf-8')
        self.output = self.folder / 'manifest.json'

    def call(self, *extra):
        with contextlib.redirect_stdout(io.StringIO()) as stdout, \
             contextlib.redirect_stderr(io.StringIO()) as stderr:
            result = mod.main(['--dicetiming-report', str(self.report_path),
                               '--output', str(self.output), *extra])
        return result, stdout.getvalue(), stderr.getvalue()

    def test_01_manifest_binds_exact_report_bytes_without_copied_content(self):
        status, stdout, stderr = self.call()
        self.assertEqual(status, 0)
        self.assertEqual(stderr, '')
        self.assertIn('origin and runtime remain unverified', stdout)
        manifest = json.loads(self.output.read_text())
        self.assertEqual(manifest['schema_version'], summary.BUNDLE_SCHEMA)
        self.assertEqual(set(manifest['reports']), {'dicetiming'})
        self.assertEqual(manifest['reports']['dicetiming'],
                         hashlib.sha256(self.report_path.read_bytes()).hexdigest())
        self.assertIs(manifest['same_installation_provenance_verified'], False)
        self.assertIs(manifest['runtime_evidence_verified'], False)
        self.assertNotIn('SecretName', self.output.read_text())
        self.assertNotIn('SecretColumn', self.output.read_text())
        self.assertNotIn(str(self.report_path), self.output.read_text())

    def test_02_generated_manifest_passes_real_summary_cli(self):
        self.assertEqual(self.call()[0], 0)
        out = self.folder / 'summary.json'
        with contextlib.redirect_stdout(io.StringIO()):
            result = summary.main(['--dicetiming-report', str(self.report_path),
                                   '--bundle-manifest', str(self.output),
                                   '--output', str(out)])
        self.assertEqual(result, 0)
        content = json.loads(out.read_text())
        self.assertTrue(content['redacted_report_bytes_bound'])
        self.assertFalse(content['same_installation_provenance_verified'])
        self.assertFalse(content['dice_timing_profile_mapping_verified'])

    def test_03_no_overwrite_second_call_fails_closed(self):
        self.assertEqual(self.call()[0], 0)
        initial = self.output.read_bytes()
        status, _, stderr = self.call()
        self.assertEqual(status, 2)
        self.assertIn('FileExistsError', stderr)
        self.assertEqual(self.output.read_bytes(), initial)

    def test_04_mismatched_or_forged_acceptance_claim_rejected(self):
        for name in ('d2_baud_verified', 'readvin_execution_verified',
                     'original_timing_values_read', 'client_vin_accepted'):
            data = dict(self.report)
            data[name] = True
            self.report_path.write_text(json.dumps(data), encoding='utf-8')
            status, _, stderr = self.call()
            self.assertEqual(status, 2)
            self.assertNotIn('SecretName', stderr)
            self.assertFalse(self.output.exists())

    def test_05_input_aliases_and_source_output_alias_rejected(self):
        for args in (["--readvin-report", str(self.report_path)],
                     ["--output", str(self.report_path)]):
            status, _, _ = self.call(*args)
            self.assertEqual(status, 2)
            self.assertFalse(self.output.exists())

    def test_06_modified_source_after_manifest_fails_downstream(self):
        self.assertEqual(self.call()[0], 0)
        self.report_path.write_bytes(self.report_path.read_bytes() + b'\n')
        out = self.folder / 'summary.json'
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(summary.main(['--dicetiming-report', str(self.report_path),
                                           '--bundle-manifest', str(self.output),
                                           '--output', str(out)]), 2)
        self.assertFalse(out.exists())

    def test_07_invalid_json_duplicate_keys_and_nan_rejected(self):
        for bad in ('{"schema_version":1,"schema_version":2}', '{"x": NaN}'):
            self.report_path.write_text(bad, encoding='utf-8')
            self.assertEqual(self.call()[0], 2)
            self.assertFalse(self.output.exists())

    def test_08_no_report_rejected_without_output(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(mod.main(['--output', str(self.output)]), 2)
        self.assertFalse(self.output.exists())

    def test_09_symlink_report_rejected(self):
        target = self.folder / 'original.json'
        self.report_path.rename(target)
        try:
            self.report_path.symlink_to(target)
        except OSError:
            self.skipTest('symlinks not enabled')
        self.assertEqual(self.call()[0], 2)
        self.assertFalse(self.output.exists())

    def test_10_owner_only_mode_on_posix(self):
        self.assertEqual(self.call()[0], 0)
        if os.name == 'posix':
            self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)

    def test_11_multiple_valid_reports_get_distinct_exact_sha256(self):
        second = self.folder / 'second.json'
        # Compare report is a static redacted count comparison with matched totals.
        report = {
            'schema_version': 'virtualcar-vida-dicetiming-count-compare-v1',
            'status': 'aggregate_count_comparison_only',
            'database': 'DiceTiming',
            'sqlite_fk_metadata_available': False,
            'schema_equivalence_verified': False,
            'same_installation_provenance_verified': False,
            'referential_rows_verified': False,
            'timing_profile_link_verified': False,
            'original_timing_values_read': False,
            'd2_baud_verified': False,
            'readvin_execution_verified': False,
            'client_vin_accepted': False,
            'replay_approved': False,
            'sqlite_table_count': 1, 'sqlserver_table_count': 1,
            'sqlite_column_count': 1, 'sqlserver_column_count': 1,
            'sqlserver_declared_fk_column_count': 0,
            'table_counts_equal': True,
            'column_counts_equal': True,
            'aggregate_counts_equal': True,
            'visible_schema_hmac_comparison': 'not_tested',
            'visible_schema_hmac_equal': None,
        }
        second.write_text(json.dumps(report), encoding='utf-8')
        status, _, _ = self.call('--dicetiming-compare-report', str(second))
        self.assertEqual(status, 0)
        manifest = json.loads(self.output.read_text())
        self.assertEqual(set(manifest['reports']), {'dicetiming', 'dicetiming_compare'})
        self.assertNotEqual(manifest['reports']['dicetiming'],
                            manifest['reports']['dicetiming_compare'])

    def test_12_does_not_create_manifest_inside_checkout(self):
        checkout = Path(mod.__file__).resolve().parents[2]
        destination = checkout / 'unsafe.manifest.json'
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(mod.main(['--dicetiming-report', str(self.report_path),
                                       '--output', str(destination)]), 2)
        self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
