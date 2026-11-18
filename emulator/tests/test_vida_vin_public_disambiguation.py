"""Synthetic tests for public source reconstruction; no owner's original VIDA."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import vida_vin_public_disambiguation as a

VIN = 'YV1CZ000290000001'
PARTNER = 1002
FIELDS = ['Id', 'fkVehicleModel', 'fkModelYear', 'fkEngine', 'fkTransmission']


def pair(model=44, year=2009, group=PARTNER, engine=8400, transmission=80):
    return {'fkVehicleModel_original': model, 'fkModelYear_original': year,
            'fkPartnerGroup_original': group, 'fkEngine_original': engine,
            'fkTransmission_original': transmission}


def candidates(*pairs, partial=False):
    return {'schema_version': a.CANDIDATE_SCHEMA,
            'vin_original': VIN, 'partner_group_original': PARTNER,
            'source_database': 'BaseData',
            'source_tables': ['dbo.VINDecodeModel', 'dbo.VINDecodeVariant'],
            'original_values_preserved': True,
            'sql_snapshot_or_runtime_provenance_verified': False,
            'actual_vida_decoder_algorithm_verified': False,
            'vehicle_profile_engine_transmission_filter_applied': False,
            'client_vin_acceptance_verified': False, 'ecu_identity_verified': False,
            'model_capture_scope': 'filtered_subset_only' if partial else 'full_within_limit',
            'variant_capture_scope': 'full_within_limit',
            'partial_capture_cannot_exclude_missing_rows': partial,
            'model_variant_candidate_pairs': list(pairs),
            'model_variant_candidate_pair_count': len(pairs)}


def capture(*rows, partial=False):
    return {'schema_version': a.TABLE_SCHEMA, 'source_database': 'BaseData',
            'source_schema': 'dbo', 'source_table': 'VehicleProfile',
            'original_names_and_driver_values_not_anonymized': True,
            'same_installation_provenance_verified': False,
            'vehicle_runtime_verified': False,
            'columns': [{'name': k} for k in FIELDS],
            'rows': list(rows), 'row_count': len(rows),
            'full_table_extracted_within_row_limit': not partial,
            **({'selection_scope': 'filtered_subset_only',
                'filtered_subset_complete_within_row_limit': True,
                'full_table_row_count_verified': False} if partial else {})}


class PublicDecoderSemanticTests(unittest.TestCase):
    def test_01_single_candidate_skips_profile_check(self):
        r = a.analyze(candidates(pair()), capture())
        self.assertEqual(r['public_filtered_candidate_count'], 1)
        self.assertFalse(r['public_profile_filter_triggered'])
        self.assertFalse(r['readvin_gui_acceptance_verified'])

    def test_02_multiple_candidates_trigger_exact_profile_filter(self):
        r = a.analyze(candidates(pair(transmission=80), pair(transmission=81)),
                      capture([1, 44, 2009, 8400, 80]))
        self.assertEqual(r['distinct_cross_join_candidate_count'], 2)
        self.assertEqual(r['public_filtered_candidate_count'], 1)
        self.assertEqual(r['candidate_combinations_original'][0]['profile_match_ids_original'], [1])

    def test_03_null_generic_profile_does_not_pass_exact_second_filter(self):
        r = a.analyze(candidates(pair(transmission=80), pair(transmission=81)),
                      capture([1, 44, 2009, None, None]))
        self.assertEqual(r['public_filtered_candidate_count'], 0)

    def test_04_cross_key_source_mixing_is_flagged(self):
        r = a.analyze(candidates(pair(model=44, transmission=80),
                                 pair(model=55, transmission=81)),
                      capture([1, 44, 2009, 8400, 81]))
        self.assertGreater(r['source_cross_key_pair_count'], 0)
        self.assertTrue(any(q['only_cross_key_origin_observed'] for q in r['candidate_combinations_original']))
        self.assertFalse(r['public_decoder_equivalence_verified'])

    def test_05_no_engine_yields_zero(self):
        r = a.analyze(candidates(pair(engine=None, transmission=80)), capture())
        self.assertEqual(r['public_filtered_candidate_count'], 0)

    def test_06_all_null_transmission_keeps_null(self):
        r = a.analyze(candidates(pair(transmission=None)), capture())
        self.assertEqual(r['public_filtered_candidate_count'], 1)
        self.assertIsNone(r['candidate_combinations_original'][0]['fkTransmission_original'])

    def test_07_some_transmissions_excludes_null_transmission_branch(self):
        r = a.analyze(candidates(pair(engine=8400,transmission=None),
                                 pair(engine=8401,transmission=80)),
                      capture([1,44,2009,8400,80],[2,44,2009,8401,80]))
        self.assertTrue(all(q['fkTransmission_original'] is not None for q in r['candidate_combinations_original']))

    def test_08_null_transmission_public_filter_matches_any_same_model_year_profile(self):
        r = a.analyze(candidates(pair(engine=8400,transmission=None),
                                 pair(engine=8401,transmission=None)),
                      capture([1,44,2009,9999,55]))
        self.assertEqual(r['public_filtered_candidate_count'], 2)

    def test_09_wrong_model_year_profile_excluded(self):
        r = a.analyze(candidates(pair(engine=8400,transmission=80),
                                 pair(engine=8401,transmission=80)),
                      capture([1,44,2010,8400,80]))
        self.assertEqual(r['public_filtered_candidate_count'], 0)

    def test_10_filtered_capture_preserves_warning(self):
        r = a.analyze(candidates(pair(),partial=True),capture(partial=True))
        self.assertTrue(r['model_variant_capture_incomplete'])
        self.assertEqual(r['vehicle_profile_capture_scope'],'filtered_subset_only')
        self.assertFalse(r['original_vida_decoder_runtime_verified'])

    def test_11_distinct_cross_product_removes_duplicates(self):
        r = a.analyze(candidates(pair(),pair()),capture())
        self.assertEqual(r['distinct_cross_join_candidate_count'],1)
        self.assertEqual(r['source_cross_join_pair_count'],4)

    def test_12_critical_data_retained_only_local(self):
        r = a.analyze(candidates(pair()),capture())
        self.assertEqual(r['vin_original'], VIN)
        self.assertFalse(r['ecu_identification_verified'])

    def test_13_invalid_numeric_boolean_rejected(self):
        with self.assertRaises(a.OfflineEvidenceError):
            a.analyze(candidates(pair(model=True)),capture())

    def test_14_wrong_table_rejected(self):
        c = capture(); c['source_table'] = 'VINDecodeVariant'
        with self.assertRaises(a.OfflineEvidenceError):
            a.analyze(candidates(pair()),c)

    def test_15_fake_runtime_success_rejected(self):
        c = candidates(pair());c['client_vin_acceptance_verified']=True
        with self.assertRaises(a.OfflineEvidenceError):a.analyze(c,capture())

    def test_16_public_multi_model_warning_branch(self):
        r = a.analyze(candidates(pair(model=44),pair(model=55)),
                      capture([1,44,2009,8400,80],[2,55,2009,8400,80]))
        self.assertEqual(r['public_branch_in_available_inputs'],
                         'multiple_vehicle_models_in_remaining_candidates')

    def test_17_cli_exclusive_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp); cp=path/'candidate.json';pp=path/'profile.json';out=path/'out.json'
            cp.write_text(json.dumps(candidates(pair())), encoding='utf-8')
            pp.write_text(json.dumps(capture()),encoding='utf-8')
            argv=['--candidates',str(cp),'--profiles',str(pp),'--output',str(out)]
            self.assertEqual(a.main(argv),0)
            with contextlib.redirect_stderr(io.StringIO()) as e:
                self.assertEqual(a.main(argv),2)
                self.assertEqual(a.main(argv[:-1]+[str(cp)]),2)
            self.assertNotIn(VIN,e.getvalue())

    def test_18_duplicate_json_nan_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'data.json'
            for raw in ('{"id":1,"id":2}', '{"id":NaN}'):
                path.write_text(raw,encoding='utf-8')
                with self.assertRaises(a.OfflineEvidenceError):a.read_json(path)

    def test_19_no_source_input_mutations(self):
        m = candidates(pair(transmission=80),pair(transmission=81))
        p = capture([1,44,2009,8400,80])
        before=(json.dumps(m),json.dumps(p))
        a.analyze(m,p)
        self.assertEqual((json.dumps(m),json.dumps(p)),before)

    def test_20_cli_no_private_echo_on_failed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp); cp=path/'PRIVATE_VIN_FILE.json';pp=path/'p.json';out=path/'o.json'
            cp.write_text('corrupt owner VIN !',encoding='utf-8')
            pp.write_text(json.dumps(capture()),encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()) as e:
                self.assertEqual(a.main(['--candidates',str(cp),'--profiles',str(pp),'--output',str(out)]),2)
            self.assertNotIn('PRIVATE_VIN_FILE',e.getvalue())
            self.assertFalse(out.exists())


if __name__=='__main__':
    unittest.main()
