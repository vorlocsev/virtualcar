"""Eight source-level regression gates: fixed SQL catalog, no data access.

The real Windows PowerShell / SQL behavior remains UNTESTED until owner CI
and an authorized local instance run. These are static, not execution tests.
"""
from pathlib import Path
import shutil
import subprocess
import re
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'scripts' / 'Inspect-VidaGetScriptSchema.ps1'


class VidaGetScriptMetadataSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding='utf8')
        cls.sql = re.search(r"\$query\s*=\s*@'\n(.*?)\n'@", cls.source, re.S).group(1)

    def test_01_sql_uses_only_catalog_and_fixed_db(self):
        sql = self.sql.lower()
        for name in ('sys.procedures','sys.schemas','sys.parameters','sys.tables'):
            self.assertIn(name, sql)
        for forbidden in ('xmlDataCompressed','sys.sql_modules','scriptcontent.xml','sp_helptext'):
            self.assertNotIn(forbidden.lower(), sql)
        self.assertIn("Database = 'DiagSwdlRepository'", self.source)

    def test_02_no_stored_procedure_or_data_query(self):
        sql = re.sub(r"N'[^']*'", "N''", self.sql, flags=re.I)
        tokens = re.findall(r'\b[a-zA-Z_]+\b',sql.lower())
        for term in ('exec','execute','insert','update','delete','merge','alter','drop','create','truncate','xp_cmdshell'):
            self.assertNotIn(term,tokens)
        for name in ('dbo.ScriptContent', 'dbo.Script', 'dbo.ScriptProfileMap'):
            self.assertNotIn(name.lower(), sql.lower())

    def test_03_only_exact_five_il_parameter_names(self):
        expected=['@scriptType','@profileList','@scriptId','@languageCode','@ecuType']
        found=set(re.findall(r"p\.name\s*=\s*N'(@\w+)'", self.sql))
        self.assertEqual(found,set(expected))

    def test_04_unknown_metadata_does_not_mean_missing(self):
        self.assertIn("'not_visible_or_absent'",self.source)
        self.assertIn('Metadata depends on SQL permissions',self.source)
        self.assertNotIn("'procedure_missing'",self.source)

    def test_05_no_path_identity_or_sql_credentials_exported(self):
        self.assertIn('OutputFile', self.source)
        self.assertIn('GetFullPath($OutputFile)',self.source)
        self.assertNotIn('server_instance =',self.source.lower())
        self.assertNotIn('script_xml =',self.source.lower())
        self.assertIn("source = 'local_authorized_sql_catalog_metadata_only'",self.source)

    def test_06_exclusive_new_output_outside_repository(self):
        for p in ("[System.IO.FileMode]::CreateNew","Test-Path -LiteralPath $output", "repositoryRoot", "output.StartsWith($prefix"):
            self.assertIn(p,self.source)
        self.assertNotIn('Export-Csv', self.source)

    def test_07_unknown_identity_fields_are_never_true(self):
        for token in ("runtime_readvin_script_selected = 'unknown'", "b9fb_to_vin_mapping = 'unknown'",
                      "xc90_v8_my2009_identity_accepted = 'unknown'", 'replay_approved = $false',
                      'no_stored_procedure_executed = $true'):
            self.assertIn(token, self.source)

    def test_08_all_source_types_explicitly_categorized(self):
        for token in ("return 'text'", "return 'integer'", "return 'boolean'", "return 'identifier'", "return 'xml'", "return 'other'", "return 'unavailable'"):
            self.assertIn(token,self.source)
        self.assertIn('other_visible_parameter_count',self.source)
        self.assertIn('Get-Command Invoke-Sqlcmd',self.source)
        # Parse only, NEVER invoke the source script or connect to SQL.
        executable = shutil.which('powershell.exe') or shutil.which('pwsh')
        if executable:
            quoted = str(SOURCE).replace("'", "''")
            expression = ("$tokens=$null; $parseErrors=$null; "
                          "[System.Management.Automation.Language.Parser]::ParseFile('"
                          + quoted + "',[ref]$tokens,[ref]$parseErrors) | Out-Null; "
                          "if ($parseErrors.Count -gt 0) { exit 1 }")
            result = subprocess.run([executable, '-NoProfile', '-NonInteractive',
                                     '-Command', expression], timeout=20,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, 'PowerShell parser rejected the helper')
        self.assertEqual(len(re.findall(r"(?m)^\s*\w+\s*=\s*\((?:Visible|SqlTypeCategory) '[^']+'\)", self.source)), 14)


    def test_09_any_schema_count_uses_only_catalog(self):
        self.assertIn("AS AnySchemaProcedureVisibleCount", self.sql)
        self.assertIn("AS NonDboProcedureVisibleCount", self.sql)
        self.assertRegex(self.sql, r"(?s)FROM sys\.procedures p\s+WHERE p\.name=N'GetScript'\) AS AnySchemaProcedureVisibleCount")
        self.assertRegex(self.sql, r"(?s)FROM sys\.procedures p JOIN sys\.schemas s.*?s\.name<>N'dbo'\) AS NonDboProcedureVisibleCount")

    def test_10_parameters_remain_dbo_scoped(self):
        self.assertIn("parameter_scope = 'dbo_GetScript_only_if_visible'", self.source)
        self.assertEqual(self.sql.count("OBJECT_ID(N'dbo.GetScript',N'P')"), 11)
        self.assertNotIn('OBJECT_ID(@', self.sql)
        self.assertNotIn('sp_executesql', self.sql.lower())

    def test_11_schema_count_consistency_is_checked(self):
        self.assertIn("$anySchemaCount -ne ($nonDboCount + [int]$procedureVisible)", self.source)
        self.assertIn("throw 'Contradictory GetScript schema visibility counts.'", self.source)
        self.assertIn("ReadCount 'AnySchemaProcedureVisibleCount'", self.source)
        self.assertIn("ReadCount 'NonDboProcedureVisibleCount'", self.source)

    def test_12_visible_dbo_and_nondbo_are_not_conflated(self):
        for label in ('single_visible_dbo',
                      'multiple_visible_schemas_including_dbo',
                      'single_visible_non_dbo',
                      'multiple_visible_non_dbo_schemas',
                      'no_visible_getscript_or_insufficient_permissions'):
            self.assertIn("'" + label + "'", self.source)
        self.assertIn("procedure_visibility = $(if ($procedureVisible)", self.source)
        self.assertIn("getscript_schema_visibility_category = $schemaSummary", self.source)

    def test_13_schema_names_and_credentials_not_exported(self):
        report = self.source.split("$report = [ordered]@{", 1)[1].split("\n}\n$json", 1)[0]
        for token in ('sys.schemas', 's.name', '$ServerInstance', '$Credential', '$query',
                      '$OutputFile', '$row', '@scriptType'):
            self.assertNotIn(token, report)
        self.assertIn('visible_getscript_any_schema_count = $anySchemaCount', report)
        self.assertIn('visible_getscript_non_dbo_schema_count = $nonDboCount', report)

    def test_14_schema_visibility_not_taken_as_accepted_vehicle(self):
        for token in ("runtime_readvin_script_selected = 'unknown'",
                      "xc90_v8_my2009_identity_accepted = 'unknown'",
                      'no_stored_procedure_executed = $true',
                      'no_table_rows_read = $true',
                      'replay_approved = $false'):
            self.assertIn(token, self.source)
        self.assertIn('Any-schema visibility is not proof', self.source)


if __name__ == '__main__':
    unittest.main()
