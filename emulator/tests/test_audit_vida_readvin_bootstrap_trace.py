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


if __name__ == '__main__':
    unittest.main()
