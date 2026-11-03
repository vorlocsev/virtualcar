"""Eight groups for closed-catalog rejected A6 metadata, never ECU evidence."""
import json
from pathlib import Path
import tempfile
import unittest

from test_audit_j2534_connect import tool, be, conn
from test_can_ps_rejected_attempts import attempt


def selector_event(channel=1, origin=1, pins=0x030B, baud=125000, protocol=0x8004,
                   target=0x40, selector=1, mask=4, status=1, *, pid="1234ABCD"):
    return (f"[PID={pid} PrivateClient.exe] {tool.PS_A6_SELECTOR} "
            f"{be(channel, origin, pins, baud, protocol, target, selector, mask, status)}\n")


class CanPsA6SelectorTests(unittest.TestCase):
    def test_01_closed_catalog_unknown_and_existing_api_counts(self):
        lines = [selector_event(selector=i) for i in tool.A6_SELECTORS]
        result = tool.audit([conn(0x8004, 0, 125000, 0), attempt(shape=11)] + lines)
        data = result["can_ps_a6_selectors"]
        self.assertEqual((data["events"], data["invalid_events"]), (4, 0))
        self.assertEqual({x["selector"] for x in data["categories"]},
                         {"1A02", "1A04", "D0D1", "other_redacted"})
        self.assertEqual(result["connect"]["attempts"], 1)
        self.assertEqual(result["rejected_can_ps_attempts"]["calls"], 1)
        self.assertFalse(data["counts_are_additional_api_calls"])

    def test_02_origin_protocol_route_baud_and_mask_are_independent(self):
        lines = [selector_event(origin=origin, protocol=protocol, pins=pins,
                                baud=baud, target=target, mask=mask)
                 for origin in (1, 2) for protocol in (5, 0x8004)
                 for pins in (0, 0x030B, 0x060E) for baud in (0, 125000, 500000)
                 for target in (0x40, 0x50) for mask in range(8)]
        data = tool.audit(lines)["can_ps_a6_selectors"]
        self.assertEqual((data["events"], data["invalid_events"]), (len(lines), 0))
        self.assertEqual({x["target"] for x in data["categories"]}, {"0x40", "0x50"})
        self.assertEqual({x["message_protocol"] for x in data["categories"]}, {"CAN", "CAN_PS"})
        self.assertEqual({x["origin"] for x in data["categories"]},
                         {"write_call", "periodic_registration_call"})

    def test_03_every_word_rejects_values_outside_contract(self):
        bad = [selector_event(channel=0), selector_event(origin=0), selector_event(origin=3),
               selector_event(pins=0xDEAD), selector_event(baud=250000),
               selector_event(protocol=0), selector_event(protocol=6),
               selector_event(target=0), selector_event(target=0x7A),
               selector_event(selector=4), selector_event(selector=0x1A02),
               selector_event(mask=8), selector_event(mask=0xFFFFFFFF),
               selector_event(status=0), selector_event(status=22)]
        data = tool.audit(bad)["can_ps_a6_selectors"]
        self.assertEqual((data["events"], data["invalid_events"]), (0, len(bad)))
        self.assertEqual(data["categories"], [])
        self.assertEqual(data["source_order"], [])

    def test_04_exact_36_byte_record_without_coercion(self):
        line = selector_event().strip()
        bad = [line + " 00", line.rsplit(" ", 1)[0], line + " ZZ",
               line.replace("00 00 00 01", "0x00 00 00 01", 1),
               line.replace(tool.PS_A6_SELECTOR, tool.PS_A6_SELECTOR + " extra")]
        data = tool.audit(bad + [line])["can_ps_a6_selectors"]
        self.assertEqual((data["events"], data["invalid_events"]), (1, len(bad)))
        self.assertEqual(data["source_order"][0]["line"], len(bad) + 1)

    def test_05_source_order_does_not_join_channel_or_process_state(self):
        lines = [selector_event(), "unrelated\n", selector_event(origin=2, channel=2),
                 selector_event(channel=1, pid="87654321"), selector_event(pins=0)]
        data = tool.audit(lines)["can_ps_a6_selectors"]
        self.assertEqual([x["line"] for x in data["source_order"]], [1, 3, 4, 5])
        self.assertEqual(sorted(x["count"] for x in data["categories"]), [1, 1, 2])
        self.assertFalse(data["state_correlation_performed"])
        rendered = json.dumps(data)
        for text in ("channel", "1234ABCD", "87654321", "PrivateClient"):
            self.assertNotIn(text, rendered)

    def test_06_no_payload_or_selector_semantics_are_exported(self):
        secret = "[PID=1234ABCD PrivateClient.exe] TX (app request) PRIVATE_VIN_PIN_OPERAND\n"
        data = tool.audit([secret, selector_event(selector=3), selector_event(selector=0)])[
            "can_ps_a6_selectors"]
        self.assertEqual(data["outcome"], "rejected_not_transmitted")
        for key in ("hardware_pins_verified", "can_transmission_verified", "ecu_response_verified",
                    "read_only_reference_approved", "periodic_firing_observed", "selector_semantics_verified"):
            self.assertFalse(data[key])
        rendered = json.dumps(data)
        for text in ("PRIVATE", "VIN", "PIN", "OPERAND", "PrivateClient", "030B", "32772", "53201"):
            self.assertNotIn(text, rendered)

    def test_07_legacy_logs_never_invent_a_selector(self):
        lines = [conn(0x8004, 0, 125000, 0), attempt(shape=11)]
        baseline = tool.audit(lines)
        self.assertNotIn("can_ps_a6_selectors", baseline)
        # A valid-looking record under another marker or invalid PID is ignored.
        ignored = [selector_event().replace(tool.PS_A6_SELECTOR, "A6 selector"),
                   selector_event(pid="not-a-pid"),
                   selector_event().strip() + " " * tool.MAX_LINE]
        self.assertEqual(tool.audit(lines + ignored), baseline)

    def test_08_bounded_source_order_and_exclusive_cli_output(self):
        with self.assertRaisesRegex(ValueError, "a6_selector_limit"):
            tool.audit(selector_event() for _ in range(tool.MAX_A6_SELECTORS + 1))
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "source.log", Path(folder) / "audit.json"
            source.write_text(selector_event(selector=2), encoding="utf-8")
            tool.main([str(source), "--output", str(output)])
            original = output.read_bytes()
            self.assertEqual(json.loads(original)["can_ps_a6_selectors"]["events"], 1)
            with self.assertRaises(FileExistsError):
                tool.main([str(source), "--output", str(output)])
            self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
