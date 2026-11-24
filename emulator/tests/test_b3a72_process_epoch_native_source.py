"""B3A72 native process-epoch marker source and linker contracts."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src" / "virtualcar.c").read_text(encoding="utf-8")
KERNEL_DEF = (ROOT / "src" / "kernel32.def").read_text(encoding="utf-8")
BUILD = (ROOT / "build-cross.sh").read_text(encoding="utf-8")
LIVE_AUDIT = (ROOT / "tools" / "audit_vida_cem50_loaded_module.py").read_text(encoding="utf-8")


class ProcessEpochNativeSourceTests(unittest.TestCase):
    def test_01_process_creation_time_uses_windows_process_api(self):
        self.assertIn("GetCurrentProcess(void)", SOURCE)
        self.assertIn("GetProcessTimes(HANDLE process", SOURCE)
        self.assertIn("GetProcessTimes(GetCurrentProcess()", SOURCE)

    def test_02_filetime_is_encoded_as_eight_big_endian_bytes(self):
        self.assertIn('logline("Process creation FILETIME (BE)",value,8)', SOURCE)
        self.assertIn("u32_be(value,created.high);u32_be(value+4,created.low)", SOURCE)

    def test_03_epoch_marker_precedes_active_ini_and_fixture_metadata(self):
        marker = SOURCE.index("log_process_creation_filetime();")
        active = SOURCE.index('str_copy(detail,"Active INI: "')
        fixtures = SOURCE.index('logline("P2 fixture target/opcode/response-id/frame-count (BE)"')
        self.assertLess(marker, active)
        self.assertLess(active, fixtures)

    def test_04_kernel32_import_definition_contains_both_apis(self):
        self.assertIn(" GetCurrentProcess\n", KERNEL_DEF)
        self.assertIn(" GetProcessTimes\n", KERNEL_DEF)

    def test_05_cross_linker_resolves_both_import_symbols(self):
        self.assertIn("/alternatename:__imp_GetCurrentProcess=__imp__GetCurrentProcess", BUILD)
        self.assertIn("/alternatename:__imp_GetProcessTimes=__imp__GetProcessTimes", BUILD)

    def test_06_live_process_epoch_brackets_pid_module_snapshot(self):
        before = LIVE_AUDIT.index("epoch_before = process_creation_filetime(pid)")
        modules = LIVE_AUDIT.index("mods = snapshot(0x00000008 | 0x00000010, pid)")
        after = LIVE_AUDIT.index("epoch_after = process_creation_filetime(pid)")
        self.assertLess(before, modules)
        self.assertLess(modules, after)
        self.assertIn("epoch_before == epoch_after", LIVE_AUDIT)


if __name__ == "__main__":
    unittest.main()
