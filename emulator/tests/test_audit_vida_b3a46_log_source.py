"""Eight bounded read-only tests, no native driver or private source logs."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import audit_vida_b3a46_log_source as tool
sys.path.pop(0)


class B3A46Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.a = self.root / 'a'
        self.b = self.root / 'b'
        self.a.mkdir()
        self.b.mkdir()
        self.file = self.a / tool.NAME

    @staticmethod
    def native(tag='VirtualCar DLL initialized', extra=''):
        return '[PID=1234ABCD iexplore.exe] ' + tag + extra + '\n'

    def test_01_missing_not_attributed(self):
        self.assertEqual(tool.inspect(self.a)['status'], 'missing')

    def test_02_native_signature_in_tail(self):
        self.file.write_text(self.native(extra=' PRIVATE_VIN'))
        x = tool.inspect(self.a)
        self.assertEqual(x['status'], 'native_marker_in_tail')
        self.assertEqual(x['markers_in_tail'], 1)
        self.assertNotIn('PRIVATE_VIN', str(x))

    def test_03_unrelated_file_not_attributed(self):
        self.file.write_text(self.native(tag='unrelated line'))
        self.assertEqual(tool.inspect(self.a)['status'], 'present_no_marker_in_tail')

    def test_04_unprefixed_marker_rejected(self):
        self.file.write_text('PassThruOpen -> device 1\n')
        self.assertEqual(tool.inspect(self.a)['markers_in_tail'], 0)

    def test_05_no_recursion_and_root_dedup(self):
        nested = self.a / 'nested'
        nested.mkdir()
        (nested / tool.NAME).write_text(self.native())
        x = tool.inventory([self.a, self.a, self.b])
        self.assertEqual(len(x), 2)
        self.assertTrue(all(y['status'] == 'missing' for y in x))

    def test_06_symlink_rejected(self):
        original = self.b / tool.NAME
        original.write_text(self.native())
        try:
            self.file.symlink_to(original)
        except (OSError, NotImplementedError):
            self.skipTest('symlinks unavailable')
        self.assertEqual(tool.inspect(self.a)['status'], 'symlink_rejected')

    def test_07_incomplete_last_line_ignored(self):
        self.file.write_text(self.native().rstrip('\n'))
        self.assertEqual(tool.inspect(self.a)['markers_in_tail'], 0)

    def test_08_output_private_and_exclusive(self):
        self.file.write_text(self.native(extra=' SECRET_VIN'))
        out = self.root / 'owner-private.json'
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            tool.main(['--root', str(self.a), '--private-manifest', str(out)])
        text = log.getvalue()
        for forbidden in (str(self.file), str(self.a), '1234ABCD', 'SECRET_VIN'):
            self.assertNotIn(forbidden, text)
        self.assertIn('"path"', out.read_text())
        with self.assertRaises(FileExistsError):
            with contextlib.redirect_stdout(io.StringIO()):
                tool.main(['--root', str(self.a), '--private-manifest', str(out)])


if __name__ == '__main__':
    unittest.main()
