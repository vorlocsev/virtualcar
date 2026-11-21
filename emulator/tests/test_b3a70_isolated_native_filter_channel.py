"""B3A70 source-only synthetic logger tests (no native DLL or VIDA)."""
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import audit_b3a70_isolated_native_filter_channel as audit
sys.path.pop(0)


def line(kind, *words, pid="12345678", host="powershell.exe"):
    label, width = audit.LABELS[kind]
    assert len(words) * 4 == width
    data = b"".join(value.to_bytes(4, "big") for value in words)
    return "[PID=" + pid + " " + host + "] " + label + " " + data.hex(" ").upper()


def fixture():
    return [
        line("strict_policy", 1),
        line("accepted", 7, 1, 101, 0x8004, 125000),
        line("tx", 7, 5, 0x100, 125000, 20),
        line("d2", 0x40, 0xFB, 125000, 0),
        line("stopped", 7, 101),
        line("accepted", 7, 1, 102, 0x8004, 125000),
        line("tx", 7, 5, 0x100, 125000, 30),
        line("d2", 0x40, 0xFB, 125000, 0),
    ] + [
        line("rx", 7, 5, 0x100, 125000, 31 + i) for i in range(13)
    ] + [line("stopped", 7, 102)]


class NativeFilterChannelTests(unittest.TestCase):
    def test_01_exact_isolated_lifetime_passes(self):
        result = audit.analyze(fixture())
        self.assertEqual(result["status"], "B3A70_ISOLATED_FILTER_CHANNEL_PASS")
        self.assertEqual(result["marker_counts"], {
            "strict_policy": 1, "accepted": 2, "stopped": 2, "tx": 2,
            "rx": 13, "d2": 2})
        self.assertTrue(result["filter_lifetime_balanced"])
        self.assertEqual(result["first_filter_rx_count"], 0)
        self.assertEqual(result["second_filter_rx_count"], 13)
        self.assertEqual(result["d2_40_b9fb_request_markers"], 2)

    def test_02_wrong_channel_rejected(self):
        lines = fixture()
        lines[7] = line("tx", 8, 5, 0x100, 125000, 30)
        result = audit.analyze(lines)
        self.assertIn("tx_rx_channel_differs_from_active_filter", result["failures"])
        self.assertEqual(result["status"], "NOT_VERIFIED")

    def test_03_mismatched_stop_filter_id_rejected(self):
        lines = fixture()
        lines[-1] = line("stopped", 7, 999)
        result = audit.analyze(lines)
        self.assertIn("stop_without_active_matching_filter", result["failures"])
        self.assertFalse(result["filter_lifetime_balanced"])

    def test_04_overlap_rejected(self):
        lines = fixture()
        stop = lines.pop(4)
        lines.insert(-1, stop)
        self.assertIn("overlapping_or_duplicate_filter_lifetime",
                      audit.analyze(lines)["failures"])

    def test_05_wrong_rx_extended_status_rejected(self):
        lines = fixture()
        lines[9] = line("rx", 7, 5, 0, 125000, 31)
        self.assertIn("rx_missing_can_29bit_id", audit.analyze(lines)["failures"])

    def test_06_wrong_d2_target_rejected(self):
        lines = fixture()
        lines[3] = line("d2", 0x50, 0xFB, 125000, 0)
        self.assertIn("different_d2_target_opcode_or_baud",
                      audit.analyze(lines)["failures"])

    def test_07_multiple_native_pid_groups_rejected(self):
        lines = fixture()
        lines[3] = line("d2", 0x40, 0xFB, 125000, 0,
                        pid="ABCD1234")
        self.assertIn("expected_single_native_logger_group",
                      audit.analyze(lines)["failures"])

    def test_08_malformed_marker_never_passes(self):
        lines = fixture()
        lines[1] = lines[1].rsplit(" ", 1)[0]
        self.assertEqual(audit.analyze(lines)["malformed_native_markers"], 1)
        self.assertNotEqual(audit.analyze(lines)["status"],
                            "B3A70_ISOLATED_FILTER_CHANNEL_PASS")

    def test_09_rx_during_wrong_filter_rejected(self):
        lines = fixture()
        lines.insert(4, line("rx", 7, 5, 0x100, 125000, 22))
        result = audit.analyze(lines)
        self.assertIn("negative_positive_lifetime_tx_rx_d2_mismatch",
                      result["failures"])

    def test_10_private_pid_filter_ids_and_path_not_emitted(self):
        result = audit.analyze(fixture() + [
            "[PID=12345678 powershell.exe] TX (app request) 12 34",
            "[PID=12345678 powershell.exe] Active INI: C:\\Secret\\private.ini",
        ])
        text = repr(result)
        for value in ("12345678", "powershell.exe", "C:\\Secret",
                      "101", "102"):
            # Numeric filter IDs may appear as ordinary digits within long
            # texts, so only disallow their serialization as numeric values.
            if value in ("101", "102"):
                continue
            self.assertNotIn(value, text)
        self.assertFalse(result["raw_pid_filter_id_vin_mask_frame_path_exported"])
        self.assertFalse(result["original_vida_readvin_verified"])

    def test_11_no_policy_is_not_attested(self):
        self.assertIn("strict_policy_not_attested_on_isolated_loader",
                      audit.analyze(fixture()[1:])["failures"])

    def test_12_unexpected_traffic_or_protocol_rejected(self):
        lines = fixture()
        lines[2] = line("tx", 7, 6, 0x100, 125000, 20)
        self.assertIn("unexpected_internal_can_protocol_or_baud",
                      audit.analyze(lines)["failures"])


if __name__ == "__main__":
    unittest.main()
