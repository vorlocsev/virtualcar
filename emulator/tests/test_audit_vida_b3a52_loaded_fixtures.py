"""B3A52: eight synthetic, source-backed D2 fixture attribution gates."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_b3a52_loaded_fixtures as audit
sys.path.pop(0)

PID = "[PID=1234ABCD iexplore.exe] "
OTHER = "[PID=ABCDE123 iexplore.exe] "
SLOTS = [(0x40, 0xFB), (0x40, 0xF0), (0x50, 0xFB),
         (0x50, 0xF0), (0x40, 0xFC), (0x50, 0xFC)] + [
             (0x60 + i, 0xFB) for i in range(8)]


def words(*values):
    return " ".join(f"{byte:02X}" for n in values
                    for byte in n.to_bytes(4, "big")) + " "


def init(pid=PID, counts=None, name="virtualcar.ini"):
    counts = counts or {}
    rows = [pid + audit.ACTIVE + "C:\\Private\\" + name]
    for i, (target, opcode) in enumerate(SLOTS):
        rows.append(pid + audit.FIXTURE +
                    words(target, opcode, 0x01200003, counts.get(i, 0)))
    return rows


def request(pid=PID):
    return pid + audit.D2_REQUEST + words(0x50, 0xFB, 250000, 0)


class NativeLoadedD2Tests(unittest.TestCase):
    def test_01_zero_loaded_b9fb_in_same_pid_history(self):
        out = audit.classify_initialization(init(), [request()] * 6)
        self.assertEqual(out["observed_d2_b9fb_requests"], 6)
        self.assertEqual(out["init_fixture_metadata"], "14_native_fixture_records_classified")
        self.assertEqual(out["loaded_d2_b9fb"]["CEM_40"], "zero_frames_loaded")
        self.assertEqual(out["loaded_d2_b9fb"]["CEM_50"], "zero_frames_loaded")

    def test_02_nonzero_loaded_cannot_prove_original_ecu(self):
        out = audit.classify_initialization(init(counts={0: 13, 2: 13}),
                                           [request()])
        self.assertEqual(out["loaded_d2_b9fb"]["CEM_40"], "frames_loaded_unverified")
        self.assertEqual(out["loaded_d2_b9fb"]["CEM_50"], "frames_loaded_unverified")
        self.assertFalse(out["oem_reply_authenticated"])
        self.assertFalse(out["vin_accepted"])

    def test_03_no_history_does_not_infer_loaded_ini(self):
        out = audit.classify_initialization([], [request()])
        self.assertEqual(out["init_record"], "not_found_in_bounded_prebaseline_tail")
        self.assertEqual(out["loaded_d2_b9fb"]["CEM_40"], "not_observed")

    def test_04_other_pid_cannot_bind_historical_init(self):
        out = audit.classify_initialization(init(OTHER), [request()])
        self.assertEqual(out["init_fixture_metadata"], "not_observed")
        self.assertFalse(out["original_vida_process_attested"])

    def test_05_multiple_request_pids_fail_closed_and_are_redacted(self):
        out = audit.classify_initialization(init(), [request(), request(OTHER)])
        self.assertEqual(out["init_record"], "ambiguous_multiple_native_logger_pids")
        for secret in ("1234ABCD", "ABCDE123", "iexplore.exe", "C:\\Private\\"):
            self.assertNotIn(secret, json.dumps(out))

    def test_06_missing_or_malformed_native_words_fail_closed(self):
        first = audit.classify_initialization(init()[:-1], [request()])
        second = audit.classify_initialization(init()[:-1] + [
            PID + audit.FIXTURE + "XX BAD BYTES"], [request()])
        self.assertEqual(first["init_fixture_metadata"], "incomplete_or_malformed")
        self.assertEqual(second["init_fixture_metadata"], "incomplete_or_malformed")

    def test_07_only_latest_init_accepted_but_not_runtime_attested(self):
        out = audit.classify_initialization(
            init(counts={2: 13}) + init(counts={0: 13}), [request()])
        self.assertEqual(out["loaded_d2_b9fb"]["CEM_40"], "frames_loaded_unverified")
        self.assertEqual(out["loaded_d2_b9fb"]["CEM_50"], "zero_frames_loaded")
        self.assertFalse(out["original_vida_process_attested"])

    def test_08_wrong_ini_name_out_of_bounds_and_bad_order(self):
        wrong = audit.classify_initialization(init(name="other.ini"), [request()])
        self.assertEqual(wrong["init_record"], "native_marker_with_unexpected_ini_filename")
        # Invalid data beyond the native logger line boundary cannot change classification.
        long = [PID + audit.ACTIVE + ("A" * 600) + "\\virtualcar.ini"]
        self.assertEqual(audit.classify_initialization(long, [request()])["init_fixture_metadata"],
                         "not_observed")
        rows = init()
        rows[1], rows[3] = rows[3], rows[1]
        out = audit.classify_initialization(rows, [request()])
        self.assertEqual(out["init_fixture_metadata"], "unexpected_base_fixture_order")


if __name__ == "__main__":
    unittest.main()
