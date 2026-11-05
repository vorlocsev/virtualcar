"""Eight offline channel-aware chronology regression groups for native P2."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from test_audit_d2_followup_window import A3, D2FB, marker, response, tx, words

spec = importlib.util.spec_from_file_location(
    "audit_native_p2_channel_chronology",
    ROOT / "tools" / "audit_native_p2_channel_chronology.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def read(lines):
    return tool.audit("\n".join(lines))


def single(result):
    assert result["epochs_with_events"] == 1
    return result["epochs"][0]


class NativeP2ChannelChronologyTests(unittest.TestCase):
    def test_01_a3_before_b9fb_on_different_native_channel(self):
        lines = (tx(A3, channel=1, at=1_000_000)
                 + tx(D2FB, channel=2, at=1_200_000)
                 + response(channel=2, first=1_220_000))
        report = read(lines)
        epoch = single(report)
        self.assertEqual(epoch["outcome"], "a3_before_b9fb_request")
        self.assertEqual([x["kind"] for x in epoch["events"]],
                         ["a3_tx", "b9fb_tx", "b9fb_rx_complete"])
        self.assertEqual([x["channel"] for x in epoch["events"]],
                         ["ch1", "ch2", "ch2"])
        self.assertEqual(epoch["b9fb_completed"], 1)
        self.assertFalse(epoch["same_channel_proven_for_observed_order"])
        self.assertFalse(report["client_b9fb_acceptance_verified"])

    def test_02_b9fb_then_a3_same_channel_target_has_native_gap(self):
        lines = tx(D2FB, at=1_000_000) + response(first=1_020_000)
        lines += tx(A3, at=1_532_000)
        result = read(lines)
        epoch = single(result)
        self.assertEqual(epoch["outcome"], "a3_after_b9fb_same_channel_and_target")
        self.assertTrue(epoch["same_channel_proven_for_observed_order"])
        self.assertEqual(epoch["last_rx_to_a3_ms"], 500)
        self.assertEqual(epoch["events"][0]["channel"], "ch1")
        self.assertEqual(epoch["events"][-1]["channel"], "ch1")
        self.assertFalse(epoch["a3_security_access_verified"])

    def test_03_a3_during_b9fb_delivery_not_post_complete(self):
        pre = tx(D2FB, at=1_000_000) + response(first=1_020_000)
        # Inject A3 between two delivered RX frames and preserve original
        # source-order metadata. The complete B9FB must be logged last.
        first_half = pre[:2 + 14]
        last_half = pre[2 + 14:]
        lines = first_half + tx(A3, at=1_027_500) + last_half
        epoch = single(read(lines))
        self.assertEqual(epoch["outcome"], "a3_during_b9fb_delivery")
        self.assertEqual(epoch["b9fb_completed"], 1)
        self.assertIsNone(epoch["last_rx_to_a3_ms"])
        self.assertFalse(epoch["same_channel_proven_for_observed_order"])

    def test_04_later_a3_different_channel_or_target_has_no_validated_pair(self):
        lines = tx(D2FB) + response()
        other_channel = read(lines + tx(A3, channel=2, at=1_332_000))
        epoch = single(other_channel)
        self.assertEqual(epoch["outcome"], "a3_after_b9fb_different_channel")
        self.assertFalse(epoch["same_channel_proven_for_observed_order"])
        target40 = bytes.fromhex("CF 40 A3 02 03 A5 A5 00")
        other_target = read(lines + tx(target40, at=1_332_000))
        epoch = single(other_target)
        self.assertEqual(epoch["outcome"], "a3_after_b9fb_different_target")
        self.assertFalse(epoch["same_channel_proven_for_observed_order"])

    def test_05_reused_channel_after_disconnect_not_same_connection(self):
        disconnect = [
            marker("PassThruDisconnect channel (BE)", words(1)),
            marker("PassThruDisconnect"),
        ]
        lines = tx(D2FB) + response() + disconnect + tx(A3, at=1_332_000)
        epoch = single(read(lines))
        self.assertEqual(epoch["outcome"],
                         "a3_after_b9fb_channel_reused_after_disconnect")
        self.assertFalse(epoch["same_channel_proven_for_observed_order"])
        self.assertNotIn("PID", json.dumps(epoch))
        # A different PID cannot be paired with the first PID's B9FB.
        other_pid = tx(D2FB) + response() + tx(A3, pid="DEADBEEF", at=1_332_000)
        result = read(other_pid)
        self.assertEqual(result["epochs_with_events"], 2)
        self.assertEqual(result["outcome_counts"]["no_a3_observed"], 1)
        self.assertEqual(result["outcome_counts"]["no_completed_b9fb_observed"], 1)

    def test_06_malformed_rx_indication_and_incomplete_d2_do_not_complete(self):
        lines = tx(D2FB) + response(include_final=False) + tx(A3, at=1_332_000)
        a = single(read(lines))
        self.assertEqual(a["outcome"], "no_completed_b9fb_observed")
        self.assertEqual(a["b9fb_incomplete"], 1)
        off_route = tx(D2FB) + response(can=0x01200004)
        result = read(off_route)
        self.assertEqual(single(result)["b9fb_completed"], 0)
        self.assertEqual(result["parse_events"]["unrelated_rx_on_b9fb_channel"], 13)
        # An RX marked TX_INDICATION must never complete a B9FB.
        bad = []
        for item in response():
            if "RX context" in item:
                # Reproduce actual words with RxStatus=0x108.
                bad.append(marker(tool.RX_CONTEXT, words(1, 5, 0x108, 500000, 1_020_000)))
            else:
                bad.append(item)
        result = read(tx(D2FB) + bad)
        self.assertEqual(single(result)["b9fb_completed"], 0)
        self.assertEqual(result["parse_events"]["rx_indication_not_ecu_frame"], 13)

    def test_07_no_raw_pid_vin_or_payload_in_report_and_malformed_tx_fails_closed(self):
        secret = "SECRET_VIN_OR_PRIVATE_PATH_DO_NOT_COPY"
        base = tx(D2FB) + response() + tx(A3, at=1_332_000)
        data = read(base + [secret])
        report = json.dumps(data)
        for blocked in ("ABCDEF12", "PRIVATE_CLIENT", "CB 50 B9",
                        secret, "01200003", "F9 FB 57"):
            self.assertNotIn(blocked, report)
        self.assertFalse(data["a3_security_access_verified"])
        bad = tx(D2FB) + response()
        bad += [marker("TX context channel/protocol/flags/baud/time-us (BE)", words(1, 5, 0x100, 500000, 1_300_000)),
                marker("TX (app request) NOT_A_VALID_J2534_CAN_FRAME")]
        result = read(bad)
        self.assertFalse(single(result)["channel_metadata_complete"])
        self.assertEqual(result["parse_events"]["unattributed_or_bad_tx"], 1)

    def test_08_new_epoch_and_exclusive_cli_output(self):
        lines = tx(A3, at=1_000_000)
        lines += [marker("PassThruClose")]
        lines += tx(D2FB, at=1_200_000) + response(first=1_220_000)
        result = read(lines)
        self.assertEqual(result["epochs_with_events"], 2)
        self.assertEqual(result["outcome_counts"],
                         {"no_a3_observed": 1, "no_completed_b9fb_observed": 1})
        with tempfile.TemporaryDirectory() as d:
            source, target = Path(d)/"trace.log", Path(d)/"audit.json"
            source.write_text("\n".join(tx(D2FB) + response()
                                        + tx(A3, at=1_532_000)), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main([str(source), "--output", str(target)]), 0)
            saved = target.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main([str(source), "--output", str(target)]), 2)
                self.assertEqual(tool.main([str(source), "--output", str(source)]), 2)
            self.assertEqual(saved, target.read_bytes())
            self.assertTrue(json.loads(saved)["tx_channel_binding_from_native_context"])


if __name__ == "__main__":
    unittest.main()
