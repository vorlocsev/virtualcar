"""Eight synthetic P0 tests for native J2534 TX context provenance.

No SectorV execution, real J2534 adapter, donor captures, or OEM identity.
"""
import importlib.util
import json
from pathlib import Path
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
spec = importlib.util.spec_from_file_location("audit_j2534_discovery",
                                              TOOLS / "audit_j2534_discovery.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

PID = "DEADBEEF"
B9FB = bytes.fromhex("CB 50 B9 FB 00 00 00 00")
B9F0 = bytes.fromhex("CB 50 B9 F0 00 00 00 00")
FIRST = bytes.fromhex("8F 50 F9 FB 57 00 30 66")


def be(*values):
    return b"".join(int(v).to_bytes(4, "big") for v in values)


def event(label, data=b"", pid=PID):
    return ("[PID=" + pid + " SyntheticClient.exe] " + label
            + (" " + data.hex(" ").upper() if data else ""))


def tx_context(channel=1, pid=PID):
    return event("TX context channel/protocol/flags/baud/time-us (BE)",
                 be(channel, 5, 0, 500000, 100000), pid)


def tx_record(payload=B9FB, pid=PID):
    return event("TX (app request)", be(0x000FFFFE) + payload, pid)


def request(channel=1, payload=B9FB, pid=PID):
    return [tx_context(channel, pid), tx_record(payload, pid)]


def rx_context(channel=1, pid=PID):
    return event("RX context channel/protocol/status/baud/time-us (BE)",
                 be(channel, 5, 0, 500000, 102000), pid)


def rx_record(data, pid=PID):
    return event("PassThruReadMsgs -> delivered", be(0x01200003) + data, pid)


def response13(channel=1, pid=PID):
    seq = (9, 10, 11, 12, 13, 14, 15, 8, 9, 10, 11, 0x4F)
    frames = (FIRST,) + tuple(bytes([h]) + bytes(7) for h in seq)
    out = []
    for frame in frames:
        out.extend((rx_context(channel, pid), rx_record(frame, pid)))
    return out


class NativeTxContextBoundaryTests(unittest.TestCase):
    def single(self, lines):
        report = tool.audit(lines)
        self.assertEqual(len(report["transactions"]), 1)
        return report["transactions"][0], report

    def test_01_valid_native_tx_and_13_scoped_rx_still_deliver(self):
        item, report = self.single(request() + response13())
        self.assertEqual((item["channel"], item["rx_frames"], item["status"]),
                         (1, 13, "delivered"))
        self.assertNotIn("native_tx_without_fresh_context", report["parse_errors"])
        self.assertFalse(report["replay_approved"])

    def test_02_unrelated_same_pid_event_invalidates_old_tx_context(self):
        report = tool.audit([tx_context(),
                             event("Unrelated native diagnostic event"),
                             tx_record()])
        self.assertEqual(report["transactions"], [])
        self.assertEqual(report["parse_errors"].get("interrupted_native_tx_context"), 1)
        self.assertEqual(report["parse_errors"].get("native_tx_without_fresh_context"), 1)

    def test_03_malformed_tx_context_cannot_fall_back_to_legacy(self):
        malformed = event("TX context channel/protocol/flags/baud/time-us (BE)",
                          be(1, 5, 0, 500000))  # Only four words, not five
        report = tool.audit([malformed, tx_record()])
        self.assertEqual(report["transactions"], [])
        self.assertEqual(report["parse_errors"].get("malformed_context"), 1)
        self.assertEqual(report["parse_errors"].get("native_tx_without_fresh_context"), 1)

    def test_04_second_orphaned_native_request_cannot_supersede_first(self):
        item, report = self.single(request(1) + [tx_record(B9F0)] + response13(1))
        self.assertEqual((item["service"], item["rx_frames"], item["status"]),
                         ("B9FB", 13, "delivered"))
        self.assertEqual(report["parse_errors"].get("native_tx_without_fresh_context"), 1)

    def test_05_new_valid_context_recovers_after_orphaned_request(self):
        lines = [tx_context(1), event("interruption"), tx_record(B9F0)]
        lines += request(2) + response13(2)
        item, report = self.single(lines)
        self.assertEqual((item["channel"], item["service"], item["status"]),
                         (2, "B9FB", "delivered"))
        self.assertEqual(report["parse_errors"].get("native_tx_without_fresh_context"), 1)

    def test_06_historical_unscoped_native_records_remain_supported(self):
        rows = [tx_record()]
        rows += [rx_record(row) for row in (FIRST,) +
                 tuple(bytes([h]) + bytes(7) for h in
                       (9, 10, 11, 12, 13, 14, 15, 8, 9, 10, 11, 0x4F))]
        item, report = self.single(rows)
        self.assertEqual((item["channel"], item["rx_frames"], item["status"]),
                         (None, 13, "delivered"))
        self.assertNotIn("native_tx_without_fresh_context", report["parse_errors"])

    def test_07_orphaned_tx_does_not_contaminate_parallel_channels(self):
        rows = request(1) + request(2, B9F0)
        rows += [tx_context(3), event("interruption"), tx_record(B9FB)]
        rows += response13(1)
        report = tool.audit(rows)
        self.assertEqual(len(report["transactions"]), 2)
        by_ch = {item["channel"]: item for item in report["transactions"]}
        self.assertEqual((by_ch[1]["status"], by_ch[1]["rx_frames"]),
                         ("delivered", 13))
        self.assertEqual((by_ch[2]["status"], by_ch[2]["service"]),
                         ("unverified", "B9F0"))
        self.assertEqual(report["parse_errors"].get("native_tx_without_fresh_context"), 1)

    def test_08_noncanonical_20_byte_context_and_pid_privacy(self):
        # A 20-byte payload followed by unrelated text is not a native record.
        fake = tx_context() + " PRIVATE_HOST_PATH"
        result = tool.audit([fake, tx_record()])
        self.assertEqual(result["transactions"], [])
        self.assertEqual(result["parse_errors"].get("malformed_context"), 1)
        self.assertEqual(result["parse_errors"].get("native_tx_without_fresh_context"), 1)

        # Another PID may interleave between this PID's valid context and TX.
        interleaved = [tx_context(),
                       event("YV1CZ0002A0000001", pid="0BADF00D"),
                       tx_record()] + response13()
        item, report = self.single(interleaved)
        self.assertEqual((item["channel"], item["status"]), (1, "delivered"))
        serialized = json.dumps(report)
        for secret in ("YV1CZ0002A0000001", "DEADBEEF",
                       "0BADF00D", "PRIVATE_HOST_PATH", "SyntheticClient"):
            self.assertNotIn(secret, serialized)
        self.assertFalse(report["replay_approved"])


if __name__ == "__main__":
    unittest.main()
