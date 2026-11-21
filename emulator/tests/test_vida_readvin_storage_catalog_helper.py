"""Eight static safety gates for the owner's read-only VIDA SQL catalog tool.

Does not launch PowerShell or connect to a real SQL Server.
"""
from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "Inspect-VidaReadVinStorageSchema.ps1"


class VidaReadVinStorageCatalogSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")
        m = re.search(r"\$query\s*=\s*@'\s*\n(.*?)\n'@", cls.source, re.S)
        if m is None:
            raise AssertionError("Missing single fixed SQL query")
        cls.sql = m.group(1)

    def test_01_only_sql_catalog_metadata_is_queried(self):
        for table in ("sys.tables", "sys.schemas", "sys.columns", "sys.types"):
            self.assertIn(table, self.sql)
        self.assertIn("Database = 'DiagSwdlRepository'", self.source)
        self.assertIn("FROM sys.tables t", self.sql)
        self.assertNotIn("FROM dbo.", self.sql)
        self.assertNotIn("JOIN dbo.", self.sql)

    def test_02_no_execution_or_record_queries(self):
        stripped = re.sub(r"N?'[^']*'", "''", self.sql)
        tokens = set(re.findall(r"\b[a-zA-Z_]+\b", stripped.lower()))
        for word in ("exec", "execute", "insert", "update", "delete", "merge", "alter", "drop", "create", "truncate", "declare"):
            self.assertNotIn(word, tokens)
        for forbidden in ("ScriptContent.xmlDataCompressed", "OPENROWSET", "sys.sql_modules", "sp_helptext"):
            self.assertNotIn(forbidden.lower(), self.sql.lower())

    def test_03_script_table_allowlist_fixed(self):
        sql_tables = set(re.findall(r"N'(Script(?:Type|ProfileMap|Content|CarFunction)?)'", self.sql))
        expected = {"Script", "ScriptType", "ScriptProfileMap", "ScriptContent", "ScriptCarFunction"}
        self.assertEqual(sql_tables, expected)
        self.assertIn("if ($expected -cnotcontains $table)", self.source)
        self.assertIn("JOIN sys.columns c", self.sql)

    def test_04_bounded_and_validated_metadata_only(self):
        for token in ("$rows.Count -gt 256", "$entry.columns.Count -gt 64", "column.Length -gt 80", "type.Length -gt 128", "length -gt 32767"):
            self.assertIn(token, self.source)
        self.assertIn("Unexpected column metadata", self.source)

    def test_05_privacy_and_schema_redaction(self):
        for token in ("schema_names_redacted = $true", "contains_table_rows = $false", "contains_xml = $false", "contains_vin_or_can = $false", "contains_sql_credentials = $false", "contains_source_paths = $false"):
            self.assertIn(token, self.source)
        self.assertIn("if ($schema -ceq 'dbo')", self.source)
        report = self.source.split("$report = [ordered]@{", 1)[1].split("\n}\n$json", 1)[0]
        for secret in ("$ServerInstance", "$Credential", "$query", "$r.ColumnName", "$r.SchemaName", "$OutputFile"):
            self.assertNotIn(secret, report)

    def test_06_exclusive_outside_repository(self):
        for token in ("$PSScriptRoot", "GetFullPath($OutputFile)", "StartsWith($prefix", "[System.IO.FileMode]::CreateNew", "Test-Path -LiteralPath $output"):
            self.assertIn(token, self.source)
        self.assertNotIn("Export-Csv", self.source)

    def test_07_no_identity_or_replay_promotion(self):
        for token in ("selected_readvin_script_proven = $false", "b9fb_to_vin_mapping_verified = $false", "xc90_v8_my2009_identity_accepted = $false", "replay_approved = $false", "sql_getscript_executed = $false"):
            self.assertIn(token, self.source)

    def test_08_no_implicit_absence_and_no_unsafe_workflow(self):
        self.assertIn("'not_visible_or_absent'", self.source)
        self.assertIn("catalog_metadata_visibility_permission_dependent = $true", self.source)
        for token in ("Invoke-Sqlcmd", "QueryTimeout = 30", "System.Management.Automation.PSCredential"):
            self.assertIn(token, self.source)
        self.assertNotIn("Start-Process", self.source)
        self.assertNotIn("Invoke-WebRequest", self.source)
        self.assertNotIn("PassThruConnect", self.source)


if __name__ == "__main__":
    unittest.main()
