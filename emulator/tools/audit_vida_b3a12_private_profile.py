#!/usr/bin/env python3
"""Read-only B3A12 verification of a PRIVATE XC90 V8 MY2009 B3A7 LAB profile.

No VIN/chassis/paths/hashes of private identity in JSON or terminal output.
No J2534 calls, VIDA modifications, Registry32 writes, or ECU RX fabrication.
The original VIDA manual VEHICLE PROFILE proof is a distinct acceptance gate.
"""
from __future__ import annotations
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys

EXPECTED_B3A7_HEAD = '0722b530aa48a7f1790d5f0dd1dddbe790518705'
EXPECTED_B3A7_DLL_SHA256 = 'AFB19B26C3BA6BE11D3ADD321EC7A90BEF4E005F36EC7B963AC0C8F25E4EF210'
REGISTRY_KEY = r'SOFTWARE\PassThruSupport.04.04\VirtualCar VIDA KLINE B3A7 PR319'
REGISTRY_NAME = 'J2534 VIDA KLINE B3A7 PR319 (LAB)'
REQUIRED_FLAGS = ('EnableVidaIso9141Lab', 'EnableVidaKlineTxAckLab',
                  'EnableVidaFiveBaudObserverLab', 'EnableVidaCanPsLab',
                  'StrictJ2534Filters')
VIN_PATTERN = re.compile(r'^YV1CR8556[0-9A-HJ-NPR-Z]{8}$', re.ASCII)

class ProfileError(ValueError):
    pass


def ensure(cond, reason):
    if not cond:
        raise ProfileError(reason)


def digest(blob):
    return hashlib.sha256(blob).hexdigest().upper()


def _pe32_machine(data):
    ensure(len(data) >= 0x80 and data[:2] == b'MZ', 'DLL is not PE/MZ')
    offset = struct.unpack_from('<I', data, 0x3C)[0]
    ensure(offset >= 0x40 and offset + 6 <= len(data), 'invalid PE header offset')
    ensure(data[offset:offset+4] == b'PE\x00\x00', 'DLL PE signature missing')
    return struct.unpack_from('<H', data, offset+4)[0]


def _profile_config(path):
    parser = configparser.ConfigParser(interpolation=None, strict=True, inline_comment_prefixes=None)
    try:
        parser.read_string(Path(path).read_text(encoding='utf-8-sig'))
    except (configparser.Error, UnicodeError, OSError) as ex:
        raise ProfileError('invalid LAB INI structure') from ex
    return parser


def registry_status(lab, probe=None):
    if probe is not None:
        return probe(lab)
    if os.name != 'nt':
        return 'NOT_CHECKED_ON_THIS_OS'
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REGISTRY_KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_32KEY) as reg:
            name = winreg.QueryValueEx(reg, 'Name')[0]
            library = winreg.QueryValueEx(reg, 'FunctionLibrary')[0]
    except FileNotFoundError:
        return 'NOT_REGISTERED'
    except OSError as exc:
        raise ProfileError('unable to inspect J2534 Registry32 adapter') from exc
    if name != REGISTRY_NAME:
        return 'REGISTRY_MISMATCH'
    if os.path.normcase(os.path.normpath(library)) != os.path.normcase(os.path.normpath(str(lab / 'VirtualCarJ2534.dll'))):
        return 'REGISTRY_MISMATCH'
    return 'REGISTERED_EXACT'


