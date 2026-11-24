"""Compile the production model with exact stopped/nonzero/negative test vectors."""
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestSharedEcmState(unittest.TestCase):
    def test_exact_model(self):
        source=(ROOT/"src"/"virtualcar.c").read_text(encoding="utf-8")
        start=source.index("/* B3A315 shared synthetic ECM snapshot;")
        end=source.index("/* B3A315 shared ECM snapshot end */",start)
        model=source[start:end]
        harness=(ROOT/"tests"/"b3a315_model_harness.c").read_text(encoding="utf-8")
        compiler=shlex.split(os.environ["CC"]) if os.environ.get("CC") else [shutil.which("gcc") or shutil.which("clang") or "gcc"]
        with tempfile.TemporaryDirectory(prefix="b3a315-") as tmp:
            folder=Path(tmp)
            (folder/"model.c").write_text(model,encoding="utf-8")
            (folder/"harness.c").write_text(harness,encoding="utf-8")
            exe=folder/("check.exe" if os.name=="nt" else "check")
            subprocess.run(compiler+["-std=c11","-Wall","-Wextra","-Werror",str(folder/"harness.c"),"-o",str(exe)],check=True,timeout=60)
            result=subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=20)
            self.assertIn("B3A315_MODEL_PASS",result.stdout)
