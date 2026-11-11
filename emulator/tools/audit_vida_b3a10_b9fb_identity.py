#!/usr/bin/env python3
"""B3A10 offline Volvo D2 B9FB forensic identity *consistency* auditor.

For source-byte evidence only. No synthetic ECU response, ECU PIN, VIN
fabrication, J2534 registration, or permission to replay. The source input is
never modified. A successful D2 parse does not prove vehicle identity.
"""
from __future__ import annotations
import argparse
import configparser
import hashlib
import json
from pathlib import Path
import re

RX_RE = re.compile(rb'PassThruReadMsgs\(\)\s+msg\[0\]\.Data\s*=\s*\[([^\]]+)\]')
OCTET = re.compile(rb'\s*0x([0-9a-fA-F]{1,2})\s*')
VIN_RE = re.compile(r'^[A-HJ-NPR-Z0-9]{17}$')
# Volvo catalog mapping is verified; interpreting THIS B9FB field as type
# remains a source-based *candidate*, never a confirmed B9FB schema.
MODEL_TYPE_CATALOG = {'275': 'XC90', '295': 'XC70', '285': 'V70',
                      '384': 'S60', '184': 'S80'}
YEAR_CODES = {**{str(y-2000): y for y in range(2001, 2010)},
              **dict(zip('ABCDEFGHJKLMNPRSTVWXY',range(2010, 2031)))}

class EvidenceError(ValueError):
    pass

def check(condition, message):
    if not condition: raise EvidenceError(message)

def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()

def parse_octets(items: bytes) -> bytes:
    cells=items.split(b',')
    if cells and not cells[-1].strip(): cells.pop()
    check(5 <= len(cells) <= 4128, 'J2534 frame length outside limits')
    check(all(OCTET.fullmatch(c) for c in cells), 'malformed J2534 hex token')
    return bytes(int(OCTET.fullmatch(c).group(1),16) for c in cells)

def extract_d2_frames(original_log: bytes) -> list[bytes]:
    check(len(original_log) <= 64*1024*1024, 'source file exceeds 64 MiB')
    frames=[parse_octets(match.group(1)) for match in RX_RE.finditer(original_log)]
    check(frames, 'source has no original DiCE/J2534 RX frames')
    return frames

def read_ini_frames(original_ini: bytes) -> list[bytes]:
    config=configparser.ConfigParser(interpolation=None,strict=True)
    config.read_string(original_ini.decode('utf-8-sig'))
    check(config.has_section('D2_50'), 'D2_50 section absent')
    count=config.getint('D2_50','B9FBFrameCount',fallback=0)
    check(2 <= count <= 64, 'D2_50 fixture frame count invalid or disabled')
    data=[]
    for index in range(count):
        name='B9FBFrame'+format(index,'X')
        raw=config.get('D2_50',name,fallback=None)
        check(raw is not None, 'missing '+name)
        check(re.fullmatch(r'(?:[0-9A-Fa-f]{2}\s+){7}[0-9A-Fa-f]{2}',raw.strip()) is not None,
              'invalid 8-byte frame in '+name)
        data.append(bytes.fromhex(raw))
    response_id=config.get('D2_50','ResponseId',fallback='01200003').strip()
    check(re.fullmatch(r'[0-9a-fA-F]{8}',response_id) is not None,'invalid response CAN ID')
    can_id=bytes.fromhex(response_id)
    return [can_id+frame for frame in data]

def reassemble(frames: list[bytes]) -> tuple[bytes,int]:
    check(2 <= len(frames) <= 64, 'unbounded/missing multi-frame B9FB')
    ids={int.from_bytes(msg[:4], 'big') for msg in frames if len(msg)>=4}
    check(len(ids)==1 and ids <= {0x01000003,0x01200003},
          'mixed or unexpected CEM 0x50 CAN response ID')
    check(all(len(msg)==12 for msg in frames), 'expected J2534 CAN ID + 8-byte D2')
    data=[msg[4:] for msg in frames]
    check(data[0][0]==0x8F and data[0][1:4]==b'\x50\xF9\xFB',
          'unverified first B9FB/target 0x50 frame')
    check(data[-1][0]==0x4F,'missing terminal 0x4F D2 frame')
    for index,frame in enumerate(data[1:-1]):
        expected=0x08+(index+1)%8
        check(frame[0]==expected,
              f'D2 continuation sequence mismatch at index {index+1}')
    stream=b''.join(frame[1:] for frame in data)
    check(stream[:3]==b'\x50\xF9\xFB','unverified D2 application echo')
    return stream[3:],next(iter(ids))

