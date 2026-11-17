#!/usr/bin/env python3
"""B3A291: read-only, non-disclosing original VIDA PID-scope log triage.

Counts observed CEM 29-bit UDS identification requests and delivered responses,
D2 B9F0/B9FB/B9FC requests, staged responses and per-channel delivered frame
indices. Never emits raw CAN payload, VIN, target paths or frame data.

No VIDA, J2534, registry, SQL, code or profile modifications.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from pathlib import Path
import re
import sys

TAG = re.compile(r'^\[PID=([0-9A-Fa-f]{8}) ([^\]]+)\] (.*)$')
HEXDUMP = re.compile(r'^(?:[0-9A-Fa-f]{2})(?: [0-9A-Fa-f]{2})*$')
DIDS = ('F110', 'F114', 'F106', 'A45F', 'DD02')
D2_OPCODES = (0xF0, 0xFB, 0xFC)


def parse_hex(text: str) -> bytes | None:
    text = text.strip()
    if not HEXDUMP.fullmatch(text):
        return None
    return bytes.fromhex(text)


def be4(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 4], 'big')


def analyze(lines: list[str], pid: str) -> list[str]:
    counts = Counter()
    channels: dict[int, int] = {}
    gen_by_connection = defaultdict(int)
    last_d2_channel: int | None = None
    current_d2 = {}
    frames = defaultdict(set)
    # Deliberately conservative: NRC attribution is an order-based candidate,
    # not an ECU response correlation ID. A new same-route TX supersedes it.
    candidate_did: str | None = None
    matched = 0
    for raw in lines:
        m = TAG.match(raw.rstrip('\r\n'))
        if not m or m.group(1).upper() != pid or m.group(2).upper() != 'IEXPLORE.EXE':
            continue
        matched += 1
        msg = m.group(3)
        if msg.startswith('J2534 scope channel_connect (BE) '):
            data = parse_hex(msg.split('(BE) ', 1)[1])
            if data is not None and len(data) >= 12:
                ch, serial = be4(data, 0), be4(data, 8)
                channels[ch] = serial
                gen_by_connection[(ch, serial)] = 0
            continue
        if msg.startswith('J2534 scope channel_disconnect (BE) '):
            data = parse_hex(msg.split('(BE) ', 1)[1])
            if data is not None and len(data) >= 12:
                ch, serial = be4(data, 0), be4(data, 8)
                if channels.get(ch) == serial:
                    channels.pop(ch, None)
            continue
        if msg.startswith('P2 D2 service context channel/target/service/opcode/baud (BE) '):
            data = parse_hex(msg.split('(BE) ', 1)[1])
            if data is not None and len(data) == 20:
                last_d2_channel = be4(data, 0)
            continue
        if msg.startswith('TX (app request) '):
            data = parse_hex(msg.split('TX (app request) ', 1)[1])
            if data is None or len(data) < 7:
                candidate_did = None
                continue
            can_id = be4(data, 0)
            if can_id == 0x18DA50F1 and data[4] == 0x22:
                did = data[5:7].hex().upper()
                if did in DIDS:
                    counts[f'UDS_{did}_TX'] += 1
                    candidate_did = did
                else:
                    candidate_did = None
            else:
                candidate_did = None
            if can_id == 0x000FFFFE and len(data) >= 8 and data[4] == 0xCB and data[6] == 0xB9 and data[7] in D2_OPCODES:
                counts[f'D2_{data[5]:02X}_B9{data[7]:02X}_TX'] += 1
            continue
        if msg.startswith('PassThruReadMsgs -> delivered '):
            data = parse_hex(msg.split('PassThruReadMsgs -> delivered ', 1)[1])
            if data is None or len(data) < 7 or be4(data, 0) != 0x18DAF150:
                continue
            payload = data[4:]
            if len(payload) >= 3 and payload[0] == 0x62:
                did = payload[1:3].hex().upper()
                if did in DIDS:
                    counts[f'UDS_{did}_POSITIVE_DELIVERED'] += 1
                if candidate_did == did:
                    counts[f'UDS_{did}_ORDER_MATCHED_POSITIVE'] += 1
                candidate_did = None
            elif len(payload) >= 3 and payload[:2] == bytes.fromhex('7F22'):
                if candidate_did in DIDS:
                    counts[f'UDS_{candidate_did}_ORDER_MATCHED_NRC_{payload[2]:02X}'] += 1
                    candidate_did = None
                else:
                    counts['UDS_UNASSIGNED_NEGATIVE_DELIVERED'] += 1
            continue
        if msg.startswith('P2 D2 read-only recorded frames staged '):
            data = parse_hex(msg.split('staged ', 1)[1])
            if data is None or len(data) != 4 or last_d2_channel is None:
                counts['D2_STAGED_UNASSIGNED'] += 1
                continue
            ch = last_d2_channel
            serial = channels.get(ch)
            if serial is None:
                counts['D2_STAGED_NO_CHANNEL_SERIAL'] += 1
                continue
            gen_by_connection[(ch, serial)] += 1
            gen = gen_by_connection[(ch, serial)]
            opcode = f'{data[2]:02X}{data[3]:02X}'
            current_d2[(ch, serial, gen)] = f'{data[1]:02X}_{opcode}'
            counts[f'D2_{data[1]:02X}_{opcode}_STAGED'] += 1
            continue
        if msg.startswith('P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE) '):
            data = parse_hex(msg.split('(BE) ', 1)[1])
            if data is None or len(data) != 20:
                counts['D2_DELIVERY_META_MALFORMED'] += 1
                continue
            ch, gen, frame = be4(data, 0), be4(data, 4), be4(data, 8)
            serial = channels.get(ch, -1)
            frames[(ch, serial, gen)].add(frame)
            counts['D2_FRAMES_DELIVERED_TOTAL'] += 1
            continue
        if 'P2 D2 strict route rejected (no fixture emitted)' in msg:
            counts['D2_ROUTE_REJECTED'] += 1
        elif 'P2 D2 read command: no validated response fixture' in msg:
            counts['D2_NO_VALIDATED_FIXTURE'] += 1

    result = [f'B3A291_EXACT_PID={pid}', f'B3A291_PID_LINES={matched}',
              'B3A291_NRC_ATTRIBUTION=ORDER_ONLY_NOT_CAUSAL']
    for did in DIDS:
        for key in ('TX', 'POSITIVE_DELIVERED', 'ORDER_MATCHED_POSITIVE', 'ORDER_MATCHED_NRC_31'):
            result.append(f'B3A291_UDS_{did}_{key}={counts[f"UDS_{did}_{key}"]}')
    for target in (0x40, 0x50):
        for opcode in D2_OPCODES:
            name = f'D2_{target:02X}_B9{opcode:02X}'
            result.append(f'B3A291_{name}_TX={counts[f"{name}_TX"]}')
            result.append(f'B3A291_{name}_STAGED={counts[f"{name}_STAGED"]}')
    for label in ('D2_FRAMES_DELIVERED_TOTAL', 'D2_NO_VALIDATED_FIXTURE',
                  'D2_ROUTE_REJECTED', 'D2_STAGED_UNASSIGNED',
                  'D2_STAGED_NO_CHANNEL_SERIAL', 'D2_DELIVERY_META_MALFORMED'):
        result.append(f'B3A291_{label}={counts[label]}')
    for ch, serial, gen in sorted(frames):
        indexes = sorted(frames[(ch, serial, gen)])
        expected = list(range(1, len(indexes) + 1))
        kind = current_d2.get((ch, serial, gen), 'UNKNOWN_IN_CAPTURE')
        result.append(
            f'B3A291_D2_EXCHANGE=channel:{ch},serial:{serial},gen:{gen},'
            f'kind:{kind},distinct:{len(indexes)},'
            f'first:{indexes[0]},last:{indexes[-1]},contiguous:{indexes == expected}'
        )
    result.extend(('B3A291_GUI_READVIN_ACCEPTANCE=NOT_ASSESSED',
                   'B3A291_GUI_CEM_IDENT_ACCEPTANCE=NOT_ASSESSED',
                   'B3A291_RESULT=READ_ONLY_COMPLETE'))
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description='B3A291: read-only VIDA CEM identification log audit')
    ap.add_argument('--log', type=Path, required=True)
    ap.add_argument('--pid', default='00001828')
    ap.add_argument('--tail-lines', type=int, default=100000)
    args = ap.parse_args()
    if not re.fullmatch('[0-9A-Fa-f]{8}', args.pid) or not (1 <= args.tail_lines <= 500000):
        print('B3A291_RESULT=ERROR_INVALID_ARGUMENT')
        return 2
    try:
        with args.log.open('r', encoding='latin-1', errors='replace') as f:
            lines = list(deque(f, maxlen=args.tail_lines))
    except OSError:
        print('B3A291_RESULT=ERROR_LOG_UNAVAILABLE')
        return 1
    result = analyze(lines, args.pid.upper())
    for line in result:
        print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
