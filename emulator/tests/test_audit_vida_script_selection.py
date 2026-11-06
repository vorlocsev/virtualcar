"""Eight synthetic VIDA trace evidence tests; no authentic vehicle identifiers."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_vida_script_selection import audit_lines, audit_file, main


def event(t, component, thread, payload):
    return f"16:51:{t} [{component:<14}][{thread:03}][Event] {payload}\n"


def get(t="31,544", thread=1, script_type="VehCommSpecification"):
    return event(t, "ScriptProvider", thread,
                 "Database: DiagSwdlRepository, SP: GetScript, Type: '" + script_type
                 + "' ScriptId: '' Language: 'en-US' EcuType: '123' Profile: 'PRIVATE' ")


def fetched(t="31,576", thread=1, name="INTERNAL-TEST-ID"):
    return event(t, "ScriptProvider", thread, "Fetched script: '"+name+"' title: 'SYNTHETIC'")


def running(t="31,591", thread=1, name="INTERNAL-TEST-ID"):
    return event(t, "Script", thread, "Running script: '"+name+"' title: 'SYNTHETIC'")


class VidaSelectionTraceTests(unittest.TestCase):
    def test_01_ordered_triplet_is_not_identity_verification(self):
        r = audit_lines([get(), fetched(), running()])
        self.assertEqual(r["events"]["matched_get_fetch_run_triplets"], 1)
        self.assertEqual(r["events"]["matched_veh_comm_specification_triplets"], 1)
        self.assertFalse(r["script_selected_for_identify_vehicle_verified"])

    def test_02_other_getscript_type_not_cem_identity(self):
        r = audit_lines([get(script_type="SpecialUnverifiedType"), fetched(), running()])
        self.assertEqual(r["events"]["requests_other_type"], 1)
        self.assertEqual(r["events"]["matched_veh_comm_specification_triplets"], 0)
        self.assertFalse(r["b9fb_to_vin_mapping_verified"])

    def test_03_wrong_script_id_fails_correlation(self):
        r = audit_lines([get(), fetched(name="SCRIPT-A"), running(name="SCRIPT-B")])
        self.assertEqual(r["events"]["different_script_running_events"], 1)
        self.assertEqual(r["events"]["matched_get_fetch_run_triplets"], 0)

    def test_04_cross_thread_cannot_be_joined(self):
        r = audit_lines([get(thread=1), fetched(thread=2), running(thread=2)])
        self.assertEqual(r["events"]["matched_get_fetch_run_triplets"], 0)
        self.assertEqual(r["events"]["orphan_fetched_script_events"], 1)
        self.assertEqual(r["events"]["unmatched_running_script_events"], 1)

    def test_05_superseding_lookup_and_deadline(self):
        r = audit_lines([get(), get(t="31,600"), fetched(t="31,700"), running(t="31,800")])
        self.assertEqual(r["events"]["superseded_incomplete_get_script_requests"], 1)
        self.assertEqual(r["events"]["matched_get_fetch_run_triplets"], 1)
        r = audit_lines([get(), fetched(t="59,900"), running(t="59,950")])
        self.assertEqual(r["events"]["matched_get_fetch_run_triplets"], 1)
        r = audit_lines([get(t="00,000"), fetched(t="31,100"), running(t="31,101")])
        self.assertEqual(r["events"]["matched_get_fetch_run_triplets"], 0)

    def test_06_error_and_identity_method_mention_are_not_selection(self):
        r = audit_lines([get(), "Vcc.ScriptMissingException: Lookup failed\n",
                         "RunScriptService.GetVehCommSpecification threw an exception\n",
                         " at RunScriptService.RunIdentifyVehicleScript\n"])
        self.assertEqual(r["events"]["script_missing_exception_mentions"], 1)
        self.assertEqual(r["events"]["get_vehcomm_specification_error_mentions"], 1)
        self.assertEqual(r["events"]["run_identify_vehicle_method_mentions"], 1)
        self.assertFalse(r["script_selected_for_identify_vehicle_verified"])

    def test_07_source_bounds_malformed_and_encoding(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "PRIVATE.log")
            p.write_bytes(b"\xff\xfe")
            with self.assertRaises(UnicodeError): audit_file(p)
            p.write_text("A" * 8200, encoding="utf8")
            with self.assertRaises(ValueError): audit_file(p)
            with self.assertRaises(ValueError): audit_lines([get(t="61,544")])

    def test_08_cli_privacy_exclusive_and_no_content_export(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d, "PRIVATE-VIN-DO-NOT-SHARE.log")
            src.write_text(get() + fetched(name="YV1PRIVATE_S123") + running(name="YV1PRIVATE_S123"), encoding="utf8")
            out = Path(d, "SAFE.json")
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(src), "--output", str(out)])
            data = out.read_text()
            for secret in ("YV1PRIVATE", "PRIVATE-VIN", "PRIVATE'", str(src), "INTERNAL-TEST-ID"):
                self.assertNotIn(secret, data)
            self.assertEqual(json.loads(data)["events"]["matched_get_fetch_run_triplets"], 1)
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main([str(src), "--output", str(out)])


if __name__ == "__main__":
    unittest.main()
