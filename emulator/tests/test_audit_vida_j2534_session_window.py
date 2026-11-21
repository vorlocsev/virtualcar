"""Eight synthetic paired-log-window gates; no VIDA process or real VIN."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_j2534_session_window as tool
sys.path.pop(0)

PID = "[PID=1234ABCD iexplore.exe] "


def line(message, host=PID):
    return host + message + "\n"


def metadata(*values):
    return " ".join(f"{b:02X}" for n in values for b in n.to_bytes(4, "big"))


class VidaDualWindowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.vida = root / "Vida.log"
        self.virtual = root / "SectorVVirtualCar.log"
        self.baseline = root / "owner-private" / "baseline.json"
        self.output = root / "owner-private" / "categorical.json"

    def invoke(self, mode, output=True):
        args = [mode, "--vida-log", str(self.vida),
                "--virtual-log", str(self.virtual),
                "--private-baseline", str(self.baseline)]
        if mode == "delta" and output:
            args.extend(("--output", str(self.output)))
        with contextlib.redirect_stdout(io.StringIO()):
            tool.main(args)

    def report(self):
        self.invoke("delta")
        return json.loads(self.output.read_text(encoding="utf-8"))

    def test_01_empty_existing_logs_no_false_acceptance(self):
        self.vida.write_bytes(b"prior original VIDA session\n")
        self.virtual.write_bytes(line("PassThruOpen -> device 1").encode())
        self.invoke("baseline")
        item = self.report()
        self.assertEqual(item["appended_bytes"], {"original_vida": 0,
                                                   "virtual_j2534": 0})
        self.assertEqual(item["virtual_marker_counts"]["open_success"], 0)
        self.assertFalse(item["original_vida_dll_loaded_verified"])
        self.assertFalse(item["vin_accepted_verified"])

    def test_02_new_lifecycle_metadata_and_vin_literals_not_identity(self):
        self.vida.write_text("old\n", encoding="utf-8")
        self.virtual.write_text("old\n", encoding="utf-8")
        self.invoke("baseline")
        with self.vida.open("a", encoding="utf-8") as output:
            output.write("PassThruOpen GetScript ReadVin --->\n")
        with self.virtual.open("a", encoding="utf-8") as output:
            output.write(line("VirtualCar DLL initialized (v0.3.6.6 extended configuration DID)"))
            output.write(line("PassThruOpen -> device 1"))
            output.write(line("J2534 Connect result protocol/flags/baud/status (BE) "
                              + metadata(0x8004, 0, 125000, 0)))
            output.write(line("TX (app request) PRIVATE_VIN_DATA"))
            output.write(line("PassThruReadMsgs -> delivered PRIVATE_CAN_PAYLOAD"))
            output.write(line("VIDA B3A6 KLINE exact original write LOCAL ACK ONLY "
                              "(NO BUS/ECU TX/RX)"))
        item = self.report()
        self.assertEqual(item["vida_literal_counts"]["read_vin_literal"], 1)
        self.assertEqual(item["virtual_marker_counts"]["open_success"], 1)
        self.assertEqual(item["virtual_marker_counts"]["rx_delivered_logged"], 1)
        self.assertEqual(item["virtual_marker_counts"]["kline_local_ack"], 1)
        self.assertEqual(item["connect_modes"]["attempts"], 1)
        self.assertEqual(item["connect_modes"]["statuses"], {"ok": 1})
        self.assertFalse(item["physical_ecu_rx_verified"])
        self.assertFalse(item["vin_accepted_verified"])

    def test_03_mutated_historical_prefix_rejected(self):
        self.vida.write_bytes(b"previous content\n")
        self.invoke("baseline")
        self.vida.write_bytes(b"PREVIOUS content\n")
        with self.assertRaisesRegex(ValueError, "prefix changed"):
            self.invoke("delta")

    def test_04_truncated_and_swapped_sources_fail_closed(self):
        self.vida.write_bytes(b"history\n")
        self.virtual.write_bytes(b"old\n")
        self.invoke("baseline")
        self.vida.write_bytes(b"x")
        with self.assertRaises(ValueError):
            self.invoke("delta")
        private = json.loads(self.baseline.read_text())
        with self.assertRaisesRegex(ValueError, "source path changed"):
            tool._append(Path(self.tmp.name) / "different.log",
                         private["virtual_j2534"])

    def test_05_partial_edge_records_ignored(self):
        self.vida.write_bytes(b"unfinished")
        self.virtual.write_bytes(b"legacy\n")
        self.invoke("baseline")
        with self.vida.open("ab") as output:
            output.write(b"ReadVin orphan\nGetScript\nReadVin incomplete")
        with self.virtual.open("ab") as output:
            output.write(line("PassThruOpen -> device 1").encode())
            output.write((PID + "PassThruClose").encode())
        report = self.report()
        self.assertEqual(report["vida_literal_counts"]["get_script"], 1)
        self.assertEqual(report["vida_literal_counts"]["read_vin_literal"], 0)
        self.assertEqual(report["virtual_marker_counts"]["close"], 0)
        self.assertGreaterEqual(report["incomplete_edge_fragments_ignored"], 2)

    def test_06_missing_log_at_baseline_then_created(self):
        self.invoke("baseline")
        self.vida.write_text("GetScript\n", encoding="utf-8")
        self.virtual.write_text(line("PassThruOpen -> device 1"), encoding="utf-8")
        report = self.report()
        self.assertEqual(report["virtual_marker_counts"]["open_success"], 1)
        self.assertEqual(report["vida_literal_counts"]["get_script"], 1)

    def test_07_no_private_output_and_exclusive_files(self):
        secret = "PRIVATE_VIN_ABC0123456789"
        self.vida.write_text(secret + " ReadVin\n", encoding="utf-8")
        self.virtual.write_text(line("TX (app request) " + secret), encoding="utf-8")
        self.invoke("baseline")
        with self.virtual.open("a", encoding="utf-8") as output:
            output.write(line("PassThruOpen -> device 1 " + secret))
        item = self.report()
        encoded = json.dumps(item, ensure_ascii=False)
        for bad in (secret, str(self.vida), str(self.virtual),
                    "1234ABCD", "PRIVATE_CAN_PAYLOAD"):
            self.assertNotIn(bad, encoded)
        with self.assertRaises(FileExistsError):
            self.invoke("baseline")
        with self.assertRaises(FileExistsError):
            self.invoke("delta")

    def test_08_untrusted_log_lines_and_host_classes_not_attribution(self):
        self.invoke("baseline")
        with self.virtual.open("a", encoding="utf-8") as output:
            output.write("PassThruOpen -> device 1\n")  # no PID prefix
            output.write(line("PassThruOpen -> device 1",
                              host="[PID=11111111 untrusted.exe] "))
            output.write(line("J2534 Connect result protocol/flags/baud/status (BE) "
                              "01 GG"))
        item = self.report()
        self.assertEqual(item["virtual_marker_counts"]["open_success"], 1)
        self.assertIn("other", item["virtual_host_class_line_counts"])
        self.assertEqual(item["connect_modes"]["attempts"], 0)
        self.assertGreaterEqual(item["connect_modes"]["invalid_events"], 1)
        self.assertFalse(item["original_vida_selected_driver_verified"])

    def test_cem_append_evidence_separates_channels_and_excludes_baseline(self):
        def tx(channel, baud, data):
            return (line("TX context channel/protocol/flags/baud/time-us (BE) "
                         + metadata(channel, 5, 0x100, baud, 10000))
                    + line("TX (app request) 00 0F FF FE " + data))

        def rx(channel, baud, response, data):
            return (line("RX context channel/protocol/status/baud/time-us (BE) "
                         + metadata(channel, 5, 0x100, baud, 12000))
                    + line("PassThruReadMsgs -> delivered " + response + " " + data))

        self.virtual.write_text(tx(1, 125000, "CB 40 B9 FB 00 00 00 00"), encoding="utf-8")
        self.invoke("baseline")
        with self.virtual.open("a", encoding="utf-8") as stream:
            stream.write(tx(1, 125000, "CB 40 AE 1B 00 00 00 00"))
            stream.write(tx(2, 500000, "CB 50 B9 F0 00 00 00 00"))
            stream.write(line("P2 D2 read command: no validated response fixture"))
            stream.write(rx(1, 125000, "00 80 00 03", "CB 40 EE 1B 00 00 00 00"))
            stream.write(tx(1, 125000, "CB 40 B9 F5 00 00 00 00"))
            stream.write(rx(1, 125000, "00 80 00 03", "CB 40 F9 F5 00 00 00 00"))
            stream.write(tx(1, 125000, "CB 40 B9 F8 00 00 00 00"))
            stream.write(rx(1, 125000, "00 80 00 03", "CA 40 F9 F8 00 00 00 00"))
            stream.write(tx(2, 500000, "CB 50 B9 F8 00 00 00 00"))
        evidence = self.report()["cem_transport"]
        routes = {(r["target"], r["service"], r["baud_bps"]): r["statuses"] for r in evidence["routes"]}
        self.assertEqual(routes, {
            ("0x40", "AE1B", 125000): {"delivered": 1},
            ("0x40", "B9F5", 125000): {"delivered": 1},
            ("0x40", "B9F8", 125000): {"partial_rx": 1},
            ("0x50", "B9F0", 500000): {"no_fixture": 1},
            ("0x50", "B9F8", 500000): {"unverified": 1},
        })
        serialized = json.dumps(evidence)
        for private in ("1234ABCD", "CB 40 F9 F5", "channel", "iexplore"):
            self.assertNotIn(private, serialized)
        self.assertFalse(evidence["client_acceptance_verified"])


if __name__ == "__main__":
    unittest.main()
