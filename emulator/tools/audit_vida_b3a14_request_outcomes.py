#!/usr/bin/env python3
"""B3A14: read-only classification of original VIDA ReadVin request/response evidence.

Inputs are untouched original B3A13 *since-arm* logs or a historical B3A7 ZIP.
Never emits private VIN/chassis, original payloads, log paths, PID or source bytes.
An emulator-delivered frame is NOT proof of physical/OEM ECU provenance.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile, BadZipFile

STAGE = 'B3A14-original-VIDA-readvin-request-outcomes'
PID_LINE = re.compile(r'^\[PID=([0-9a-fA-F]{8}) IEXPLORE\.EXE\] (.*)$', re.I)
VIDA_REQUEST = re.compile(r"VehComm request: Ecu '([0-9A-Fa-f]{1,8})', Message '([0-9A-Fa-f]+)'", re.I)
HEX = re.compile(r'^(?:[0-9A-Fa-f]{2})(?: [0-9A-Fa-f]{2})*\s*$')
ROUTES = {
    ('726', '22F114'): '726:22F114',
    ('40', 'B9FB'): '40:B9FB',
    ('50', 'B9FB'): '50:B9FB',
    ('51', 'B9F0'): '51:B9F0',
}

class GateError(ValueError):
    pass


def ensure(condition, message):
    if not condition:
        raise GateError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest().upper()


def from_bytes_message(data: bytes):
    if len(data) < 5:
        return None
    arbitration = int.from_bytes(data[:4], 'big')
    payload = data[4:]
    if arbitration == 0x726 and payload[:3] == bytes.fromhex('22F114'):
        return '726:22F114'
    if arbitration == 0xFFFFE and len(payload) >= 4 and payload[0] == 0xCB:
        if payload[1:4] == bytes.fromhex('40B9FB'):
            return '40:B9FB'
        if payload[1:4] == bytes.fromhex('50B9FB'):
            return '50:B9FB'
    return None


def vida_events(raw: bytes):
    counts = Counter(); order = []
    for line in raw.decode('latin-1').splitlines():
        if 'VehComm request:' in line:
            m = VIDA_REQUEST.search(line)
            ensure(m is not None, 'malformed VIDA VehComm request line')
            addr, message = m.groups()
            route = ROUTES.get((addr.upper().lstrip('0') or '0', message.upper()), 'OTHER')
            counts[route] += 1
            order.append(route)
        if 'PassThruReadMsgs(' in line:
            counts['read_calls'] += 1
        if 'PassThruReadMsgs failed with return value:ERR_TIMEOUT' in line:
            counts['timeout_errors'] += 1
        if 'PassThruWriteMsgs(' in line:
            counts['write_calls'] += 1
        # A receive indication in VIDA is interesting, but cannot prove ECU provenance.
        if re.search(r'<---\s*\(\d+\)\s*(?:[0-9A-Fa-f]{2},)+', line):
            counts['vida_receive_indications'] += 1
        if 'Read VIN <<<' in line:
            counts['readvin_ui_marker'] += 1
    return counts, order


def virtual_events(raw: bytes):
    counts = Counter(); per_pid = {}; malformed = 0
    for line in raw.decode('latin-1').splitlines():
        m = PID_LINE.match(line)
        if not m:
            continue
        pid, message = m.groups()
        session = per_pid.setdefault(pid.upper(), {'active': False, 'open': False, 'requests': Counter()})
        if message.startswith('Active INI: '):
            session['active'] = True
        elif message.startswith('PassThruOpen -> device 1'):
            if session['active']:
                session['open'] = True
                counts['lab_opens'] += 1
        elif message.startswith('TX (app request) '):
            payload = message[len('TX (app request) '):].strip()
            ensure(HEX.fullmatch(payload) is not None, 'malformed VirtualCar TX bytes')
            ensure(session['active'] and session['open'], 'TX without same-PID active INI and open')
            route = from_bytes_message(bytes.fromhex(payload))
            session['requests'][route or 'OTHER'] += 1
            counts['tx_total'] += 1
        elif message.startswith('PassThruReadMsgs timeout:'):
            counts['virtual_timeout_sampled'] += 1
        elif message.startswith('PassThruReadMsgs -> delivered'):
            # Delivery is from the emulator queue and may be a synthetic fixture.
            counts['emulator_delivered'] += 1
        elif message.startswith('RX (simulated)'):
            counts['emulator_simulated_queued'] += 1
        elif message.startswith('VIDA B3A7 FIVE_BAUD_INIT OBSERVE ONLY'):
            counts['five_baud_observe_only'] += 1
        elif message.startswith('P2 D2 read command: no validated response fixture'):
            counts['no_validated_d2_fixture'] += 1
    order = Counter()
    for session in per_pid.values():
        order.update(session['requests'])
    return counts, order, len(per_pid)


def audit(vida_raw: bytes, virtual_raw: bytes, *, source_gate: str,
          b3a13_report: dict | None = None):
    ensure(isinstance(vida_raw, bytes) and isinstance(virtual_raw, bytes), 'raw bytes expected')
    ensure(vida_raw and virtual_raw, 'both original log slices must contain bytes')
    ensure(source_gate in ('B3A13_OPERATOR_EVIDENCE', 'B3A7_HISTORICAL_BASELINE'), 'invalid source gate')
    if source_gate == 'B3A13_OPERATOR_EVIDENCE':
        ensure(isinstance(b3a13_report, dict), 'B3A13 aggregate required')
        ensure(b3a13_report.get('runtime_gate') == 'PATH_LOAD_WITH_ZERO_B9FB_CONFIRMED',
               'B3A13 runtime path/zero-B9FB PASS is required')
        ensure(b3a13_report.get('both_b9fb_routes_zero_in_runtime') is True,
               'B3A13 both B9FB routes must be zero')
        ensure(b3a13_report.get('ini_sha256_unchanged_since_arm') is True,
               'B3A13 INI integrity not proven')
        ensure(b3a13_report.get('new_original_vida_log_bytes') == len(vida_raw),
               'VIDA delta length differs from B3A13 aggregate')
        ensure(b3a13_report.get('new_original_virtualcar_log_bytes') == len(virtual_raw),
               'VirtualCar delta length differs from B3A13 aggregate')
    vcounts, vorder = vida_events(vida_raw)
    ecounts, eorder, pids = virtual_events(virtual_raw)
    if source_gate == 'B3A13_OPERATOR_EVIDENCE':
        ensure(ecounts['lab_opens'] > 0, 'no active-INI same-PID J2534 open')
    if ecounts['emulator_delivered']:
        verdict = 'EMULATOR_DELIVERY_PRESENT_SOURCE_UNVERIFIED'
    elif sum(vcounts[route] for route in ROUTES.values()) or ecounts['tx_total']:
        verdict = ('REQUESTS_TIMEOUT_NO_DELIVERED_FRAMES' if vcounts['timeout_errors'] else
                   'REQUESTS_NO_DELIVERED_FRAMES_RESULT_PENDING')
    else:
        verdict = 'NO_READVIN_REQUESTS_IN_EVIDENCE_WINDOW'
    return {
        'stage': STAGE, 'source_gate': source_gate,
        'classification': verdict,
        'vida_request_order': vorder,
        'vida_request_counts': {key: vcounts[key] for key in [*ROUTES.values(), 'OTHER']},
        'driver_tx_counts': {key: eorder[key] for key in [*ROUTES.values(), 'OTHER']},
        'vida_j2534_read_calls': vcounts['read_calls'],
        'vida_j2534_read_timeout_errors': vcounts['timeout_errors'],
        'vida_j2534_write_calls': vcounts['write_calls'],
        'vida_receive_indications_unverified': vcounts['vida_receive_indications'],
        'emulator_delivered_frames_unverified': ecounts['emulator_delivered'],
        'emulator_simulated_frames_queued': ecounts['emulator_simulated_queued'],
        'emulator_timeout_samples_not_total': ecounts['virtual_timeout_sampled'],
        'missing_d2_fixtures_logged': ecounts['no_validated_d2_fixture'],
        'five_baud_observe_only_events': ecounts['five_baud_observe_only'],
        'lab_opens': ecounts['lab_opens'],
        'original_vida_pids_count': pids,
        'original_log_sha256': {'vida_since_arm': sha(vida_raw), 'virtualcar_since_arm': sha(virtual_raw)},
        'original_log_bytes': {'vida_since_arm': len(vida_raw), 'virtualcar_since_arm': len(virtual_raw)},
        'original_logs_changed': False,
        'private_vin_exported': False,
        'physical_ecu_source_authenticated': False,
        'original_vida_automatic_readvin': 'NOT_PROVEN',
        'replay_approved': False,
    }


def baseline_zip(path: Path):
    with ZipFile(path) as z:
        ensure(z.testzip() is None, 'historical ZIP CRC failed')
        names = z.namelist()
        def read_one(suffix):
            matches = [name for name in names if name.replace('\\', '/').endswith('/' + suffix)]
            ensure(len(matches) == 1, f'one {suffix} member expected')
            return z.read(matches[0])
        return read_one('VIDA-since-arm.raw'), read_one('VirtualCar-since-arm.raw')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--b3a13-evidence', type=Path, help='local folder from B3A13 collect')
    group.add_argument('--baseline-b3a7-zip', type=Path, help='historical baseline only, NOT a new run')
    p.add_argument('--out', type=Path, help='optional new aggregate JSON; must not exist')
    args = p.parse_args(argv)
    try:
        if args.b3a13_evidence:
            d = args.b3a13_evidence
            result = audit((d / 'VIDA-since-arm.raw').read_bytes(),
                           (d / 'VirtualCar-since-arm.raw').read_bytes(),
                           source_gate='B3A13_OPERATOR_EVIDENCE',
                           b3a13_report=json.loads((d / 'B3A13-aggregate.json').read_text(encoding='utf-8')))
        else:
            vida, virtual = baseline_zip(args.baseline_b3a7_zip)
            result = audit(vida, virtual, source_gate='B3A7_HISTORICAL_BASELINE')
        if args.out is not None:
            with args.out.open('x', encoding='utf-8') as out:
                json.dump(result, out, indent=2, ensure_ascii=False)
                out.write('\n')
        print('B3A14:', result['classification'])
        print('VIDA requests:', len(result['vida_request_order']),
              'VIDA ERR_TIMEOUT:', result['vida_j2534_read_timeout_errors'],
              'Emulator delivered:', result['emulator_delivered_frames_unverified'])
        print('Original VIDA automatic ReadVIN: NOT PROVEN')
        print('No original logs modified; private VIN not printed; no replay approved.')
        return 0
    except (OSError, GateError, KeyError, ValueError, BadZipFile) as ex:
        p.exit(2, f'B3A14 FAIL-CLOSED: {ex}\n')


if __name__ == '__main__':
    sys.exit(main())