def audit(lab, private_identity, probe=None):
    lab = Path(lab)
    identity = json.loads(Path(private_identity).read_text(encoding='utf-8-sig'))
    manifest = json.loads((lab / 'b3a7-manifest.json').read_text(encoding='utf-8-sig'))
    dll = (lab / 'VirtualCarJ2534.dll').read_bytes()
    ensure(digest(dll) == EXPECTED_B3A7_DLL_SHA256, 'B3A7 DLL SHA256 mismatch')
    ensure(_pe32_machine(dll) == 0x14c, 'B3A7 DLL is not Windows x86')
    ensure(manifest.get('sourceCommit') == EXPECTED_B3A7_HEAD and
           manifest.get('dllSha256', '').upper() == EXPECTED_B3A7_DLL_SHA256,
           'B3A7 source/DLL manifest mismatch')
    cfg = _profile_config(lab / 'virtualcar.ini')
    ensure(cfg.has_section('Vehicle'), 'Vehicle section missing')
    vin = cfg.get('Vehicle', 'VIN', fallback='').strip()
    private_vin = identity.get('vin')
    ensure(isinstance(private_vin, str) and VIN_PATTERN.fullmatch(private_vin) is not None,
           'private MY2009 target VIN shape invalid')
    ensure(vin == private_vin, 'installed LAB VIN does not match private identity')
    ensure(cfg.get('Vehicle', 'ModelYear', fallback='') == '2009' and
           identity.get('model_year') == 2009 and private_vin[9] == '9' and private_vin[10] == '1',
           'MY2009 year or plant mismatch')
    ensure(identity.get('chassis') == private_vin[-6:], 'private identity chassis mismatch')
    ensure(identity.get('engine') == 'B8444S' and identity.get('transmission') == 'TF-80SC AWD',
           'private vehicle powertrain mismatch')
    ensure(identity.get('vin_from_ecu') is False and identity.get('verified_live_cem_reply') is False,
           'local profile must not assert a verified ECU VIN response')
    for key in REQUIRED_FLAGS:
        ensure(cfg.get('Diagnostics', key, fallback='') == '1', f'Diagnostics.{key} is not enabled')
    ensure(cfg.get('Diagnostics', 'BackendTelemetryEnabled', fallback='') == '0', 'backend telemetry changed')
    ensure(cfg.get('P2', 'StrictRouting', fallback='') == '1', 'strict P2 routing disabled')
    for section in ('D2_40', 'D2_50'):
        ensure(cfg.get(section, 'B9FBFrameCount', fallback='') == '0',
               f'B9FB synthetic reply fixture unexpectedly enabled on {section}')
    for section in ('PassiveCAN', 'PassiveTrace'):
        ensure(cfg.get(section, 'Enabled', fallback='') == '0',
               f'{section} unexpectedly enabled')
    reg = registry_status(lab, probe)
    ensure(reg not in ('REGISTRY_MISMATCH',), 'J2534 Registry32 target does not match exact B3A7 DLL')
    return {
        'stage': 'B3A12-private-vehicle-profile',
        'profile_check': 'PASS',
        'registry32': reg,
        'b3a7_head': EXPECTED_B3A7_HEAD,
        'b3a7_exact_dll': 'PASS_WINDOWS_X86_SHA256',
        'vehicle_family': 'XC90 P2 V8 MY2009',
        'vehicle_vin_matches_private_identity': True,
        'chassis_consistent_with_private_vin': True,
        'vin_present_in_lab_ini': True,
        'private_identity_exported': False,
        'b9fb_synthetic_ecu_rx_enabled': False,
        'five_baud_keywords_sourced': False,
        'original_vida_manual_profile': 'SEPARATE_OPERATOR_SCREENSHOT',
        'original_vida_automatic_readvin': 'NOT_PROVEN',
        'original_ecu_rx': 'NOT_PROVEN',
        'runtime_use_of_profile': 'NOT_PROVEN_UNTIL_VIDA_LOADS_LAB_AFTER_CHANGE',
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lab', type=Path, required=True)
    p.add_argument('--private-identity', type=Path, required=True)
    p.add_argument('--out', type=Path, help='optional new aggregate JSON; existing paths refused')
    opts = p.parse_args(argv)
    try:
        output = audit(opts.lab, opts.private_identity)
        report = json.dumps(output, ensure_ascii=False, indent=2) + '\n'
        if opts.out:
            with opts.out.open('x', encoding='utf-8') as f:
                f.write(report)
        print('B3A12 PASS: private XC90 V8 MY2009 LAB identity, B3A7 DLL and strict no-RX settings')
        print('J2534 Registry32:', output['registry32'])
        print('Original VIDA automatic ReadVIN: NOT PROVEN')
        if not opts.out:
            print(report)
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as ex:
        p.exit(2, f'B3A12 FAIL-CLOSED: {ex}\n')

if __name__ == '__main__':
    sys.exit(main())
