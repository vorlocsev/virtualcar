/* Read-only Hardware chronology must be channel-scoped, never ECU ACK. */
#include <assert.h>
#include <stdio.h>
#include "../src/p2core/p2_j2534_bridge.h"
int main(void) {
  p2_j2534_bridge b;
  p2_bridge_tx_result out;
  static const uint8_t a3[12]={0x00,0x0F,0xFF,0xFE,0xCF,0x50,0xA3,0x02,0x03,0xA5,0xA5,0};
  static const uint8_t e0[12]={0x00,0x0F,0xFF,0xFE,0xCB,0x50,0xB9,0xE0,0,0,0,0};
  static const uint8_t f0[12]={0x00,0x0F,0xFF,0xFE,0xCB,0x50,0xB9,0xF0,0,0,0,0};
  static const uint8_t fb[12]={0x00,0x0F,0xFF,0xFE,0xCB,0x50,0xB9,0xFB,0,0,0,0};
  p2_bridge_init(&b);
  p2_bridge_connect(&b,1u,5u,500000u);
  p2_bridge_connect(&b,2u,5u,500000u);
  assert(p2_bridge_inspect_tx(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,a3,12u,&out));
  assert(out.observed && b.channels[0].hw_tx.last_request==1u);
  assert(b.channels[1].hw_tx.last_request==0u);
  /* A different channel must NOT inherit A3 from channel 1. */
  assert(p2_bridge_inspect_tx(&b,2u,P2_BRIDGE_CAN_29BIT_FLAG,f0,12u,&out));
  assert(b.channels[1].hw_tx.out_of_order==1u);
  assert(b.channels[1].hw_tx.last_request==0u);
  /* Correct TX order on channel 1 is still NOT authentication. */
  assert(p2_bridge_inspect_tx(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,e0,12u,&out));
  assert(p2_bridge_inspect_tx(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,f0,12u,&out));
  assert(b.channels[0].hw_tx.last_request==3u);
  assert(b.channels[0].hw_tx.a3_tx==1u && b.channels[0].hw_tx.e0_tx==1u);
  /* B9FB classification/replay path is unchanged by the observer. */
  assert(p2_bridge_inspect_tx(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,fb,12u,&out));
  assert(out.observed && out.decision==P2_CEM_KEEP_EXISTING);
  assert(b.vehicle.b9fb_seen==1u && b.channels[0].hw_tx.last_request==3u);
  /* Disconnect and reuse of numeric channel ID reset all phase evidence. */
  p2_bridge_disconnect(&b,1u);
  p2_bridge_connect(&b,1u,5u,500000u);
  assert(b.channels[0].hw_tx.last_request==0u && b.channels[0].hw_tx.a3_tx==0u);
  assert(p2_bridge_inspect_tx(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,f0,12u,&out));
  assert(b.channels[0].hw_tx.out_of_order==1u);
  /* ISO15765 channel cannot be mistaken for raw CAN Hardware chronology. */
  p2_bridge_connect(&b,3u,6u,500000u);
  assert(p2_bridge_inspect_tx(&b,3u,P2_BRIDGE_CAN_29BIT_FLAG,a3,12u,&out));
  assert(b.channels[2].hw_tx.a3_tx==0u);
  assert(b.vehicle.diagnostic_ignition==P2_DIAG_IGNITION_UNKNOWN);
  assert(b.inspected_rx==0u);
  puts("PASS: per-channel TX Hardware observation, reset, ISO guard and B9FB");
  return 0;
}
