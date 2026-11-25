"""VC059.4: pinned offline identity and configured-route audit. No ECU I/O."""
import argparse,configparser,re,json
from pathlib import Path
from vc0593 import Gate
from vc0592 import Editor,PINS,LOCKED,canonical,strict_json,sha,require,write_json_new
from vc046_routes import build
TOPOLOGY_SHA='bf3002b7555a07843e0b49918556fe692eaafb0d4540f0e87d45d9ae0a0ab394'
IDENTITY={2:0x40,3:1,4:2,8:2,9:0x20,10:6,12:2,16:7,28:1,33:1,36:0x61,123:9}
# Explicit reviewed mapping for this simulator only. Not inferred from CarCom 000/NULL.
GGD={416:(5,0x18DA01F1,0x18DAF101),529:(2,0x18DA50F1,0x18DAF150),573:(6,0x18DA32F1,0x18DAF132),1489:(1,0x18DA10F1,0x18DAF110),1614:(7,0x18DA76F1,0x18DAF176)}
# Changes to these equipment selectors require a separate topology review.
EQUIPMENT={13,15,20,21,23,25,43,45,46,55,64,67,73,76,79,81,85,90,91,105,106,107,110,113,118,120,122,124,125,127,128,129}

def parse_ini(raw):
    c=configparser.ConfigParser(interpolation=None,strict=True);c.read_string(raw.decode('ascii'));return c

def extract_fb(c):
    s=c['D2_50'];require(s.getint('B9FBFrameCount')==13,'B9FB count')
    frames=[bytes.fromhex(s['B9FBFrame'+format(i,'X')]) for i in range(13)]
    require(all(len(f)==8 and f[0]==(0x8f if i==0 else 0x4f if i==12 else 8|(i&7)) for i,f in enumerate(frames)),'B9FB framing')
    stream=b''.join(f[1:] for f in frames);require(stream[:3]==b'\x50\xf9\xfb','B9FB echo');b=stream[3:];require(len(b)==88 and b[0]==87,'B9FB length');return b

def route_inventory(c, catalog):
    out=[]; require(c['Vehicle'].getint('ECUCount')==8,'unexpected ECU count')
    ids=[int(c[f'ECU{i}']['RequestId'],16) for i in range(8)];require(len(set(ids))==8,'duplicate request ID')
    for r in catalog['routes']:
        proto,bus,address=r['key'];vid=r['variant_id'];item=dict(catalog=r,configured=False,runtime_verified=False,physical_presence_verified=False)
        if proto=='GGD':
            i,tx,rx=GGD[vid];s=c[f'ECU{i}'];ok=(int(s['RequestId'],16),int(s['ResponseId'],16),s.getint('ExpectedBaud'))==(tx,rx,500000)
            require(ok,'GGD route mismatch: '+str(vid));item.update(configured=True,ini_section=f'ECU{i}',lab_request_id=f'{tx:08X}',lab_response_id=f'{rx:08X}',lab_baud=500000)
            if vid!=529:
                require(s['DID0Code']=='F110','F110 selector mismatch');v=bytes.fromhex(s['DID0Hex']).decode('ascii').rstrip(' ');require(v==r['variant_identifier'],'F110 lab label mismatch');item['configured_f110_label']=v
        elif vid==2160:
            sec='D2_50' if address=='50' else 'D2_40_B9F0';s=c[sec];count=s.getint('B9FBFrameCount' if address=='50' else 'FrameCount');require(count==(13 if address=='50' else 3),'CEM D2 fixture absent');require(int(s['ResponseId'],16)==(0x01200003 if address=='50' else 0x00800003),'CEM D2 response ID');item.update(configured=True,ini_section=sec,lab_response_id=s['ResponseId'],fixture_count=count)
        else:
            nodes=[s for s in c.sections() if s.startswith('D2_Node') and c[s].get('Target')=='0F' and c[s].get('Enabled')=='1']
            require(len(nodes)==3 and {c[s]['Opcode'] for s in nodes}=={'D0','D2','D4'} and all(c[s].getint('Baud')==125000 and c[s]['ResponseId']=='00800003' and c[s].getint('FrameCount')==1 for s in nodes),'CPM lab routes mismatch');item.update(configured=True,ini_sections=nodes,lab_baud=125000,lab_response_id='00800003',fixture_count=3)
        out.append(item)
    require(len(out)==8 and all(x['configured'] for x in out),'incomplete configured inventory');return out

