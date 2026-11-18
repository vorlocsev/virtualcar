"""Synthetic-only tests: no VIDA, SQL, VIN source or J2534 access."""
import copy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import vida_vin_vehicle_profile as tool

VIN = 'YV1CZ000290000001'  # Public synthetic example, not the owner's VIN.
PARTNER = 1002
PROFILE_A = '0000000000000001'
PROFILE_B = '0000000000000002'
BASE_FIELDS = ('Id', 'FolderLevel', 'fkVehicleModel', 'fkModelYear',
               'fkPartnerGroup', 'fkEngine', 'fkTransmission', 'fkBodyStyle',
               'fkSteering', 'fkNodeECU', 'fkSpecialVehicle')


def candidates(*pairs, scope='full_within_limit'):
    pairs = pairs or ({
        'fkVehicleModel_original': 45, 'fkModelYear_original': 2009,
        'fkPartnerGroup_original': PARTNER, 'fkEngine_original': 8444,
        'fkTransmission_original': 80},)
    return {'schema_version': tool.CANDIDATE_SCHEMA, 'source_database': 'BaseData',
            'source_tables': ['dbo.VINDecodeModel', 'dbo.VINDecodeVariant'],
            'vin_original': VIN, 'partner_group_original': PARTNER,
            'model_capture_scope': scope, 'variant_capture_scope': 'full_within_limit',
            'partial_capture_cannot_exclude_missing_rows': scope != 'full_within_limit',
            'model_variant_candidate_pairs': list(pairs),
            'model_variant_candidate_pair_count': len(pairs),
            'original_values_preserved': True,
            'sql_snapshot_or_runtime_provenance_verified': False,
            'actual_vida_decoder_algorithm_verified': False,
            'vehicle_profile_engine_transmission_filter_applied': False,
            'client_vin_acceptance_verified': False, 'ecu_identity_verified': False}


def row(ident=PROFILE_A, level=3, model=45, year=2009, group=PARTNER,
        engine=8444, trans=80, body=None, steering=None, node=None, special=None):
    return [ident, level, model, year, group, engine, trans, body, steering, node, special]


def capture(*rows, full=True):
    rows = list(rows) if rows else [row()]
    return {'schema_version': tool.CAPTURE_SCHEMA, 'source_database': 'BaseData',
            'source_schema': 'dbo', 'source_table': 'VehicleProfile',
            'original_names_and_driver_values_not_anonymized': True,
            'same_installation_provenance_verified': False, 'vehicle_runtime_verified': False,
            'columns': [{'name': key} for key in BASE_FIELDS],
            'rows': rows, 'row_count': len(rows),
            'full_table_extracted_within_row_limit': full,
            **({} if full else {'selection_scope': 'filtered_subset_only',
                                'filtered_subset_complete_within_row_limit': True,
                                'full_table_row_count_verified': False})}


