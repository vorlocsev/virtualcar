"""Synthetic SQL Server bounded reference coverage tests; no original VIDA data."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("t111_t122_aggregate", TOOLS / "audit_vida_t111_t122_aggregate.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.current = []

    def execute(self, sql):
        self.connection.queries.append(sql)
        if sql == "SELECT DB_NAME()":
            self.current = [(self.connection.database,)]
        elif "FROM sys.columns" in sql:
            self.current = [
                (self.connection.source_schema, self.connection.source_table, self.connection.source_id),
                (self.connection.source_schema, self.connection.source_table, self.connection.source_ref),
                (self.connection.target_schema, self.connection.target_table, self.connection.target_id),
                ("dbo", "PRIVATE_CLIENT_VIN_123456", "PRIVATE_SECRET")
            ]
            if self.connection.omit_column:
                self.current = [r for r in self.current if r[2] != self.connection.source_ref]
        elif "FROM sys.tables" in sql:
            self.current = [
                (self.connection.source_schema, self.connection.source_table),
                (self.connection.target_schema, self.connection.target_table),
                ("dbo", "PRIVATE_CLIENT_VIN_123456")
            ]
            if self.connection.duplicate:
                self.current.append(("another", "T111_Service"))
        elif "SELECT COUNT_BIG(*)" in sql:
            self.current = self.connection.aggregate
        else:
            raise AssertionError("unexpected SQL")
        return self

    def fetchmany(self, size):
        return self.current[:size]


class Connection:
    def __init__(self, database="CarCom", source_schema="dbo", target_schema="dbo"):
        self.database = database
        self.source_schema = source_schema
        self.target_schema = target_schema
        self.source_table = "T111_Service"
        self.target_table = "T122_Protocol"
        self.source_id = "id"
        self.source_ref = "fkT122_Protocol"
        self.target_id = "id"
        self.queries = []
        self.aggregate = [(10, 2, 7, 1)]
        self.omit_column = False
        self.duplicate = False
        self.closed = False
        self.timeout = 0

    def cursor(self):
        return Cursor(self)

    def close(self):
        self.closed = True


class VidaAggregateTests(unittest.TestCase):
    def setUp(self):
        self.conn = Connection()
        self.connect_calls = []

    def connect(self, string, autocommit, timeout):
        self.connect_calls.append((string, autocommit, timeout))
        return self.conn

    def test_01_bounded_aggregate_and_negative_evidence(self):
        report = mod.probe("VIDA_RESTRICTED", self.connect)
        self.assertEqual(report["sampled_service_rows"], 10)
        self.assertEqual((report["null_reference_rows"], report["matching_reference_rows"],
                          report["unmatched_reference_rows"]), (2, 7, 1))
        self.assertFalse(report["readvin_execution_verified"])
        self.assertFalse(report["d2_baud_verified"])
        self.assertFalse(report["client_vin_accepted"])
        self.assertEqual(len(self.connect_calls), 1)
        string, autocommit, timeout = self.connect_calls[0]
        self.assertIn("Trusted_Connection=Yes", string)
        self.assertIn("TrustServerCertificate=No", string)
        self.assertIn("DATABASE=CarCom", string)
        self.assertEqual((autocommit, timeout, self.conn.timeout), (True, 8, 8))
        self.assertTrue(self.conn.closed)
        self.assertEqual(len(self.conn.queries), 4)
        sql = self.conn.queries[-1]
        self.assertIn("TOP (1000)", sql)
        self.assertIn("OUTER APPLY", sql)
        self.assertIn("SELECT TOP (1) p.[id]", sql)
        self.assertNotIn("SELECT *", sql)
        self.assertNotIn("PRIVATE", json.dumps(report))

    def test_02_empty_sample_does_not_prove_readvin(self):
        self.conn.aggregate = [(0, None, None, None)]
        r = mod.probe("VIDA_RESTRICTED", self.connect)
        self.assertFalse(r["sample_nonempty"])
        self.assertFalse(r["selected_vehicle_profile_verified"])
        self.assertEqual(r["matching_reference_rows"], 0)

    def test_03_wrong_database_fails_before_catalog(self):
        self.conn.database = "PRIVATE_INCORRECT_DB"
        with self.assertRaisesRegex(mod.ProbeError, "preflight failed"):
            mod.probe("VIDA_RESTRICTED", self.connect)
        self.assertEqual(self.conn.queries, ["SELECT DB_NAME()"])
        self.assertTrue(self.conn.closed)

    def test_04_missing_column_rejected_before_source_read(self):
        self.conn.omit_column = True
        with self.assertRaisesRegex(mod.ProbeError, "preflight failed"):
            mod.probe("VIDA_RESTRICTED", self.connect)
        self.assertFalse(any("SELECT COUNT_BIG" in x for x in self.conn.queries))
        self.assertTrue(self.conn.closed)

    def test_05_ambiguous_table_rejected(self):
        self.conn.duplicate = True
        with self.assertRaisesRegex(mod.ProbeError, "preflight failed"):
            mod.probe("VIDA_RESTRICTED", self.connect)
        self.assertFalse(any("SELECT COUNT_BIG" in x for x in self.conn.queries))

    def test_06_untrusted_dsn_rejected_before_connect(self):
        with self.assertRaisesRegex(mod.ProbeError, "invalid DSN"):
            mod.probe("VIDA_X;PWD=private", self.connect)
        self.assertEqual(self.connect_calls, [])

    def test_07_identifier_escaping_and_private_name_suppression(self):
        self.conn.source_schema = "schema]name"
        self.conn.target_schema = "target]schema"
        report = mod.probe("VIDA_RESTRICTED", self.connect)
        sql = self.conn.queries[-1]
        self.assertIn("[schema]]name].[T111_Service]", sql)
        self.assertIn("[target]]schema].[T122_Protocol]", sql)
        self.assertNotIn("schema]name", json.dumps(report))
        self.assertNotIn("PRIVATE", json.dumps(report))

    def test_08_query_setup_error_closes_and_redacts(self):
        class Bad(Connection):
            def __setattr__(self, key, value):
                if key == "timeout" and value == 8:
                    raise RuntimeError("PRIVATE_PASSWORD_DETAIL")
                super().__setattr__(key, value)
        self.conn = Bad()
        with self.assertRaises(mod.ProbeError) as caught:
            mod.probe("VIDA_RESTRICTED", self.connect)
        self.assertNotIn("PRIVATE_PASSWORD_DETAIL", str(caught.exception))
        self.assertTrue(self.conn.closed)

    def test_09_inconsistent_aggregate_rejected(self):
        self.conn.aggregate = [(10, 2, 7, 5)]
        with self.assertRaisesRegex(mod.ProbeError, "inconsistent aggregate counts"):
            mod.probe("VIDA_RESTRICTED", self.connect)
        self.assertTrue(self.conn.closed)

    def test_10_cli_exclusive_output_no_connection_leak(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "aggregate.json"
            with patch.object(mod, "probe", return_value=mod.probe("VIDA_RESTRICTED", self.connect)):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(mod.main(["--output", str(output)]), 0)
                    self.assertEqual(mod.main(["--output", str(output)]), 2)
            result = json.loads(output.read_text())
            self.assertEqual(result["matching_reference_rows"], 7)
            self.assertFalse(result["replay_approved"])


    def test_11_case_sensitive_catalog_identifiers_are_preserved(self):
        self.conn.source_schema = "VidaMixed"
        self.conn.target_schema = "ProtocolsMixed"
        self.conn.source_table = "t111_service"
        self.conn.target_table = "t122_PROTOCOL"
        self.conn.source_id = "ID"
        self.conn.source_ref = "FKt122_PROTOCOL"
        self.conn.target_id = "Id"
        report = mod.probe("VIDA_RESTRICTED", self.connect)
        sql = self.conn.queries[-1]
        self.assertIn("[VidaMixed].[t111_service]", sql)
        self.assertIn("[ProtocolsMixed].[t122_PROTOCOL]", sql)
        self.assertIn("s.[FKt122_PROTOCOL]", sql)
        self.assertIn("ORDER BY s.[ID]", sql)
        self.assertIn("p.[Id]", sql)
        self.assertNotIn("VidaMixed", json.dumps(report))
        self.assertEqual(report["source_table"], "T111_Service")

    def test_12_escape_all_catalog_identifier_slots(self):
        self.conn.source_schema = "Vida]Group"
        self.conn.target_schema = "Proto]Group"
        self.conn.source_table = "T111_]Service"  # This is not allowlisted; no aggregate.
        with self.assertRaisesRegex(mod.ProbeError, "preflight failed"):
            mod.probe("VIDA_RESTRICTED", self.connect)
        self.assertFalse(any("OUTER APPLY" in sql for sql in self.conn.queries))
        self.assertTrue(self.conn.closed)
        self.conn = Connection(source_schema="Vida]Group", target_schema="Proto]Group")
        self.conn.source_id = "iD"
        self.conn.source_ref = "fkt122_protocol"
        self.conn.target_id = "iD"
        mod.probe("VIDA_RESTRICTED", self.connect)
        sql = self.conn.queries[-1]
        self.assertIn("[Vida]]Group].[T111_Service]", sql)
        self.assertIn("[Proto]]Group].[T122_Protocol]", sql)

    def test_13_duplicate_case_variants_fail_before_application_select(self):
        self.conn.duplicate = True
        with self.assertRaisesRegex(mod.ProbeError, "preflight failed"):
            mod.probe("VIDA_RESTRICTED", self.connect)
        self.assertFalse(any("OUTER APPLY" in sql for sql in self.conn.queries))

    def test_14_existing_output_fails_before_private_query(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "aggregate.json"
            output.write_text("DO_NOT_OVERWRITE")
            with patch.object(mod, "probe", side_effect=AssertionError("should not query")):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(mod.main(["--output", str(output)]), 2)
            self.assertEqual(output.read_text(), "DO_NOT_OVERWRITE")



if __name__ == "__main__":
    unittest.main()