def identity_audit(b,ini,catalog):
    require(set(IDENTITY)==LOCKED,'identity lock mismatch');require(all(b[i]==v for i,v in IDENTITY.items()),'fixed lab identity mismatch')
    c=parse_ini(ini);v=c['Vehicle']['VIN'];require(re.fullmatch('[A-HJ-NPR-Z0-9]{17}',v) and v[9]=='9' and c['Vehicle'].getint('ModelYear')==2009,'VIN syntax/year mismatch')
    fb=extract_fb(c);require(fb[11:28].decode('ascii')==v,'VIN/B9FB mismatch');require(fb[46:52].decode('ascii')==v[-6:],'B9FB chassis mismatch')
    require(c['Diagnostics'].getint('EnableGGDCemLab')==1 and c['VC054_F106Lab'].getint('Enabled')==1,'lab gate disabled')
    require(all(c[s].getint('FrameCount')==0 for s in ('D2_40_B9FC','D2_50_B9FC')),'unexpected B9FC enabled')
    return dict(vin=v,model_year=2009,b9fb_bytes=len(fb),b9fb_sha256=sha(fb),identity_codes={str(i):f'{b[i]:02X}' for i in IDENTITY},routes=route_inventory(c,catalog),b9fc_enabled=False)

class IdentityGate:
    def __init__(self,editor,topology_raw):
        require(sha(topology_raw)==TOPOLOGY_SHA,'topology SHA256 mismatch');self.catalog=build(strict_json(topology_raw));self.editor=editor;self.gate=Gate(editor)
        self.base=identity_audit(editor.block,editor.ini,self.catalog)
    def audit(self,draft):
        p=self.gate.audit(draft);b,pdu,ini,r=self.editor.compile(draft);identity=identity_audit(b,ini,self.catalog)
        require(identity==self.base,'candidate topology or identity differs from reviewed baseline')
        touched=sorted({e['offset'] for e in draft['edits']}&EQUIPMENT)
        return dict(schema='vc0594-identity-topology-audit-v1',topology_source_sha256=TOPOLOGY_SHA,selected_profile=self.catalog['selected_profile'],draft_sha256=sha(canonical(draft)),candidate_block_sha256=sha(b),identity=identity,configured_routes=8,locked_fields=len(IDENTITY),equipment_changes=touched,topology_review_required=bool(touched),policy=p,notes=['CPM lab fixtures exist independently of configured auxiliary heater','HCM route is a lab fixture; headlamp hardware not proven','CarCom CAN IDs 000/NULL are preserved, not interpreted as bus IDs'],status='blocked' if p['errors'] else 'review' if touched or p['warnings'] else 'pass',lab_only=True,topology_verified=False,physical_presence_verified=False,oem_verified=False,vida_verified=False)
    def compile(self,draft,ack=(),topology_ack=None):
        a=self.audit(draft);require(not a['policy']['errors'],'blocked by dependency policy')
        if a['topology_review_required']:require(topology_ack==sha(canonical(a)),'acknowledge exact topology audit SHA256')
        else:require(topology_ack is None,'unexpected topology acknowledgement')
        b,p,ini,r,dep=self.gate.compile(draft,ack);require(sha(b)==a['candidate_block_sha256'],'audit/compiler mismatch')
        r.update(schema='vc0594-compile-report-v1',identity_audit_sha256=sha(canonical(a)),identity_consistency_passed=True,configured_route_count=8,topology_review_acknowledged=bool(topology_ack),topology_verified=False)
        return b,p,ini,r,a
