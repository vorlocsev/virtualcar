"""Compile exact production supply voltage overrides, without Windows or hardware."""
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestSupplyVoltageSync(unittest.TestCase):
    def test_exact_helper(self):
        source=(ROOT/"src"/"virtualcar.c").read_text(encoding="utf-8")
        start=source.index("/* B3A324: only existing observed synthetic voltage reads")
        end=source.index("/* B3A324 helper end */",start)
        helper=source[start:end]
        harness=(ROOT/"tests"/"b3a324_supply_harness.c").read_text(encoding="utf-8")
        compiler=shlex.split(os.environ["CC"]) if os.environ.get("CC") else [shutil.which("gcc") or shutil.which("clang") or "gcc"]
        with tempfile.TemporaryDirectory(prefix="b3a324-") as tmp:
            folder=Path(tmp)
            (folder/"helper.c").write_text(helper,encoding="utf-8")
            (folder/"harness.c").write_text(harness,encoding="utf-8")
            exe=folder/("check.exe" if os.name=="nt" else "check")
            subprocess.run(compiler+["-std=c11","-Wall","-Wextra","-Werror",str(folder/"harness.c"),"-o",str(exe)],check=True,timeout=60)
            result=subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=20)
            self.assertIn("B3A324_SUPPLY_SYNC_PASS",result.stdout)

    def test_scope(self):
        source=(ROOT/"src"/"virtualcar.c").read_text(encoding="utf-8")
        self.assertIn('GetPrivateProfileStringA("B3A324_SupplyVoltageSyncLab","Enabled","0"',source)
        self.assertIn("g_b3a324_supply_sync=(battery_sync && g_b3a309_ecm_live_lab",source)
        self.assertIn("lab_supply_voltage_sync(g_b3a324_supply_sync,g_battery_mv,data,len,count,c->d2_frame);",source)
        self.assertIn("res[3]=lab_cem_voltage_byte(g_b3a324_supply_sync,g_battery_mv);",source)
