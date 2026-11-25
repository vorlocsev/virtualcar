"""Offline regression of the production CEM529 lab identity handler."""
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src' / 'virtualcar.c'


class TestCem529Identity(unittest.TestCase):
    def test_exact_handler(self):
        source = SOURCE.read_text(encoding='utf-8')
        marker = 'static U32 answer_b3a150_ggd_cem50_lab('
        self.assertEqual(source.count(marker), 1)
        start = source.index(marker)
        end = source.index('\n}', start) + 2
        compiler = shlex.split(os.environ['CC']) if os.environ.get('CC') else [shutil.which('gcc') or shutil.which('clang') or 'gcc']
        with tempfile.TemporaryDirectory(prefix='vc0665-') as tmp:
            folder = Path(tmp)
            (folder / 'route_under_test.h').write_text(source[start:end] + '\n', encoding='utf-8')
            exe = folder / ('check.exe' if os.name == 'nt' else 'check')
            subprocess.run(compiler + ['-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT / 'src'), '-I', tmp, str(ROOT / 'tests' / 'vc0665_identity_harness.c'), '-o', str(exe)], check=True, timeout=60)
            result = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=20)
            self.assertIn('VC0663_C_CHECKS=78 PASS', result.stdout)

    def test_default_off_and_dependency(self):
        source = SOURCE.read_text(encoding='utf-8')
        for name, flag in [('VC0662_F110Lab', 'g_vc0662_f110'), ('VC0663_IdentityLab', 'g_vc0663_identity')]:
            self.assertIn(f'static U32 {flag}=0u;', source)
            self.assertIn(f'GetPrivateProfileStringA("{name}","Enabled","0",v,sizeof(v),g_profile_path);', source)
        first = 'g_vc0662_f110=g_b3a150_ggd_cem_lab && vc0662_f110_enabled(v);'
        second = 'g_vc0663_identity=g_vc0662_f110 && vc0662_f110_enabled(v);'
        self.assertLess(source.index(first), source.index(second))
