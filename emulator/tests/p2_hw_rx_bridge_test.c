/* Read-only J2534 bridge candidate audit; all data are synthetic lab bytes. */
#include <assert.h>
#include <stdio.h>
#include "../src/p2core/p2_j2534_bridge.h"

int main(void){
    p2_j2534_bridge b;
    p2_bridge_tx_result out;
    static const uint8_t a3[12]={0,0x0F,0xFF,0xFE,0xCF,0x50,0xA3,0x02,0x03,0xA5,0xA5,0};
    static const uint8_t e3[12]={0x01,0x20,0,0x03,0xCB,0x50,0xE3,0x02,0,0,0,0};
    static const uint8_t fb[12]={0,0x0F,0xFF,0xFE,0xCB,0x50,0xB9,0xFB,0,0,0,0};
    static const uint8_t e3_11[12]={0,0,7,0xE8,0xCB,0x50,0xE3,0x02,0,0,0,0};
    p2_bridge_init(&b);
    p2_bridge_connect(&b,1u,5u,500000u);
    p2_bridge_connect(&b,2u,5u,500000u);
    /* 1: no active request on either channel => orphan, never acceptance. */
    assert(p2_bridge_inspect_hw_rx(&b,1u,0,e3,12u)==P2_HW_RX_ORPHAN_E3_CANDIDATE);
    /* 2: channel 1 A3 request, independent channel 2 remains orphan. */
    assert(p2_bridge_inspect_tx(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,a3,12u,&out));
    assert(out.hw_event==P2_HW_A3_TX);
    assert(p2_bridge_inspect_hw_rx(&b,2u,0,e3,12u)==P2_HW_RX_ORPHAN_E3_CANDIDATE);
    /* 3: only an unverified candidate for the expected legacy ID. */
    assert(p2_bridge_inspect_hw_rx(&b,1u,0,e3,12u)==P2_HW_RX_LEGACY_ID_CANDIDATE_UNVERIFIED);
    assert(b.channels[0].hw_tx.last_request==1);
    /* 4: bridge never generates ECU RX or diagnostic ignition state. */
    assert(b.vehicle.diagnostic_ignition==P2_DIAG_IGNITION_UNKNOWN);
    assert(b.vehicle.diag_e3_02_candidates==0u);
    /* 5: a frame from an 11-bit response CAN ID is excluded. */
    assert(p2_bridge_inspect_hw_rx(&b,1u,0,e3_11,12u)==P2_HW_RX_UNRELATED);
    /* 6: DLC must be exactly 8 + 4 J2534 ID bytes. */
    assert(p2_bridge_inspect_hw_rx(&b,1u,0,e3,11u)==P2_HW_RX_UNRELATED);
    /* 7: unknown channel ID is not correlated. */
    assert(p2_bridge_inspect_hw_rx(&b,77u,0,e3,12u)==P2_HW_RX_UNRELATED);
    /* 8: ISO15765 channel must never be treated as raw-CAN CEM exchange. */
    p2_bridge_connect(&b,3u,6u,500000u);
    assert(p2_bridge_inspect_hw_rx(&b,3u,0,e3,12u)==P2_HW_RX_UNRELATED);
    /* 9: after disconnect + reconnect previous A3 is forgotten. */
    p2_bridge_disconnect(&b,1u);
    p2_bridge_connect(&b,1u,5u,500000u);
    assert(p2_bridge_inspect_hw_rx(&b,1u,0,e3,12u)==P2_HW_RX_ORPHAN_E3_CANDIDATE);
    /* 10: bus retune / channel rebind also resets A3 evidence. */
    assert(p2_bridge_inspect_tx(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,a3,12u,&out));
    p2_bridge_connect(&b,1u,5u,125000u);
    assert(p2_bridge_inspect_hw_rx(&b,1u,0,e3,12u)==P2_HW_RX_ORPHAN_E3_CANDIDATE);
    /* 11: B9FB remains an independent, non-acknowledging route. */
    p2_bridge_connect(&b,1u,5u,500000u);
    assert(p2_bridge_inspect_tx(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,fb,12u,&out));
    assert(out.decision==P2_CEM_KEEP_EXISTING && b.channels[0].hw_tx.last_request==0u);
    assert(p2_bridge_inspect_hw_rx(&b,1u,0,e3,12u)==P2_HW_RX_ORPHAN_E3_CANDIDATE);
    puts("PASS 11/11 B3A316 bridge and no-reply regression groups");
    return 0;
}
