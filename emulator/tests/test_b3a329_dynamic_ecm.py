"""Compile the exact production timeline and model without Windows."""
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestDynamicEcmTimeline(unittest.TestCase):
    def test_exact_timeline(self):
        source=(ROOT/"src"/"virtualcar.c").read_text(encoding="utf-8")
        model=source[source.index("/* B3A315 shared synthetic ECM snapshot;"):source.index("/* B3A315 shared ECM snapshot end */")]
        timeline=source[source.index("/* B3A329 deterministic synthetic timeline;"):source.index("/* B3A329 timeline end */")]
        harness=(ROOT/"tests"/"b3a329_timeline_harness.c").read_text(encoding="utf-8")
        compiler=shlex.split(os.environ["CC"]) if os.environ.get("CC") else [shutil.which("gcc") or shutil.which("clang") or "gcc"]
        with tempfile.TemporaryDirectory(prefix="b3a329-") as tmp:
            folder=Path(tmp)
            (folder/"model.c").write_text(model,encoding="utf-8")
            (folder/"timeline.c").write_text(timeline,encoding="utf-8")
            (folder/"harness.c").write_text(harness,encoding="utf-8")
            exe=folder/("check.exe" if os.name=="nt" else "check")
            subprocess.run(compiler+["-std=c11","-Wall","-Wextra","-Werror",str(folder/"harness.c"),"-o",str(exe)],check=True,timeout=60)
            result=subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=20)
            self.assertIn("B3A329_TIMELINE_PASS",result.stdout)

    def test_wiring(self):
        source=(ROOT/"src"/"virtualcar.c").read_text(encoding="utf-8")
        self.assertIn('GetPrivateProfileStringA("B3A329_DynamicEcmLab","Enabled","0"',source)
        self.assertIn("g_b3a324_supply_sync && str_len(v)==1u",source)
        self.assertIn("ecm_lab_dynamic_start(g_b3a329_dynamic_lab,GetTickCount());ecm_lab_refresh();",source)
        self.assertIn("lock_state();ecm_lab_refresh();",source)
        self.assertIn("g_battery_mv=g_ecm_lab_state.battery_mv;",source)
        request=source[source.index("static void process_request("):]
        self.assertLess(request.index("ecm_lab_refresh();"),request.index("if(process_d2("))
