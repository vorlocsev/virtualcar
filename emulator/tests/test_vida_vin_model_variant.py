import copy
import json
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import vida_vin_model_variant as m

VIN = 'YV1CZ000290000001'
PG = 1002


def doc(name, cols, values, full=True):
    return {'schema_version': m.SCHEMA, 'source_database': 'BaseData',
            'source_schema': 'dbo', 'source_table': name,
            'original_names_and_driver_values_not_anonymized': True,
            'vehicle_runtime_verified': False, 'same_installation_provenance_verified': False,
            'columns': [{'name': c} for c in cols], 'rows': [values], 'row_count': 1,
            'full_table_extracted_within_row_limit': full,
            **({} if full else {'selection_scope':'filtered_subset_only',
                'filtered_subset_complete_within_row_limit': True,
                'full_table_row_count_verified': False})}


def fixtures():
    models = doc('VINDecodeModel', m.REQUIRED['VINDecodeModel'],
                 [1,3,'YV1',275,2009,PG,0,999999,10,'9'])
    variants = doc('VINDecodeVariant', m.REQUIRED['VINDecodeVariant'],
                   [4,5,'CZ',275,2009,PG,8444,80])
    return models,variants


class CandidateTests(unittest.TestCase):
    def test_01_candidates_not_identity(self):
        a,b=fixtures(); result=m.analyze(VIN,PG,a,b)
        self.assertEqual(result['model_variant_candidate_pair_count'],1)
        self.assertEqual(result['model_variant_candidate_pairs'][0]['fkVehicleModel_original'],275)
        self.assertFalse(result['client_vin_acceptance_verified'])
        self.assertFalse(result['actual_vida_decoder_algorithm_verified'])

    def test_02_wrong_partner_never_matches(self):
        a,b=fixtures(); self.assertEqual(m.analyze(VIN,1001,a,b)['model_variant_candidate_pair_count'],0)

    def test_03_wrong_model_substring(self):
        a,b=fixtures(); a['rows'][0][2]='YV4'
        self.assertEqual(m.analyze(VIN,PG,a,b)['filter_stage_counts_in_given_captures']['model_vin_substring'],0)

    def test_04_wrong_variant_substring(self):
        a,b=fixtures(); b['rows'][0][2]='CC'
        self.assertEqual(m.analyze(VIN,PG,a,b)['model_variant_candidate_pair_count'],0)

    def test_05_wrong_year(self):
        a,b=fixtures(); a['rows'][0][-1]='A'
        self.assertEqual(m.analyze(VIN,PG,a,b)['model_variant_candidate_pair_count'],0)

    def test_06_wrong_chassis(self):
        a,b=fixtures(); a['rows'][0][6]=10000
        self.assertEqual(m.analyze(VIN,PG,a,b)['model_variant_candidate_pair_count'],0)

    def test_07_nullable_year_code(self):
        a,b=fixtures(); a['rows'][0][-1]=None
        self.assertEqual(m.analyze(VIN,PG,a,b)['model_variant_candidate_pair_count'],1)

    def test_08_year_sql_positions_are_one_based(self):
        a,b=fixtures(); a['rows'][0][-2]=11
        self.assertEqual(m.analyze(VIN,PG,a,b)['model_variant_candidate_pair_count'],0)

    def test_09_variant_join_rejects_model_mismatch(self):
        a,b=fixtures(); b['rows'][0][3]=295
        self.assertEqual(m.analyze(VIN,PG,a,b)['model_variant_candidate_pair_count'],0)

    def test_10_capture_subset_negative_cannot_exclude_others(self):
        a,b=fixtures();a['full_table_extracted_within_row_limit']=False
        a['selection_scope']='filtered_subset_only';a['filtered_subset_complete_within_row_limit']=True
        a['full_table_row_count_verified']=False
        self.assertTrue(m.analyze(VIN,PG,a,b)['partial_capture_cannot_exclude_missing_rows'])

    def test_11_reject_forged_runtime_claims(self):
        a,b=fixtures();a['vehicle_runtime_verified']=True
        with self.assertRaises(m.EvidenceError):m.analyze(VIN,PG,a,b)

    def test_12_reject_invalid_types_and_ranges(self):
        a,b=fixtures();a['rows'][0][0]=0
        with self.assertRaises(m.EvidenceError):m.analyze(VIN,PG,a,b)
        a,b=fixtures();b['rows'][0][6]={'fake':'struct'}
        with self.assertRaises(m.EvidenceError):m.analyze(VIN,PG,a,b)

    def test_13_reject_bad_vin(self):
        a,b=fixtures()
        for vin in ('YV1', VIN[:10]+'I'+VIN[11:], VIN[:-1]+'A'):
            with self.subTest(vin=vin),self.assertRaises(m.EvidenceError):
                m.analyze(vin,PG,a,b)

    def test_14_cli_no_overwrite_or_echo(self):
        a,b=fixtures()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            mf,vf,vn,out=[root/n for n in ('m.json','v.json','vin.txt','out.json')]
            mf.write_text(json.dumps(a));vf.write_text(json.dumps(b));vn.write_text(VIN)
            args=['--vin-file',str(vn),'--partner-group',str(PG),
                  '--model-rows',str(mf),'--variant-rows',str(vf),'--output',str(out)]
            self.assertEqual(m.main(args),0)
            self.assertEqual(json.loads(out.read_text())['vin_original'],VIN)
            self.assertEqual(m.main(args),2)
            self.assertEqual(m.main(args[:-1]+[str(vn)]),2)

if __name__ == '__main__': unittest.main()
