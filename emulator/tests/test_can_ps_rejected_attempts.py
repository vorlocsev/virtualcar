"""Eight synthetic groups: rejected calls are never accepted TX or ECU evidence."""
import json
from pathlib import Path
import tempfile
import unittest

from test_audit_j2534_connect import tool, be, conn
from test_can_ps_config_probe import probe


def attempt(origin=1, pins=0x030B, protocol=0x8004, shape=13, check=0,
            status=1, channel=1, pid="1234ABCD"):
    return (f"[PID={pid} PrivateClient.exe] {tool.PS_REJECTED} "
            f"{be(channel, origin, pins, protocol, shape, check, status)}\n")


class CanPsRejectedAttemptTests(unittest.TestCase):
    def test_01_catalog_counts_calls_separately_from_connect_and_probe(self):
        lines = [conn(0x8004, 0x900, 125000, 0), probe(4, status=1)]
        lines += [attempt(shape=shape) for shape in tool.ATTEMPT_SHAPES]
        result = tool.audit(lines)
        data = result["rejected_can_ps_attempts"]
        self.assertEqual(data["calls"], len(tool.ATTEMPT_SHAPES))
        self.assertEqual(data["invalid_events"], 0)
        self.assertEqual(result["connect"]["attempts"], 1)
        self.assertEqual(result["can_ps_config_probe"]["events"], 1)
        self.assertEqual({x["shape"] for x in data["categories"]}, set(tool.ATTEMPT_SHAPES.values()))
        for flag in ("read_only_reference_approved", "ecu_response_verified", "hardware_pins_verified"):
            self.assertFalse(data[flag])

    def test_02_protocol_pin_and_api_origin_are_distinct(self):
        lines = [attempt(protocol=5, pins=0), attempt(origin=2, pins=0x060E),
                 attempt(protocol=6, shape=0, check=3), attempt(protocol=0, shape=0, check=3)]
        data = tool.audit(lines)["rejected_can_ps_attempts"]
        self.assertEqual(data["calls"], 4)
        self.assertEqual({x["message_protocol"] for x in data["categories"]},
                         {"CAN", "CAN_PS", "ISO15765", "uninspected_or_other"})
        self.assertEqual({x["origin"] for x in data["categories"]},
                         {"write_call", "periodic_registration_call"})
        self.assertFalse(data["periodic_firing_observed"])

    def test_03_uninspected_zero_batch_and_invalid_envelopes_are_not_shapes(self):
        lines = [attempt(shape=0, check=check) for check in (1, 2, 4)]
        lines += [attempt(shape=0, check=check, protocol=0) for check in (5, 6)]
        data = tool.audit(lines)["rejected_can_ps_attempts"]
        self.assertEqual((data["calls"], data["invalid_events"]), (5, 0))
        self.assertEqual({x["shape"] for x in data["categories"]}, {"unknown"})
        self.assertEqual(len({x["inspection"] for x in data["categories"]}), 5)

    def test_04_impossible_combinations_are_rejected(self):
        bad = [attempt(channel=0), attempt(origin=3), attempt(pins=0x0809),
               attempt(protocol=99), attempt(shape=5), attempt(check=7), attempt(status=0)]
        bad += [attempt(shape=13, check=i, protocol=0 if i in (3, 5, 6) else 5)
                for i in range(1, 7)]
        bad += [attempt(protocol=6), attempt(protocol=0), attempt(protocol=5, check=3, shape=0),
                attempt(protocol=5, check=5, shape=0),
                attempt(protocol=0, check=6, shape=0, origin=2)]
        data = tool.audit(bad)["rejected_can_ps_attempts"]
        self.assertEqual((data["calls"], data["invalid_events"]), (0, len(bad)))

    def test_05_exact_28_byte_marker_no_coercion_or_legacy_reinterpretation(self):
        good = attempt().strip()
        malformed = [good + " 00", good.rsplit(" ", 1)[0], good + " ZZ",
                     good.replace("00 00 00 01", "0x00 00 00 01", 1),
                     good.replace(be(1, 1, 0x030B, 0x8004, 13, 0, 1), be(1, 4, 0, 1))]
        result = tool.audit(malformed + [good.replace("1234ABCD", "not-a-pid")])
        self.assertEqual(result["rejected_can_ps_attempts"]["invalid_events"], len(malformed))
        self.assertEqual(result["rejected_can_ps_attempts"]["calls"], 0)
        self.assertEqual(result["connect"]["attempts"], 0)
        self.assertNotIn("can_ps_config_probe", result)

    def test_06_source_order_does_not_join_reused_channels_or_processes(self):
        data = tool.audit([attempt(), "unrelated\n", attempt(origin=2, channel=2),
                           attempt(channel=1, pid="87654321"), attempt(pins=0x060E)])[
                               "rejected_can_ps_attempts"]
        self.assertEqual([x["line"] for x in data["source_order"]], [1, 3, 4, 5])
        self.assertEqual(sorted(x["count"] for x in data["categories"]), [1, 1, 2])
        self.assertFalse(data["state_correlation_performed"])
        rendered = json.dumps(data)
        for text in ("channel", "1234ABCD", "87654321", "PrivateClient"):
            self.assertNotIn(text, rendered)

    def test_07_exclusions_unknown_and_raw_data_never_become_read_evidence(self):
        secret = "[PID=1234ABCD PrivateClient.exe] TX (app request) PRIVATE_VIN_PIN_OPERAND\n"
        data = tool.audit([secret] + [attempt(shape=i) for i in (0, 40, 41, 42)])[
            "rejected_can_ps_attempts"]
        self.assertEqual(data["outcome"], "rejected_not_transmitted")
        self.assertEqual(data["classification_scope"], "lexical_request_shape_only")
        self.assertFalse(data["read_only_reference_approved"])
        rendered = json.dumps(data)
        for text in ("PRIVATE", "VIN", "PIN", "OPERAND", "PrivateClient", "030B", "32772"):
            self.assertNotIn(text, rendered)

    def test_08_old_scope_exclusive_output_and_bounded_source_order(self):
        self.assertNotIn("rejected_can_ps_attempts", tool.audit([probe(4, status=1)]))
        self.assertNotIn("rejected_can_ps_attempts", tool.audit([attempt().strip()+" "*tool.MAX_LINE]))
        with self.assertRaisesRegex(ValueError, "rejected_attempt_limit"):
            tool.audit(attempt() for _ in range(tool.MAX_REJECTED_ATTEMPTS+1))
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/"source.log", Path(folder)/"audit.json"
            source.write_text(attempt(), encoding="utf-8")
            tool.main([str(source), "--output", str(output)])
            original = output.read_bytes()
            with self.assertRaises(FileExistsError):
                tool.main([str(source), "--output", str(output)])
            self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
