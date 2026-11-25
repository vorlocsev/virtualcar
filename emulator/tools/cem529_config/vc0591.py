"""VC059.1: reproducible accepted lab configuration snapshot, offline only."""
import argparse, hashlib, json, re
from pathlib import Path
from vc04_manager import Schema

PINS={
 'dictionary':'5a572a8cf0a1f80ba8040ff6275925ffd15bd649b98d0314c374f8992f46bbfb',
 'ini':'c6d8b7b36382bce1fdbc7cf1a639175ae1c64137782904420059cec1be537f88',
 'acceptance':'3d8ef295c36f97c6598eea7aa96f4fb7f39c8a2240fa707ac4bf7f112456629c',
 'coverage':'acd6b6e51a750674a2877f444c0be22f3ee2982253dc3270c298238eb0c59c49',
 'windows':'68a277cc4ec11699b838c1aec215012ebaeed1c6a633af50de74e5408bf96217'}
COMMIT='21da0c32044c6f9e103fc3ab41cb8547ae2d6bc0'
BLOCK='9ed8c40c472a33d45ea31dd8f700aabac20397f04319afd15ec4f67ca2d7b9c6'
FIELDS=set(range(130))-{0,1,7}

def sha(b):return hashlib.sha256(b).hexdigest()
def require(x,msg):
    if not x:raise ValueError(msg)
def pinned(role,raw):
    require(sha(raw)==PINS[role],role+' SHA256 mismatch');return raw

def locate(raw):
    # Match only the one exact reviewed F106 section, not a global arbitrary key.
    m=list(re.finditer(rb'(?m)^\[VC054_F106Lab\]\r?\nBlockHex=([0-9a-f]{284})\r?\nLayout=donor-142\r?\nEnabled=1\r?$',raw))
    require(len(m)==1,'missing/ambiguous exact lab section')
    return m[0]
def valid_block(b):return len(b)==142 and b[0]==0x8c and b[1]==sum(b[2:])%256

def index(rows):
    require(isinstance(rows,list) and len(rows)==127,'row count')
    d={}
    for row in rows:
        i=row['offset'];require(type(i)==int and i in FIELDS and i not in d,'invalid/duplicate offset');d[i]=row
    require(set(d)==FIELDS,'incomplete positions');return d

def derive(dictionary,ini,acceptance,coverage,windows):
    raws=dict(dictionary=dictionary,ini=ini,acceptance=acceptance,coverage=coverage,windows=windows)
    for k,v in raws.items():pinned(k,v)
    schema=Schema(json.loads(dictionary));require(schema.variant==529,'wrong variant')
    a=json.loads(acceptance);c=json.loads(coverage);w=json.loads(windows)
    require(a['schema']=='vc0586-vida-gui-acceptance-v1' and a['full_gui_regression_verified'] is True and a['matched']==127 and a['mismatches']==0 and a['undefined_value_count']==a['parameter_error_count']==0,'acceptance incomplete')
    require(a['local_candidate_ini_sha256']==PINS['ini'] and a['catalog_coverage_sha256']==PINS['coverage'] and a['block_sha256']==BLOCK,'acceptance hashes')
    require(a['lab_only'] is True and a['oem_verified'] is False and a['installed_ini_sha256_verified'] is False and a['installed_dll_sha256_verified_this_run'] is False and a['fresh_transport_trace_verified'] is False,'acceptance scope')
    require(w['commit']==COMMIT and w['status']=='passed' and len(w['cases'])==23 and all(r['pass'] is True for r in w['cases']),'Windows evidence')
    b=bytes.fromhex(locate(ini)[1].decode());require(valid_block(b) and sha(b)==BLOCK,'baseline block mismatch')
    aa=index(a['entries']);cc=index(c['entries']);rows=[]
    for i in sorted(FIELDS):
        n=schema.fields[i];v=[x for x in n['values'] if x['operator']==1 and int(x['compare'],16)==b[i]]
        require(len(v)==1,'ambiguous selected code');v=v[0]
        require(v['as_text'] not in (None,'','Undefined value','Parameter error'),'invalid selected text')
        exact=dict(offset=i,raw_hex=f'{b[i]:02X}',as_name=n['as_name'],as_text=v['as_text'],row_id=v['Id'])
        for e in (aa[i],cc[i]):require(all(e[k]==x for k,x in exact.items()) and e['oem_verified'] is False,'catalog/evidence mismatch')
        require(aa[i]['gui_status']=='passed' and aa[i]['observed']==v['as_text'],'GUI mismatch')
        rows.append(dict(**exact,node_id=n['id'],ppe_text=v['ppe_text'],as_unit=v['as_unit'],ppe_unit=v['ppe_unit'],gui_baseline_observed=aa[i]['observed'],screenshots=aa[i]['screenshots']))
    return {'schema':'vc0591-cem529-lab-store-v1','variant':529,'profile_id':163120,'layout':'donor-142','metadata_bytes':130,'block_bytes':142,'source_sha256':PINS.copy(),'source_commit':COMMIT,'dll_sha256':w['builds']['patched']['dll_sha256'],'block_sha256':BLOCK,'lab_only':True,'oem_verified':False,'physical_j2534_verified':False,'baseline_gui_rows':127,'installed_hash_verified':False,'fresh_transport_verified':False,'unmapped':{'0':f'{b[0]:02X}','7':f'{b[7]:02X}'},'checksum_policy':'lab-sum8-bytes-2-through-141','tail_hex':b[130:].hex().upper(),'entries':rows}

def compile_snapshot(store, dictionary, ini, acceptance, coverage, windows):
    # Re-derive authority, reject any altered snapshot; editing is a separate stage.
    expected=derive(dictionary,ini,acceptance,coverage,windows)
    require(json.dumps(store,sort_keys=True,ensure_ascii=False)==json.dumps(expected,sort_keys=True,ensure_ascii=False),'store differs from reviewed immutable snapshot')
    b=bytearray(142);b[0]=int(store['unmapped']['0'],16);b[7]=int(store['unmapped']['7'],16);b[130:]=bytes.fromhex(store['tail_hex'])
    for i,r in index(store['entries']).items():b[i]=int(r['raw_hex'],16)
    b[1]=sum(b[2:])%256
    require(valid_block(b) and sha(b)==BLOCK,'compiled block mismatch')
    m=locate(ini);output=ini[:m.start(1)]+b.hex().encode()+ini[m.end(1):]
    require(output==ini,'compiled INI mismatch')
    return bytes(b),b'\x62\xf1\x06'+bytes(b),output

def inputs(a):return [(getattr(a,k)).read_bytes() for k in ('dictionary','ini','acceptance','coverage','windows')]
