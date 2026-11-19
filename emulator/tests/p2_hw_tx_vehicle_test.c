/* Verify TX evidence is wired into the vehicle observer, with no new RX. */
#include <assert.h>
#include <stdio.h>
#include "../src/p2core/p2_vehicle_core.h"
int main(void) {
  p2_vehicle car;
  static const uint8_t a3[8]={0xCF,0x50,0xA3,0x02,0x03,0xA5,0xA5,0};
  static const uint8_t e0[8]={0xCB,0x50,0xB9,0xE0,0,0,0,0};
  static const uint8_t f0[8]={0xCB,0x50,0xB9,0xF0,0,0,0,0};
  static const uint8_t fb[8]={0xCB,0x50,0xB9,0xFB,0,0,0,0};
  p2_vehicle_tx_assessment out;
  p2_vehicle_init(&car,0);
  out=p2_vehicle_observe_tx(&car,P2_BUS_HS,500000,P2_CEM_D2_TX_CAN_ID,a3,8);
  assert(out.must_forward_unchanged && out.generated_reply_count==0);
  assert(car.a3_shape_seen==1 && car.hw_tx.last_request==1 && car.hw_tx.a3_tx==1);
  out=p2_vehicle_observe_tx(&car,P2_BUS_HS,500000,P2_CEM_D2_TX_CAN_ID,e0,8);
  assert(out.must_forward_unchanged && out.generated_reply_count==0);
  out=p2_vehicle_observe_tx(&car,P2_BUS_HS,500000,P2_CEM_D2_TX_CAN_ID,f0,8);
  assert(out.must_forward_unchanged && out.generated_reply_count==0);
  assert(car.hw_tx.last_request==3 && car.hw_tx.e0_tx==1 && car.hw_tx.f0_tx==1);
  /* The B9FB classifier remains present and this feature emits no reply. */
  out=p2_vehicle_observe_tx(&car,P2_BUS_HS,500000,P2_CEM_D2_TX_CAN_ID,fb,8);
  assert(out.classified.request==P2_CEM_B9FB);
  assert(out.must_forward_unchanged && out.generated_reply_count==0);
  assert(car.hw_tx.last_request==3 && car.b9fb_seen==1);
  assert(car.diagnostic_ignition==P2_DIAG_IGNITION_UNKNOWN);
  puts("PASS: p2_vehicle Hardware TX metadata integration; no replies generated");
  return 0;
}
