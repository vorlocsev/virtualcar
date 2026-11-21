#!/usr/bin/env python3
"""B3A141: offline, privacy-safe structural audit of CEM D2 B9F0 INI fixtures.

This tool does not generate ECU identity, alter INI files or call J2534/VIDA.
Static shape parity follows emulator/src/virtualcar.c validate_d2_fixture.
"""
import argparse
import configparser
import json
from pathlib import Path
import re
import sys

SCHEMA = 'virtualcar-b3a141-d2-b9f0-static-v1'
MAX_INI_BYTES = 512 * 1024
MAX_FRAMES = 64
MAX_FRAME_TEXT = 510
_UINT = re.compile(r'(?:0[xX][0-9A-Fa-f]+|[0-9]+)\Z')
_HEX_ID = re.compile(r'(?:0[xX])?[0-9A-Fa-f]+\Z')
_ROUTES = (
    ('CEM_40', 'D2_40_B9F0', 0x40, 0x00800003, 125000),
    ('CEM_50', 'D2_50_B9F0', 0x50, 0x01000003, 500000),
)


def _decimal(text):
    if not _UINT.fullmatch(text):
        return None
    try:
        return int(text, 16 if text.lower().startswith('0x') else 10)
    except ValueError:
        return None


def _hex_id(text):
    if not _HEX_ID.fullmatch(text):
        return None
    try:
        return int(text, 16)
    except ValueError:
        return None


def _frame8(text):
    """Mirror native parse_frame8 acceptance of separators, exactly 8 bytes."""
    if not text or len(text) >= MAX_FRAME_TEXT:
        return None
    packed = re.sub(r'[ \t:\-]', '', text)
    if not re.fullmatch(r'[0-9a-fA-F]{16}', packed):
        return None
    return bytes.fromhex(packed)


def _shape(frames, target):
    """Native framing shape, not authenticated D2 content or OEM checksum."""
    if not 1 <= len(frames) <= MAX_FRAMES:
        return 'invalid_d2_frame_sequence'
    if len(frames) == 1:
        first = frames[0]
        if (first[0] & 0xF8) != 0xC8 or first[1] != target:
            return 'invalid_d2_frame_sequence'
        if first[2:4] == b'\x7f\xb9':
            return 'structural_negative_not_ecu_identity'
        if first[2:4] == b'\xf9\xf0':
            return 'structural_positive_not_oem_verified'
        return 'invalid_d2_frame_sequence'
    first = frames[0]
    if first[0] not in (0x8F, 0x97) or first[1:4] != bytes((target, 0xF9, 0xF0)):
        return 'invalid_d2_frame_sequence'
    base = 0x10 if first[0] & 0x10 else 0x08
    seq = 1
    final = False
    for pos, frame in enumerate(frames[1:], 1):
        header = frame[0]
        if 0x48 <= header <= 0x4F:
            if pos != len(frames)-1:
                return 'invalid_d2_frame_sequence'
            if base == 0x08 and len(frames) == 13 and header != 0x4F:
                return 'invalid_d2_frame_sequence'
            final = True
            continue
        if (header & 0xF8) == 0x50:
            if pos == len(frames)-1:
                return 'invalid_d2_frame_sequence'
            continue
        if (header == 0x8F and pos > 1 and
                (frames[pos-1][0] & 0xF8) == 0x50 and
                frame[1:4] == bytes((target, 0xF9, 0xF0))):
            continue
        if header != base | seq:
            return 'invalid_d2_frame_sequence'
        seq = (seq+1) & 7
    return 'structural_positive_not_oem_verified' if final else 'missing_terminal_frame'


def _single_frame_wire_class(frames, native_class):
    """Additional VIDA-style declared-length preflight, not a native loader claim.

    In Volvo D2 a single-frame marker is C8 + meaningful-byte count.
    Native validate_d2_fixture currently checks only its high five bits,
    and can accept C8 even when target/F9/F0 occupy three data bytes.
    """
    if native_class not in ('structural_positive_not_oem_verified',
                            'structural_negative_not_ecu_identity'):
        return 'not_evaluated'
    if len(frames) != 1:
        return 'multiframe_native_shape_only'
    frame = frames[0]
    meaningful = frame[0] & 0x07
    if meaningful < 3:
        return 'declared_length_shorter_than_target_and_echo'
    if meaningful == 3 and frame[2:4] == b'\xf9\xf0':
        return 'positive_echo_only_no_identity_payload'
    if any(frame[1 + meaningful:]):
        # Volvo D2 examples contain ignored residual bytes beyond the
        # declared single-frame payload. Do NOT reject an otherwise valid
        # single-frame header solely because this tail is non-zero.
        return 'single_frame_nonzero_tail_ignored_candidate'
    return 'single_frame_length_and_padding_candidate'


