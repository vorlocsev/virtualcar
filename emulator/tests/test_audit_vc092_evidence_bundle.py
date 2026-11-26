"""Eight VC092 synthetic evidence-bundle checks; no live system access."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vc092_evidence_bundle as audit
from test_audit_vc090e_ecu_identification import catalog

HEAD = "a" * 40
DLL = b"synthetic-not-an-executable" * 20
NATIVE = audit.digest(DLL)


def encode(obj):
    return json.dumps(obj).encode("utf-8")


def native():
    return dict(schema=audit.SCHEMAS["native_preflight"], source_sha=HEAD,
                native_dll_sha256=NATIVE, native_dll_bytes=len(DLL), status="pass",
                failed_stage="", gates=dict.fromkeys(audit.NATIVE_GATES, "pass"),
                **dict.fromkeys(("registration_install_remove", "vida_provider_selection",
                    "vida_loaded_module_identity", "vida_readvin", "vida_t111", "vida_t122",
                    "physical_j2534"), "not_tested"))


def checkpoint(phase):
    return dict(schema=audit.SCHEMAS["registration_" + phase],
                source_sha=HEAD, native_sha256=NATIVE, phase=phase,
                canonical_present=phase in ("Installed", "RemoveCancelled"),
                ui_actions="owner_confirmation_required", vida="not_tested",
                physical_j2534="not_tested", registry32_other=dict(digest="1"*64, other_provider_count=69),
                registry64=dict(digest="2"*64, other_provider_count=1))


def manifest(files, scope="synthetic", claims=False):
    return dict(schema=audit.SCHEMA, source_sha=HEAD, native_sha256=NATIVE,
                scope=scope, owner_claims=dict.fromkeys(audit.CLAIMS, claims),
                files={role: dict(file=role+(".dll" if role=="native_dll" else ".json"),
                                  sha256=audit.digest(raw)) for role, raw in files.items()})


def reconcile(files, **kwargs):
    return audit.reconcile(manifest(files, **kwargs), HEAD, files)


class BundleTests(unittest.TestCase):
    def test_01_empty_bundle_remains_blocked(self):
        result = reconcile({})
        self.assertEqual(result["gates"]["environment"], "blocked_or_synthetic")
        self.assertEqual(result["registration_checkpoints"], 0)
        self.assertEqual(result["gates"]["native_preflight"], "not_tested")
        self.assertFalse(result["release_ready"])

    def test_02_exact_report_and_candidate_bytes(self):
        files = {"native_preflight": encode(native()), "native_dll": DLL}
        self.assertEqual(reconcile(files)["gates"]["native_preflight"], "reported_preflight_consistent")
        self.assertEqual(reconcile({"native_preflight": encode(native())})["gates"]["native_preflight"],
                         "candidate_file_missing")
        self.assertEqual(reconcile(dict(files, native_dll=b"other"))["gates"]["native_preflight"],
                         "candidate_mismatch")
        data = native()
        data["source_sha"] = "b"*40
        self.assertEqual(reconcile(dict(files, native_preflight=encode(data)))["gates"]["native_preflight"],
                         "source_mismatch")

    def test_03_partial_and_complete_registration_are_not_acceptance(self):
        files = {role: encode(checkpoint(phase)) for phase, role in zip(audit.PHASES, audit.REG_ROLES)}
        partial = dict(list(files.items())[:2])
        result = reconcile(partial)
        self.assertEqual(result["registration_checkpoints"], 2)
        self.assertEqual(result["gates"]["registration"], "partial_checkpoints")
        result = reconcile(files, scope="owner_reviewed", claims=True)
        self.assertEqual(result["gates"]["registration"], "reported_checkpoints_consistent")
        self.assertEqual(result["gates"]["environment"], "owner_claims_only")
        self.assertFalse(result["registration_install_remove_verified"])
        self.assertFalse(result["registry_mutation_authorized_by_tool"])

    def test_04_checkpoint_gap_registry_and_candidate_mismatch(self):
        files = {"registration_Baseline": encode(checkpoint("Baseline")),
                 "registration_Installed": encode(checkpoint("Installed"))}
        self.assertEqual(reconcile(files)["gates"]["registration"], "checkpoint_gap")
        item = checkpoint("InstallCancelled")
        item["registry32_other"]["digest"] = "3"*64
        files = {"registration_Baseline": files["registration_Baseline"],
                 "registration_InstallCancelled": encode(item)}
        self.assertEqual(reconcile(files)["gates"]["registration"], "registry_snapshot_mismatch")
        item = checkpoint("InstallCancelled")
        item["native_sha256"] = "4"*64
        files["registration_InstallCancelled"] = encode(item)
        self.assertEqual(reconcile(files)["gates"]["registration"], "candidate_mismatch")

    def test_05_favorable_observations_are_unbound(self):
        cases = (("binding", "candidate_binding_gate", "candidate_path_and_disk_bytes_observed"),
                 ("readvin", "native_evidence_gate", "matching_lab_identity_delivery_observed"),
                 ("ecu", "readout_reconciliation_gate", "reported_categories_consistent_only"))
        files = {}
        for role, key, value in cases:
            schema_key = "schema_version" if role == "binding" else "schema"
            files[role] = encode({schema_key: audit.SCHEMAS[role], key: value,
                                  **dict.fromkeys(audit.FALSE_FLAGS[role], False)})
        files["catalog"] = encode(catalog())
        result = reconcile(files, scope="owner_reviewed", claims=True)
        for role, _, _ in cases:
            self.assertEqual(result["gates"][role], "unbound_report_observation")
        self.assertEqual(result["gates"]["catalog"], "sample_all_references_matched")
        self.assertEqual(result["overall"], "runtime_acceptance_not_verified")
        for key in ("same_runtime_session_verified", "original_vida_readvin_verified",
                    "original_vida_ecu_identification_verified", "original_catalog_coverage_verified",
                    "release_ready"):
            self.assertFalse(result[key])

    def test_06_reject_contradictory_and_invalid_reports(self):
        data = native()
        data["gates"]["fresh_native_build"] = "fail"
        with self.assertRaises(ValueError):
            reconcile({"native_preflight": encode(data)})
        data = checkpoint("Baseline")
        data["canonical_present"] = True
        with self.assertRaises(ValueError):
            reconcile({"registration_Baseline": encode(data)})
        data = catalog()
        data["matching_reference_rows"] += 1
        with self.assertRaises(ValueError):
            reconcile({"catalog": encode(data)})
        data = dict(schema=audit.SCHEMAS["readvin"], **dict.fromkeys(audit.FALSE_FLAGS["readvin"], False))
        data["original_vida_vin_accepted_verified"] = True
        with self.assertRaises(ValueError):
            reconcile({"readvin": encode(data)})

    def test_07_manifest_digest_head_and_path_guards(self):
        files = {"native_dll": DLL}
        original = manifest(files)
        with self.assertRaises(ValueError):
            audit.reconcile(original, "b"*40, files)
        with self.assertRaises(ValueError):
            audit.reconcile(original, HEAD, {"native_dll": b"changed"})
        with self.assertRaises(ValueError):
            audit.reconcile(original, HEAD, {})
        for name in ("../private.dll", "C:private.dll", "folder/private.dll", "bad..dll"):
            m = copy.deepcopy(original)
            m["files"]["native_dll"]["file"] = name
            with self.assertRaises(ValueError):
                audit.reconcile(m, HEAD, files)
        with self.assertRaises(ValueError):
            audit.load_json(b'{"schema":1,"schema":2}')

    def test_08_cli_exclusive_output_integrity_and_privacy(self):
        files = {"native_preflight": encode(native()), "native_dll": DLL}
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            m = manifest(files)
            m["files"]["native_preflight"]["file"] = "PRIVATE-local.json"
            src = root/"manifest.json"
            src.write_bytes(encode(m))
            for role, raw in files.items():
                (root/m["files"][role]["file"]).write_bytes(raw)
            out = root/"out.json"
            args = ["--manifest", str(src), "--expected-head", HEAD, "--output", str(out)]
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(audit.main(args), 0)
                with self.assertRaises(SystemExit) as err:
                    audit.main(args)
                self.assertEqual(err.exception.code, 2)
            data = out.read_text()
            self.assertNotIn("PRIVATE", data)
            self.assertEqual(json.loads(data)["manifest_sha256"], audit.digest(src.read_bytes()))
            for role, raw in files.items():
                self.assertEqual((root/m["files"][role]["file"]).read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
