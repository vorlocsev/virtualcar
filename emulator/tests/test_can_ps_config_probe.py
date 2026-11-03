"""Eight synthetic metadata groups; no driver, VIN, pin hardware or ECU fixture."""
import json
from pathlib import Path
import tempfile
import unittest

from test_audit_j2534_connect import tool, be, cfg, conn


def probe(operation, value=0, status=0, channel=1, pid="1234ABCD"):
    return f"[PID={pid} SyntheticProbe.exe] {tool.PS_PROBE} {be(channel, operation, value, status)}\n"


class CanPsConfigProbeTests(unittest.TestCase):
    def test_01_config_roundtrip_and_rejected_transport_are_not_bus_support(self):
        lines = [conn(0x8004, 0x900, 125000, 0), probe(1, 0x8004), probe(3),
                 probe(2, 0x030B), probe(3, 0x030B), probe(4, status=1),
                 probe(5, status=1), probe(6, status=1)]
        result = tool.audit(lines)
        data = result["can_ps_config_probe"]
        self.assertEqual((data["events"], data["invalid_events"]), (7, 0))
        self.assertEqual(data["mode"], "configuration_only_no_transport")
        self.assertFalse(data["hardware_pins_verified"])
        self.assertFalse(result["vehicle_identity_verified"])
        self.assertFalse(result["p2_p3_compatibility_verified"])
        self.assertEqual(result["connect"]["modes"][0]["protocol"], "CAN_PS")

    def test_02_parameter_id_is_distinct_from_pin_pair_value(self):
        result = tool.audit([cfg(1, 0x8001, 0x030B), cfg(1, 779, 0x060E)])
        self.assertEqual(result["set_config"]["parameters"], [
            {"parameter": "J1962_PINS", "handling": "accepted_no_effect", "count": 1},
            {"parameter": "other", "handling": "accepted_no_effect", "count": 1}])
        rendered = json.dumps(result)
        for value in ("779", "32769", "030B", "060E"):
            self.assertNotIn(value, rendered)
        self.assertNotIn("can_ps_config_probe", result)

    def test_03_failed_selections_are_counted_without_guessing_binding(self):
        result = tool.audit([probe(2, status=5), probe(2, 0x060E, status=1), probe(3, 0x030B),
                             probe(7, 1, status=25), probe(7, status=1)])
        data = result["can_ps_config_probe"]
        self.assertEqual(data["events"], 5)
        self.assertFalse(data["state_correlation_performed"])
        self.assertTrue(any(x["selection"] == "redacted" and x["status"] == "invalid_ioctl_value"
                            for x in data["operations"]))
        self.assertTrue(any(x["selection"] == "pins_6_14" and x["status"] == "not_supported"
                            for x in data["operations"]))

    def test_04_impossible_metadata_does_not_become_success(self):
        bad = [probe(1, 0x8005), probe(1, 0x8004, status=1), probe(2),
               probe(2, 0x0809), probe(2, 0x030B, status=5), probe(3, 0x060E, status=1),
               probe(4), probe(5), probe(6), probe(7, 1, status=1), probe(7, status=25),
               probe(99), probe(3, channel=0)]
        data = tool.audit(bad)["can_ps_config_probe"]
        self.assertEqual((data["events"], data["invalid_events"]), (0, len(bad)))
        self.assertEqual(data["operations"], [])

    def test_05_malformed_records_and_context_never_leak_numbers(self):
        good = probe(2, 0x030B).strip()
        malformed = [good + " ZZ", good + " 00", good.rsplit(" ", 1)[0],
                     good.replace("00 00 00 01", "0x00 00 00 01", 1)]
        result = tool.audit(malformed + [good.replace("1234ABCD", "not-a-pid")])
        data = result["can_ps_config_probe"]
        self.assertEqual((data["events"], data["invalid_events"]), (0, 4))
        self.assertNotIn("030B", json.dumps(result))

    def test_06_channels_and_processes_are_aggregates_not_state_joins(self):
        lines = [probe(3, channel=1), probe(2, 0x030B, channel=2),
                 probe(2, 0x060E, channel=1, pid="87654321"), probe(3, 0x030B, channel=2)]
        data = tool.audit(lines)["can_ps_config_probe"]
        self.assertEqual(data["events"], 4)
        self.assertFalse(data["state_correlation_performed"])
        self.assertNotIn("channel", json.dumps(data))
        self.assertNotIn("1234ABCD", json.dumps(data))
        self.assertNotIn("87654321", json.dumps(data))

    def test_07_old_trace_scope_and_exclusive_cli_output_remain(self):
        old = tool.audit([conn(5, 0, 500000, 0), cfg(1, 1, 125000, 1)])
        self.assertNotIn("can_ps_config_probe", old)
        self.assertEqual(old["format"], "virtualcar-j2534-connect-audit-v1")
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/"source.log", Path(folder)/"audit.json"
            source.write_text(probe(1, 0x8004), encoding="utf-8")
            tool.main([str(source), "--output", str(output)])
            original = output.read_bytes()
            with self.assertRaises(FileExistsError):
                tool.main([str(source), "--output", str(output)])
            self.assertEqual(output.read_bytes(), original)

    def test_08_privacy_and_input_limits(self):
        secret = "[PID=1234ABCD SecretClient.exe] TX (app request) PRIVATE_0123456789\n"
        lines = [secret, probe(2, 0x030B), probe(2, status=5), probe(4, status=1)]
        rendered = json.dumps(tool.audit(lines))
        for value in ("PRIVATE", "SecretClient", "SyntheticProbe", "1234ABCD", "030B"):
            self.assertNotIn(value, rendered)
        with self.assertRaisesRegex(ValueError, "line_limit"):
            tool.audit("unrelated" for _ in range(tool.MAX_LINES+1))
        self.assertNotIn("can_ps_config_probe", tool.audit([probe(1, 0x8004).strip()+" "*tool.MAX_LINE]))


if __name__ == "__main__":
    unittest.main()
