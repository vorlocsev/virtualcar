"""Eight synthetic import gates: exact D2 echo and private-source preservation."""
import configparser
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('import_p2_trace_safety', ROOT / 'tools/import_p2_trace.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def call_import(source, profile, output, *extra):
    args = ['import_p2_trace.py', str(source), '--profile', str(profile), '--output', str(output), *extra]
    with patch.object(sys, 'argv', args), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        try:
            module.main()
        except SystemExit as error:
            return error.code
    return 0


def inputs(directory):
    source, profile = Path(directory) / 'private.log', Path(directory) / 'private.ini'
    source.write_text('TX (app request) 00 0F FF FE CB 50 B9 FB 00 00 00 00\n'
                      'RX (simulated) 01 20 00 03 CC 50 F9 FB 00 00 00 00\n', encoding='utf-8')
    profile.write_text('; SYNTHETIC input, no real vehicle data\n[Vehicle]\nVIN=XXXXXXXXXXXXXXXXX\n', encoding='utf-8')
    return source, profile


class ImportSafetyTests(unittest.TestCase):
    def test_01_exact_positive_echo_for_all_allowed_operations(self):
        for target in (0x40, 0x50):
            for opcode in (0xF0, 0xFB, 0xFC):
                module.validate_response([(0x1200003, bytes([0xCC, target, 0xF9, opcode, 0, 0, 0, 0]))], target, opcode)

    def test_02_negative_b9_reply_is_preserved_without_success_claim(self):
        frames = [(0x1200003, bytes.fromhex('CC 50 7F B9 31 00 00 00'))]
        module.validate_response(frames, 0x50, 0xFB)
        self.assertEqual(frames[0][1], bytes.fromhex('CC 50 7F B9 31 00 00 00'))
        with self.assertRaises(ValueError):
            module.validate_response([(0x1200003, bytes.fromhex('CC 50 7F 22 31 00 00 00'))], 0x50, 0xFB)

    def test_03_foreign_positive_echo_and_arbitrary_single_frame_rejected(self):
        for payload in ('CC 50 F9 F0 00 00 00 00', 'CC 50 E3 02 00 00 00 00',
                        'CC 40 F9 FB 00 00 00 00', 'CC 50 00 00 00 00 00 00'):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                module.validate_response([(0x1200003, bytes.fromhex(payload))], 0x50, 0xFB)

    def test_04_source_log_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source, profile = inputs(directory)
            original = source.read_bytes()
            self.assertEqual(call_import(source, profile, source), 2)
            self.assertEqual(source.read_bytes(), original)

    def test_05_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source, profile = inputs(directory)
            output = Path(directory) / 'existing.ini'
            output.write_bytes(b'SYNTHETIC_PRESERVE_ME')
            self.assertEqual(call_import(source, profile, output), 2)
            self.assertEqual(output.read_bytes(), b'SYNTHETIC_PRESERVE_ME')

    def test_06_source_profile_and_hardlinked_input_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            source, profile = inputs(directory)
            old_source, old_profile = source.read_bytes(), profile.read_bytes()
            self.assertEqual(call_import(source, profile, profile), 2)
            alias = Path(directory) / 'source-alias.ini'
            try:
                os.link(source, alias)
            except OSError:
                self.skipTest('Hardlinks unavailable on this filesystem')
            self.assertEqual(call_import(source, profile, alias), 2)
            self.assertEqual(source.read_bytes(), old_source)
            self.assertEqual(profile.read_bytes(), old_profile)

    def test_07_valid_new_output_and_existing_redaction_regression(self):
        with tempfile.TemporaryDirectory() as directory:
            source, profile = inputs(directory)
            source.write_text((ROOT / 'samples/p2_b9fb_public_redacted.txt').read_text(), encoding='utf-8')
            old_source, old_profile = source.read_bytes(), profile.read_bytes()
            output = Path(directory) / 'new.ini'
            self.assertEqual(call_import(source, profile, output), 0)
            config = configparser.ConfigParser(interpolation=None)
            config.read(output, encoding='utf-8')
            self.assertEqual(config.getint('D2_50', 'B9FBFrameCount'), 13)
            self.assertEqual(source.read_bytes(), old_source)
            self.assertEqual(profile.read_bytes(), old_profile)
            vin = b'YV1CZ0002A0000001'  # explicitly synthetic
            frames = [(1, b'\x0A' + vin[:7]), (1, b'\x0B' + vin[7:14]), (1, b'\x0C' + vin[14:] + b'\r\nAA')]
            redacted, count = module.redact_vin(frames)
            self.assertEqual(count, 1)
            self.assertNotIn(vin, b''.join(frame[1][1:] for frame in redacted))

    def test_08_invalid_fixture_or_unwritable_output_does_not_touch_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            source, profile = inputs(directory)
            old_profile = profile.read_bytes()
            self.assertEqual(call_import(source, profile, Path(directory) / 'absent/new.ini'), 2)
            source.write_text(source.read_text().replace('CC 50 F9 FB', 'CC 50 E3 02'), encoding='utf-8')
            old_source = source.read_bytes()
            output = Path(directory) / 'invalid.ini'
            self.assertEqual(call_import(source, profile, output), 2)
            self.assertFalse(output.exists())
            self.assertEqual(source.read_bytes(), old_source)
            self.assertEqual(profile.read_bytes(), old_profile)


    def test_09_corrupted_final_marker_cannot_be_imported_as_lab_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            source, profile = inputs(directory)
            sample = (ROOT / 'samples/p2_b9fb_public_redacted.txt').read_text(
                encoding='utf-8')
            # Replace only the last 13-frame terminal header, not payload data.
            original = '0x03, 0x4f, 0x30'
            corrupted = '0x03, 0x48, 0x30'
            self.assertEqual(sample.count(original), 1)
            source.write_text(sample.replace(original, corrupted), encoding='utf-8')
            old_source, old_profile = source.read_bytes(), profile.read_bytes()
            output = Path(directory) / 'must-not-be-created.ini'
            self.assertEqual(call_import(source, profile, output), 2)
            self.assertFalse(output.exists())
            self.assertEqual(source.read_bytes(), old_source)
            self.assertEqual(profile.read_bytes(), old_profile)



if __name__ == '__main__':
    unittest.main()
