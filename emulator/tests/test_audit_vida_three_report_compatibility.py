"""B3A335 synthetic three-report compatibility; original VIDA never inspected."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_connection_config_candidate as xmltool
import audit_vida_procmon_config_read as procmon
import audit_vida_three_report_compatibility as tool
sys.path.pop(0)

HEADER = "Time of Day,Process Name,PID,Operation,Path,Result\n"
PATH = r"C:\Private\YV1_SYNTHETIC_VIN\diagnostic.config.xml"


def make_xml(mode="J2534DiagnosticConnection", client="false"):
    data = (f'<root><add key="UseClientSettings" value="{client}"/>'
            f'<add key="DiagnosticConnection" value="{mode}"/></root>').encode()
    return xmltool.classify_bytes(data)


def event(pid, operation, path=PATH, process="iexplore.exe"):
    return f'10:00:00,{process},{pid},{operation},{path},SUCCESS\n'


def make_proc(*events, process="iexplore.exe"):
    return procmon.analyze_text(HEADER + "".join(events), process)


def make_module(name="iexplore", state="registered_library_loaded_in_name_matched_client",
                comparison="exact_bytes_at_snapshot", pe="x86_pe32_header"):
    loaded = state == "registered_library_loaded_in_name_matched_client"
    return {
        "schema_version": "virtualcar-vida-process-binding-operator-v1",
        "scope": "operator_requested_current_host_name_match_only",
        "selected_process_name_category": name,
        "registered_virtual_module_observation": state,
        "installed_vs_reference_dll": comparison,
        "reference_dll_pe32": pe,
        "registered_dll_module_path_seen_in_name_matched_process": loaded,
        "selected_process_is_authenticated_original_vida": False,
        "loaded_binary_memory_matches_disk_verified": False,
        "active_vida_diagnostic_config_loaded_verified": False,
        "effective_diagnostic_connection_mode_verified": False,
        "original_vida_script_selection_verified": False,
        "original_vida_j2534_tx_rx_verified": False,
        "original_vida_vin_accepted_verified": False,
        "ecu_identity_accepted_verified": False,
        "client_started_by_audit": False,
        "physical_adapter_examined": False,
        "next_safe_gate": "independently_observe_active_vida_config_and_readvin",
    }


def read_pair():
    return make_proc(event(12, "CreateFile"), event(12, "ReadFile"))


class VidaThreeReportCompatibilityTests(unittest.TestCase):
    def test_01_three_compatible_candidates_never_become_one_session(self):
        result = tool.compare(make_xml(), make_module(), read_pair())
        self.assertEqual(result["candidate_observation_compatibility"],
                         "j2534_xml_candidate_and_virtual_module_compatible_only")
        self.assertTrue(result["process_name_categories_match"])
        self.assertTrue(result["procmon_successful_candidate_read_observed"])
        self.assertTrue(result["registered_vs_reference_disk_bytes_match"])
        for key in (
            "same_host_and_capture_window_verified",
            "same_process_identity_across_reports_verified",
            "same_config_file_path_between_xml_and_procmon_verified",
            "authenticated_original_vida_executable_verified",
            "effective_original_vida_diagnostic_connection_mode_verified",
            "original_vida_getscript_readvin_executed_verified",
            "original_vida_vin_accepted_verified",
            "ecu_identity_accepted_verified",
        ):
            self.assertIs(result[key], False)
        self.assertNotIn("YV1_SYNTHETIC_VIN", json.dumps(result))

    def test_02_nocomm_candidate_and_loaded_module_not_a_contradiction(self):
        r = tool.compare(make_xml("NoCommConnection"), make_module(), read_pair())
        self.assertEqual(r["candidate_observation_compatibility"],
                         "no_comm_xml_candidate_coexists_with_virtual_module")
        self.assertEqual(r["xml_mode_candidate"], "NoCommConnection")
        self.assertFalse(r["effective_original_vida_diagnostic_connection_mode_verified"])

    def test_03_different_name_categories_do_not_link_sessions(self):
        p = make_proc(event(12, "CreateFile", process="java.exe"),
                      event(12, "ReadFile", process="java.exe"),
                      process="java.exe")
        r = tool.compare(make_xml(), make_module(), p)
        self.assertFalse(r["process_name_categories_match"])
        self.assertEqual(r["candidate_observation_compatibility"],
                         "candidate_process_name_categories_differ")
        # Exact B3A333 process label, not the lowercased Procmon form.
        r = tool.compare(make_xml(), make_module(name="VidaMonitor"),
                         make_proc(event(1, "CreateFile", process="vidamonitor.exe"),
                                   event(1, "ReadFile", process="vidamonitor.exe"),
                                   process="vidamonitor.exe"))
        self.assertTrue(r["process_name_categories_match"])
        self.assertFalse(r["same_process_identity_across_reports_verified"])

    def test_04_ambiguous_procmon_or_no_read_never_raises_evidence(self):
        none = make_proc(event(1, "CreateFile"))
        r = tool.compare(make_xml(), make_module(), none)
        self.assertEqual(r["candidate_observation_compatibility"],
                         "no_successful_candidate_file_read_in_export")
        different = r"C:\Other\diagnostic.config.xml"
        ambiguous = make_proc(
            event(1, "CreateFile"), event(1, "ReadFile"),
            event(1, "CreateFile", path=different),
            event(1, "ReadFile", path=different))
        r = tool.compare(make_xml(), make_module(), ambiguous)
        self.assertEqual(r["candidate_observation_compatibility"],
                         "candidate_file_or_process_read_ambiguous")

    def test_05_module_missing_wrong_pe_or_mismatch(self):
        missing = make_module(
            state="registered_library_not_in_enumerated_modules")
        r = tool.compare(make_xml(), missing, read_pair())
        self.assertEqual(r["candidate_observation_compatibility"],
                         "registered_virtual_module_not_observed_in_candidate")
        for kwargs in ({"comparison": "different_bytes_at_snapshot"},
                       {"pe": "other_pe"},
                       {"comparison": "comparison_unverifiable"}):
            with self.subTest(case=kwargs):
                r = tool.compare(make_xml(), make_module(**kwargs), read_pair())
                self.assertEqual(r["candidate_observation_compatibility"],
                                 "virtual_module_reference_not_equivalent_and_pe32_checked")
                self.assertFalse(r["original_vida_j2534_tx_rx_verified"])

    def test_06_reject_unsupported_positive_attestation_and_tampered_counts(self):
        for role, field in (
            ("xml", "original_vida_process_loaded_this_file_verified"),
            ("module", "active_vida_diagnostic_config_loaded_verified"),
            ("procmon", "paired_with_live_module_snapshot_verified"),
        ):
            with self.subTest(role=role):
                a, b, c = make_xml(), make_module(), read_pair()
                reports = {"xml": a, "module": b, "procmon": c}
                reports[role][field] = True
                with self.assertRaises(tool.ReportError):
                    tool.compare(a, b, c)
        corrupted = read_pair()
        corrupted["candidate_readfile_after_prior_same_pid_path_open_events"] = 2
        with self.assertRaises(tool.ReportError):
            tool.compare(make_xml(), make_module(), corrupted)
        corrupted = make_module()
        corrupted["registered_dll_module_path_seen_in_name_matched_process"] = False
        with self.assertRaises(tool.ReportError):
            tool.compare(make_xml(), corrupted, read_pair())

    def test_07_reject_invalid_categories_and_schema(self):
        for role, field, value in (
            ("xml", "mode_candidate", "ORIGINAL_PRIVATE_VIN"),
            ("xml", "no_comm_candidate_if_loaded", True),
            ("module", "selected_process_name_category", "SectorV"),
            ("module", "registered_virtual_module_observation", "untrusted"),
            ("procmon", "selected_process_name_category", "SectorV.exe"),
            ("procmon", "candidate_readfile_success_events", True),
            ("procmon", "file_io_category", "definitely_original_vida"),
        ):
            with self.subTest(role=role, field=field):
                a, b, c = make_xml(), make_module(), read_pair()
                reports = {"xml": a, "module": b, "procmon": c}
                reports[role][field] = value
                with self.assertRaises(tool.ReportError):
                    tool.compare(a, b, c)
        bad = read_pair()
        bad["schema_version"] = "unknown"
        with self.assertRaises(tool.ReportError):
            tool.compare(make_xml(), make_module(), bad)

    def test_08_private_cli_reports_duplicate_json_and_symlink_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            reports = {
                "xml": make_xml(), "module": make_module(), "procmon": read_pair()
            }
            for kind, value in reports.items():
                (folder / (kind + ".json")).write_text(json.dumps(value))
            args = [
                "--xml-report", str(folder / "xml.json"),
                "--module-report", str(folder / "module.json"),
                "--procmon-report", str(folder / "procmon.json"),
            ]
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(tool.main(args), 0)
            serialized = out.getvalue()
            self.assertNotIn(str(folder), serialized)
            self.assertNotIn("YV1_SYNTHETIC_VIN", serialized)
            self.assertIn('"same_host_and_capture_window_verified": false',
                          serialized)
            duplicated = folder / "xml.json"
            duplicated.write_text('{"schema_version":"a","schema_version":"b"}')
            with self.assertRaises(tool.ReportError):
                tool.read_report(duplicated)
            duplicated.write_bytes(b"X" * (tool.MAX_REPORT_BYTES + 1))
            with contextlib.redirect_stderr(err):
                self.assertEqual(tool.main(args), 2)
            self.assertNotIn(str(duplicated), err.getvalue())
            link = folder / "alias.json"
            try:
                link.symlink_to(folder / "module.json")
            except (OSError, NotImplementedError):
                pass
            else:
                with self.assertRaises(tool.ReportError):
                    tool.read_report(link)


if __name__ == "__main__":
    unittest.main()
