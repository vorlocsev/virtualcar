"""Synthetic-only redacted Profile/Service and ReadVin static coverage checks."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_vida_profile_init_bridge import catalog, timing
from test_vida_evidence_summary import readvin
import build_vida_redacted_manifest as manifest
import vida_evidence_summary as summary
import vida_profile_init_bridge as profile_tool
import vida_profile_readvin_static_coverage as coverage


class StaticProfileReadVinCoverageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def data(self, cat=None, dt=None, rv=None):
        cat, dt, rv = cat or catalog(), dt or timing(), rv or readvin()
        digest = {k: k[0] * 64 for k in coverage.INPUTS}
        # Use distinct, syntactically valid digests for pure function tests.
        digest['catalog'] = 'a'*64
        digest['dicetiming'] = 'b'*64
        digest['profile_init'] = 'c'*64
        digest['readvin'] = 'd'*64
        p = profile_tool.bridge(cat, dt, {'catalog': digest['catalog'],
                                          'dicetiming': digest['dicetiming']})
        return cat, dt, p, rv, digest

    def files(self, cat=None, dt=None, rv=None):
        inputs = {'catalog': cat or catalog(), 'dicetiming': dt or timing(),
                  'readvin': rv or readvin()}
        paths = {}
        for kind, data in inputs.items():
            path = self.folder / (kind + '.json')
            path.write_text(json.dumps(data), encoding='utf-8')
            paths[kind] = path
        p = self.folder / 'profile_init.json'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            status = profile_tool.main(['--catalog-report', str(paths['catalog']),
                                        '--dicetiming-report', str(paths['dicetiming']),
                                        '--output', str(p)])
        self.assertEqual(status, 0)
        paths['profile_init'] = p
        return paths

    def cli_args(self, paths, output):
        return ['--catalog-report', str(paths['catalog']),
                '--dicetiming-report', str(paths['dicetiming']),
                '--profile-init-report', str(paths['profile_init']),
                '--readvin-report', str(paths['readvin']),
                '--output', str(output)]

    def run_cli(self, paths, output):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return coverage.main(self.cli_args(paths, output))

    def build_files(self, cat=None, dt=None, rv=None):
        paths = self.files(cat, dt, rv)
        coverage_path = self.folder / 'coverage.json'
        self.assertEqual(self.run_cli(paths, coverage_path), 0)
        paths['profile_readvin'] = coverage_path
        return paths

    def summary_args(self, paths, output, with_manifest=None):
        args = ['--catalog-report', str(paths['catalog']),
                '--dicetiming-report', str(paths['dicetiming']),
                '--profile-init-report', str(paths['profile_init']),
                '--readvin-report', str(paths['readvin']),
                '--profile-readvin-coverage-report', str(paths['profile_readvin']),
                '--output', str(output)]
        if with_manifest is not None:
            args += ['--bundle-manifest', str(with_manifest)]
        return args

    def test_01_complete_independent_static_coverage_never_proves_handoff(self):
        cat, dt, profile, rv, digest = self.data()
        output = coverage.analyze(cat, dt, profile, rv, digest)
        self.assertEqual(output['static_coverage'], 'present')
        self.assertEqual(output['missing_static_prerequisites'], [])
        self.assertEqual(len(output['static_prerequisites']), 4)
        self.assertTrue(all(output['static_prerequisites'].values()))
        for key in ('source_row_joins_verified', 'same_vida_installation_verified',
                    'profile_to_getscript_binding_verified',
                    'getscript_to_readvin_selection_verified', 'd2_baud_verified',
                    'runtime_readvin_execution_verified', 'client_vin_accepted',
                    'physical_j2534_verified', 'replay_approved'):
            self.assertIs(output[key], False)
        self.assertNotIn('OwnerOnly', json.dumps(output))

    def test_02_missing_middle_ecu_service_link_marks_incomplete(self):
        cat = catalog()
        table = cat['databases']['CarCom']['known_tables']['T110_Service_EcuVariant']
        table['known_columns_present'].remove('fkT111_Service')
        table['known_columns_missing'].append('fkT111_Service')
        edge = next(e for e in cat['edges'] if e['source'] == 'T110_Service_EcuVariant'
                    and e['target'] == 'T111_Service')
        edge['column_shape_present'] = False
        args = self.data(cat=cat)
        result = coverage.analyze(*args)
        self.assertEqual(result['static_coverage'], 'incomplete')
        self.assertEqual(result['missing_static_prerequisites'], ['profile_service_columns'])
        self.assertTrue(result['static_prerequisites']['readvin_declared_identity_graph'])

    def test_03_forged_readvin_runtime_or_bad_identity_graph_rejected(self):
        for mutation in ('vin_accepted_by_client', 'runtime_readvin_selected'):
            cat, dt, profile, rv, digest = self.data()
            rv[mutation] = True
            with self.subTest(mutation=mutation), self.assertRaises(summary.EvidenceError):
                coverage.analyze(cat, dt, profile, rv, digest)
        cat, dt, profile, rv, digest = self.data()
        rv['identity_output_nodes'] = 0
        with self.assertRaises(summary.EvidenceError):
            coverage.analyze(cat, dt, profile, rv, digest)

    def test_04_source_digest_input_must_have_exact_four_keys(self):
        cat, dt, profile, rv, digest = self.data()
        for invalid in ({'catalog': 'a'*64}, {**digest, 'extra': 'e'*64},
                        {**digest, 'readvin': 'A'*64}, None):
            with self.subTest(invalid=repr(invalid)[:20]), self.assertRaises(summary.EvidenceError):
                coverage.analyze(cat, dt, profile, rv, invalid)

    def test_05_cli_carries_actual_hashes_of_all_four_redacted_sources(self):
        paths = self.build_files()
        doc = json.loads(paths['profile_readvin'].read_text())
        self.assertEqual(doc['source_report_sha256'], {
            kind: hashlib.sha256(paths[kind].read_bytes()).hexdigest()
            for kind in coverage.INPUTS})
        self.assertEqual(doc['static_coverage'], 'present')
        self.assertNotIn(str(self.folder), paths['profile_readvin'].read_text())

    def test_06_cli_refuses_reused_output_and_alias_without_writing(self):
        paths = self.build_files()
        self.assertEqual(self.run_cli(paths, paths['profile_readvin']), 2)
        target = paths['catalog']
        current = target.read_bytes()
        self.assertEqual(self.run_cli(paths, target), 2)
        self.assertEqual(target.read_bytes(), current)

    def test_07_summary_passes_static_gate_but_not_getscript_runtime(self):
        paths = self.build_files()
        out = self.folder / 'summary.json'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(summary.main(self.summary_args(paths, out)), 0)
        doc = json.loads(out.read_text())
        stages = {g['id']: g['status'] for g in doc['stages']}
        self.assertEqual(stages['profile_readvin_static_prerequisites'], 'passed')
        self.assertEqual(stages['profile_to_readvin_join'], 'not_tested')
        self.assertEqual(stages['getscript_runtime_selection'], 'not_tested')
        self.assertEqual(stages['client_vin_acceptance'], 'not_tested')
        self.assertIs(doc['profile_readvin_static_coverage']['getscript_handoff_verified'], False)

    def test_08_summary_incomplete_static_gate_failed_but_runtime_not_tested(self):
        cat = catalog()
        table = cat['databases']['CarCom']['known_tables']['T110_Service_EcuVariant']
        table['known_columns_present'].remove('fkT111_Service')
        table['known_columns_missing'].append('fkT111_Service')
        edge = next(e for e in cat['edges'] if e['source'] == 'T110_Service_EcuVariant'
                    and e['target'] == 'T111_Service')
        edge['column_shape_present'] = False
        paths = self.build_files(cat=cat)
        out = self.folder / 'summary.json'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(summary.main(self.summary_args(paths, out)), 0)
        states = {g['id']: g['status'] for g in json.loads(out.read_text())['stages']}
        self.assertEqual(states['profile_readvin_static_prerequisites'], 'failed')
        self.assertEqual(states['profile_to_readvin_join'], 'not_tested')

    def test_09_forged_present_status_rejected_after_recomputed_sources(self):
        paths = self.build_files()
        tampered = json.loads(paths['profile_readvin'].read_text())
        tampered['static_coverage'] = 'incomplete'
        tampered['missing_static_prerequisites'] = ['profile_service_columns']
        tampered['static_prerequisites']['profile_service_columns'] = False
        paths['profile_readvin'].write_text(json.dumps(tampered), encoding='utf-8')
        out = self.folder / 'summary.json'
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(summary.main(self.summary_args(paths, out)), 2)
        self.assertFalse(out.exists())

    def test_10_forged_positive_runtime_flag_rejected(self):
        paths = self.build_files()
        report = json.loads(paths['profile_readvin'].read_text())
        report['profile_to_getscript_binding_verified'] = True
        paths['profile_readvin'].write_text(json.dumps(report), encoding='utf-8')
        out = self.folder / 'summary.json'
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(summary.main(self.summary_args(paths, out)), 2)
        self.assertFalse(out.exists())

    def test_11_summary_requires_all_four_sources(self):
        paths = self.build_files()
        doc = json.loads(paths['profile_readvin'].read_text())
        hashes = doc['source_report_sha256']
        cat, dt, profile, rv, _ = self.data()
        for sources in ((cat, dt, profile, None), (cat, dt, None, rv),
                        (cat, None, profile, rv)):
            with self.assertRaises(summary.EvidenceError):
                summary._static_coverage(doc, *sources, hashes)

    def test_12_generated_manifest_binds_five_report_bytes(self):
        paths = self.build_files()
        target = self.folder / 'manifest.json'
        args = self.summary_args(paths, target)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(manifest.main(args), 0)
        doc = json.loads(target.read_text())
        self.assertEqual(set(doc['reports']), set(coverage.INPUTS) | {'profile_readvin'})
        self.assertFalse(doc['runtime_evidence_verified'])
        out = self.folder / 'summary.json'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(summary.main(self.summary_args(paths, out, target)), 0)
        self.assertTrue(json.loads(out.read_text())['redacted_report_bytes_bound'])

    def test_13_modified_source_after_coverage_rejected_with_original_sha(self):
        paths = self.build_files()
        paths['readvin'].write_bytes(paths['readvin'].read_bytes() + b'\n')
        out = self.folder / 'summary.json'
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(summary.main(self.summary_args(paths, out)), 2)
        self.assertFalse(out.exists())

    def test_14_extra_private_text_cannot_be_copied_by_summary(self):
        paths = self.build_files()
        report = json.loads(paths['profile_readvin'].read_text())
        report['PRIVATE_VIN_TEXT'] = 'SYNTHETIC_SECRET_VIN'
        paths['profile_readvin'].write_text(json.dumps(report), encoding='utf-8')
        out = self.folder / 'summary.json'
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(summary.main(self.summary_args(paths, out)), 2)
        self.assertNotIn('SYNTHETIC_SECRET_VIN', err.getvalue())
        self.assertFalse(out.exists())

    def test_15_legacy_summary_without_coverage_keeps_stage_not_tested(self):
        result = summary.assemble(catalog=catalog(), readvin=readvin())
        gates = {g['id']: g['status'] for g in result['stages']}
        self.assertEqual(gates['profile_readvin_static_prerequisites'], 'not_tested')
        self.assertEqual(gates['profile_to_readvin_join'], 'not_tested')

    def test_16_rejected_symlink_report(self):
        paths = self.files()
        source = paths['readvin']
        actual = self.folder / 'readvin-original.json'
        source.rename(actual)
        try:
            source.symlink_to(actual)
        except OSError:
            self.skipTest('symlinks unsupported by current filesystem')
        target = self.folder / 'coverage.json'
        self.assertEqual(self.run_cli(paths, target), 2)
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
