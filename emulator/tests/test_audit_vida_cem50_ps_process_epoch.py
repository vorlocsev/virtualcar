"""B3A72 synthetic process-epoch PS/INI evidence contracts. No live VIDA/J2534."""
from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_cem50_ps_process_epoch as audit
sys.path.pop(0)

DLL = r"C:\ProgramData\J2534-CEM50-PS\J2534CEM50PS.dll"
INI = r"C:\ProgramData\J2534-CEM50-PS\virtualcar.ini"
PID = 42
FILETIME = 133000000000000000


def line(event, pid=PID, host="iexplore.exe"):
    return "[PID=%08X %s] %s" % (pid, host, event)


def metadata(target, opcode, count, *, extra=False):
    data = b"".join(v.to_bytes(4, "big") for v in
                    (target, opcode, 0x00800003, count))
    return line("P2 fixture target/opcode/response-id/frame-count (BE) " +
                data.hex(" ").upper())


def epoch_marker(value=FILETIME, pid=PID):
    raw = value.to_bytes(8, "big")
    return line("Process creation FILETIME (BE) " + raw.hex(" ").upper(), pid)


def history(path=INI):
    defaults = ((0x40, 0xFB), (0x40, 0xF0), (0x50, 0xFB),
                (0x50, 0xF0), (0x40, 0xFC), (0x50, 0xFC))
    return [epoch_marker(), line("Active INI: " + path)] + [
        metadata(t, op, 13 if i == 2 else 0)
        for i, (t, op) in enumerate(defaults)
    ] + [metadata(0, 0, 0)] * 8


def request(pid=PID, host="iexplore.exe", target=0x40, opcode=0xFB):
    data = b"".join(v.to_bytes(4, "big") for v in
                    (target, opcode, 125000, 0x100))
    return [line("TX (app request) 00 0F FF FE CB 40 B9 FB", pid, host),
            line("P2 D2 request target/opcode/baud/flags (BE) " +
                 data.hex(" ").upper(), pid, host)]


def process(pid=PID, dll=DLL, modules=None):
    return {"exe": "iexplore.exe", "pid": pid,
            "modules": [dll] if modules is None else modules,
            "creation_filetime": FILETIME}


