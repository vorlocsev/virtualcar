"""Eight synthetic regressions for one-process x86 D2/UDS handoff gate.

CI also exercises the same gate on a compiled Windows x86 J2534 DLL.
The in-memory fixtures below are deliberately synthetic and not Volvo OEM.
"""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import verify_native_p2_p3_handoff as tool
from test_audit_d2_followup_window import D2FB, marker, response, tx, rx, words
from test_native_b9f0_response import F0, NEG, f0_response
from test_native_b9f0_first_p3_response import p3_rx

LAB = bytes.fromhex("62 F1 14") + b"VCARLAB0000000000"


def p3_tx(*, channel=2, protocol=6, at=1_202_000):
    """The real x86 lab's F114 request, not the unrelated F190 test helper."""
    if protocol != 6:
        raise ValueError("lab_uses_iso15765_only")
    return [
        marker("TX context channel/protocol/flags/baud/time-us (BE)",
               words(channel, protocol, 0, 500000, at)),
        marker("TX (app request)",
               (0x726).to_bytes(4, "big") + bytes.fromhex("22 F1 14")),
    ]


def parts():
    return (
        tx(D2FB, at=1_000_000) + response(first=1_020_000),
        tx(F0, at=1_132_000) + f0_response(start=1_142_000),
        p3_tx(channel=2, protocol=6, at=1_202_000)
        + p3_rx(LAB, channel=2, protocol=6,
                at=1_222_000),
    )


def sample(*, b9fb=True, b9f0=True, p3=True):
    chunks = parts()
    lines = []
    if b9fb:
        lines += chunks[0]
    if b9f0:
        lines += chunks[1]
    if p3:
        lines += chunks[2]
    lines += [marker("PassThruClose")]
    return "\n".join(lines)


class NativeP2P3SingleRunGateTests(unittest.TestCase):
    def test_01_complete_read_only_synthetic_transport_passes(self):
        result = tool.verify(sample())
        self.assertTrue(result["single_closed_native_epoch_verified"])
        self.assertTrue(result["direct_b9fb_to_b9f0_request_verified"])
        self.assertTrue(result["first_p3_did_positive_transport_verified"])
        self.assertFalse(result["client_acceptance_verified"])
        self.assertFalse(result["real_xc90_v8_my2009_verified"])
        self.assertFalse(result["physical_j2534_verified"])

    def test_02_missing_b9fb_cannot_infer_complete_sequence(self):
        with self.assertRaisesRegex(ValueError, "unexpected_b9fb_b9f0"):
            tool.verify(sample(b9fb=False))

    def test_03_no_b9f0_is_not_p3_handoff(self):
        with self.assertRaisesRegex(ValueError, "unexpected_b9fb_b9f0"):
            tool.verify(sample(b9f0=False))

    def test_04_negative_b9f0_does_not_pass(self):
        base, _, later = parts()
        negative = tx(F0, at=1_132_000)
        negative += rx(NEG, at=1_142_000)
        source = "\n".join(base + negative + later
                           + [marker("PassThruClose")])
        with self.assertRaisesRegex(ValueError, "native_b9f0_p3_transport_chain"):
            tool.verify(source)

    def test_05_missing_p3_rx_does_not_infer_ecu_found(self):
        lines = parts()[0] + parts()[1] + p3_tx(
            channel=2, protocol=6, at=1_202_000)
        lines += [marker("PassThruClose")]
        with self.assertRaisesRegex(ValueError, "native_b9f0_p3_transport_chain"):
            tool.verify("\n".join(lines))

    def test_06_foreign_route_or_mismatched_did_is_not_positive(self):
        prefix = parts()[0] + parts()[1]
        request = p3_tx(channel=2, protocol=6, at=1_202_000)
        for reply in (
            p3_rx(LAB, channel=2, can=0x72F, protocol=6, at=1_222_000),
            p3_rx(bytes.fromhex("62 F1 87 55"), channel=2,
                  protocol=6, at=1_222_000),
        ):
            with self.subTest(reply=reply[0]):
                lines = prefix + request + reply + [marker("PassThruClose")]
                with self.assertRaisesRegex(ValueError,
                                            "native_b9f0_p3_transport_chain"):
                    tool.verify("\n".join(lines))

    def test_07_new_pid_or_unclosed_epoch_cannot_join_rx(self):
        base = parts()[0] + parts()[1]
        p3 = p3_tx(channel=2, protocol=6, at=1_202_000)
        alien = p3_rx(LAB, channel=2, protocol=6, at=1_222_000,
                      pid="FEEDBEEF")
        lines = base + p3 + alien + [marker("PassThruClose")]
        with self.assertRaisesRegex(ValueError, "native_b9f0_p3_transport_chain"):
            tool.verify("\n".join(lines))
        without_close = "\n".join(base + p3
                                  + p3_rx(LAB, channel=2, protocol=6))
        with self.assertRaisesRegex(ValueError, "native_process_epoch_incomplete"):
            tool.verify(without_close)

    def test_08_privacy_cli_no_overwrite_and_preserve_private_source(self):
        private = "PRIVATE_ACTUAL_CUSTOMER_VIN_AND_HOST"
        source = sample() + "\n" + private
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw, out = root / "private.log", root / "safe.json"
            raw.write_text(source, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main([str(raw), "--output", str(out)]), 0)
            exported = out.read_text(encoding="utf-8")
            for hidden in (private, "ABCDEF12", "PRIVATE_CLIENT",
                           "F1 14", "VCARLAB0000000000", str(raw)):
                self.assertNotIn(hidden, exported)
            self.assertTrue(json.loads(exported)["read_only"])
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main([str(raw), "--output", str(out)]), 2)
                self.assertEqual(tool.main([str(raw), "--output", str(raw)]), 2)
            self.assertEqual(raw.read_text(encoding="utf-8"), source)


if __name__ == "__main__":
    unittest.main()
