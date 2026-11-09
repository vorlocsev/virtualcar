"""Synthetic acceptance tests for bounded P0 D2 generation evidence.

The input is locally generated text, never private SectorV captures.
These checks do not load J2534, send CAN, or authenticate an OEM VIN.
"""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_sectorv_fresh_window as fresh
import audit_sectorv_operator_session as collector
import audit_sectorv_ui_window_triage as triage

HEADS = (0x8F, 9, 10, 11, 12, 13, 14, 15, 8, 9, 10, 11, 0x4F)


def be(*words):
    return b"".join(int(word).to_bytes(4, "big") for word in words)


def event(label, raw=b""):
    return ("[PID=DEADBEEF SyntheticClient.exe] " + label
            + (" " + raw.hex(" ").upper() if raw else "") + "\n")


def lines13(*, generation=1, count=13, frame_numbers=None):
    out = [
        event("TX context channel/protocol/flags/baud/time-us (BE)",
              be(1, 5, 0, 500000, 100000)),
        event("TX (app request)",
              be(0x000FFFFE) + bytes.fromhex("CB 50 B9 FB 00 00 00 00")),
    ]
    indices = list(range(1, count + 1)) if frame_numbers is None else frame_numbers
    for index in indices:
        header = HEADS[index - 1]
        payload = (bytes.fromhex("8F 50 F9 FB 57 00 30 66")
                   if index == 1 else bytes((header,)) + bytes(7))
        out.extend((
            event("RX context channel/protocol/status/baud/time-us (BE)",
                  be(1, 5, 0, 500000, 101000 + index * 1000)),
            event("PassThruReadMsgs -> delivered",
                  be(0x01200003) + payload),
            event("P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE)",
                  be(1, generation, index, 101000 + index * 1000,
                     102000 + index * 1000)),
        ))
    return out


def window(jlines=None, blines=None):
    jlines = [] if jlines is None else jlines
    blines = [] if blines is None else blines
    result = fresh.summarize(jlines, blines, operator_one_run=False)
    result["windows"] = {
        "j2534": {
            "new_bytes": len("".join(jlines).encode("utf-8")),
            "complete_lines": len(jlines),
            "dropped_first": False, "dropped_last": False,
            "source_present": True, "prefix_verified": False,
        },
        "backend": {
            "new_bytes": len("".join(blines).encode("utf-8")),
            "complete_lines": len(blines),
            "dropped_first": False, "dropped_last": False,
            "source_present": True, "prefix_verified": False,
        },
    }
    result["registered_provider"] = {
        "baseline_category": "runner_not_windows",
        "postrun_category": "runner_not_windows",
        "binary_endpoint_consistency": "not_verified",
        "loaded_in_sectorv_client": "not_observed",
        "during_run_immutability": "not_verified",
        "same_guest_independently_attested": False,
    }
    return result


def gui():
    return {
        "schema_version": "virtualcar-sectorv-ui-observation-v1",
        "client": "SectorV",
        "scenario": "P2_MY2009_lab",
        "source": "human_ui_observation",
        "run_scope": "single_vm_client_run",
        "read_only": True,
        "physical_adapter_disconnected": True,
        "observations": {
            "adapter_listed": "yes", "adapter_selected": "yes",
            "connection": "connected", "ecu_list": "empty",
            "vehicle_identity": "not_displayed",
            "error_category": "vin_read_failed",
        },
    }


