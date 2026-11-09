"""Synthetic P0 tests for native D2 generation metadata, NOT GUI VIN acceptance."""
import importlib.util
import json
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "tools" / "audit_j2534_discovery.py"
spec = importlib.util.spec_from_file_location("audit_j2534_discovery", MODULE)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

PID = "DEADBEEF"
HEADS = (0x8F, 9, 10, 11, 12, 13, 14, 15, 8, 9, 10, 11, 0x4F)


def be(*words):
    return b"".join(int(value).to_bytes(4, "big") for value in words)


def event(title, data=b"", pid=PID):
    return (f"[PID={pid} PrivateDiagnosticClient.exe] " + title
            + ((" " + data.hex(" ").upper()) if data else ""))


def context(channel=1, pid=PID, protocol=5, status=0):
    return event("RX context channel/protocol/status/baud/time-us (BE)",
                 be(channel, protocol, status, 500000, 102000), pid)


def delivery(data, pid=PID):
    return event("PassThruReadMsgs -> delivered",
                 be(0x01200003) + data, pid)


def tag(channel=1, generation=1, frame=1, pid=PID):
    return event("P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE)",
                 be(channel, generation, frame, 102000, 104000), pid)


def frame(index, target=0x50):
    head = HEADS[index - 1]
    if index == 1:
        return bytes((head, target, 0xF9, 0xFB, 0x57, 0, 0, 0))
    return bytes((head,)) + bytes(7)


def group(indices=range(1, 14), channel=1, generation=1, pid=PID,
          target=0x50):
    out = []
    for index in indices:
        out += [context(channel, pid), delivery(frame(index, target), pid),
                tag(channel, generation, index, pid)]
    return out


def summary(rows):
    return tool.audit(rows)["native_d2_delivery_tags"]


class NativeD2DeliveryGenerationTests(unittest.TestCase):
    def test_01_valid_13frame_b9fb_tag_sequence_is_only_transport_evidence(self):
        output = summary(group())
        self.assertEqual((output["tag_records"], output["paired_tag_records"],
                          output["generation_groups"]), (13, 13, 1))
        self.assertEqual(output["groups_with_frame_indices_1_to_n"], 1)
        self.assertEqual(output["b9fb_13frame_control_sequence_groups"], 1)
        self.assertEqual(output["client_vin_and_ecu_acceptance"], "not_verified")
        self.assertEqual(output["physical_can_or_ecu_provenance"], "not_verified")
        self.assertFalse(output["replay_approved"])

    def test_02_missing_initial_frame_never_looks_contiguous(self):
        output = summary(group(range(2, 14)))
        self.assertEqual(output["paired_tag_records"], 12)
        self.assertEqual(output["groups_with_missing_duplicate_or_out_of_order_indices"], 1)
        self.assertEqual(output["b9fb_13frame_control_sequence_groups"], 0)

    def test_03_duplicate_and_reordered_frame_numbers_cannot_complete(self):
        for indices in ((1, 2, 2), (1, 3, 2), (1, 3, 4)):
            with self.subTest(indices=indices):
                output = summary(group(indices))
                self.assertEqual(output["generation_groups"], 1)
                self.assertEqual(
                    output["groups_with_missing_duplicate_or_out_of_order_indices"], 1)

    def test_04_malformed_and_unpaired_native_tags_are_not_assigned(self):
        invalid = event(
            "P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE)",
            be(1, 1, 1))
        rows = [context(), delivery(frame(1)), invalid, tag()]
        output = summary(rows)
        self.assertEqual(output["tag_records"], 2)
        self.assertEqual(output["malformed_tag_records"], 1)
        self.assertEqual(output["unpaired_tag_records"], 1)
        self.assertEqual(output["paired_tag_records"], 0)

    def test_05_channel_mismatch_bad_status_or_non_can_is_rejected(self):
        cases = (
            [context(), delivery(frame(1)), tag(channel=2)],
            [context(status=0x08), delivery(frame(1)), tag()],
            [context(protocol=6), delivery(frame(1)), tag()],
            [context(), delivery(frame(1)[:-1]), tag()],
            [context(), delivery(frame(1)), tag(generation=0)],
            [context(), delivery(frame(1)), tag(frame=65)],
        )
        for rows in cases:
            with self.subTest(case=rows[0][-30:]):
                output = summary(rows)
                self.assertEqual(output["paired_tag_records"], 0)
                self.assertEqual(output["generation_groups"], 0)
                self.assertEqual(
                    output["unpaired_tag_records"] +
                    output["route_or_metadata_mismatch"], 1)

    def test_06_other_pid_does_not_interrupt_but_same_pid_does(self):
        other = event("Private VIN YV1CZ0002A0000001", pid="0BADF00D")
        good = summary([context(), delivery(frame(1)), other, tag()])
        self.assertEqual(good["paired_tag_records"], 1)
        broken = summary([context(), delivery(frame(1)),
                          event("same PID unrelated"), tag()])
        self.assertEqual(broken["paired_tag_records"], 0)
        self.assertEqual(broken["unpaired_tag_records"], 1)

    def test_07_generation_channel_and_open_sessions_do_not_merge(self):
        rows = group((1, 2), channel=1, generation=1)
        rows += group((1, 2), channel=1, generation=2)
        rows += group((1, 2), channel=2, generation=1)
        rows += [event("PassThruOpen -> device 1")]
        rows += group((1, 2), channel=1, generation=1)
        output = summary(rows)
        self.assertEqual(output["tag_records"], 8)
        self.assertEqual(output["generation_groups"], 4)
        self.assertEqual(output["groups_with_frame_indices_1_to_n"], 4)
        self.assertEqual(output["b9fb_13frame_control_sequence_groups"], 0)

    def test_08_no_tags_or_private_payload_is_never_exported_as_identity(self):
        private = b"YV1CZ0002A0000001"
        secret_frame = bytes((9,)) + private[:7]
        rows = [context(), delivery(frame(1)), tag(),
                context(), delivery(secret_frame), tag(frame=2)]
        result = tool.audit(rows)
        raw = json.dumps(result)
        for secret in ("DEADBEEF", "PrivateDiagnosticClient", "0BADF00D",
                       "YV1CZ0002A0000001", "59 56 31"):
            self.assertNotIn(secret, raw)
        self.assertFalse(result["replay_approved"])
        self.assertEqual(
            result["native_d2_delivery_tags"]["client_vin_and_ecu_acceptance"],
            "not_verified")
        old = summary([delivery(frame(1))])
        self.assertFalse(old["observed"])
        self.assertEqual(old["generation_groups"], 0)


if __name__ == "__main__":
    unittest.main()
