#!/usr/bin/env python3
"""B3A53: read-only classification of CURRENT B9FB INI loader gates.

No source VIN, frame bytes, response CAN ID, paths, process IDs or hashes
are exported. Current disk configuration is not a historical VIDA load.
"""
import argparse
import configparser
import json
from pathlib import Path
import re
import sys

from audit_p2_b9fb_shape import vida_2014d_d2_response_id_candidate

SCHEMA = "virtualcar-b3a53-d2-b9fb-loader-v1"
MAX_INI_BYTES = 512 * 1024
MAX_FRAMES = 64
MAX_VALUE = 510
HEX = set('0123456789abcdefABCDEF')
UINT = re.compile(r'(?:0[xX][0-9A-Fa-f]+|[0-9]+)\Z')
ROUTES = (("CEM_40", "D2_40", 0x40, 0x00800003, 125000),
          ("CEM_50", "D2_50", 0x50, 0x01200003, 500000))


def _parse_num(raw, fallback=0, *, base=10):
    if raw is None:
        return fallback
    s = raw.strip()
    try:
        if base == 10:
            if not UINT.fullmatch(s):
                return fallback
            n = int(s[2:], 16) if s.lower().startswith('0x') else int(s, 10)
        else:
            if not re.fullmatch(r'(?:0[xX])?[0-9A-Fa-f]+', s):
                return fallback
            n = int(s[2:], 16) if s.lower().startswith('0x') else int(s, 16)
        return n & 0xFFFFFFFF
    except ValueError:
        return fallback


def _parse_frame8(text):
    if text is None or len(text) >= MAX_VALUE:
        return None
    out, i = bytearray(), 0
    while i < len(text):
        while i < len(text) and text[i] in ' \t-:':
            i += 1
        if i == len(text):
            break
        if i + 1 >= len(text) or text[i] not in HEX or text[i + 1] not in HEX:
            return None
        out.append(int(text[i:i+2], 16))
        if len(out) > 8:
            return None
        i += 2
    return bytes(out) if len(out) == 8 else None


def _valid_d2(frames, target):
    """Source-backed analogue of native validate_d2_fixture, B9FB only."""
    count = len(frames)
    if not 1 <= count <= MAX_FRAMES:
        return False
    if count == 1:
        f = frames[0]
        return ((f[0] & 0xF8) == 0xC8 and f[1] == target and
                ((f[2] == 0xF9 and f[3] == 0xFB) or
                 (f[2] == 0x7F and f[3] == 0xB9)))
    f = frames[0]
    if f[0] not in (0x8F, 0x97) or f[1:4] != bytes((target, 0xF9, 0xFB)):
        return False
    base = 0x10 if f[0] & 0x10 else 0x08
    seq, final = 1, False
    for index in range(1, count):
        frame = frames[index]
        h = frame[0]
        if 0x48 <= h <= 0x4F:
            if index != count - 1 or (base == 0x08 and count == 13 and h != 0x4F):
                return False
            final = True
            continue
        if (h & 0xF8) == 0x50:
            if index == count - 1:
                return False
            continue
        if (h == 0x8F and index > 1 and
                (frames[index - 1][0] & 0xF8) == 0x50 and
                frame[1:4] == bytes((target, 0xF9, 0xFB))):
            continue
        if h != (base | seq):
            return False
        seq = (seq + 1) & 7
    return final


