"""Eight regressions of first-later-A3 candidate against native channel log."""
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

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

chronology = load("p2_native_channel_chronology_first_pair",
                  "audit_native_p2_channel_chronology.py")
gate = load("p2_native_channel_first_a3_gate", "verify_native_p2_first_a3.py")
A3_40 = bytes.fromhex("CF 40 A3 02 03 A5 A5 00")
B9FB_40 = bytes.fromhex("CB 40 B9 FB 00 00 00 00")


def observed(lines):
    r = chronology.audit("\n".join(lines))
    assert r["epochs_with_events"] == 1
    return r["epochs"][0]


def native_sequence(gap_us=520):
    final = 1_032_000
    lines = tx(D2FB, at=1_000_000) + response(first=1_020_000)
    lines += tx(A3, at=final + gap_us)
    lines += tx(A3_40, channel=2, baud=125000, at=final + gap_us + 20_000)
    lines += tx(A3_40, at=final + gap_us + 40_000)
    lines += tx(B9FB_40, channel=2, baud=125000, at=final + gap_us + 60_000)
    lines += [marker("PassThruClose")]
    return lines


def timing(gap_us=520):
    return {
        "format": "virtualcar-native-d2-followup-gate-v1",
        "native_d2_followup_verified": True,
        "first_next_tx_service": "d2_a3_target_known",
        "first_next_tx_target": "0x50",
        "first_next_tx_same_target": True,
        "first_next_tx_same_channel": True,
        "b9fb_rx_frames": 13,
        "other_unanswered_b9fb_attempts": 1,
        "client_acceptance_verified": False,
        "last_rx_to_first_next_tx_ms": round(gap_us/1000, 3),
    }


class FirstLaterA3Tests(unittest.TestCase):
    def test_01_full_lab_session_keeps_overall_ambiguity_but_first_a3_is_observed(self):
        epoch = observed(native_sequence())
        candidate = epoch["first_completed_b9fb_to_later_a3"]
        self.assertEqual(epoch["outcome"], "multiple_candidates_no_unique_pairing")
        self.assertEqual((epoch["b9fb_requested"], epoch["b9fb_completed"],
                          epoch["a3_requested"]), (2, 1, 3))
        self.assertEqual(candidate["status"], "same_channel_target_timed")
        self.assertEqual(candidate["b9fb_completion_order"], 2)
        self.assertEqual(candidate["first_later_a3_order"], 3)
        self.assertEqual(candidate["last_b9fb_rx_to_first_later_a3_ms"], 0.52)
        self.assertTrue(candidate["same_channel_target_generation_verified"])
        self.assertFalse(candidate["client_acceptance_verified"])

    def test_02_a3_before_b9fb_is_not_post_b9fb_evidence(self):
        epoch = observed(tx(A3, at=900_000) + tx(D2FB)
                         + response(first=1_020_000))
        self.assertEqual(epoch["outcome"], "a3_before_b9fb_request")
        candidate = epoch["first_completed_b9fb_to_later_a3"]
        self.assertEqual(candidate["status"], "no_later_a3_observed")
        self.assertIsNone(candidate["first_later_a3_order"])
        self.assertFalse(candidate["same_channel_target_generation_verified"])

    def test_03_a3_during_rx_is_not_after_completed_b9fb(self):
        fragment = tx(D2FB) + response()
        lines = fragment[:16] + tx(A3, at=1_027_500) + fragment[16:]
        candidate = observed(lines)["first_completed_b9fb_to_later_a3"]
        self.assertEqual(candidate["status"], "no_later_a3_observed")
        self.assertIsNone(candidate["last_b9fb_rx_to_first_later_a3_ms"])

    def test_04_first_later_a3_different_channel_or_target_not_matched(self):
        first = tx(D2FB) + response()
        for other, expected in (
            (tx(A3, channel=2, at=1_132_000), "different_channel"),
            (tx(A3_40, at=1_132_000), "different_target"),
        ):
            with self.subTest(expected=expected):
                c = observed(first + other)["first_completed_b9fb_to_later_a3"]
                self.assertEqual(c["status"], expected)
                self.assertFalse(c["same_channel_target_generation_verified"])

    def test_05_disconnect_or_new_b9fb_blocks_old_pair(self):
        prefix = tx(D2FB) + response()
        disconnect = [marker("PassThruDisconnect channel (BE)", words(1)),
                      marker("PassThruDisconnect")]
        reused = observed(prefix + disconnect + tx(A3, at=1_232_000))
        c = reused["first_completed_b9fb_to_later_a3"]
        self.assertEqual(c["status"], "channel_reused_after_disconnect")
        self.assertFalse(c["same_channel_target_generation_verified"])
        second = observed(prefix + tx(B9FB_40, channel=2, baud=125000,
                                      at=1_100_000) + tx(A3, at=1_232_000))
        c = second["first_completed_b9fb_to_later_a3"]
        self.assertEqual(c["status"], "intervening_b9fb_request")
        self.assertFalse(c["same_channel_target_generation_verified"])

    def test_06_bad_context_or_unsigned_clock_gap_never_proves_pair(self):
        prefix = tx(D2FB) + response()
        invalid = [marker(chronology.TX_CONTEXT, words(1, 5, 0x100, 500000, 1_033_000)),
                   marker("TX (app request) MALFORMED")]
        c = observed(prefix + invalid + tx(A3, at=1_132_000))[
            "first_completed_b9fb_to_later_a3"]
        self.assertEqual(c["status"], "source_context_incomplete")
        self.assertFalse(c["same_channel_target_generation_verified"])
        far = observed(prefix + tx(A3, at=100_000_000))[
            "first_completed_b9fb_to_later_a3"]
        self.assertEqual(far["status"], "timestamp_unverified")
        self.assertIsNone(far["last_b9fb_rx_to_first_later_a3_ms"])

    def test_07_independent_native_summaries_agree_for_full_lab_case(self):
        original = chronology.audit("\n".join(native_sequence()))
        result = gate.verify(original, timing())
        self.assertTrue(result["synthetic_native_same_channel_first_a3_verified"])
        self.assertTrue(result["session_summary_still_ambiguous"])
        self.assertEqual(result["native_first_a3_gap_ms"], 0.52)
        self.assertFalse(result["sectorv_client_acceptance_verified"])
        self.assertFalse(result["a3_security_access_verified"])

    def test_08_disagreement_and_exclusive_output_fail_closed(self):
        original = chronology.audit("\n".join(native_sequence()))
        for change in ("gap", "order", "channel", "identity"):
            copied = json.loads(json.dumps(original))
            expected = dict(timing())
            if change == "gap":
                expected["last_rx_to_first_next_tx_ms"] = 1.52
            if change == "order":
                copied["epochs"][0]["first_completed_b9fb_to_later_a3"]["first_later_a3_order"] = 5
            if change == "channel":
                copied["epochs"][0]["events"][2]["channel"] = "ch2"
            if change == "identity":
                copied["client_b9fb_acceptance_verified"] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                gate.verify(copied, expected)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            a, b, output = (folder / x for x in ("chronology.json", "timing.json", "safe.json"))
            a.write_text(json.dumps(original), encoding="utf-8")
            b.write_text(json.dumps(timing()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gate.main([str(a), str(b), "--output", str(output)]), 0)
            body = output.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(gate.main([str(a), str(b), "--output", str(output)]), 2)
                self.assertEqual(gate.main([str(a), str(b), "--output", str(a)]), 2)
            self.assertEqual(body, output.read_bytes())
            self.assertNotIn(b"PRIVATE_CLIENT", body)


if __name__ == "__main__":
    unittest.main()
