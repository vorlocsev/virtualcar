"""Eight synthetic tests of threadless VIDA 2010D D2/J2534 boundaries."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "vida2010_boundary", ROOT / "tools" / "audit_vida_2010d_boundary.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def old(text, time="22:36:22,306", category="J2534ChannelMana"):
    return f"{time} [{category}][VehCom] {text}"


def request(target, opcode="B9FB", time="22:36:22,291"):
    return old(f"VehComm request: Ecu '{target}', Message '{opcode}'",
               time, category="DiagConnection ")


def dump(target, op="FB", time="22:36:22,306"):
    return old(
        " ---> (0) 00,0F,FF,FE,CB," + target + ",B9," + op +
        ",00,00,00,00,", time)


class LegacyVida2010BoundaryTests(unittest.TestCase):
    def test_01_b9fb_write_failure_not_automatically_parser_failure(self):
        data = tool.audit("\n".join([
            request("40"),
            old("PassThruConnect(88, 0x10000001, 0x20000100, 125000, 90)",
                "22:36:22,291"),
            old("PassThruStartMsgFilter(90, PASS_FILTER)", "22:36:22,306"),
            old("PassThruWriteMsgs(90, PASSTHRU_MSG, 1, 2000) - synthetic",
                "22:36:22,306"),
            old("J2534 function:passThruWriteMsgs failed with return value:ERR_DEVICE_NOT_CONNECTED",
                "22:36:22,306"),
            dump("40"),
            request("50", time="22:36:22,416"),
        ]))
        a, b = data["attempts"]
        self.assertEqual(a["target"], "0x40")
        self.assertEqual(a["service"], "B9FB")
        self.assertEqual(a["outcome"], "write_failed")
        self.assertEqual(a["write_failure_code"], "ERR_DEVICE_NOT_CONNECTED")
        self.assertEqual(a["write_failure_offset_ms"], 15)
        self.assertEqual(a["next_request_delta_ms"], 125)
        self.assertTrue(a["request_dump_matches"])
        self.assertEqual(a["rx_dump_lines_unverified"], 0)
        self.assertEqual(b["outcome"], "request_only")
        self.assertFalse(data["thread_binding_verified"])
        self.assertFalse(a["j2534_write_success_verified"])
        self.assertFalse(a["ecu_response_verified"])
        self.assertFalse(a["client_acceptance_verified"])

    def test_02_following_open_errors_do_not_become_b9fb_rx(self):
        lines = [request("40"),
                 old("PassThruWriteMsgs(90, PASSTHRU_MSG, 1, 2000)"),
                 old("J2534 function:PassThruWriteMsgs failed with return value:ERR_FAILED"),
                 old("J2534 function:passThruOpen failed with return value:ERR_DEVICE_IN_USE"),
                 old("J2534 function:passThruIoctl_ReadVBatt failed with return value:ERR_INVALID_DEVICE_ID"),
                 request("50", time="22:36:22,416")]
        data = tool.audit("\n".join(lines))
        self.assertEqual(data["attempts"][0]["write_failure_code"], "ERR_FAILED")
        self.assertEqual(data["attempts"][0]["rx_dump_lines_unverified"], 0)
        self.assertEqual(data["adapter_error_counts"]["ERR_DEVICE_IN_USE"], 1)
        self.assertEqual(data["adapter_error_counts"]["ERR_INVALID_DEVICE_ID"], 1)

    def test_03_rx_dump_does_not_prove_client_acceptance(self):
        raw = "\n".join([request("50"),
                         old("PassThruWriteMsgs(90, PASSTHRU_MSG, 1, 2000)"),
                         dump("50"),
                         old("<--- (0) 01,20,00,03,8F,50,F9,FB,00,00,00,00,")])
        data = tool.audit(raw)
        a = data["attempts"][0]
        self.assertEqual(a["outcome"], "write_attempt_result_unknown")
        self.assertEqual(a["rx_dump_lines_unverified"], 1)
        self.assertFalse(a["ecu_response_verified"])

    def test_04_malformed_tx_dump_not_a_matching_d2_request(self):
        malformed = [dump("40", op="F0"),
                     old("---> (0) 00,0F,FF,FE,CB,40,B9,FB,00"),
                     old("---> (0) 00,0F,FF,FE,CB,40,B9,FB,00,00,00,PRIVATE")]
        for line in malformed:
            with self.subTest(line=line[:20]):
                raw = "\n".join([request("40"), old(
                    "PassThruWriteMsgs(90, PASSTHRU_MSG, 1, 2000)"), line])
                self.assertFalse(tool.audit(raw)["attempts"][0]["request_dump_matches"])

    def test_05_html_escaped_legacy_brackets_are_recognized(self):
        raw = request("40").replace("[", "&#91;").replace("]", "&#93;")
        data = tool.audit(raw)
        self.assertEqual(data["attempts"][0]["service"], "B9FB")

    def test_06_modern_three_bracket_format_is_not_merged(self):
        raw = ("22:36:22,291 [DiagConnection ][00A][VehCom] "
               "VehComm request: Ecu '40', Message 'B9FB'\n"
               "22:36:22,306 [J2534ChannelMana][00A][VehCom] "
               "PassThruWriteMsgs(90, PASSTHRU_MSG, 1, 2000)")
        data = tool.audit(raw)
        self.assertEqual(data["attempts"], [])
        self.assertGreaterEqual(data["ignored_no_matching_vida_header"], 2)

    def test_07_missing_or_invalid_clock_does_not_invent_time(self):
        raw = ("\n".join([
            "[DiagConnection ][VehCom] VehComm request: Ecu '40', Message 'B9FB'",
            "[J2534ChannelMana][VehCom] PassThruWriteMsgs(90, PASSTHRU_MSG, 1, 2000)",
            "[J2534ChannelMana][VehCom] J2534 function:passThruWriteMsgs failed with return value:ERR_TIMEOUT",
            "[DiagConnection ][VehCom] VehComm request: Ecu '50', Message 'B9FB'",
        ]))
        result = tool.audit(raw)
        self.assertIsNone(result["attempts"][0]["write_failure_offset_ms"])
        self.assertIsNone(result["attempts"][0]["next_request_delta_ms"])
        self.assertEqual(result["attempts"][0]["write_failure_code"], "ERR_TIMEOUT")

    def test_08_no_ps1_execution_private_output_or_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            src, out = p / "private-input.log", p / "result.json"
            marker = "PRIVATE_VIN_AND_ADAPTER_SERIAL_DO_NOT_COPY"
            src.write_text("\n".join([
                request("50"),
                old("PassThruWriteMsgs(90, PASSTHRU_MSG, 1, 2000)"),
                dump("50"),
                "Write-Output " + marker,
                "C:\\PRIVATE_USER\\VIDA\\Diagnostics\\" + marker,
            ]), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main([str(src), "--output", str(out)]), 0)
            contents = out.read_text(encoding="utf-8")
            self.assertNotIn(marker, contents)
            self.assertNotIn(directory, contents)
            self.assertNotIn("00,0F,FF,FE", contents)
            self.assertFalse(json.loads(contents)["thread_binding_verified"])
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                self.assertEqual(tool.main([str(src), "--output", str(out)]), 2)
                self.assertEqual(tool.main([str(src), "--output", str(src)]), 2)
            self.assertNotIn(marker, errors.getvalue())


if __name__ == "__main__":
    unittest.main()
