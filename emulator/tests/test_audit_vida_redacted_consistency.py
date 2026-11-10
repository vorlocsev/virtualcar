"""Synthetic-only tests of cross-report ReadVin consistency; no original VIDA data."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_vida_redacted_consistency import analyze, main


def fixtures():
    v2 = {
        'schema_version': 'virtualcar-vida-single-private-readvin-zip-v1',
        'xml_zip_structure_validated': True,
        'script_selected_by_getscript_runtime': False,
        'vin_accepted_by_client': False,
        'b9fb_to_vin_runtime_flow_verified': False,
        'lexical_tokens_present_not_execution': {'f114': True, 'b9fb': False,
                                                  'addvin': True, 'setx40serial': True},
        'identity_xml_graph_declarations': {
            'node_count': 3, 'readvin_component_count': 1,
            'vehicle_identity_output_count': 1, 'event_handler_count': 2,
            'declared_call_count': 2, 'graph_layout': {'status': 'nested_sections'},
            'declared_identity_edges': {
                'add_vin': {'declared': 1, 'absent_disabled_attribute': 1,
                            'not_disabled_literal': 0, 'disabled_literal': 0,
                            'unrecognized_disabled_literal': 0},
                'set_x40_serial': {'declared': 1, 'absent_disabled_attribute': 1,
                                   'not_disabled_literal': 0, 'disabled_literal': 0,
                                   'unrecognized_disabled_literal': 0}},
        },
    }
    bin_map = {'one_edge': 0, 'two_edges': 1, 'three_or_more_edges': 0,
               'no_path_in_event_call_graph': 0, 'explicitly_disabled_call': 0}
    v3 = {
        'schema_version': 'virtualcar-vida-readvin-static-topology-v1',
        'all_node_and_call_sections_resolved': True,
        'actual_runtime_graph_execution_verified': False,
        'client_vin_accepted': False, 'replay_approved': False,
        'node_count': 3,
        'node_role_counts': {'readvin': 1, 'identity_output': 1, 'other': 1, 'unresolved': 0},
        'eventhandler_count': 2, 'declared_event_call_count': 2,
        'identity_output_method_topology': {
            'add_vin': {'total_targeting_identity_output': 1,
                        'possible_declared_chain_distance_to_identity': copy.deepcopy(bin_map),
                        'disabled_attribute_counts': {
                            'unspecified': 1, 'not_disabled_literal': 0,
                            'disabled_literal': 0, 'unrecognized_literal': 0},
                        'calls_with_declared_parameter_child': 1,
                        'declared_parameter_child_total': 1},
            'set_x40_serial': {'total_targeting_identity_output': 1,
                               'possible_declared_chain_distance_to_identity': copy.deepcopy(bin_map),
                        'disabled_attribute_counts': {
                            'unspecified': 1, 'not_disabled_literal': 0,
                            'disabled_literal': 0, 'unrecognized_literal': 0},
                        'calls_with_declared_parameter_child': 1,
                        'declared_parameter_child_total': 1},
        },
    }
    return v2, v3


class SafeCrosscheckTests(unittest.TestCase):
    def test_01_consistent_static_reports_are_not_identity_proof(self):
        r = analyze(*fixtures())
        self.assertTrue(r['structural_counters_consistent'])
        self.assertEqual(r['crosschecked_fields'], 7)
        self.assertFalse(r['vin_accepted_by_client'])
        self.assertFalse(r['replay_approved'])

    def test_02_counter_mismatch_fails_closed(self):
        a, b = fixtures()
        b['eventhandler_count'] = 3
        with self.assertRaises(ValueError):
            analyze(a, b)

    def test_03_claim_of_success_rejected(self):
        for side, name in ((0, 'vin_accepted_by_client'), (1, 'client_vin_accepted'),
                           (0, 'script_selected_by_getscript_runtime'),
                           (1, 'actual_runtime_graph_execution_verified')):
            pair = list(fixtures())
            pair[side][name] = True
            with self.subTest(side=side, name=name), self.assertRaises(ValueError):
                analyze(*pair)

    def test_04_boolean_not_integer_counts(self):
        a, b = fixtures()
        a['identity_xml_graph_declarations']['node_count'] = True
        with self.assertRaises(ValueError):
            analyze(a, b)
        a, b = fixtures()
        a['lexical_tokens_present_not_execution']['f114'] = 1
        with self.assertRaises(ValueError):
            analyze(a, b)

    def test_05_roles_and_chain_bins_must_partition(self):
        a, b = fixtures()
        b['node_role_counts']['other'] = 2
        with self.assertRaises(ValueError):
            analyze(a, b)
        a, b = fixtures()
        b['identity_output_method_topology']['add_vin'][
            'possible_declared_chain_distance_to_identity']['two_edges'] = 2
        with self.assertRaises(ValueError):
            analyze(a, b)

    def test_06_partial_graph_not_promoted(self):
        a, b = fixtures()
        a['identity_xml_graph_declarations']['graph_layout']['status'] = 'unresolved_or_partial'
        with self.assertRaises(ValueError):
            analyze(a, b)

    def test_07_cli_redacts_original_synthetic_marker_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            a, b = fixtures()
            a['original_non_allowlisted_private_vin'] = 'SYNTHETIC_VIN_PRIVATE_TOKEN'
            pa, pb, out = p / 'a.json', p / 'b.json', p / 'out.json'
            pa.write_text(json.dumps(a))
            pb.write_text(json.dumps(b))
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(pa), str(pb), '--output', str(out)])
            result = out.read_text()
            self.assertNotIn('SYNTHETIC_VIN_PRIVATE_TOKEN', result)
            self.assertNotIn(str(pa), result)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([str(pa), str(pb), '--output', str(out)])

    def test_09_disabled_attribute_categories_must_match_across_sources(self):
        a, b = fixtures()
        b['identity_output_method_topology']['add_vin'][
            'disabled_attribute_counts']['unspecified'] = 0
        b['identity_output_method_topology']['add_vin'][
            'disabled_attribute_counts']['not_disabled_literal'] = 1
        with self.assertRaises(ValueError):
            analyze(a, b)

    def test_10_parameter_declarations_do_not_prove_vin_data_flow(self):
        r = analyze(*fixtures())
        self.assertTrue(r['all_identity_calls_have_parameter_child'])
        self.assertEqual(r['identity_disabled_unspecified_total'], 2)
        self.assertEqual(r['identity_parameter_declarations']['add_vin'][
            'declared_parameter_child_total'], 1)
        self.assertFalse(r['vin_accepted_by_client'])

    def test_11_parameter_count_cannot_exceed_call_count(self):
        a, b = fixtures()
        b['identity_output_method_topology']['set_x40_serial'][
            'calls_with_declared_parameter_child'] = 2
        with self.assertRaises(ValueError):
            analyze(a, b)

    def test_08_reject_schema_and_overlarge_inputs(self):
        a, b = fixtures()
        a['schema_version'] = 'other'
        with self.assertRaises(ValueError):
            analyze(a, b)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            pa, pb, out = p / 'a.json', p / 'b.json', p / 'report.json'
            pa.write_text('{' + 'a' * (128 * 1024) + '}')
            pb.write_text(json.dumps(b))
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([str(pa), str(pb), '--output', str(out)])
            self.assertFalse(out.exists())


    def test_12_duplicate_json_keys_rejected_before_analysis(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            a, b = fixtures()
            source = folder / 'v2.json'
            reference = folder / 'v3.json'
            result = folder / 'result.json'
            # A later false flag must not silently erase an earlier true flag.
            source.write_text(json.dumps(a).replace(
                '"vin_accepted_by_client": false',
                '"vin_accepted_by_client": true, "vin_accepted_by_client": false'
            ), encoding='utf-8')
            reference.write_text(json.dumps(b), encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([str(source), str(reference), '--output', str(result)])
            self.assertFalse(result.exists())

    def test_13_nonfinite_json_numbers_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            a, b = fixtures()
            source = folder / 'v2.json'
            reference = folder / 'v3.json'
            result = folder / 'result.json'
            source.write_text(json.dumps(a), encoding='utf-8')
            reference.write_text(json.dumps(b).replace(
                '"node_count": 3', '"node_count": NaN'
            ), encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([str(source), str(reference), '--output', str(result)])
            self.assertFalse(result.exists())


    def test_14_both_reports_agree_but_no_readvin_component(self):
        a, b = fixtures()
        a['identity_xml_graph_declarations']['readvin_component_count'] = 0
        b['node_role_counts']['readvin'] = 0
        b['node_role_counts']['other'] = 2
        with self.assertRaisesRegex(ValueError, 'incomplete ReadVin identity'):
            analyze(a, b)

    def test_15_both_reports_agree_but_no_identity_output(self):
        a, b = fixtures()
        a['identity_xml_graph_declarations']['vehicle_identity_output_count'] = 0
        b['node_role_counts']['identity_output'] = 0
        b['node_role_counts']['other'] = 2
        with self.assertRaisesRegex(ValueError, 'incomplete ReadVin identity'):
            analyze(a, b)


if __name__ == '__main__':
    unittest.main()
