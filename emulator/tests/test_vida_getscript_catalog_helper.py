"""Eight source-level regression gates: fixed SQL catalog, no data access.

The real Windows PowerShell / SQL behavior remains UNTESTED until owner CI
and an authorized local instance run. These are static, not execution tests.
"""
from pathlib import Path
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
        self.assertIn('Catalog visibility depends on SQL permissions',self.source)
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
        self.assertEqual(len(re.findall(r"(?m)^\s*\w+\s*=\s*\((?:Visible|SqlTypeCategory) '[^']+'\)", self.source)), 14)


if __name__ == '__main__':
    unittest.main()
