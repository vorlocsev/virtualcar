"""B3A312 source-only safety contract for Windows PowerShell VIDA bridge.

These tests do NOT execute PowerShell or connect to the owner's SQL Server.
"""
from pathlib import Path
import re
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "connect_installed_vida_carcom.ps1"


class InstalledVidaBridgeSourceChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_01_probe_and_analyze_separate(self):
        self.assertIn("[ValidateSet('Probe','Analyze')]", self.source)
        self.assertIn("if($Mode -eq 'Probe')", self.source)
        self.assertIn("source_rows_read=$false", self.source)

    def test_02_local_instance_integrated_security(self):
        self.assertIn("'.\\VIDA'", self.source)
        self.assertIn("$b.IntegratedSecurity=$true", self.source)
        self.assertIn("$b.ApplicationIntent=[System.Data.SqlClient.ApplicationIntent]::ReadOnly", self.source)
        self.assertNotIn("SqlCredential", self.source)
        self.assertNotIn("Password=", self.source)

    def test_03_all_carcom_tables_present(self):
        for table in ("T161_Profile", "T160_DefaultEcuVariant",
                      "T100_EcuVariant", "T101_Ecu", "T120_Config_EcuVariant",
                      "T121_Config", "T122_Protocol"):
            with self.subTest(table=table):
                self.assertIn(table, self.source)
        self.assertIn("FROM [sys].[tables]", self.source)
        self.assertIn("JOIN [sys].[columns]", self.source)

    def test_04_parameterized_selects_only(self):
        self.assertIn("$cmd.Parameters.Add('@value'", self.source)
        text = self.source
        sql = re.findall(r"'(SELECT TOP .*?)'", text)
        self.assertGreaterEqual(len(sql), 7)
        for statement in sql:
            self.assertTrue(statement.startswith("SELECT TOP ("))
            self.assertIn("@value", statement)
        self.assertNotRegex(
            text, r"(?i)\$cmd\.CommandText\s*=\s*['\"]\s*(?:UPDATE|INSERT|DELETE|EXEC|MERGE|ALTER)\b"
        )

    def test_05_bounded_private_inputs(self):
        self.assertIn("Read-ProfileLines $ExactProfiles 43 43", self.source)
        self.assertIn("Read-ProfileLines $GeneralProfiles 1 8", self.source)
        self.assertIn("SELECT TOP (33)", self.source)
        self.assertIn("SELECT TOP (2)", self.source)
        self.assertIn("overlap of private profile sets", self.source)

    def test_06_never_promote_to_ecu_identity(self):
        for token in (
            "original_vida_runtime_profile_selected=$false",
            "cem_hardware_h_l_verified=$false",
            "client_ecu_alive_verified=$false",
            "original_vida_readvin_accepted=$false",
            "response_fixture_selection_approved=$false",
            "source_sql_snapshot_consistent=$false",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.source)

    def test_07_exclusive_aggregate_output_not_originals(self):
        self.assertIn("[System.IO.FileMode]::CreateNew", self.source)
        self.assertIn("unsafe report output directory", self.source)
        self.assertIn("source/output path collision", self.source)
        self.assertIn("contains_owner_identifiers_vin_payloads_or_config_values=$false", self.source)

    def test_08_no_running_vida_or_j2534(self):
        forbidden = [
            "Start-Process", "PassThruConnect", "PassThruWriteMsgs",
            "Invoke-Sqlcmd", "Set-ItemProperty", "New-ItemProperty",
            "Register-ObjectEvent", "Invoke-Expression",
        ]
        for cmd in forbidden:
            with self.subTest(command=cmd):
                self.assertNotIn(cmd, self.source)


    def test_09_no_powershell_pid_automatic_variable_assignment(self):
        # $PID is a read-only automatic variable (PowerShell variable names
        # are case-insensitive); assigning $pid breaks Analyze at runtime.
        self.assertNotRegex(self.source, r"(?im)^\s*\$pid\s*=")
        self.assertIn("$profileDbId=Unique-Row", self.source)
        self.assertIn("$profileDbId[0]", self.source)


    def test_10_sanitized_failure_stage_and_nonzero_exit(self):
        for phase in ("preflight", "connection", "database", "schema",
                      "private_input", "aggregation", "report"):
            with self.subTest(phase=phase):
                self.assertIn("$phase='" + phase + "'", self.source)
        self.assertIn("status='failed';phase=$phase;error_class=", self.source)
        self.assertIn("[Console]::Error.WriteLine($safeError)", self.source)
        self.assertNotIn("Write-Error", self.source)
        self.assertRegex(self.source, r"(?s)catch\s*\{.*?exit 2\s*\}")
        self.assertNotIn("Exception.Message", self.source)


    def test_11_reject_output_path_reparse_ancestors(self):
        self.assertIn("function Assert-SafeReportParent", self.source)
        self.assertIn("[System.IO.Path]::GetDirectoryName($reportPath)", self.source)
        self.assertIn("[System.IO.DirectoryInfo]::new($parent)", self.source)
        self.assertIn("while($null -ne $cursor)", self.source)
        self.assertIn("[System.IO.FileAttributes]::ReparsePoint", self.source)
        self.assertIn("throw 'unsafe report parent reparse point'", self.source)
        self.assertIn("Assert-SafeReportParent $out", self.source)
        self.assertLess(
            self.source.index("Assert-SafeReportParent $out"),
            self.source.index("$phase='aggregation'")
        )


if __name__ == "__main__":
    unittest.main()
