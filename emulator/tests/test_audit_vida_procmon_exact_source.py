"""B3A336: synthetic exact-path/PID Procmon candidate-source evidence tests."""
import contextlib
import csv
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_connection_config_candidate as xmltool
import audit_vida_procmon_exact_source as tool
sys.path.pop(0)

PRIVATE_PATH = r"C:\Secret\PERSONAL_MARKER\diagnostic.config.xml"
OTHER_PATH = r"C:\Another\private\diagnostic.config.xml"
HEADER = ("Process Name", "PID", "Operation", "Path", "Result")


def config(mode="J2534DiagnosticConnection"):
    raw = (f'<root><add key="DiagnosticConnection" value="{mode}"/>'
           '<add key="UseClientSettings" value="false"/></root>').encode()
    return xmltool.classify_bytes(raw)


def event(pid, operation, path=PRIVATE_PATH, name="iexplore.exe",
          result="SUCCESS"):
    return (name, str(pid), operation, path, result)


def csv_text(*events):
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(events)
    return buf.getvalue()


def analyze(*rows, selected_pid="200", selected_path=PRIVATE_PATH,
            name="iexplore.exe", mode="J2534DiagnosticConnection"):
    return tool.analyze_text(csv_text(*rows), name, selected_pid,
                             selected_path, config(mode))


