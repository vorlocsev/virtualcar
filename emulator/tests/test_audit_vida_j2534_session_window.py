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


if __name__ == "__main__":
    unittest.main()
