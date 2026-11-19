/* B3A316: synthetic positive-header candidates only, NOT genuine ECU RX. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../src/p2core/p2_cem_router.h"

int main(void){
    p2_hw_tx_trace tx={0};
    static const uint8_t req50[8]={0xCF,0x50,0xA3,0x02,0x03,0xA5,0xA5,0x00};
    static const uint8_t rx50[8]={0xCB,0x50,0xE3,0x02,0,0,0,0};
    static const uint8_t vin50[8]={0xCB,0x50,0xF9,0xFB,0,0,0,0};
    uint8_t altered[8];
    p2_hw_rx_event result;

    /* 1: a header without active A3 TX is never session evidence. */
    assert(p2_hw_inspect_e3_rx_candidate(&tx,500000,0x01200003,rx50,8)==P2_HW_RX_ORPHAN_E3_CANDIDATE);
    /* 2: correct A3 TX and legacy ID yield ONLY an unverified candidate. */
    assert(p2_hw_observe_tx(&tx,P2_CEM_D2_TX_CAN_ID,500000,req50,8)==P2_HW_A3_TX);
    result=p2_hw_inspect_e3_rx_candidate(&tx,500000,0x01200003,rx50,8);
    assert(result==P2_HW_RX_LEGACY_ID_CANDIDATE_UNVERIFIED);
    /* 3: RX must not advance or authenticate TX-phase state. */
    assert(tx.last_request==1 && tx.last_target==0x50);
    assert(tx.a3_tx==1 && tx.e0_tx==0 && tx.f0_tx==0);
    /* 4: other D2 services, including VIN, cannot satisfy this candidate. */
    assert(p2_hw_inspect_e3_rx_candidate(&tx,500000,0x01200003,vin50,8)==P2_HW_RX_UNRELATED);
    /* 5: route mismatch (only one CEM target on this channel). */
    memcpy(altered,rx50,8);altered[1]=0x40;
    assert(p2_hw_inspect_e3_rx_candidate(&tx,500000,0x01200003,altered,8)==P2_HW_RX_ROUTE_MISMATCH_CANDIDATE);
    /* 6: wrong subcommand cannot match A3 02. */
    memcpy(altered,rx50,8);altered[3]=0x03;
    assert(p2_hw_inspect_e3_rx_candidate(&tx,500000,0x01200003,altered,8)==P2_HW_RX_SUBCOMMAND_MISMATCH_CANDIDATE);
    /* 7: bus mismatch is a candidate error and never a positive result. */
    assert(p2_hw_inspect_e3_rx_candidate(&tx,125000,0x01200003,rx50,8)==P2_HW_RX_WRONG_BUS_CANDIDATE);
    /* 8: response CAN ID from the earlier donor is not an OEM invariant. */
    assert(p2_hw_inspect_e3_rx_candidate(&tx,500000,0x01200005,rx50,8)==P2_HW_RX_OTHER_ID_CANDIDATE);
    /* 9: invalid DLC and frame marker rejected. */
    assert(p2_hw_inspect_e3_rx_candidate(&tx,500000,0x01200003,rx50,7)==P2_HW_RX_INVALID_FRAME_CANDIDATE);
    memcpy(altered,rx50,8);altered[0]=0x0B;
    assert(p2_hw_inspect_e3_rx_candidate(&tx,500000,0x01200003,altered,8)==P2_HW_RX_INVALID_FRAME_CANDIDATE);
    /* 10: different route 0x40 uses separate legacy CAN ID assumption. */
    { p2_hw_tx_trace other={0};
      static const uint8_t req40[8]={0xCF,0x40,0xA3,0x02,0x03,0xA5,0xA5,0};
      static const uint8_t rx40[8]={0xCB,0x40,0xE3,0x02,0,0,0,0};
      assert(p2_hw_observe_tx(&other,P2_CEM_D2_TX_CAN_ID,125000,req40,8)==P2_HW_A3_TX);
      assert(p2_hw_inspect_e3_rx_candidate(&other,125000,0x00800003,rx40,8)==P2_HW_RX_LEGACY_ID_CANDIDATE_UNVERIFIED);
      assert(p2_hw_inspect_e3_rx_candidate(&other,125000,0x01200003,rx40,8)==P2_HW_RX_OTHER_ID_CANDIDATE);
    }
    /* 11: neither unsupported inputs nor null buffer promote acceptance. */
    assert(p2_hw_inspect_e3_rx_candidate(0,500000,0x01200003,rx50,8)==P2_HW_RX_ORPHAN_E3_CANDIDATE);
    assert(p2_hw_inspect_e3_rx_candidate(&tx,500000,0x01200003,0,8)==P2_HW_RX_UNRELATED);
    /* 12: labels fixed, metadata-only, and preserve provenance warning. */
    assert(strcmp(p2_hw_rx_event_name(P2_HW_RX_LEGACY_ID_CANDIDATE_UNVERIFIED),
                  "P2_HW_RX_LEGACY_ID_CANDIDATE_UNVERIFIED")==0);
    assert(strcmp(p2_hw_rx_event_name(P2_HW_RX_UNRELATED),"P2_HW_RX_UNRELATED")==0);
    puts("PASS 12/12 B3A316 synthetic RX candidate classification groups");
    return 0;
}
