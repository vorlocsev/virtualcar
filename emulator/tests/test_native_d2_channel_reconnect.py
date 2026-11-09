"""P0: native D2 generation tags must be scoped to a J2534 channel lifetime.

Synthetic emulator log records only. No actual SectorV, J2534 hardware or VIN.
"""
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "audit_j2534_discovery",
    Path(__file__).resolve().parents[1] / "tools" / "audit_j2534_discovery.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

PID = "DEADBEEF"
HEADS = (0x8F, 9, 10, 11, 12, 13, 14, 15, 8, 9, 10, 11, 0x4F)


def be(*words):
    return b"".join(int(word).to_bytes(4, "big") for word in words)


def line(title, value=b"", pid=PID):
    return (f"[PID={pid} SyntheticSectorV.exe] " + title
            + (" " + value.hex(" ").upper() if value else ""))


def rx(index, channel=1, generation=1, pid=PID):
    head = HEADS[index - 1]
    data = (bytes((head, 0x50, 0xF9, 0xFB, 0x57, 0, 0, 0))
            if index == 1 else bytes((head,)) + bytes(7))
    return [
        line("RX context channel/protocol/status/baud/time-us (BE)",
             be(channel, 5, 0, 500000, 100000), pid),
        line("PassThruReadMsgs -> delivered", be(0x01200003) + data, pid),
        line("P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE)",
             be(channel, generation, index, 101000, 102000), pid),
    ]


def frames(indices, channel=1, generation=1, pid=PID):
    out = []
    for index in indices:
        out.extend(rx(index, channel, generation, pid))
    return out


def disconnect(channel, pid=PID, raw=None):
    meta = be(channel) if raw is None else raw
    return [line("PassThruDisconnect channel (BE)", meta, pid),
            line("PassThruDisconnect", pid=pid)]


def counts(rows):
    return tool.audit(rows)["native_d2_delivery_tags"]


class NativeD2ChannelReuseTests(unittest.TestCase):
    def test_01_reused_channel_generation_one_cannot_complete_b9fb(self):
        rows = frames(range(1, 7))
        rows += disconnect(1) + [line("PassThruConnect protocol / flags / baud (BE)",
                                      be(5, 0, 500000))]
        rows += frames(range(7, 14))
        result = counts(rows)
        self.assertEqual((result["tag_records"], result["paired_tag_records"]),
                         (13, 13))
        self.assertEqual(result["generation_groups"], 2)
        self.assertEqual(result["b9fb_13frame_control_sequence_groups"], 0)
        self.assertEqual(result["groups_with_missing_duplicate_or_out_of_order_indices"], 1)

    def test_02_other_channel_disconnect_preserves_active_b9fb_generation(self):
        rows = frames(range(1, 7), channel=1)
        rows += disconnect(2)
        rows += frames(range(7, 14), channel=1)
        result = counts(rows)
        self.assertEqual(result["generation_groups"], 1)
        self.assertEqual(result["groups_with_frame_indices_1_to_n"], 1)
        self.assertEqual(result["b9fb_13frame_control_sequence_groups"], 1)

    def test_03_parallel_channels_only_selected_disconnect_splits(self):
        rows = frames(range(1, 7), channel=1)
        rows += frames(range(1, 7), channel=2)
        rows += disconnect(1)
        rows += frames(range(7, 14), channel=1)
        rows += frames(range(7, 14), channel=2)
        result = counts(rows)
        self.assertEqual(result["generation_groups"], 3)
        self.assertEqual(result["b9fb_13frame_control_sequence_groups"], 1)
        self.assertEqual(result["groups_with_missing_duplicate_or_out_of_order_indices"], 1)

    def test_04_disconnect_metadata_alone_prevents_false_complete_group(self):
        # The actual C emitter writes a second bare PassThruDisconnect,
        # but a lost final log line must not join two apparent sessions.
        rows = frames(range(1, 7))
        rows += [line("PassThruDisconnect channel (BE)", be(1))]
        rows += frames(range(7, 14))
        result = counts(rows)
        self.assertEqual(result["generation_groups"], 2)
        self.assertEqual(result["b9fb_13frame_control_sequence_groups"], 0)

    def test_05_malformed_channel_metadata_with_disconnect_splits_all(self):
        rows = frames(range(1, 7))
        rows += disconnect(1, raw=be(1) + bytes((0xAB,)))
        rows += frames(range(7, 14))
        result = counts(rows)
        self.assertEqual(result["generation_groups"], 2)
        self.assertEqual(result["b9fb_13frame_control_sequence_groups"], 0)

    def test_06_disconnect_without_channel_metadata_fails_closed(self):
        rows = frames(range(1, 7))
        rows += [line("PassThruDisconnect")]
        rows += frames(range(7, 14))
        result = counts(rows)
        self.assertEqual(result["generation_groups"], 2)
        self.assertEqual(result["b9fb_13frame_control_sequence_groups"], 0)
        self.assertFalse(result["replay_approved"])

    def test_07_other_pid_disconnect_cannot_split_the_active_channel(self):
        rows = frames(range(1, 7))
        rows += disconnect(1, pid="0BADF00D")
        rows += frames(range(7, 14))
        result = counts(rows)
        self.assertEqual(result["generation_groups"], 1)
        self.assertEqual(result["b9fb_13frame_control_sequence_groups"], 1)
        self.assertNotIn("0BADF00D", json.dumps(result))
        self.assertNotIn("DEADBEEF", json.dumps(result))

    def test_08_device_close_open_also_keeps_generation_groups_separate(self):
        rows = frames(range(1, 14))
        rows += [line("PassThruClose"), line("PassThruOpen -> device 1")]
        rows += frames(range(1, 14))
        result = counts(rows)
        self.assertEqual(result["tag_records"], 26)
        self.assertEqual(result["generation_groups"], 2)
        self.assertEqual(result["b9fb_13frame_control_sequence_groups"], 2)
        self.assertEqual(result["client_vin_and_ecu_acceptance"], "not_verified")
        self.assertFalse(result["replay_approved"])


if __name__ == "__main__":
    unittest.main()
