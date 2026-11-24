"""Compile exact production REM voltage override, without Windows or hardware."""
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestRemVoltageSync(unittest.TestCase):
    def test_exact_helper(self):
        source=(ROOT/"src"/"virtualcar.c").read_text(encoding="utf-8")
        start=source.index("/* B3A320: exact existing REM voltage response only")
        end=source.index("\n}",start)+3
        helper=source[start:end]
        harness=(ROOT/"tests"/"b3a320_rem_harness.c").read_text(encoding="utf-8")
        compiler=shlex.split(os.environ["CC"]) if os.environ.get("CC") else [shutil.which("gcc") or shutil.which("clang") or "gcc"]
        with tempfile.TemporaryDirectory(prefix="b3a320-") as tmp:
            folder=Path(tmp)
            (folder/"helper.c").write_text(helper,encoding="utf-8")
            (folder/"harness.c").write_text(harness,encoding="utf-8")
            exe=folder/("check.exe" if os.name=="nt" else "check")
            subprocess.run(compiler+["-std=c11","-Wall","-Wextra","-Werror",str(folder/"harness.c"),"-o",str(exe)],check=True,timeout=60)
            result=subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=20)
            self.assertIn("B3A320_REM_SYNC_PASS",result.stdout)

    def test_scope(self):
        source=(ROOT/"src"/"virtualcar.c").read_text(encoding="utf-8")
        self.assertIn('GetPrivateProfileStringA("B3A320_RemVoltageSyncLab","Enabled","0"',source)
        self.assertIn("g_b3a320_rem_sync=(battery_sync && g_b3a309_ecm_live_lab",source)
        self.assertIn("count=lab_current_frames(data,len,c->baud,c->flags,tx_flags,c->d2_frame);\n        lab_rem_voltage_sync(g_b3a320_rem_sync,g_battery_mv,data,len,count,c->d2_frame);",source)
        self.assertEqual(source.count("lab_rem_voltage_sync("),2)
