"""Eight deterministic source-compatibility checks. No real ECU RX is created."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'tools'/'audit_vida_b3a10_b9fb_identity.py'
spec=importlib.util.spec_from_file_location('b3a10',SCRIPT)
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)

PUBLIC_FRAMES=[bytes.fromhex(row) for row in '''
8F 50 F9 FB 57 00 30 66
09 70 28 30 30 35 0D 0A
0A 58 58 58 58 58 58 58
0B 58 58 58 58 58 58 58
0C 58 58 58 0D 0A 32 35
0D 31 35 36 38 39 35 32
0E 0D 0A 32 39 35 0D 0A
0F 31 39 38 36 32 35 0D
08 0A 32 31 0D 0A 32 30
09 30 35 31 32 0D 0A 30
0A 30 30 30 34 33 33 38
0B 36 30 34 30 38 32 32
4F 30 36 39 33 31 0D 0A
'''.strip().splitlines()]

def packet_lines(frames=PUBLIC_FRAMES,can_id=0x01200003):
    # Transcribed historical public DiCE example: no original target ECU identity.
    rows=[]
    for i,frame in enumerate(frames):
        msg=can_id.to_bytes(4,'big')+frame
        rows.append(f'02:42:50,{578+i*15:03d} 0100 000004 PassThruReadMsgs() msg[0].Data = ['+
                    ', '.join('0x%02x'%b for b in msg)+']')
    return ('\n'.join(rows)+'\n').encode()

def lab_frames():
    # Reframe the public source after replacing all 17 redacted X bytes with
    # the virtual lab VIN. This is deliberately NOT an authentic ECU capture.
    fb,_=a.reassemble([bytes.fromhex('01 20 00 03')+f for f in PUBLIC_FRAMES])
    old=fb[11:28]
    assert old==b'X'*17
    stream=b'\x50\xF9\xFB'+fb[:11]+b'YV1CZ0002A0000001'+fb[28:]
    assert len(stream)==91
    headers=[f[0] for f in PUBLIC_FRAMES]
    return [bytes([h])+stream[i*7:(i+1)*7] for i,h in enumerate(headers)]

def lab_ini(frames=None):
    if frames is None:frames=lab_frames()
    rows=['[Vehicle]','VIN = YV1CZ0002A0000001','[D2_50]','ResponseId = 01200003','B9FBFrameCount = '+str(len(frames))]
    rows.extend('B9FBFrame%X = %s'%(i,' '.join('%02X'%v for v in frame)) for i,frame in enumerate(frames))
    return ('\n'.join(rows)+'\n').encode()

class B3A10Tests(unittest.TestCase):
    def test_01_historical_dice_b9fb_13frames_88bytes(self):
        r=a.inspect(packet_lines(),'historical_public')
        self.assertEqual((r['frame_count'],r['fb_bytes'],r['vin_field_offset']),(13,88,11))
        self.assertEqual(r['can_response_id'],'0x01200003')
        self.assertTrue(r['transport_valid'])
        self.assertFalse(r['replay_approved'])
        print('PASS VIDA B3A10 1: 13 DiCE frames/88 FB bytes/byte offset 11 recovered')
    def test_02_historical_donor_has_unverified_xc70_type_candidate(self):
        r=a.inspect(packet_lines(),'historical_public')
        self.assertEqual(r['type_field_candidate'],'295')
        self.assertEqual(r['type_catalog_model'],'XC70')
        self.assertFalse(r['type_semantics_verified_for_this_B9FB'])
        self.assertIn('B9FB_type_candidate_conflicts_with_target_model',r['inconsistencies_or_unknowns'])
        self.assertTrue(r['vin_redacted'])
        self.assertFalse(r['vehicle_identity_proven'])
        print('PASS VIDA B3A10 2: type 295 is XC70 candidate, not proof of XC90')
    def test_03_lab_vin_modelyear_and_chassis_fields_disagree(self):
        r=a.inspect(lab_ini(),'synthetic_lab',from_ini=True)
        self.assertEqual((r['vin_year_candidate'],r['target_year']),(2010,2009))
        self.assertFalse(r['chassis_matches_vin_suffix'])
        self.assertFalse(r['vin_redacted'])
        self.assertIn('VIN_model_year_conflicts_with_target',r['inconsistencies_or_unknowns'])
        self.assertIn('VIN_and_chassis_candidate_disagree',r['inconsistencies_or_unknowns'])
        print('PASS VIDA B3A10 3: lab model year and independent chassis conflict')
    def test_04_public_vs_lab_never_identical_or_verified(self):
        x=a.inspect(packet_lines(),'historical_public')
        y=a.inspect(lab_ini(),'synthetic_lab',from_ini=True)
        z=a.compare(x,y)
        self.assertFalse(z['same_fb_bytes'])
        self.assertTrue(z['same_frame_count'])
        self.assertEqual((z['historical_type_candidate'],z['lab_type_candidate']),('295','295'))
        self.assertFalse(z['replay_approved'])
        self.assertNotIn('YV1CZ',str(z))
        rawdiff=a.compare_byte_exact(packet_lines(),lab_ini())
        self.assertEqual(rawdiff['changed_fb_byte_count'],17)
        self.assertEqual(rawdiff['changed_fb_offsets'],list(range(11,28)))
        self.assertTrue(rawdiff['changes_only_in_historical_vin_field_11_to_27'])
        print('PASS VIDA B3A10 4: historical/donor and synthetic profile differ, no VIN replay')
    def test_05_missing_and_reordered_cf_are_rejected(self):
        for seq in (PUBLIC_FRAMES[:5]+PUBLIC_FRAMES[6:],
                    PUBLIC_FRAMES[:4]+[PUBLIC_FRAMES[5],PUBLIC_FRAMES[4]]+PUBLIC_FRAMES[6:]):
            with self.assertRaises(a.EvidenceError):a.inspect(packet_lines(seq),'historical_public')
        print('PASS VIDA B3A10 5: missing/reordered D2 continuation rejected')
    def test_06_wrong_can_id_or_echo_rejected(self):
        with self.assertRaises(a.EvidenceError):a.inspect(packet_lines(can_id=0x00800003),'historical_public')
        arr=PUBLIC_FRAMES.copy();arr[0]=bytes.fromhex('8F 40 F9 FB 57 00 30 66')
        with self.assertRaises(a.EvidenceError):a.inspect(packet_lines(arr),'historical_public')
        print('PASS VIDA B3A10 6: wrong CEM response ID or B9FB target rejected')
    def test_07_bad_last_frame_and_corrupt_ini_rejected(self):
        arr=PUBLIC_FRAMES.copy();arr[-1]=bytes([0x0B])+arr[-1][1:]
        with self.assertRaises(a.EvidenceError):a.inspect(packet_lines(arr),'historical_public')
        arr=lab_frames();arr[2]=arr[2][:-1]
        with self.assertRaises(a.EvidenceError):a.inspect(lab_ini(arr),'synthetic_lab',from_ini=True)
        print('PASS VIDA B3A10 7: missing 4F terminal and invalid 8-byte fixture rejected')
    def test_08_original_bytes_untouched_and_no_source_promoted(self):
        raw=packet_lines();copy=raw[:]
        for cls in ('historical_public','synthetic_lab','original_unverified'):
            report=a.inspect(raw,cls)
            self.assertFalse(report['authentic_ecu_rx_proven'])
            self.assertFalse(report['replay_approved'])
            self.assertEqual(report['source_sha256'],a.sha256(raw))
            self.assertEqual(copy,raw)
        self.assertEqual(a.YEAR_CODES['9'],2009)
        self.assertEqual(a.YEAR_CODES['A'],2010)
        self.assertEqual(a.MODEL_TYPE_CATALOG['275'],'XC90')
        print('PASS VIDA B3A10 8: original source immutable, no identity/replay promotion')

if __name__=='__main__':unittest.main()