def decode_candidate(fb: bytes, target_model: str='XC90', target_year: int=2009) -> dict:
    check(len(fb)>=10 and fb[:2]==b'\x57\x00',
          'not the expected historical 0x57/0x00 B9FB sample shape')
    parts=fb[6:].split(b'\r\n')
    check(len(parts)>=8, 'not enough CRLF-delimited B9FB candidate fields')
    try: fields=[p.decode('ascii') for p in parts]
    except UnicodeDecodeError as ex: raise EvidenceError('non-ASCII candidate field') from ex
    vin=fields[1]
    model_type=fields[3]
    chassis=fields[4]
    masked_vin=(len(vin)==17 and (vin=='X'*17 or vin.count('X')>=12))
    is_vin_shape=bool(VIN_RE.fullmatch(vin)) and not masked_vin
    model_year_candidate=YEAR_CODES.get(vin[9]) if is_vin_shape else None
    candidates=[]
    if masked_vin: candidates.append('historical_VIN_is_redacted')
    elif not is_vin_shape: candidates.append('VIN_shape_invalid_or_unverified')
    if model_type in MODEL_TYPE_CATALOG and MODEL_TYPE_CATALOG[model_type]!=target_model:
        candidates.append('B9FB_type_candidate_conflicts_with_target_model')
    elif model_type not in MODEL_TYPE_CATALOG:
        candidates.append('B9FB_type_candidate_unknown')
    if is_vin_shape and model_year_candidate is not None and model_year_candidate!=target_year:
        candidates.append('VIN_model_year_conflicts_with_target')
    if is_vin_shape and len(chassis)==6 and chassis.isdigit() and vin[-6:]!=chassis:
        candidates.append('VIN_and_chassis_candidate_disagree')
    check(target_year>=2000 and target_year<=2030, 'target model year out of scope')
    return {
      'fb_bytes':len(fb),'fb_sha256':sha256(fb),
      'prefix_57_00':True,
      'vin_field_offset':fb.find(vin.encode('ascii')) if len(vin)==17 else None,
      'vin_field_length':len(vin),
      'vin_field_sha256':sha256(vin.encode('ascii')),
      'vin_redacted':masked_vin,
      'vin_shape_valid_unredacted':is_vin_shape,
      'vin_year_candidate':model_year_candidate,
      'type_field_candidate':model_type,
      'type_catalog_model':MODEL_TYPE_CATALOG.get(model_type),
      'type_semantics_verified_for_this_B9FB':False,
      'separate_chassis_field_length':len(chassis),
      'chassis_matches_vin_suffix':(vin[-6:]==chassis) if is_vin_shape else None,
      'target_model':target_model,'target_year':target_year,
      'inconsistencies_or_unknowns':candidates,
      'vehicle_identity_proven':False,'replay_approved':False,
    }

def inspect(original: bytes,source_kind: str, from_ini=False, model='XC90', year=2009) -> dict:
    check(source_kind in ('historical_public','synthetic_lab','original_unverified'),
          'unknown source provenance class')
    frames=read_ini_frames(original) if from_ini else extract_d2_frames(original)
    fb,can_id=reassemble(frames)
    result=decode_candidate(fb,model,year)
    result.update(stage='B3A10',status='TRANSPORT_VALID_IDENTITY_NOT_PROVEN',
                  source_kind=source_kind,source_sha256=sha256(original),
                  transport='P2_CAN_D2', ecu='0x50', service='B9FB',
                  can_response_id=f'0x{can_id:08X}', frame_count=len(frames),
                  transport_valid=True,original_bytes_modified=False,
                  authentic_ecu_rx_proven=False,replay_approved=False)
    return result

def compare(first:dict,second:dict) -> dict:
    check(first.get('stage')==second.get('stage')=='B3A10','incompatible reports')
    return {'historical_source_sha256':first['source_sha256'],
            'lab_source_sha256':second['source_sha256'],
            'historical_fb_sha256':first['fb_sha256'],
            'lab_fb_sha256':second['fb_sha256'],
            'same_frame_count':first['frame_count']==second['frame_count'],
            'same_fb_bytes':first['fb_sha256']==second['fb_sha256'],
            'historical_type_candidate':first['type_field_candidate'],
            'lab_type_candidate':second['type_field_candidate'],
            'historical_vin_redacted':first['vin_redacted'],
            'lab_vin_year_candidate':second['vin_year_candidate'],
            'lab_chassis_consistency':second['chassis_matches_vin_suffix'],
            'replay_approved':False}

def compare_byte_exact(source_log: bytes, lab_ini: bytes) -> dict:
    """Compare only source-supported B9FB bytes; never silently rewrite VIN."""
    source_fb,source_id=reassemble(extract_d2_frames(source_log))
    lab_fb,lab_id=reassemble(read_ini_frames(lab_ini))
    check(len(source_fb)==len(lab_fb), 'B9FB variants have different lengths; manual review')
    changed=[i for i,(a,b) in enumerate(zip(source_fb,lab_fb)) if a!=b]
    return {'historical_can_id':f'0x{source_id:08X}',
            'lab_can_id':f'0x{lab_id:08X}',
            'historical_fb_sha256':sha256(source_fb),
            'lab_fb_sha256':sha256(lab_fb),
            'changed_fb_byte_count':len(changed),
            'changed_fb_offsets':changed,
            'changes_only_in_historical_vin_field_11_to_27':
                bool(changed) and all(11<=index<=27 for index in changed),
            'source_bytes_modified':False,
            'authentic_ecu_identity_proven':False,
            'replay_approved':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--kind',choices=('historical_public','synthetic_lab','original_unverified'),required=True)
    p.add_argument('--ini',action='store_true',help='source is an INI profile, not a DiCE log')
    p.add_argument('--compare-ini',type=Path,help='compare original DiCE log to separate synthetic INI')
    p.add_argument('--model',default='XC90')
    p.add_argument('--year',type=int,default=2009)
    p.add_argument('--out',type=Path)
    a=p.parse_args()
    try:
        original=a.source.read_bytes()
        report=inspect(original,a.kind,a.ini,a.model,a.year)
        if a.compare_ini:
            check(not a.ini, '--compare-ini requires primary source to be a DiCE log')
            report['lab_comparison']=compare_byte_exact(original,a.compare_ini.read_bytes())
        output=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
        if a.out:
            with a.out.open('x',encoding='utf-8') as f:f.write(output)
        else: print(output)
    except (EvidenceError,OSError,configparser.Error,ValueError) as e:
        p.exit(2,'B3A10 REJECTED: '+str(e)+'\n')
    print('B3A10: transport parsed, identity not proven; ECU replay prohibited')

if __name__=='__main__':main()
