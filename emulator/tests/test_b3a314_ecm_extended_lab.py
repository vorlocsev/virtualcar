"""Host-only compiled check of the exact B3A314 helper; no VIDA or native DLL."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "src" / "virtualcar.c"
START = "static U32 answer_b3a314_ecm_live_lab("
HARNESS = r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
typedef uint8_t U8;
typedef uint32_t U32;
#define PROTO_ISO15765 6u
#define CAN_29BIT_ID 0x100u
typedef struct { U32 api_protocol,protocol,baud,flags; } CHANNEL;
typedef struct { U32 req,resp,expected_baud; } ECU;
static U32 g_b3a314_ecm_live_lab=0;
static void logline(const char *s,const U8 *p,U32 n){(void)s;(void)p;(void)n;}
'''
MAIN = r'''
int main(void){
    CHANNEL c={6,6,500000,0x100};
    ECU e={0x18DA10F1,0x18DAF110,500000};
    U8 req[4]={0x22,0xD9,0xAC,0},out[8];
    const U32 id=e.req;
    const struct {U32 did,n;U8 data[4];} cases[]={
        {0xD9AC,2,{0x00,0x00}},
        {0xD9AD,2,{0x00,0x00}},
        {0xD9B8,1,{0x60}},
        {0xF404,1,{0x00}},
        {0xF405,1,{0x3C}},
        {0xF410,2,{0x00,0x00}},
        {0xF433,1,{0x64}},
        {0xF449,1,{0x00}},
        {0xF44A,1,{0x00}},
        {0xF40B,1,{0x64}},
        {0xD9A4,1,{0xC8}},
        {0xDA47,2,{0x33,0x33}},
        {0xF443,2,{0,0}},
        {0xD994,4,{0,0,0,0}}
    };
    U32 i;
#define CALL() answer_b3a314_ecm_live_lab(&c,&e,id,0x100,req,3,out)
    assert(CALL()==0);g_b3a314_ecm_live_lab=1;
    for(i=0;i<sizeof(cases)/sizeof(cases[0]);i++){
        req[1]=(U8)(cases[i].did>>8);req[2]=(U8)cases[i].did;
        memset(out,0xCC,sizeof(out));
        assert(CALL()==3+cases[i].n);
        assert(out[0]==0x62 && out[1]==req[1] && out[2]==req[2]);
        assert(memcmp(out+3,cases[i].data,cases[i].n)==0);
        assert(out[3+cases[i].n]==0xCC);
    }
    req[1]=0x12;req[2]=0x0D;assert(CALL()==0);req[1]=0xD9;req[2]=0xAE;assert(CALL()==0);req[2]=0xAC;
    req[0]=0x2E;assert(CALL()==0);req[0]=0x22;
    assert(answer_b3a314_ecm_live_lab(&c,&e,id,0x100,req,2,out)==0);
    assert(answer_b3a314_ecm_live_lab(&c,&e,id,0x100,req,4,out)==0);
    c.baud=125000;assert(CALL()==0);c.baud=500000;
    c.protocol=5;assert(CALL()==0);c.protocol=6;
    c.api_protocol=5;assert(CALL()==0);c.api_protocol=6;
    c.flags=0;assert(CALL()==0);c.flags=0x100;
    assert(answer_b3a314_ecm_live_lab(&c,&e,id,0,req,3,out)==0);
    assert(answer_b3a314_ecm_live_lab(&c,&e,id,0x101,req,3,out)==0);
    assert(answer_b3a314_ecm_live_lab(&c,&e,id,0x140,req,3,out)==5);
    assert(answer_b3a314_ecm_live_lab(&c,&e,0x7DF,0x100,req,3,out)==0);
    e.req=0x18DA50F1;assert(CALL()==0);e.req=id;
    e.resp=0x18DAF150;assert(CALL()==0);e.resp=0x18DAF110;
    e.expected_baud=0;assert(CALL()==0);e.expected_baud=500000;
    assert(answer_b3a314_ecm_live_lab(0,&e,id,0x100,req,3,out)==0);
    assert(answer_b3a314_ecm_live_lab(&c,&e,id,0x100,0,3,out)==0);
    assert(answer_b3a314_ecm_live_lab(&c,&e,id,0x100,req,3,0)==0);
    puts("B3A314_ECM_HELPER_PASS");return 0;
}
'''

class TestEcmExtendedLiveLab(unittest.TestCase):
    def test_exact_helper(self):
        source=SOURCE.read_text(encoding="utf-8")
        self.assertEqual(source.count(START),1)
        pos=source.index(START)
        helper=source[pos:source.index("\n}",pos)+2]
        model_start=source.index("/* B3A315 shared synthetic ECM snapshot;")
        model_end=source.index("/* B3A315 shared ECM snapshot end */",model_start)
        helper=source[model_start:model_end]+helper
        compiler=shlex.split(os.environ["CC"]) if os.environ.get("CC") else [shutil.which("gcc") or shutil.which("clang") or "gcc"]
        with tempfile.TemporaryDirectory(prefix="b3a314-") as tmp:
            c=Path(tmp)/"check.c"
            exe=Path(tmp)/("check.exe" if os.name=="nt" else "check")
            c.write_text(HARNESS+helper+MAIN,encoding="utf-8")
            subprocess.run(compiler+["-std=c11","-O2","-Wall","-Wextra",str(c),"-o",str(exe)],check=True,timeout=60)
            result=subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=20)
            self.assertIn("B3A314_ECM_HELPER_PASS",result.stdout)

    def test_wiring(self):
        source=SOURCE.read_text(encoding="utf-8")
        self.assertIn('GetPrivateProfileStringA("B3A314_EcmExtendedLiveLab","Enabled","0"',source)
        self.assertIn("g_b3a314_ecm_live_lab=(str_len(v)==1u && v[0]=='1')?1u:0u;",source)
        self.assertIn("sz=answer_b3a314_ecm_live_lab(c,ecu,id,msg->TxFlags,payload,n,answer);\n            if(!sz)sz=answer_b3a309_ecm_live_lab(c,ecu,id,msg->TxFlags,payload,n,answer);",source)
        self.assertIn("g_ecu[i].did_code[slot]<0xF100u||g_ecu[i].did_code[slot]>0xF1FFu",source)
