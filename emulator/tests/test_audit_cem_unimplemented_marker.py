"""Eight synthetic checks for exact native CEM no-response marker attribution.

All requests are invented transport envelopes, never OEM credentials or
real CEM security operands. No actual vehicle/adapter is used.
"""
import json
import unittest

from test_audit_j2534_discovery import tool, tx, rx, event, be


MARKER = "P2 D2 CEM A3/A6: no verified response implementation"


def a3(target=0x50, channel=1, **kwargs):
    # Three-byte, zero-operand synthetic request: shape only.
    return tx(0xFFFFE, bytes((0xCA, target, 0xA3, 0, 0, 0, 0, 0)),
              ch=channel, **kwargs)


def a6(target=0x50, channel=1, **kwargs):
    # Invented parameter key. This is not a real ignition state or CEM data.
    return tx(0xFFFFE, bytes((0xCD, target, 0xA6, 0x24, 0x42, 1, 0, 0)),
              ch=channel, **kwargs)


def status(lines):
    return tool.audit(lines)["transactions"][0]


class NativeUnimplementedCemTests(unittest.TestCase):
    def test_01_explicit_a3_50_unimplemented_not_generic_timeout(self):
        one = status(a3() + [event(MARKER)])
        self.assertEqual((one["status"], one["reason"]),
                         ("unsupported", "cem_response_not_implemented"))
        self.assertEqual((one["service"], one["target"], one["rx_frames"]),
                         ("A3", "0x50", 0))
        self.assertTrue(one["native_cem_response_unimplemented"])
        self.assertFalse(one["j2534_timeout_observed"])

    def test_02_a6_40_marker_and_real_read_timeout_are_distinct(self):
        lines = a6(target=0x40, channel=3, baud=125000)
        lines += [event(MARKER),
                  event("PassThruReadMsgs timeout: channel / wait-ms / consecutive-count (BE)",
                        be(3, 500, 1))]
        one = status(lines)
        self.assertEqual((one["status"], one["reason"]),
                         ("unsupported", "cem_response_not_implemented"))
        self.assertTrue(one["native_cem_response_unimplemented"])
        self.assertTrue(one["j2534_timeout_observed"])
        self.assertEqual(one["baud_bps"], 125000)

    def test_03_timeout_without_native_marker_remains_timeout(self):
        lines = a3()
        lines += [event("PassThruReadMsgs timeout: channel / wait-ms / consecutive-count (BE)",
                        be(1, 500, 1))]
        one = status(lines)
        self.assertEqual((one["status"], one["reason"]),
                         ("timeout", "j2534_read_timeout_observed"))
        self.assertFalse(one["native_cem_response_unimplemented"])
        self.assertTrue(one["j2534_timeout_observed"])

    def test_04_exact_marker_only_not_near_match_or_source_spoof(self):
        for fake in (MARKER + " CORRUPTED", "prefix " + MARKER,
                     "P2 D2 CEM A3/A6: unverified response implementation",
                     "P2 D2 CEM A3/A6: no verified response fixture"):
            with self.subTest(fake=fake):
                one = status(a3() + [event(fake)])
                self.assertFalse(one["native_cem_response_unimplemented"])
                self.assertEqual(one["status"], "unverified")

    def test_05_marker_does_not_reclassify_b9fb_or_p3(self):
        d2 = tx(0xFFFFE, bytes.fromhex("CB 50 B9 FB 00 00 00 00"), ch=1)
        p3 = tx(0x726, bytes.fromhex("22 F1 14"), ch=2, proto=6)
        data = tool.audit(d2 + [event(MARKER)] + p3 + [event(MARKER)])
        self.assertEqual(len(data["transactions"]), 2)
        self.assertTrue(all(item["status"] == "unverified"
                            for item in data["transactions"]))
        self.assertTrue(all(not item["native_cem_response_unimplemented"]
                            for item in data["transactions"]))

    def test_06_multiple_channels_marker_targets_latest_tx_only(self):
        lines = a3(target=0x50, channel=1)
        lines += a6(target=0x40, channel=2, baud=125000)
        lines += [event(MARKER)]
        result = {item["channel"]: item for item in tool.audit(lines)["transactions"]}
        self.assertEqual((result[1]["status"], result[2]["status"]),
                         ("unverified", "unsupported"))
        self.assertFalse(result[1]["native_cem_response_unimplemented"])
        self.assertTrue(result[2]["native_cem_response_unimplemented"])

    def test_07_foreign_process_and_unknown_target_never_bound(self):
        other = event(MARKER, pid="FEEDCAFE")
        one = status(a3() + [other])
        self.assertFalse(one["native_cem_response_unimplemented"])
        self.assertEqual(one["status"], "unverified")
        unknown = tx(0xFFFFE, bytes.fromhex("A3 00 00 00 00 00 00 00"), ch=1)
        one = status(unknown + [event(MARKER)])
        self.assertIsNone(one["target"])
        self.assertFalse(one["native_cem_response_unimplemented"])

    def test_08_marker_plus_conflicting_rx_unverified_and_private_free(self):
        # Synthetic CD/E6 framing, not an authenticated ECU response.
        lines = a6()
        lines += [event(MARKER)]
        lines += rx(0x01200003, bytes.fromhex("CD 50 E6 24 42 53 00 00"), ch=1)
        result = tool.audit(lines)
        one = result["transactions"][0]
        self.assertEqual((one["status"], one["reason"]),
                         ("unverified", "cem_unimplemented_marker_rx_conflict"))
        self.assertEqual(one["rx_frames"], 1)
        self.assertTrue(one["native_cem_response_unimplemented"])
        report = json.dumps(result)
        for banned in ("DEADBEEF", "DiagnosticClient", "24 42 53", "FEEDCAFE"):
            self.assertNotIn(banned, report)
        self.assertFalse(result["replay_approved"])
        self.assertFalse(result["contains_payload_data"])


if __name__ == "__main__":
    unittest.main()