class BoundedNativeGenerationTests(unittest.TestCase):
    def test_01_thirteen_frames_are_visible_in_bounded_report_not_gui_proof(self):
        report = window(lines13())
        tags = report["discovery"]["native_d2_delivery_tags"]
        self.assertEqual((tags["tag_records"], tags["generation_groups"],
                          tags["b9fb_13frame_control_sequence_groups"]),
                         (13, 1, 1))
        self.assertEqual(report["discovery"]["d2"]["0x50"]["B9FB"]["requests"], 1)
        self.assertEqual(tags["client_vin_and_ecu_acceptance"], "not_verified")
        result = triage.triage(report, gui())
        self.assertEqual(result["native_d2_generation_evidence"]["paired_tag_records"], 13)
        self.assertEqual(result["native_d2_generation_evidence"]
                         ["b9fb_13frame_control_sequence_groups"], 1)
        self.assertEqual(result["first_next_gate"], "establish_isolated_same_run_evidence")
        self.assertFalse(result["oem_vin_and_ecu_verified"])

    def test_02_partial_or_reordered_frames_cannot_represent_complete_group(self):
        for indices in (list(range(2, 14)), [1, 2, 2]):
            with self.subTest(indices=indices):
                data = window(lines13(frame_numbers=indices))
                result = triage.triage(data, gui())
                self.assertEqual(
                    result["native_d2_generation_evidence"]
                    ["discontinuous_generation_groups"], 1)
                self.assertEqual(
                    result["native_d2_generation_evidence"]
                    ["b9fb_13frame_control_sequence_groups"], 0)

    def test_03_existing_v2_window_without_generation_tags_stays_compatible(self):
        report = window(lines13())
        del report["discovery"]["native_d2_delivery_tags"]
        result = triage.triage(report, gui())
        self.assertNotIn("native_d2_generation_evidence", result)
        self.assertEqual(result["client_vehicle_identity_accepted"], "not_verified")

    def test_04_reject_unknown_tag_fields_or_exported_raw_identifiers(self):
        for key, value in (("VIN", "YV1CZ0002A0000001"),
                           ("channel", 1),
                           ("pid", "DEADBEEF")):
            with self.subTest(key=key):
                report = window(lines13())
                report["discovery"]["native_d2_delivery_tags"][key] = value
                with self.assertRaises(ValueError):
                    triage.triage(report, gui())
        report = window()
        report["discovery"]["native_d2_delivery_tags"] = []
        with self.assertRaises(ValueError):
            triage.triage(report, gui())

    def test_05_unsafe_provenance_claims_rejected_in_old_or_new_gui(self):
        for key, value in (("client_vin_and_ecu_acceptance", "verified"),
                           ("physical_can_or_ecu_provenance", "verified"),
                           ("replay_approved", True),
                           ("observed", 1),
                           ("source", "private_can_log")):
            with self.subTest(key=key):
                report = window(lines13())
                report["discovery"]["native_d2_delivery_tags"][key] = value
                with self.assertRaises(ValueError):
                    triage.triage(report, gui())

    def test_06_reject_inconsistent_counts_even_when_report_is_redacted(self):
        for key, value in (("tag_records", 14),
                           ("paired_tag_records", 12),
                           ("unpaired_tag_records", 1),
                           ("generation_groups", 2),
                           ("groups_with_frame_indices_1_to_n", 2),
                           ("groups_with_missing_duplicate_or_out_of_order_indices", 1),
                           ("b9fb_13frame_control_sequence_groups", 2)):
            with self.subTest(key=key):
                report = window(lines13())
                report["discovery"]["native_d2_delivery_tags"][key] = value
                with self.assertRaises(ValueError):
                    triage.triage(report, gui())
        report = window(lines13())
        report["windows"]["j2534"]["complete_lines"] = 12
        with self.assertRaises(ValueError):
            triage.triage(report, gui())

    def test_07_only_newly_appended_lines_may_enter_generation_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "private.log"
            old = lines13(generation=22)
            source.write_text("".join(old), encoding="utf-8")
            baseline = fresh._snapshot(source)
            new = lines13(generation=23, count=2)
            with source.open("a", encoding="utf-8") as handle:
                handle.write("".join(new))
            appended, meta = fresh._append_lines(source, baseline)
            self.assertEqual(len(appended), len(new))
            self.assertTrue(meta["prefix_verified"])
            report = window(appended)
            tags = report["discovery"]["native_d2_delivery_tags"]
            self.assertEqual(tags["tag_records"], 2)
            self.assertEqual(tags["generation_groups"], 1)
            self.assertEqual(tags["b9fb_13frame_control_sequence_groups"], 0)
            self.assertNotIn("22", json.dumps(tags))
            self.assertFalse(report["replay_approved"])

    def test_08_operator_begin_finish_exports_only_bounded_redacted_categories(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            j = root / "private-j2534.log"
            b = root / "private-backend.jsonl"
            j.write_text("".join(lines13(generation=77)), encoding="utf-8")
            b.write_bytes(b"")
            session = root / "p0-session-01"
            opts = ["--session-dir", str(session), "--j2534", str(j),
                    "--backend", str(b)]
            unavailable = {"state": "runner_not_windows", "path_sha256": None,
                           "file_sha256": None, "bytes": None}
            with mock.patch.object(collector.fresh, "_provider_snapshot",
                                   return_value=unavailable):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(collector.main(["begin", *opts]), 0)
                with j.open("a", encoding="utf-8") as handle:
                    handle.write("".join(lines13(generation=78)))
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(collector.main([
                        "finish", *opts, "--isolated-read-only-vm",
                        "--physical-adapter-disconnected",
                        "--adapter-listed", "yes", "--adapter-selected", "yes",
                        "--connection", "connected", "--ecu-list", "empty",
                        "--vehicle-identity", "not_displayed",
                        "--error-category", "vin_read_failed",
                    ]), 0)
            win = json.loads((session / collector.WINDOW_REPORT).read_text())
            result = json.loads((session / collector.TRIAGE_REPORT).read_text())
            self.assertEqual(win["discovery"]["native_d2_delivery_tags"]
                             ["b9fb_13frame_control_sequence_groups"], 1)
            self.assertEqual(result["native_d2_generation_evidence"]
                             ["b9fb_13frame_control_sequence_groups"], 1)
            self.assertFalse(result["oem_vin_and_ecu_verified"])
            for file in (collector.WINDOW_REPORT, collector.TRIAGE_REPORT):
                text = (session / file).read_text()
                for secret in ("DEADBEEF", "SyntheticClient", str(root),
                               "YV1CZ0002A0000001", "77", "78", "01 20 00 03"):
                    self.assertNotIn(secret, text)


if __name__ == "__main__":
    unittest.main()
