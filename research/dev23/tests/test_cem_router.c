#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "p2_cem_router.h"
static unsigned groups=0;
#define GROUP do { ++groups; }while(0)
int main(void) {
  const uint8_t a3_hs[8]={0xCF,0x50,0xA3,0x02,0x03,0xA5,0xA5,0x00};
  const uint8_t a3_ls[8]={0xCF,0x40,0xA3,0x02,0x03,0xA5,0xA5,0x00};
  const uint8_t f0[8]={0xCB,0x50,0xB9,0xF0,0,0,0,0};
  const uint8_t e0[8]={0xCB,0x50,0xB9,0xE0,0,0,0,0};
  const uint8_t fb[8]={0xCB,0x50,0xB9,0xFB,0,0,0,0};
  const uint8_t ref[8]={0xCF,0x50,0xA6,0x1A,0x04,0x01,0,0};
  uint8_t a[8]={0x80,0,0,0,0,0x12,0x34,0x56};
  uint8_t b[8]={0x00,0x78,0,0,0,0,0,0};
  uint8_t body[15]={0x01,0x23,0x45,0x67,0x89,0x20,'A','A'};
  uint32_t pn=0;
  p2_cem_result r;
  r=p2_cem_classify(P2_CEM_D2_TX_CAN_ID,500000,a3_hs,8);
  assert(r.request==P2_CEM_A3_SHAPE&&r.decision==P2_CEM_NEED_EVIDENCE&&r.matched_full_shape);GROUP;
  r=p2_cem_classify(P2_CEM_D2_TX_CAN_ID,125000,a3_ls,8);
  assert(r.request==P2_CEM_A3_SHAPE&&r.is_expected_bus);GROUP;
  r=p2_cem_classify(P2_CEM_D2_TX_CAN_ID,500000,f0,8);
  assert(r.request==P2_CEM_B9F0&&r.decision==P2_CEM_NEED_EVIDENCE);GROUP;
  r=p2_cem_classify(P2_CEM_D2_TX_CAN_ID,500000,e0,8);
  assert(r.request==P2_CEM_B9E0&&r.decision==P2_CEM_NEED_EVIDENCE);GROUP;
  r=p2_cem_classify(P2_CEM_D2_TX_CAN_ID,500000,fb,8);
  assert(r.request==P2_CEM_B9FB&&r.decision==P2_CEM_KEEP_EXISTING);GROUP;
  r=p2_cem_classify(0x123,500000,fb,8);
  assert(r.request==P2_CEM_NOT_D2);GROUP;
  r=p2_cem_classify(P2_CEM_D2_TX_CAN_ID,125000,a3_hs,8);
  assert(r.request==P2_CEM_A3_SHAPE&&r.decision==P2_CEM_ROUTE_MISMATCH);GROUP;
  r=p2_cem_classify(P2_CEM_D2_TX_CAN_ID,500000,ref,8);
  assert(r.request==P2_CEM_A6_REF6660_CANDIDATE&&r.decision==P2_CEM_NEED_EVIDENCE);GROUP;
  assert(p2_cem_decode_legacy_b9f0_pn(a,b,&pn)&&pn==12345678u);
  b[1]=0xAF;assert(!p2_cem_decode_legacy_b9f0_pn(a,b,&pn));GROUP;
  assert(p2_cem_validate_sectorv_f0_body(body,15));
  body[0]=0xFA;assert(!p2_cem_validate_sectorv_f0_body(body,15));
  body[0]=0x01;assert(!p2_cem_validate_sectorv_f0_body(body,14));GROUP;
  { uint8_t e3[3]={0xE3,0x02,0x01};assert(p2_cem_e3_02_candidate(e3,3));
    assert(!p2_cem_e3_02_candidate(e3,1)); }GROUP;
  { uint8_t bad[8]={0xCF,0x60,0xA3,0x02,0x03,0xA5,0xA5,0};
    r=p2_cem_classify(P2_CEM_D2_TX_CAN_ID,500000,bad,8);
    assert(r.request==P2_CEM_UNKNOWN&&!r.is_valid_cem_route); }GROUP;
  printf("dev23: %u/12 independent test groups passed\n",groups);
  return groups==12?0:1;
}
