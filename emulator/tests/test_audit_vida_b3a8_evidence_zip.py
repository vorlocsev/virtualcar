"""Eight synthetic, read-only B3A8 evidence-gate regression groups.

Tests use no real VIDA files, VINs, ECM/CEM replies or vehicle secrets.
"""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "audit_vida_b3a8_evidence_zip.py"
spec = importlib.util.spec_from_file_location("b3a8_zip_audit", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def synthetic_members():
    req = [("726", "22F114"), ("40", "B9FB"), ("50", "B9FB"),
           ("50", "B9FB"), ("50", "B9FB"), ("40", "B9FB"),
           ("50", "B9FB"), ("51", "B9F0")]
    vida_lines = [f"12:00:00,001 [DiagConnection  ][001][VehCom]  VehComm request: Ecu '{a}', Message '{b}' " for a, b in req]
    waits = [75, 60, 50, 100, 50, 60, 50] + [5000] * 20
    for ms in waits:
        vida_lines.append(f"12:00:01,001 [J2534ChannelMana][001][VehCom]  PassThruReadMsgs(1, PASSTHRU_MSG, 1, {ms} ) - SyntheticTest")
        vida_lines.append('12:00:01,002 [J2534ChannelMana][001][Error]   J2534 function:PassThruReadMsgs failed with return value:ERR_TIMEOUT')
    vida_lines += ['12:00:02,001 [J2534ChannelMana][001][VehCom]  Calling FiveBaudInit on address 0x51',
                   '12:00:55,001 [DiagConnection  ][001][Error]  Could not retrieve VIN from vehicle']
    vida_suffix = ('\r\n'.join(vida_lines) + '\r\n').encode()
    fields = [1, 3, 10400, 0, 1, 1, 1, 1, 1, 2, 1, 1]
    meta = ' '.join(f'{v:08X}'[i:i+2] for v in fields for i in range(0, 8, 2))
    virtual_messages = [
        'P3 CEM F114 probe: no configured CEM fixture; no response',
        *['P2 D2 read command: no validated response fixture'] * 3,
        *['P2 D2 strict route rejected (no fixture emitted)'] * 3,
        *['VIDA B3A6 KLINE exact original write LOCAL ACK ONLY (NO BUS/ECU TX/RX) 84 40 13 B2 F0 00'] * 3,
        'VIDA B3A6 KLINE exact original write LOCAL ACK ONLY (NO BUS/ECU TX/RX) 83 51 13 B9 F0',
        'VIDA B3A6 KLINE exact original write LOCAL ACK ONLY (NO BUS/ECU TX/RX) 82 51 13 A0',
        'VIDA B3A7 FIVE_BAUD_INIT ABI channel/proto/baud/mod/pointers/lengths (BE) ' + meta,
        'VIDA B3A7 FIVE_BAUD_INIT original target (1 byte) 51',
        'ISO9141 LAB FIVE_BAUD_INIT: no verified ECU keywords; unsupported'
    ]
    virtual_suffix = ('\r\n'.join('[PID=0000ABCD IEXPLORE.EXE] ' + m for m in virtual_messages) + '\r\n').encode()
    prefix_v, prefix_e = b'older original VIDA log\n', b'[PID=00000001 OTHER.EXE] older legacy log\n'
    manifest = {'sourceCommit': audit.EXPECTED_HEAD, 'dllSha256': audit.EXPECTED_DLL_SHA256}
    arm = {'head': audit.EXPECTED_HEAD, 'dllSha256': audit.EXPECTED_DLL_SHA256,
           'vidaOffset': len(prefix_v), 'virtualOffset': len(prefix_e)}
    acceptance = {'sourceHead': audit.EXPECTED_HEAD, 'dllSha256': audit.EXPECTED_DLL_SHA256,
                  'runtimeIdentity': 'CONFIRMED', 'b3a7ObserverGate': 'B3A7_OBSERVER_CONFIRMED',
                  'result': 'OBSERVATION_ONLY_NO_ECU_RX_PROOF', 'VIDAReadVinEvent': True,
                  'vidaLoadsExactDll': True, 'unredacted': True,
                  'newVidaBytes': len(vida_suffix), 'newVirtualBytes': len(virtual_suffix),
                  'activeVidaPidHex': ['0000ABCD'], 'selectedSamePidLines': len(virtual_messages),
                  'originalVidaVinError': True, 'VINReadSucceeded': 'NOT_PROVEN',
                  'authenticECURx': 'NOT_PROVEN'}
    ini = b'''[D2_40]
B9FBFrameCount=0
[D2_50]
B9FBFrameCount=0
[Diagnostics]
EnableVidaIso9141Lab=1
EnableVidaKlineTxAckLab=1
EnableVidaFiveBaudObserverLab=1
'''
    return {'b3a7-manifest.json': manifest, 'b3a7-arm.json': arm,
            'B3A7-acceptance.json': acceptance, 'virtualcar-exact.ini': ini,
            'VIDA-original-full.log': prefix_v + vida_suffix, 'VIDA-since-arm.raw': vida_suffix,
            'VirtualCar-original-full.log': prefix_e + virtual_suffix,
            'VirtualCar-since-arm.raw': virtual_suffix}


def to_zip(path, data):
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, value in data.items():
            if isinstance(value, dict):
                value = json.dumps(value, sort_keys=True).encode()
            z.writestr('evidence-synthetic\\' + name, value)


class B3A8EvidenceTests(unittest.TestCase):
    def check(self, change=None, should_fail=False):
        data = synthetic_members()
        if change:
            change(data)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, 'synthetic-VIDA-B3A7.zip')
            to_zip(path, data)
            if should_fail:
                with self.assertRaises(audit.EvidenceError):
                    audit.audit_zip(path)
            else:
                return audit.audit_zip(path)

    def test_01_source_order_timeouts_and_only_aggregate_json(self):
        report = self.check()
        self.assertEqual((len(report['readvin']['requests']), report['readvin']['read_timeout_count']), (8, 27))
        self.assertFalse(report['replay_approved'])
        self.assertTrue(all(not item['replay_approved'] for item in report['readvin']['requests']))
        self.assertNotIn('older original VIDA log', json.dumps(report))
        self.assertNotIn('SyntheticTest', json.dumps(report))
        print('PASS VIDA B3A8 1: byte-exact synthetic ZIP/source report, no raw data')

    def test_02_suffix_and_original_offsets_are_immutable(self):
        self.check(lambda data: data.__setitem__('VIDA-original-full.log', b'altered prefix' + data['VIDA-since-arm.raw']), True)
        self.check(lambda data: data['b3a7-arm.json'].__setitem__('virtualOffset', 0), True)
        print('PASS VIDA B3A8 2: suffix mismatch and tampered original offsets rejected')

    def test_03_exact_head_and_binary_digest_provenance_required(self):
        self.check(lambda data: data['b3a7-manifest.json'].__setitem__('sourceCommit', '0' * 40), True)
        self.check(lambda data: data['B3A7-acceptance.json'].__setitem__('dllSha256', '0' * 64), True)
        print('PASS VIDA B3A8 3: exact HEAD and staged x86 SHA provenance mandatory')

    def test_04_only_one_original_vida_pid_allowed(self):
        self.check(lambda data: data.__setitem__(
            'VirtualCar-since-arm.raw', data['VirtualCar-since-arm.raw'].replace(b'0000ABCD', b'00001234', 1)), True)
        print('PASS VIDA B3A8 4: mixed PID cannot be attributed to original VIDA')

    def test_05_missing_or_extra_readvin_request_is_detected(self):
        self.check(lambda data: data.__setitem__(
            'VIDA-since-arm.raw', data['VIDA-since-arm.raw'].replace(b"Message 'B9FB'", b"Message 'B9F0'", 1)), True)
        print('PASS VIDA B3A8 5: incorrect request/target sequence blocked')

    def test_06_missing_timeout_must_not_be_counted_as_success(self):
        self.check(lambda data: data.__setitem__(
            'VIDA-since-arm.raw', data['VIDA-since-arm.raw'].replace(b'ERR_TIMEOUT', b'ERR_OK', 1)), True)
        print('PASS VIDA B3A8 6: one ambiguous ReadMsgs result invalidates evidence gate')

    def test_07_possible_ecu_reply_requires_manual_source_review(self):
        self.check(lambda data: data.__setitem__(
            'VIDA-since-arm.raw', data['VIDA-since-arm.raw'] +
            b'12:00:01,009 [J2534ChannelMana][001][VehCom] <--- (0) 00,00,07,2E,62,F1,14,00\r\n'), True)
        print('PASS VIDA B3A8 7: unverified RX cannot silently become ECU fixture')

    def test_08_lab_fixture_or_abi_changes_fail_closed(self):
        self.check(lambda data: data.__setitem__(
            'virtualcar-exact.ini', data['virtualcar-exact.ini'].replace(b'B9FBFrameCount=0', b'B9FBFrameCount=1', 1)), True)
        self.check(lambda data: data.__setitem__(
            'VirtualCar-since-arm.raw', data['VirtualCar-since-arm.raw'].replace(b'original target (1 byte) 51', b'original target (1 byte) 52')), True)
        print('PASS VIDA B3A8 8: synthetic fixture and source ABI changes fail closed')


if __name__ == '__main__':
    unittest.main()
