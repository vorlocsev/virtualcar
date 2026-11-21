"""Read-only D2 A6 metadata classification; no DID values or positive ECU response."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "src" / "p2core"

C_SOURCE = r'''
#include "p2_vehicle_core.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define CHECK(test) do { \
    if (!(test)) { fprintf(stderr, "FAIL at check %d line %d\n", n+1, __LINE__); return 1; } \
    ++n; \
} while (0)

int main(void) {
    int n=0;
    const uint32_t can_id=P2_CEM_D2_TX_CAN_ID;
    uint8_t known[8]={0xCD,0x50,0xA6,0x1A,0x04,0x01,0,0};
    uint8_t other[8]={0xCD,0x50,0xA6,0x24,0x42,0x01,0,0};
    uint8_t b9fb[8]={0xCB,0x50,0xB9,0xFB,0,0,0,0};
    uint8_t b9f0[8]={0xCB,0x50,0xB9,0xF0,0,0,0,0};
    uint8_t a3[8]={0xCF,0x50,0xA3,0x02,0x03,0xA5,0xA5,0};
    p2_cem_result r;
    p2_vehicle v;
    p2_vehicle_tx_assessment a;
    p2_vehicle_init(&v,0);

    r=p2_cem_classify(can_id,500000u,known,8u);
    CHECK(r.request==P2_CEM_A6_REF6660_CANDIDATE && r.decision==P2_CEM_NEED_EVIDENCE);
    r=p2_cem_classify(can_id,500000u,other,8u);
    CHECK(r.request==P2_CEM_A6_OTHER_DID_UNVERIFIED && r.decision==P2_CEM_NEED_EVIDENCE);
    CHECK(strcmp(p2_cem_request_name(r.request),"a6_other_did_unverified")==0);
    /* Keep DID values out of J2534 classification labels. */
    CHECK(strstr(p2_cem_request_name(r.request),"2442")==0);
    other[1]=0x40;
    r=p2_cem_classify(can_id,125000u,other,8u);
    CHECK(r.request==P2_CEM_A6_OTHER_DID_UNVERIFIED && r.is_expected_bus);
    r=p2_cem_classify(can_id,500000u,other,8u);
    CHECK(r.request==P2_CEM_A6_OTHER_DID_UNVERIFIED && r.decision==P2_CEM_ROUTE_MISMATCH);
    other[1]=0x50;
    other[5]=0x02;
    r=p2_cem_classify(can_id,500000u,other,8u);
    CHECK(r.request==P2_CEM_UNKNOWN);
    other[5]=0x01;
    other[0]=0xCF;
    r=p2_cem_classify(can_id,500000u,other,8u);
    CHECK(r.request==P2_CEM_UNKNOWN);
    other[0]=0xCD;
    r=p2_cem_classify(can_id,500000u,other,7u);
    CHECK(r.request==P2_CEM_UNKNOWN);
    r=p2_cem_classify(0x000FFFFDu,500000u,other,8u);
    CHECK(r.request==P2_CEM_NOT_D2);
    r=p2_cem_classify(can_id,500000u,b9fb,8u);
    CHECK(r.request==P2_CEM_B9FB && r.decision==P2_CEM_KEEP_EXISTING);
    r=p2_cem_classify(can_id,500000u,b9f0,8u);
    CHECK(r.request==P2_CEM_B9F0 && r.decision==P2_CEM_NEED_EVIDENCE);
    r=p2_cem_classify(can_id,500000u,a3,8u);
    CHECK(r.request==P2_CEM_A3_SHAPE && r.decision==P2_CEM_NEED_EVIDENCE);
    a=p2_vehicle_observe_tx(&v,P2_BUS_HS,500000u,can_id,other,8u);
    CHECK(a.classified.request==P2_CEM_A6_OTHER_DID_UNVERIFIED &&
          a.must_forward_unchanged && a.generated_reply_count==0u);
    CHECK(v.a6_other_did_seen==1u && v.possible_ref6660_seen==0u);
    a=p2_vehicle_observe_tx(&v,P2_BUS_HS,500000u,can_id,known,8u);
    CHECK(v.possible_ref6660_seen==1u && v.a6_other_did_seen==1u &&
          a.generated_reply_count==0u);
    printf("PASS %d/16 read-only A6 metadata assertions\n",n);
    return n==16 ? 0 : 1;
}
'''


class D2OtherA6MetadataTests(unittest.TestCase):
    def test_01_native_c_classifier_and_vehicle_counters(self):
        compiler = shutil.which("gcc") or shutil.which("clang") or shutil.which("cc")
        if not compiler:
            self.skipTest("C compiler unavailable")
        with tempfile.TemporaryDirectory(prefix="virtualcar-d2-a6-") as tmp:
            directory = Path(tmp)
            harness = directory / "d2_a6_metadata_test.c"
            program = directory / "d2_a6_metadata_test"
            harness.write_text(C_SOURCE, encoding="utf-8")
            subprocess.run([
                compiler, "-std=c11", "-Wall", "-Wextra", "-O0",
                "-I", str(CORE), str(harness),
                str(CORE / "p2_cem_router.c"),
                str(CORE / "p2_vehicle_core.c"),
                str(CORE / "p2_ls_observer.c"),
                "-o", str(program),
            ], check=True, capture_output=True, text=True, timeout=35)
            result = subprocess.run([str(program)], check=True, capture_output=True,
                                    text=True, timeout=20)
            self.assertIn("PASS 16/16", result.stdout)


if __name__ == "__main__":
    unittest.main()
