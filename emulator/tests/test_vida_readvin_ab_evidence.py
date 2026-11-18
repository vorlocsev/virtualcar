"""Synthetic, isolated original-VIDA evidence correlation tests; no real VIN."""
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
import vida_readvin_ab_evidence as t

VIN = 'YV1CZ000290000001'  # Synthetic public example only
WORKFLOW = 'b' * 64
COMMIT = 'c' * 40


def observation(mode, result='NOT_TESTED', group=1002, vin=VIN):
    return {'schema_version': t.OBS_SCHEMA, 'mode': mode,
            'vin_original': vin, 'partner_group_original': group,
            'vida_build': 'VIDA2014D_SYNTHETIC', 'workflow_dll_sha256': WORKFLOW,
            'observed_at': '2026-11-18T05:00:00+01:00',
            'gui_result': result, 'gui_message_original': None,
            'transport': 'NOT_OBSERVED',
            'virtualcar_head_sha': COMMIT if mode == 'j2534' else None,
            'evidence_path': None, 'evidence_sha256': None}


def with_file(obs, folder):
    contents = ('synthetic screenshot log for ' + obs['mode']).encode()
    file = folder / (obs['mode'] + '_private_original.log')
    file.write_bytes(contents)
    obs['evidence_path'] = str(file)
    obs['evidence_sha256'] = hashlib.sha256(contents).hexdigest()
    obs['gui_message_original'] = 'synthetic original GUI text'
    return obs


def candidate():
    return {'schema_version': t.CANDIDATE_SCHEMA,
            'vin_original': VIN, 'partner_group_original': 1002,
            'public_filtered_candidate_count': 1,
            'public_branch_in_available_inputs': 'single_vehicle_model_in_remaining_candidates',
            'model_variant_capture_incomplete': False,
            'vehicle_profile_capture_scope': 'filtered_subset_only',
            'original_vida_decoder_runtime_verified': False,
            'readvin_gui_acceptance_verified': False,
            'ecu_identification_verified': False}


class ABTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def case(self, manual='NOT_TESTED', j2534='NOT_TESTED'):
        m = observation('manual', manual)
        j = observation('j2534', j2534)
        if manual != 'NOT_TESTED':
            with_file(m, self.root)
        if j2534 != 'NOT_TESTED':
            with_file(j, self.root)
        return m, j

    def test_01_two_unobserved_sessions_are_not_a_pass(self):
        a, b = self.case()
        out = t.correlate(a, b)
        self.assertEqual(out['classification'], 'MISSING_OWNER_GUI_OBSERVATION')
        self.assertFalse(out['readvin_acceptance_independently_verified'])

    def test_02_manual_pass_j2534_fail_is_transport_or_parser_path(self):
        a,b = self.case('ACCEPTED','REJECTED')
        out=t.correlate(a,b)
        self.assertEqual(out['classification'],'J2534_OR_RESPONSEHANDLER_PATH_SUSPECTED')
        self.assertTrue(out['source_context_comparable'])

    def test_03_manual_fail_j2534_fail_does_not_exclude_j2534_fault(self):
        a,b=self.case('REJECTED','REJECTED')
        self.assertEqual(t.correlate(a,b)['classification'],'DECODER_OR_PARTNER_COVERAGE_SUSPECTED')

    def test_04_both_pass_only_owner_reported(self):
        a,b=self.case('ACCEPTED','ACCEPTED')
        out=t.correlate(a,b)
        self.assertEqual(out['classification'],'BOTH_GUI_OUTCOMES_OWNER_REPORTED_ACCEPTED')
        self.assertFalse(out['readvin_acceptance_independently_verified'])
        self.assertFalse(out['ecu_identification_verified'])

    def test_05_manual_fail_j2534_pass_is_session_difference(self):
        a,b=self.case('REJECTED','ACCEPTED')
        self.assertEqual(t.correlate(a,b)['classification'],'SESSION_OR_MANUAL_UI_PATH_DIFFERENCE')

    def test_06_same_partner_group_required(self):
        a,b=self.case('ACCEPTED','REJECTED')
        b['partner_group_original']=1001
        out=t.correlate(a,b)
        self.assertFalse(out['source_context_comparable'])
        self.assertEqual(out['classification'],'NOT_COMPARABLE_SOURCE_CONTEXT')

    def test_07_same_vin_required_for_comparable(self):
        a,b=self.case('ACCEPTED','ACCEPTED')
        b['vin_original']='YV1CZ000290000002'
        self.assertFalse(t.correlate(a,b)['source_context_comparable'])

    def test_08_same_workflow_dll_hash_required(self):
        a,b=self.case('ACCEPTED','REJECTED')
        b['workflow_dll_sha256']='a'*64
        self.assertFalse(t.correlate(a,b)['source_context_comparable'])

    def test_09_tampered_evidence_file_must_fail(self):
        a,b=self.case('ACCEPTED','REJECTED')
        Path(a['evidence_path']).write_bytes(b'tampered')
        with self.assertRaises(t.EvidenceError): t.correlate(a,b)

    def test_10_missing_evidence_file_cannot_prove_gui(self):
        a,b=self.case('ACCEPTED','REJECTED')
        Path(b['evidence_path']).unlink()
        with self.assertRaises(t.EvidenceError): t.correlate(a,b)

    def test_11_manual_cannot_claim_adapter_transport(self):
        a,b=self.case('REJECTED','REJECTED')
        a['transport']='RX_DEQUEUED'
        with self.assertRaises(t.EvidenceError): t.correlate(a,b)

    def test_12_not_tested_cannot_claim_rx(self):
        a,b=self.case()
        b['transport']='RX_DEQUEUED'
        with self.assertRaises(t.EvidenceError): t.correlate(a,b)

    def test_13_j2534_observed_result_requires_exact_head(self):
        a,b=self.case('ACCEPTED','REJECTED')
        b['virtualcar_head_sha']=None
        with self.assertRaises(t.EvidenceError): t.correlate(a,b)

    def test_14_timestamps_need_timezone(self):
        a,b=self.case()
        a['observed_at']='2026-11-18T05:00:00'
        with self.assertRaises(t.EvidenceError): t.correlate(a,b)

    def test_15_b3a302_candidate_report_must_match_vin_and_group(self):
        a,b=self.case('ACCEPTED','REJECTED')
        c=candidate()
        self.assertEqual(t.correlate(a,b,c)['offline_public_candidate_review']['candidate_count_only'],1)
        c['partner_group_original']=1001
        with self.assertRaises(t.EvidenceError):t.correlate(a,b,c)

    def test_16_forged_original_decoder_runtime_claim_rejected(self):
        a,b=self.case()
        c=candidate();c['original_vida_decoder_runtime_verified']=True
        with self.assertRaises(t.EvidenceError):t.correlate(a,b,c)

    def test_17_cross_context_candidate_join_rejected(self):
        a,b=self.case('ACCEPTED','REJECTED')
        b['partner_group_original']=1001
        with self.assertRaises(t.EvidenceError):t.correlate(a,b,candidate())

    def test_18_never_change_observation_inputs(self):
        a,b=self.case('ACCEPTED','REJECTED')
        before=(copy.deepcopy(a),copy.deepcopy(b))
        t.correlate(a,b)
        self.assertEqual((a,b),before)

    def test_19_cli_writes_only_to_new_file(self):
        a,b=self.case('ACCEPTED','REJECTED')
        source_m=self.root/'manual.json';source_j=self.root/'j2534.json';output=self.root/'result.json'
        source_m.write_text(json.dumps(a));source_j.write_text(json.dumps(b))
        argv=['--manual',str(source_m),'--j2534',str(source_j),'--output',str(output)]
        self.assertEqual(t.main(argv),0)
        self.assertEqual(json.loads(output.read_text())['vin_original'],VIN)
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(t.main(argv),2)
            self.assertEqual(t.main(argv[:-1]+[str(source_m)]),2)
        self.assertNotIn(VIN,errors.getvalue())
        self.assertNotIn(str(source_m),errors.getvalue())

    def test_20_json_duplicate_keys_and_nonfinite_rejected(self):
        path=self.root/'json-source.json'
        for value in ('{"x":1,"x":2}', '{"x":NaN}', '\ud800'):
            path.write_text(value,encoding='utf-8',errors='surrogatepass')
            with self.assertRaises((t.EvidenceError,UnicodeError)):
                t.read_json(path)

    def test_21_group_boolean_rejected(self):
        a,b=self.case();a['partner_group_original']=True
        with self.assertRaises(t.EvidenceError): t.correlate(a,b)

    def test_22_local_original_message_preserved_not_printed(self):
        a,b=self.case('REJECTED','REJECTED')
        a['gui_message_original']='The VIN can not be decoded on selected Partner Group'
        result=t.correlate(a,b)
        self.assertEqual(result['manual_observation']['gui_message_original'],a['gui_message_original'])
        self.assertEqual(result['j2534_observation']['gui_result_owner_reported'],'REJECTED')
        self.assertFalse(result['original_gui_log_interpretation_independently_verified'])

if __name__=='__main__':unittest.main()
