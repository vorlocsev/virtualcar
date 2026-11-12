"""Eight synthetic groups for opt-in CAN_PS metadata classification; no OEM frames."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "tools" / "audit_j2534_connect.py"
spec = importlib.util.spec_from_file_location("audit_j2534_connect_pslab", MODULE)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def be(*words):
    return " ".join(f"{b:02X}" for n in words for b in n.to_bytes(4, "big"))


def conn(proto, flags, baud, status):
    return "[PID=1234ABCD p3tool.exe] " + tool.CONNECT + " " + be(
        proto, flags, baud, status) + "\n"


def cfg(channel, parameter, value, applied=0):
    return "[PID=1234ABCD p3tool.exe] " + tool.CONFIG + " " + be(
        channel, parameter, value, applied) + "\n"


def param(report, name, handling):
    return next((entry for entry in report["set_config"]["parameters"]
                 if entry["parameter"] == name and entry["handling"] == handling), None)


class EightPsPinMetadataGroups(unittest.TestCase):
    def test_01_standard_connect_not_vehicle_identity(self):
        result = tool.audit([conn(5, 0, 500000, 0), conn(6, 0, 500000, 0)])
        self.assertEqual(result["connect"]["statuses"], {"ok": 2})
        self.assertFalse(result["vehicle_identity_verified"])

    def test_02_29bit_flag_is_not_physical_wire_proof(self):
        result = tool.audit([conn(5, 0x100, 125000, 0)])
        self.assertEqual(result["connect"]["modes"][0]["flags"], "CAN_29BIT_ID")
        self.assertFalse(result["p2_p3_compatibility_verified"])

    def test_03_ps_success_and_rejection_stay_separate(self):
        result = tool.audit([conn(0x8004, 0, 125000, 3),
                             conn(0x8005, 0, 125000, 0)])
        self.assertEqual(result["connect"]["statuses"],
                         {"invalid_protocol": 1, "ok": 1})
        self.assertEqual(len(result["connect"]["modes"]), 2)
        self.assertFalse(result["vehicle_identity_verified"])

    def test_04_ms_pins_are_local_j2534_state(self):
        result = tool.audit([cfg(2, 0x8001, 0x030B, 1)])
        self.assertIsNotNone(param(result, "J2534_PINS",
                                   "virtual_ms_pins_applied"))
        self.assertEqual(result["set_config"]["invalid_events"], 0)
        self.assertNotIn("030B", json.dumps(result))

    def test_05_legacy_779_is_not_a_pin_parameter_identifier(self):
        result = tool.audit([cfg(2, 779, 0x030B, 0)])
        self.assertIsNotNone(param(result, "LEGACY_PARAMETER_779",
                                   "accepted_no_effect"))
        self.assertNotIn("J1962_PINS", json.dumps(result))

    def test_06_redacted_applied_metadata_remains_unattributed(self):
        result = tool.audit([cfg(2, 0, 0, 1), cfg(2, 0, 0, 0)])
        self.assertIsNotNone(param(result, "other",
                                   "redacted_applied_unidentified"))
        self.assertIsNotNone(param(result, "other", "accepted_no_effect"))
        self.assertNotIn("KLINE_PARITY", json.dumps(result))

    def test_07_invalid_pins_and_wrong_applied_status_rejected(self):
        result = tool.audit([cfg(2, 0x8001, 0x030C, 1),
                             cfg(2, 779, 0x030B, 1),
                             cfg(0, 1, 125000, 1)])
        self.assertEqual(result["set_config"]["invalid_events"], 3)
        self.assertEqual(result["set_config"]["events"], 0)

    def test_08_privacy_and_output_must_not_overwrite(self):
        secret = "SECRET_VIN_AND_PATH_foo"
        rows = [conn(5, 0, 500000, 0),
                f"[PID=1234ABCD secret.exe] TX {secret}\n",
                cfg(2, 0x8001, 0x030B, 1)]
        result = tool.audit(rows)
        self.assertNotIn(secret, json.dumps(result))
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "private.log"
            output = Path(folder) / "summary.json"
            source.write_text("".join(rows), encoding="utf-8")
            tool.main([str(source), "--output", str(output)])
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["set_config"]["events"], 1)
            self.assertFalse(report["vehicle_identity_verified"])
            with self.assertRaises(FileExistsError):
                tool.main([str(source), "--output", str(output)])


if __name__ == "__main__":
    unittest.main()
