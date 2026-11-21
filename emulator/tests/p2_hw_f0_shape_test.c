/* B3A315: 10 source-bound shape groups; no ECU or J2534 RX generated. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../src/p2core/p2_cem_router.h"

int main(void) {
  uint8_t p[15]={0x31,0x33,0x30,0x35,0x00,0x20,0x41,0x31};
  uint8_t saved[15];

  /* 1: valid 15-byte structural candidate is not OEM verified. */
  assert(p2_cem_inspect_sectorv_f0_body(p,15)==P2_CEM_F0_STRUCTURAL_CANDIDATE);
  assert(p2_cem_validate_sectorv_f0_body(p,15)==1);
  /* 2: missing buffer. */
  assert(p2_cem_inspect_sectorv_f0_body(0,15)==P2_CEM_F0_NO_BODY);
  assert(p2_cem_validate_sectorv_f0_body(0,15)==0);
  /* 3: raw single CAN frame must not be treated as assembled response. */
  assert(p2_cem_inspect_sectorv_f0_body(p,8)==P2_CEM_F0_INVALID_LENGTH);
  /* 4: oversized responses must not be silently truncated. */
  assert(p2_cem_inspect_sectorv_f0_body(p,16)==P2_CEM_F0_INVALID_LENGTH);
  /* 5: invalid high BCD nibble. */
  p[1]=0xA1;
  assert(p2_cem_inspect_sectorv_f0_body(p,15)==P2_CEM_F0_INVALID_BCD);
  p[1]=0x33;
  /* 6: invalid low BCD nibble. */
  p[2]=0x1F;
  assert(p2_cem_inspect_sectorv_f0_body(p,15)==P2_CEM_F0_INVALID_BCD);
  p[2]=0x30;
  /* 7: lower bound of revision character set. */
  p[6]=0x1F;
  assert(p2_cem_inspect_sectorv_f0_body(p,15)==P2_CEM_F0_INVALID_REVISION);
  p[6]=0x20;
  /* 8: upper bound of revision character set. */
  p[7]=0x7F;
  assert(p2_cem_inspect_sectorv_f0_body(p,15)==P2_CEM_F0_INVALID_REVISION);
  p[7]=0x7E;
  /* 9: absent revision marker, exact observed client branch. */
  p[5]=0x00;p[6]=0;p[7]=0xFF;
  assert(p2_cem_inspect_sectorv_f0_body(p,15)==P2_CEM_F0_STRUCTURAL_CANDIDATE);
  /* 10: nonmutating helper and labels never echo CEM identity bytes. */
  memcpy(saved,p,sizeof(p));
  assert(p2_cem_inspect_sectorv_f0_body(p,15)==P2_CEM_F0_STRUCTURAL_CANDIDATE);
  assert(memcmp(saved,p,sizeof(p))==0);
  assert(strcmp(p2_cem_f0_shape_name(P2_CEM_F0_STRUCTURAL_CANDIDATE),
                "structural_candidate_unverified")==0);
  assert(strcmp(p2_cem_f0_shape_name(P2_CEM_F0_INVALID_BCD),"invalid_bcd")==0);
  puts("PASS 10/10 B3A315 F0 structural classification groups");
  return 0;
}
