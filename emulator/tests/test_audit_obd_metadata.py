"""Eight synthetic groups for native Virtual Car ISO15765 RX metadata.

These records test the emitter's 4/0 and data-size/data-size forms, not every
adapter's J2534 interpretation or any historical VDASH/client acceptance.
"""
import json
import unittest

from test_audit_j2534_discovery import tool, event, be, tx, rx
from test_audit_obd_observation import FIXTURE, request, reply


MARKER = "PassThruReadMsgs ISO15765 protocol/status/size/extra-index/timestamp-us (BE)"


def metadata(protocol=6, status=0, size=24, extra=24, timestamp=90000, **kwargs):
    return event(MARKER, be(protocol, status, size, extra, timestamp), **kwargs)


def audit(lines):
    return tool.audit(lines, include_obd=True)


def counts(item):
    return item["iso15765_rx_metadata"]


class ObdMetadataTests(unittest.TestCase):
    def test_01_native_start_and_vin_metadata_are_checked_separately(self):
        result = audit(FIXTURE.read_text(encoding="utf-8").splitlines())
        vin, suppressed = result["transactions"]
        self.assertEqual((vin["status"], vin["start_indications"], vin["rx_frames"]),
                         ("delivered", 1, 1))
        self.assertEqual(counts(vin), {"checked_frames": 2, "missing_frames": 0, "invalid_frames": 0})
        self.assertEqual(counts(suppressed), {"checked_frames": 0, "missing_frames": 0, "invalid_frames": 0})
        self.assertEqual(result["parse_errors"], {})

    def test_02_conflicting_protocol_status_size_and_index_are_unverified(self):
        for changes in ({"protocol": 5}, {"status": 2}, {"size": 4, "extra": 0},
                        {"size": 23, "extra": 23}, {"extra": 0}, {"extra": 25}):
            with self.subTest(changes=changes):
                result = audit(request() + reply() + [metadata(**changes)])
                item = result["transactions"][0]
                self.assertEqual(item["status"], "unverified")
                self.assertEqual(item["reason"], "inconsistent_obd_iso15765_metadata")
                self.assertEqual(counts(item), {"checked_frames": 0, "missing_frames": 0, "invalid_frames": 1})
                self.assertEqual(result["parse_errors"], {"inconsistent_obd_iso15765_metadata": 1})
        # The ID-only start has its own shape, distinct from a payload message.
        result = audit(request() + reply(b"", flags=2) + [metadata(status=2, size=4, extra=4)])
        self.assertEqual(result["transactions"][0]["reason"], "inconsistent_obd_iso15765_metadata")

    def test_03_metadata_bytes_are_strict_and_cannot_silently_disappear(self):
        good = metadata()
        for damaged in (event(MARKER), event(MARKER, be(6, 0, 24, 24)),
                        good + " 00", good + " ZZ", good.replace(" 00 00 00 06", " 0x00 00 00 06", 1)):
            with self.subTest(damaged=damaged):
                result = audit(request() + reply() + [damaged])
                item = result["transactions"][0]
                self.assertEqual((item["status"], item["reason"]),
                                 ("unverified", "malformed_obd_iso15765_metadata"))
                self.assertEqual(counts(item), {"checked_frames": 0, "missing_frames": 0, "invalid_frames": 1})
                self.assertEqual(result["parse_errors"], {"malformed_obd_iso15765_metadata": 1})

    def test_04_missing_metadata_preserves_legacy_delivery_and_is_explicit(self):
        result = audit(request() + reply(b"", flags=2) + reply())
        item = result["transactions"][0]
        self.assertEqual(item["status"], "delivered")
        self.assertEqual(counts(item), {"checked_frames": 0, "missing_frames": 2, "invalid_frames": 0})
        self.assertEqual(result["parse_errors"], {})
        self.assertEqual(counts(audit(request())["transactions"][0]),
                         {"checked_frames": 0, "missing_frames": 0, "invalid_frames": 0})
        # A CAN reply is outside this ISO15765 metadata boundary.
        can = request(proto=5) + reply(b"\x10\x14\x49\x02\x01\x30\x30\x30", proto=5)
        self.assertEqual(counts(audit(can)["transactions"][0]),
                         {"checked_frames": 0, "missing_frames": 0, "invalid_frames": 0})

    def test_05_pid_channel_and_source_order_prevent_metadata_guessing(self):
        # A metadata suffix from another PID cannot bind to this delivery.
        result = audit(request() + reply() + [metadata(pid="01234567")])
        item = result["transactions"][0]
        self.assertEqual((item["status"], counts(item)["missing_frames"]), ("delivered", 1))
        self.assertEqual(result["parse_errors"], {"unbound_iso15765_metadata": 1})
        # Once any physical line intervenes, later metadata stays unbound.
        for intervening in (event("Unrelated note"), event("Unrelated note", pid="01234567"), ""):
            result = audit(request() + reply() + [intervening, metadata()])
            self.assertEqual(counts(result["transactions"][0])["missing_frames"], 1)
            self.assertEqual(result["parse_errors"], {"unbound_iso15765_metadata": 1})
        # Metadata has no channel field: only the immediately preceding RX binds.
        result = audit(request(ch=1) + request(ch=2) + reply(ch=1)
                       + [metadata(extra=0)] + reply(ch=2) + [metadata()])
        channels = {item["channel"]: item for item in result["transactions"]}
        self.assertEqual(channels[1]["status"], "unverified")
        self.assertEqual(channels[2]["status"], "delivered")
        self.assertEqual(counts(channels[2])["checked_frames"], 1)
        duplicate = audit(request() + reply() + [metadata(), metadata()])
        self.assertEqual(counts(duplicate["transactions"][0])["checked_frames"], 1)
        self.assertEqual(duplicate["parse_errors"], {"unbound_iso15765_metadata": 1})
        orphan = audit([metadata()])
        self.assertEqual(orphan["transactions"], [])
        self.assertEqual(orphan["parse_errors"], {"unbound_iso15765_metadata": 1})

    def test_06_lifecycle_and_eof_do_not_rebind_metadata(self):
        boundaries = ([event("CLEAR_RX context channel/protocol/flags/baud/time-us (BE)",
                             be(1, 6, 0, 500000, 110000)),
                       event("J2534 CLEAR_RX_BUFFER: queued and staged D2 dropped")],
                      [event("PassThruDisconnect channel (BE)", be(1)), event("PassThruDisconnect")],
                      [event("PassThruOpen -> device 1")], [event("PassThruClose")])
        for boundary in boundaries:
            with self.subTest(boundary=boundary[-1]):
                result = audit(request() + reply() + boundary + [metadata()])
                self.assertEqual(counts(result["transactions"][0]),
                                 {"checked_frames": 0, "missing_frames": 1, "invalid_frames": 0})
                self.assertEqual(result["parse_errors"], {"unbound_iso15765_metadata": 1})
                checked = audit(request() + reply() + [metadata()] + boundary)
                self.assertEqual(counts(checked["transactions"][0])["checked_frames"], 1)
        # EOF closes a pending binding and records absence once, not as an error.
        end = audit(request() + reply())
        self.assertEqual(counts(end["transactions"][0])["missing_frames"], 1)
        self.assertEqual(end["parse_errors"], {})

    def test_07_queue_timestamp_is_not_compared_with_delivery_time(self):
        for timestamp in (0, 90000, 0xFFFFFFFF):
            with self.subTest(timestamp=timestamp):
                result = audit(request(time_us=0xFFFFFF00) + reply(time_us=1000)
                               + [metadata(timestamp=timestamp)])
                self.assertEqual(result["transactions"][0]["status"], "delivered")
                self.assertEqual(counts(result["transactions"][0])["checked_frames"], 1)
                self.assertEqual(result["parse_errors"], {})

    def test_08_privacy_and_default_report_remain_compatible(self):
        lines = FIXTURE.read_text(encoding="utf-8").splitlines()
        report = audit(lines)
        rendered = json.dumps(report)
        for private in ("DEADBEEF", "SyntheticVDASH", "00000000000000000", "30 30 30", "C:\\Private"):
            self.assertNotIn(private, rendered)
        self.assertFalse(report["replay_approved"])
        self.assertFalse(report["obd_observation"]["vehicle_identity_verified"])
        self.assertEqual(report["obd_observation"]["client_result"], "client_result_unknown")
        without = [line for line in lines if MARKER not in line]
        self.assertEqual(tool.audit(lines), tool.audit(without))
        self.assertNotIn("iso15765_rx_metadata", json.dumps(tool.audit(lines)))
        # P3 default transport remains unaffected even by contradictory suffixes.
        p3 = tx(0x726, bytes.fromhex("22 F1 14"), ch=1, proto=6)
        p3 += rx(0x72E, bytes.fromhex("62 F1 14 00"), ch=1, proto=6)
        self.assertEqual(tool.audit(p3), tool.audit(p3 + [metadata(size=4, extra=0)]))


if __name__ == "__main__":
    unittest.main()
