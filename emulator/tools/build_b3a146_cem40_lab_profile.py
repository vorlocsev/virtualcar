#!/usr/bin/env python3
"""Opt-in, strictly synthetic CEM_40/125k B9FB (+optional B9F0) lab INI.

Historical 0x50 fields are deliberately retargeted as a transport experiment,
NOT as OEM XC90 2009 data. The active INI is never modified automatically.
"""
import argparse
import configparser
import io
import json
import os
from pathlib import Path
import re
import sys

TEMPLATE = Path(__file__).resolve().parents[1] / 'virtualcar-p2-b9fb-lab-vin.ini'
EXPECTED_TEMPLATE_VIN = 'YV1CZ0002A0000001'
MAX_BYTES = 512 * 1024
FRAME_HEADERS = (0x8F, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E,
                 0x0F, 0x08, 0x09, 0x0A, 0x0B, 0x4F)
VIN_RE = re.compile(r'[A-HJ-NPR-Z0-9]{17}\Z')
FRAME_RE = re.compile(r'(?:[0-9A-Fa-f]{2}[ \t:\-]*){8}\Z')


def _unique_json(pairs):
    output, keys = {}, set()
    for key, value in pairs:
        if not isinstance(key, str) or key.casefold() in keys:
            raise ValueError('ambiguous json key')
        output[key] = value
        keys.add(key.casefold())
    return output


def _identity(raw):
    if len(raw.encode('utf-8')) > 128 * 1024:
        raise ValueError('oversize identity')
    data = json.loads(raw, object_pairs_hook=_unique_json)
    if not isinstance(data, dict):
        raise ValueError('invalid identity type')
    roots = [data] if 'VIN' in data else []
    roots += [data[name] for name in ('Vehicle', 'Identity', 'VehicleIdentity')
              if isinstance(data.get(name), dict) and 'VIN' in data[name]]
    if len(roots) != 1:
        raise ValueError('ambiguous identity scope')
    vin, year = roots[0].get('VIN'), roots[0].get('ModelYear')
    if not isinstance(vin, str) or not VIN_RE.fullmatch(vin):
        raise ValueError('invalid synthetic vin shape')
    if type(year) not in (str, int) or str(year) != '2009':
        raise ValueError('MY2009 required')
    return vin


def _cfg(source):
    if len(source.encode('utf-8')) > MAX_BYTES:
        raise ValueError('oversize template')
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.read_string(source)
    if len({name.casefold() for name in parser.sections()}) != len(parser.sections()):
        raise ValueError('ambiguous section names')
    return parser


def _frame(text):
    if not text or len(text) > 510 or not FRAME_RE.fullmatch(text.strip()):
        raise ValueError('invalid frame bytes')
    frame = bytes.fromhex(re.sub(r'[ \t:\-]', '', text))
    if len(frame) != 8:
        raise ValueError('frame size')
    return frame


def _render(frame):
    return frame.hex(' ').upper()


