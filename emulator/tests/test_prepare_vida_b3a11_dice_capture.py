"""Eight synthetic B3A11 capture-intake regression groups; no real OEM bytes."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_tool(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = load_tool('b3a11', ROOT / 'tools' / 'prepare_vida_b3a11_dice_capture.py')
b3a9 = load_tool('b3a9', ROOT / 'tools' / 'audit_vida_b3a9_provenance.py')


def synthetic_capture():
    # All payload content is deliberately synthetic, not a Volvo identity.
    frames = [bytes.fromhex('00 0F FF FE CB 50 B9 FB 00 00 00 00')]
    frames.append(bytes.fromhex('01 20 00 03 8F 50 F9 FB 00 00 00 00'))
    for i in range(1, 12):
        frames.append(bytes([0x01, 0x20, 0, 3, 0x08 + i % 8]) + b'LABDATA')
    frames.append(bytes([0x01, 0x20, 0, 3, 0x4F]) + b'LABDATA')
    lines = []
    for index, frame in enumerate(frames):
        timestamp = 400 + 15 * index
        kind = 'Write' if index == 0 else 'Read'
        cells = ', '.join(f'0x{byte:02X}' for byte in frame)
        lines.append((f'02:42:50,{timestamp:03} 0100 000004 '
                      f'PassThru{kind}Msgs() msg[0].Data = [{cells}]\r\n').encode())
    return b''.join(lines)


class B3A11Tests(unittest.TestCase):
    def test_01_bounded_dice_trace_candidate_not_accepted(self):
        result = m.scan_original(synthetic_capture())
        self.assertEqual(result['status'], 'CANDIDATES_REQUIRE_INDEPENDENT_REVIEW')
        self.assertEqual(len(result['candidates']), 1)
        self.assertEqual(len(result['candidates'][0]['rx']), 13)
        manifest = m.skeleton(result, result['candidates'][0])
        self.assertEqual(manifest['source']['origin'], 'UNVERIFIED_BY_AUDITOR')
        self.assertFalse(manifest['_b3a11_review']['replay_approved'])
        self.assertIsNone(manifest['route']['baud_bps'])
        print('PASS VIDA B3A11 1: 13 synthetic D2 frames linked to TX, identity NOT proven')

    def test_02_original_vida_without_dice_payload_has_no_candidate(self):
        text = b'19:25:13,856 [J2534ChannelMana][AA][VehCom]  PassThruReadMsgs(1, PASSTHRU_MSG, 1, 5000 )\r\n'
        result = m.scan_original(text)
        self.assertEqual(result['status'], 'NO_FORMATTED_DICE_J2534_EVENTS')
        self.assertFalse(result['candidates'])
        print('PASS VIDA B3A11 2: previous original VIDA timeout log cannot invent ECU reply')

    def test_03_dropped_continuation_frame_rejected(self):
        lines = synthetic_capture().splitlines(keepends=True)
        del lines[6]
        report = m.scan_original(b''.join(lines))
        self.assertEqual(report['status'], 'NO_COMPLETE_MATCHED_RESPONSE')
        self.assertGreater(report['counters']['invalid_sequence'], 0)
        print('PASS VIDA B3A11 3: missing middle D2 frame blocks candidacy')

    def test_04_new_tx_or_duplicate_opener_blocks_borrowing(self):
        lines = synthetic_capture().splitlines(keepends=True)
        report = m.scan_original(b''.join(lines[:6] + lines[0:1] + lines[6:]))
        self.assertEqual(len(report['candidates']), 0)
        self.assertEqual(report['counters']['abandoned_on_tx'], 1)
        duplicate = lines[1].replace(b'02:42:50,415', b'02:42:50,445')
        report = m.scan_original(b''.join(lines[:4] + [duplicate] + lines[4:]))
        self.assertEqual(len(report['candidates']), 0)
        self.assertGreater(report['counters']['ambiguous_replies'], 0)
        print('PASS VIDA B3A11 4: retry and duplicate opener cannot borrow old RX')

    def test_05_wrong_can_id_and_timeout_are_not_bound(self):
        lines = synthetic_capture().splitlines(keepends=True)
        changed = lines[2].replace(b'0x01, 0x20, 0x00, 0x03', b'0x00, 0x80, 0x00, 0x03')
        # The opener's CAN ID is a different candidate than the remaining frames.
        report = m.scan_original(b''.join(lines[:2] + [changed] + lines[3:]))
        self.assertEqual(len(report['candidates']), 0)
        self.assertGreater(report['counters']['interleaved_rx'], 0)
        self.assertGreater(report['counters']['invalid_sequence'], 0)
        report = m.scan_original(synthetic_capture(), window_ms=1)
        self.assertFalse(report['candidates'])
        self.assertGreater(report['counters']['expired_window'], 0)
        print('PASS VIDA B3A11 5: CAN-ID and exact request-to-reply time guards')

    def test_06_exact_original_line_hash_and_b3a9_interface(self):
        raw = synthetic_capture()
        report = m.scan_original(raw)
        cand = report['candidates'][0]
        line = raw.splitlines(keepends=True)[0]
        manifest = m.skeleton(report, cand)
        self.assertEqual(manifest['events']['request']['line_sha256'], m.sha256(line))
        # No operator can make this passing provenance merely by a valid shape.
        self.assertEqual(b3a9.evaluate_capture(manifest, raw)['status'], 'REJECTED')
        # A fully asserted identity in a SYNTHETIC TEST still cannot approve replay.
        manifest['source']['origin'] = 'original_vehicle_dice'
        manifest['vehicle']['identity_basis'] = 'original_vehicle_record'
        manifest['vehicle']['identity_record_sha256'] = 'A' * 64
        manifest['route']['baud_bps'] = 125000
        checked = b3a9.evaluate_capture(manifest, raw)
        self.assertEqual(checked['status'], 'STRUCTURE_ONLY_PENDING_INDEPENDENT_REVIEW')
        self.assertFalse(checked['replay_approved'])
        print('PASS VIDA B3A11 6: B3A9 compatible provenance; manual claims never approve RX')

    def test_07_original_file_unchanged_and_new_directory_only(self):
        original = synthetic_capture()
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / 'original.log'
            source.write_bytes(original)
            out = root / 'review'
            result = m.collect(source, out)
            self.assertEqual(result['candidate_count'], 1)
            self.assertEqual(source.read_bytes(), original)
            man = json.loads(next(out.glob('B3A11-candidate-*.manifest.json')).read_text())
            self.assertEqual(man['source']['sha256'], m.sha256(original))
            self.assertNotIn('LABDATA', json.dumps(man))
            self.assertFalse(json.loads((out / 'B3A11-intake-report.json').read_text())['replay_approved'])
            with self.assertRaises(m.SourceError):
                m.collect(source, out)
        print('PASS VIDA B3A11 7: originals immutable, raw payload not exported, no overwrite')

    def test_08_bad_metadata_source_and_malformed_bytes_rejected(self):
        raw = synthetic_capture()
        lines = raw.splitlines(keepends=True)
        changed = lines[1].replace(b'0xF9', b'0xFA')
        self.assertFalse(m.scan_original(b''.join(lines[:1] + [changed] + lines[2:]))['candidates'])
        with self.assertRaises(m.SourceError):
            m.scan_original(raw, window_ms=30001)
        with self.assertRaises(m.SourceError):
            m.scan_original(raw.replace(b'0xCB', b'0xCG'))
        with self.assertRaises(m.SourceError):
            m.scan_original(b'')
        print('PASS VIDA B3A11 8: wrong B9FB byte, invalid token and unsafe limits rejected')


if __name__ == '__main__':
    unittest.main(verbosity=2)
