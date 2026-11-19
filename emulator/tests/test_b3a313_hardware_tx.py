"""B3A313: run pure-C Hardware TX observer and vehicle bridge regressions."""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "p2core"
TESTS = ROOT / "tests"


class HardwareTxObserverTests(unittest.TestCase):
    def _build_and_run(self, test_file, sources, expected):
        compiler = shutil.which("gcc") or shutil.which("clang") or shutil.which("cc")
        if not compiler:
            self.skipTest("C compiler unavailable (native host test not run)")
        with tempfile.TemporaryDirectory(prefix="b3a313-") as d:
            exe = pathlib.Path(d) / "observer"
            cmd = [compiler, "-std=c11", "-O0", "-Wall", "-Wextra",
                   "-o", str(exe), str(TESTS / test_file)] + [str(SRC / x) for x in sources]
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=35)
            res = subprocess.run([str(exe)], check=True, capture_output=True,
                                 text=True, timeout=20)
            self.assertIn(expected, res.stdout)

    def test_8_pure_c_groups(self):
        self._build_and_run(
            "p2_hw_tx_sequence_test.c", ["p2_cem_router.c"],
            "PASS 8/8")

    def test_vehicle_observer_integration(self):
        self._build_and_run(
            "p2_hw_tx_vehicle_test.c",
            ["p2_vehicle_core.c", "p2_cem_router.c", "p2_ls_observer.c"],
            "PASS: p2_vehicle")


if __name__ == "__main__":
    unittest.main()
