"""Eight offline gates for a single PRIVATE diagnostic-client capture bundle.

No SectorV/VDASH binary, VIN, key, hardware ECU, or personal data is included.
"""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import prepare_p2_client_run as tool
from test_audit_d2_followup_window import D2FB, marker, response, tx, words
from test_native_b9f0_response import F0, f0_response
from test_native_b9f0_first_p3_response import p3_rx
from test_native_p2_p3_single_run_gate import p3_tx

P3_POS = bytes.fromhex("62 F1 14 41")
GOOD_CONNECT = [
    marker("PassThruOpen -> device 1"),
    marker("J2534 Connect bound channel/protocol/flags/baud (BE)",
           words(1, 5, 0x800, 500000)),
    marker("J2534 Connect result protocol/flags/baud/status (BE)",
           words(5, 0x800, 500000, 0)),
]


def session(*, include_b9fb=True, include_b9f0=True, include_p3=True,
            native_label="SectorV.exe"):
    lines = GOOD_CONNECT[:]
    if include_b9fb:
        lines += tx(D2FB, at=1_000_000) + response(first=1_020_000)
    if include_b9f0:
        lines += tx(F0, at=1_132_000) + f0_response(start=1_142_000)
    if include_p3:
        lines += p3_tx(channel=2, protocol=6, at=1_202_000)
        lines += p3_rx(P3_POS, channel=2, protocol=6, at=1_222_000)
    lines += [marker("PassThruClose")]
    # The native logger records the basename of its host executable.
    # All other data in these transport fixtures remain synthetic.
    return "\n".join(lines).replace("PRIVATE_CLIENT", native_label)


def ui(**changes):
    value = {
        "format": tool.UI_FORMAT, "client": "sectorv",
        "virtual_adapter_selected": True, "scan_finished": True,
        "vin_display": "unknown", "ecu_list": "unknown",
        "same_run_operator_attested": False,
    }
    value.update(changes)
    return value


