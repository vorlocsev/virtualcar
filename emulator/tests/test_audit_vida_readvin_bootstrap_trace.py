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
RXP3 = '[J2534][VehCom] <--- (0) 00,00,07,2E,62,F1,14,11,\n'
RXP240 = '[J2534][VehCom] <--- (0) 01,20,00,03,8F,40,F9,FB,01,00,00,00,\n'
RXP250 = '[J2534][VehCom] <--- (0) 01,20,00,05,8F,50,F9,FB,01,00,00,00,\n'
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

    def test_46_ordered_request_then_tx_per_family_is_stronger_evidence(self):
        log = PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + P2A + TXP2A + P2B + TXP2B
        report = audit_text(log, 'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_request_before_tx_all_families'], 1)
        self.assertEqual(report['sessions_with_ordered_expected_script_requests_and_tx'], 1)
        self.assertFalse(report['actual_positive_ecu_reply_correlated'])
        self.assertFalse(report['client_vin_accepted'])

    def test_47_all_tx_before_vehcomm_requests_is_not_strict_evidence(self):
        log = PREFACE + SELECT + FETCH + RUN + TXP3 + TXP2A + TXP2B + P3 + P2A + P2B
        report = audit_text(log, 'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_requests_and_tx'], 1)
        self.assertEqual(report['sessions_with_ordered_expected_script_request_before_tx_all_families'], 0)

    def test_48_one_tx_before_its_own_request_blocks_strict_evidence(self):
        log = PREFACE + SELECT + FETCH + RUN + TXP3 + P3 + P2A + TXP2A + P2B + TXP2B
        report = audit_text(log, 'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_request_before_tx_all_families'], 0)
        self.assertEqual(report['sessions_with_ordered_expected_script_requests_and_tx'], 1)

    def test_49_requests_and_tx_cannot_cross_getscript_windows(self):
        log = (PREFACE + SELECT + FETCH + RUN + P3 + TXP3
               + SELECT + FETCH + RUN + P2A + TXP2A + P2B + TXP2B)
        report = audit_text(log, 'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_request_before_tx_all_families'], 0)

    def test_50_repeated_running_without_fetch_resets_pending_request(self):
        log = PREFACE + SELECT + FETCH + RUN + P3 + RUN + TXP3 + P2A + TXP2A + P2B + TXP2B
        report = audit_text(log, 'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_request_before_tx_all_families'], 0)

    def test_51_unrelated_run_closes_pending_pair_window(self):
        other = "[Script] Running script: 'OTHER-SCRIPT 1.8'\n"
        log = (PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + P2A
               + other + TXP2A + P2B + TXP2B)
        report = audit_text(log, 'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_request_before_tx_all_families'], 0)

    def test_52_rx_echo_and_wrong_can_id_do_not_complete_pairing(self):
        wrong = '[J2534] ---> (0) 00,00,07,25,22,F1,14,\n'
        log = PREFACE + SELECT + FETCH + RUN + P3 + wrong + P2A + TXP2A + P2B + TXP2B + RXECHO
        report = audit_text(log, 'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_request_before_tx_all_families'], 0)
        self.assertEqual(report['totals']['j2534_rx_id_only_or_short_lines'], 1)

    def test_53_duplicate_tx_for_one_family_cannot_replace_missing_pair(self):
        log = (PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + TXP3
               + P2A + TXP2A + P2B)
        report = audit_text(log, 'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_request_before_tx_all_families'], 0)

    def test_54_pre_run_request_and_tx_are_not_accepted_in_strict_mode(self):
        log = PREFACE + SELECT + P3 + TXP3 + FETCH + RUN + P2A + TXP2A + P2B + TXP2B
        report = audit_text(log, 'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_request_before_tx_all_families'], 0)

    def test_55_new_window_can_recover_from_earlier_wrong_order(self):
        log = (PREFACE + SELECT + FETCH + RUN + TXP3 + P3
               + SELECT + FETCH + RUN + P3 + TXP3 + P2A + TXP2A + P2B + TXP2B)
        report = audit_text(log, 'VCC-225200-1')
        self.assertEqual(report['sessions_with_ordered_expected_script_request_before_tx_all_families'], 1)
        self.assertFalse(report['runtime_getscript_selection_verified'])

    def test_56_new_ordering_field_never_exposes_private_script(self):
        secret = 'PRIVATE-SCRIPT-ID'
        fetch = "[ScriptProvider] Fetched script: 'PRIVATE-SCRIPT-ID 1.8'\n"
        run = "[Script] Running script: 'PRIVATE-SCRIPT-ID 1.8'\n"
        log = PREFACE + SELECT + fetch + run + P3 + TXP3 + P2A + TXP2A + P2B + TXP2B
        result = json.dumps(audit_text(log, secret))
        self.assertEqual(json.loads(result)['sessions_with_ordered_expected_script_request_before_tx_all_families'], 1)
        self.assertNotIn(secret, result)
        self.assertFalse(json.loads(result)['replay_approved'])

    def test_57_without_script_selector_new_strict_gate_stays_zero(self):
        log = PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + P2A + TXP2A + P2B + TXP2B
        report = audit_text(log)
        self.assertEqual(report['sessions_with_ordered_expected_script_request_before_tx_all_families'], 0)
        self.assertFalse(report['expected_script_id_filter_supplied'])



    def test_58_ordered_request_tx_rx_prefixes_all_three_only_candidate(self):
        r = audit_text(PREFACE + SELECT + FETCH + RUN +
                       P3 + TXP3 + RXP3 + P2A + TXP2A + RXP240 +
                       P2B + TXP2B + RXP250, 'VCC-225200-1')
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_rx_prefix_candidates'], 1)
        self.assertEqual(r['totals']['rx_p3_prefix_after_ordered_request_tx_candidates'], 1)
        self.assertEqual(r['totals']['rx_p2_target40_prefix_after_ordered_request_tx_candidates'], 1)
        self.assertEqual(r['totals']['rx_p2_target50_prefix_after_ordered_request_tx_candidates'], 1)
        self.assertFalse(r['actual_positive_ecu_reply_correlated'])
        self.assertFalse(r['client_vin_accepted'])
        self.assertFalse(r['replay_approved'])

    def test_59_rx_before_tx_not_matched_even_with_all_requests(self):
        log = (PREFACE + SELECT + FETCH + RUN +
               P3 + RXP3 + TXP3 + P2A + RXP240 + TXP2A +
               P2B + RXP250 + TXP2B)
        r = audit_text(log, 'VCC-225200-1')
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_rx_prefix_candidates'], 0)
        for key in ('rx_p3_prefix_after_ordered_request_tx_candidates',
                    'rx_p2_target40_prefix_after_ordered_request_tx_candidates',
                    'rx_p2_target50_prefix_after_ordered_request_tx_candidates'):
            self.assertEqual(r['totals'][key], 0)
        self.assertEqual(r['sessions_with_ordered_expected_script_request_before_tx_all_families'], 1)

    def test_60_rx_after_tx_but_without_vehcomm_request_not_matched(self):
        log = PREFACE + SELECT + FETCH + RUN + TXP3 + RXP3 + TXP2A + RXP240 + TXP2B + RXP250
        r = audit_text(log, 'VCC-225200-1')
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_rx_prefix_candidates'], 0)
        self.assertEqual(r['totals']['rx_p3_prefix_after_ordered_request_tx_candidates'], 0)

    def test_61_tx_identifier_echoes_rejected_even_with_positive_prefix(self):
        p3_echo = '[J2534] <--- (0) 00,00,07,26,62,F1,14,11,\n'
        d2_echo40 = '[J2534] <--- (0) 00,0F,FF,FE,8F,40,F9,FB,\n'
        d2_echo50 = '[J2534] <--- (0) 00,0F,FF,FE,8F,50,F9,FB,\n'
        log = (PREFACE + SELECT + FETCH + RUN +
               P3 + TXP3 + p3_echo + P2A + TXP2A + d2_echo40 +
               P2B + TXP2B + d2_echo50)
        r = audit_text(log, 'VCC-225200-1')
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_rx_prefix_candidates'], 0)
        self.assertEqual(r['totals']['rx_p3_prefix_after_ordered_request_tx_candidates'], 0)
        self.assertEqual(r['totals']['rx_p2_target40_prefix_after_ordered_request_tx_candidates'], 0)
        self.assertEqual(r['totals']['rx_p2_target50_prefix_after_ordered_request_tx_candidates'], 0)

    def test_62_even_d2_can_id_is_not_a_valid_rx_prefix_candidate(self):
        even = '[J2534] <--- (0) 01,20,00,02,8F,40,F9,FB,01,00,00,00,\n'
        r = audit_text(PREFACE + SELECT + FETCH + RUN + P2A + TXP2A + even,
                       'VCC-225200-1')
        self.assertEqual(r['totals']['rx_p2_target40_prefix_after_ordered_request_tx_candidates'], 0)

    def test_63_wrong_d2_target_cannot_complete_expected_target(self):
        r = audit_text(PREFACE + SELECT + FETCH + RUN + P2A + TXP2A + RXP250,
                       'VCC-225200-1')
        self.assertEqual(r['totals']['rx_p2_target40_prefix_after_ordered_request_tx_candidates'], 0)
        self.assertEqual(r['totals']['rx_p2_target50_prefix_after_ordered_request_tx_candidates'], 0)

    def test_64_getscript_boundary_clears_pending_rx_candidate(self):
        r = audit_text(PREFACE + SELECT + FETCH + RUN + P3 + TXP3 +
                       SELECT + FETCH + RUN + RXP3,
                       'VCC-225200-1')
        self.assertEqual(r['totals']['rx_p3_prefix_after_ordered_request_tx_candidates'], 0)

    def test_65_repeated_same_family_request_invalidates_stale_tx(self):
        r = audit_text(PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + P3 + RXP3,
                       'VCC-225200-1')
        self.assertEqual(r['totals']['rx_p3_prefix_after_ordered_request_tx_candidates'], 0)
        r = audit_text(PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + P3 + TXP3 + RXP3,
                       'VCC-225200-1')
        self.assertEqual(r['totals']['rx_p3_prefix_after_ordered_request_tx_candidates'], 1)

    def test_66_tx_indication_and_tx_msg_status_in_rx_line_rejected(self):
        for suffix in (' TRANSMITTED FRAME indication', ' transmitted frame INDICATION',
                       ' TX_MSG_TYPE'):
            with self.subTest(suffix=suffix):
                candidate = RXP3.rstrip('\n') + suffix + '\n'
                r = audit_text(PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + candidate,
                               'VCC-225200-1')
                self.assertEqual(r['totals']['rx_p3_prefix_after_ordered_request_tx_candidates'], 0)

    def test_67_mixed_direction_line_cannot_be_counted_as_rx(self):
        r = audit_text(PREFACE + SELECT + FETCH + RUN + P3 + TXP3 +
                       RXP3.rstrip('\n') + ' ---> inline echo\n', 'VCC-225200-1')
        self.assertEqual(r['totals']['rx_p3_prefix_after_ordered_request_tx_candidates'], 0)

    def test_68_no_expected_script_id_never_promotes_rx_to_ordered(self):
        r = audit_text(PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + RXP3)
        self.assertEqual(r['totals']['rx_p3_prefix_after_ordered_request_tx_candidates'], 0)
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_rx_prefix_candidates'], 0)

    def test_69_running_different_version_cannot_promote_rx(self):
        wrong = "[Script] Running script: 'VCC-225200-1 3.0'\n"
        r = audit_text(PREFACE + SELECT + FETCH + wrong + P3 + TXP3 + RXP3,
                       'VCC-225200-1')
        self.assertEqual(r['totals']['rx_p3_prefix_after_ordered_request_tx_candidates'], 0)

    def test_70_duplicate_rx_prefix_only_consumes_one_outstanding_tx(self):
        r = audit_text(PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + RXP3 + RXP3,
                       'VCC-225200-1')
        self.assertEqual(r['totals']['rx_p3_prefix_after_ordered_request_tx_candidates'], 1)
        self.assertEqual(r['totals']['j2534_rx_p3_positive_prefix_candidates'], 2)

    def test_71_new_logsession_cannot_join_earlier_tx_and_later_rx(self):
        r = audit_text(PREFACE + SELECT + FETCH + RUN + P3 + TXP3 +
                       PREFACE + SELECT + FETCH + RUN + RXP3,
                       'VCC-225200-1')
        self.assertEqual(r['totals']['rx_p3_prefix_after_ordered_request_tx_candidates'], 0)

    def test_72_rx_candidate_counts_never_emit_private_payload(self):
        log = (PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + RXP3 +
               'SENSITIVE_PRIVATE_VIN_MARKER\n')
        report = json.dumps(audit_text(log, 'VCC-225200-1'))
        self.assertNotIn('SENSITIVE_PRIVATE_VIN_MARKER', report)
        self.assertNotIn('VCC-225200-1', report)
        self.assertFalse(json.loads(report)['client_vin_accepted'])
        self.assertFalse(json.loads(report)['actual_positive_ecu_reply_correlated'])


    def test_73_explicit_source_ids_match_three_synthetic_rx_candidates(self):
        log = (PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + RXP3
               + P2A + TXP2A + RXP240 + P2B + TXP2B + RXP250)
        r = audit_text(log, 'VCC-225200-1', self._synthetic_rx_ids())
        self.assertTrue(r['rx_expected_can_id_filter_supplied'])
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_exact_source_rx_prefix_candidates'], 1)
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_rx_prefix_candidates'], 1)
        self.assertFalse(r['actual_positive_ecu_reply_correlated'])
        self.assertFalse(r['client_vin_accepted'])

    def test_74_wrong_p3_response_id_never_promoted_to_exact_match(self):
        log = (PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + RXP3
               + P2A + TXP2A + RXP240 + P2B + TXP2B + RXP250)
        ids = self._synthetic_rx_ids()
        ids['p3_f114'] = 0x72f
        r = audit_text(log, 'VCC-225200-1', ids)
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_rx_prefix_candidates'], 1)
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_exact_source_rx_prefix_candidates'], 0)

    def test_75_wrong_p2_response_id_never_promoted_to_exact_match(self):
        log = (PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + RXP3
               + P2A + TXP2A + RXP240 + P2B + TXP2B + RXP250)
        ids = self._synthetic_rx_ids()
        ids['p2_b9fb_50'] = 0x01200007
        r = audit_text(log, 'VCC-225200-1', ids)
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_rx_prefix_candidates'], 1)
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_exact_source_rx_prefix_candidates'], 0)

    def test_76_no_explicit_source_filter_never_promotes_exact_match(self):
        log = (PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + RXP3
               + P2A + TXP2A + RXP240 + P2B + TXP2B + RXP250)
        r = audit_text(log, 'VCC-225200-1')
        self.assertFalse(r['rx_expected_can_id_filter_supplied'])
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_rx_prefix_candidates'], 1)
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_exact_source_rx_prefix_candidates'], 0)

    def test_77_explicit_source_filter_requires_script_selector(self):
        with self.assertRaises(ValueError):
            audit_text(PREFACE + SELECT, expected_rx_can_ids=self._synthetic_rx_ids())

    def test_78_reject_invalid_or_missing_source_id_dict(self):
        from audit_vida_readvin_bootstrap_trace import _validate_rx_can_ids
        good = self._synthetic_rx_ids()
        variations = (None, {}, {'p3_f114': 0x72e},
                      {'p3_f114': 0x72e, 'p2_b9fb_40': 0x01200003,
                       'p2_b9fb_50': 0x01200005, 'unknown': 1},
                      [0x72e, 0x01200003, 0x01200005])
        for item in variations:
            with self.subTest(item=item):
                if item is None:
                    # None explicitly means backward-compatible no-filter mode.
                    self.assertFalse(audit_text(PREFACE + SELECT, 'VCC-225200-1', item)[
                        'rx_expected_can_id_filter_supplied'])
                else:
                    with self.assertRaises(ValueError):
                        _validate_rx_can_ids(item)
        for key, value in (('p3_f114', True), ('p3_f114', '0x72e'),
                           ('p3_f114', -1), ('p3_f114', 0),
                           ('p3_f114', 0x726), ('p3_f114', 0x800),
                           ('p2_b9fb_40', 0x7ff), ('p2_b9fb_40', 0x01200002),
                           ('p2_b9fb_40', 0x20000001),
                           ('p2_b9fb_50', 0x01200003)):
            with self.subTest(key=key, value=value):
                bad = dict(good)
                bad[key] = value
                with self.assertRaises(ValueError):
                    audit_text(PREFACE + SELECT, 'VCC-225200-1', bad)

    def test_79_source_id_filter_does_not_cross_getscript_window(self):
        log = (PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + RXP3
               + SELECT + FETCH + RUN + P2A + TXP2A + RXP240
               + P2B + TXP2B + RXP250)
        r = audit_text(log, 'VCC-225200-1', self._synthetic_rx_ids())
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_exact_source_rx_prefix_candidates'], 0)

    def test_80_explicit_rx_ids_do_not_count_echo(self):
        echo = '[J2534] <--- (0) 00,00,07,26,62,F1,14,11,\n'
        log = PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + echo
        r = audit_text(log, 'VCC-225200-1', self._synthetic_rx_ids())
        self.assertEqual(r['totals']['rx_p3_prefix_after_ordered_request_tx_candidates'], 0)
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_exact_source_rx_prefix_candidates'], 0)

    def test_81_cli_rejects_partial_or_invalid_rx_address_args(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder, 'private.log')
            out = Path(folder, 'result.json')
            log.write_text(PREFACE + SELECT + FETCH + RUN, encoding='utf-8')
            for extra in (['--rx-p3-can-id', '0x72e'],
                          ['--rx-p3-can-id', '0xXYZ', '--rx-p2-40-can-id', '0x1200003',
                           '--rx-p2-50-can-id', '0x1200005'],
                          ['--rx-p3-can-id', '0x72e', '--rx-p2-40-can-id', '0x1200003',
                           '--rx-p2-50-can-id', '0x1200005']):
                with self.subTest(extra=extra):
                    # The last variant lacks a script selector and must fail.
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                        main([str(log), '--output', str(out)] + extra)
                    self.assertFalse(out.exists())

    def test_82_cli_exact_can_ids_are_redacted(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder, 'private.log')
            out = Path(folder, 'result.json')
            data = (PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + RXP3
                    + P2A + TXP2A + RXP240 + P2B + TXP2B + RXP250)
            log.write_text(data, encoding='utf-8')
            args = [str(log), '--expected-script-id', 'VCC-225200-1',
                    '--rx-p3-can-id', '0x72E', '--rx-p2-40-can-id', '0x01200003',
                    '--rx-p2-50-can-id', '0x01200005', '--output', str(out)]
            with contextlib.redirect_stdout(io.StringIO()):
                main(args)
            report = out.read_text(encoding='utf-8')
            self.assertEqual(json.loads(report)[
                'sessions_with_ordered_expected_script_request_tx_exact_source_rx_prefix_candidates'], 1)
            self.assertTrue(json.loads(report)['rx_expected_can_id_filter_supplied'])
            for token in ('VCC-225200-1', '0x72E', '0x01200003', '0x01200005', str(log)):
                self.assertNotIn(token, report)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(args)

    def test_83_source_match_not_sufficient_without_all_three_family_rx(self):
        log = PREFACE + SELECT + FETCH + RUN + P3 + TXP3 + RXP3 + P2A + TXP2A + RXP240
        r = audit_text(log, 'VCC-225200-1', self._synthetic_rx_ids())
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_exact_source_rx_prefix_candidates'], 0)
        self.assertEqual(r['totals']['rx_p3_prefix_after_ordered_request_tx_candidates'], 1)

    def test_84_source_match_not_sufficient_if_rx_precedes_tx(self):
        log = (PREFACE + SELECT + FETCH + RUN + P3 + RXP3 + TXP3
               + P2A + TXP2A + RXP240 + P2B + TXP2B + RXP250)
        r = audit_text(log, 'VCC-225200-1', self._synthetic_rx_ids())
        self.assertEqual(r['sessions_with_ordered_expected_script_request_tx_exact_source_rx_prefix_candidates'], 0)

    @staticmethod
    def _synthetic_rx_ids():
        # Fixture addresses ONLY, never claimed as measured vehicle addresses.
        return {'p3_f114': 0x72e, 'p2_b9fb_40': 0x01200003,
                'p2_b9fb_50': 0x01200005}

if __name__ == '__main__':
    unittest.main()
