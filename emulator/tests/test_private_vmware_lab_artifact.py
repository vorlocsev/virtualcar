"""Guards for the short-lived, private P0 VMware LAB Actions artifact.

Static CI safety checks run on any platform. The one Windows negative test
invokes PowerShell against an untrusted event and must not build a binary.
No J2534 provider, SectorV client, raw CAN or private donor data is used.
"""
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "vmware-development-validation.yml"
HELPER = ROOT / "emulator" / "tools" / "verify_local_vmware_lab_ci.ps1"


class PrivateVmwareLabArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.yml = WORKFLOW.read_text(encoding="utf-8")
        cls.ps = HELPER.read_text(encoding="utf-8")
        cls.stage = cls.yml.split("      - name: Stage private verified VMware LAB after full validation", 1)[1]
        cls.upload = cls.stage.split("      - name: Upload short-lived private VMware LAB x86 artifact", 1)[1]
        cls.cleanup = cls.upload.split("      - name: Clean temporary private LAB output from persistent runner", 1)[1]

    def test_01_trusted_owner_only_development_push_remains_the_job_boundary(self):
        self.assertIn("github.repository == 'vorlocsev/virtualcar'", self.yml)
        self.assertIn("github.actor == 'vorlocsev'", self.yml)
        self.assertIn("$env:GITHUB_ACTOR -cne 'vorlocsev'", self.ps)
        self.assertIn("github.ref == 'refs/heads/development'", self.yml)
        self.assertIn("branches: [development]", self.yml)
        self.assertNotIn("pull_request:", self.yml)
        self.assertIn("contents: read", self.yml)

    def test_02_stage_and_upload_require_success_after_validation_summary(self):
        self.assertLess(self.yml.index("      - name: Validation summary"),
                        self.yml.index("      - name: Stage private verified VMware LAB"))
        self.assertLess(self.yml.index("      - name: Stage private verified VMware LAB"),
                        self.yml.index("      - name: Upload short-lived private VMware LAB"))
        guarded = "if: success() && github.event_name == 'push' && github.ref == 'refs/heads/development'"
        self.assertEqual(self.yml.count(guarded), 2)
        self.assertIn("-RetainValidatedLab", self.stage)

    def test_03_artifact_is_ephemeral_private_not_a_release(self):
        self.assertIn("uses: actions/upload-artifact@v4", self.upload)
        self.assertIn("retention-days: 3", self.upload)
        self.assertIn("compression-level: 0", self.upload)
        self.assertIn("if-no-files-found: error", self.upload)
        self.assertNotIn("upload-release-asset", self.upload)
        self.assertNotIn("create-release", self.upload)
        self.assertIn("No public releases or deployments", self.yml)

    def test_04_artifact_matches_only_the_verified_zip_and_sha256_sidecar(self):
        folder = "virtualcar-ci-local-lab-"
        self.assertIn("$dirName = '" + folder + "'", self.ps)
        self.assertIn("runner.temp }}/" + folder, self.upload)
        self.assertIn("/*.zip\n", self.upload)
        self.assertIn("/*.zip.sha256\n", self.upload)
        self.assertIn("if ($members.Count -ne 2", self.ps)
        self.assertIn("$members -cnotcontains ($filename + '.sha256')", self.ps)
        self.assertIn("$actualSidecar -cne $expectedSidecar", self.ps)

    def test_05_retention_is_fail_closed_at_exact_sha(self):
        self.assertIn("[switch]$RetainValidatedLab", self.ps)
        for clause in ("$env:GITHUB_EVENT_NAME -cne 'push'",
                       "$env:GITHUB_REF -cne 'refs/heads/development'",
                       "$env:GITHUB_ACTOR -cne 'vorloc'",
                       "$env:GITHUB_SHA -cne $sourceSha"):
            self.assertIn(clause, self.ps)
        self.assertIn("$retainVerifiedOutputs = $false", self.ps)
        self.assertIn("$retainVerifiedOutputs = $RetainValidatedLab.IsPresent", self.ps)
        self.assertLess(self.ps.index("'Packaged real x86 inputs did not verify'"),
                        self.ps.index("$retainVerifiedOutputs = $RetainValidatedLab.IsPresent"))

    def test_06_default_smoke_still_removes_private_archive(self):
        self.assertIn("verify_local_vmware_lab_ci.ps1\n", self.yml)
        self.assertIn("if (-not $retainVerifiedOutputs -and (Test-Path -LiteralPath $output))", self.ps)
        self.assertIn("Remove-Item -LiteralPath $control -Force -ErrorAction Stop", self.ps)
        self.assertIn("Remove-Item -LiteralPath $output -Recurse -Force -ErrorAction Stop", self.ps)

    def test_07_persistent_runner_cleanup_is_unconditional_and_bounded(self):
        self.assertIn("if: always()", self.cleanup)
        self.assertIn("GITHUB_RUN_ATTEMPT", self.cleanup)
        self.assertIn("GITHUB_RUN_ID", self.cleanup)
        self.assertIn("Refusing to clean outside RUNNER_TEMP", self.cleanup)
        self.assertIn("Remove-Item -LiteralPath $target -Recurse -Force", self.cleanup)
        self.assertLess(self.yml.index("      - name: Upload short-lived"),
                        self.yml.index("      - name: Clean temporary private LAB"))

    @unittest.skipUnless(os.name == "nt", "PowerShell 5.1 denial test requires Windows")
    def test_08_nonowner_nonpush_cannot_retain_or_package_lab(self):
        env = dict(os.environ)
        env.update({
            "GITHUB_REPOSITORY": "vorlocsev/virtualcar",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_ACTOR": "unauthorized_test_actor",
            "GITHUB_SHA": "a" * 40,
        })
        run = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(HELPER), "-RetainValidatedLab"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=15,
        )
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("LAB retention requires owner-authored development push",
                      run.stderr)
        self.assertNotIn("PASS: actual Win32 GUI", run.stdout)


if __name__ == "__main__":
    unittest.main()
