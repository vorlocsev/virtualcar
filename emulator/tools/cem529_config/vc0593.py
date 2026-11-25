"""VC059.3 offline policy gate for CEM529 lab drafts; no vehicle I/O."""
import argparse,json
from pathlib import Path
from vc0592 import Editor,PINS,canonical,strict_json,sha,require,write_json_new

# Explicit scenario policy, not extracted OEM dependency rules. Numeric codes
# refer only to the pinned CEM529 dictionary; no semantic inference from labels.
RULES = (
 ('PETROL_HEATER','error',(33,23),'Diesel heater selected for petrol lab scenario',lambda b:b[33]==1 and b[23] in (3,4,5)),
 ('AUTO_STARTBLOCK','error',(8,71),'Manual gearbox startblock selected with automatic gearbox',lambda b:b[8]==2 and b[71]==2),
 ('AC_HEATER_ONLY','error',(20,21),'Air conditioning enabled with standard heater only',lambda b:b[20]==2 and b[21]==1),
 ('AC_REAR','error',(20,105),'Rear air conditioning enabled while air conditioning is absent',lambda b:b[20]==1 and b[105]==2),
 ('AC_CLIMATE','error',(20,21),'Air conditioning absent with AC/ECC climate unit',lambda b:b[20]==1 and b[21] in (2,5,6,7,9)),
 ('AQS_FILTER','warning',(21,75),'ECC/AQS and AQS filter selections differ; review equipment',lambda b:(b[21]==6)!=(b[75]==4)),
 ('PARK_AEM','error',(64,76),'AEM parking assistance selected without AEM',lambda b:b[64] in (2,5) and b[76]==1),
 ('AIRBAG_SWITCH','error',(73,113),'Passenger airbag cut-off switch present without passenger airbag',lambda b:b[73]==1 and b[113]==2),
 ('OWS_CAL','error',(91,116),'OWS calibration selected while OWS is absent',lambda b:b[91] in (1,5) and b[116]!=1),
 ('TPMS_LOAD','error',(79,112),'Tyre pressure warning and heavy-load warning selections disagree',lambda b:(b[79]==1)!=(b[112]==0x22)),
 ('XENON_ADJUST','error',(81,55),'Active bi-xenon with auto adjust requires automatic adjust in lab',lambda b:b[81] in (0x11,0x12) and b[55]!=3),
 ('ALARM_OPTIONS','warning',(46,47,48,49,50,51,77,83),'Alarm accessories selected without alarm scenario; review',lambda b:b[46] in (1,4) and any((b[47]!=1,b[48]==1,b[49]==2,b[50]==2,b[51]!=1,b[77]==2,b[83]==2))),
 ('HEATER_CALL','warning',(23,25,84),'Remote heater start without configured fuel/electric heater; review accessory',lambda b:b[23]==1 and b[25]==1 and b[84]!=1),
 ('RTI_CONTROL','warning',(43,85),'RTI regional system selected without RTI control unit',lambda b:b[85] not in (1,2,3,8) and b[43]==1),
 ('AUDIO_AMP','warning',(45,67),'Amplifier selected with no radio; review infotainment',lambda b:b[45]==1 and b[67]!=1),
 ('AUDIO_SYSTEM','warning',(45,107),'Infotainment system radio selected while infotainment absent',lambda b:b[45]==0x59 and b[107]==1),
)
POLICY='vc0593-cem529-xc90-lab-policy-v1'

class Gate:
    def __init__(self,editor):self.editor=editor
    def audit(self,draft):
        b,pdu,ini,report=self.editor.compile(draft)
        findings=[]
        for rid,severity,fields,msg,predicate in RULES:
            triggered=bool(predicate(b))
            findings.append(dict(id=rid,severity=severity,offsets=list(fields),message=msg,status='triggered' if triggered else 'clear',values=[dict(offset=i,code=f'{b[i]:02X}') for i in fields]))
        errors=[r['id'] for r in findings if r['status']=='triggered' and r['severity']=='error']
        warnings=[r['id'] for r in findings if r['status']=='triggered' and r['severity']=='warning']
        audit=dict(schema='vc0593-policy-audit-v1',policy=POLICY,draft_sha256=sha(canonical(draft)),candidate_block_sha256=sha(b),rules=len(RULES),errors=errors,warnings=warnings,policy_status='blocked' if errors else 'review' if warnings else 'pass',findings=findings,lab_only=True,oem_dependencies_verified=False,vida_verified=False,topology_verified=False,windows_verified=False,physical_j2534_verified=False)
        return audit
    def compile(self,draft,ack=()):
        audit=self.audit(draft)
        require(not audit['errors'],'blocked by lab policy: '+','.join(audit['errors']))
        require(len(set(ack))==len(ack) and set(ack)==set(audit['warnings']),'acknowledge exactly current warning IDs: '+','.join(audit['warnings']))
        b,pdu,ini,report=self.editor.compile(draft)
        require(sha(b)==audit['candidate_block_sha256'],'audit/compiler mismatch')
        report.update(schema='vc0593-compile-report-v1',policy_audit_sha256=sha(canonical(audit)),lab_policy_passed=True,acknowledged_warnings=sorted(ack),oem_dependencies_verified=False)
        return b,pdu,ini,report,audit
