#include "p2_vehicle_core.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned passed = 0;
#define GROUP() (++passed)
int main(void) {
  p2_vehicle v;
  p2_vehicle_config cfg = p2_vehicle_xc90_v8_my2009_config();
  p2_vehicle_tx_assessment t;
  p2_ls_observation rx;
  const uint8_t a3[8] = {0xCF,0x50,0xA3,0x02,0x03,0xA5,0xA5,0};
  const uint8_t f0[8] = {0xCB,0x50,0xB9,0xF0,0,0,0,0};
  const uint8_t fb[8] = {0xCB,0x50,0xB9,0xFB,0,0,0,0};
  const uint8_t ref[8]= {0xCF,0x50,0xA6,0x1A,0x04,0x01,0,0};
  uint8_t cem[8] = {0,0,0,0,0,0,0xC0,0};
  uint8_t j2534[12] = {0,0x0F,0xFF,0xFE,0xCF,0x50,0xA3,0x02,0x03,0xA5,0xA5,0};

  /* 1. Default target profile with no unverified broadcast assumptions. */
  p2_vehicle_init(&v, NULL);
  assert(v.cfg.hs_bitrate==500000u && v.cfg.ls_bitrate==125000u);
  assert(!v.cfg.enable_community_ls_signals && v.cfg.observed_cem_ls_can_id==0);
  assert(!v.passive_key.valid && v.diagnostic_ignition==P2_DIAG_IGNITION_UNKNOWN); GROUP();

  /* 2. A3 request recognized; status is evidence-only; never invent RX. */
  t=p2_vehicle_observe_tx(&v,P2_BUS_HS,500000,0x000FFFFE,a3,8);
  assert(t.classified.request==P2_CEM_A3_SHAPE && t.generated_reply_count==0);
  assert(t.must_forward_unchanged && v.a3_shape_seen==1); GROUP();

  /* 3. F0 remains evidence-needed, B9FB remains delegated to existing driver. */
  t=p2_vehicle_observe_tx(&v,P2_BUS_HS,500000,0x000FFFFE,f0,8);
  assert(t.classified.request==P2_CEM_B9F0 && t.classified.decision==P2_CEM_NEED_EVIDENCE);
  t=p2_vehicle_observe_tx(&v,P2_BUS_HS,500000,0x000FFFFE,fb,8);
  assert(t.classified.request==P2_CEM_B9FB && t.classified.decision==P2_CEM_KEEP_EXISTING);
  assert(v.b9f0_seen==1 && v.b9fb_seen==1 && t.generated_reply_count==0); GROUP();

  /* 4. Ref6660 and E3 sightings cannot turn unknown ignition into confirmed ON. */
  t=p2_vehicle_observe_tx(&v,P2_BUS_HS,500000,0x000FFFFE,ref,8);
  { const uint8_t e3[]={0xE3,0x02,0x01}; p2_vehicle_note_d2_candidate_rx(&v,e3,sizeof(e3)); }
  assert(v.possible_ref6660_seen==1 && v.diag_e3_02_candidates==1);
  assert(v.diagnostic_ignition==P2_DIAG_IGNITION_UNKNOWN); GROUP();

  /* 5. Misrouted request only annotated, never blocks or modifies an actual TX. */
  t=p2_vehicle_observe_tx(&v,P2_BUS_LS,125000,0x000FFFFE,a3,8);
  assert(t.classified.decision==P2_CEM_ROUTE_MISMATCH && t.must_forward_unchanged);
  assert(v.diag_wrong_bus_annotations==1); GROUP();

  /* 6. Passive LS key decode is opt-in and the observed 29-bit ID is configurable. */
  assert(!p2_vehicle_observe_rx(&v,P2_BUS_LS,125000,true,0x00617FF8,cem,8,100,&rx));
  cfg.enable_community_ls_signals=true;
  cfg.observed_cem_ls_can_id=0x01234567u; /* synthetic configured ID */
  p2_vehicle_init(&v,&cfg);
  assert(!p2_vehicle_observe_rx(&v,P2_BUS_LS,125000,true,0x00617FF8,cem,8,100,&rx));
  assert(p2_vehicle_observe_rx(&v,P2_BUS_LS,125000,true,0x01234567,cem,8,101,&rx));
  assert(rx.kind==P2_LS_CEM_IGNITION && rx.can_id==0x01234567u);
  assert(v.passive_key.valid && v.passive_key.key_present && v.passive_key.key_position==2);
  assert(v.diagnostic_ignition==P2_DIAG_IGNITION_UNKNOWN); GROUP();

  /* 7. Wrong bus/DLC, stale timestamps never contaminate state. */
  cem[6] = 0;
  assert(!p2_vehicle_observe_rx(&v,P2_BUS_HS,500000,true,0x01234567,cem,8,105,&rx));
  assert(!p2_vehicle_observe_rx(&v,P2_BUS_LS,125000,false,0x01234567,cem,8,105,&rx));
  assert(!p2_vehicle_observe_rx(&v,P2_BUS_LS,125000,true,0x01234567,cem,7,105,&rx));
  assert(!p2_vehicle_observe_rx(&v,P2_BUS_LS,125000,true,0x01234567,cem,8,99,&rx));
  assert(v.passive_key.key_position==2 && v.stale_ignition_frames==1);
  assert(p2_vehicle_observe_rx(&v,P2_BUS_LS,125000,true,0x01234567,cem,8,110,&rx));
  assert(!v.passive_key.key_present && v.passive_key.key_position==0); GROUP();

  /* 8. PassThru framing, four-byte CAN ID, protocol/length checks. */
  assert(p2_vehicle_observe_passthru_tx(&v,5,500000,true,j2534,sizeof(j2534),&t));
  assert(t.classified.request==P2_CEM_A3_SHAPE && t.generated_reply_count==0);
  assert(!p2_vehicle_observe_passthru_tx(&v,32772,500000,true,j2534,sizeof(j2534),&t));
  assert(!p2_vehicle_observe_passthru_tx(&v,5,500000,true,j2534,3,&t));
  assert(!p2_vehicle_observe_passthru_tx(&v,5,500000,false,j2534,sizeof(j2534),&t));
  assert(!p2_vehicle_observe_passthru_tx(&v,5,250000,true,j2534,sizeof(j2534),&t)); GROUP();

  printf("dev25: %u/8 integration groups OK; diag ignition remains UNKNOWN\n",passed);
  return passed == 8 ? 0 : 1;
}
