"""Offline CarCom metadata buffer inspector. No ECU, J2534, INI or checksum generation."""
import argparse
import json
import re
from pathlib import Path

VARIANTS = {2160: ('31296075 AA', '0xfc', 'BLOFF', 130),
            529: ('30682825 A', '0xf106', 'REID', 130),
            3018: ('31327407 AA', '0xfc', 'BLOFF', 133)}

def load(path):
    path = Path(path)
    if path.stat().st_size > 4*1024*1024:
        raise ValueError('Dictionary too large')
    return Schema(json.loads(path.read_text(encoding='utf-8-sig')))

class Schema:
    def __init__(self, doc):
        self.variant = doc['variant']
        identifier, selector, kind, self.size = VARIANTS[self.variant]
        root = doc['root']
        if (doc['schema'], doc['identifier'], doc['selector'], root['kind'], root['length'], doc['root_metadata_bits']) != ('vc03-carcom-tree-v1', identifier, selector, kind, self.size*8, self.size*8):
            raise ValueError('Schema identity mismatch')
        self.fields = {}
        for n in doc['nodes']:
            p = n['offset']
            if type(p) is not int or not 0 <= p < self.size*8 or p%8 or n['effective_bit_offset'] != p or not n['direct_root_child'] or n['path'] != [root['id'], n['id']] or not n['direct_range_valid'] or (n['length'], n['kind'], n['data_type'], n['exclude'], n['composite']) != (8,'PARAM',2,0,0):
                raise ValueError('Unsupported field shape')
            i = p//8
            if i in self.fields: raise ValueError('Overlapping fields')
            for v in n['values']:
                if v['operator'] == 1:
                    if not re.fullmatch(r'0x[0-9a-fA-F]{1,2}', v['compare']): raise ValueError('Invalid enum')
                elif v['operator'] != 0 or v['compare'] != '': raise ValueError('Unsupported operator')
            self.fields[i] = n
        if set(self.fields) != set(range(self.size))-{0,1,7} or len(self.fields) != doc['direct_param_count'] or sum(len(n['values']) for n in self.fields.values()) != doc['value_rows']:
            raise ValueError('Incomplete map')
    def decode(self, buffer):
        if len(buffer) != self.size: raise ValueError('Wrong buffer length')
        out=[]
        for i, raw in enumerate(buffer):
            n = self.fields.get(i)
            if n is None:
                out.append({'offset':i,'raw':raw,'status':'unmapped','name':None,'matches':[]}); continue
            matches = [v for v in n['values'] if v['operator']==1 and int(v['compare'],16)==raw]
            status = 'ambiguous' if len(matches)>1 else 'exact_code' if matches else 'unlisted_code'
            out.append({'offset':i,'raw':raw,'name':n['name'] or None,'status':status,'matches':matches,'fallback':[v for v in n['values'] if v['operator']==0] if not matches else []})
        return out
    def rebuild(self, rows):
        if len(rows)!=self.size or any(type(r['offset']) is not int or r['offset']!=i or type(r['raw']) is not int or not 0<=r['raw']<=255 for i,r in enumerate(rows)):
            raise ValueError('Invalid complete buffer rows')
        return bytes(r['raw'] for r in rows)

def compare(a,b):
    def codes(n): return {int(v['compare'],16) for v in n['values'] if v['operator']==1}
    def sig(n): return [{k:v for k,v in x.items() if k!='Id'} for x in n['values']]
    shared=sorted(a.fields.keys() & b.fields.keys())
    differences=[]
    for i in shared:
        x,y=a.fields[i],b.fields[i]
        if x['name']!=y['name'] or x['text_id']!=y['text_id'] or sig(x)!=sig(y):
            differences.append({'offset':i,'a_name':x['name'],'b_name':y['name'],'a_only_codes':sorted(codes(x)-codes(y)),'b_only_codes':sorted(codes(y)-codes(x)), 'a_text_id':x['text_id'],'b_text_id':y['text_id'],'value_rows_equal':sig(x)==sig(y),'a_values':x['values'],'b_values':y['values']})
    return {'variants':[a.variant,b.variant],'shared_offsets':len(shared),'same_names':sum(a.fields[i]['name']==b.fields[i]['name'] for i in shared),'same_code_sets':sum(codes(a.fields[i])==codes(b.fields[i]) for i in shared),'same_value_rows':sum(sig(a.fields[i])==sig(b.fields[i]) for i in shared),'only_a':sorted(a.fields.keys()-b.fields.keys()),'only_b':sorted(b.fields.keys()-a.fields.keys()),'differences':differences,'wire_format_verified':False}
