"""B3A56 synthetic contracts: privacy, module path and claim boundaries."""
import json
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import audit_vida_cem50_loaded_module as tool
sys.path.pop(0)

DLL = tool.DEFAULT_DLL
SHA = tool.PINNED_SHA256


def rec(exe="iexplore.exe", modules=()):
    return {"exe": exe, "modules": list(modules) if modules is not None else None}


class CEM50LoadedModuleTests(unittest.TestCase):
    def test_01_exact_live_path_and_matching_disk_digest(self):
        r = tool.analyze([rec(modules=(DLL,))], disk_digest=SHA,
                         ini_present=True)
        self.assertEqual(r["status"], "EXACT_DLL_IN_HOST_SHA_MATCH")
        self.assertEqual(r["exact_module_path_instances"], 1)
        self.assertTrue(r["expected_ini_present_at_module_directory"])
        self.assertFalse(r["loaded_ini_contents_verified"])
        self.assertFalse(r["original_vida_readvin_pass_verified"])

    def test_02_same_filename_different_provider_not_attributed(self):
        other = r"C:\OtherVendor\J2534CEM50PS.dll"
        r = tool.analyze([rec(modules=(other,))], disk_digest=SHA)
        self.assertEqual(r["status"], "ONLY_SAME_NAME_OTHER_PATH")
        self.assertEqual(r["exact_module_path_instances"], 0)
        self.assertEqual(r["same_basename_other_path_instances"], 1)

    def test_03_no_current_host_is_not_historical_failure(self):
        r = tool.analyze([], disk_digest=SHA)
        self.assertEqual(r["status"], "NO_HOST_PROCESS_IN_SNAPSHOT")
        self.assertFalse(r["original_vida_readvin_pass_verified"])

    def test_04_inspection_denied_is_inconclusive(self):
        r = tool.analyze([rec(modules=None)], disk_digest=SHA)
        self.assertEqual(r["status"], "INCONCLUSIVE_MODULE_ACCESS")
        self.assertEqual(r["host_processes_module_inspection_blocked"], 1)

    def test_05_loaded_path_hash_mismatch_not_success(self):
        r = tool.analyze([rec(modules=(DLL,))], disk_digest="0" * 64)
        self.assertEqual(r["status"], "EXACT_DLL_IN_HOST_DISK_SHA_MISMATCH")
        self.assertFalse(r["installed_disk_sha256_matches_pinned"])

    def test_06_only_required_host_is_counted(self):
        r = tool.analyze([rec("java.exe", (DLL,)),
                          rec("iexplore.exe", ())], disk_digest=SHA)
        self.assertEqual(r["host_processes_present"], 1)
        self.assertEqual(r["exact_module_path_instances"], 0)
        self.assertEqual(r["status"], "EXPECTED_DLL_NOT_SEEN_AT_SNAPSHOT")

    def test_07_windows_paths_are_case_insensitive_and_slash_tolerant(self):
        alt = r"c:/programdata/j2534-cem50-ps/j2534cem50ps.DLL"
        self.assertTrue(tool._same_path(alt, DLL))
        r = tool.analyze([rec(modules=(alt,))], disk_digest=SHA)
        self.assertEqual(r["exact_module_path_instances"], 1)

    def test_08_no_paths_pid_vin_or_raw_modules_in_report(self):
        private = r"C:\Private\User\VIDA\CEM\J2534CEM50PS.dll"
        r = tool.analyze([rec(modules=(private, DLL))], disk_digest=SHA,
                         ini_present=True)
        data = json.dumps(r, sort_keys=True)
        for forbidden in (DLL, private, "YV1CR855691511566", "1234ABCD",
                          "module_paths", "pid"):
            # Lowercase 'pid' does not appear in user-facing report.
            self.assertNotIn(forbidden, data)
        self.assertFalse(r["raw_paths_pids_modules_or_vin_exported"])

    def test_09_bad_sha_and_unexpected_dll_rejected(self):
        with self.assertRaises(ValueError):
            tool.analyze([], expected_sha256="ZZ")
        with self.assertRaises(ValueError):
            tool.analyze([], expected_dll=r"C:\Windows\something.dll")
        with self.assertRaises(ValueError):
            tool.analyze([], host_exe="malware.exe")

    def test_10_absent_on_disk_does_not_negate_live_module(self):
        r = tool.analyze([rec(modules=(DLL,))], disk_digest=None,
                         ini_present=False)
        self.assertEqual(r["status"], "EXACT_DLL_IN_HOST_DISK_UNREADABLE")
        self.assertIsNone(r["installed_disk_sha256_matches_pinned"])
        self.assertFalse(r["expected_ini_present_at_module_directory"])

    def test_11_multiple_hosts_no_raw_details_in_output(self):
        r = tool.analyze([rec(modules=(DLL,)),
                          rec(modules=(r"D:\Old\J2534CEM50PS.dll",)),
                          rec(modules=None)], disk_digest=SHA)
        self.assertEqual(r["host_processes_present"], 3)
        self.assertEqual(r["host_processes_modules_inspected"], 2)
        self.assertEqual(r["host_processes_module_inspection_blocked"], 1)
        self.assertEqual(r["exact_module_path_instances"], 1)
        self.assertEqual(r["same_basename_other_path_instances"], 1)


if __name__ == "__main__":
    unittest.main()
