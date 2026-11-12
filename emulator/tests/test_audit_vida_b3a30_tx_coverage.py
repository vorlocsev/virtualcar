"""B3A30 synthetic log-format tests; no owner logs or real ECU responses."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_b3a30_tx_coverage as tool
sys.path.pop(0)


def line(message, time="12:00:00,000", thread="00A", component="J2534ChannelMana"):
    prefix = time + " " if time else ""
    return f"{prefix}[{component}][{thread}][VehCom]  {message}"


def write(channel=1, count=1, timeout=2000, suffix="", **kw):
    return line(f"PassThruWriteMsgs({channel}, PASSTHRU_MSG, {count}, {timeout}){suffix}", **kw)


def connect(channel=1, protocol=3, baud=10400, **kw):
    return line(f"PassThruConnect(0, 0x{protocol:02X}, 0, {baud}, {channel})", **kw)


def marker(data="83,51,13,B9,F0,", index=0, **kw):
    return line(f"---> ({index}) {data}", **kw)


def error(**kw):
    return line("J2534 function:PassThruWriteMsgs failed with return value:ERR_NOT_SUPPORTED", **kw)


def alternate(index=0, **kw):
    return line(f"PassThruWriteMsgs() msg[{index}].Data = [0x83, 0x51, 0x13, 0xb9, 0xf0]", **kw)


class B3A30SyntheticTests(unittest.TestCase):
    """Eight behavioral groups keep log evidence separate from ECU provenance."""

    def category(self, rows, expected):
        report = tool.audit_lines(rows)
        self.assertEqual(report["inventory"]["write_not_supported_errors"], 1)
        self.assertEqual(report["error_categories"][expected], 1)
        self.assertEqual(sum(report["error_categories"].values()), 1)
        return report

    def test_01_single_tx_literal_shapes_and_existing_call_suffix(self):
        shapes = {
            "84,40,13,B2,F0,00,": "RELAY_CLOSE_LITERAL",
            "83,51,13,B9,F0,": "B9F0_LITERAL",
            "82,51,13,A0,": "TEARDOWN_LITERAL",
            "01,": "OTHER_LITERAL",
        }
        for data, shape in shapes.items():
            with self.subTest(shape=shape):
                rows = [connect(), write(suffix=" - SyntheticThread ->SYNTHETIC_ADAPTER<-"),
                        marker(data), error()]
                report = self.category(rows, "COMPLETE_SINGLE_LOGGED_TX")
                self.assertEqual(report["complete_literal_shapes"][shape], 1)
                self.assertEqual(sum(report["complete_literal_shapes"].values()), 1)
                self.assertEqual(report["error_connect_candidates"]
                                 ["SAME_THREAD_ISO9141_10400_UNACKNOWLEDGED"], 1)
                self.assertEqual(report["inventory"]["write_calls"], 1)
                self.assertEqual(report["inventory"]["write_batch_single"], 1)
                self.assertEqual(report["inventory"]["arrow_tx_exact_component"], 1)
        # Textual casing/zero padding denotes one numeric thread, not another.
        self.category([write(thread="000a"), marker(thread="A"), error(thread="0A")],
                      "COMPLETE_SINGLE_LOGGED_TX")

    def test_02_absent_records_and_other_component_remain_distinct(self):
        self.category([write(), error()], "NO_TX_RECORD")
        report = self.category([write(), marker(component="VehComm"), error()],
                               "TX_RECORD_OTHER_COMPONENT")
        self.assertEqual(report["inventory"]["arrow_tx_other_component"], 1)
        self.assertEqual(report["inventory"]["arrow_tx_exact_component"], 0)
        self.category([write(), marker(), marker(component="VehComm"), error()],
                      "AMBIGUOUS_OR_MALFORMED_RECORD")
        self.category([write(), marker(thread="00B"), error()], "NO_TX_RECORD")
        report = tool.audit_lines([write(component="VehComm", count=2),
                                   "12:00:00,000 0100 000004 PassThruWriteMsgs(1, PASSTHRU_MSG, 1, 2000)"])
        self.assertEqual(report["inventory"]["write_calls"], 0)
        self.assertEqual(report["inventory"]["write_batch_multiple_other_component"], 1)
        self.assertEqual(report["inventory"]["write_batch_single_unscoped"], 1)
        # An unidentified record could belong to the pending write; never use a
        # later well-formed marker to hide that ambiguity.
        self.category([write(), "---> (0) 83,51,13,B9,F0,", marker(), error()],
                      "AMBIGUOUS_OR_MALFORMED_RECORD")

    def test_03_alternate_syntax_scoped_or_inventory_only(self):
        report = self.category([write(), alternate(), error()], "COMPLETE_SINGLE_LOGGED_TX")
        self.assertEqual(report["inventory"]["alternate_tx_records"], 1)
        self.assertEqual(report["complete_literal_shapes"]["B9F0_LITERAL"], 1)
        legacy = ("12:00:00,000 0100 000004 PassThruWriteMsgs() msg[0].Data = "
                  "[0x83, 0x51, 0x13, 0xb9, 0xf0]")
        report = self.category([legacy, error()], "UNMATCHED_ERROR")
        self.assertEqual(report["inventory"]["alternate_tx_records"], 1)
        self.assertEqual(report["inventory"]["malformed_tx_records"], 0)
        self.assertEqual(report["inventory"]["unvalidated_tx_records"], 1)
        self.category([write(), marker(), alternate(), error()],
                      "AMBIGUOUS_OR_MALFORMED_RECORD")
        self.category([write(), legacy, marker(), error()],
                      "AMBIGUOUS_OR_MALFORMED_RECORD")
        self.category([alternate(), error()], "UNMATCHED_ERROR")

    def test_04_batches_indices_and_full_token_validation(self):
        report = self.category([write(count=2), marker(), marker(index=1), error()],
                               "MULTI_MESSAGE")
        self.assertEqual(report["inventory"]["write_batch_multiple"], 1)
        self.category([write(count=2), error()], "MULTI_MESSAGE")
        malformed = [
            [marker(index=1)],
            [marker(), marker()],
            [marker("83,51,13,B9,GG,")],
            [marker("83,51,13,B9,F0 PRIVATE")],
            [marker("83,51,,13,B9,F0,")],
            [marker("")],
            [line("--> (0) 83,51,13,B9,F0,")],
            [marker(), line("----> (0) 83,51,13,B9,F0,")],
            [alternate(index=1)],
            [line("PassThruWriteMsgs() msg[0].Data = [0x83, 0x51, 0x13, 0xb9, 0xf0] PRIVATE")],
        ]
        for packets in malformed:
            with self.subTest(packets=packets):
                report = self.category([write()] + packets + [error()],
                                       "AMBIGUOUS_OR_MALFORMED_RECORD")
                self.assertEqual(sum(report["complete_literal_shapes"].values()), 0)
        for count in (0, 4097):
            self.category([write(count=count), marker(), error()], "UNMATCHED_ERROR")
        report = tool.audit_lines([line("PassThruWriteMsgs(BAD)")])
        self.assertEqual(report["inventory"]["invalid_write_calls"], 1)
        self.assertTrue(all(value >= 0 for value in report["inventory"].values()))

    def test_05_connect_candidates_never_transfer_protocol_or_prove_success(self):
        cases = [
            ([write(), marker(), error()], "MISSING_OR_STALE"),
            ([connect(thread="00B"), write(), marker(), error()],
             "CROSS_THREAD_PROTOCOL_UNVERIFIED"),
            ([connect(protocol=5, baud=500000), write(), marker(), error()],
             "SAME_THREAD_OTHER_UNACKNOWLEDGED"),
            ([connect(), write(time="12:00:31,000"), marker(time="12:00:31,001"),
              error(time="12:00:31,002")], "MISSING_OR_STALE"),
            ([connect()] + ["synthetic unrelated record"] * 201 + [write(), marker(), error()],
             "MISSING_OR_STALE"),
            ([connect(), line("J2534 function:PassThruConnect failed with return value:ERR_INVALID_PROTOCOL_ID"),
              write(), marker(), error()], "MISSING_OR_STALE"),
            ([connect(), connect(protocol=5, baud=500000, thread="00B"), write(), marker(), error()],
             "CROSS_THREAD_PROTOCOL_UNVERIFIED"),
        ]
        for rows, candidate in cases:
            with self.subTest(candidate=candidate, lines=len(rows)):
                report = self.category(rows, "COMPLETE_SINGLE_LOGGED_TX")
                self.assertEqual(report["error_connect_candidates"][candidate], 1)
        self.category([write(), marker(), connect(thread="00B"), error()], "UNMATCHED_ERROR")
        self.category([write(), marker(), error(thread="00B")], "UNMATCHED_ERROR")

    def test_06_lifecycle_intervening_calls_and_monotonic_bounded_windows(self):
        barriers = [
            "Starting new logsession: 2026-01-01 12:00:00",
            line("PassThruDisconnect(1)", thread="00B"),
            line("PassThruClose(0)", thread="00B"),
            line("PassThruOpen(0)", thread="00B"),
            line("PassThruReadMsgs(1, PASSTHRU_MSG, 1, 2000)"),
            line("PassThruIoctl(1, CLEAR_RX_BUFFER, NULL, NULL)"),
            line("J2534Channel::ClearRxBuffer()"),
            "<--- (0)",  # Empty marker only; no synthetic ECU response bytes.
            "12:00:00,000 [J2534ChannelMana][ZZZ][VehCom] <--- (0)",
            line("<--- (0)"),
            line("PassThruOpen", thread="00B"),
            line("PassThruClose", thread="00B"),
            line("PassThruDisconnect", thread="00B"),
            line("PassThruConnect", thread="00B"),
        ]
        for barrier in barriers:
            with self.subTest(barrier=barrier):
                self.category([connect(), write(), marker(), barrier, error()], "UNMATCHED_ERROR")
        # A different channel/thread call does not consume the current writer.
        self.category([write(), line("PassThruReadMsgs(2, PASSTHRU_MSG, 1, 20)", thread="00B"),
                       marker(), error()], "COMPLETE_SINGLE_LOGGED_TX")
        self.category([write(time="12:00:01,000"), marker(time="12:00:00,000"),
                       error(time="12:00:01,001")], "UNMATCHED_ERROR")
        self.category([write(), marker(), error(time="12:00:05,001")], "UNMATCHED_ERROR")
        self.category([write()] + ["synthetic unrelated record"] * 20 + [error()], "UNMATCHED_ERROR")
        self.category([write(time=""), marker(time=""), error(time="")], "UNMATCHED_ERROR")
        self.category([write(), marker(), error(time="25:00:00,000")], "UNMATCHED_ERROR")
        self.category([write(), marker(), error(time="12:61:00,000")], "UNMATCHED_ERROR")
        self.category([write(), marker(), error(component="VehComm")], "UNMATCHED_ERROR")

    def test_07_bounded_input_and_truncated_records_fail_closed(self):
        with self.assertRaises(ValueError):
            tool.audit_lines(["X" * 100_000])
        # Exercise limits without constructing large files or expensive jobs.
        with patch.object(tool, "MAX_LINES", 2), self.assertRaises(ValueError):
            tool.audit_lines(["synthetic"] * 3)
        with patch.object(tool, "MAX_BYTES", 10), self.assertRaises(ValueError):
            tool.audit_lines(["123456", "123456"])
        with patch.object(tool, "MAX_STATES", 2), self.assertRaises(ValueError):
            tool.audit_lines([line("synthetic", thread=f"{value:03X}") for value in range(3)])
        self.category([write(), marker("00," * 4128), error()], "COMPLETE_SINGLE_LOGGED_TX")
        self.category([write(), marker("00," * 4129), error()], "AMBIGUOUS_OR_MALFORMED_RECORD")
        with self.assertRaises(ValueError):
            tool.audit_lines(["synthetic\x00record"])
        self.category([write(), marker("83,51,13,B9,"), error()], "COMPLETE_SINGLE_LOGGED_TX")
        # A shorter but syntactically valid payload is only OTHER_LITERAL.
        report = tool.audit_lines([write(), marker("83,51,13,B9,"), error()])
        self.assertEqual(report["complete_literal_shapes"]["OTHER_LITERAL"], 1)
        self.category([write(), marker("83,51,13,B9,F"), error()],
                      "AMBIGUOUS_OR_MALFORMED_RECORD")
        report = tool.audit_lines([write(), marker()])
        self.assertEqual(sum(report["error_categories"].values()), 0)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "synthetic-truncated.log"
            output = Path(directory) / "never-created.json"
            for raw in (("\n".join([write(), marker(), error()])).encode(), b"\xff\n"):
                source.write_bytes(raw)
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ex:
                    tool.main(["--vida-log", str(source), "--output", str(output)])
                self.assertEqual(ex.exception.code, 2)
                self.assertFalse(output.exists())
                self.assertEqual(source.read_bytes(), raw)

    def test_08_cli_category_only_privacy_exclusive_output_and_read_only_source(self):
        secret = "SYNTHETIC_PRIVATE_SENTINEL"
        with tempfile.TemporaryDirectory(prefix=secret) as directory:
            source = Path(directory) / (secret + ".log")
            output = Path(directory) / "new-report.json"
            rows = [connect(thread="ABCDEF12"),
                    write(thread="ABCDEF12", suffix=" - " + secret),
                    marker(thread="ABCDEF12"), error(thread="ABCDEF12"),
                    line(secret), "[PID=DEADBEEF " + secret + "] " + secret]
            original = ("\n".join(rows) + "\n").encode("utf-8")
            source.write_bytes(original)
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(tool.main(["--vida-log", str(source), "--output", str(output)]), 0)
            payload = output.read_text(encoding="utf-8")
            report = json.loads(payload)
            self.assertEqual(report["error_categories"]["COMPLETE_SINGLE_LOGGED_TX"], 1)
            combined = payload + stdout.getvalue() + stderr.getvalue()
            for value in (secret, str(source), str(output), "ABCDEF12", "DEADBEEF",
                          "12:00:00,000", "83,51,13,B9,F0", "J2534ChannelMana"):
                self.assertNotIn(value, combined)
            self.assertEqual(source.read_bytes(), original)
            first_output = output.read_bytes()
            with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as ex:
                tool.main(["--vida-log", str(source), "--output", str(output)])
            self.assertEqual(ex.exception.code, 2)
            self.assertEqual(output.read_bytes(), first_output)
            self.assertEqual(source.read_bytes(), original)
            # An output equal to the input must never overwrite the source.
            with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
                tool.main(["--vida-log", str(source), "--output", str(source)])
            self.assertEqual(source.read_bytes(), original)
            with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
                tool.main(["--vida-log", str(Path(directory) / secret), "--output", str(output)])
            with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
                tool.main(["--vida-log", str(source), "--output", str(output), "--unknown", secret])
            self.assertNotIn(secret, stderr.getvalue())
            self.assertNotIn(directory, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
