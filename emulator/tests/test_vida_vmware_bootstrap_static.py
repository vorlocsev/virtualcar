"""Static owner-runner bootstrap safety checks. Never copies a VIDA database.

On Windows CI, PowerShell AST is parsed without executing the installer.
"""
from pathlib import Path
import shutil
import subprocess
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "eng" / "Install-VidaOfflineRunner.ps1"


class VidaVmwareBootstrapStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")

    def test_01_known_exact_nine_database_names(self):
        for name in (
            "DiagSwdlRepository", "CarCom", "BaseData", "DiagSwdlSession",
            "DiceTiming", "ImageRepository", "EPC", "servicerep_ru-RU",
            "AccessServer",
        ):
            self.assertIn("'" + name + "'", self.script)
        self.assertIn("foreach ($suffix in @('.sqlite', '.manifest.json'))", self.script)

    def test_02_source_private_destination_and_runner_manifest(self):
        for marker in (
            "E:\\VirtualCar\\VIDA-private",
            "E:\\VirtualCar\\VIDA-tools",
            "E:\\VirtualCar\\Tools\\python312.path",
            "SourceFolder", "ValidatorZip",
        ):
            self.assertIn(marker, self.script)
        self.assertIn("if ($source -eq $destination)", self.script)

    def test_03_fail_closed_preexisting_destination_or_ci_workspace(self):
        for marker in (
            "Refusing to store private data inside a GitHub workspace.",
            "Destination already exists; refusing overwrite",
            "Input must be a regular file",
            "[IO.FileAttributes]::ReparsePoint",
        ):
            self.assertIn(marker, self.script)

    def test_04_verify_before_atomic_final_move(self):
        for marker in (
            "Insufficient disk space", "VIDA-private.staging-",
            "Copy-Item -LiteralPath",
            "verify_offline_collection.py", "if ($LASTEXITCODE -ne 0)",
            "Move-Item -LiteralPath $stage -Destination $destination",
        ):
            self.assertIn(marker, self.script)
        self.assertLess(self.script.index("& $python $validator --folder $stage"),
                        self.script.index("Move-Item -LiteralPath $stage"))
        self.assertNotIn("Remove-Item", self.script)

    def test_05_no_sql_github_or_data_export(self):
        forbidden = (
            "Invoke-Sqlcmd", "pyodbc", "Invoke-WebRequest",
            "gh api", "actions/upload-artifact", "git push",
            "BACKUP DATABASE", "WriteAllBytes",
        )
        for term in forbidden:
            self.assertNotIn(term, self.script)

    def test_06_runner_service_is_opt_in_and_elevated(self):
        self.assertIn("[switch]$ConfigureRunnerService", self.script)
        self.assertIn("WindowsBuiltInRole]::Administrator", self.script)
        self.assertIn("Where-Object { $_.Name -like 'actions.runner.*' }", self.script)
        self.assertIn("Set-Service -Name $svc.Name -StartupType Automatic", self.script)
        self.assertIn("if ($ConfigureRunnerService)", self.script)
        self.assertIn("does not power on a stopped VMware guest", self.script)

    def test_07_windows_powershell_ast_parse_without_execution(self):
        exe = shutil.which("powershell.exe") or shutil.which("pwsh")
        if not exe:
            self.skipTest("PowerShell parser is only available on Windows CI")
        quoted = str(SCRIPT).replace("'", "''")
        command = ("$t=$null; $e=$null; "
                   "[System.Management.Automation.Language.Parser]::ParseFile('"
                   + quoted + "',[ref]$t,[ref]$e) | Out-Null; "
                   "if ($e.Count -gt 0) { $e | Out-String | Write-Error; exit 1 }")
        process = subprocess.run(
            [exe, "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(process.returncode, 0, process.stderr)


if __name__ == "__main__":
    unittest.main()
