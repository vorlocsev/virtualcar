"""Eight synthetic checks for VDASH UI/J2534 evidence boundary correlation."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

p = Path(__file__).resolve().parents[1] / "tools" / "audit_vdash_session_boundary.py"
spec = importlib.util.spec_from_file_location("vdash_boundary", p)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def ui(**kw):
    record = dict(format=tool.UI_FORMAT, client_build="vdash_2_0",
                  one_client_run_attested=True, same_run_sources_attested=True,
                  predetect_vehicle_shown=True, connect_pressed=True,
                  connect_ui_finished=True, ecu_list="empty")
    record.update(kw)
    return record


def connect(ok=1, fail=0):
    return dict(format=tool.CONNECT_FORMAT, contains_payload_data=False,
                connect=dict(attempts=ok+fail, invalid_events=0,
                             statuses=dict(ok=ok, invalid_protocol=fail)))


def tx(route, service, status="delivered", session=1):
    return dict(session=session, route=route, service=service, status=status)


def discovery(*rows, errors=None):
    vins = [e for e in rows if e["route"] == "OBD" and e["service"] == "0902"]
    return dict(format=tool.DISC_FORMAT, contains_payload_data=False, read_only=True,
                replay_approved=False, transactions=list(rows), parse_errors=errors or {},
                obd_observation=dict(vin_requests=len(vins),
                                     vin_delivered=sum(e["status"] == "delivered" for e in vins),
                                     recognized_d2_p3_probes=sum(
                                         e["route"] in ("D2", "P3") for e in rows)))


class VdashBoundaryTests(unittest.TestCase):
    def test_01_obd_vin_but_no_ecus_no_oem_probe(self):
        x = tool.audit(ui(), connect(), discovery(
            tx("OBD", "0902"), tx("OBD", "3E80", "unverified")))
        self.assertEqual(x["research_focus"], "vin_delivered_no_oem_request_observed")
        self.assertFalse(x["ecu_identity_verified"])
        self.assertFalse(x["initialize_units_execution_verified"])
        self.assertEqual(x["vin_transport_deliveries"], 1)
        # Realistic integration of the existing *synthetic* VDASH 2.0 log:
        # the two upstream tools must be compatible with this correlator.
        root = Path(__file__).resolve().parents[1]
        def upstream(name):
            path = root / "tools" / name
            spec = importlib.util.spec_from_file_location(name[:-3], path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        raw = (root / "tests" / "fixtures" / "vdash20_obd_synthetic.txt"
               ).read_text(encoding="utf-8").splitlines()
        con_report = upstream("audit_j2534_connect.py").audit(raw)
        disc_report = upstream("audit_j2534_discovery.py").audit(raw, include_obd=True)
        integrated = tool.audit(ui(), con_report, disc_report)
        self.assertEqual(integrated["research_focus"],
                         "vin_delivered_no_oem_request_observed")
        self.assertEqual(integrated["j2534_connect_ok"], 1)
        self.assertFalse(integrated["same_run_independently_verified"])

    def test_02_targeted_d2_delivered_not_vdash_parser_proof(self):
        x = tool.audit(ui(), connect(), discovery(
            tx("OBD", "0902"), tx("D2", "B9FB")))
        self.assertEqual(x["research_focus"], "inspect_command_result_and_ui_projection")
        self.assertEqual(x["recognized_oem_deliveries"], 1)
        self.assertFalse(x["vdash_command_completion_verified"])

    def test_03_adapter_and_connect_ui_boundaries(self):
        self.assertEqual(tool.audit(ui(), connect(0, 1), discovery())["research_focus"],
                         "inspect_j2534_connect_failure")
        self.assertEqual(tool.audit(ui(), connect(0, 0), discovery())["research_focus"],
                         "inspect_driver_or_missing_connect_log")
        self.assertEqual(tool.audit(ui(connect_pressed=False), connect(), discovery())["research_focus"],
                         "explicit_connect_not_observed")
        self.assertEqual(tool.audit(ui(connect_pressed=None), connect(), discovery())["research_focus"],
                         "unknown_connect_ui_action")

    def test_04_attestation_and_multisession_prevent_join(self):
        for a in (ui(one_client_run_attested=False),
                  ui(same_run_sources_attested=False)):
            x = tool.audit(a, connect(), discovery(tx("OBD", "0902")))
            self.assertEqual(x["research_focus"], "no_cross_source_conclusion")
        d = discovery(tx("OBD", "0902", session=1),
                      tx("D2", "B9FB", session=2))
        self.assertEqual(tool.audit(ui(), connect(), d)["research_focus"],
                         "no_cross_source_conclusion")

    def test_05_partial_and_parse_errors_not_accepted(self):
        d = discovery(tx("D2", "B9FB", "partial_rx"))
        x = tool.audit(ui(), connect(), d)
        self.assertEqual(x["recognized_oem_deliveries"], 0)
        self.assertEqual(x["research_focus"], "more_client_transport_evidence_needed")
        d = discovery(tx("D2", "B9FB"), errors={"invalid_lines": 1})
        self.assertEqual(tool.audit(ui(), connect(), d)["research_focus"],
                         "no_cross_source_conclusion")

    def test_06_nonempty_ecu_list_not_authentic_xc90(self):
        x = tool.audit(ui(ecu_list="nonempty", client_build="vdash_2_5_115_79"),
                       connect(), discovery())
        self.assertEqual(x["research_focus"], "ui_list_observed_identity_unverified")
        self.assertFalse(x["xc90_v8_my2009_verified"])

    def test_07_malformed_or_nonreadonly_input_rejected(self):
        bad = [
            (ui(client_build="customer-vin"), connect(), discovery()),
            (ui(connect_pressed="yes"), connect(), discovery()),
            (ui(one_client_run_attested=1), connect(), discovery()),
            (ui(), {**connect(), "contains_payload_data": True}, discovery()),
            (ui(), connect(), {**discovery(), "replay_approved": True}),
            (ui(), connect(), {**discovery(), "obd_observation": {
                "vin_requests": 0, "vin_delivered": 1, "recognized_d2_p3_probes": 0}}),
            (ui(), connect(), discovery(tx("OBD", "0902", session=0))),
        ]
        for a, b, c in bad:
            with self.subTest(ui=a), self.assertRaises(ValueError):
                tool.audit(a, b, c)

    def test_08_allowlisted_output_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            names = [Path(td)/name for name in ("ui.json", "connect.json",
                                               "discovery.json", "result.json")]
            private = "PRIVATE_VIN_AND_SESSION_KEY"
            sources = [ui(), connect(), discovery(tx("OBD", "0902"))]
            for value, path in zip(sources, names):
                value["unknown_private_field"] = private
                path.write_text(json.dumps(value), encoding="utf-8")
            argv = ["--ui", str(names[0]), "--connect", str(names[1]),
                    "--discovery", str(names[2]), "--output", str(names[3])]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main(argv), 0)
            out = names[3].read_text(encoding="utf-8")
            self.assertNotIn(private, out)
            self.assertNotIn(td, out)
            self.assertFalse(json.loads(out)["same_run_independently_verified"])
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                self.assertEqual(tool.main(argv), 2)
            self.assertNotIn(td, errors.getvalue())

    def test_09_invalid_connect_metadata_blocks_classification(self):
        conn = connect()
        conn["connect"]["invalid_events"] = 1
        r = tool.audit(ui(), conn, discovery(tx("OBD", "0902")))
        self.assertFalse(r["cross_source_correlatable_by_attestation_only"])
        self.assertEqual(r["research_focus"], "no_cross_source_conclusion")
        self.assertEqual(r["j2534_invalid_connect_records"], 1)

    def test_10_ui_connect_incomplete_not_ecu_rejection(self):
        r = tool.audit(ui(connect_ui_finished=False), connect(),
                       discovery(tx("OBD", "0902"), tx("D2", "B9FB")))
        self.assertEqual(r["research_focus"], "ui_connect_not_complete")
        self.assertEqual(r["recognized_oem_deliveries"], 1)
        self.assertFalse(r["vdash_command_completion_verified"])

    def test_11_unknown_ui_completion_not_accepted(self):
        r = tool.audit(ui(connect_ui_finished=None), connect(),
                       discovery(tx("OBD", "0902"), tx("D2", "B9FB")))
        self.assertEqual(r["research_focus"], "ui_connect_completion_unknown")
        self.assertIsNone(r["ui_connect_finished_reported"])

    def test_12_completed_ui_connect_keeps_bounded_hypothesis(self):
        r = tool.audit(ui(connect_ui_finished=True), connect(),
                       discovery(tx("OBD", "0902"), tx("D2", "B9FB")))
        self.assertEqual(r["research_focus"], "inspect_command_result_and_ui_projection")
        self.assertFalse(r["initialize_units_execution_verified"])

    def test_13_partial_or_negative_oem_not_delivery(self):
        for status in ("partial_rx", "negative_response", "unverified"):
            with self.subTest(status=status):
                r = tool.audit(ui(), connect(), discovery(tx("D2", "B9FB", status)))
                self.assertEqual(r["recognized_oem_requests"], 1)
                self.assertEqual(r["recognized_oem_deliveries"], 0)
                self.assertEqual(r["research_focus"], "more_client_transport_evidence_needed")

    def test_14_invalid_connect_counter_type_rejected(self):
        for value in (True, "1", -1, 20001):
            conn = connect()
            conn["connect"]["invalid_events"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                tool.audit(ui(), conn, discovery())

    def test_15_missing_invalid_connect_counter_rejected(self):
        conn = connect()
        del conn["connect"]["invalid_events"]
        with self.assertRaises(ValueError):
            tool.audit(ui(), conn, discovery())

    def test_16_private_extensions_still_redacted(self):
        a, b, c = ui(), connect(), discovery(tx("OBD", "0902"))
        for item in (a, b, c):
            item["unknown_private"] = "CUSTOMER_PRIVATE_VIN"
        r = tool.audit(a, b, c)
        self.assertNotIn("CUSTOMER_PRIVATE_VIN", json.dumps(r))
        self.assertEqual(r["j2534_invalid_connect_records"], 0)
        self.assertFalse(r["same_run_independently_verified"])


if __name__ == "__main__":
    unittest.main()
