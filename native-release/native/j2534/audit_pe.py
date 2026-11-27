"""Strict PE export/import check for the isolated Windows x86 candidate."""
import argparse
import struct
from pathlib import Path
EXPECTED = {'PassThru'+s for s in ('Open','Close','Connect','Disconnect','ReadMsgs','WriteMsgs','StartPeriodicMsg','StopPeriodicMsg','StartMsgFilter','StopMsgFilter','SetProgrammingVoltage','ReadVersion','GetLastError','Ioctl')}
ALLOWED = {'kernel32.dll'}
def audit(data):
    def need(ok, msg):
        if not ok: raise ValueError(msg)
    def read(fmt, off):
        need(0 <= off <= len(data)-struct.calcsize(fmt), 'Truncated PE')
        return struct.unpack_from(fmt,data,off)
    def u16(o): return read('<H',o)[0]
    def u32(o): return read('<I',o)[0]
    need(data[:2]==b'MZ','Missing MZ'); p=u32(60)
    need(data[p:p+4]==b'PE\0\0','Missing PE'); machine, count=read('<HH',p+4)
    opt=p+24; size=u16(p+20)
    need(machine==0x14c and u16(opt)==0x10b and u16(p+22)&0x2000,'Not x86 PE32 DLL')
    need(size>=224 and u32(opt+92)>=16 and 0<count<=96,'Invalid optional header')
    sections=[]
    for i in range(count):
        vsize,va,rawsize,raw=read('<IIII',opt+size+i*40+8)
        need(raw+rawsize<=len(data),'Truncated section'); sections.append((va,rawsize,raw))
    def locate(rva,n=1):
        hits=[raw+rva-va for va,sz,raw in sections if va<=rva and rva+n<=va+sz]
        need(len(hits)==1,'Invalid RVA'); return hits[0]
    def string(rva):
        raw=locate(rva); end=data.find(b'\0',raw,min(raw+256,len(data)))
        need(end>=raw,'Unterminated name'); locate(rva,end-raw+1); return data[raw:end].decode('ascii')
    exp,esz,imp,isz=read('<IIII',opt+96)
    need(exp and esz>=40 and imp and isz>=20,'Missing exports/imports')
    e=locate(exp,40); funcs,names,ft,nt,ot=read('<IIIII',e+20)
    need(funcs==names==len(EXPECTED),'Wrong export count')
    found=set(); ords=set()
    for i in range(names):
        name=string(u32(locate(nt+4*i,4))); idx=u16(locate(ot+2*i,2))
        need(idx<funcs and idx not in ords and name not in found,'Duplicate export'); ords.add(idx); found.add(name)
        target=u32(locate(ft+4*idx,4)); need(target and not exp<=target<exp+esz,'Forwarded/null export'); locate(target)
    need(found==EXPECTED,'Unexpected export names')
    modules=set(); terminated=False
    for i in range(min(isz//20,256)):
        fields=read('<IIIII',locate(imp+i*20,20))
        if not any(fields): terminated=True;break
        need(fields[3]!=0,'Missing import name'); modules.add(string(fields[3]).lower())
    need(terminated and modules==ALLOWED,'Unexpected imports: '+str(modules))
    delay,delay_size=read('<II',opt+96+13*8);need(not delay and not delay_size,'Delay imports not allowed')
    return sorted(found),sorted(modules)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('dll',type=Path);a=p.parse_args()
    exports,imports=audit(a.dll.read_bytes());print('VC108P_PE=PASS x86 exports='+str(len(exports))+' imports='+','.join(imports))
