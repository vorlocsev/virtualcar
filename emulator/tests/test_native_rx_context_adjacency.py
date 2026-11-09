"""Fail-closed native J2534 RX-context attribution regression tests.

Only synthetic text logs, no running SectorV, J2534, raw captures or vehicle ID.
The current C DLL writes RX context directly before each delivered record.
"""
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "audit_j2534_discovery", HERE / "tools" / "audit_j2534_discovery.py")
audit_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_tool)

PID = "DEADBEEF"
D2FB = bytes.fromhex("CB 50 B9 FB 00 00 00 00")
FIRST = bytes.fromhex("8F 50 F9 FB 57 00 30 66")
RXID = 0x01200003


def line(label, payload=b"", pid=PID):
    return (f"[PID={pid} SyntheticClient.exe] " + label
            + ((" " + payload.hex(" ").upper()) if payload else ""))


def be(*words):
    return b"".join(int(word).to_bytes(4, "big") for word in words)


def request(channel=1, pid=PID):
    return [
        line("TX context channel/protocol/flags/baud/time-us (BE)",
             be(channel, 5, 0, 500000, 100000), pid),
        line("TX (app request)", be(0x000FFFFE) + D2FB, pid),
    ]


def context(channel=1, pid=PID):
    return line("RX context channel/protocol/status/baud/time-us (BE)",
                be(channel, 5, 0, 500000, 102000), pid)


def delivered(frame=FIRST, pid=PID):
    return line("PassThruReadMsgs -> delivered", be(RXID) + frame, pid)


def response13(channel=1, pid=PID):
    heads = [9, 10, 11, 12, 13, 14, 15, 8, 9, 10, 11, 0x4F]
    data = [FIRST] + [bytes([h]) + b"\x00" * 7 for h in heads]
    result = []
    for frame in data:
        result += [context(channel, pid), delivered(frame, pid)]
    return result


class NativeRxContextBoundaryTests(unittest.TestCase):
    def one(self, rows):
        result = audit_tool.audit(rows)
        self.assertEqual(len(result["transactions"]), 1)
        return result["transactions"][0], result

    def test_01_current_context_on_all_13_frames_still_delivers_transport(self):
        tx, report = self.one(request() + response13())
        self.assertEqual((tx["status"], tx["rx_frames"], tx["channel"]),
                         ("delivered", 13, 1))
        self.assertNotIn("native_rx_without_fresh_context", report["parse_errors"])
        self.assertFalse(report["replay_approved"])

    def test_02_intervening_same_pid_line_revokes_native_rx_context(self):
        tx, report = self.one(request() + [
            context(), line("Unrelated read-only logger marker"), delivered()])
        self.assertEqual((tx["status"], tx["rx_frames"]), ("unverified", 0))
        self.assertEqual(report["parse_errors"]["interrupted_native_rx_context"], 1)
        self.assertEqual(report["parse_errors"]["native_rx_without_fresh_context"], 1)

    def test_03_malformed_native_context_cannot_demote_to_legacy_rx(self):
        tx, report = self.one(request() + [
            line("RX context channel/protocol/status/baud/time-us (BE)",
                 b"\x00\x01"), delivered()])
        self.assertEqual(tx["rx_frames"], 0)
        self.assertEqual(tx["status"], "unverified")
        self.assertEqual(report["parse_errors"]["malformed_context"], 1)
        self.assertEqual(report["parse_errors"]["native_rx_without_fresh_context"], 1)

    def test_04_native_context_must_not_be_reused_for_second_frame(self):
        tx, report = self.one(request() + [
            context(), delivered(),
            delivered(bytes.fromhex("09 00 00 00 00 00 00 00"))])
        self.assertEqual((tx["status"], tx["rx_frames"]), ("partial_rx", 1))
        self.assertEqual(report["parse_errors"]["native_rx_without_fresh_context"], 1)

    def test_05_fresh_context_restores_full_delivery_after_orphan(self):
        all_rx = response13()
        rows = request() + all_rx[:2] + [line("Interruption"), delivered()] + all_rx[2:]
        tx, report = self.one(rows)
        self.assertEqual((tx["status"], tx["rx_frames"]), ("delivered", 13))
        self.assertEqual(report["parse_errors"]["native_rx_without_fresh_context"], 1)

    def test_06_legacy_unscoped_rx_without_any_native_context_is_preserved(self):
        all_rx = [row for row in response13()
                  if "PassThruReadMsgs -> delivered" in row]
        tx, report = self.one([line("TX (app request)", be(0x000FFFFE) + D2FB)]
                              + all_rx)
        self.assertEqual((tx["status"], tx["rx_frames"], tx["channel"]),
                         ("delivered", 13, None))
        self.assertNotIn("native_rx_without_fresh_context", report["parse_errors"])

    def test_07_stale_context_cannot_poison_parallel_channel(self):
        rows = request(1) + request(2) + [
            context(1), line("Interruption"), delivered()] + response13(2)
        result = audit_tool.audit(rows)
        self.assertEqual(len(result["transactions"]), 2)
        by_channel = {tx["channel"]: tx for tx in result["transactions"]}
        self.assertEqual((by_channel[1]["status"], by_channel[1]["rx_frames"]),
                         ("unverified", 0))
        self.assertEqual((by_channel[2]["status"], by_channel[2]["rx_frames"]),
                         ("delivered", 13))
        self.assertEqual(result["parse_errors"]["native_rx_without_fresh_context"], 1)

    def test_08_other_pid_interleaving_preserves_pid_scope_and_privacy(self):
        vin = b"YV1CZ0002A0000001"  # Synthetic secret-like marker, not a donor VIN.
        rows = request() + [context(),
                            line("Unrelated " + vin.decode(), pid="0BADF00D"),
                            delivered()]
        tx, report = self.one(rows)
        self.assertEqual((tx["status"], tx["rx_frames"]), ("partial_rx", 1))
        raw = json.dumps(report)
        self.assertNotIn(vin.decode(), raw)
        self.assertNotIn("SyntheticClient", raw)
        self.assertNotIn(PID, raw)
        self.assertFalse(report["replay_approved"])


if __name__ == "__main__":
    unittest.main()
