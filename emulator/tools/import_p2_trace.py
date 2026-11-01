#!/usr/bin/env python3
"""Import a read-only Volvo P2 D2 CEM response from a J2534 trace.

Works with a textual PassThruWriteMsgs/ReadMsgs trace or VirtualCar TX/RX log.
Only CB [40|50] B9 [F0|FB|FC] read requests are supported. No security or write data.
VIN-like identifiers are redacted by default in the local INI output; this
may invalidate vehicle checksums and should not be used for real identification.
"""
import argparse
import configparser
import re
from pathlib import Path

DATA_RE = re.compile(r"\b0x([a-fA-F0-9]{1,2})\b")
HEX_RE = re.compile(r"\b[0-9a-fA-F]{2}\b")
VIN_RE = re.compile(rb"(?<![A-Z0-9])[A-HJ-NPR-Z0-9]{17}(?![A-Z0-9])")


def message(line):
    is_tx = 'PassThruWriteMsgs' in line or 'TX (app request)' in line
    is_rx = 'PassThruReadMsgs() msg' in line or 'PassThruReadMsgs -> delivered' in line or 'RX (simulated)' in line or 'CAN_HS <---' in line
    if not (is_tx or is_rx):
        return None
    if 'Data = [' in line:
        bits = DATA_RE.findall(line.partition('Data = [')[2])
    elif 'TX (app request)' in line:
        bits = HEX_RE.findall(line.split('TX (app request)', 1)[1])
    elif 'RX (simulated)' in line:
        bits = HEX_RE.findall(line.split('RX (simulated)', 1)[1])
    elif 'PassThruReadMsgs -> delivered' in line:
        bits = HEX_RE.findall(line.split('PassThruReadMsgs -> delivered', 1)[1])
    else:
        bits = HEX_RE.findall(line.split('data=', 1)[-1])
    if len(bits) < 12:
        return None
    payload = bytes(int(b, 16) for b in bits[:12])
    return ('TX' if is_tx else 'RX', int.from_bytes(payload[:4], 'big'), payload[4:12])


def sessions(lines, target, opcode):
    sessions_found, active = [], None
    for line in lines:
        item = message(line)
        if item:
            direction, can_id, data = item
            if direction == 'TX':
                if active is not None:
                    sessions_found.append(active)
                active = None
                if can_id == 0x000FFFFE and data[:4] == bytes([0xCB, target, 0xB9, opcode]):
                    active = []
            elif active is not None:
                active.append((can_id, data))
        elif active is not None and ('PassThruDisconnect' in line or 'PassThruClose' in line):
            sessions_found.append(active)
            active = None
    if active is not None:
        sessions_found.append(active)
    return [x for x in sessions_found if x]


def redact_vin(frames):
    # D2 reply's byte 0 is the protocol control byte. Only payload bytes are
    # eligible for redaction, preserving frame order and the control bytes.
    flattened = bytearray(b''.join(payload[1:] for _,payload in frames))
    redactions=0
    for found in list(VIN_RE.finditer(bytes(flattened))):
        if any(65 <= b <= 90 for b in found.group()):
            flattened[found.start():found.end()]=b'X'*17
            redactions += 1
    output=[]
    for i,(can_id,data) in enumerate(frames):
        output.append((can_id,bytes([data[0]])+bytes(flattened[i*7:(i+1)*7])))
    return output,redactions


def validate_response(frames, target, opcode):
    """Reject incomplete/mispaired D2 fixture before it reaches the J2534 DLL.

    This validates transport framing only, NOT the authenticity of vehicle data.
    """
    if not frames:
        raise ValueError('No response frames')
    if not 1 <= len(frames) <= 64:
        raise ValueError('Response exceeds 64 frames')
    if len({can_id for can_id, _ in frames}) != 1:
        raise ValueError('Response mixes CAN IDs')
    for can_id, payload in frames:
        if not 0 < can_id <= 0x1FFFFFFF or len(payload) != 8:
            raise ValueError('Invalid extended CAN response')
    first = frames[0][1]
    if len(frames) > 1:
        if first[:4] not in (bytes([0x8F,target,0xF9,opcode]), bytes([0x97,target,0xF9,opcode])):
            raise ValueError('Wrong D2 first-frame header')
        base=0x10 if first[0]==0x97 else 0x08
        counter=1
        prev_subblock=False
        for i, (_,frame) in enumerate(frames[1:],1):
            head=frame[0]
            if 0x48<=head<=0x4F:
                if i!=len(frames)-1:raise ValueError('Early D2 final frame')
                return
            if (head&0xF8)==0x50:
                if i==len(frames)-1:raise ValueError('Incomplete D2 sub-block')
                prev_subblock=True
                continue
            if prev_subblock and head==0x8F and frame[1:4]==bytes([target,0xF9,opcode]):
                prev_subblock=False
                continue
            prev_subblock=False
            if head!=(base|counter):
                raise ValueError(f'Invalid D2 sequence at frame {i}')
            counter=(counter+1)&7
        raise ValueError('Missing final D2 frame')
    else:
        if first[0]&0xF8 != 0xC8 or first[1]!=target:
            raise ValueError('Invalid D2 single-frame response')
        # Match the DLL fixture gate: target alone does not pair a reply.
        # Keep a recorded B9 negative reply intact; never turn it positive.
        if not ((first[2]==0xF9 and first[3]==opcode) or
                (first[2]==0x7F and first[3]==0xB9)):
            raise ValueError('Wrong D2 single-frame service/opcode echo')


