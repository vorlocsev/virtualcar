#!/usr/bin/env python3
"""B3A19 isolated native C classifier tests. No synthetic ECU RX."""
from __future__ import annotations
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HEADER = ROOT / "src/p2core/vida_uds29_route.h"
SOURCE = ROOT / "src/virtualcar.c"

C_HARNESS = r"""
typedef unsigned int U32;
typedef unsigned char U8;
#define PROTO_ISO15765 6u
#define PROTO_CAN 5u
#include "vida_uds29_route.h"
static int probe(U32 id,U32 proto,const U8 *payload,U32 len,int yes,
                 U32 target,U32 sid,U32 operand) {
    VIDA_UDS29_REQUEST out={0xABu,0xCDu,0xEFu,0x1234u};
    int got=vida_uds29_request_probe(id,proto,payload,len,&out);
    if(got!=yes)return 1;
    if(!got)return out.request_id!=0xABu || out.target!=0xCDu ||
                    out.sid!=0xEFu || out.operand!=0x1234u;
    return out.request_id!=id || out.target!=target ||
           out.sid!=sid || out.operand!=operand;
}
int main(void) {
    const U8 did[]={0x22,0xF1,0x10};
    const U8 dtc[]={0x19,0x02,0xFF};
    const U8 protected[]={0x2E,0xF1,0x10};
    U32 ids[]={0x18DA10F1u,0x18DA18F1u,0x18DA1AF1u,0x18DA50F1u,
               0x18DA01F1u,0x18DA32F1u,0x18DA76F1u};
    U32 targets[]={0x10u,0x18u,0x1Au,0x50u,0x01u,0x32u,0x76u};
    unsigned int i;
    for(i=0;i<7;i++)
        if(probe(ids[i],6,did,3,1,targets[i],0x22u,0xF110u))return 10+i;
    if(probe(ids[0],6,dtc,3,1,0x10,0x19,0x02FF))return 20;
    if(probe(0x726u,6,did,3,0,0,0,0))return 21;
    if(probe(0x18DAF110u,6,did,3,0,0,0,0))return 22;
    if(probe(ids[0],5,did,3,0,0,0,0))return 23;
    if(probe(ids[0],6,did,2,0,0,0,0))return 24;
    if(probe(ids[0],6,protected,3,0,0,0,0))return 25;
    if(probe(ids[0],6,0,3,0,0,0,0))return 26;
    if(vida_uds29_request_probe(ids[0],6,did,3,0))return 27;
    return 0;
}
"""

class RouteObservationB3A19(unittest.TestCase):
    def test_header_exact_address_and_sid_gate(self):
        src=HEADER.read_text(encoding="utf-8")
        self.assertIn("0x18DA00F1u",src)
        self.assertIn("0xFFFF00FFu",src)
        self.assertIn("payload_len != 3u",src)
        self.assertIn("0x22u",src)
        self.assertIn("0x19u",src)

    def test_header_no_implementation_or_private_identity(self):
        src=HEADER.read_text(encoding="utf-8")
        for forbidden in ("emit_response(", "answer_uds(", "enqueue(", "YV1CR", "511566"):
            self.assertNotIn(forbidden,src)

    def test_source_hook_after_ecu_and_cem_special_case(self):
        src=SOURCE.read_text(encoding="utf-8")
        start=src.index("static void process_request(")
        body=src[start:src.index("static void begin_tx_evidence(",start)]
        self.assertIn('#include "p2core/vida_uds29_route.h"',src)
        self.assertLess(body.index("for(i=0;i<g_ecu_count;i++){"),body.index("vida_uds29_request_probe("))
        self.assertLess(body.index("P3 CEM F114 probe: no configured CEM fixture; no response"),body.index("vida_uds29_request_probe("))
        self.assertIn('"missing_profile","no_response"',body)
        self.assertIn("VIDA UDS29 unconfigured route",body)

    def test_c99_compiled_classifier(self):
        compiler=shutil.which("gcc") or shutil.which("clang")
        if not compiler:self.skipTest("no local native C compiler")
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)
            (p/"test.c").write_text(C_HARNESS,encoding="utf-8")
            subprocess.run([compiler,"-std=c99","-Wall","-Wextra","-Werror",
                            "-I",str(HEADER.parent),str(p/"test.c"),"-o",str(p/"test")],
                           check=True,capture_output=True,text=True)
            subprocess.run([str(p/"test")],check=True,capture_output=True,text=True)

if __name__=="__main__":
    unittest.main()
