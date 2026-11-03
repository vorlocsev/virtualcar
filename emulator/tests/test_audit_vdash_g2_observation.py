"""Eight bounded synthetic checks for G2 runtime observation sanitization."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("vdash_g2", ROOT / "tools" / "audit_vdash_g2_observation.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fixture():
    lengths = [64, 64, 20, 20, 64, 64, 20]
    return {
        "format": mod.FORMAT,
        "attestation": {"original_binary_hash_matched": True,
                        "running_original_image": True},
        "private_path": "C:/PRIVATE/FILE/DO_NOT_EXPORT",
        "probes": [
            {"token": token, "next_distinct_method_distance_bytes": length,
             "rva_alias_count": 72 if token == "0x06001359" else 1,
             "window_bytes": length, "read_status": "ok",
             "changed_vs_disk": False, "cil_header_class": "other",
             "private_sample": "SECRET_BYTES"}
            for token, length in zip(mod.TARGETS, lengths)
        ],
    }


class G2ObservationTests(unittest.TestCase):
    def test_01_complete_unchanged_is_not_no_antitamper_proof(self):
        r = mod.audit(fixture())
        self.assertEqual(r["counts"]["unchanged_at_sampled_window"], 7)
        self.assertFalse(r["runtime_method_recovery_verified"])
        self.assertFalse(r["vdash_ecu_identification_verified"])

    def test_02_changed_unique_header_is_only_candidate(self):
        f = fixture()
        f["probes"][4].update(changed_vs_disk=True, cil_header_class="fat")
        r = mod.audit(f)
        self.assertEqual(r["counts"]["changed_unique_rva_header_candidate"], 1)
        self.assertFalse(r["runtime_method_recovery_verified"])

    def test_03_shared_predicate_cannot_be_attributed_to_token(self):
        f = fixture()
        f["probes"][-1].update(changed_vs_disk=True, cil_header_class="tiny")
        r = mod.audit(f)
        self.assertEqual(r["targets"][-1]["assessment"], "changed_shared_rva_unattributed")
        self.assertEqual(r["targets"][-1]["rva_ownership"], "shared")

    def test_04_old_overlapping_v1_window_rejected(self):
        f = fixture()
        f["probes"][2]["window_bytes"] = 64
        with self.assertRaisesRegex(ValueError, "overlap_or_wrong_window"):
            mod.audit(f)
        f = fixture()
        f["probes"][2]["next_distinct_method_distance_bytes"] = 64
        with self.assertRaisesRegex(ValueError, "overlap_or_wrong_window"):
            mod.audit(f)

    def test_05_duplicate_unknown_or_mismatched_alias_rejected(self):
        for change in ("duplicate", "foreign", "alias"):
            with self.subTest(change=change):
                f = fixture()
                if change == "duplicate":
                    f["probes"][2]["token"] = f["probes"][1]["token"]
                elif change == "foreign":
                    f["probes"][2]["token"] = "0x0600ffff"
                else:
                    f["probes"][-1]["rva_alias_count"] = 1
                with self.assertRaises(ValueError):
                    mod.audit(f)

    def test_06_missing_read_is_unknown_not_a_no_change(self):
        f = fixture()
        f["probes"][3].update(read_status="read_failed", changed_vs_disk=None,
                              cil_header_class="unknown")
        r = mod.audit(f)
        self.assertEqual(r["counts"]["not_observed"], 1)
        f["probes"][3]["changed_vs_disk"] = False
        with self.assertRaisesRegex(ValueError, "unobserved_cannot_contain_observation"):
            mod.audit(f)

    def test_07_privacy_fails_closed_on_injected_private_values(self):
        f = fixture()
        f["probes"][0]["private_dump"] = "VIN_SECRET_AND_METHOD_BODY"
        f["attestation"]["private_pid"] = 12345
        r = mod.audit(f)
        dumped = json.dumps(r)
        for secret in ("SECRET_BYTES", "VIN_SECRET", "C:/PRIVATE", "12345"):
            self.assertNotIn(secret, dumped)
        self.assertFalse(r["contains_private_metadata"])
        f["attestation"]["original_binary_hash_matched"] = False
        self.assertEqual(mod.audit(f)["evidence_level"], "unattested_window_observation")

    def test_08_cli_preserves_private_source_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private.json"
            safe = Path(directory) / "safe.json"
            payload = json.dumps(fixture())
            private.write_text(payload, encoding="utf-8")
            self.assertEqual(mod.main([str(private), "--output", str(safe)]), 0)
            saved = safe.read_bytes()
            self.assertEqual(mod.main([str(private), "--output", str(safe)]), 2)
            self.assertEqual(saved, safe.read_bytes())
            self.assertEqual(private.read_text(encoding="utf-8"), payload)
            self.assertEqual(mod.main([str(private), "--output", str(private)]), 2)
            self.assertEqual(private.read_text(encoding="utf-8"), payload)


if __name__ == "__main__":
    unittest.main()
