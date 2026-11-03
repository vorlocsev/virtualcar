"""Eight synthetic groups: local API outcomes never prove CAN or ECU activity."""
import json
from pathlib import Path
import tempfile
import unittest

from test_audit_j2534_connect import tool, be, cfg, conn
from test_can_ps_config_probe import probe
from test_can_ps_rejected_attempts import attempt
from test_can_ps_rejected_setup import periodic_event


def outcome(operation=3, mask=2, pins=0x030B, baud=125000, shape=42, status=0,
            channel=1, pid="1234ABCD"):
    return (f"[PID={pid} PrivateClient.exe] {tool.PS_API_OUTCOME} "
            f"{be(channel, mask, operation, pins, baud, shape, status)}\n")


class CanPsApiOutcomeTests(unittest.TestCase):
    def test_01_all_masks_keep_each_creation_bit_independent(self):
        lines = []
        for mask in range(8):
            lines.append(outcome(1, mask, pins=0, shape=0))
            for operation, bit, shape in ((2, 1, 1), (3, 2, 42), (4, 4, 42)):
                lines.append(outcome(operation, mask, shape=shape, status=0 if mask & bit else 1))
        data = tool.audit(lines)["can_ps_api_outcomes"]
        self.assertEqual((data["mode_snapshots"], data["calls"], data["invalid_events"]), (8, 24, 0))
        self.assertEqual((data["injected_success_calls"], data["rejected_creation_calls"]), (12, 12))
        self.assertEqual(data["mode"], "counterfactual_local_api_outcomes_only")
        self.assertEqual({row["mask"] for row in data["categories"]}, set(range(8)))
        for name in ("state_correlation_performed", "can_transmission_verified", "ecu_response_verified",
                     "periodic_firing_observed", "read_only_reference_approved"):
            self.assertFalse(data[name])

    def test_02_success_requires_the_exact_creation_eligibility(self):
        bad = []
        good = []
        for operation, bit, shape in ((2, 1, 1), (3, 2, 42), (4, 4, 42)):
            good.append(outcome(operation, bit, shape=shape))
            good += [outcome(operation, 0, pins=0, baud=0, shape=0, status=1),
                     outcome(operation, 7, pins=0x060E, baud=500000, shape=shape, status=1)]
            bad += [outcome(operation, 0, shape=shape), outcome(operation, 7 ^ bit, shape=shape),
                    outcome(operation, bit, pins=0, shape=shape),
                    outcome(operation, bit, pins=0x060E, shape=shape),
                    outcome(operation, bit, baud=0, shape=shape),
                    outcome(operation, bit, baud=500000, shape=shape),
                    outcome(operation, bit, shape=0), outcome(operation, bit, shape=shape, status=22),
                    outcome(operation, bit, shape=42 if operation == 2 else 1, status=1)]
        data = tool.audit(good + bad)["can_ps_api_outcomes"]
        self.assertEqual((data["calls"], data["invalid_events"]), (len(good), len(bad)))
        self.assertEqual((data["injected_success_calls"], data["rejected_creation_calls"]), (3, 6))

    def test_03_cleanup_survives_route_changes_but_mode_zero_remains_legacy(self):
        good = [outcome(5, 1, pins=0x060E, baud=500000, shape=0),
                outcome(6, 4, pins=0, baud=0, shape=0),
                outcome(7, 2, pins=0x060E, baud=500000, shape=0),
                outcome(8, 1, pins=0, baud=0, shape=0),
                outcome(5, 2, shape=0, status=22), outcome(6, 1, shape=0, status=13)]
        bad = [outcome(op, 0, shape=0) for op in range(5, 9)]
        bad += [outcome(5, 2, shape=0), outcome(6, 1, shape=0),
                outcome(5, 1, shape=0, status=13), outcome(6, 4, shape=0, status=22),
                outcome(7, 1, shape=0, status=1), outcome(8, 4, shape=0, status=12),
                outcome(5, 1, shape=1), outcome(6, 4, shape=42)]
        data = tool.audit(good + bad)["can_ps_api_outcomes"]
        self.assertEqual((data["calls"], data["lifecycle_calls"], data["invalid_events"]),
                         (len(good), len(good), len(bad)))
        self.assertEqual(data["injected_success_calls"], 0)
        self.assertEqual({x["outcome"] for x in data["categories"]},
                         {"local_resource_operation", "local_handle_not_found"})

    def test_04_capacity_is_local_to_filter_and_periodic_not_connect_or_write(self):
        good = [outcome(2, 1, shape=1, status=12), outcome(4, 4, status=12)]
        bad = [outcome(3, 2, status=12), outcome(2, 0, shape=1, status=12),
               outcome(4, 4, pins=0x060E, status=12), outcome(4, 4, baud=500000, status=12),
               outcome(5, 1, shape=0, status=12)]
        result = tool.audit([conn(5, 0, 500000, 12)] + good + bad)
        data = result["can_ps_api_outcomes"]
        self.assertEqual((data["capacity_errors"], data["calls"], data["invalid_events"]), (2, 2, len(bad)))
        self.assertEqual({x["status"] for x in data["categories"]}, {"exceeded_limit"})
        self.assertEqual({x["outcome"] for x in data["categories"]}, {"local_capacity_exhausted_no_transport"})
        self.assertNotIn("channel_limit", json.dumps(data))
        self.assertEqual(result["connect"]["statuses"], {"channel_limit": 1})

    def test_05_exact_words_enums_and_snapshot_combinations_fail_closed(self):
        good = outcome().strip()
        malformed = [good + " 00", good + " ZZ", good.rsplit(" ", 1)[0],
                     good.replace("00 00 00 01", "0x00 00 00 01", 1)]
        bad = [outcome(channel=0), outcome(mask=8), outcome(operation=0), outcome(operation=9),
               outcome(pins=0x0809), outcome(baud=250000), outcome(shape=99), outcome(status=9),
               outcome(1, pins=0x030B, shape=0), outcome(1, pins=0, baud=0, shape=0),
               outcome(1, pins=0, shape=1), outcome(1, pins=0, shape=0, status=1)]
        data = tool.audit(malformed + bad + [good.replace("1234ABCD", "not-a-pid")])[
            "can_ps_api_outcomes"]
        self.assertEqual((data["calls"], data["mode_snapshots"], data["invalid_events"]),
                         (0, 0, len(malformed) + len(bad)))
        self.assertEqual(data["source_order"], [])

    def test_06_source_order_is_self_contained_without_conflating_old_markers(self):
        lines = [conn(0x8004, 0x900, 125000, 0), outcome(1, 2, pins=0, shape=0), "ignored\n",
                 outcome(3, 1, status=1), probe(4, status=1), attempt(origin=2, shape=42),
                 periodic_event(interval=1000), outcome(3, 2, channel=2, pid="87654321")]
        result = tool.audit(lines)
        data = result["can_ps_api_outcomes"]
        self.assertEqual((data["mode_snapshots"], data["calls"], data["injected_success_calls"],
                          data["rejected_creation_calls"]), (1, 2, 1, 1))
        self.assertEqual([x["line"] for x in data["source_order"]], [2, 4, 8])
        self.assertEqual([x["mask"] for x in data["source_order"]], [2, 1, 2])
        self.assertEqual(result["connect"]["attempts"], 1)
        self.assertEqual(result["can_ps_config_probe"]["events"], 1)
        self.assertEqual(result["rejected_can_ps_attempts"]["calls"], 1)
        self.assertEqual(result["can_ps_rejected_setup"]["periodic_registration_calls"], 1)
        self.assertFalse(data["state_correlation_performed"])

    def test_07_privacy_bounds_and_exclusive_cli_output(self):
        private = "[PID=1234ABCD PrivateClient.exe] TX (app request) PRIVATE_VIN_PIN_OPERAND\n"
        data = tool.audit([private, outcome(), outcome(mask=0xDEADBEEF)])["can_ps_api_outcomes"]
        for secret in ("PrivateClient", "1234ABCD", "PRIVATE", "VIN", "OPERAND", "DEADBEEF", "3735928559", "channel"):
            self.assertNotIn(secret, json.dumps(data))
        self.assertNotIn("can_ps_api_outcomes", tool.audit([outcome().strip() + " " * tool.MAX_LINE]))
        with self.assertRaisesRegex(ValueError, "api_outcome_limit"):
            tool.audit(outcome() for _ in range(tool.MAX_API_OUTCOMES + 1))
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/"source.log", Path(folder)/"audit.json"
            source.write_text(outcome(), encoding="utf-8")
            tool.main([str(source), "--output", str(output)])
            original = output.read_bytes()
            with self.assertRaises(FileExistsError):
                tool.main([str(source), "--output", str(output)])
            self.assertEqual(output.read_bytes(), original)

    def test_08_old_scope_and_snapshot_are_not_simulated_transmission(self):
        old_lines = [conn(5, 0, 500000, 0), cfg(1, 1, 125000, 1), probe(4, status=1)]
        old = tool.audit(old_lines)
        self.assertNotIn("can_ps_api_outcomes", old)
        result = tool.audit(old_lines + [outcome(1, 7, pins=0, baud=500000, shape=0)])
        for key, value in old.items():
            self.assertEqual(result[key], value)
        data = result["can_ps_api_outcomes"]
        self.assertEqual((data["mode_snapshots"], data["calls"], data["injected_success_calls"]), (1, 0, 0))
        self.assertEqual(result["format"], "virtualcar-j2534-connect-audit-v1")
        self.assertFalse(result["vehicle_identity_verified"])
        self.assertFalse(data["can_transmission_verified"])
        self.assertFalse(data["ecu_response_verified"])


if __name__ == "__main__":
    unittest.main()
