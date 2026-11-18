"""Synthetic-only evidence and fail-closed tests; no original VIDA files."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import vida_partner_group_catalog as mod


def schema():
    names = ['VinStartPos', 'VinEndPos', 'VinCompare', 'fkPartnerGroup',
             'fkModelYear', 'YearCode', 'ChassisNoFrom', 'ChassisNoTo']
    return {'schema_version': mod.SCHEMA_FORMAT, 'source_database': 'BaseData',
            'original_identifiers_preserved': True, 'original_user_rows_read': False,
            'runtime_readvin_verified': False,
            'tables': [{'schema': 'dbo', 'name': 'VINDecodeModel',
                        'columns': [{'name': n, 'column_id': i+1} for i,n in enumerate(names)]}],
            'foreign_keys': [{'source_schema': 'dbo', 'source_table': 'VINDecodeModel',
                              'referenced_schema': 'dbo', 'referenced_table': 'PartnerGroup',
                              'columns': [{'source': 'fkPartnerGroup', 'referenced': 'id', 'ordinal': 1}]}]}


def rows(full=True):
    cols = schema()['tables'][0]['columns']
    return {'schema_version': mod.TABLE_FORMAT, 'source_database': 'BaseData',
            'source_schema': 'dbo', 'source_table': 'VINDecodeModel',
            'original_names_and_driver_values_not_anonymized': True,
            'same_installation_provenance_verified': False,
            'vehicle_runtime_verified': False,
            'columns': cols, 'rows': [[1, 3, 'YV1', 1002, 2009, '9', 0, 999999],
                                     [1, 3, 'YV1', 1001, 2009, '9', 0, 999999],
                                     [1, 3, 'YV1', 1002, 2010, 'A', 0, 999999]],
            'row_count': 3, 'full_table_extracted_within_row_limit': full,
            **({} if full else {'selection_scope': 'filtered_subset_only',
                                 'filtered_subset_complete_within_row_limit': True,
                                 'full_table_row_count_verified': False})}


def context(value=1002):
    return {'schema_version': mod.CONTEXT_FORMAT, 'fkPartnerGroup_original': value}


class CatalogEvidenceTests(unittest.TestCase):
    def test_01_catalog_only_does_not_assume_rows_or_coverage(self):
        result = mod.inspect(schema())
        self.assertTrue(result['table_found_in_visible_catalog'])
        self.assertEqual(result['source_scope'], 'schema_only')
        self.assertIsNone(result['capture_row_count'])
        self.assertFalse(result['vin_match_verified'])

    def test_02_catalog_without_table_is_unknown_not_failed_decode(self):
        s = schema()
        s['tables'][0]['name'] = 'SomeOtherTable'
        result = mod.inspect(s)
        self.assertFalse(result['table_found_in_visible_catalog'])
        self.assertFalse(result['vida_gui_vin_accepted'])

    def test_03_full_capture_group_exact_values(self):
        result = mod.inspect(schema(), rows(), context())
        self.assertEqual(result['selected_group_rows_in_this_capture'], 2)
        self.assertEqual(result['selected_partner_group_original'], 1002)
        self.assertEqual(sum(x['observed_rows'] for x in result['fkPartnerGroup_observed_row_counts']), 3)
        self.assertFalse(result['vin_decode_semantics_verified'])

    def test_04_string_and_number_group_not_conflated(self):
        r = rows()
        r['rows'][0][3] = '1002'
        out = mod.inspect(schema(), r, context())
        self.assertEqual(out['selected_group_rows_in_this_capture'], 1)
        self.assertEqual(len(out['fkPartnerGroup_observed_row_counts']), 3)

    def test_05_filtered_subset_does_not_claim_full_coverage(self):
        result = mod.inspect(schema(), rows(False), context(9999))
        self.assertEqual(result['source_scope'], 'filtered_subset_only')
        self.assertEqual(result['selected_group_rows_in_this_capture'], 0)
        self.assertFalse(result['vin_match_verified'])

    def test_06_catalog_and_capture_column_mismatch_rejected(self):
        c = rows()
        c['columns'][0]['name'] = 'OtherField'
        with self.assertRaises(mod.CatalogEvidenceError):
            mod.inspect(schema(), c)

    def test_07_contradictory_source_claims_rejected(self):
        bads = []
        s = schema(); s['runtime_readvin_verified'] = True; bads.append((s, rows()))
        r = rows(); r['vehicle_runtime_verified'] = True; bads.append((schema(), r))
        r = rows(False); r['full_table_extracted_within_row_limit'] = True; bads.append((schema(),r))
        r = rows(); r['row_count'] = 2; bads.append((schema(),r))
        r = rows(); r['rows'][0].append('bad'); bads.append((schema(),r))
        for a, b in bads:
            with self.subTest(a=a.get('runtime_readvin_verified'), b=b.get('row_count')):
                with self.assertRaises(mod.CatalogEvidenceError):
                    mod.inspect(a,b)

    def test_08_declared_original_fk_preserved_without_join_claim(self):
        out = mod.inspect(schema(), rows())
        self.assertEqual(out['original_declared_fk_links'][0]['columns'][0]['source'], 'fkPartnerGroup')
        self.assertFalse(out['runtime_group_selection_verified'])

    def test_09_malformed_original_group_type_rejected(self):
        r = rows(); r['rows'][0][3] = {'private':'unhandled'}
        with self.assertRaises(mod.CatalogEvidenceError):
            mod.inspect(schema(), r)

    def test_10_no_raw_vin_or_extra_column_exfiltration(self):
        r = rows()
        # The tool reports group aggregates only, never raw table rows.
        r['rows'][0][2] = 'PRIVATE_ORIGINAL_VIN_DO_NOT_UPLOAD'
        out = mod.inspect(schema(),r)
        self.assertNotIn('PRIVATE_ORIGINAL_VIN_DO_NOT_UPLOAD', json.dumps(out))
        self.assertTrue(out['original_data_modified_or_anonymized'] is False)

    def test_11_cli_output_new_only_and_no_source_path_echo(self):
        with tempfile.TemporaryDirectory() as p:
            base = Path(p)
            a,b,c,z = (base/x for x in ('schema.json','rows.json','context.json','report.json'))
            a.write_text(json.dumps(schema()),encoding='utf-8')
            b.write_text(json.dumps(rows()),encoding='utf-8')
            c.write_text(json.dumps(context()),encoding='utf-8')
            argv=['--schema',str(a),'--rows',str(b),'--group-context',str(c),'--output',str(z)]
            self.assertEqual(mod.main(argv),0)
            self.assertEqual(json.loads(z.read_text())['selected_group_rows_in_this_capture'],2)
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(mod.main(argv),2)
            self.assertNotIn(str(z),err.getvalue())

    def test_12_bad_json_and_duplicate_keys_fail_closed(self):
        with tempfile.TemporaryDirectory() as p:
            f=Path(p)/'bad.json'
            for content in ('{"a":1,"a":2}', '{"k":NaN}', '\ud800'):
                f.write_text(content,encoding='utf-8',errors='surrogatepass')
                with self.subTest(content=content[:20]),self.assertRaises((ValueError,UnicodeError)):
                    mod.read_json(f,8192)

    def test_13_context_cannot_claim_received_vin(self):
        for invalid in ({'schema_version':mod.CONTEXT_FORMAT,'fkPartnerGroup_original':1002,'vin_accepted':True},
                        {'schema_version':mod.CONTEXT_FORMAT,'fkPartnerGroup_original':True},
                        {'schema_version':mod.CONTEXT_FORMAT,'fkPartnerGroup_original':1002.0}):
            with self.assertRaises(mod.CatalogEvidenceError):
                mod.inspect(schema(),rows(),invalid)

    def test_15_source_year_case_listed_without_normalization(self):
        original = schema()
        original['tables'][0]['columns'].append({'name': 'Yearcodepos', 'column_id': 9})
        result = mod.inspect(original)
        reported = {c['column']: c['present'] for c in result['original_column_presence']}
        self.assertTrue(reported['Yearcodepos'])
        self.assertFalse(reported['YearCodePos'])

    def test_14_nonexistent_source_table_rows_are_not_evidence(self):
        s=schema();s['tables'][0]['name']='other'
        with self.assertRaises(mod.CatalogEvidenceError):
            mod.inspect(s,rows())

if __name__=='__main__':
    unittest.main()
