"""B3A31 synthetic marker bookkeeping; no original logs or ECU responses."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_b3a31_header_families as tool
sys.path.pop(0)


def line(message, time="12:00:00,000", thread="00A", component="J2534ChannelMana",
         logger="VehCom"):
    prefix = time + " " if time else ""
    return f"{prefix}[{component}][{thread}][{logger}]  {message}"


def write(channel=1, count=1, **kw):
    return line(f"PassThruWriteMsgs({channel}, PASSTHRU_MSG, {count}, 2000)", **kw)


def marker(index=0, data="01,", **kw):
    return line(f"---> ({index}) {data}", **kw)


def error(**kw):
    return line("J2534 function:PassThruWriteMsgs failed with return value:ERR_NOT_SUPPORTED", **kw)


def legacy():
    # Only the prefix syntax is known here; neither numeric field is adopted
    # as a proven thread, PID, J2534 channel or timestamp of an actual TX.
    return "12:00:00,000 0100 000004 ---> (0) 01,"


def cell(report, scope="EXACT_COMPONENT", kind="ARROW"):
    return report["marker_scope_counts"][kind][scope]


def reason(report, value, scope="EXACT_COMPONENT", kind="ARROW"):
    return report["unbound_reason_counts"][kind][scope][value]


class B3A31SyntheticTests(unittest.TestCase):
    """Eight groups keep source-row bookkeeping separate from attribution."""

    def checked(self, rows):
        report = tool.audit_lines(rows)
        tool._validate_report(report)
        self.assertTrue(report["bookkeeping"]["all_invariants_passed"])
        self.assertEqual(sum(report["log_error_categories"].values()),
                         report["b3a30_inventory"]["write_not_supported_errors"])
        return report

    def test_01_header_families_and_explicit_unbound_census(self):
        rows = [marker(), legacy(), "---> (0) 01,",
                line("---> (0) 01,", thread="ZZZ"),
                marker(thread="00B", component="OtherComponent"),
                write(), marker(), error(), write(),
                line("PassThruWriteMsgs() msg[0].Data = [0x01]"), error()]
        report = self.checked(rows)
        self.assertEqual(cell(report), {"total": 2, "active_write_present": 1, "base_unbound": 1})
        self.assertEqual(cell(report, "OTHER_COMPONENT"),
                         {"total": 1, "active_write_present": 0, "base_unbound": 1})
        self.assertEqual(cell(report, "UNSCOPED"),
                         {"total": 3, "active_write_present": 0, "base_unbound": 3})
        self.assertEqual(cell(report, kind="ALTERNATE"),
                         {"total": 1, "active_write_present": 1, "base_unbound": 0})
        expected = {"EXACT_COMPONENT_BRACKETS": 2, "OTHER_COMPONENT_BRACKETS": 1,
                    "LEGACY_NUMERIC_PREFIX": 1, "BARE_ARROW": 1, "OTHER_OR_UNKNOWN": 1}
        self.assertEqual(report["header_family_counts"]["ARROW"], expected)
        self.assertEqual(report["marker_syntax_counts"]["ARROW"]["EXACT_COMPONENT"]["VALID_SYNTAX"], 2)
        self.assertEqual(report["marker_syntax_counts"]["ARROW"]["UNSCOPED"]["UNVALIDATED_IDENTITY"], 3)
        self.assertEqual(report["b3a30_inventory"]["unbound_tx_records"], 5)
        self.assertEqual(reason(report, "UNKNOWN_THREAD_IDENTITY", "UNSCOPED"), 3)
        self.assertEqual(report["log_error_categories"]["COMPLETE_SINGLE_LOGGED_TX"], 2)
        # SYNTHETIC arithmetic fixture only: matching aggregate counts does
        # not reconstruct or explain any owner-original marker/error event.
        synthetic_counts = []
        for _ in range(18):
            synthetic_counts += [marker(thread="00B"), legacy(), write(), error()]
        for _ in range(70):
            synthetic_counts += [write(), marker()]
        report = self.checked(synthetic_counts)
        inventory = report["b3a30_inventory"]
        self.assertEqual((inventory["write_calls"], inventory["arrow_tx_exact_component"],
                          inventory["arrow_tx_unscoped"], inventory["unbound_tx_records"]),
                         (88, 88, 18, 36))
        self.assertEqual(cell(report)["base_unbound"], 18)
        self.assertEqual(cell(report, "UNSCOPED")["base_unbound"], 18)
        self.assertEqual(reason(report, "NO_PENDING_SAME_THREAD_WRITE"), 18)
        self.assertEqual(reason(report, "UNKNOWN_THREAD_IDENTITY", "UNSCOPED"), 18)
        self.assertEqual(report["log_error_categories"]["NO_TX_RECORD"], 18)
        self.assertEqual(report["claims"]["actual_transport"], "UNVERIFIED")

    def test_02_swapped_jumbled_threads_and_other_component_are_not_rebound(self):
        report = self.checked([write(thread="00A"), marker(thread="00B"), error(thread="00A")])
        self.assertEqual(reason(report, "NO_PENDING_SAME_THREAD_WRITE"), 1)
        self.assertEqual(report["log_error_categories"]["NO_TX_RECORD"], 1)
        self.assertEqual(cell(report)["base_unbound"], 1)
        report = self.checked([write(), line("---> (0) 01,", thread="00-A"), error()])
        self.assertEqual(reason(report, "UNKNOWN_THREAD_IDENTITY", "UNSCOPED"), 1)
        self.assertEqual(report["log_error_categories"]["AMBIGUOUS_OR_MALFORMED_RECORD"], 1)
        # Numeric aliases are the same identity under the pinned base parser.
        report = self.checked([write(thread="000a"), marker(thread="A"), error(thread="0A")])
        self.assertEqual(cell(report)["active_write_present"], 1)
        self.assertEqual(report["log_error_categories"]["COMPLETE_SINGLE_LOGGED_TX"], 1)
        report = self.checked([write(), marker(component="OtherComponent"), error()])
        self.assertEqual(cell(report, "OTHER_COMPONENT")["active_write_present"], 1)
        self.assertEqual(cell(report, "OTHER_COMPONENT")["base_unbound"], 0)
        self.assertEqual(report["log_error_categories"]["TX_RECORD_OTHER_COMPONENT"], 1)
        truncated_header = "12:00:00,000 [J2534ChannelMana][00A[VehCom] ---> (0) 01,"
        report = self.checked([write(), truncated_header, error()])
        self.assertEqual(report["header_family_counts"]["ARROW"]["OTHER_OR_UNKNOWN"], 1)
        self.assertEqual(reason(report, "UNKNOWN_THREAD_IDENTITY", "UNSCOPED"), 1)

    def test_03_duplicate_malformed_and_batch_records_do_not_change_unbound_definition(self):
        for packets in ([marker(), marker()], [marker(index=1)],
                        [marker(data="01,GG,")], [marker(data="01 PRIVATE")]):
            with self.subTest(packets=packets):
                report = self.checked([write()] + packets + [error()])
                self.assertEqual(cell(report)["active_write_present"], len(packets))
                self.assertEqual(cell(report)["base_unbound"], 0)
                self.assertEqual(report["log_error_categories"]["AMBIGUOUS_OR_MALFORMED_RECORD"], 1)
        report = self.checked([write(count=2), marker(), marker(index=1), error()])
        self.assertEqual(cell(report)["active_write_present"], 2)
        self.assertEqual(report["log_error_categories"]["MULTI_MESSAGE"], 1)
        report = self.checked([marker(data="01,GG,")])
        self.assertEqual(cell(report)["base_unbound"], 1)
        self.assertEqual(reason(report, "NO_PENDING_SAME_THREAD_WRITE"), 1)
        self.assertEqual(report["b3a30_inventory"]["malformed_tx_records"], 1)
        self.assertEqual(report["marker_syntax_counts"]["ARROW"]["EXACT_COMPONENT"]["MALFORMED_SYNTAX"], 1)
        parity_fixtures = [
            [write(), marker(), error()],
            [write(), marker(), marker(), legacy(), error()],
            [write(), marker(component="OtherComponent"), error()],
            [write(count=2), marker(), marker(index=1), error()],
            [write(), "Starting new logsession: 2026-01-01 12:00:00", marker(), error()],
            [write(thread="00B"), marker(thread="00A"), error(thread="00B")],
        ]
        for rows in parity_fixtures:
            with self.subTest(parity_rows=len(rows)):
                report = self.checked(rows)
                baseline = tool.base.audit_lines(rows)
                self.assertEqual(report["b3a30_inventory"], baseline["inventory"])
                self.assertEqual(report["log_error_categories"], baseline["error_categories"])

    def test_04_observed_invalidation_reasons_survive_intervening_rows(self):
        cases = [
            ([write(), line("PassThruDisconnect(1)", thread="00B"), marker()],
             "LAST_WRITE_CLEARED_BY_LIFECYCLE"),
            ([write(), line("PassThruClose(0)", thread="00B"), marker()],
             "LAST_WRITE_CLEARED_BY_LIFECYCLE"),
            ([write(), line("PassThruConnect(0, 5, 0, 500000, 1)", thread="00B"), marker()],
             "LAST_WRITE_CLEARED_BY_LIFECYCLE"),
            ([write(), line("PassThruReadMsgs(1, PASSTHRU_MSG, 1, 2000)"), marker()],
             "LAST_WRITE_CLEARED_BY_INTERVENING_CALL"),
            ([write(), error(), marker()], "LAST_WRITE_CLEARED_BY_TERMINAL_ERROR"),
            ([write(), line("<--- (0)"), marker()], "LAST_WRITE_CLEARED_BY_OTHER_RECORD"),
            ([write()] + ["synthetic unrelated row"] * 21 + [marker()], "LAST_WRITE_EXPIRED"),
            ([write(), marker(time="12:00:05,001")], "LAST_WRITE_EXPIRED"),
            ([write(), marker(time="")], "CLOCK_MISSING_OR_BACKWARDS"),
            ([write(), "unknown prefix PassThruReadMsgs(1, PASSTHRU_MSG, 1, 2000)", marker()],
             "UNKNOWN_LAYOUT_BARRIER"),
        ]
        for rows, expected in cases:
            with self.subTest(reason=expected, rows=len(rows)):
                report = self.checked(rows)
                self.assertEqual(reason(report, expected), 1)
                self.assertEqual(cell(report)["base_unbound"], 1)
        # Unrelated channel lifecycle does not explain another channel's writer.
        report = self.checked([write(), line("PassThruDisconnect(2)", thread="00B"), marker(), error()])
        self.assertEqual(cell(report)["base_unbound"], 0)
        self.assertEqual(report["log_error_categories"]["COMPLETE_SINGLE_LOGGED_TX"], 1)
        # A fresh reused-channel write clears the old categorical tombstone.
        report = self.checked([write(), line("PassThruDisconnect(1)"), write(), marker(), error()])
        self.assertEqual(cell(report)["base_unbound"], 0)
        self.assertEqual(report["log_error_categories"]["COMPLETE_SINGLE_LOGGED_TX"], 1)

    def test_05_proximity_uses_only_row_order_with_session_and_midnight_limits(self):
        report = self.checked([write(time="23:59:59,999"), marker(time="00:00:00,001"),
                               error(time="00:00:00,002")])
        self.assertEqual(reason(report, "CLOCK_MISSING_OR_BACKWARDS"), 1)
        proximity = report["source_order_proximity"]["BASE_UNBOUND_ARROWS"]
        self.assertEqual(proximity["PRECEDING_WRITE"]["ROWS_0_5"], 1)
        self.assertEqual(proximity["FOLLOWING_WRITE_ERROR"]["ROWS_0_5"], 1)
        report = self.checked([write(), "Starting new logsession: 2026-01-01 12:00:00",
                               "---> (0) 01,", error()])
        proximity = report["source_order_proximity"]["UNSCOPED_ARROWS"]
        self.assertEqual(proximity["PRECEDING_WRITE"]["UNKNOWN"], 1)
        self.assertEqual(proximity["PRECEDING_WRITE_ERROR"]["UNKNOWN"], 1)
        self.assertEqual(proximity["FOLLOWING_WRITE_ERROR"]["ROWS_0_5"], 1)
        for distance, bucket in ((1, "ROWS_0_5"), (6, "ROWS_6_20"),
                                 (21, "ROWS_21_100"), (101, "ROWS_OVER_100")):
            with self.subTest(distance=distance):
                filler = ["synthetic unrelated row"] * (distance - 1)
                report = self.checked([write()] + filler + ["---> (0) 01,"])
                self.assertEqual(report["source_order_proximity"]["UNSCOPED_ARROWS"]
                                 ["PRECEDING_WRITE"][bucket], 1)
                report = self.checked(["---> (0) 01,"] + filler + [write()])
                self.assertEqual(report["source_order_proximity"]["UNSCOPED_ARROWS"]
                                 ["FOLLOWING_WRITE"][bucket], 1)

    def test_06_invariants_reject_inconclusive_or_corrupted_sum_of_parts(self):
        original = self.checked([marker(), legacy()])
        mutations = [
            lambda r: r.__setitem__("schema", "UNREVIEWED_SCHEMA"),
            lambda r: r.__setitem__("unexpected_field", 1),
            lambda r: r["marker_scope_counts"]["ARROW"]["EXACT_COMPONENT"].__setitem__("total", 2),
            lambda r: r["unbound_reason_counts"]["ARROW"]["UNSCOPED"].__setitem__("UNKNOWN_THREAD_IDENTITY", 2),
            lambda r: r["header_family_counts"]["ARROW"].__setitem__("BARE_ARROW", 1),
            lambda r: r["marker_syntax_counts"]["ARROW"]["EXACT_COMPONENT"].__setitem__("VALID_SYNTAX", 2),
            lambda r: r["source_order_proximity"]["UNSCOPED_ARROWS"]["PRECEDING_WRITE"].__setitem__("UNKNOWN", 2),
            lambda r: r["b3a30_inventory"].__setitem__("unbound_tx_records", 3),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutations.index(mutate)):
                report = copy.deepcopy(original)
                mutate(report)
                with self.assertRaises(ValueError):
                    tool._validate_report(report)

    def test_07_oversized_malformed_utf8_and_truncated_file_fail_closed(self):
        for rows in (["X" * 100_000], ["synthetic\x00row"]):
            with self.subTest(length=len(rows[0])), self.assertRaises(ValueError):
                tool.audit_lines(rows)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "synthetic.log"
            output = Path(directory) / "must-not-exist.json"
            for raw in (("\n".join([write(), marker(), error()])).encode(), b"\xff\n"):
                source.write_bytes(raw)
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ex:
                    tool.main(["--vida-log", str(source), "--output", str(output)])
                self.assertEqual(ex.exception.code, 2)
                self.assertFalse(output.exists())
                self.assertEqual(source.read_bytes(), raw)
            with source.open("wb") as stream:
                stream.truncate(32 * 1024 * 1024 + 1)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ex:
                tool.main(["--vida-log", str(source), "--output", str(output)])
            self.assertEqual(ex.exception.code, 2)
            self.assertFalse(output.exists())

    def test_08_cli_privacy_truthful_claims_and_exclusive_output(self):
        secret = "SYNTHETIC_PRIVATE_SENTINEL"
        with tempfile.TemporaryDirectory(prefix=secret) as directory:
            source = Path(directory) / (secret + ".log")
            output = Path(directory) / "new-report.json"
            rows = [write(thread="ABCDEF12", logger=secret),
                    marker(thread="ABCDEF12", logger=secret), error(thread="ABCDEF12"),
                    legacy(), line(secret, component=secret), "[PID=DEADBEEF " + secret + "]"]
            original = ("\n".join(rows) + "\n").encode()
            source.write_bytes(original)
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(tool.main(["--vida-log", str(source), "--output", str(output)]), 0)
            first_output = output.read_bytes()
            report = json.loads(first_output)
            claims = report["claims"]
            self.assertEqual(claims["audit_execution_on_supplied_input"], "COMPLETED")
            self.assertTrue(claims["log_error_categories_computed"])
            self.assertEqual(claims["input_authenticity"], "NOT_VERIFIED")
            self.assertEqual(claims["actual_transport"], "UNVERIFIED")
            combined = first_output.decode() + stdout.getvalue() + stderr.getvalue()
            for value in (secret, directory, str(source), str(output), "ABCDEF12", "DEADBEEF",
                          "12:00:00,000", "0100 000004", "J2534ChannelMana", "---> (0)",
                          "original_18_event_classification", "REQUIRES_OWNER_LOCAL_RUN"):
                self.assertNotIn(value, combined)
            self.assertEqual(source.read_bytes(), original)
            for argv in (["--vida-log", str(source), "--output", str(output)],
                         ["--vida-log", str(source), "--output", str(source)],
                         ["--vida-log", str(source), "--output", str(output), "--unknown", secret]):
                with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as ex:
                    tool.main(argv)
                self.assertEqual(ex.exception.code, 2)
                self.assertEqual(output.read_bytes(), first_output)
                self.assertEqual(source.read_bytes(), original)
            self.assertNotIn(secret, stderr.getvalue())
            self.assertNotIn(directory, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
