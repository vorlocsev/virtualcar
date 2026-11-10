"""Synthetic-only profile -> InitHw hints and DiceTiming bridge security tests."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import audit_vida_carcom_schema_links as hints
import vida_dicetiming_catalog as dice
import vida_evidence_summary as summary
import vida_profile_init_bridge as bridge
import build_vida_redacted_manifest as manifest_builder


def catalog():
    dbs = {}
    for database, tables in hints.TABLES.items():
        entries = {name: {
            'present': True, 'column_count': max(1, len(columns)),
            'known_columns_present': list(columns), 'known_columns_missing': [],
        } for name, columns in tables.items()}
        dbs[database] = {'known_tables': entries, 'table_count': max(1, len(entries)),
                         'column_count': sum(x['column_count'] for x in entries.values()),
                         'declared_fk_column_count': 0}
    edges = []
    for kind, group in (('service_shape', hints.CANDIDATE_EDGES),
                        ('hardware_shape', hints.HARDWARE_CANDIDATE_EDGES)):
        for db, src, sc, dst, dc in group:
            edges.append({'database': db, 'source': src, 'source_column': sc,
                          'target': dst, 'target_column': dc,
                          'evidence': kind, 'column_shape_present': True,
                          'referential_rows_verified': False})
    negative = {field: False for field in summary.CATALOG_NEGATIVE}
    return {
        'schema_version': 'virtualcar-vida-unified-catalog-v1',
        'status': 'metadata_only', 'backend': 'sqlite-export',
        'databases': dbs, 'edges': edges, **negative,
    }


def timing():
    return dice._finish({('dbo', 'OwnerOnly'): {'timing_value'}}, 0, 'sqlite-export')


class ProfileBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def test_01_profile_init_route_candidate_is_not_actual_value_or_join(self):
        report = bridge.bridge(catalog(), timing())
        self.assertEqual(report['profile_init_shape'], 'candidate_shape')
        self.assertEqual(report['service_protocol_shape'], 'candidate_shape')
        self.assertTrue(report['dicetiming_metadata_checked'])
        self.assertFalse(report['dicetiming_to_carcom_join_verified'])
        self.assertFalse(report['selected_ecu_profile_verified'])
        self.assertFalse(report['inherited_init_hw_values_verified'])
        self.assertFalse(report['d2_baud_verified'])
        self.assertFalse(report['client_vin_accepted'])
        self.assertNotIn('OwnerOnly', json.dumps(report))

    def test_02_missing_folder_priority_does_not_promote_route(self):
        src = catalog()
        table = src['databases']['CarCom']['known_tables']['T161_Profile']
        table['known_columns_present'].remove('folderLevel')
        table['known_columns_missing'].append('folderLevel')
        result = bridge.bridge(src, timing())
        self.assertEqual(result['profile_init_shape'], 'incomplete_shape')
        self.assertEqual(result['service_protocol_shape'], 'candidate_shape')
        self.assertGreater(result['missing_public_hints']['profile_init'], 0)

    def test_03_missing_hw_edge_shape_corresponds_to_missing_column(self):
        src = catalog()
        table = src['databases']['CarCom']['known_tables']['T136_InitHw_Profile']
        table['known_columns_present'].remove('fkT130_Init')
        table['known_columns_missing'].append('fkT130_Init')
        edge = next(x for x in src['edges'] if x['evidence'] == 'hardware_shape'
                    and x['source'] == 'T136_InitHw_Profile' and x['target'] == 'T130_Init')
        edge['column_shape_present'] = False
        result = bridge.bridge(src, timing())
        self.assertEqual(result['profile_init_shape'], 'incomplete_shape')

    def test_04_forged_edge_true_rejected_when_column_missing(self):
        src = catalog()
        table = src['databases']['CarCom']['known_tables']['T136_InitHw_Profile']
        table['known_columns_present'].remove('fkT130_Init')
        table['known_columns_missing'].append('fkT130_Init')
        with self.assertRaises(summary.EvidenceError):
            bridge.bridge(src, timing())

    def test_05_missing_or_duplicated_required_edges_rejected(self):
        src = catalog()
        src['edges'].pop()
        with self.assertRaises(summary.EvidenceError):
            bridge.bridge(src, timing())
        src = catalog()
        src['edges'].append(copy.deepcopy(src['edges'][0]))
        with self.assertRaises(summary.EvidenceError):
            bridge.bridge(src, timing())

    def test_06_wrong_report_schema_and_positive_d2_flags_rejected(self):
        t = timing()
        t['d2_baud_verified'] = True
        with self.assertRaises(summary.EvidenceError):
            bridge.bridge(catalog(), t)
        t = timing()
        t['schema_version'] = 'private'
        with self.assertRaises(summary.EvidenceError):
            bridge.bridge(catalog(), t)

    def test_07_forged_carcom_row_acceptance_rejected(self):
        src = catalog()
        src['edges'][0]['referential_rows_verified'] = True
        with self.assertRaises(summary.EvidenceError):
            bridge.bridge(src, timing())

    def test_08_untrusted_column_set_and_type_rejected(self):
        for bad in (['id', 'id'], ['id', 'SECRET_NAME'], [['bad_list']]):
            src = catalog()
            src['databases']['CarCom']['known_tables']['T101_Ecu']['known_columns_present'] = bad
            with self.subTest(bad=repr(bad)), self.assertRaises(summary.EvidenceError):
                bridge.bridge(src, timing())

    def test_09_no_private_source_strings_in_output(self):
        src = catalog()
        src['private_secret'] = 'VIN_SECRET_XX'
        result = bridge.bridge(src, timing())
        self.assertNotIn('VIN_SECRET', json.dumps(result))
        self.assertEqual(result['missing_public_hints'], {'profile_init': 0,
                                                           'service_protocol': 0})

    def test_10_cli_works_on_redacted_files_with_new_exclusive_output(self):
        cat_path = self.folder / 'cat.json'
        dice_path = self.folder / 'dice.json'
        output = self.folder / 'shape.json'
        cat_path.write_text(json.dumps(catalog()), encoding='utf-8')
        dice_path.write_text(json.dumps(timing()), encoding='utf-8')
        args = ['--catalog-report', str(cat_path),
                '--dicetiming-report', str(dice_path), '--output', str(output)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(bridge.main(args), 0)
            self.assertEqual(bridge.main(args), 2)
        self.assertFalse(json.loads(output.read_text())['replay_approved'])

    def test_11_cli_rejects_input_output_alias_and_invalid_source(self):
        cat_path = self.folder / 'cat.json'
        dice_path = self.folder / 'dice.json'
        cat_path.write_text(json.dumps(catalog()), encoding='utf-8')
        dice_path.write_text(json.dumps(timing()), encoding='utf-8')
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(bridge.main(['--catalog-report', str(cat_path),
                                          '--dicetiming-report', str(dice_path),
                                          '--output', str(cat_path)]), 2)
            self.assertEqual(bridge.main(['--catalog-report', str(cat_path),
                                          '--dicetiming-report', str(cat_path),
                                          '--output', str(self.folder / 'failed.json')]), 2)
        self.assertFalse((self.folder / 'failed.json').exists())


    def _write_inputs(self):
        cat_path = self.folder / 'catalog.json'
        dic_path = self.folder / 'dicetiming.json'
        cat_path.write_text(json.dumps(catalog()), encoding='utf-8')
        dic_path.write_text(json.dumps(timing()), encoding='utf-8')
        return cat_path, dic_path

    def _run_bridge(self):
        cat_path, dic_path = self._write_inputs()
        bridge_path = self.folder / 'profile-bridge.json'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(bridge.main(['--catalog-report', str(cat_path),
                                          '--dicetiming-report', str(dic_path),
                                          '--output', str(bridge_path)]), 0)
        return cat_path, dic_path, bridge_path

    def test_12_cli_bridge_carries_exact_redacted_source_digests(self):
        cat_path, dic_path, path = self._run_bridge()
        report = json.loads(path.read_text())
        self.assertEqual(report['source_report_sha256']['catalog'],
                         hashlib.sha256(cat_path.read_bytes()).hexdigest())
        self.assertEqual(report['source_report_sha256']['dicetiming'],
                         hashlib.sha256(dic_path.read_bytes()).hexdigest())
        self.assertFalse(report['dicetiming_to_carcom_join_verified'])

    def test_13_summary_checks_bridge_binding_and_keeps_join_unverified(self):
        cat_path, dic_path, bridge_path = self._run_bridge()
        output = self.folder / 'summary.json'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(summary.main(['--catalog-report', str(cat_path),
                                          '--dicetiming-report', str(dic_path),
                                          '--profile-init-report', str(bridge_path),
                                          '--output', str(output)]), 0)
        result = json.loads(output.read_text())
        gates = {item['id']: item['status'] for item in result['stages']}
        self.assertEqual(gates['carcom_profile_init_shape'], 'passed')
        self.assertEqual(gates['carcom_service_protocol_shape'], 'passed')
        self.assertEqual(gates['dicetiming_to_carcom_row_join'], 'not_tested')
        self.assertTrue(result['profile_init_metadata_bridge']['redacted_report_byte_binding_verified'])
        self.assertFalse(result['dice_timing_profile_mapping_verified'])

    def test_14_manifest_generator_checks_bridge_and_source_inputs(self):
        cat_path, dic_path, bridge_path = self._run_bridge()
        manifest = self.folder / 'manifest.json'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(manifest_builder.main(['--catalog-report', str(cat_path),
                      '--dicetiming-report', str(dic_path),
                      '--profile-init-report', str(bridge_path),
                      '--output', str(manifest)]), 0)
        bundle = json.loads(manifest.read_text())
        self.assertEqual(set(bundle['reports']), {'catalog', 'dicetiming', 'profile_init'})
        out = self.folder / 'summary.json'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(summary.main(['--catalog-report', str(cat_path),
                '--dicetiming-report', str(dic_path), '--profile-init-report', str(bridge_path),
                '--bundle-manifest', str(manifest), '--output', str(out)]), 0)
        self.assertTrue(json.loads(out.read_text())['redacted_report_bytes_bound'])

    def test_15_replaced_source_bytes_fail_closed_even_valid_structure(self):
        cat_path, dic_path, bridge_path = self._run_bridge()
        cat_path.write_bytes(cat_path.read_bytes() + b'\n')
        out = self.folder / 'failed.json'
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(summary.main(['--catalog-report', str(cat_path),
                '--dicetiming-report', str(dic_path), '--profile-init-report', str(bridge_path),
                '--output', str(out)]), 2)
        self.assertFalse(out.exists())

    def test_16_forged_bridge_true_claim_and_inconsistent_count_rejected(self):
        cat_path, dic_path, bridge_path = self._run_bridge()
        valid = json.loads(bridge_path.read_text())
        for field, value in [('dicetiming_to_carcom_join_verified', True),
                             ('inherited_init_hw_values_verified', True),
                             ('profile_init_shape', 'candidate_shape')]:
            report = dict(valid)
            if field == 'profile_init_shape':
                report['missing_public_hints'] = {'profile_init': 1,
                                                   'service_protocol': 0}
            else:
                report[field] = value
            with self.subTest(field=field), self.assertRaises(summary.EvidenceError):
                summary._profile_bridge(report, valid['source_report_sha256'])

    def test_17_bridge_requires_both_original_report_digests(self):
        cat_path, dic_path, bridge_path = self._run_bridge()
        report = json.loads(bridge_path.read_text())
        with self.assertRaises(summary.EvidenceError):
            summary._profile_bridge(report, {'catalog': report['source_report_sha256']['catalog']})
        with self.assertRaises(summary.EvidenceError):
            summary._profile_bridge(report, {'catalog': '0'*64,
                 'dicetiming': report['source_report_sha256']['dicetiming']})
        report['source_report_sha256'] = None
        with self.assertRaises(summary.EvidenceError):
            summary._profile_bridge(report, {'catalog': '0'*64, 'dicetiming': '0'*64})


    def test_18_forged_passed_shape_with_valid_source_digest_rejected(self):
        cat = catalog()
        shape = cat['databases']['CarCom']['known_tables']['T161_Profile']
        shape['known_columns_present'].remove('folderLevel')
        shape['known_columns_missing'].append('folderLevel')
        digests = {'catalog': 'a'*64, 'dicetiming': 'b'*64}
        report = bridge.bridge(cat, timing(), digests)
        self.assertEqual(report['profile_init_shape'], 'incomplete_shape')
        report['profile_init_shape'] = 'candidate_shape'
        report['missing_public_hints']['profile_init'] = 0
        with self.assertRaisesRegex(summary.EvidenceError, 'differs from source'):
            summary.assemble(catalog=cat, dice_timing=timing(), profile_bridge=report,
                             input_digests=digests)

    def test_19_genuine_incomplete_shape_is_failed_not_fake_passed(self):
        cat = catalog()
        shape = cat['databases']['CarCom']['known_tables']['T161_Profile']
        shape['known_columns_present'].remove('folderLevel')
        shape['known_columns_missing'].append('folderLevel')
        digests = {'catalog': 'c'*64, 'dicetiming': 'd'*64}
        report = bridge.bridge(cat, timing(), digests)
        result = summary.assemble(catalog=cat, dice_timing=timing(),
                                  profile_bridge=report, input_digests=digests)
        states = {x['id']: x['status'] for x in result['stages']}
        self.assertEqual(states['carcom_profile_init_shape'], 'failed')
        self.assertEqual(states['carcom_service_protocol_shape'], 'passed')
        self.assertEqual(states['dicetiming_to_carcom_row_join'], 'not_tested')

    def test_20_forged_service_bus_shape_with_valid_hash_rejected(self):
        cat = catalog()
        shape = cat['databases']['CarCom']['known_tables']['T121_Config']
        shape['known_columns_present'].remove('busRate')
        shape['known_columns_missing'].append('busRate')
        digests = {'catalog': 'e'*64, 'dicetiming': 'f'*64}
        report = bridge.bridge(cat, timing(), digests)
        self.assertEqual(report['service_protocol_shape'], 'incomplete_shape')
        report['service_protocol_shape'] = 'candidate_shape'
        report['missing_public_hints']['service_protocol'] = 0
        with self.assertRaisesRegex(summary.EvidenceError, 'differs from source'):
            summary.assemble(catalog=cat, dice_timing=timing(), profile_bridge=report,
                             input_digests=digests)

    def test_21_extraneous_unreviewed_report_fields_fail_closed(self):
        cat, dic = catalog(), timing()
        digests = {'catalog': 'a'*64, 'dicetiming': 'b'*64}
        report = bridge.bridge(cat, dic, digests)
        report['PRIVATE_VIN'] = 'SECRET_NOT_FOR_OUTPUT'
        with self.assertRaisesRegex(summary.EvidenceError, 'differs from source') as err:
            summary.assemble(catalog=cat, dice_timing=dic, profile_bridge=report,
                             input_digests=digests)
        self.assertNotIn('SECRET_NOT_FOR_OUTPUT', str(err.exception))

    def test_22_source_content_is_mandatory_not_only_hashes(self):
        cat, dic = catalog(), timing()
        digests = {'catalog': 'a'*64, 'dicetiming': 'b'*64}
        report = bridge.bridge(cat, dic, digests)
        with self.assertRaisesRegex(summary.EvidenceError, 'source content missing'):
            summary.assemble(profile_bridge=report, input_digests=digests)
        with self.assertRaisesRegex(summary.EvidenceError, 'source content missing'):
            summary.assemble(catalog=cat, profile_bridge=report, input_digests=digests)

    def test_23_genuine_complete_bridge_remains_accepted(self):
        cat, dic = catalog(), timing()
        digests = {'catalog': 'a'*64, 'dicetiming': 'b'*64}
        report = bridge.bridge(cat, dic, digests)
        result = summary.assemble(catalog=cat, dice_timing=dic,
                                  profile_bridge=report, input_digests=digests)
        self.assertEqual(result['profile_init_metadata_bridge']['profile_init_shape'],
                         'candidate_shape')
        self.assertFalse(result['dice_timing_profile_mapping_verified'])
        self.assertEqual(next(x['status'] for x in result['stages']
                              if x['id'] == 'dicetiming_to_carcom_row_join'), 'not_tested')

    def test_24_forged_bridge_with_recalculated_hash_rejected_in_cli_and_manifest(self):
        cat_path, dic_path, bridge_path = self._run_bridge()
        cat = json.loads(cat_path.read_text())
        shape = cat['databases']['CarCom']['known_tables']['T161_Profile']
        shape['known_columns_present'].remove('folderLevel')
        shape['known_columns_missing'].append('folderLevel')
        cat_path.write_text(json.dumps(cat), encoding='utf-8')
        forged = json.loads(bridge_path.read_text())
        forged['source_report_sha256']['catalog'] = hashlib.sha256(cat_path.read_bytes()).hexdigest()
        # The forged Passed status stays internally consistent with its counter.
        self.assertEqual(forged['profile_init_shape'], 'candidate_shape')
        self.assertEqual(forged['missing_public_hints']['profile_init'], 0)
        bridge_path.write_text(json.dumps(forged), encoding='utf-8')
        output = self.folder / 'must-not-exist.json'
        inputs = ['--catalog-report', str(cat_path), '--dicetiming-report', str(dic_path),
                  '--profile-init-report', str(bridge_path), '--output', str(output)]
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(summary.main(inputs), 2)
            self.assertEqual(manifest_builder.main(inputs), 2)
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
