"""Portable host tests for synthetic read-only lab helpers, not a native J2534 test."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get('B3A285_SOURCE', str(HERE.parent / 'src' / 'virtualcar.c')))
FIXTURES = Path(os.environ.get('B3A285_FIXTURES', str(HERE / 'b3a285')))


def extract(source, start, function):
    if source.count(start) != 1 or source.count(function) != 1:
        raise AssertionError('Ambiguous production helper')
    pos = source.index(start)
    end = source.index('\n}', source.index(function)) + 2
    return source[pos:end]


class TestLabHelpers(unittest.TestCase):
    def run_fixture(self, name, start, function, marker):
        source = SOURCE.read_text(encoding='utf-8')
        fixture = (FIXTURES / name).read_text(encoding='utf-8')
        production = extract(source, start, function)
        old = extract(fixture, start, function)
        self.assertEqual(old, production, 'Fixture implementation drifted from production')
        compiler = shlex.split(os.environ['CC']) if os.environ.get('CC') else [shutil.which('gcc') or shutil.which('clang') or 'gcc']
        with tempfile.TemporaryDirectory(prefix='b3a285-helper-') as tmp:
            c = Path(tmp) / name
            exe = Path(tmp) / ('helper.exe' if os.name == 'nt' else 'helper')
            c.write_text(fixture.replace(old, production, 1), encoding='utf-8')
            subprocess.run(compiler + ['-std=c11', '-O2', '-Wall', '-Wextra', str(c), '-o', str(exe)], check=True)
            result = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
            self.assertIn(marker, result.stdout)
            print(result.stdout.strip())

    def test_current_55(self):
        self.run_fixture('test_current.c', '/* B3A267: opt-in synthetic A5/A6', 'static U32 lab_current_frames(', '55/55_PASS')

    def test_srs_12(self):
        self.run_fixture('test_srs_ae11.c', 'static int lab_d2_empty_reply(', 'static int lab_d2_empty_reply(', '12/12_PASS')


if __name__ == '__main__':
    unittest.main(verbosity=2)
