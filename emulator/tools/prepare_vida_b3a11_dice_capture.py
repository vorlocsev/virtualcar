#!/usr/bin/env python3
"""B3A11: prepare immutable provenance links for a *user-supplied* DiCE trace.

Strictly read-only: no vehicle/VIDA access, no CAN TX, no VIN reconstruction,
no ECU RX simulation, no redaction and no automatic identity/replay approval.
Outputs only hashes/line indices plus an intentionally UNVERIFIED manifest.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_FRAMES = 64
MAX_WINDOW_MS = 30000
TOKEN_RE = re.compile(rb'\s*0x([0-9a-fA-F]{1,2})\s*')
FRAME_RE = re.compile(rb'\bPassThru(Write|Read)Msgs\(\)\s+msg\[0\]\.Data\s*=\s*\[([^\]\r\n]+)\]')
CLOCK_RE = re.compile(rb'^(\d\d):(\d\d):(\d\d),(\d{3})\b')
DAY_MS = 24 * 60 * 60 * 1000
TARGET_REQUEST = bytes.fromhex('00 0F FF FE CB 50 B9 FB')
ALLOWED_RX_IDS = {0x01000003, 0x01200003}


class SourceError(ValueError):
    pass


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest().upper()


def require(ok: bool, message: str) -> None:
    if not ok:
        raise SourceError(message)


def parse_time(line: bytes) -> int | None:
    match = CLOCK_RE.match(line)
    if match is None:
        return None
    h, m, s, ms = map(int, match.groups())
    require(h < 24 and m < 60 and s < 60, 'malformed timestamp')
    return ((h * 60 + m) * 60 + s) * 1000 + ms


def parse_hex_bytes(tokens: bytes) -> bytes:
    parts = tokens.split(b',')
    if parts and not parts[-1].strip():
        parts.pop()
    require(5 <= len(parts) <= 4128 and all(TOKEN_RE.fullmatch(p) for p in parts),
            'malformed J2534 message (no partial hex parsing)')
    return bytes(int(TOKEN_RE.fullmatch(p).group(1), 16) for p in parts)


def scan_original(raw: bytes, window_ms: int = 5000) -> dict:
    """Only bracket original, same-file 0x50 B9FB requests and RX candidates.

    Any intervening TX or unexpected sequence aborts the candidate, preventing
    borrowing a donor response from another request or recording interval.
    Other CAN RX IDs are counted, but cannot provide B9FB response bytes.
    """
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_SOURCE_BYTES,
            'original source empty, inaccessible or above 64 MiB')
    require(0 < window_ms <= MAX_WINDOW_MS, 'unsafe source matching window')
    lines = raw.splitlines(keepends=True)
    pending = None
    found = []
    counts = {'valid_formatted_events': 0, 'b9fb50_tx': 0,
              'unbound_rx': 0, 'interleaved_rx': 0, 'abandoned_on_tx': 0,
              'invalid_sequence': 0, 'expired_window': 0, 'missing_time': 0,
              'unexpected_response_id': 0, 'ambiguous_replies': 0}

    for line_no, raw_line in enumerate(lines, 1):
        m = FRAME_RE.search(raw_line)
        if not m:
            continue
        packet = parse_hex_bytes(m.group(2))
        require(len(packet) >= 5, 'no J2534 CAN ID + bytes')
        ts = parse_time(raw_line)
        direction = m.group(1)
        counts['valid_formatted_events'] += 1
        entry = {'line': line_no, 'line_sha256': sha256(raw_line),
                 'timestamp_ms': ts, 'data': packet,
                 'can_id': int.from_bytes(packet[:4], 'big')}

        if direction == b'Write':
            if pending is not None:
                counts['abandoned_on_tx'] += 1
                pending = None
            if packet.startswith(TARGET_REQUEST) and len(packet) <= 12:
                counts['b9fb50_tx'] += 1
                pending = {'tx': entry, 'rx': [], 'rxid': None,
                           'last_ts': ts, 'other_rx': 0}
            continue

        if pending is None:
            counts['unbound_rx'] += 1
            continue
        if ts is None or pending['last_ts'] is None:
            counts['missing_time'] += 1
            pending = None
            continue
        gap = (ts - pending['last_ts']) % DAY_MS
        since_tx = (ts - pending['tx']['timestamp_ms']) % DAY_MS
        if gap > window_ms or since_tx > window_ms:
            counts['expired_window'] += 1
            pending = None
            continue

        if entry['can_id'] not in ALLOWED_RX_IDS:
            counts['interleaved_rx'] += 1
            pending['other_rx'] += 1
            continue
        data = packet[4:]
        if len(data) != 8:
            counts['invalid_sequence'] += 1
            pending = None
            continue
        if not pending['rx']:
            if data[:4] != bytes.fromhex('8F 50 F9 FB'):
                counts['unexpected_response_id'] += 1
                # An unrelated frame on this candidate CAN ID does not bind
                # a response, but makes automated attribution more ambiguous.
                pending['other_rx'] += 1
                continue
            pending['rxid'] = entry['can_id']
            pending['rx'].append(entry)
            pending['last_ts'] = ts
            continue

        if entry['can_id'] != pending['rxid']:
            counts['ambiguous_replies'] += 1
            pending = None
            continue
        if data[:4] == bytes.fromhex('8F 50 F9 FB'):
            counts['ambiguous_replies'] += 1
            pending = None
            continue
        next_index = len(pending['rx'])  # 1 after 8F opener
        expected = 0x08 + next_index % 8
        if data[0] != 0x4F and data[0] != expected:
            counts['invalid_sequence'] += 1
            pending = None
            continue
        pending['rx'].append(entry)
        pending['last_ts'] = ts
        if len(pending['rx']) > MAX_FRAMES:
            counts['invalid_sequence'] += 1
            pending = None
            continue
        if data[0] == 0x4F:
            if len(pending['rx']) >= 2:
                found.append(pending)
            else:
                counts['invalid_sequence'] += 1
            pending = None

    if pending:
        counts['unterminated_request'] = 1
    status = ('NO_FORMATTED_DICE_J2534_EVENTS' if counts['valid_formatted_events'] == 0
              else 'NO_B9FB50_REQUEST' if counts['b9fb50_tx'] == 0
              else 'NO_COMPLETE_MATCHED_RESPONSE' if not found
              else 'CANDIDATES_REQUIRE_INDEPENDENT_REVIEW')
    return {'status': status, 'lines': len(lines), 'source_sha256': sha256(raw),
            'source_size_bytes': len(raw), 'candidates': found, 'counters': counts}


def skeleton(result: dict, candidate: dict, identity_sha: str | None = None,
             baud: int | None = None) -> dict:
    """Never make a source or vehicle-identity assertion on the user's behalf."""
    tx, rx = candidate['tx'], candidate['rx']
    return {
      'schema_version': 1,
      'source': {'sha256': result['source_sha256'],
                 'size_bytes': result['source_size_bytes'],
                 'raw_unchanged': True,
                 'origin': 'UNVERIFIED_BY_AUDITOR',
                 'format': 'dice_j2534_text', 'transformation': 'none'},
      'vehicle': {'make': 'Volvo', 'model': 'XC90', 'platform': 'P2',
                  'model_year': 2009, 'engine': 'V8',
                  'identity_basis': 'UNVERIFIED_BY_AUDITOR',
                  'identity_record_sha256': identity_sha or ''},
      'route': {'ecu': '50', 'service': 'B9FB', 'protocol': 'CAN',
                'baud_bps': baud},
      'events': {
          'request': {'line': tx['line'], 'line_sha256': tx['line_sha256']},
          'responses': [{'line': x['line'], 'line_sha256': x['line_sha256']}
                        for x in rx]},
      '_b3a11_review': {'status': 'UNVERIFIED_CANDIDATE_ONLY',
                        'source_unmodified': True,
                        'response_can_id': f"0x{candidate['rxid']:08X}",
                        'frame_count': len(rx),
                        'response_elapsed_ms': (rx[-1]['timestamp_ms'] -
                                                tx['timestamp_ms']) % DAY_MS,
                        'unrelated_rx_seen': candidate['other_rx'],
                        'baud_is_operator_claim': baud is not None,
                        'identity_record_hash_is_not_proof': True,
                        'replay_approved': False}
    }


