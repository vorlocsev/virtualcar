"""Synthetic privacy and exact-append tests for the B3A55 transaction auditor."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import audit_vida_j2534_session_window as window
import audit_vida_j2534_window_transactions as tool
sys.path.pop(0)


def be(*words):
    return b"".join(value.to_bytes(4, "big") for value in words).hex(" ").upper()


def line(message, pid="1234ABCD", host="iexplore.exe"):
    return f"[PID={pid} {host}] {message}\n"


def tx_context(channel=1, protocol=5, baud=500000, stamp=100000):
    return line("TX context channel/protocol/flags/baud/time-us (BE) " +
                be(channel, protocol, 0, baud, stamp))


def rx_context(channel=1, protocol=5, baud=500000, stamp=102000):
    return line("RX context channel/protocol/status/baud/time-us (BE) " +
                be(channel, protocol, 0, baud, stamp))


class VidaWindowTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.log = root / "SectorVVirtualCar.log"
        self.vida = root / "VIDA.log"
        self.baseline = root / "private" / "baseline.json"
        self.log.write_text("old prefix\n", encoding="utf-8")
        self.vida.write_text("old VIDA prefix\n", encoding="utf-8")
        self.baseline.parent.mkdir()
        data = {
            "schema_version": window.SCHEMA,
            "private_do_not_publish": True,
            "original_vida": window._snapshot(self.vida),
            "virtual_j2534": window._snapshot(self.log),
        }
        self.baseline.write_text(json.dumps(data), encoding="utf-8")

    def report(self):
        return tool.analyze_window(self.log, self.baseline, "iexplore")

    def test_01_accepted_write_is_classified_without_open_marker(self):
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(tx_context())
            stream.write(line("TX (app request) 00 00 07 26 03 22 F1 90"))
        report = self.report()
        self.assertEqual(report["native_marker_counts"]["app_tx"], 1)
        self.assertEqual(report["native_marker_counts"]["open_success"], 0)
        self.assertEqual(report["recognized_transactions"], 1)
        item = report["transaction_groups"][0]
        self.assertEqual((item["can_id"], item["target"], item["route"],
                          item["service"], item["protocol"],
                          item["baud_bps"], item["status"]),
                         ("0x726", None, "P3", "22F190", "CAN", 500000, "unverified"))
        self.assertFalse(report["original_vida_vin_accepted_verified"])

    def test_02_host_category_filter_excludes_other_process(self):
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(tx_context())
            stream.write(line("TX (app request) 00 00 07 26 03 22 F1 90"))
            stream.write(line("TX context channel/protocol/flags/baud/time-us (BE) " +
                              be(2, 5, 0, 500000, 200000),
                              pid="AABBCCDD", host="java.exe"))
            stream.write(line("TX (app request) 00 00 07 26 03 22 F1 90",
                              pid="AABBCCDD", host="java.exe"))
        report = self.report()
        self.assertEqual(report["selected_host_lines"], 2)
        self.assertEqual(report["native_marker_counts"]["app_tx"], 1)
        self.assertEqual(report["recognized_transactions"], 1)

    def test_03_timeout_is_distinguished_from_silent_unverified(self):
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(tx_context())
            stream.write(line("TX (app request) 00 00 07 26 03 22 F1 90"))
            stream.write(line("PassThruReadMsgs timeout: channel / wait-ms / consecutive-count (BE) " +
                              be(1, 100, 1)))
        report = self.report()
        self.assertEqual(report["native_marker_counts"]["read_timeout"], 1)
        self.assertEqual(report["transaction_groups"][0]["status"], "timeout")
        self.assertEqual(report["transaction_groups"][0]["reason"],
                         "j2534_read_timeout_observed")

    def test_04_rx_delivery_is_transport_only_not_client_acceptance(self):
        response = "00 00 07 2E 07 62 F1 90 59 56 31 43"
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(tx_context())
            stream.write(line("TX (app request) 00 00 07 26 03 22 F1 90"))
            stream.write(rx_context())
            stream.write(line("PassThruReadMsgs -> delivered " + response))
        report = self.report()
        self.assertEqual(report["native_marker_counts"]["rx_delivered"], 1)
        item = report["transaction_groups"][0]
        self.assertEqual((item["status"], item["reason"]),
                         ("delivered", "p3_uds_transport_only"))
        self.assertEqual(report["client_result"], "UNKNOWN")
        self.assertFalse(report["original_vida_vin_accepted_verified"])
        self.assertNotIn("YV1CR855691511566", json.dumps(report))

    def test_05_payload_and_source_identity_are_not_exported(self):
        secret = "YV1CR855691511566"
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(tx_context())
            stream.write(line("TX (app request) 00 00 07 26 03 22 F1 90 " + secret))
        report = self.report()
        encoded = json.dumps(report)
        self.assertNotIn(secret, encoded)
        self.assertNotIn(str(self.log), encoded)
        self.assertNotIn("1234ABCD", encoded)
        self.assertFalse(report["raw_payload_vin_pid_path_and_source_lines_exported"])

    def test_06_changed_log_prefix_fails_closed(self):
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(line("TX (app request) 00 00 07 26 03 22 F1 90"))
        self.log.write_text("mutated old prefix\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "prefix changed"):
            self.report()

    def test_07_other_host_is_not_a_fallback(self):
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(line("TX (app request) 00 00 07 26 03 22 F1 90",
                              host="java.exe"))
        report = self.report()
        self.assertEqual(report["selected_host_lines"], 0)
        self.assertEqual(report["recognized_transactions"], 0)

    def test_08_no_identity_claim_even_with_complete_transport_header(self):
        response = "00 00 07 2E 07 62 F1 90 59 56 31 43"
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(tx_context())
            stream.write(line("TX (app request) 00 00 07 26 03 22 F1 90"))
            stream.write(rx_context())
            stream.write(line("PassThruReadMsgs -> delivered " + response))
        report = self.report()
        self.assertEqual(report["native_d2_delivery_tags"]["physical_can_or_ecu_provenance"],
                         "not_verified")
        self.assertEqual(report["native_d2_delivery_tags"]["client_vin_and_ecu_acceptance"],
                         "not_verified")
        self.assertFalse(report["ecu_identity_accepted_verified"])


    def test_09_native_queue_clear_and_d2_fixture_events_are_counted(self):
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(tx_context())
            stream.write(line("TX (app request) 00 00 07 26 03 22 F1 90"))
            stream.write(line("RX (simulated) 00 00 07 2E 03 62 F1 90"))
            stream.write(line("J2534 CLEAR_RX_BUFFER: queued D2/raw ISO-TP and staged CF dropped"))
            stream.write(line("P2 D2 read command: no validated response fixture"))
        report = self.report()
        counts = report["native_marker_counts"]
        self.assertEqual(counts["rx_enqueued"], 1)
        self.assertEqual(counts["clear_rx_buffer"], 1)
        self.assertEqual(counts["d2_no_fixture"], 1)
        self.assertEqual(counts["rx_delivered"], 0)

    def test_10_native_cem_no_fixture_and_unmatched_events_are_counted(self):
        with self.log.open("a", encoding="utf-8") as stream:
            stream.write(line("P3 CEM F114 probe: no configured CEM fixture; no response"))
            stream.write(line("Unmatched request ID / protocol, no response"))
        counts = self.report()["native_marker_counts"]
        self.assertEqual(counts["p3_cem_f114_no_fixture"], 1)
        self.assertEqual(counts["p3_unmatched"], 1)



if __name__ == "__main__":
    unittest.main()