class SamePidTest(unittest.TestCase):
    def test_01_two_routes_native_fixture_counts(self):
        out = audit.analyze(history(), request(), [process()], disk_sha="7F21E2606C6E7981ECDEDFE6769F180981C6DDFFFFBCC5C35CD4A6E983C98C3E")
        self.assertEqual(out["status"], "CORRELATED_SAME_PROCESS_EPOCH_EXACT_DLL_ACTIVE_INI")
        self.assertTrue(out["process_creation_epoch_verified"])
        self.assertTrue(out["process_creation_epoch_marker_present"])
        self.assertEqual(out["native_loaded_b9fb_cem40"], "zero_frames_loaded")
        self.assertEqual(out["native_loaded_b9fb_cem50"], "frames_loaded_unverified")
        self.assertTrue(out["same_text_pid_live_exact_dll"])
        self.assertTrue(out["logged_ini_path_matches_dll_directory"])
        self.assertTrue(out["disk_sha_matches_pinned"])

    def test_02_no_b9fb_log_request(self):
        out = audit.analyze(history(), [], [process()])
        self.assertEqual(out["status"], "NO_D2_B9FB_REQUEST_PID")

    def test_03_multiple_native_pids(self):
        out = audit.analyze(history(), request() + request(pid=43), [process()])
        self.assertEqual(out["status"], "AMBIGUOUS_D2_B9FB_PIDS")

    def test_04_no_live_same_pid(self):
        out = audit.analyze(history(), request(), [process(43)])
        self.assertEqual(out["status"], "NO_LIVE_MATCHING_PROCESS_PID")

    def test_05_uninspected_module(self):
        out = audit.analyze(history(), request(), [{"exe": "iexplore.exe",
            "pid": PID, "modules": None}])
        self.assertEqual(out["status"], "MODULE_ENUMERATION_BLOCKED")

    def test_06_same_basename_wrong_dll_path(self):
        out = audit.analyze(history(), request(),
                            [process(dll=r"C:\Other\J2534CEM50PS.dll")])
        self.assertEqual(out["status"], "NO_EXACT_PS_DLL_FOR_REQUEST_PID")

    def test_07_no_active_ini_before_request(self):
        out = audit.analyze([], request(), [process()])
        self.assertEqual(out["status"], "NO_ACTIVE_INI_AFTER_PROCESS_EPOCH")

    def test_08_wrong_logged_ini(self):
        out = audit.analyze(history(path=r"C:\Other\virtualcar.ini"),
                            request(), [process()])
        self.assertEqual(out["status"], "ACTIVE_INI_MARKER_POINTS_ELSEWHERE")

    def test_09_incomplete_native_fixture_metadata(self):
        out = audit.analyze([line("Active INI: " + INI)], request(), [process()])
        self.assertEqual(out["status"], "MATCHED_PATH_WITH_INCOMPLETE_INIT_METADATA")
        self.assertEqual(out["native_loaded_fixture_metadata"], "incomplete_or_malformed")

    def test_10_wrong_host_is_not_claimed(self):
        out = audit.analyze(history(), request(host="java.exe"), [process()])
        self.assertEqual(out["status"], "NO_UNAMBIGUOUS_REQUEST_PID_IN_CHOSEN_HOST")

    def test_11_serialization_never_exposes_secrets_or_pid(self):
        out = audit.analyze(history(), request(), [process()])
        blob = json.dumps(out)
        for secret in ("0000002A", "C:\\", "J2534CEM50PS.dll", "00 0F FF FE",
                       "YV1", "00800003", str(FILETIME)):
            self.assertNotIn(secret, blob)
        self.assertTrue(out["process_creation_epoch_verified"])
        for key in ("ini_bytes_loaded_verified", "original_vida_readvin_verified",
                    "ecu_rx_delivered_verified"):
            self.assertFalse(out[key])
        self.assertFalse(out["source_contains_private_pid_path_or_payload"])

    def test_13_missing_epoch_marker_keeps_pid_only_status(self):
        rows = [row for row in history() if not row.startswith("[PID=" + "%08X" % PID + " iexplore.exe] Process creation FILETIME")]
        out = audit.analyze(rows, request(), [process()])
        self.assertEqual(out["status"], "CORRELATED_SAME_TEXT_PID_EPOCH_NOT_ATTESTED")
        self.assertFalse(out["process_creation_epoch_marker_present"])
        self.assertFalse(out["process_creation_epoch_verified"])

    def test_14_reused_pid_epoch_mismatch_is_rejected(self):
        current = process()
        current["creation_filetime"] = FILETIME + 1
        out = audit.analyze(history(), request(), [current])
        self.assertEqual(out["status"], "PROCESS_CREATION_EPOCH_MISMATCH")
        self.assertFalse(out["process_creation_epoch_verified"])

    def test_15_live_creation_time_unavailable_is_inconclusive(self):
        current = process()
        current["creation_filetime"] = None
        out = audit.analyze(history(), request(), [current])
        self.assertEqual(out["status"], "PROCESS_CREATION_EPOCH_LIVE_TIME_UNAVAILABLE")
        self.assertFalse(out["process_creation_epoch_verified"])

    def test_16_latest_epoch_marker_wins_for_reused_pid(self):
        rows = [epoch_marker(FILETIME - 1)] + history()
        out = audit.analyze(rows, request(), [process()])
        self.assertEqual(out["status"], "CORRELATED_SAME_PROCESS_EPOCH_EXACT_DLL_ACTIVE_INI")
        self.assertTrue(out["process_creation_epoch_verified"])

    def test_17_epoch_marker_after_request_is_not_used(self):
        defaults = ((0x40, 0xFB), (0x40, 0xF0), (0x50, 0xFB),
                    (0x50, 0xF0), (0x40, 0xFC), (0x50, 0xFC))
        rows = [line("Active INI: " + INI)] + [
            metadata(t, op, 13 if i == 2 else 0)
            for i, (t, op) in enumerate(defaults)
        ] + [metadata(0, 0, 0)] * 8
        out = audit.analyze(rows, request() + [epoch_marker()], [process()])
        self.assertEqual(out["status"], "CORRELATED_SAME_TEXT_PID_EPOCH_NOT_ATTESTED")
        self.assertFalse(out["process_creation_epoch_verified"])

    def test_18_malformed_epoch_marker_is_not_attested(self):
        rows = [line("Process creation FILETIME (BE) 00 11"),
                line("Active INI: " + INI)] + [
                    metadata(t, op, 13 if i == 2 else 0)
                    for i, (t, op) in enumerate(((0x40, 0xFB), (0x40, 0xF0),
                        (0x50, 0xFB), (0x50, 0xF0), (0x40, 0xFC), (0x50, 0xFC)))
                ] + [metadata(0, 0, 0)] * 8
        out = audit.analyze(rows, request(), [process()])
        self.assertEqual(out["status"], "PROCESS_CREATION_EPOCH_MARKER_MALFORMED")
        self.assertFalse(out["process_creation_epoch_verified"])

    def test_19_active_ini_before_latest_epoch_is_not_reused(self):
        rows = [line("Active INI: " + INI)] + [
            metadata(t, op, 13 if i == 2 else 0)
            for i, (t, op) in enumerate(((0x40, 0xFB), (0x40, 0xF0),
                (0x50, 0xFB), (0x50, 0xF0), (0x40, 0xFC), (0x50, 0xFC)))
        ] + [metadata(0, 0, 0)] * 8 + [epoch_marker()]
        out = audit.analyze(rows, request(), [process()])
        self.assertEqual(out["status"], "NO_ACTIVE_INI_AFTER_PROCESS_EPOCH")
        self.assertFalse(out["same_text_pid_native_active_ini"])

    def test_12_disk_hash_mismatch_is_not_validation(self):
        out = audit.analyze(history(), request(), [process()], disk_sha="0" * 64)
        self.assertFalse(out["disk_sha_matches_pinned"])
        self.assertEqual(out["status"], "SAME_PROCESS_EPOCH_BUT_DISK_SHA_UNVERIFIED")
        self.assertFalse(out["original_vida_readvin_verified"])


if __name__ == "__main__":
    unittest.main()