def collect(log: Path, target: Path, identity_record: Path | None = None,
            baud: int | None = None, window_ms: int = 5000) -> dict:
    require(not target.exists(), 'refusing existing output directory')
    raw = log.read_bytes()
    scan = scan_original(raw, window_ms)
    identity_sha = sha256(identity_record.read_bytes()) if identity_record else None
    items = [skeleton(scan, c, identity_sha, baud) for c in scan['candidates']]
    require(len(items) <= 64, 'too many capture candidates for bounded review')
    target.mkdir(parents=True, exist_ok=False)
    for i, item in enumerate(items, 1):
        (target / f'B3A11-candidate-{i:02}.manifest.json').write_text(
            json.dumps(item, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    report = {'stage': 'B3A11-source-intake', 'status': scan['status'],
              'original_source_sha256': scan['source_sha256'],
              'original_source_size_bytes': scan['source_size_bytes'],
              'source_line_count': scan['lines'],
              'candidate_count': len(items),
              'candidate_review_only': True,
              'raw_capture_modified': False,
              'source_vehicle_identity_verified': False,
              'authentic_ecu_rx_proven': False,
              'replay_approved': False,
              'source_format': 'dice_j2534_text',
              'counters': scan['counters']}
    (target / 'B3A11-intake-report.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw-log', type=Path, required=True,
                   help='unmodified original DiCE/J2534 source log')
    p.add_argument('--out-dir', type=Path, required=True,
                   help='new, not-yet-existing review directory')
    p.add_argument('--identity-record', type=Path,
                   help='original local vehicle identity document, SHA only; not proof')
    p.add_argument('--baud', choices=(125000, 250000, 500000), type=int,
                   help='operator-asserted baud, not inferred from DiCE log')
    p.add_argument('--window-ms', default=5000, type=int,
                   help='max elapsed request-to-reply and per-frame gap (1..30000)')
    args = p.parse_args(argv)
    try:
        report = collect(args.raw_log, args.out_dir, args.identity_record,
                         args.baud, args.window_ms)
    except (SourceError, OSError, UnicodeError) as err:
        p.exit(2, f'B3A11 INTAKE FAILED: {err}\n')
    print(f"B3A11: {report['status']} | candidates={report['candidate_count']}"
          ' | replay NOT APPROVED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
