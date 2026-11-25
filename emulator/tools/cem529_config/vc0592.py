"""Offline VC059.2 editor: immutable baseline, explicit lab drafts, no ECU I/O."""
import argparse, json, re
from pathlib import Path
from vc0591 import PINS, FIELDS, sha, require, index, locate, valid_block, compile_snapshot, Schema

BASE_SCHEMA='vc0592-cem529-lab-draft-v1'
# Temporary identity/vehicle profile locks until the identity and topology stage.
LOCKED={2,3,4,8,9,10,12,16,28,33,36,123}
BAD_TEXT={None,'','Undefined value','Parameter error','Faulty value'}

def canonical(doc):
    return (json.dumps(doc,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('utf8')

def strict_json(raw):
    def pairs(p):
        d={}
        for k,v in p:
            require(k not in d,'duplicate JSON key: '+k);d[k]=v
        return d
    return json.loads(raw,object_pairs_hook=pairs)

class Editor:
    def __init__(self, store, raw):
        self.baseline=store
        self.raw=raw
        self.block,self.pdu,self.ini=compile_snapshot(store,*raw)
        self.schema=Schema(strict_json(raw[0]))
        self.rows=index(store['entries'])
        self.baseline_sha=sha(canonical(store))
    def options(self, offset):
        require(type(offset) is int and offset in FIELDS,'not a mapped byte')
        n=self.schema.fields[offset];counts={}
        for v in n['values']:
            if v['operator']==1:
                c=int(v['compare'],16);counts[c]=counts.get(c,0)+1
        options=[]
        for v in n['values']:
            if v['operator']!=1:continue
            c=int(v['compare'],16)
            options.append(dict(code=f'{c:02X}',row_id=v['Id'],as_text=v['as_text'],ppe_text=v['ppe_text'],as_unit=v['as_unit'],ppe_unit=v['ppe_unit'],selectable=(offset not in LOCKED and c!=255 and counts[c]==1 and v['as_text'] not in BAD_TEXT)))
        return dict(offset=offset,name=n['as_name'],node_id=n['id'],baseline_code=f'{self.block[offset]:02X}',locked=offset in LOCKED,options=options)
    def selection(self,i,code):
        require(type(i) is int and i in FIELDS,'unknown or unmapped offset')
        require(i not in LOCKED,'identity field locked until VC059.4')
        require(isinstance(code,str) and re.fullmatch(r'[0-9A-F]{2}',code) is not None,'code must be two uppercase hex digits')
        candidates=[x for x in self.options(i)['options'] if x['code']==code and x['selectable']]
        require(len(candidates)==1,'unlisted, ambiguous or error code')
        v=candidates[0];require(code!=f'{self.block[i]:02X}','no-op edit; omit unchanged field')
        return dict(offset=i,name=self.rows[i]['as_name'],node_id=self.rows[i]['node_id'],old_code=f'{self.block[i]:02X}',old_text=self.rows[i]['as_text'],new_code=code,new_text=v['as_text'],new_row_id=v['row_id'],ppe_text=v['ppe_text'],as_unit=v['as_unit'],ppe_unit=v['ppe_unit'],gui_status='not_tested')
    def draft(self,edits):
        require(isinstance(edits,list) and len(edits)<=len(FIELDS),'invalid edit list')
        seen=set();rows=[]
        for e in edits:
            require(isinstance(e,dict) and set(e)=={'offset','code'},'unexpected edit keys')
            i=e['offset'];require(type(i) is int and i not in seen,'invalid or duplicate edit offset');seen.add(i)
            rows.append(self.selection(i,e['code']))
        rows.sort(key=lambda x:x['offset'])
        return dict(schema=BASE_SCHEMA,baseline_snapshot_sha256=self.baseline_sha,baseline_block_sha256=sha(self.block),dictionary_sha256=PINS['dictionary'],variant=529,profile_id=163120,lab_only=True,oem_verified=False,vida_verified=False,physical_j2534_verified=False,dependencies_verified=False,topology_verified=False,baseline_historical_gui_rows=127,edits=rows)
    def compile(self,draft):
        require(isinstance(draft,dict) and isinstance(draft.get('edits'),list),'invalid draft')
        edits=[dict(offset=r['offset'],code=r['new_code']) for r in draft['edits']]
        expected=self.draft(edits)
        require(canonical(draft)==canonical(expected),'draft differs from validated selection or evidence')
        b=bytearray(self.block)
        for r in expected['edits']:b[r['offset']]=int(r['new_code'],16)
        b[1]=sum(b[2:])%256;b=bytes(b)
        require(valid_block(b),'invalid compiled block')
        changed=[i for i in range(len(b)) if b[i]!=self.block[i]]
        require(set(changed)-{1}=={r['offset'] for r in expected['edits']},'unexpected byte change')
        m=locate(self.ini);ini=self.ini[:m.start(1)]+b.hex().encode()+self.ini[m.end(1):]
        require(bytes.fromhex(locate(ini)[1].decode())==b,'INI mismatch')
        pdu=b'\x62\xf1\x06'+b
        report=dict(schema='vc0592-compile-report-v1',draft_sha256=sha(canonical(expected)),baseline_ini_sha256=sha(self.ini),candidate_ini_sha256=sha(ini),block_sha256=sha(b),pdu_sha256=sha(pdu),changed_offsets=changed,changed_parameter_count=len(edits),checksum_changed=1 in changed,unmapped_preserved=all(b[i]==self.block[i] for i in (0,7)),tail_preserved=b[130:]==self.block[130:],lab_only=True,oem_verified=False,vida_verified=False,dependencies_verified=False,topology_verified=False,physical_j2534_verified=False,windows_verified=False,baseline_historical_gui_rows=127,edits=expected['edits'])
        return b,pdu,ini,report

def write_json_new(path,doc):
    with path.open('xb') as f:f.write((json.dumps(doc,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