def build_profile(template_text, identity_json, *, enable_synthetic_b9f0=False):
    cfg = _cfg(template_text)
    vin = _identity(identity_json)
    if (cfg.get('Vehicle', 'VIN') != EXPECTED_TEMPLATE_VIN or
        cfg.get('P2', 'StrictRouting') != '1' or
        cfg.get('D2_40', 'ResponseId').strip().upper() != '00800003' or
        cfg.get('D2_50', 'ResponseId').strip().upper() != '01200003' or
        cfg.get('D2_50', 'B9FBFrameCount') != '13' or
        cfg.get('D2_40', 'B9FBFrameCount') != '0' or
        cfg.has_option('D2_50', 'FrameCount') or
        cfg.has_option('D2_40', 'FrameCount')):
        raise ValueError('unexpected synthetic template basis')
    for name in ('D2_40_B9F0', 'D2_50_B9F0', 'D2_40_B9FC', 'D2_50_B9FC'):
        if cfg.get(name, 'FrameCount') != '0':
            raise ValueError('unverified positive fixture in template')
    source_frames = [_frame(cfg.get('D2_50', f'B9FBFrame{i:X}'))
                     for i in range(13)]
    if tuple(f[0] for f in source_frames) != FRAME_HEADERS:
        raise ValueError('wrong canonical D2 frame sequence')
    data = b''.join(f[1:] for f in source_frames)
    if (len(data) != 91 or data[:3] != b'\x50\xf9\xfb' or
        data[14:31] != EXPECTED_TEMPLATE_VIN.encode('ascii') or
        data[3:5] != b'\x57\x00'):
        raise ValueError('unsupported synthetic data contract')
    observed = data[3:]
    fields = observed[6:].split(b'\r\n')
    if (len(observed) != 88 or len(fields) != 9 or fields[-1] != b'' or
        tuple(len(f) for f in fields[:-1]) != (3, 17, 9, 3, 6, 2, 6, 20)):
        raise ValueError('unexpected 88-byte historical example shape')
    # Explicit research/lab transposition of a 0x50-era synthetic donor.
    # Its remaining fields may contradict MY2009 and are NOT rewritten.
    transformed = b'\x40' + data[1:14] + vin.encode('ascii') + data[31:]
    assert len(transformed) == 91
    cfg.set('D2_40', 'B9FBFrameCount', '13')
    for i, head in enumerate(FRAME_HEADERS):
        cfg.set('D2_40', f'B9FBFrame{i:X}',
                _render(bytes((head,)) + transformed[7*i:7*(i+1)]))
    cfg.set('D2_50', 'B9FBFrameCount', '0')
    for i in range(13):
        cfg.remove_option('D2_50', f'B9FBFrame{i:X}')
    if enable_synthetic_b9f0:
        # Synthetic *marker*, intentionally not a plausible OEM part number.
        msg = b'\x40\xf9\xf0SIM-CEM-125'  # 14 payload bytes = 2 x 7
        assert len(msg) == 14
        cfg.set('D2_40_B9F0', 'ResponseId', '00800003')
        cfg.set('D2_40_B9F0', 'FrameCount', '2')
        cfg.set('D2_40_B9F0', 'Frame0', _render(b'\x8f'+msg[:7]))
        cfg.set('D2_40_B9F0', 'Frame1', _render(b'\x4f'+msg[7:]))
    cfg.set('Vehicle', 'VIN', vin)
    cfg.set('Vehicle', 'ModelYear', '2009')
    cfg.set('P2', 'FixtureProvenance', 'B3A146_synthetic_50_to_40_route_experiment')
    cfg.set('P2', 'FixtureAuthority', 'laboratory_only_not_oem_xc90_data')
    # Verify all reconstructed transport bytes after setting the INI fields.
    actual = [_frame(cfg.get('D2_40', f'B9FBFrame{i:X}')) for i in range(13)]
    if (b''.join(f[1:] for f in actual) != transformed or
        tuple(f[0] for f in actual) != FRAME_HEADERS or
        cfg.get('D2_50', 'B9FBFrameCount') != '0'):
        raise ValueError('generated profile failed self-check')
    stream = io.StringIO()
    stream.write('; B3A146 LAB EXPERIMENT: NOT OEM XC90 DATA; DO NOT DEPLOY AUTOMATICALLY\n')
    stream.write('; Contains private synthetic VIN. Never upload or publish this output.\n\n')
    cfg.write(stream)
    return stream.getvalue()


def write_new(path, text):
    if (path.name.casefold() != 'b3a146-cem40-lab.ini' or
        path.is_symlink() or not path.parent.is_dir()):
        raise ValueError('output must use safe new lab basename in existing dir')
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--identity-json', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--enable-synthetic-b9f0', action='store_true',
                   help='opt-in two-frame SIM-CEM-125 fake identity for transport tests')
    args = p.parse_args(argv)
    try:
        source = TEMPLATE
        ident = args.identity_json
        if (source.is_symlink() or not source.is_file() or
            source.stat().st_size > MAX_BYTES or ident.is_symlink() or
            not ident.is_file() or ident.name.casefold() != 'vehicle-identity.json' or
            ident.stat().st_size > 128 * 1024):
            raise ValueError('invalid source metadata')
        private = build_profile(source.read_text(encoding='utf-8-sig'),
                                ident.read_text(encoding='utf-8-sig'),
                                enable_synthetic_b9f0=args.enable_synthetic_b9f0)
        write_new(args.output, private)
    except (OSError, ValueError, UnicodeError, configparser.Error, json.JSONDecodeError):
        print('B3A146: REJECTED; private values not printed', file=sys.stderr)
        return 2
    print('B3A146: PRIVATE_LAB_PROFILE_CREATED_NOT_ACTIVATED')
    print('CEM_40/B9FB/125k: 13 synthetic frames; CEM_50/B9FB disabled')
    print('CEM_40/B9F0: 2-frame lab marker' if args.enable_synthetic_b9f0
          else 'CEM_40/B9F0: deliberately disabled')
    print('OEM authenticity, VIDA process binding, ReadVin and ECU ID: NOT_PROVEN')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
