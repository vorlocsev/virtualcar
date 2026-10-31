"""Original synthetic-only tests for read-only SavvyCAN metadata importer."""
import importlib.util
from io import StringIO
import json
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "analyze_can_csv.py"
spec = importlib.util.spec_from_file_location("analyze_can_csv", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
HEADER = "Time Stamp,ID,Extended,Dir,Bus,LEN,D1,D2,D3,D4,D5,D6,D7,D8\n"


def row(timestamp, can_id="00613DF8", extended="true", bus=0, dlc=8, data=None):
    data = data or ["00"] * 8
    return f"{timestamp},{can_id},{extended},Rx,{bus},{dlc}," + ",".join(data) + "\n"


def report(rows, **kwargs):
    return mod.analyze(StringIO(HEADER + "".join(rows)),
                       source_model=kwargs.pop("source_model", "S60"),
                       source_model_year=kwargs.pop("source_model_year", 2002), **kwargs)


class SavvyCanTests(unittest.TestCase):
    def test_source_model_year_not_auto_relabelled(self):
        a = report([row(1000)])
        self.assertEqual(a["compatibility"], "source_vehicle_differs_from_target")
        self.assertFalse(a["replay_approved"])
        self.assertFalse(a["contains_payload_data"])

    def test_same_model_year_not_sufficient_to_approve(self):
        a = report([row(1000)], source_model="XC90 V8", source_model_year=2009)
        self.assertEqual(a["compatibility"], "identity_match_not_verified")
        self.assertFalse(a["replay_approved"])

    def test_classic_can_dlc_15_rejected(self):
        a = report([row(1000, dlc=15), row(2000)])
        self.assertEqual(a["errors"]["non_classic_can_length"], 1)
        self.assertEqual(a["valid_frames"], 1)
        self.assertEqual(a["discarded_rows"], 1)

    def test_29bit_and_11bit_are_independent(self):
        a = report([row(1000, "00000726", "false"), row(2000, "00000726", "true")])
        self.assertEqual(len(a["ids"]), 2)
        self.assertEqual({i["extended"] for i in a["ids"]}, {True, False})

    def test_standard_id_range_guard(self):
        a = report([row(1000, "00000FFF", "false"), row(2000, "1FFFFFFF", "true"),
                    row(3000, "20000000", "true")])
        self.assertEqual(a["valid_frames"], 1)
        self.assertEqual(a["errors"]["out_of_range_can_id"], 2)

    def test_missing_byte_and_malformed_header(self):
        a = report([row(1000, data=["GG"] + ["00"] * 7)])
        self.assertEqual(a["valid_frames"], 0)
        self.assertEqual(a["errors"]["malformed_payload_byte"], 1)
        with self.assertRaises(mod.CaptureError):
            mod.analyze(StringIO("ID,LEN\n7E0,8\n"), source_model="S60", source_model_year=2002)

    def test_periods_use_timestamp_microseconds(self):
        a = report([row(1000), row(11000), row(31000)])
        item = a["ids"][0]
        self.assertEqual(item["period_samples"], 2)
        self.assertEqual(item["mean_period_ms"], 15)
        self.assertEqual(item["min_period_ms"], 10)
        self.assertEqual(item["max_period_ms"], 20)

    def test_out_of_order_does_not_poison_periods(self):
        a = report([row(1000), row(11000), row(5000), row(21000)])
        self.assertEqual(a["valid_frames"], 3)
        self.assertEqual(a["errors"]["out_of_order_timestamp"], 1)
        self.assertEqual(a["ids"][0]["mean_period_ms"], 10)

    def test_bus_rates_are_declared_not_inferred(self):
        a = report([row(1000), row(2000, "00B00002", bus=1)],
                   bus_speeds={0: 125000, 1: 250000})
        self.assertEqual([b["configured_speed_bps"] for b in a["buses"]], [125000, 250000])
        self.assertNotIn(500000, [b["configured_speed_bps"] for b in a["buses"]])

    def test_activity_gaps_are_not_ignition_evidence(self):
        a = report([row(1000), row(7100000)], gap_threshold_ms=5000)
        self.assertEqual(a["buses"][0]["gaps_over_threshold"], 1)
        self.assertIn("No broadcast frame indicates", a["notes"][1])

    def test_no_payloads_or_vins_in_report(self):
        vin = b"YV1CZ0002A0000001"  # synthetic lab marker, never transmitted
        frames = [row(1000, data=[f"{b:02X}" for b in vin[:8]])]
        a = report(frames)
        s = json.dumps(a)
        self.assertNotIn(vin.decode(), s)
        self.assertNotIn("59", s)
        self.assertNotIn("56", s)

    def test_csv_header_with_bom_and_trailing_comma(self):
        s = StringIO("\ufeff" + HEADER + row(1000).rstrip() + ",\n")
        # BOM is stripped at opening by CLI using utf-8-sig; API expects a decoded header.
        with self.assertRaises(mod.CaptureError):
            mod.analyze(s, source_model="S60", source_model_year=2002)
        self.assertEqual(report([row(1000).rstrip() + ",\n"])["valid_frames"], 1)


if __name__ == "__main__":
    unittest.main()
