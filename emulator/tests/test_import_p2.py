"""Tiny regression suite for the read-only P2 trace importer."""
import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('import_p2_trace',ROOT/'tools'/'import_p2_trace.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class P2ImportTests(unittest.TestCase):
    def test_public_b9f0_excerpt(self):
        blob=(ROOT/'samples'/'p2_b9f0_public_excerpt.txt').read_text().splitlines()
        sessions=module.sessions(blob,0x50,0xF0)
        self.assertEqual(len(sessions),1)
        self.assertEqual(len(sessions[0]),3)
        self.assertEqual(sessions[0][0][0],0x01000003)
        self.assertEqual(sessions[0][0][1][:4],b'\x8f\x50\xf9\xf0')

    def test_no_protected_commands_matched(self):
        blob=['TX (app request) 00 0F FF FE CB 50 B8 FB 00 00 00 00',
              'RX (simulated) 01 20 00 03 8F 50 F9 FB 00 00 00 00']
        self.assertEqual(module.sessions(blob,0x50,0xFB),[])

    def test_redact_vin_cross_frame(self):
        vin=b'YV1CZ0002A0000001'
        frames=[(0x01200003,bytes([0x0A])+vin[:7]),
                (0x01200003,bytes([0x0B])+vin[7:14]),
                (0x01200003,bytes([0x0C])+vin[14:]+b'\r\nAA')]
        redacted,n=module.redact_vin(frames)
        self.assertEqual(n,1)
        self.assertNotIn(vin,b''.join(row[1][1:] for row in redacted))
        self.assertEqual([row[1][0] for row in redacted],[0x0A,0x0B,0x0C])

    def test_public_b9fb_13frame_redacted(self):
        sample=(ROOT/'samples'/'p2_b9fb_public_redacted.txt').read_text().splitlines()
        found=module.sessions(sample,0x50,0xFB)
        self.assertEqual(len(found),1)
        frames=found[0]
        self.assertEqual(len(frames),13)
        self.assertEqual(frames[0][0],0x01200003)
        self.assertEqual(frames[0][1][:4],bytes.fromhex('8f 50 f9 fb'))
        module.validate_response(frames,0x50,0xFB)
        payload=b''.join(data[1:] for _,data in frames)
        self.assertIn(b'X'*17,payload)
        self.assertEqual(payload.count(b'X'*17),1)
        lab=module.set_lab_vin(frames,'YV1CZ0002A0000001')
        self.assertIn(b'YV1CZ0002A0000001',b''.join(data[1:] for _,data in lab))
        self.assertEqual([data[0] for _,data in frames],[data[0] for _,data in lab])

    def test_reject_invalid_d2_sequence(self):
        frames=module.sessions((ROOT/'samples'/'p2_b9fb_public_redacted.txt').read_text().splitlines(),0x50,0xFB)[0]
        with self.assertRaises(ValueError):
            module.validate_response(frames[:-1],0x50,0xFB)
        altered=list(frames)
        wrong=bytearray(altered[4][1]);wrong[0]=0x0E
        altered[4]=(altered[4][0],bytes(wrong))
        with self.assertRaises(ValueError):
            module.validate_response(altered,0x50,0xFB)
        with self.assertRaises(ValueError):
            module.validate_response(frames,0x40,0xFB)
        with self.assertRaises(ValueError):
            module.set_lab_vin(frames,'INVALID')

    def test_known_13frame_final_header_all_seven_shorter_values_rejected(self):
        # The public response is already redacted; all modifications are synthetic.
        original=module.sessions(
            (ROOT/'samples'/'p2_b9fb_public_redacted.txt').read_text().splitlines(),
            0x50,0xFB)[0]
        self.assertEqual(len(original),13)
        self.assertEqual(original[-1][1][0],0x4F)
        module.validate_response(original,0x50,0xFB)
        for final in range(0x48,0x4F):
            with self.subTest(final=f'{final:02X}'):
                broken=list(original)
                broken[-1]=(broken[-1][0],bytes([final])+broken[-1][1][1:])
                with self.assertRaisesRegex(ValueError,'Invalid final D2 marker'):
                    module.validate_response(broken,0x50,0xFB)

    def test_other_d2_lengths_and_start_family_not_forced_to_4f(self):
        original=module.sessions(
            (ROOT/'samples'/'p2_b9fb_public_redacted.txt').read_text().splitlines(),
            0x50,0xFB)[0]
        # Twelve-frame and 0x10-series are generic, unverified formats.
        twelve=list(original[:12])
        twelve[-1]=(twelve[-1][0],bytes([0x48])+twelve[-1][1][1:])
        module.validate_response(twelve,0x50,0xFB)
        alternative=list(original)
        for i,(can_id,data) in enumerate(alternative):
            if i==0: head=0x97
            elif i==len(alternative)-1: head=0x48
            else: head=0x10|(i&7)
            alternative[i]=(can_id,bytes([head])+data[1:])
        module.validate_response(alternative,0x50,0xFB)
        # These transport-level tests never assert OEM identity acceptance.

    def test_missing_rx_does_not_form_session(self):
        self.assertEqual(module.sessions(['TX (app request) 00 0F FF FE CB 50 B9 FB 00 00 00 00'],0x50,0xFB),[])

if __name__=='__main__': unittest.main()
