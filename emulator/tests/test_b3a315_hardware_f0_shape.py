"""B3A315: native offline checks for source-bounded Hardware F0 shape."""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "p2core" / "p2_cem_router.c"
TEST = ROOT / "tests" / "p2_hw_f0_shape_test.c"


class HardwareF0ShapeTests(unittest.TestCase):
    def test_source_bound_f0_shape_ten_groups(self):
        compiler = shutil.which("gcc") or shutil.which("clang") or shutil.which("cc")
        if compiler is None:
            self.skipTest("C compiler not present")
        with tempfile.TemporaryDirectory(prefix="b3a315-") as temp:
            exe = pathlib.Path(temp) / "f0_audit"
            command = [compiler, "-std=c11", "-O0", "-Wall", "-Wextra",
                       "-Werror", "-o", str(exe), str(TEST), str(SRC)]
            subprocess.run(command, capture_output=True, text=True,
                           check=True, timeout=35)
            result = subprocess.run([str(exe)], capture_output=True, text=True,
                                    check=True, timeout=20)
            self.assertIn("PASS 10/10", result.stdout)


if __name__ == "__main__":
    unittest.main()
