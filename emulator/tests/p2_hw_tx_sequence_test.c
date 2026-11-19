/* B3A313: pure-C, no J2534, no ECU, no positive responses. */
#include <assert.h>
#include <stdio.h>
#include "../src/p2core/p2_cem_router.h"
int main(void) {
  static const uint8_t a3_50[8]={0xCF,0x50,0xA3,0x02,0x03,0xA5,0xA5,0};
  static const uint8_t e0_50[8]={0xCB,0x50,0xB9,0xE0,0,0,0,0};
  static const uint8_t f0_50[8]={0xCB,0x50,0xB9,0xF0,0,0,0,0};
  uint8_t bad[8], a3_40[8], e0_40[8], f0_40[8];
  p2_hw_tx_trace t={0};
  /* 1. A3 request seen; definitely not an ECU acknowledgement. */
  assert(p2_hw_observe_tx(&t,P2_CEM_D2_TX_CAN_ID,500000,a3_50,8)==P2_HW_A3_TX);
  assert(t.last_request==1 && t.a3_tx==1);
  /* 2. Complete TX order remains marked UNVERIFIED without authentic RX. */
  assert(p2_hw_observe_tx(&t,P2_CEM_D2_TX_CAN_ID,500000,e0_50,8)==P2_HW_E0_TX_AFTER_A3_TX_UNVERIFIED);
  assert(p2_hw_observe_tx(&t,P2_CEM_D2_TX_CAN_ID,500000,f0_50,8)==P2_HW_F0_TX_AFTER_E0_TX_UNVERIFIED);
  /* 3. Hardware number without preceding TX cannot invent session state. */
  t=(p2_hw_tx_trace){0};
  assert(p2_hw_observe_tx(&t,P2_CEM_D2_TX_CAN_ID,500000,f0_50,8)==P2_HW_OUT_OF_ORDER);
  assert(t.last_request==0 && t.out_of_order==1);
  /* 4. Cross-target request cannot inherit the other CEM route. */
  a3_40[0]=0xCF; a3_40[1]=0x40;
  e0_40[0]=0xCB; e0_40[1]=0x40;
  f0_40[0]=0xCB; f0_40[1]=0x40;
  for(int i=2;i<8;i++){a3_40[i]=a3_50[i];e0_40[i]=e0_50[i];f0_40[i]=f0_50[i];}
  t=(p2_hw_tx_trace){0};
  assert(p2_hw_observe_tx(&t,P2_CEM_D2_TX_CAN_ID,500000,a3_50,8)==P2_HW_A3_TX);
  assert(p2_hw_observe_tx(&t,P2_CEM_D2_TX_CAN_ID,125000,e0_40,8)==P2_HW_OUT_OF_ORDER);
  assert(t.last_request==1 && t.last_target==0x50);
  /* 5. Alternate 0x40 / 125 kbit/s route works as TX-only observation. */
  t=(p2_hw_tx_trace){0};
  assert(p2_hw_observe_tx(&t,P2_CEM_D2_TX_CAN_ID,125000,a3_40,8)==P2_HW_A3_TX);
  assert(p2_hw_observe_tx(&t,P2_CEM_D2_TX_CAN_ID,125000,e0_40,8)==P2_HW_E0_TX_AFTER_A3_TX_UNVERIFIED);
  assert(p2_hw_observe_tx(&t,P2_CEM_D2_TX_CAN_ID,125000,f0_40,8)==P2_HW_F0_TX_AFTER_E0_TX_UNVERIFIED);
  /* 6. Wrong baud never advances stage. */
  t=(p2_hw_tx_trace){0};
  assert(p2_hw_observe_tx(&t,P2_CEM_D2_TX_CAN_ID,125000,a3_50,8)==P2_HW_WRONG_BUS);
  assert(t.a3_tx==0 && t.wrong_bus==1);
  /* 7. Payload data and length are exact. */
  for(int i=0;i<8;i++)bad[i]=a3_50[i];
  bad[6]=0;
  assert(p2_hw_observe_tx(&t,P2_CEM_D2_TX_CAN_ID,500000,bad,8)==P2_HW_INVALID_SHAPE);
  assert(p2_hw_observe_tx(&t,P2_CEM_D2_TX_CAN_ID,500000,a3_50,7)==P2_HW_INVALID_SHAPE);
  assert(t.last_request==0 && t.invalid_shapes==2);
  /* 8. Existing B9FB path, unrelated CAN ID and null request unaffected. */
  static const uint8_t fb[8]={0xCB,0x50,0xB9,0xFB,0,0,0,0};
  assert(p2_hw_observe_tx(&t,P2_CEM_D2_TX_CAN_ID,500000,fb,8)==P2_HW_UNRELATED);
  assert(p2_hw_observe_tx(&t,0x7E0u,500000,a3_50,8)==P2_HW_UNRELATED);
  assert(p2_hw_observe_tx(&t,P2_CEM_D2_TX_CAN_ID,500000,NULL,8)==P2_HW_UNRELATED);
  assert(t.last_request==0 && t.a3_tx==0);
  puts("PASS 8/8 read-only Hardware TX observation groups");
  return 0;
}
