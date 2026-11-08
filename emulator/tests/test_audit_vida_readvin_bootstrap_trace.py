"""Synthetic-only tests of bounded private VIDA ReadVin bootstrap log evidence."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_vida_readvin_bootstrap_trace import audit_text, main, MAX_LINE_LENGTH

PREFACE = "Starting new logsession: 2026-01-01 00:00:00\n"
SELECT = "[ScriptProvider][Event] Database: DiagSwdlRepository, SP: GetScript, Type: 'ReadVin' ScriptId: '' Language: 'en-US' EcuType: '-1' Profile: 'EMPTYPROFILE,'\n"
FETCH = "[ScriptProvider][Info] Fetched script: 'VCC-225200-1 1.8' title: 'Read VIN first readout (Odometer Value) (No immo check)'\n"
RUN = "[Script][Info] Running script: 'VCC-225200-1 1.8' title: 'Read VIN first readout'\n"
P3 = "[DiagConnection][VehCom] VehComm request: Ecu '726', Message '22F114'\n"
P2A = "[DiagConnection][VehCom] VehComm request: Ecu '40', Message 'B9FB'\n"
P2B = "[DiagConnection][VehCom] VehComm request: Ecu '50', Message 'B9FB'\n"
TXP3 = '[J2534][VehCom] ---> (0) 00,00,07,26,22,F1,14,\n'
TXP2A = '[J2534][VehCom] ---> (0) 00,0F,FF,FE,CB,40,B9,FB,00,00,00,00,\n'
TXP2B = '[J2534][VehCom] ---> (0) 00,0F,FF,FE,CB,50,B9,FB,00,00,00,00,\n'
RXECHO = '[J2534][VehCom] <--- (0) 00,00,07,26,\n[J2534][VehCom] TRANSMITTED FRAME indication\n'
ERROR = '[J2534][Error] J2534 function:PassThruReadMsgs failed with return value:ERR_BUFFER_EMPTY\n'

class VidaBootstrapTraceTests(unittest.TestCase):
    def test_01_emptyprofile_bootstrap_script_selected(self):
        out = audit_text(PREFACE + SELECT + FETCH + RUN)
        self.assertEqual(out['totals']['readvin_emptyprofile_selections'], 1)
        self.assertEqual(out['totals']['bootstrap_readvin_running'], 1)
        self.assertFalse(out['readvin_selected_from_actual_getscript_database_verified'])

    def test_02_all_three_request_families_counted_same_session(self):
        out = audit_text(PREFACE + SELECT + P3 + P2A + P2B + TXP3 + TXP2A + TXP2B)
        self.assertEqual(out['sessions_with_all_three_request_families'], 1)
        for key in ('j2534_p3_f114_tx_frames','j2534_p2_b9fb_target40_tx_frames', 'j2534_p2_b9fb_target50_tx_frames'):
            self.assertEqual(out['totals'][key], 1)
        self.assertFalse(out['client_vin_accepted'])

    def test_03_tx_echo_is_not_positive_ecu_response(self):
        out = audit_text(PREFACE + SELECT + TXP3 + RXECHO + ERROR)
        self.assertEqual(out['totals']['j2534_rx_id_only_or_short_lines'], 1)
        self.assertEqual(out['totals']['j2534_rx_p3_positive_prefix_candidates'], 0)
        self.assertEqual(out['totals']['j2534_err_buffer_empty'], 1)
        self.assertFalse(out['actual_positive_ecu_reply_correlated'])

    def test_04_rx_looking_positive_prefix_still_not_accepted_vin(self):
        out = audit_text(PREFACE + SELECT + '[J2534] <--- (0) 00,00,07,2E,62,F1,14,11,\n')
        self.assertEqual(out['totals']['j2534_rx_p3_positive_prefix_candidates'], 1)
        self.assertFalse(out['actual_positive_ecu_reply_correlated'])
        self.assertFalse(out['client_vin_accepted'])

    def test_05_rx_d2_positive_prefix_still_not_accepted(self):
        out = audit_text(PREFACE + SELECT + '[J2534] <--- (0) 01,20,00,03,8F,50,F9,FB,01,00,00,00\n')
        self.assertEqual(out['totals']['j2534_rx_p2_b9fb_positive_prefix_candidates'], 1)
        self.assertFalse(out['replay_approved'])

    def test_06_sessions_never_merged_for_complete_scan(self):
        out = audit_text(PREFACE+SELECT+P3+P2A+PREFACE+SELECT+P2B)
        self.assertEqual(out['session_count'], 2)
        self.assertEqual(out['sessions_with_all_three_request_families'], 0)

    def test_07_unrelated_type_and_profile_do_not_open_bootstrap(self):
        txt = PREFACE + "[ScriptProvider] SP: GetScript Type: 'VehCommSpecification' Profile: 'EMPTYPROFILE,'\n" + P2A
        out = audit_text(txt)
        self.assertEqual(out['totals']['readvin_emptyprofile_selections'], 0)
        self.assertEqual(out['totals']['vehcomm_p2_b9fb_target40_requests'], 0)

    def test_08_readvin_with_nonempty_profile_not_bootstrap(self):
        txt = PREFACE + "[ScriptProvider] SP: GetScript Type: 'ReadVin' Profile: 'PROFILE_X,'\n" + P3
        out = audit_text(txt)
        self.assertEqual(out['totals']['readvin_getscript_declarations'], 1)
        self.assertEqual(out['totals']['vehcomm_p3_f114_requests'], 0)

    def test_09_secret_identifiers_never_emitted(self):
        txt = PREFACE+SELECT+'VIN: SENSITIVE-SYNTHETIC-XYZ\n'+TXP3
        result = json.dumps(audit_text(txt))
        self.assertNotIn('SENSITIVE-SYNTHETIC-XYZ', result)
        self.assertNotIn('EMPTYPROFILE,', result)
        self.assertNotIn('VCC-225200-1', result)

    def test_10_untrusted_incorrect_can_id_not_classified_as_tx(self):
        out=audit_text(PREFACE+SELECT+'[J2534] ---> (0) 00,00,07,25,22,F1,14\n')
        self.assertEqual(out['totals']['j2534_p3_f114_tx_frames'], 0)

    def test_11_excessive_line_fails_closed(self):
        with self.assertRaises(ValueError):
            audit_text('A' * (MAX_LINE_LENGTH + 1))

    def test_12_cli_exclusive_output_and_secret_privacy(self):
        with tempfile.TemporaryDirectory() as t:
            src=Path(t,'secret.log');dst=Path(t,'report.json')
            src.write_text(PREFACE+SELECT+TXP2B+'VIN: FORBIDDEN_XXXX\n',encoding='utf8')
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(src),'--output',str(dst)])
            saved=dst.read_text(encoding='utf8')
            self.assertEqual(json.loads(saved)['totals']['j2534_p2_b9fb_target50_tx_frames'],1)
            self.assertNotIn('FORBIDDEN_XXXX',saved)
            self.assertNotIn(str(src),saved)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([str(src),'--output',str(dst)])


    def test_13_unrelated_getscript_closes_existing_bootstrap_window(self):
        unrelated = "[ScriptProvider] SP: GetScript Type: 'VehCommSpecification' Profile: 'EMPTYPROFILE,'\n"
        out = audit_text(PREFACE + SELECT + P3 + unrelated + P2A + P2B + TXP2A)
        self.assertEqual(out['totals']['vehcomm_p3_f114_requests'], 1)
        self.assertEqual(out['totals']['vehcomm_p2_b9fb_target40_requests'], 0)
        self.assertEqual(out['totals']['j2534_p2_b9fb_target40_tx_frames'], 0)
        self.assertEqual(out['sessions_with_all_three_request_families'], 0)

    def test_14_profiled_readvin_closes_bootstrap_window(self):
        profiled = "[ScriptProvider] SP: GetScript Type: 'ReadVin' Profile: 'PROFILE_X,'\n"
        out = audit_text(PREFACE + SELECT + P3 + profiled + P2A + P2B)
        self.assertEqual(out['totals']['readvin_getscript_declarations'], 2)
        self.assertEqual(out['totals']['readvin_emptyprofile_selections'], 1)
        self.assertEqual(out['totals']['vehcomm_p2_b9fb_target40_requests'], 0)
        self.assertEqual(out['sessions_with_all_three_request_families'], 0)

    def test_15_two_bootstrap_windows_cannot_complete_one_combined_gate(self):
        out = audit_text(PREFACE + SELECT + P3 + SELECT + P2A + P2B)
        self.assertEqual(out['session_count'], 1)
        self.assertEqual(out['totals']['readvin_emptyprofile_selections'], 2)
        self.assertEqual(out['totals']['vehcomm_p3_f114_requests'], 1)
        self.assertEqual(out['totals']['vehcomm_p2_b9fb_target40_requests'], 1)
        self.assertEqual(out['totals']['vehcomm_p2_b9fb_target50_requests'], 1)
        self.assertEqual(out['sessions_with_all_three_request_families'], 0)
        self.assertFalse(out['client_vin_accepted'])

    def test_16_second_complete_window_in_same_session_counts_only_once(self):
        out = audit_text(PREFACE + SELECT + P3 + SELECT + P3 + P2A + P2B)
        self.assertEqual(out['sessions_with_all_three_request_families'], 1)
        self.assertEqual(out['session_count'], 1)
        self.assertFalse(out['actual_positive_ecu_reply_correlated'])

    def test_17_new_bootstrap_after_unrelated_getscript_reopens_window(self):
        unrelated = "[ScriptProvider] SP: GetScript Type: 'Other' Profile: 'EMPTYPROFILE,'\n"
        out = audit_text(PREFACE + SELECT + P3 + unrelated + P2A + SELECT + P3 + P2A + P2B)
        self.assertEqual(out['sessions_with_all_three_request_families'], 1)
        self.assertEqual(out['totals']['vehcomm_p2_b9fb_target40_requests'], 1)
        self.assertFalse(out['xc90_v8_my2009_identified'])

    def test_18_session_boundary_cannot_join_split_windows(self):
        out = audit_text(PREFACE + SELECT + P3 + P2A + PREFACE + SELECT + P2B)
        self.assertEqual(out['sessions_with_all_three_request_families'], 0)
        self.assertEqual(out['session_count'], 2)



    def test_19_unrelated_running_script_closes_active_readvin_without_getscript(self):
        other = "[Script][Info] Running script: 'Unrelated ECU coding'\n"
        out = audit_text(PREFACE + SELECT + P3 + other + P2A + P2B + TXP2A)
        self.assertEqual(out['totals']['vehcomm_p3_f114_requests'], 1)
        self.assertEqual(out['totals']['vehcomm_p2_b9fb_target40_requests'], 0)
        self.assertEqual(out['totals']['j2534_p2_b9fb_target40_tx_frames'], 0)
        self.assertEqual(out['sessions_with_all_three_request_families'], 0)
        self.assertFalse(out['client_vin_accepted'])

    def test_20_new_readvin_selection_after_other_running_reopens_window(self):
        other = "[Script][Info] Running script: 'Unrelated ECU coding'\n"
        out = audit_text(PREFACE + SELECT + P3 + other + P2A + SELECT + P3 + P2A + P2B)
        self.assertEqual(out['sessions_with_all_three_request_families'], 1)
        self.assertEqual(out['totals']['vehcomm_p2_b9fb_target40_requests'], 1)
        self.assertEqual(out['session_count'], 1)
        self.assertFalse(out['actual_positive_ecu_reply_correlated'])

    def test_21_selected_readvin_running_keeps_current_window_open(self):
        out = audit_text(PREFACE + SELECT + P3 + RUN + P2A + P2B)
        self.assertEqual(out['sessions_with_all_three_request_families'], 1)
        self.assertEqual(out['totals']['bootstrap_readvin_running'], 1)
        self.assertFalse(out['replay_approved'])



    def test_22_expected_script_ordered_fetch_run_and_requests(self):
        out = audit_text(PREFACE + SELECT + FETCH + RUN + P3 + P2A + P2B,
                         'VCC-225200-1')
        self.assertTrue(out['expected_script_id_filter_supplied'])
        self.assertEqual(out['sessions_with_ordered_expected_script_fetch_run_lines'], 1)
        self.assertEqual(out['sessions_with_ordered_expected_script_run_and_three_request_families'], 1)
        self.assertFalse(out['runtime_getscript_selection_verified'])
        self.assertFalse(out['client_vin_accepted'])

    def test_23_run_without_prior_fetch_not_evidence(self):
        out = audit_text(PREFACE + SELECT + RUN + P3 + P2A + P2B,
                         'VCC-225200-1')
        self.assertEqual(out['sessions_with_ordered_expected_script_fetch_run_lines'], 0)
        self.assertEqual(out['sessions_with_ordered_expected_script_run_and_three_request_families'], 0)

    def test_24_requests_before_run_cannot_complete_ordered_gate(self):
        out = audit_text(PREFACE + SELECT + P3 + P2A + P2B + FETCH + RUN,
                         'VCC-225200-1')
        self.assertEqual(out['sessions_with_ordered_expected_script_fetch_run_lines'], 1)
        self.assertEqual(out['sessions_with_ordered_expected_script_run_and_three_request_families'], 0)
        self.assertEqual(out['sessions_with_all_three_request_families'], 1)

    def test_25_other_fetched_script_breaks_expected_pair(self):
        other = "[ScriptProvider] Fetched script: 'OTHER-SCRIPT 1.8' title: 'Something else'\n"
        out = audit_text(PREFACE + SELECT + FETCH + other + RUN + P3 + P2A + P2B,
                         'VCC-225200-1')
        self.assertEqual(out['sessions_with_ordered_expected_script_fetch_run_lines'], 0)
        self.assertEqual(out['sessions_with_ordered_expected_script_run_and_three_request_families'], 0)

    def test_26_getscript_reset_and_unrelated_run_close_window(self):
        other = "[ScriptProvider] SP: GetScript Type: 'VehCommSpecification' Profile: 'EMPTYPROFILE,'\n"
        unexpected_run = "[Script] Running script: 'OTHER-SCRIPT 1.0'\n"
        for log in (PREFACE + SELECT + FETCH + other + RUN + P3 + P2A + P2B,
                    PREFACE + SELECT + FETCH + unexpected_run + RUN + P3 + P2A + P2B):
            with self.subTest(log=log[:60]):
                out = audit_text(log, 'VCC-225200-1')
                self.assertEqual(out['sessions_with_ordered_expected_script_fetch_run_lines'], 0)
                self.assertEqual(out['sessions_with_ordered_expected_script_run_and_three_request_families'], 0)

    def test_27_expected_label_exact_prefix_and_valid_version(self):
        for other in ("[ScriptProvider] Fetched script: 'VCC-225200-12 1.8'\n",
                      "[ScriptProvider] Fetched script: 'VCC-225200-1 EXTRA'\n"):
            with self.subTest(other=other):
                out = audit_text(PREFACE + SELECT + other + RUN + P3 + P2A + P2B,
                                 'VCC-225200-1')
                self.assertEqual(out['sessions_with_ordered_expected_script_fetch_run_lines'], 0)
        out = audit_text(PREFACE + SELECT + FETCH + RUN, 'VCC-225200-1')
        self.assertEqual(out['sessions_with_ordered_expected_script_fetch_run_lines'], 1)

    def test_28_run_and_requests_must_stay_inside_same_window(self):
        out = audit_text(PREFACE + SELECT + FETCH + RUN + P3 + SELECT + P2A + P2B,
                         'VCC-225200-1')
        self.assertEqual(out['sessions_with_ordered_expected_script_fetch_run_lines'], 1)
        self.assertEqual(out['sessions_with_ordered_expected_script_run_and_three_request_families'], 0)
        out = audit_text(PREFACE + SELECT + FETCH + RUN + P3 + PREFACE + SELECT + P2A + P2B,
                         'VCC-225200-1')
        self.assertEqual(out['sessions_with_ordered_expected_script_run_and_three_request_families'], 0)

    def test_29_custom_expected_script_id_supported_without_vin_assumption(self):
        fetched = "[ScriptProvider] Fetched script: 'PRIVATE-READVIN-CANDIDATE 2.4'\n"
        running = "[Script] Running script: 'PRIVATE-READVIN-CANDIDATE 2.4'\n"
        out = audit_text(PREFACE + SELECT + fetched + running + P3 + P2A + P2B,
                         'PRIVATE-READVIN-CANDIDATE')
        self.assertEqual(out['sessions_with_ordered_expected_script_fetch_run_lines'], 1)
        self.assertEqual(out['sessions_with_ordered_expected_script_run_and_three_request_families'], 1)
        self.assertFalse(out['original_readvin_xml_binding_verified'])

    def test_30_reject_unsafe_script_id_and_no_private_values_in_report(self):
        for value in ('', ' X', 'X ', 'X\nY', 'X/../Y', 'X'*97, 123, False):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    audit_text(PREFACE + SELECT, value)
        secret = 'PRIVATE-READVIN-CANDIDATE'
        fetched = "[ScriptProvider] Fetched script: '" + secret + " 1.3'\n"
        running = "[Script] Running script: '" + secret + " 1.3'\n"
        text = json.dumps(audit_text(PREFACE + SELECT + fetched + running, secret))
        self.assertNotIn(secret, text)
        self.assertNotIn('EMPTYPROFILE', text)

    def test_31_cli_expected_script_filter_stays_private(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder, 'private.log')
            out = Path(folder, 'report.json')
            log.write_text(PREFACE + SELECT + FETCH + RUN + P3 + P2A + P2B,
                           encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(log), '--expected-script-id', 'VCC-225200-1',
                      '--output', str(out)])
            report = out.read_text(encoding='utf-8')
            self.assertTrue(json.loads(report)['expected_script_id_filter_supplied'])
            self.assertEqual(json.loads(report)['sessions_with_ordered_expected_script_run_and_three_request_families'], 1)
            self.assertNotIn('VCC-225200-1', report)
            self.assertNotIn(str(log), report)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([str(log), '--expected-script-id', 'VCC-225200-1',
                      '--output', str(out)])



    def test_32_different_fetched_and_running_versions_cannot_correlate(self):
        wrong_run = "[Script] Running script: 'VCC-225200-1 2.4'\n"
        out = audit_text(PREFACE + SELECT + FETCH + wrong_run + P3 + P2A + P2B,
                         'VCC-225200-1')
        self.assertEqual(out['sessions_with_ordered_expected_script_fetch_run_lines'], 0)
        self.assertEqual(out['sessions_with_ordered_expected_script_run_and_three_request_families'], 0)
        self.assertEqual(out['totals']['vehcomm_p3_f114_requests'], 0)
        self.assertFalse(out['client_vin_accepted'])

    def test_33_versioned_fetch_unversioned_run_is_not_same_artifact(self):
        no_version = "[Script] Running script: 'VCC-225200-1'\n"
        out = audit_text(PREFACE + SELECT + FETCH + no_version + P3 + P2A + P2B,
                         'VCC-225200-1')
        self.assertEqual(out['sessions_with_ordered_expected_script_fetch_run_lines'], 0)
        self.assertEqual(out['sessions_with_all_three_request_families'], 0)

    def test_34_unversioned_fetch_versioned_run_is_not_same_artifact(self):
        no_version = "[ScriptProvider] Fetched script: 'VCC-225200-1'\n"
        out = audit_text(PREFACE + SELECT + no_version + RUN + P3 + P2A + P2B,
                         'VCC-225200-1')
        self.assertEqual(out['sessions_with_ordered_expected_script_fetch_run_lines'], 0)
        self.assertEqual(out['sessions_with_ordered_expected_script_run_and_three_request_families'], 0)

    def test_35_unversioned_fetch_and_run_match_if_both_omit_version(self):
        no_version_fetch = "[ScriptProvider] Fetched script: 'VCC-225200-1'\n"
        no_version_run = "[Script] Running script: 'VCC-225200-1'\n"
        out = audit_text(PREFACE + SELECT + no_version_fetch + no_version_run
                         + P3 + P2A + P2B, 'VCC-225200-1')
        self.assertEqual(out['sessions_with_ordered_expected_script_fetch_run_lines'], 1)
        self.assertEqual(out['sessions_with_ordered_expected_script_run_and_three_request_families'], 1)
        self.assertFalse(out['runtime_getscript_selection_verified'])

    def test_36_matching_numeric_version_still_matches(self):
        fetch = "[ScriptProvider] Fetched script: 'VCC-225200-1 2.4.1'\n"
        run = "[Script] Running script: 'VCC-225200-1 2.4.1'\n"
        out = audit_text(PREFACE + SELECT + fetch + run + P3 + P2A + P2B,
                         'VCC-225200-1')
        self.assertEqual(out['sessions_with_ordered_expected_script_fetch_run_lines'], 1)
        self.assertEqual(out['sessions_with_ordered_expected_script_run_and_three_request_families'], 1)

    def test_37_new_getscript_after_mismatch_can_complete_new_window(self):
        wrong_run = "[Script] Running script: 'VCC-225200-1 2.4'\n"
        out = audit_text(PREFACE + SELECT + FETCH + wrong_run + P3 + SELECT
                         + FETCH + RUN + P3 + P2A + P2B, 'VCC-225200-1')
        self.assertEqual(out['sessions_with_ordered_expected_script_fetch_run_lines'], 1)
        self.assertEqual(out['sessions_with_ordered_expected_script_run_and_three_request_families'], 1)
        self.assertEqual(out['totals']['vehcomm_p3_f114_requests'], 1)



    def test_38_expected_run_three_requests_and_three_tx_same_window(self):
        evidence = PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + P2A + TXP2A + P2B + TXP2B
        report = audit_text(evidence, 'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_requests_and_tx'], 1)
        self.assertEqual(report['sessions_with_ordered_expected_script_run_and_three_request_families'], 1)
        self.assertFalse(report['actual_positive_ecu_reply_correlated'])
        self.assertFalse(report['client_vin_accepted'])

    def test_39_requests_without_three_tx_do_not_satisfy_strong_gate(self):
        report = audit_text(PREFACE + SELECT + FETCH + RUN + P3 + P2A + P2B + TXP3 + TXP2A,
                            'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_requests_and_tx'], 0)
        self.assertEqual(report['sessions_with_ordered_expected_script_run_and_three_request_families'], 1)

    def test_40_tx_before_run_cannot_satisfy_strong_gate(self):
        report = audit_text(PREFACE + SELECT + TXP3 + TXP2A + TXP2B + FETCH + RUN + P3 + P2A + P2B,
                            'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_requests_and_tx'], 0)
        self.assertEqual(report['totals']['j2534_p3_f114_tx_frames'], 1)

    def test_41_tx_split_across_two_getscript_windows_not_combined(self):
        log = (PREFACE + SELECT + FETCH + RUN + P3 + P2A + P2B + TXP3
               + SELECT + FETCH + RUN + P3 + P2A + P2B + TXP2A + TXP2B)
        report = audit_text(log, 'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_run_and_three_request_families'], 1)
        self.assertEqual(report['sessions_with_ordered_expected_script_requests_and_tx'], 0)

    def test_42_tx_wrong_id_or_rx_echo_never_completes_strong_gate(self):
        bad_p3 = '[J2534] ---> (0) 00,00,07,25,22,F1,14,\n'
        report = audit_text(PREFACE + SELECT + FETCH + RUN + P3 + P2A + P2B
                            + bad_p3 + TXP2A + TXP2B + RXECHO, 'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_requests_and_tx'], 0)
        self.assertEqual(report['totals']['j2534_rx_id_only_or_short_lines'], 1)

    def test_43_other_script_run_closes_tx_evidence_window(self):
        unrelated = "[Script] Running script: 'OTHER-SCRIPT 1.0'\n"
        log = (PREFACE + SELECT + FETCH + RUN + P3 + P2A + P2B + TXP3
               + unrelated + TXP2A + TXP2B)
        report = audit_text(log, 'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_requests_and_tx'], 0)

    def test_44_tx_before_requests_but_after_run_is_still_log_evidence(self):
        log = PREFACE + SELECT + FETCH + RUN + TXP3 + TXP2A + TXP2B + P3 + P2A + P2B
        report = audit_text(log, 'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_requests_and_tx'], 1)
        self.assertFalse(report['runtime_getscript_selection_verified'])

    def test_45_strong_gate_private_expected_id_not_in_summary(self):
        sensitive = 'PRIVATE-SCRIPT-ID'
        fetch = "[ScriptProvider] Fetched script: 'PRIVATE-SCRIPT-ID 1.8'\n"
        run = "[Script] Running script: 'PRIVATE-SCRIPT-ID 1.8'\n"
        report = json.dumps(audit_text(PREFACE + SELECT + fetch + run
                                       + P3 + P2A + P2B + TXP3 + TXP2A + TXP2B,
                                       sensitive))
        self.assertNotIn(sensitive, report)
        self.assertEqual(json.loads(report)['sessions_with_ordered_expected_script_requests_and_tx'], 1)

if __name__ == '__main__':
    unittest.main()
