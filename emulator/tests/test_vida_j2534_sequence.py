"""Synthetic-only correctness and negative evidence gates for B3A297."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import vida_j2534_sequence as mod


def row(session, request, *, can_id=None, service=None, target=None,
        protocol="ISO15765", baud=500000, bits="29bit", status="unverified", rx=0):
    return {"session": session, "request": request, "can_id": can_id,
            "service": service, "target": target, "protocol": protocol,
            "baud_bps": baud, "id_format": bits, "status": status,
            "rx_dequeued": rx}


def source(*rows):
    return {"format": mod.INPUT_FORMAT, "contains_payload_data": False,
            "client_acceptance_verified": False, "identity_verified": False,
            "transactions": list(rows)}


def vin(n=1, session=1):
    return row(session, n, can_id="0x726", service="22F114", bits="11bit")


def target(n=2, session=1, name="ECM", rx=0):
    inv = {v: k for k, v in mod.TARGETS.items()}
    return row(session, n, can_id=inv[name], service=None,
               target=f"{name}_REQUEST_ONLY", rx=rx)


class SequenceTests(unittest.TestCase):
    def test_01_valid_order_no_gui_claim(self):
        out = mod.analyze(source(vin(), target(), target(3, name="TCM")))
        self.assertEqual(out["vin_shaped_tx_total"], 1)
        self.assertEqual(out["ecu_target_tx_after_vin_shaped_tx_total"], 2)
        self.assertFalse(out["client_vin_accepted"])
        self.assertEqual(out["sessions"][0]["t111"], "not_tested")

    def test_02_missing_vin_cannot_infer_progress(self):
        out = mod.analyze(source(target()))
        self.assertEqual(out["ecu_target_tx_after_vin_shaped_tx_total"], 0)
        self.assertEqual(out["sessions"][0]["pre_anchor_or_unanchored_ecu_target_requests"], 1)

    def test_03_before_vin_remains_pre_anchor(self):
        out = mod.analyze(source(target(1), vin(2), target(3)))
        self.assertEqual(out["sessions"][0]["pre_anchor_or_unanchored_ecu_target_requests"], 1)
        self.assertEqual(out["sessions"][0]["post_anchor_ecu_target_requests"], 1)

    def test_04_sessions_never_cross_match(self):
        out = mod.analyze(source(vin(1, 1), target(2, 2)))
        self.assertEqual(out["ecu_target_tx_after_vin_shaped_tx_total"], 0)

    def test_05_exact_d2_anchor_only(self):
        d2 = row(1, 1, can_id="0x000FFFFE", service="B9FB", target="0x40",
                 protocol="CAN", baud=125000, bits="29bit")
        self.assertEqual(mod.analyze(source(d2, target()))["ecu_target_tx_after_vin_shaped_tx_total"], 1)
        d2["baud_bps"] = 500000
        self.assertEqual(mod.analyze(source(d2, target()))["ecu_target_tx_after_vin_shaped_tx_total"], 0)

    def test_06_wrong_29bit_route_or_protocol(self):
        bad = target()
        bad["protocol"] = "CAN"
        self.assertEqual(mod.analyze(source(vin(), bad))["ecu_target_tx_after_vin_shaped_tx_total"], 0)
        bad["protocol"] = "ISO15765"
        bad["target"] = "ECM"
        self.assertEqual(mod.analyze(source(vin(), bad))["ecu_target_tx_after_vin_shaped_tx_total"], 0)

    def test_07_rx_frames_not_client_acceptance(self):
        out = mod.analyze(source(vin(), target(rx=9)))
        self.assertEqual(out["sessions"][0]["targets_after_vin_shaped_tx"][0]["j2534_rx_dequeued_frames"], 9)
        self.assertFalse(out["ecu_identity_verified"])

    def test_08_reject_forged_flags_duplicate_ordinals_and_bool(self):
        for bad in (dict(source(vin()), client_acceptance_verified=True),
                    source(vin(), target(1)),
                    source(vin(1), row(2, True)),
                    dict(source(), contains_payload_data=True)):
            with self.subTest(bad=repr(bad)[:30]), self.assertRaises(mod.SequenceError):
                mod.analyze(bad)

    def test_09_unknown_data_and_private_fields_not_exported(self):
        a = target()
        a["VIN"] = "PRIVATE_DATA_MUST_STAY_LOCAL"
        out = mod.analyze(source(vin(), a))
        self.assertNotIn("PRIVATE_DATA_MUST_STAY_LOCAL", json.dumps(out))

    def test_10_cli_exclusive_output_bad_json_and_no_path_echo(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "input.json"
            o = Path(temp) / "out.json"
            p.write_text(json.dumps(source(vin(), target())), encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(mod.main(["--audit-report", str(p), "--output", str(o)]), 0)
                self.assertEqual(mod.main(["--audit-report", str(p), "--output", str(o)]), 2)
            self.assertEqual(json.loads(o.read_text(encoding="utf-8"))["format"], mod.OUTPUT_FORMAT)
            self.assertNotIn(str(p), err.getvalue())
            p.write_text('{"x":1,"x":2}', encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(mod.main(["--audit-report", str(p), "--output", str(p)]), 2)


if __name__ == "__main__":
    unittest.main()
