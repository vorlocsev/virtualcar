"""B3A68 pure source-only tests: no live VIDA/J2534, VIN or raw logfile."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import audit_vida_b3a68_d2_filter_window as audit
sys.path.pop(0)

PID = 0xA1B2C3D4


def line(label, pid=PID, host="iexplore.exe"):
    return f"[PID={pid:08X} {host}] {label}"


def be(label, words, pid=PID, host="iexplore.exe"):
    data = b"".join(n.to_bytes(4, "big") for n in words)
    return line(label + " " + data.hex(" ").upper(), pid, host)


def request(pid=PID, host="iexplore.exe", target=0x40, rate=125000):
    return be(audit.LABEL_REQUEST, (target, 0xFB, rate, 0x100), pid, host)


def ftriplet(mask=0x00000001, pat=0x00000001, typ=1, pid=PID,
             host="iexplore.exe"):
    return [
        be(audit.LABEL_FILTER, (typ, 55), pid, host),
        be(audit.LABEL_MASK, (mask,), pid, host),
        be(audit.LABEL_PATTERN, (pat,), pid, host),
    ]


class OriginalD2FilterTests(unittest.TestCase):
    def test_01_same_pid_odd_filter_precedes_request(self):
        hist = [line("Active INI: C:\\Private\\virtualcar.ini")] + ftriplet()
        out = audit.analyze(hist, [request()])
        self.assertEqual(out["status"], "SAME_TEXT_PID_FILTER_CANDIDATES_NOT_CHANNEL_ATTESTED")
        self.assertEqual(out["preceding_scope"], "after_last_same_text_pid_active_ini_marker")
        self.assertEqual(out["d2_40_b9fb_requests_in_append"], 1)
        self.assertEqual(out["complete_filter_mask_pattern_triplets"], 1)
        self.assertEqual(out["pass_filter_would_match_lab_id"], 1)
        self.assertEqual(out["pass_odd_bit_only_filter_candidate"], 1)
        self.assertFalse(out["actual_filter_channel_verified"])

    def test_02_wrong_exact_pass_filter_is_not_a_match(self):
        out = audit.analyze([line("Active INI: X")] +
                            ftriplet(0xFFFFFFFF, 0x00800002),
                            [request()])
        self.assertEqual(out["pass_filter_would_match_lab_id"], 0)
        self.assertEqual(out["complete_filter_mask_pattern_triplets"], 1)

    def test_03_right_exact_pass_filter_is_a_match(self):
        out = audit.analyze([line("Active INI: X")] +
                            ftriplet(0xFFFFFFFF, 0x00800003),
                            [request()])
        self.assertEqual(out["pass_exact_lab_id_filter_candidate"], 1)

    def test_04_prior_block_would_match_not_success(self):
        out = audit.analyze([line("Active INI: X")] +
                            ftriplet(0x00000001, 0x00000001, typ=2),
                            [request()])
        self.assertEqual(out["pass_filter_would_match_lab_id"], 0)
        self.assertEqual(out["block_filter_would_match_lab_id"], 1)

    def test_05_filter_after_request_is_not_prior_evidence(self):
        out = audit.analyze([], [request()] + ftriplet())
        self.assertEqual(out["filter_start_records_preceding"], 0)
        self.assertEqual(out["pass_filter_would_match_lab_id"], 0)

    def test_06_other_pid_filter_does_not_count(self):
        out = audit.analyze([line("Active INI: X")] +
                            ftriplet(pid=0x01020304), [request()])
        self.assertEqual(out["filter_start_records_preceding"], 0)

    def test_07_wrong_host_not_accepted(self):
        out = audit.analyze([], [request(host="java.exe")])
        self.assertEqual(out["status"], "NO_D2_40_B9FB_REQUEST_IN_APPEND")

    def test_08_d2_50_does_not_match_d2_40(self):
        out = audit.analyze([], [request(target=0x50)])
        self.assertEqual(out["status"], "NO_D2_40_B9FB_REQUEST_IN_APPEND")

    def test_09_multiple_native_pid_groups_fail_closed(self):
        out = audit.analyze([], [request(), request(pid=0x00001122)])
        self.assertEqual(out["status"], "AMBIGUOUS_MULTIPLE_NATIVE_LOGGER_PIDS")

    def test_10_repeated_same_pid_requests_fail_closed(self):
        out = audit.analyze([], [request(), request()])
        self.assertEqual(out["status"], "MULTIPLE_SAME_PID_REQUESTS_UNATTRIBUTABLE")

    def test_11_interleaved_mask_pattern_is_incomplete(self):
        hist = [line("Active INI: X"),
                be(audit.LABEL_FILTER, (1, 4)),
                be(audit.LABEL_MASK, (1,)),
                line("unrelated event", pid=0xAAAA0000),
                be(audit.LABEL_PATTERN, (1,))]
        out = audit.analyze(hist, [request()])
        self.assertEqual(out["complete_filter_mask_pattern_triplets"], 0)
        self.assertEqual(out["incomplete_filter_triplets"], 1)
        self.assertEqual(out["status"], "NO_COMPLETE_SAME_TEXT_PID_FILTER_BEFORE_REQUEST")

    def test_12_connect_result_and_setconfig_are_not_channel_attribution(self):
        hist = [line("Active INI: X"),
                be(audit.LABEL_CONNECT, (0x8004, 0, 125000, 0)),
                be(audit.LABEL_CONNECT, (5, 0, 500000, 3)),
                be(audit.LABEL_CONFIG, (1, 0, 0, 0))] + ftriplet()
        out = audit.analyze(hist, [request()])
        modes = out["connect_modes_preceding"]
        self.assertIn({"protocol": "CAN_PS", "baud_bps": "125000",
                       "result": "success", "count": 1}, modes)
        self.assertIn({"protocol": "CAN", "baud_bps": "500000",
                       "result": "nonzero_result", "count": 1}, modes)
        self.assertEqual(out["set_config_records_preceding"], 1)
        self.assertFalse(out["actual_filter_channel_verified"])

    def test_13_without_init_marker_only_append_window_counts(self):
        hist = ftriplet()
        out = audit.analyze(hist, ftriplet() + [request()])
        self.assertEqual(out["preceding_scope"], "append_only_no_prior_active_ini_marker")
        self.assertEqual(out["filter_start_records_preceding"], 1)

    def test_14_old_init_is_superseded_by_latest_marker(self):
        hist = [line("Active INI: X")] + ftriplet() + [
            line("Active INI: Y")] + ftriplet(0xFFFFFFFF, 0x00800002)
        out = audit.analyze(hist, [request()])
        self.assertEqual(out["complete_filter_mask_pattern_triplets"], 1)
        self.assertEqual(out["pass_filter_would_match_lab_id"], 0)

    def test_15_no_identity_pids_paths_or_raw_masks_leave_report(self):
        hist = [line("Active INI: C:\\Secret\\YV1XX000000000000")] + ftriplet()
        out = audit.analyze(hist, [request()])
        result = json.dumps(out)
        for secret in ("A1B2C3D4", "C:\\Secret", "YV1XX",
                       "0x00800003", "00000001", "filter mask "):
            self.assertNotIn(secret, result)
        self.assertFalse(out["original_vida_filter_installer_attested"])
        self.assertFalse(out["actual_vida_readvin_verified"])
        self.assertFalse(out["j2534_rx_delivered_verified"])

    def test_16_invalid_host_rejected(self):
        with self.assertRaises(ValueError):
            audit.analyze([], [], "unknown.exe")


if __name__ == "__main__":
    unittest.main()
