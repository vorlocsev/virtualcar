"""P0: only bounded Virtual Car J2534 connect/config categories, no OEM proof.

All source lines are synthetic. Neither SectorV GUI nor physical adapter runs.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import audit_sectorv_fresh_window as fresh
import audit_sectorv_ui_window_triage as triage
from test_audit_sectorv_ui_window_triage import window, ui

PID = "DEADBEEF"
CONNECT = "J2534 Connect result protocol/flags/baud/status (BE)"
CONFIG = "J2534 SET_CONFIG channel/parameter/value/applied (BE)"


def be(*words):
    return b"".join(int(w).to_bytes(4, "big") for w in words)


def log(label, raw, pid=PID):
    return (f"[PID={pid} PrivateSectorVTest.exe] {label} "
            + raw.hex(" ").upper() + "\n")


def connect(protocol=5, flags=0, baud=500000, status=0, pid=PID):
    return log(CONNECT, be(protocol, flags, baud, status), pid=pid)


def config(parameter=1, value=125000, applied=1):
    return log(CONFIG, be(1, parameter, value, applied))


def bounded(lines):
    discovered = fresh.summarize(lines, [], operator_one_run=True)
    report = window()
    report["connect"] = copy.deepcopy(discovered["connect"])
    report["windows"]["j2534"].update({
        "new_bytes": max(32, sum(len(line.encode("utf-8")) for line in lines)),
        "complete_lines": len(lines),
    })
    return report


def triaged(lines):
    return triage.triage(bounded(lines), ui(), operator_pair_confirmed=True)


class P0ConnectModeEvidenceTests(unittest.TestCase):
    def test_01_canonical_can_500k_connect_is_transport_only(self):
        item = triaged([connect()])
        modes = item["j2534_connect_mode_evidence"]
        self.assertEqual(modes["connect_modes"], [{
            "protocol": "CAN", "flags": "none",
            "baud_bps": "500000", "status": "ok", "count": 1,
        }])
        self.assertEqual(modes["set_config_events"], 0)
        self.assertEqual(modes["origin"],
                         "virtualcar_local_bounded_metadata_only")
        self.assertFalse(modes["sectorv_connection_or_ecu_verified"])
        self.assertFalse(item["oem_vin_and_ecu_verified"])

    def test_02_vendor_modes_and_volvo_flag_retain_distinct_errors(self):
        item = triaged([
            connect(0x8004, 0, 125000, 3),
            connect(6, 0x20000000, 125000, 0),
            connect(0x10000001, 0x600, 500000, 3),
        ])
        modes = item["j2534_connect_mode_evidence"]["connect_modes"]
        self.assertEqual(len(modes), 3)
        self.assertEqual({v["protocol"] for v in modes},
                         {"CAN_PS", "ISO15765", "CAN_XON_XOFF"})
        self.assertEqual({v["status"] for v in modes},
                         {"ok", "invalid_protocol"})
        self.assertIn("VOLVO_CH2", {v["flags"] for v in modes})
        self.assertEqual(item["client_vehicle_identity_accepted"], "not_verified")

    def test_03_set_config_applied_vs_accepted_no_effect_stays_categorical(self):
        item = triaged([
            connect(), config(1, 125000, 1),
            config(779, 0x030B, 0), config(779, 0xFADECAFE, 1),
        ])
        evidence = item["j2534_connect_mode_evidence"]
        self.assertEqual(evidence["set_config_events"], 2)
        self.assertEqual(evidence["invalid_set_config_events"], 1)
        self.assertEqual(
            {(entry["parameter"], entry["handling"])
             for entry in evidence["set_config_parameters"]},
            {("DATA_RATE", "applied_baud"),
             ("J1962_PINS", "accepted_no_effect")})
        raw = json.dumps(item, ensure_ascii=False)
        self.assertNotIn("FADECAFE", raw)
        self.assertNotIn("030B", raw)

    def test_04_historical_window_without_mode_evidence_remains_supported(self):
        old = window()
        old["connect"] = {"attempts": 0, "statuses": {}}
        result = triage.triage(old, ui(), operator_pair_confirmed=True)
        self.assertNotIn("j2534_connect_mode_evidence", result)
        self.assertEqual(result["client_vehicle_identity_accepted"], "not_verified")

    def test_05_reject_private_identifiers_or_unallowlisted_metadata(self):
        for field, value in (
            ("protocol", "C:/PRIVATE/VIN/YV1CZ0002A0000001"),
            ("flags", "SECRET_PRIVATE_FLAG"),
            ("baud_bps", "123456"),
            ("status", "accepted_vin"),
            ("count", True),
        ):
            with self.subTest(field=field):
                report = bounded([connect()])
                report["connect"]["mode_evidence"]["connect_modes"][0][field] = value
                with self.assertRaises(ValueError):
                    triage.triage(report, ui())
        report = bounded([connect()])
        report["connect"]["mode_evidence"]["connect_modes"][0]["VIN"] = "PRIVATE"
        with self.assertRaises(ValueError):
            triage.triage(report, ui())

    def test_06_connect_total_status_and_duplicate_modes_fail_closed(self):
        variants = (
            ("missing mode", lambda report: report["connect"]["mode_evidence"]
             ["connect_modes"].clear()),
            ("excess count", lambda report: report["connect"]["mode_evidence"]
             ["connect_modes"][0].update(count=2)),
            ("wrong status", lambda report: report["connect"]["mode_evidence"]
             ["connect_modes"][0].update(status="invalid_protocol")),
            ("duplicate", lambda report: report["connect"]["mode_evidence"]
             ["connect_modes"].append(copy.deepcopy(
                 report["connect"]["mode_evidence"]["connect_modes"][0]))),
            ("invalid event excess", lambda report: report["connect"]
             ["mode_evidence"].update(invalid_connect_events=2)),
        )
        for name, change in variants:
            with self.subTest(name=name):
                report = bounded([connect()])
                change(report)
                with self.assertRaises(ValueError):
                    triage.triage(report, ui())

    def test_07_set_config_count_semantics_and_spoofed_fields_rejected(self):
        variants = (
            lambda r: r["connect"]["mode_evidence"].update(set_config_events=3),
            lambda r: r["connect"]["mode_evidence"]
            ["set_config_parameters"][0].update(handling="applied_baud", parameter="J1962_PINS"),
            lambda r: r["connect"]["mode_evidence"]
            ["set_config_parameters"][0].update(count=-1),
            lambda r: r["connect"]["mode_evidence"]
            ["set_config_parameters"][0].update(path="C:/PRIVATE"),
        )
        for change in variants:
            with self.subTest(change=change):
                report = bounded([connect(), config()])
                change(report)
                with self.assertRaises(ValueError):
                    triage.triage(report, ui())

    def test_08_only_appended_connect_modes_enter_one_operator_window(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "private-j2534.log"
            source.write_text(connect(0x8005, 0, 125000, 3), encoding="utf-8")
            snapshot = fresh._snapshot(source)
            newer = [connect(5, 0, 500000, 0),
                     config(23, 77, 0)]
            with source.open("a", encoding="utf-8") as stream:
                stream.writelines(newer)
            lines, meta = fresh._append_lines(source, snapshot)
            # Windows text-mode append writes CRLF, while our synthetic
            # fixtures use LF. Audit semantics concern complete records.
            self.assertEqual([item.rstrip("\r\n") for item in lines],
                             [item.rstrip("\r\n") for item in newer])
            self.assertTrue(meta["prefix_verified"])
            redacted = triaged(lines)
            modes = redacted["j2534_connect_mode_evidence"]
            self.assertEqual(modes["connect_modes"][0]["protocol"], "CAN")
            self.assertEqual(modes["connect_modes"][0]["status"], "ok")
            self.assertEqual(modes["set_config_events"], 1)
            self.assertNotIn("CAN_PS", json.dumps(modes))
            self.assertNotIn("ISO15765_PS", json.dumps(modes))
            for private in ("DEADBEEF", "PrivateSectorVTest", str(folder),
                            "YV1CZ0002A0000001"):
                self.assertNotIn(private, json.dumps(redacted))
            self.assertFalse(redacted["replay_approved"])


if __name__ == "__main__":
    unittest.main()