def set_lab_vin(frames, vin):
    """Replace a previously masked VIN with an explicitly synthetic lab VIN."""
    if not re.fullmatch(r'[A-HJ-NPR-Z0-9]{17}', vin):
        raise ValueError('Lab VIN must contain exactly 17 valid VIN characters')
    data = bytearray(b''.join(payload[1:] for _, payload in frames))
    matches = list(re.finditer(rb'X{17}', bytes(data)))
    if len(matches) != 1:
        raise ValueError('Expected exactly one masked 17-character VIN in D2 data')
    found = matches[0]
    data[found.start():found.end()] = vin.encode('ascii')
    return [(can_id, bytes([payload[0]]) + bytes(data[i*7:(i+1)*7]))
            for i, (can_id, payload) in enumerate(frames)]


def main():
    a=argparse.ArgumentParser(description='Volvo P2 CEM D2 B9F0/B9FB/B9FC read-only trace importer')
    a.add_argument('log',type=Path)
    a.add_argument('--target',choices=['40','50'],default='50')
    a.add_argument('--opcode',choices=['F0','FB','FC'],default='FB')
    a.add_argument('--profile',type=Path,default=Path(__file__).resolve().parent.parent/'virtualcar-p2.ini')
    a.add_argument('--output',type=Path,required=True,help='New local INI; existing files are never overwritten')
    a.add_argument('--keep-identifiers',action='store_true',help='Retain VIN/personal vehicle identifiers in PRIVATE local output (use only for your own captures)')
    a.add_argument('--lab-vin',help='Replace exactly one masked VIN with a synthetic 17-character test VIN; diagnostic lab only')
    args=a.parse_args()
    if args.output.resolve() in (args.log.resolve(), args.profile.resolve()):
        a.error('Output must be a new file, not the source log or profile')
    target,opcode=int(args.target,16),int(args.opcode,16)
    groups=sessions(args.log.read_text(encoding='utf-8',errors='replace').splitlines(),target,opcode)
    if not groups:
        a.error('No matching D2 CEM request with recorded responses was found')
    frames=max(groups,key=len)
    try:
        validate_response(frames, target, opcode)
    except ValueError as exc:
        a.error(str(exc))
    can_id=frames[0][0]
    if args.keep_identifiers and args.lab_vin:
        a.error('Do not combine --keep-identifiers and --lab-vin')
    if not args.keep_identifiers:
        frames,count=redact_vin(frames)
        print(f'VIN-like identifiers anonymised: {count}; checksums may no longer be valid.')
        if args.lab_vin:
            try:
                frames=set_lab_vin(frames,args.lab_vin)
            except ValueError as exc:
                a.error(str(exc))
            print('SYNTHETIC test VIN inserted. Remaining historical ECU fields are NOT coherent with a real vehicle.')
    else:
        print('WARNING: raw vehicle identifiers are retained. Do not share the resulting INI.')
    cfg=configparser.ConfigParser(interpolation=None)
    cfg.optionxform=str
    cfg.read(args.profile,encoding='utf-8')
    if not cfg.has_section('P2'):cfg.add_section('P2')
    if args.lab_vin:
        if not cfg.has_section('Vehicle'): cfg.add_section('Vehicle')
        cfg.set('Vehicle','VIN',args.lab_vin)
    section=f'D2_{args.target}' if opcode==0xFB else f'D2_{args.target}_B9{args.opcode}'
    if not cfg.has_section(section):cfg.add_section(section)
    cfg.set(section,'ResponseId',f'{can_id:08X}')
    for key in list(cfg[section]):
        if re.fullmatch(r'(B9FBFrame|Frame)[0-9A-F]{1,2}',key):cfg.remove_option(section,key)
    count_key='B9FBFrameCount' if opcode==0xFB else 'FrameCount'
    cfg.set(section,count_key,str(len(frames)))
    for i,(_id,data) in enumerate(frames):
        key=('B9FBFrame' if opcode==0xFB else 'Frame')+f'{i:X}'
        cfg.set(section,key,' '.join(f'{b:02X}' for b in data))
    try:
        # Exclusive creation also protects existing hardlink/symlink aliases
        # and a destination created after the earlier source-path check.
        with args.output.open('x',encoding='utf-8') as f: cfg.write(f)
    except OSError:
        a.error('Unable to create new output; existing files are never overwritten')
    print(f'Imported: CEM 0x{target:02X} B9{opcode:02X}, {len(frames)} frames, RX CAN ID 0x{can_id:08X}')
    print(f'Wrote local P2 profile to {args.output}')

if __name__=='__main__':main()

