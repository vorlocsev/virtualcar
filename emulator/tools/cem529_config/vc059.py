"""Supported offline CLI for the pinned CEM529 lab configuration. No ECU I/O."""
import argparse,json,re
from pathlib import Path
from vc0592 import Editor,PINS,LOCKED,strict_json,require,write_json_new,sha,canonical
from vc0594 import IdentityGate

FILES=dict(zip((*PINS,'store','topology'),(
 'VC041-529.private.json','VC0586-candidate.private.ini','VC0586-vida-acceptance.private.json',
 'VC0586-catalog-coverage.private.json','VC056-result.private.json',
 'VC0591-configuration-store.private.json','VC046-XC90-V8-20261125-085427.private.json')))

def outside_checkout(path):
    p=path.resolve()
    require(not any((q/'.git').exists() for q in (p,*p.parents)), 'private data/output must be outside Git checkouts')
    return p

def load_gate(folder):
    folder=outside_checkout(folder)
    raw={k:outside_checkout(folder/n).read_bytes() for k,n in FILES.items()}
    return IdentityGate(Editor(strict_json(raw['store']),[raw[k] for k in PINS]),raw['topology'])

def run(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True)
    sub=p.add_subparsers(dest='action',required=True);sub.add_parser('list');o=sub.add_parser('options');o.add_argument('offset',type=int)
    d=sub.add_parser('draft');d.add_argument('--set',action='append',default=[]);d.add_argument('--output',required=True,type=Path)
    a=sub.add_parser('audit');a.add_argument('--draft',required=True,type=Path);a.add_argument('--output',type=Path)
    c=sub.add_parser('compile');c.add_argument('--draft',required=True,type=Path);c.add_argument('--output',required=True,type=Path);c.add_argument('--ack',action='append',default=[]);c.add_argument('--topology-ack');c.add_argument('--audit-sha',required=True)
    x=p.parse_args(argv);g=load_gate(x.data);e=g.editor
    if x.action=='list':r=[dict(offset=i,name=v['as_name'],code=v['raw_hex'],text=v['as_text'],locked=i in LOCKED) for i,v in sorted(e.rows.items())]
    elif x.action=='options':r=e.options(x.offset)
    elif x.action=='draft':
        edits=[]
        for item in x.set:
            require(re.fullmatch(r'[0-9]{1,3}=[0-9A-Fa-f]{2}',item) is not None,'use decimal OFFSET=HEX');i,v=item.split('=');edits.append(dict(offset=int(i),code=v.upper()))
        r=e.draft(edits);write_json_new(outside_checkout(x.output),r)
    else:
        d=strict_json(outside_checkout(x.draft).read_bytes());audit=g.audit(d);digest=sha(canonical(audit))
        if x.action=='audit':
            r=dict(audit=audit,audit_sha256=digest)
            if x.output:write_json_new(outside_checkout(x.output),r)
            print(json.dumps(r,ensure_ascii=True,indent=2));return 2 if audit['status']=='blocked' else 0
        require(x.audit_sha==digest,'compile requires exact current audit SHA256')
        b,pdu,ini,r,au=g.compile(d,x.ack,x.topology_ack);out=outside_checkout(x.output);out.mkdir(exist_ok=False)
        for name,data in [('f106-block.private.bin',b),('f106-pdu.private.bin',pdu),('virtualcar.ini',ini)]:
            with (out/name).open('xb') as f:f.write(data)
        write_json_new(out/'VC0594-identity.private.json',au);write_json_new(out/'VC0594-compile.private.json',r)
    print(json.dumps(r,ensure_ascii=True,indent=2));return 0
if __name__=='__main__':raise SystemExit(run())
