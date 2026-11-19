"""B3A316: ensure candidate-E3 classification never creates verified session RX."""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "p2core"
TESTS = ROOT / "tests"


class HardwareE3CandidateTests(unittest.TestCase):
    def compile_and_run(self, filename, sources, expected):
        compiler = shutil.which("gcc") or shutil.which("clang") or shutil.which("cc")
        if not compiler:
            self.skipTest("native C compiler unavailable")
        with tempfile.TemporaryDirectory(prefix="b3a316-") as d:
            exe = pathlib.Path(d) / "audit"
            cmd = [compiler, "-std=c11", "-O0", "-Wall", "-Wextra", "-Werror",
                   "-o", str(exe), str(TESTS / filename)] + [
                   str(SRC / name) for name in sources]
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=35)
            run = subprocess.run([str(exe)], check=True, capture_output=True,
                                 text=True, timeout=20)
            self.assertIn(expected, run.stdout)

    def test_12_rx_header_groups(self):
        self.compile_and_run("p2_hw_rx_candidate_test.c",
                             ["p2_cem_router.c"], "PASS 12/12")

    def test_11_channel_and_b9fb_groups(self):
        self.compile_and_run(
            "p2_hw_rx_bridge_test.c",
            ["p2_j2534_bridge.c", "p2_vehicle_core.c",
             "p2_cem_router.c", "p2_ls_observer.c"],
            "PASS 11/11")


if __name__ == "__main__":
    unittest.main()
