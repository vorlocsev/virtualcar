"""Eight synthetic groups for P3Tool-relevant J2534 metadata-only audit."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "tools" / "audit_j2534_connect.py"
spec = importlib.util.spec_from_file_location("audit_j2534_connect", MODULE)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def be(*words):
    return " ".join(f"{byte:02X}" for w in words for byte in w.to_bytes(4, "big"))


def conn(proto, flags, baud, status, *, host="p3tool.exe", pid="1234ABCD"):
    return f"[PID={pid} {host}] {tool.CONNECT} {be(proto, flags, baud, status)}\n"


def cfg(channel, param, value, applied=0, *, host="p3tool.exe"):
    return f"[PID=1234ABCD {host}] {tool.CONFIG} {be(channel, param, value, applied)}\n"


class P3ToolJ2534PreflightTests(unittest.TestCase):
    def test_01_standard_iso_and_can_hs_are_only_transport_success(self):
        result = tool.audit([conn(6, 0, 500000, 0), conn(5, 0, 500000, 0)])
        self.assertEqual(result["connect"]["attempts"], 2)
        self.assertEqual(result["connect"]["statuses"], {"ok": 2})
        self.assertEqual([x["protocol"] for x in result["connect"]["modes"]],
                         ["CAN", "ISO15765"])
        self.assertFalse(result["vehicle_identity_verified"])

    def test_02_125k_volvo_ch2_flag_is_labelled_not_implemented(self):
        result = tool.audit([conn(6, 0x20000000, 125000, 0),
                             conn(5, 0, 125000, 0)])
        self.assertEqual(result["connect"]["attempts"], 2)
        self.assertTrue(any(x["flags"] == "VOLVO_CH2" for x in result["connect"]["modes"]))
        self.assertFalse(result["p2_p3_compatibility_verified"])

    def test_03_vendor_protocol_errors_remain_distinct(self):
        result = tool.audit([conn(0x8004, 0, 125000, 3),
                             conn(0x8005, 0, 125000, 3)])
        self.assertEqual(result["connect"]["statuses"], {"invalid_protocol": 2})
        self.assertEqual({x["protocol"] for x in result["connect"]["modes"]},
                         {"CAN_PS", "ISO15765_PS"})

    def test_04_xon_xoff_different_flags_do_not_become_success(self):
        result = tool.audit([conn(0x10000001, 0x600, 500000, 3),
                             conn(0x10000001, 0x20000600, 125000, 3)])
        self.assertEqual(result["connect"]["attempts"], 2)
        self.assertEqual({x["flags"] for x in result["connect"]["modes"]},
                         {"CAN_11BIT_ID_HS", "CAN_11BIT_ID_LS"})
        self.assertEqual({x["status"] for x in result["connect"]["modes"]},
                         {"invalid_protocol"})

    def test_05_expected_errors_and_other_error_are_no_leak(self):
        result = tool.audit([conn(5, 0, 500000, 4),
                             conn(5, 0, 500000, 12),
                             conn(5, 0, 500000, 26),
                             conn(99, 0xDEADBEEF, 123456, 0xFE)])
        self.assertEqual(result["connect"]["attempts"], 4)
        self.assertEqual([x["protocol"] for x in result["connect"]["modes"] if
                          x["status"] == "other_error"], ["other"])
        self.assertNotIn("DEADBEEF", json.dumps(result))
        self.assertNotIn("123456", json.dumps(result))
        self.assertNotIn("99", json.dumps(result))

    def test_06_config_applied_vs_noop_and_private_values(self):
        lines = [cfg(1, 1, 125000, 1),
                 cfg(1, 3, 0),
                 cfg(1, 23, 80),
                 cfg(1, 30, 0),
                 cfg(1, 31, 0),
                 cfg(1, 0x8001, 0x030B),
                 cfg(1, 0, 0)]
        result = tool.audit(lines)
        self.assertEqual(result["set_config"]["events"], 7)
        self.assertEqual(len(result["set_config"]["parameters"]), 7)
        self.assertEqual(next(x["handling"] for x in result["set_config"]["parameters"]
                              if x["parameter"] == "DATA_RATE"), "applied_baud")
        self.assertEqual(next(x["handling"] for x in result["set_config"]["parameters"]
                              if x["parameter"] == "J1962_PINS"), "accepted_no_effect")
        self.assertNotIn("779", json.dumps(result))
        self.assertNotIn("030B", json.dumps(result))

    def test_07_raw_can_and_host_metadata_are_never_exported(self):
        secret = "PRIVATE_VIN_123456789_"
        lines = [
            conn(6, 0, 500000, 0, host="p3tool-secret.exe"),
            f"[PID=1234ABCD p3tool-secret.exe] TX (app request) {secret}\n",
            f"[PID=1234ABCD p3tool-secret.exe] PassThruReadMsgs -> delivered {secret}\n",
            cfg(1, 0, 0xABCD1234, host="p3tool-secret.exe"),
        ]
        result = tool.audit(lines)
        content = json.dumps(result)
        for string in (secret, "1234ABCD", "p3tool-secret.exe", "ABCD1234"):
            self.assertNotIn(string, content)
        self.assertEqual(result["connect"]["attempts"], 1)
        self.assertEqual(result["set_config"]["events"], 1)

    def test_08_malformed_and_atomic_non_overwrite_cli(self):
        valid = conn(5, 0, 500000, 0)
        malformed = valid.replace("00 07 A1 20", "GG 07 A1 20")
        wrong = "[PID=XYZ test.exe] " + tool.CONNECT + " " + be(5, 0, 500000, 0)
        malicious = cfg(1, 779, 0x030B, 1)
        result = tool.audit([malformed, wrong, malicious, "some unrelated line\n", valid])
        self.assertEqual(result["connect"]["attempts"], 1)
        self.assertEqual(result["connect"]["invalid_events"], 1)
        self.assertEqual(result["set_config"]["invalid_events"], 1)
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "local.log", Path(folder) / "report.json"
            source.write_text(valid, encoding="utf-8")
            tool.main([str(source), "--output", str(output)])
            self.assertEqual(json.loads(output.read_text())["connect"]["attempts"], 1)
            with self.assertRaises(FileExistsError):
                tool.main([str(source), "--output", str(output)])
            with self.assertRaises(ValueError):
                tool.audit(["ignore\n"] * (tool.MAX_LINES + 1))


if __name__ == "__main__":
    unittest.main()
