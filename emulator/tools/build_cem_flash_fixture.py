#!/usr/bin/env python3
"""Build a private read-only D2 B9FB/B9FC fixture from a verified 320-KiB P2 M32C Flash.

Only the observed XC90 type 275, 88-byte FB and FC140 layout are accepted.
Never modifies input. Does NOT decode PIN/key/security information.
For privacy the fixture is *only* written with --private (explicit opt-in).
Response ID for FC is an UNVERIFIED laboratory assumption until traced on a vehicle.
"""
from __future__ import annotations
import argparse
import configparser
from pathlib import Path
import hashlib
import re

FB_OFFSET=0x4A000
FC_OFFSET=0x4A100
MODEL_YEAR_CODES='123456789ABCDEFGHJKLMNPRSTVWXY'
VIN_PATTERN=re.compile(rb'[A-HJ-NPR-Z0-9]{17}')

def inspect_flash(data:bytes):
    if len(data)!=320*1024:
        raise ValueError('This tool accepts exactly 320 KiB M32C Flash images')
    fb=data[FB_OFFSET:FB_OFFSET+88]
    fc=data[FC_OFFSET:FC_OFFSET+142]
    if len(fb)!=88 or fb[0]!=87 or fb[9:11]!=b'\r\n' or fb[-2:]!=b'\r\n':
        raise ValueError('Observed XC90 FB88 format not found at 0x4A000')
    fields=fb[6:].split(b'\r\n')
    if len(fields)!=9 or fields[-1]!=b'' or not VIN_PATTERN.fullmatch(fields[1]):
        raise ValueError('Eight CRLF fields or VIN not found')
    vin=fields[1].decode('ascii')
    if fields[3]!=b'275':
        raise ValueError('Not the verified XC90 vehicle type 275')
    if fields[4]!=vin[-6:].encode('ascii'):
        raise ValueError('VIN and chassis-number fields disagree')
    yearcode=vin[9]
    if yearcode not in MODEL_YEAR_CODES:
        raise ValueError('Unsupported model-year code')
    year=2001+MODEL_YEAR_CODES.index(yearcode)
    if fc[0]!=140 or fc[1]!=(sum(fc[2:])&0xff):
        raise ValueError('FC140 checksum mismatch')
    return fb,fc,vin,year

def d2_frames(payload:bytes,target:int,opcode:int):
    stream=bytes((target,0xF9,opcode))+payload
    frames=[]
    for index,pos in enumerate(range(0,len(stream),7)):
        fragment=stream[pos:pos+7]
        first=index==0
        last=pos+7>=len(stream)
        if first and last: header=0xC8+len(fragment)
        elif first: header=0x88+len(fragment)
        elif last: header=0x48+len(fragment)
        else: header=0x08+(index%8)
        frames.append(bytes((header,))+fragment+b'\0'*(7-len(fragment)))
    return frames

def build_ini(template:str,fb:bytes,fc:bytes,vin:str,year:int):
    c=configparser.ConfigParser(interpolation=None)
    c.optionxform=str
    c.read_string(template)
    for name in ('Vehicle','P2','D2_50','D2_50_B9FC'):
        if not c.has_section(name): c.add_section(name)
    c['Vehicle']['VIN']=vin
    c['Vehicle']['ModelYear']=str(year)
    c['Vehicle']['ECUCount']='1'
    c['P2']['StrictRouting']='1'
    c['P2']['FixtureProvenance']='private_consistent_2005_XC90_V8_M32C_flash_donor; FC_response_CAN_ID_unverified'
    for section,opcode,data,response_id in [('D2_50',0xFB,fb,'01200003'),('D2_50_B9FC',0xFC,fc,'01200003')]:
        frames=d2_frames(data,0x50,opcode)
        c[section]['ResponseId']=response_id
        c[section]['FrameCount']=str(len(frames))
        if opcode==0xFB:c[section]['B9FBFrameCount']=str(len(frames))
        for i,frame in enumerate(frames):
            key=('B9FBFrame' if opcode==0xFB else 'Frame')+f'{i:X}'
            c[section][key]=' '.join(f'{v:02X}' for v in frame)
    import io
    out=io.StringIO();c.write(out,space_around_delimiters=True)
    return out.getvalue()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('flash',type=Path)
    ap.add_argument('--template',type=Path,required=True)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--private',action='store_true',help='Required to write personal VIN from Flash to output fixture')
    a=ap.parse_args()
    data=a.flash.read_bytes()
    fb,fc,vin,year=inspect_flash(data)
    print(f'Image size: {len(data)}; sha256: {hashlib.sha256(data).hexdigest()}')
    print(f'XC90 type 275, model year {year}, VIN: {vin[:3]}**********{vin[13:]}')
    print(f'FB {len(fb)} bytes / {len(d2_frames(fb,0x50,0xFB))} D2 frames')
    print(f'FC {len(fc)} bytes / {len(d2_frames(fc,0x50,0xFC))} D2 frames; checksum verified')
    if a.output:
        if not a.private:ap.error('--private must be explicitly set to write identifying data')
        if a.output.resolve()==a.flash.resolve():ap.error('output must not overwrite input')
        a.output.write_text(build_ini(a.template.read_text(),fb,fc,vin,year),encoding='utf-8')
        print(f'Private INI written to {a.output} (do not publish)')

if __name__=='__main__':main()
