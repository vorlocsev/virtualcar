"""B3A317: time-bounded E3 is evidence only, never a client/OEM acceptance."""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "p2core"
TEST = ROOT / "tests" / "p2_hw_timed_bridge_test.c"


class TimedHardwareCandidateTests(unittest.TestCase):
    def test_17_timestamped_rx_candidate_groups(self):
        compiler = shutil.which("gcc") or shutil.which("clang") or shutil.which("cc")
        if not compiler:
            self.skipTest("native C compiler unavailable")
        with tempfile.TemporaryDirectory(prefix="b3a317-") as d:
            executable = pathlib.Path(d) / "hardware_time"
            command = [
                compiler, "-std=c11", "-O0", "-Wall", "-Wextra", "-Werror",
                "-o", str(executable), str(TEST),
                str(SRC / "p2_j2534_bridge.c"),
                str(SRC / "p2_vehicle_core.c"),
                str(SRC / "p2_cem_router.c"),
                str(SRC / "p2_ls_observer.c")
            ]
            subprocess.run(command, capture_output=True, text=True, timeout=40, check=True)
            proc = subprocess.run([str(executable)], capture_output=True,
                                  text=True, timeout=20, check=True)
            self.assertIn("PASS 17/17 B3A317", proc.stdout)


if __name__ == "__main__":
    unittest.main()
