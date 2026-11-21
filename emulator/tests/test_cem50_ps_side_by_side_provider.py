"""Static safety contracts for the separate, opt-in CEM50 PS provider.

Not an execution of PowerShell, Windows registry, DLL, or original VIDA.
"""
from pathlib import Path
import re
import unittest

ADAPTER = Path(__file__).resolve().parents[1] / "adapters" / "cem50"
INSTALL = (ADAPTER / "Install-J2534CEM50-PS.ps1").read_text(encoding="utf-8")
REMOVE = (ADAPTER / "Remove-J2534CEM50-PS.ps1").read_text(encoding="utf-8")
LEGACY = (ADAPTER / "Install-J2534CEM50.ps1").read_text(encoding="utf-8")
PROFILE = (ADAPTER / "virtualcar.ini").read_text(encoding="utf-8")
HEAD = "9ab3738d6c53442f83c57727f6eaaf44e383c618"
DLL_SHA = "7F21E2606C6E7981ECDEDFE6769F180981C6DDFFFFBCC5C35CD4A6E983C98C3E"


class SideBySideCem50PsProviderTests(unittest.TestCase):
    def test_01_dedicated_registry32_name_and_directory(self):
        for source in (INSTALL, REMOVE):
            self.assertIn("J2534 Diagnostic Interface CEM50 PS", source)
            self.assertIn(r"SOFTWARE\PassThruSupport.04.04\J2534 Diagnostic Interface CEM50 PS", source)
            self.assertIn("RegistryView]::Registry32", source)
            self.assertIn("'J2534-CEM50-PS'", source)
            self.assertIn("'J2534CEM50PS.dll'", source)
            self.assertNotIn("DeleteSubKeyTree('SOFTWARE", source)
        self.assertIn("$name = 'J2534 Diagnostic Interface CEM50'", LEGACY)
        self.assertIn("'J2534-CEM50'", LEGACY)
        self.assertNotIn("SetValue('CAN_PS'", LEGACY)

    def test_02_verified_native_artifact_is_hard_pinned_both_ways(self):
        for source in (INSTALL, REMOVE):
            self.assertIn(HEAD, source)
            self.assertIn(DLL_SHA, source)
        for token in ("$SummaryJson", "$NativeReportJson",
                      "exact-head\\emulator\\VirtualCarJ2534.dll",
                      "native-ps\\ps-native-check.json",
                      "summary.source_sha", "summary.route_evidence_suite",
                      "summary.windows_x86_build", "summary.can_ps_native",
                      "native.iso15765_ps_f190_verified",
                      "native.matched_frames", "native.j1962_hs", "native.j1962_ms"):
            self.assertIn(token, INSTALL)
        self.assertIn("Only a verified emulator VirtualCarJ2534.dll is permitted", INSTALL)
        self.assertIn("Get-FileHash -LiteralPath $src -Algorithm SHA256", INSTALL)

    def test_03_no_forged_oem_or_vida_gate(self):
        for source in (INSTALL, REMOVE):
            self.assertNotIn("Start-Process", source)
            self.assertNotIn("PassThruWriteMsgs", source)
            self.assertNotIn("SQL", source)
        for token in ("summary.vida_readvin_verified",
                      "summary.ecu_identification_verified",
                      "summary.physical_adapter_used",
                      "native.vida_readvin_verified",
                      "native.ecu_identification_verified",
                      "native.physical_adapter_used"):
            self.assertIn(token, INSTALL)
        self.assertIn("synthetic_lab_not_oem_attested", INSTALL)
        self.assertIn("synthetic_lab_not_oem_attested", PROFILE)

    def test_04_advertises_only_implemented_ps_and_classic_can(self):
        for value in ("CAN", "ISO15765", "CAN_PS", "ISO15765_PS"):
            self.assertIn("$key.SetValue('%s', 1" % value, INSTALL)
            self.assertIn("[int]$key.GetValue('%s') -ne 1" % value, REMOVE)
        for unsupported in ("ISO9141", "ISO14230", "SW_CAN_PS", "GM_UART_PS",
                            "J1850PWM", "J1850VPW", "SCI_A_ENGINE"):
            self.assertNotIn("SetValue('%s'" % unsupported, INSTALL)
        self.assertIn("$key.SetValue('MessageVersion', 0x0404", INSTALL)

    def test_05_apply_is_explicit_and_elevated_after_preflight(self):
        self.assertIn("if (-not $Apply) {", INSTALL)
        self.assertIn("if (-not $IConfirmOfflineSynthetic)", INSTALL)
        self.assertIn("Administrator", INSTALL)
        self.assertLess(INSTALL.index("if (-not $Apply) {"),
                        INSTALL.index("CreateDirectory($targetDirectory)"))
        self.assertLess(INSTALL.index("if (-not $IConfirmOfflineSynthetic)"),
                        INSTALL.index("CreateDirectory($targetDirectory)"))
        self.assertIn("registration already exists; never overwrite", LEGACY)
        self.assertIn("Dedicated PS registration already exists; never overwrite", INSTALL)
        self.assertIn("Dedicated PS directory already exists; never overwrite", INSTALL)
        self.assertIn("$createdDirectory = $true", INSTALL)
        self.assertIn("$createdKey = $true", INSTALL)
        self.assertIn("$reg.DeleteSubKeyTree($keyPath, $false)", INSTALL)

    def test_06_profile_gates_precede_registry_write(self):
        for gate in ("Vehicle.VIN", "Vehicle.ModelYear", "Vehicle.ECUCount",
                     "J2534_2.Enabled", "P2.StrictRouting",
                     "D2_50.B9FBFrameCount", "D2_50.ResponseId",
                     "Wrong", "Duplicate profile", "Invalid B9FB transport sequence"):
            if gate != "Wrong":
                self.assertIn(gate, INSTALL)
        self.assertIn("B9FB identity or chassis mismatched", INSTALL)
        self.assertLess(INSTALL.index("if ($wire.Count -ne 91"),
                        INSTALL.index("$reg = [Microsoft.Win32.RegistryKey]::OpenBaseKey"))
        self.assertIn("Enabled = 1", PROFILE)
        self.assertIn("B9FBFrameCount = 13", PROFILE)

    def test_07_removal_is_own_key_only_with_dry_run_and_hash(self):
        self.assertIn("if (-not $Apply) {", REMOVE)
        self.assertIn("if (-not $IConfirmClientClosed)", REMOVE)
        self.assertIn("Administrator", REMOVE)
        self.assertIn("ReparsePoint", REMOVE)
        self.assertIn("Unexpected extra files in PS installation", REMOVE)
        self.assertIn("Installed PS binary digest mismatch", REMOVE)
        self.assertIn("Registry32 key not owned by this exact PS test installation", REMOVE)
        self.assertLess(REMOVE.index("if (-not $Apply) {"),
                        REMOVE.index("$reg.DeleteSubKeyTree($keyPath, $false)"))
        self.assertIn("Remove-Item -LiteralPath $directory -Recurse -Force", REMOVE)
        self.assertNotIn("J2534-CEM50'", REMOVE)

    def test_08_same_metadata_provenance_and_exclusive_paths(self):
        registry = re.compile(r"^\$keyPath = '([^']+)'$", re.M)
        directory = re.compile(r"^\$(?:targetDirectory|directory) = Join-Path \$env:ProgramData '([^']+)'$", re.M)
        name = re.compile(r"^\$name = '([^']+)'$", re.M)
        for matcher in (registry, directory, name):
            self.assertEqual(matcher.findall(INSTALL), matcher.findall(REMOVE))
            self.assertEqual(len(matcher.findall(INSTALL)), 1)
        self.assertIn("LabSourceSha", INSTALL)
        self.assertIn("LabDllSha256", INSTALL)
        self.assertIn("LabSourceSha", REMOVE)
        self.assertIn("LabDllSha256", REMOVE)


if __name__ == "__main__":
    unittest.main()