class ClientCapturePreparationTests(unittest.TestCase):
    def test_01_full_synthetic_chain_is_transport_only(self):
        reports = tool.prepare(session())
        self.assertEqual(len(reports), 5)
        summary = reports["client-boundary.json"]
        self.assertEqual(summary["diagnostic_focus"],
                         "native_transport_positive_client_ui_result_unknown")
        self.assertEqual(summary["b9fb_positive_transport_count"], 1)
        self.assertEqual(summary["b9f0_positive_transport_count"], 1)
        self.assertEqual(summary["first_p3_positive_transport_count"], 1)
        self.assertTrue(summary["native_p2_single_closed_epoch"])
        self.assertTrue(
            summary["native_device_lifecycle"]["single_closed_device_cycle_verified"])
        self.assertFalse(summary["same_run_independently_verified"])
        self.assertFalse(summary["client_ecu_inventory_verified"])

    def test_02_reported_nonempty_ui_is_not_independent_ecu_proof(self):
        reports = tool.prepare(session(), ui(
            ecu_list="nonempty", vin_display="visible",
            same_run_operator_attested=True))
        note = reports["client-boundary.json"]
        self.assertEqual(note["diagnostic_focus"],
                         "operator_reports_nonempty_ecu_list_identity_unverified")
        self.assertEqual(note["reported_client"], "sectorv")
        self.assertTrue(note["same_run_operator_attested"])
        self.assertFalse(note["same_run_independently_verified"])
        self.assertFalse(note["xc90_v8_my2009_verified"])

    def test_03_reported_empty_ui_suggests_check_client_projection(self):
        note = tool.prepare(session(native_label="VDASH.exe"), ui(
            client="vdash_2_0", ecu_list="empty",
            same_run_operator_attested=True))["client-boundary.json"]
        self.assertEqual(note["diagnostic_focus"],
                         "transport_positive_but_operator_reports_empty_ecu_list")
        self.assertFalse(note["client_ecu_inventory_verified"])
        self.assertEqual(note["ui_ecu_list_reported"], "empty")

    def test_04_no_b9fb_yet_retains_safe_connection_diagnostics(self):
        reports = tool.prepare(session(
            include_b9fb=False, include_b9f0=False, include_p3=False))
        self.assertEqual(set(reports), set(tool.OUTPUTS))
        note = reports["client-boundary.json"]
        self.assertEqual(note["diagnostic_focus"],
                         "no_native_b9fb_request_observed")
        self.assertEqual(note["native_p2_report_status"],
                         "native_p2_evidence_not_comparable")
        self.assertEqual(note["connect_succeeded"], 1)

    def test_05_no_connect_and_invalid_connect_do_not_infer_vehicle_scan(self):
        without_connect = "\n".join(
            line for line in session().splitlines()
            if "J2534 Connect result protocol/flags/baud/status (BE)" not in line)
        # No valid connect marker; a complete synthetic route is NOT proof
        # that a real client made a successful local Connect call.
        note = tool.prepare(without_connect)["client-boundary.json"]
        self.assertEqual(note["diagnostic_focus"],
                         "no_virtual_adapter_connect_attempt_observed")
        wrong = session().replace(
            "J2534 Connect result protocol/flags/baud/status (BE)",
            "J2534 Connect result protocol/flags/baud/status (BE) BAD")
        note = tool.prepare(wrong)["client-boundary.json"]
        self.assertEqual(note["diagnostic_focus"],
                         "invalid_native_source_or_connect_metadata")

    def test_06_incomplete_b9fb_or_absent_b9f0_has_distinct_focus(self):
        native = tool.prepare(session(
            include_b9fb=True, include_b9f0=False, include_p3=False))
        self.assertEqual(native["client-boundary.json"]["diagnostic_focus"],
                         "no_b9f0_request_after_b9fb")
        incomplete = "\n".join(
            GOOD_CONNECT + tx(D2FB, at=1_000_000) +
            [marker("PassThruClose")])
        note = tool.prepare(incomplete)["client-boundary.json"]
        self.assertEqual(note["diagnostic_focus"],
                         "b9fb_no_completed_positive_transport")

    def test_07_cross_epoch_log_is_not_one_verified_native_run(self):
        two = session() + "\n" + session()
        note = tool.prepare(two)["client-boundary.json"]
        self.assertEqual(note["diagnostic_focus"],
                         "multiple_native_j2534_device_cycles")
        self.assertFalse(note["native_p2_single_closed_epoch"])
        self.assertFalse(note["same_run_independently_verified"])
        # Observed SectorV pattern: repeated valid Open/Close is not a
        # failure by itself. An absent Connect is the actionable boundary.
        repeated_open = "\n".join(
            (marker("PassThruOpen -> device 1") + "\n" +
             marker("PassThruClose")) for _ in range(13))
        note = tool.prepare(repeated_open)["client-boundary.json"]
        self.assertEqual(note["native_device_lifecycle"]["device_open_count"], 13)
        self.assertEqual(note["diagnostic_focus"],
                         "no_virtual_adapter_connect_attempt_observed")
        # Second observed pattern: Connect did happen, but the client did
        # not transmit any B9FB. Do not mask this with repeated cycles.
        connected = "\n".join(
            "\n".join(GOOD_CONNECT + [marker("PassThruClose")])
            for _ in range(5))
        note = tool.prepare(connected)["client-boundary.json"]
        self.assertEqual(note["diagnostic_focus"],
                         "no_native_b9fb_request_observed")
        self.assertEqual(note["connect_succeeded"], 5)
        self.assertEqual(note["connect_invalid_protocol_attempts"], 0)

    def test_08_cli_exclusive_output_redaction_and_strict_ui_schema(self):
        secret = "CUSTOMER_PRIVATE_ACTUAL_VIN_AND_KEY"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "native-secret.log"
            report_dir = root / "safe-output"
            observation = root / "ui.json"
            source_text = session() + "\n" + secret
            source.write_text(source_text, encoding="utf-8")
            observation.write_text(json.dumps(
                ui(ecu_list="nonempty", same_run_operator_attested=True)),
                encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main([
                    str(source), "--ui", str(observation),
                    "--output-dir", str(report_dir)]), 0)
            content = "\n".join(p.read_text(encoding="utf-8")
                                for p in report_dir.iterdir())
            for forbidden in (secret, "ABCDEF12", "PRIVATE_CLIENT",
                              "F1 14", str(source), "62 F1 14"):
                self.assertNotIn(forbidden, content)
            self.assertEqual(source.read_text(encoding="utf-8"), source_text)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main([
                    str(source), "--ui", str(observation),
                    "--output-dir", str(report_dir)]), 2)
            unsafe = ui()
            unsafe["raw_vin"] = secret
            with self.assertRaisesRegex(ValueError, "invalid_ui_fields"):
                tool.prepare(session(), unsafe)


if __name__ == "__main__":
    unittest.main()
