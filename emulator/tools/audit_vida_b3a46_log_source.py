#!/usr/bin/env python3
"""Read-only nonrecursive native J2534 log locator; private paths stay local."""
import argparse
import json
import os
from pathlib import Path
import re

NAME = 'SectorVVirtualCar.log'
ROOT = Path(__file__).resolve().parents[2]
LIMIT = 12
MAX_BYTES = 2 * 1024**3
TAIL = 65536
PREFIX = re.compile(r'^\[PID=[0-9a-fA-F]{8} [a-zA-Z0-9_.-]{1,48}\] ')
MARKERS = ('VirtualCar DLL initialized', 'PassThruOpen -> device 1',
           'J2534 Connect result protocol/flags/baud/status (BE)',
           'PassThruReadMsgs -> delivered',
           'VIDA B3A6 KLINE exact original write LOCAL ACK ONLY (NO BUS/ECU TX/RX)')


def candidate_roots(env):
    found = [Path(env[k]) for k in ('TEMP', 'TMP') if env.get(k)]
    if env.get('LOCALAPPDATA'):
        found.append(Path(env['LOCALAPPDATA']) / 'Temp')
    windir = env.get('WINDIR') or env.get('SystemRoot')
    if windir:
        found.append(Path(windir) / 'Temp')
        found.append(Path(windir) / 'System32/config/systemprofile/AppData/Local/Temp')
    return found


def inspect(root):
    path = Path(root) / NAME
    result = {'path': str(path.resolve()), 'status': 'missing',
              'bytes': None, 'markers_in_tail': 0}
    try:
        if path.is_symlink():
            result['status'] = 'symlink_rejected'
        elif path.is_file():
            before = path.stat()
            if before.st_size > MAX_BYTES:
                raise ValueError('oversized')
            with path.open('rb') as stream:
                offset = max(0, before.st_size - TAIL)
                stream.seek(offset)
                data = stream.read(TAIL)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError('changed during scan')
            if offset:
                data = data.split(b'\n', 1)[1] if b'\n' in data else b''
            if data and not data.endswith(b'\n'):
                data = data.rsplit(b'\n', 1)[0] + b'\n' if b'\n' in data else b''
            count = 0
            for line in data.decode('utf-8', errors='replace').splitlines():
                if len(line) > 512:
                    continue
                prefix = PREFIX.match(line)
                if prefix and any(line[prefix.end():].startswith(m) for m in MARKERS):
                    count += 1
            result.update(status='native_marker_in_tail' if count else
                          'present_no_marker_in_tail', bytes=before.st_size,
                          markers_in_tail=count)
    except (OSError, ValueError):
        result['status'] = 'unreadable_or_changed'
    return result


def inventory(roots):
    if len(roots) > LIMIT:
        raise ValueError('too many candidate roots')
    data, seen = [], set()
    for root in roots:
        p = Path(root).expanduser() / NAME
        key = os.path.normcase(str(p.resolve()))
        if key not in seen:
            seen.add(key)
            data.append(inspect(p.parent))
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, action='append', default=[])
    parser.add_argument('--private-manifest', type=Path, required=True)
    args = parser.parse_args(argv)
    roots = candidate_roots(os.environ) + args.root
    if not roots:
        parser.error('no candidate roots')
    output = args.private_manifest.resolve()
    if output.is_relative_to(ROOT) or any(output == (r / NAME).resolve() for r in roots):
        parser.error('manifest must be outside repository and source logs')
    data = inventory(roots)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump({'schema_version': 'virtualcar-b3a46-source-inventory-v1',
                   'private_do_not_upload': True, 'paths_are_not_process_attribution': True,
                   'candidates': data}, stream, indent=2)
    count = sum(x['status'] == 'native_marker_in_tail' for x in data)
    outcome = ('ONE_PLAUSIBLE_SOURCE' if count == 1 else
               'MULTIPLE_PLAUSIBLE_SOURCES' if count > 1 else 'NO_BOUNDED_MATCH')
    print('B3A46 Outcome:', outcome)
    print('Roots=', len(data), 'present=', sum(x['bytes'] is not None for x in data),
          'native_marker_candidates=', count)
    for i, x in enumerate(data, 1):
        print(f'Candidate {i}: {x["status"]}; markers_in_tail={x["markers_in_tail"]}')
    print('Process/VIDA attribution: NOT_VERIFIED; no source content displayed')
    print('Private path manifest retained locally; do not upload')


if __name__ == '__main__':
    main()
