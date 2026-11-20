"""Synthetic Procmon CSV config-read attribution tests: no original VIDA or logs."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_procmon_config_read as audit
sys.path.pop(0)

HEADER = '"Time of Day","Process Name","PID","Operation","Path","Result","Detail"\n'
PRIVATE = "C:\\Private\\PERSONAL_VIN_MARKER\\diagnostic.config.xml"
OTHER = "D:\\Another\\Secret\\diagnostic.config.xml"


def row(pid, op, result="SUCCESS", path=PRIVATE, process="iexplore.exe"):
    # All values below are invented solely for these synthetic tests.
    return f'"10:00:00","{process}","{pid}","{op}","{path}","{result}","Sensitive={path}"\n'


def assess(*lines, process="iexplore.exe"):
    return audit.analyze_text(HEADER + "".join(lines), process)


class VidaProcmonConfigReadTests(unittest.TestCase):
    def test_01_successful_same_pid_read_is_only_io_evidence(self):
        report = assess(row(1234, "CreateFile"), row(1234, "ReadFile"))
        self.assertEqual(report["file_io_category"],
                         "read_after_same_pid_path_open")
        self.assertEqual(report["candidate_readfile_success_events"], 1)
        self.assertEqual(report["candidate_readfile_after_prior_same_pid_path_open_events"], 1)
        self.assertEqual(report["distinct_read_candidate_paths_bucket"], "one")
        self.assertFalse(report["original_vida_effective_config_path_verified"])
        self.assertFalse(report["diagnostic_xml_parsed_by_client_verified"])
        self.assertFalse(report["original_vida_vin_accepted_verified"])
        self.assertFalse(report["ecu_identity_accepted_verified"])

    def test_02_open_only_and_failed_io_are_not_reads(self):
        opened = assess(row(1234, "CreateFile"))
        self.assertEqual(opened["file_io_category"], "open_only_no_read_in_export")
        self.assertEqual(opened["candidate_readfile_success_events"], 0)
        failed = assess(row(1234, "CreateFile", "NAME NOT FOUND"),
                        row(1234, "ReadFile", "ACCESS DENIED"))
        self.assertEqual(failed["file_io_category"], "failed_candidate_io_only")
        self.assertEqual(failed["candidate_file_io_failed_events"], 2)
        self.assertEqual(failed["candidate_readfile_success_events"], 0)

    def test_03_missing_open_or_close_breaks_simple_sequence(self):
        missing = assess(row(1234, "ReadFile"))
        self.assertEqual(missing["file_io_category"],
                         "read_without_prior_matching_open_in_export")
        self.assertEqual(missing["candidate_readfile_after_prior_same_pid_path_open_events"], 0)
        closed = assess(row(1234, "CreateFile"), row(1234, "CloseFile"),
                        row(1234, "ReadFile"))
        self.assertEqual(closed["candidate_readfile_without_prior_matching_open_events"], 1)
        self.assertFalse(closed["csv_complete_unfiltered_capture_verified"])
        self.assertFalse(closed["csv_chronological_order_verified"])

    def test_04_different_pid_or_process_cannot_satisfy_prior_open(self):
        split = assess(row(111, "CreateFile"), row(222, "ReadFile"))
        self.assertEqual(split["candidate_readfile_after_prior_same_pid_path_open_events"], 0)
        self.assertEqual(split["candidate_readfile_success_events"], 1)
        other = assess(row(111, "CreateFile", process="java.exe"),
                       row(111, "ReadFile", process="iexplore.exe"))
        self.assertEqual(other["candidate_readfile_without_prior_matching_open_events"], 1)
        self.assertEqual(other["distinct_name_matched_processes_with_successful_reads_bucket"], "one")

    def test_05_two_paths_or_two_name_matched_processes_stay_ambiguous(self):
        multiple_paths = assess(row(1, "CreateFile"), row(1, "ReadFile"),
                                row(1, "CreateFile", path=OTHER),
                                row(1, "ReadFile", path=OTHER))
        self.assertEqual(multiple_paths["file_io_category"],
                         "multiple_candidate_paths_read")
        self.assertEqual(multiple_paths["distinct_read_candidate_paths_bucket"],
                         "multiple")
        multiple_pids = assess(row(1, "CreateFile"), row(1, "ReadFile"),
                               row(2, "CreateFile"), row(2, "ReadFile"))
        self.assertEqual(multiple_pids["file_io_category"],
                         "multiple_name_matched_processes_read")
        self.assertEqual(
            multiple_pids["distinct_name_matched_processes_with_successful_reads_bucket"],
            "multiple")
        self.assertFalse(multiple_pids["original_vida_process_authenticity_verified"])

    def test_06_path_basenames_process_allowlist_and_no_leak(self):
        report = assess(row(123, "ReadFile", path=r"\\relative\\diagnostic.config.xml"),
                        row(123, "CreateFile", path=PRIVATE + ".bak"),
                        row(123, "ReadFile", path=PRIVATE + ":stream"),
                        row(123, "ReadFile", path=r"C:\Private\diagnostic.config.xml2"),
                        row(123, "ReadFile", process="other.exe"),
                        row(123, "ReadFile", process="w3wp.exe"))
        self.assertEqual(report["file_io_category"],
                         "no_matching_candidate_file_io")
        win = assess(row(123, "CreateFile", path=PRIVATE.upper()),
                     row(123, "ReadFile", path=PRIVATE.lower()))
        self.assertEqual(win["file_io_category"],
                         "read_after_same_pid_path_open")
        serialized = json.dumps(win)
        for private in ("PERSONAL_VIN_MARKER", "123", "C:\\Private",
                        "diagnostic.config.xml", "Sensitive="):
            self.assertNotIn(private, serialized)
        for value in ("notepad.exe", "iexplore.exe.bak", "SectorV.exe"):
            with self.subTest(name=value):
                with self.assertRaises(audit.AuditError):
                    assess(row(1, "ReadFile"), process=value)

    def test_07_reject_bad_columns_pid_broken_or_huge_csv(self):
        bad_texts = [
            "Process Name,PID,Operation,Result\n",
            "Process Name,PID,PID,Operation,Path,Result\n",
            HEADER + row("PRIVATE", "ReadFile"),
            HEADER + row(0, "ReadFile"),
            HEADER + row(123, "ReadFile")[:-2],
            HEADER + row(123, "ReadFile", path="not-an-absolute-path"),
        ]
        for text in bad_texts[:4]:
            with self.subTest(length=len(text)):
                with self.assertRaises(audit.AuditError):
                    audit.analyze_text(text, "iexplore.exe")
        self.assertEqual(audit.analyze_text(bad_texts[-1],
                                           "iexplore.exe")["candidate_readfile_success_events"], 0)
        with self.assertRaises(audit.AuditError):
            audit.analyze_text(HEADER + "x" * (audit.MAX_BYTES + 1),
                               "iexplore.exe")
        original = audit.MAX_ROWS
        try:
            audit.MAX_ROWS = 2
            with self.assertRaises(audit.AuditError):
                assess(row(1, "CreateFile"), row(1, "ReadFile"),
                       row(1, "CloseFile"))
        finally:
            audit.MAX_ROWS = original

    def test_08_owner_selected_file_utf8_utf16_private_and_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = HEADER + row(42, "CreateFile") + row(42, "ReadFile")
            for filename, payload in (
                ("trace-utf8.csv", source.encode("utf-8-sig")),
                ("trace-utf16.csv", source.encode("utf-16")),
            ):
                target = root / filename
                target.write_bytes(payload)
                result = audit.analyze_path(target, "iexplore.exe")
                self.assertEqual(result["file_io_category"],
                                 "read_after_same_pid_path_open")
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    rc = audit.main(["--csv", str(target),
                                     "--process-name", "iexplore.exe"])
                self.assertEqual(rc, 0)
                self.assertEqual(stderr.getvalue(), "")
                self.assertNotIn(str(target), stdout.getvalue())
                self.assertNotIn("PERSONAL_VIN_MARKER", stdout.getvalue())
            bad = root / "other.txt"
            bad.write_text(source)
            with self.assertRaises(audit.AuditError):
                audit.analyze_path(bad, "iexplore.exe")
            huge = root / "oversized.csv"
            huge.write_bytes(b"x" * (audit.MAX_BYTES + 1))
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(audit.main(["--csv", str(huge),
                                             "--process-name", "iexplore.exe"]), 2)
            self.assertNotIn(str(huge), stderr.getvalue())
            alias = root / "alias.csv"
            try:
                alias.symlink_to(root / "trace-utf8.csv")
            except (OSError, NotImplementedError):
                pass
            else:
                with self.assertRaises(audit.AuditError):
                    audit.analyze_path(alias, "iexplore.exe")


if __name__ == "__main__":
    unittest.main()
