"""Eight synthetic VC090E groups, no original VIDA or SQL connection."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vc090e_ecu_identification as audit


def row(module="LAB-CEM", profile="in_configuration", readout="alive",
        transport="positive_identification", catalog_lookup="matched_variant"):
    return dict(module=module, profile=profile, readout=readout,
                transport=transport, catalog_lookup=catalog_lookup)


def observations(*rows, same_run=True):
    return dict(schema=audit.SCHEMA, evidence_source="synthetic",
                same_run=same_run, modules=list(rows))


def catalog(n=10, matched=10, missed=0, nulls=0):
    return dict(schema_version=audit.CATALOG_SCHEMA,
                status="sampled_reference_coverage_only",
                source_database="CarCom", source_table="T111_Service",
                target_table="T122_Protocol", sample_bound=audit.SAMPLE_LIMIT,
                sampled_service_rows=n, matching_reference_rows=matched,
                unmatched_reference_rows=missed, null_reference_rows=nulls,
                sample_nonempty=n > 0, **{k: False for k in audit.CATALOG_FALSE})


class EcuEvidenceTests(unittest.TestCase):
    def test_01_catalog_counts_are_not_ecu_acceptance(self):
        result = audit.audit(observations(), catalog())
        self.assertEqual(result["catalog_reference_coverage"]["status"], "sample_all_references_matched")
        self.assertEqual(result["readout_reconciliation_gate"], "no_module_observations")
        self.assertFalse(result["original_vida_ecu_identification_accepted"])
        for args, expected in [
            ((0, 0, 0, 0), "empty_sample"),
            ((10, 7, 2, 1), "unmatched_references_observed"),
            ((10, 9, 0, 1), "null_references_observed"),
        ]:
            self.assertEqual(audit.validate_catalog(catalog(*args))["status"], expected)

    def test_02_distinct_readout_states(self):
        data = observations(row(), row("LAB-ECM", readout="not_alive",
                                       transport="no_reply", catalog_lookup="default_variant"),
                            row("LAB-REM", profile="not_in_configuration",
                                readout="not_present", transport="not_observed",
                                catalog_lookup="not_observed"))
        result = audit.audit(data, catalog())
        self.assertEqual(result["readout_counts"], dict(alive=1, not_alive=1, not_present=1, not_observed=0))
        self.assertEqual(result["reported_alive_with_positive_identification"], 1)
        self.assertEqual(result["reported_not_alive_default_variant"], 1)
        self.assertEqual(result["readout_reconciliation_gate"], "reported_categories_consistent_only")
        self.assertFalse(result["actual_j2534_identification_exchange_verified"])

    def test_03_default_variant_does_not_create_response(self):
        result = audit.audit(observations(row(readout="not_alive", transport="not_observed",
                                               catalog_lookup="default_variant")))
        self.assertEqual(result["reported_alive_with_positive_identification"], 0)
        self.assertEqual(result["evidence_gaps"]["not_alive_transport_unobserved"], 1)
        self.assertEqual(result["readout_reconciliation_gate"], "reported_evidence_incomplete")
        self.assertEqual(result["catalog_reference_coverage"]["status"], "not_supplied")

    def test_04_discrepancies_require_review(self):
        cases = [
            (row(transport="negative_response"), "alive_without_positive_identification"),
            (row(readout="not_alive"), "not_alive_with_reported_positive_identification"),
            (row(profile="not_in_configuration", readout="not_present"),
             "not_present_with_reported_positive_identification"),
            (row(readout="not_present", transport="not_observed"), "not_present_but_in_configuration"),
            (row(profile="not_in_configuration"), "readout_outside_reported_configuration"),
        ]
        for item, key in cases:
            with self.subTest(key=key):
                result = audit.audit(observations(item))
                self.assertEqual(result["discrepancies"][key], 1)
                self.assertEqual(result["readout_reconciliation_gate"], "reported_discrepancies_require_review")

    def test_05_missing_evidence_and_cross_run(self):
        for item, key in [
            (row(transport="not_observed"), "alive_transport_unobserved"),
            (row(profile="unknown"), "readout_configuration_unobserved"),
            (row(profile="unknown", readout="not_present", transport="not_observed"),
             "not_present_configuration_unobserved"),
            (row(readout="not_observed"), "positive_identification_without_readout"),
        ]:
            result = audit.audit(observations(item))
            self.assertEqual(result["evidence_gaps"][key], 1)
            self.assertEqual(result["readout_reconciliation_gate"], "reported_evidence_incomplete")
        result = audit.audit(observations(row(), same_run=False), catalog())
        self.assertEqual(result["readout_reconciliation_gate"], "same_run_not_reported")
        self.assertFalse(result["catalog_and_readout_same_run_verified"])

    def test_06_reject_duplicate_tokens_and_invalid_fields(self):
        for data in (
            observations(row(), row("lab-cem")),
            observations(row(module="path/private")),
            observations(row(readout="unknown")),
            observations(row(profile="invalid")),
            observations(*[row(str(i)) for i in range(audit.MAX_MODULES+1)]),
            dict(observations(), same_run=1),
            dict(observations(), secret="private"),
        ):
            with self.assertRaises(ValueError):
                audit.audit(data)
        with self.assertRaises(ValueError):
            audit.load_json(b'{"schema":1,"schema":2}')
        with self.assertRaises(ValueError):
            audit.load_json(b'{"number": NaN}')

    def test_07_catalog_scope_and_invalid_counts(self):
        for report in (
            dict(catalog(), sampled_service_rows=True),
            catalog(10, 8, 0, 0),
            catalog(1001, 1001),
            dict(catalog(), sample_nonempty=False),
            dict(catalog(), source_table="OTHER"),
            dict(catalog(), ecu_identification_verified=True),
        ):
            with self.assertRaises(ValueError):
                audit.audit(observations(row()), report)

    def test_08_cli_exclusive_output_privacy_and_integrity(self):
        data = observations(row(module="PRIVATE-MODULE-TOKEN"))
        with tempfile.TemporaryDirectory() as directory:
            src = Path(directory)/"observations.json"
            cat = Path(directory)/"catalog.json"
            out = Path(directory)/"report.json"
            src.write_text(json.dumps(data), encoding="utf-8")
            cat.write_text(json.dumps(dict(catalog(), private_extra="PRIVATE-CATALOG")), encoding="utf-8")
            before = (src.read_bytes(), cat.read_bytes())
            args = ["--observations", str(src), "--catalog-report", str(cat), "--output", str(out)]
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(audit.main(args), 0)
                with self.assertRaises(SystemExit) as error:
                    audit.main(args)
                self.assertEqual(error.exception.code, 2)
            self.assertEqual(before, (src.read_bytes(), cat.read_bytes()))
            text = out.read_text()
            self.assertNotIn("PRIVATE", text)
            report = json.loads(text)
            for key in ("selected_vehicle_profile_verified", "original_vida_client_authenticated",
                        "original_vida_readvin_accepted", "original_vida_ecu_identification_accepted",
                        "physical_j2534_verified"):
                self.assertFalse(report[key])


if __name__ == "__main__":
    unittest.main()