def audit_text(text):
    """Classify declarations and likely native parser outcome, not real ECU RX."""
    if type(text) is not str or len(text.encode('utf-8')) > MAX_INI_BYTES:
        raise ValueError('invalid bounded source')
    ini = configparser.ConfigParser(interpolation=None, strict=True)
    ini.read_string(text)
    sections = {}
    for name in ini.sections():
        key = name.casefold()
        if key in sections:
            raise ValueError('ambiguous INI sections')
        sections[key] = name

    def get(section, key):
        actual = sections.get(section.casefold())
        return ini.get(actual, key, fallback=None) if actual is not None else None

    out = {
        'schema_version': SCHEMA,
        'scope': 'current_explicit_ini_snapshot_not_historical_native_load',
        'b9fb': {},
        'source_path_and_private_payloads_exported': False,
        'native_original_vida_config_attributed': False,
        'authentic_oem_cem_response': False,
        'vida_vin_accepted': False,
    }
    for label, section, target, default_rid, baud in ROUTES:
        fcount = get(section, 'FrameCount')
        if fcount is None or not fcount.strip():
            fcount = get(section, 'B9FBFrameCount')
        reason = None
        if fcount is None or not fcount.strip():
            reason = 'no_frame_count_declared'
            count = 0
        elif not UINT.fullmatch(fcount.strip()):
            reason = 'invalid_frame_count_falls_back_to_zero'
            count = 0
        else:
            count = _parse_num(fcount)
            if count == 0:
                reason = 'zero_frame_count'
            elif count > MAX_FRAMES:
                reason = 'frame_count_exceeds_native_limit'
                count = 0
        rid_text = get(section, 'ResponseId')
        if rid_text is None or not rid_text.strip():
            rid_basis = 'native_default_response_id'
        elif re.fullmatch(r'(?:0[xX])?[0-9A-Fa-f]+', rid_text.strip()):
            rid_basis = 'explicit_hex_ini_response_id'
        else:
            rid_basis = 'malformed_ini_falls_back_to_native_default'
        rid = _parse_num(rid_text, default_rid, base=16)
        frames, bad_index = [], None
        if reason is None and rid > 0x1FFFFFFF:
            reason = 'response_id_outside_29bit_range'
        if reason is None:
            for index in range(count):
                name = format(index, 'X')
                entry = get(section, 'B9FBFrame' + name)
                if not entry:
                    entry = get(section, 'Frame' + name)
                if not entry:
                    reason, bad_index = 'missing_declared_frame', index
                    break
                frame = _parse_frame8(entry)
                if frame is None:
                    reason, bad_index = 'invalid_eight_byte_frame', index
                    break
                frames.append(frame)
        if reason is None and not _valid_d2(frames, target):
            reason = 'invalid_d2_frame_sequence'
        if reason is None:
            reason = ('locally_structural_negative_reply_not_vin' if
                      len(frames) == 1 and frames[0][2] == 0x7F else
                      'locally_structural_reply_not_oem_verified')
        # Classify only a locally valid D2 declaration. The documented VIDA
        # 2014D odd-ID mask is a source hypothesis, not an observed filter.
        filter_candidate = (
            vida_2014d_d2_response_id_candidate(rid)
            if reason in ('locally_structural_negative_reply_not_vin',
                          'locally_structural_reply_not_oem_verified')
            else 'not_evaluated'
        )
        out['b9fb'][label] = {
            'declared_frame_count': count,
            'response_id_source': rid_basis,
            'vida2014d_d2_rx_filter_candidate': filter_candidate,
            'actual_j2534_d2_filter_and_29bit_flags_verified': False,
            'native_base_route_baud_bps': baud,
            'static_loader_class': reason,
            'first_failed_frame_index': bad_index,
            'actual_native_loaded_frames_in_old_session': 'not_established_by_current_ini',
        }
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ini', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        path = args.ini
        if (path.is_symlink() or not path.is_file() or
                path.name.casefold() != 'virtualcar.ini' or
                path.stat().st_size > MAX_INI_BYTES):
            raise ValueError('invalid local ini')
        result = audit_text(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError, UnicodeError, configparser.Error):
        print('B3A53: PRIVATE_INI_INVALID_OR_NOT_FOUND', file=sys.stderr)
        return 2
    print('B3A53: NATIVE_B9FB_LOADER_STATIC_CHECK')
    print('Current INI B9FB gates:', json.dumps(result['b9fb'], sort_keys=True))
    print('Original VIDA DLL load / historical INI equality / OEM CEM RX / VIN: NOT_VERIFIED')
    print('No private frame, VIN, PID, or path shown; INI unchanged')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