class VidaExactProcmonSourceTests(unittest.TestCase):
    def test_01_literal_exact_pid_path_read_without_private_export(self):
        result = analyze(event(200, "CreateFile"),
                         event(200, "ReadFile",
                               path=PRIVATE_PATH.lower()),
                         selected_path=PRIVATE_PATH.upper())
        self.assertEqual(result["source_row_match_category"],
                         "selected_pid_exact_path_read_after_open_rows")
        self.assertEqual(result["selected_pid_exact_path_readfile_success_rows"], 1)
        self.assertEqual(result["selected_pid_exact_path_readfile_after_prior_open_rows"], 1)
        self.assertEqual(result["xml_mode_candidate"], "J2534DiagnosticConnection")
        for key in (
            "selected_pid_authentic_original_vida_verified",
            "original_vida_selected_this_config_file_verified",
            "selected_config_file_contents_at_capture_time_verified",
            "effective_diagnostic_connection_mode_verified",
            "same_process_loaded_virtual_j2534_module_verified",
            "original_vida_readvin_getscript_verified",
            "original_vida_vin_accepted_verified", "ecu_identity_accepted_verified",
        ):
            self.assertIs(result[key], False)
        data = json.dumps(result)
        for secret in ("PERSONAL_MARKER", PRIVATE_PATH, "200", "C:\\Secret"):
            self.assertNotIn(secret, data)

    def test_02_different_pid_cannot_match_even_identical_path(self):
        other = analyze(event(201, "CreateFile"), event(201, "ReadFile"))
        self.assertEqual(other["source_row_match_category"],
                         "selected_config_read_only_by_different_pid")
        self.assertFalse(other["selected_pid_exact_path_successful_read_observed"])
        self.assertEqual(other["other_pid_selected_config_path_successful_reads"], 1)

    def test_03_other_config_path_does_not_match_selected_xml(self):
        other = analyze(event(200, "CreateFile", path=OTHER_PATH),
                        event(200, "ReadFile", path=OTHER_PATH))
        self.assertEqual(other["source_row_match_category"],
                         "selected_pid_read_only_other_config_path")
        self.assertFalse(other["literal_selected_pid_and_normalized_path_found_in_csv"])
        mismatch = analyze(event(200, "ReadFile", path=PRIVATE_PATH + ".old"))
        self.assertEqual(mismatch["source_row_match_category"],
                         "no_selected_pid_exact_path_io_in_export")
        other_process = analyze(event(200, "ReadFile", name="w3wp.exe"))
        self.assertEqual(other_process["source_row_match_category"],
                         "no_selected_pid_exact_path_io_in_export")

    def test_04_no_open_or_intervening_close_is_not_handle_proof(self):
        without = analyze(event(200, "ReadFile"))
        self.assertEqual(without["source_row_match_category"],
                         "selected_pid_exact_path_read_without_open_row")
        closed = analyze(event(200, "CreateFile"),
                         event(200, "CloseFile"), event(200, "ReadFile"))
        self.assertEqual(closed["selected_pid_exact_path_readfile_after_prior_open_rows"], 0)
        self.assertFalse(closed["csv_chronological_order_and_file_handle_verified"])
        self.assertFalse(closed["selected_pid_start_time_and_capture_window_verified"])

    def test_05_ambiguous_multiple_candidate_paths_or_pids(self):
        multiple_paths = analyze(
            event(200, "CreateFile"), event(200, "ReadFile"),
            event(200, "CreateFile", path=OTHER_PATH),
            event(200, "ReadFile", path=OTHER_PATH))
        self.assertEqual(multiple_paths["source_row_match_category"],
                         "selected_pid_read_multiple_candidate_config_paths")
        self.assertEqual(
            multiple_paths["selected_pid_other_config_path_successful_reads"], 1)
        pids = analyze(event(200, "CreateFile"), event(200, "ReadFile"),
                       event(201, "ReadFile"))
        self.assertEqual(pids["source_row_match_category"],
                         "selected_config_path_read_by_multiple_name_matched_pids")
        self.assertEqual(pids["other_pid_selected_config_path_successful_reads"], 1)

    def test_06_failed_or_open_only_and_nocomm_candidate(self):
        fail = analyze(event(200, "CreateFile", result="NAME NOT FOUND"),
                       event(200, "ReadFile", result="ACCESS DENIED"),
                       mode="NoCommConnection")
        self.assertEqual(fail["source_row_match_category"],
                         "selected_pid_exact_path_io_failed_only")
        self.assertEqual(fail["selected_pid_exact_path_failed_open_or_read_rows"], 2)
        self.assertEqual(fail["xml_mode_candidate"], "NoCommConnection")
        self.assertFalse(fail["effective_diagnostic_connection_mode_verified"])
        opened = analyze(event(200, "CreateFile"))
        self.assertEqual(opened["source_row_match_category"],
                         "selected_pid_exact_path_open_only")

    def test_07_invalid_pid_csv_columns_and_unsupported_xml_fail_closed(self):
        for pid in ("0", "-12", "ABC", "1234567890123456789", "4294967296"):
            with self.subTest(pid=pid):
                with self.assertRaises(tool.SourceError):
                    analyze(event(200, "ReadFile"), selected_pid=pid)
        with self.assertRaises(tool.SourceError):
            analyze(event("INVALID", "ReadFile"))
        with self.assertRaises(tool.SourceError):
            analyze(event(200, "ReadFile"), selected_path=r"\relative\diagnostic.config.xml")
        with self.assertRaises(tool.SourceError):
            tool.analyze_text("Process Name,PID,Operation,Result\n",
                              "iexplore.exe", "200", PRIVATE_PATH, config())
        with self.assertRaises(tool.SourceError):
            tool.analyze_text(csv_text(event(200, "ReadFile")), "other.exe",
                              "200", PRIVATE_PATH, config())
        tampered = config()
        tampered["original_vida_vin_accepted_verified"] = True
        with self.assertRaises(tool.SourceError):
            tool.analyze_text(csv_text(event(200, "ReadFile")), "iexplore.exe",
                              "200", PRIVATE_PATH, tampered)
        tampered = config()
        tampered["use_client_settings_candidate"] = PRIVATE_PATH
        with self.assertRaises(tool.SourceError):
            tool.analyze_text(csv_text(event(200, "ReadFile")), "iexplore.exe",
                              "200", PRIVATE_PATH, tampered)

    def test_08_owner_only_windows_cli_reads_actual_synthetic_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            xml_path = home / "diagnostic.config.xml"
            xml_path.write_bytes(
                b'<root><add key="DiagnosticConnection" value="NoCommConnection"/>'
                b'<add key="UseClientSettings" value="true"/></root>')
            log_path = home / "private.csv"
            log_path.write_text(
                csv_text(event(1033, "CreateFile", path=str(xml_path)),
                         event(1033, "ReadFile", path=str(xml_path))),
                encoding="utf-8")
            if os.name == "nt":
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(tool.main([
                        "--procmon-csv", str(log_path),
                        "--xml-candidate", str(xml_path),
                        "--process-name", "iexplore.exe",
                        "--pid", "1033",
                    ]), 0)
                result = json.loads(out.getvalue())
                self.assertTrue(
                    result["selected_pid_exact_path_successful_read_observed"])
                self.assertEqual(result["xml_mode_candidate"], "NoCommConnection")
                self.assertNotIn(str(xml_path), out.getvalue())
                self.assertNotIn("1033", out.getvalue())
                self.assertEqual(err.getvalue(), "")
            else:
                with self.assertRaises(tool.SourceError):
                    tool.analyze_files(log_path, xml_path, "iexplore.exe", "1033")
            invalid = home / "wrong.csv"
            invalid.write_bytes(b"x" * 400)
            with self.assertRaises(tool.SourceError):
                tool._read_owner_csv(invalid)
            bad_xml = home / "bad.xml"
            bad_xml.write_text("<invalid/>")
            with self.assertRaises(tool.SourceError):
                tool.analyze_files(log_path, bad_xml, "iexplore.exe", "1033")


if __name__ == "__main__":
    unittest.main()