def _id_class(response_id, target, fallback, explicit):
    if response_id > 0x1FFFFFFF:
        return 'outside_29bit_range'
    if response_id <= 0x7FF:
        return 'j2534_id_width_unverified'
    if response_id % 2 == 0:
        return 'even_id_may_miss_documented_odd_mask'
    if target == 0x40 and response_id == 0x00600005:
        return 'cross_vehicle_capture_candidate_not_xc90_proven'
    if response_id == fallback and not explicit:
        return 'native_default_unverified'
    return 'odd_extended_id_candidate_not_runtime_verified'


def audit_text(source):
    """Return categorical findings only; no source fields or frames echoed."""
    if type(source) is not str or len(source.encode('utf-8')) > MAX_INI_BYTES:
        raise ValueError('source limit')
    ini = configparser.ConfigParser(interpolation=None, strict=True)
    ini.read_string(source)
    seen = set()
    for name in ini.sections():
        folded = name.casefold()
        if folded in seen:
            raise ValueError('duplicate case-insensitive sections')
        seen.add(folded)
    out = {
        'schema': SCHEMA,
        'scope': 'static_current_ini_not_live_vida_load',
        'no_vin_pid_paths_can_frames_or_response_ids_exported': True,
        'actual_vida_j2534_binding': 'NOT_PROVEN',
        'oem_ecu_identity_or_vida_acceptance': 'NOT_PROVEN',
        'routes': {},
    }
    for label, section, target, default_id, baud in _ROUTES:
        raw_count = ini.get(section, 'FrameCount', fallback=None)
        if raw_count is None:
            count = 0
            status = 'no_frame_count_declared'
        else:
            count = _decimal(raw_count.strip())
            if count is None:
                status, count = 'invalid_frame_count', 0
            elif count > MAX_FRAMES:
                status, count = 'frame_count_above_native_limit', 0
            elif count == 0:
                status = 'zero_frame_count'
            else:
                status = None
        raw_id = ini.get(section, 'ResponseId', fallback=None)
        parsed_id = _hex_id(raw_id.strip()) if raw_id is not None else None
        effective_id = default_id if parsed_id is None else parsed_id
        id_provenance = ('native_default' if raw_id is None else
                         'malformed_falls_back_to_default' if parsed_id is None else
                         'explicit_ini')
        frames = []
        if status is None and effective_id > 0x1FFFFFFF:
            status = 'response_id_outside_29bit_range'
        if status is None:
            for number in range(count):
                raw = ini.get(section, 'Frame'+format(number, 'X'), fallback=None)
                if raw is None or raw.strip() == '':
                    status = 'missing_declared_frame'
                    break
                frame = _frame8(raw)
                if frame is None:
                    status = 'invalid_eight_byte_frame'
                    break
                frames.append(frame)
        if status is None:
            status = _shape(frames, target)
        out['routes'][label] = {
            'native_target_class': label,
            'native_baud_bps': baud,
            'declared_frames': count,
            'static_loader_class': status,
            'vida_d2_single_frame_wire_candidate': _single_frame_wire_class(frames, status),
            'response_id_source': id_provenance,
            'response_id_evidence_class': _id_class(
                effective_id, target, default_id, parsed_id is not None),
            'actual_rx_or_filter_verification': False,
        }
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ini', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        path = args.ini
        if (path.name.casefold() != 'virtualcar.ini' or path.is_symlink() or
                not path.is_file() or path.stat().st_size > MAX_INI_BYTES):
            raise ValueError('invalid path or file size')
        result = audit_text(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError, UnicodeError, configparser.Error):
        print('B3A141: PRIVATE_INI_UNAVAILABLE_OR_INVALID', file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
