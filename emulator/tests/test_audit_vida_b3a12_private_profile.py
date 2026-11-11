"""Eight offline synthetic B3A12 tests. Never stores an owner VIN in test data."""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

p = Path(__file__).resolve().parents[1] / 'tools' / 'audit_vida_b3a12_private_profile.py'
spec = importlib.util.spec_from_file_location('b3a12', p)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
SYNTHETIC_VIN = 'YV1CR855691000000'  # unmistakably fake synthetic serial


def fake_pe():
    data = bytearray(512)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3C, 0x80)
    data[0x80:0x84] = b'PE\x00\x00'
    struct.pack_into('<H', data, 0x84, 0x14c)
    return bytes(data)


class B3A12PrivateProfileTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        base = Path(self.dir.name)
        self.lab = base / 'B3A7'
        self.lab.mkdir()
        self.ident = base / 'private-identity.json'
        self.ini = self.lab / 'virtualcar.ini'
        self.binary = fake_pe()
        (self.lab / 'VirtualCarJ2534.dll').write_bytes(self.binary)
        (self.lab / 'b3a7-manifest.json').write_text(json.dumps({
            'sourceCommit': a.EXPECTED_B3A7_HEAD,
            'dllSha256': a.EXPECTED_B3A7_DLL_SHA256}), encoding='utf-8')
        self.data = {'vin': SYNTHETIC_VIN, 'model_year': 2009, 'chassis': SYNTHETIC_VIN[-6:],
                     'engine': 'B8444S', 'transmission': 'TF-80SC AWD',
                     'vin_from_ecu': False, 'verified_live_cem_reply': False}
        self.save_identity()
        self.ini.write_text('[Vehicle]\nVIN='+SYNTHETIC_VIN+'\nModelYear=2009\n'
            '[Diagnostics]\nEnableVidaIso9141Lab=1\nEnableVidaKlineTxAckLab=1\n'
            'EnableVidaFiveBaudObserverLab=1\nEnableVidaCanPsLab=1\n'
            'StrictJ2534Filters=1\nBackendTelemetryEnabled=0\n'
            '[P2]\nStrictRouting=1\n[D2_40]\nB9FBFrameCount=0\n'
            '[D2_50]\nB9FBFrameCount=0\n[PassiveCAN]\nEnabled=0\n'
            '[PassiveTrace]\nEnabled=0\n', encoding='utf-8')
    def save_identity(self):
        self.ident.write_text(json.dumps(self.data), encoding='utf-8')
    def run_audit(self, registry='REGISTERED_EXACT'):
        with patch.object(a, 'digest', side_effect=lambda data: a.EXPECTED_B3A7_DLL_SHA256 if data == self.binary else '0'*64):
            return a.audit(self.lab, self.ident, probe=lambda _:registry)
    def rejected(self, message=None):
        with self.assertRaises(a.ProfileError) as err:
            self.run_audit()
        if message:
            self.assertIn(message, str(err.exception))

    def test_01_private_identity_match_without_export(self):
        result=self.run_audit()
        self.assertEqual(result['profile_check'], 'PASS')
        self.assertEqual(result['registry32'], 'REGISTERED_EXACT')
        self.assertNotIn(SYNTHETIC_VIN, json.dumps(result))
        self.assertFalse(result['private_identity_exported'])
        print('PASS VIDA B3A12 1: private VIN matches lab; no VIN emitted')

    def test_02_installed_vin_mismatch_refused(self):
        self.ini.write_text(self.ini.read_text().replace(SYNTHETIC_VIN,'YV1CR855691000001'))
        self.rejected('installed LAB VIN')
        print('PASS VIDA B3A12 2: stale lab VIN cannot be accepted')

    def test_03_model_year_and_chassis_guarded(self):
        self.data['chassis']='000001';self.save_identity()
        self.rejected('chassis')
        self.data['chassis']=SYNTHETIC_VIN[-6:];self.data['model_year']=2008;self.save_identity()
        self.rejected('year')
        print('PASS VIDA B3A12 3: year/chassis consistency required')

    def test_04_x86_binary_header(self):
        b=bytearray(self.binary);struct.pack_into('<H',b,0x84,0x8664)
        self.binary=bytes(b);(self.lab/'VirtualCarJ2534.dll').write_bytes(self.binary)
        self.rejected('Windows x86')
        print('PASS VIDA B3A12 4: x64 DLL rejected despite hash override')

    def test_05_dll_hash_and_manifest_mismatch(self):
        with self.assertRaises(a.ProfileError):a.audit(self.lab,self.ident,probe=lambda _:'REGISTERED_EXACT')
        (self.lab/'b3a7-manifest.json').write_text(json.dumps({'sourceCommit':'0'*40,'dllSha256':a.EXPECTED_B3A7_DLL_SHA256}))
        self.rejected('manifest')
        print('PASS VIDA B3A12 5: binary SHA and commit manifest both enforced')

    def test_06_b9fb_injection_and_passive_bus_refused(self):
        original=self.ini.read_text()
        self.ini.write_text(original.replace('B9FBFrameCount=0','B9FBFrameCount=13',1));self.rejected('B9FB')
        self.ini.write_text(original.replace('[PassiveCAN]\nEnabled=0','[PassiveCAN]\nEnabled=1'))
        self.rejected('PassiveCAN')
        print('PASS VIDA B3A12 6: no synthetic CEM frames/passive CAN')

    def test_07_missing_critical_gate_fails_closed(self):
        self.ini.write_text(self.ini.read_text().replace('EnableVidaFiveBaudObserverLab=1','EnableVidaFiveBaudObserverLab=0'))
        self.rejected('EnableVidaFiveBaudObserverLab')
        print('PASS VIDA B3A12 7: required VIDA lab observer flag cannot drift')

    def test_08_registry_mismatch_and_no_vida_claims(self):
        with self.assertRaises(a.ProfileError):self.run_audit('REGISTRY_MISMATCH')
        r=self.run_audit('NOT_REGISTERED')
        self.assertEqual(r['original_vida_automatic_readvin'],'NOT_PROVEN')
        self.assertEqual(r['runtime_use_of_profile'],'NOT_PROVEN_UNTIL_VIDA_LOADS_LAB_AFTER_CHANGE')
        print('PASS VIDA B3A12 8: registry isolation; no unsupported runtime claims')


if __name__=='__main__':unittest.main(verbosity=2)