class OfflineProfileTests(unittest.TestCase):
    def test_01_exact_engine_transmission_candidate(self):
        r = tool.analyze(candidates(), capture())
        self.assertEqual(r['candidate_compatible_profile_count'], 1)
        self.assertEqual(r['explicit_engine_transmission_pair_matches'], 1)
        self.assertEqual(r['candidate_compatible_profile_links'][0]['original_profile_id'], PROFILE_A)
        self.assertFalse(r['client_readvin_accepted'])

    def test_02_null_generic_profile_wildcards(self):
        r = tool.analyze(candidates(), capture(row(PROFILE_B,0,45,None,None,None,None)))
        self.assertEqual(r['candidate_compatible_profile_count'], 1)
        self.assertEqual(r['explicit_engine_transmission_pair_matches'], 0)

    def test_03_wrong_model_excluded(self):
        r = tool.analyze(candidates(), capture(row(model=275)))
        self.assertEqual(r['candidate_compatible_profile_count'], 0)

    def test_04_wrong_year_excluded(self):
        r = tool.analyze(candidates(), capture(row(year=2010)))
        self.assertEqual(r['candidate_compatible_profile_count'], 0)

    def test_05_wrong_partner_excluded(self):
        r = tool.analyze(candidates(), capture(row(group=1001)))
        self.assertEqual(r['candidate_compatible_profile_count'], 0)

    def test_06_wrong_engine_excluded(self):
        r = tool.analyze(candidates(), capture(row(engine=1234)))
        self.assertEqual(r['candidate_compatible_profile_count'], 0)

    def test_07_wrong_transmission_excluded(self):
        r = tool.analyze(candidates(), capture(row(trans=6)))
        self.assertEqual(r['candidate_compatible_profile_count'], 0)

    def test_08_body_style_requires_owner_context(self):
        original = capture(row(body=3))
        unknown = tool.analyze(candidates(), original)
        self.assertEqual(unknown['candidate_compatible_profile_count'], 0)
        self.assertEqual(unknown['candidate_requires_context_profile_count'], 1)
        self.assertEqual(unknown['candidate_requires_context_profile_links'][0]['unresolved_fields'], ['fkBodyStyle'])
        known = tool.analyze(candidates(), original, body_style=3)
        self.assertEqual(known['candidate_compatible_profile_count'], 1)
        self.assertEqual(tool.analyze(candidates(), original, body_style=4)['candidate_compatible_profile_count'], 0)

    def test_09_advanced_dimension_profile_excluded(self):
        r = tool.analyze(candidates(), capture(row(node=777)))
        self.assertEqual(r['advanced_dimension_rows_excluded'], 1)
        self.assertEqual(r['candidate_compatible_profile_count'], 0)

    def test_10_missing_engine_in_candidate_is_not_exact(self):
        p=candidates();p['model_variant_candidate_pairs'][0]['fkEngine_original']=None
        r=tool.analyze(p,capture())
        self.assertEqual(r['candidate_requires_context_profile_count'],1)
        self.assertEqual(r['explicit_engine_transmission_pair_matches'],0)

    def test_11_source_scope_propagation(self):
        r=tool.analyze(candidates(scope='filtered_subset_only'),capture(full=False))
        self.assertTrue(r['source_model_variant_scope_incomplete'])
        self.assertTrue(r['profile_capture_incomplete'])
        self.assertFalse(r['full_original_vida_profile_inheritance_verified'])

    def test_12_duplicate_profile_id_rejected(self):
        with self.assertRaises(tool.ProfileEvidenceError):
            tool.analyze(candidates(),capture(row(),row()))

    def test_13_bad_original_capture_column_rejected(self):
        r=capture();r['columns'][0]['name']='not_Id'
        with self.assertRaises(tool.ProfileEvidenceError):tool.analyze(candidates(),r)

    def test_14_reject_forged_runtime_claim(self):
        for key in ('client_vin_acceptance_verified','actual_vida_decoder_algorithm_verified',
                    'ecu_identity_verified','vehicle_profile_engine_transmission_filter_applied'):
            p=candidates();p[key]=True
            with self.subTest(key=key),self.assertRaises(tool.ProfileEvidenceError):
                tool.analyze(p,capture())

    def test_15_reject_schema_and_scope_forgery(self):
        p=candidates();p['partial_capture_cannot_exclude_missing_rows']=True
        with self.assertRaises(tool.ProfileEvidenceError):tool.analyze(p,capture())
        c=capture(full=False);c['full_table_extracted_within_row_limit']=True
        with self.assertRaises(tool.ProfileEvidenceError):tool.analyze(candidates(),c)

    def test_16_distinguish_bool_from_numeric_fk(self):
        c=capture(row(engine=True))
        with self.assertRaises(tool.ProfileEvidenceError):tool.analyze(candidates(),c)

    def test_17_no_original_raw_extra_row_exposure(self):
        c=capture();c['columns'].append({'name':'SomeOwnerPrivateNotes'});c['rows'][0].append('PRIVATE_DO_NOT_PUBLISH')
        r=tool.analyze(candidates(),c)
        self.assertNotIn('PRIVATE_DO_NOT_PUBLISH',json.dumps(r))
        self.assertIn(VIN,json.dumps(r))

    def test_18_cli_exclusive_output_and_no_echo_on_error(self):
        with tempfile.TemporaryDirectory() as dir:
            root=Path(dir);p=root/'source.json';v=root/'profile.json';o=root/'report.json'
            p.write_text(json.dumps(candidates()),encoding='utf-8')
            v.write_text(json.dumps(capture()),encoding='utf-8')
            args=['--candidates',str(p),'--profiles',str(v),'--output',str(o)]
            self.assertEqual(tool.main(args),0)
            self.assertEqual(json.loads(o.read_text())['candidate_compatible_profile_count'],1)
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(tool.main(args),2)
                self.assertEqual(tool.main(['--candidates',str(p),'--profiles',str(v),'--output',str(p)]),2)
            self.assertNotIn(VIN,err.getvalue())
            self.assertNotIn('PRIVATE',err.getvalue())

    def test_19_reject_duplicate_json_key_and_nan(self):
        with tempfile.TemporaryDirectory() as dir:
            p=Path(dir)/'data.json'
            for text in ('{"x":1,"x":2}','{"x":NaN}'):
                p.write_text(text)
                with self.assertRaises(tool.ProfileEvidenceError):tool.read_json(p)

    def test_21_original_base_data_profile_hex_id_preserves_zeroes(self):
        original = '0c00c8af80205920'  # confirmed global profile ID in owner catalog
        result = tool.analyze(candidates(), capture(row(ident=original)))
        self.assertEqual(result['candidate_compatible_profile_links'][0]['original_profile_id'], original)

    def test_22_reject_numeric_carcom_id_as_base_data_id(self):
        with self.assertRaises(tool.ProfileEvidenceError):
            tool.analyze(candidates(), capture(row(ident=163119)))

    def test_23_reject_bad_profile_id_shapes(self):
        for ident in ('0x0c00c8af80205920','0c00c8af8020592', 'GGGGGGGGGGGGGGGG', '', 'aaa\nbbbbbbbbbbbb'):
            with self.subTest(identifier=ident), self.assertRaises(tool.ProfileEvidenceError):
                tool.analyze(candidates(), capture(row(ident=ident)))

    def test_25_owner_original_global_folder_level_zero_is_accepted_not_vehicle_match(self):
        original = '0c00c8af80205920'
        root = row(ident=original, level=0, model=None, year=None,
                   group=None, engine=None, trans=None, body=None)
        result = tool.analyze(candidates(), capture(root, row()))
        self.assertEqual(result['global_level0_profile_candidates_in_capture'],
                         [{'original_profile_id': original, 'original_folder_level': 0}])
        self.assertEqual(result['candidate_compatible_profile_count'], 1)
        self.assertFalse(result['global_readvin_script_selection_verified'])

    def test_26_null_model_non_global_row_does_not_fail_or_match(self):
        result = tool.analyze(candidates(), capture(row(model=None, level=1)))
        self.assertEqual(result['candidate_compatible_profile_count'], 0)
        self.assertEqual(result['global_level0_profile_candidates_in_capture'], [])

    def test_24_keep_case_of_original_hex_profile_key(self):
        original = 'ABCDEF0123456789'
        result = tool.analyze(candidates(), capture(row(ident=original)))
        self.assertEqual(result['candidate_compatible_profile_links'][0]['original_profile_id'], original)

    def test_20_unproven_same_snapshot_remains_false(self):
        r=tool.analyze(candidates(),capture())
        self.assertFalse(r['cross_export_transactional_consistency_verified'])
        self.assertFalse(r['ecu_identification_verified'])
        self.assertFalse(r['original_vida_decoder_runtime_verified'])


if __name__ == '__main__':
    unittest.main()
