"""Regression for the read-only CEM M32C -> D2 B9FB/B9FC fixture builder.
All test VINs and blocks are synthetic, not copied from vehicle dumps.
"""
import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fc_fixture',ROOT/'tools'/'build_cem_flash_fixture.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
VIN=b'YV1CZ0002A0000001' # Synthetic public test VIN


def synthetic_flash():
    fields=[b'005', VIN, b'251568952', b'275', VIN[-6:], b'21', b'200512', b'00004338604082206931']
    # Adapt trailing placeholder to exactly 88 bytes without introducing identity:
    raw=b'\r\n'.join(fields)+b'\r\n'
    assert len(raw)==82, len(raw)
    fb=bytes([87,0,0x30,0x68,0x25,0x62])+raw
    vals=bytes((i*5)%7 for i in range(140))
    fc=bytes((140,sum(vals)&255))+vals
    b=bytearray(b'\xff'*(320*1024));b[mod.FB_OFFSET:mod.FB_OFFSET+88]=fb;b[mod.FC_OFFSET:mod.FC_OFFSET+142]=fc
    return bytes(b)

class CEMFixtureTests(unittest.TestCase):
    def test_observed_layout(self):
        fb,fc,vin,year=mod.inspect_flash(synthetic_flash())
        self.assertEqual(len(fb),88);self.assertEqual(len(fc),142)
        self.assertEqual(vin,VIN.decode());self.assertEqual(year,2010)
        fbframes=mod.d2_frames(fb,0x50,0xFB)
        fcframes=mod.d2_frames(fc,0x50,0xFC)
        self.assertEqual(len(fbframes),13);self.assertEqual(len(fcframes),21)
        self.assertEqual(fbframes[0][:4],bytes.fromhex('8f 50 f9 fb'))
        self.assertEqual(fbframes[-1][0],0x4f)
        self.assertEqual(fcframes[0][:4],bytes.fromhex('8f 50 f9 fc'))
        self.assertEqual(fcframes[-1][0],0x4d)
        self.assertEqual(b''.join(f[1:] for f in fbframes)[3:],fb)
        self.assertEqual(b''.join(f[1:] for f in fcframes)[:145][3:],fc)
    def test_bad_checksum_rejected(self):
        b=bytearray(synthetic_flash());b[mod.FC_OFFSET+1]^=1
        with self.assertRaisesRegex(ValueError,'checksum'):mod.inspect_flash(bytes(b))
    def test_wrong_chassis_rejected(self):
        b=bytearray(synthetic_flash());b[mod.FB_OFFSET+6+len(b'005\r\n')+17+len(b'\r\n')+len(b'251568952\r\n275\r\n')] = ord('2')
        with self.assertRaisesRegex(ValueError,'chassis'):mod.inspect_flash(bytes(b))
    def test_other_model_rejected(self):
        b=bytearray(synthetic_flash());fb=b[mod.FB_OFFSET:mod.FB_OFFSET+88];idx=fb.find(b'275');self.assertGreater(idx,0)
        b[mod.FB_OFFSET+idx:mod.FB_OFFSET+idx+3]=b'295'
        with self.assertRaisesRegex(ValueError,'275'):mod.inspect_flash(bytes(b))
    def test_size_rejected(self):
        with self.assertRaises(ValueError):mod.inspect_flash(b'\0'*512)
    def test_profile_not_published_without_explicit_optin(self):
        fb,fc,vin,year=mod.inspect_flash(synthetic_flash())
        ini=mod.build_ini((ROOT/'virtualcar-p2.ini').read_text(),fb,fc,vin,year)
        self.assertIn('FrameCount = 21',ini)
        self.assertIn('B9FBFrameCount = 13',ini)
        self.assertIn('FC_response_CAN_ID_unverified',ini)
        self.assertIn(VIN.decode(),ini)

if __name__=='__main__':unittest.main()
