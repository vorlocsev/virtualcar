/* B3A317: in-memory time-scoped E3 candidate evidence, NOT ECU confirmation. */
#include <assert.h>
#include <stdio.h>
#include "../src/p2core/p2_j2534_bridge.h"

static const uint8_t a3[12]={0,0x0F,0xFF,0xFE,0xCF,0x50,0xA3,0x02,0x03,0xA5,0xA5,0};
static const uint8_t e3[12]={0x01,0x20,0,3,0xCB,0x50,0xE3,0x02,0,0,0,0};
static const uint8_t fb[12]={0,0x0F,0xFF,0xFE,0xCB,0x50,0xB9,0xFB,0,0,0,0};
static const uint8_t dummy[12]={0,0x0F,0xFF,0xFE,0xCB,0x50,0xA1,0,0,0,0,0};

int main(void){
    p2_j2534_bridge b={0};
    p2_bridge_tx_result o;
    p2_bridge_init(&b);
    p2_bridge_connect(&b,1u,5u,500000u);
    p2_bridge_connect(&b,2u,5u,500000u);
    /* 1: orphan RX before TX is never accepted. */
    assert(p2_bridge_inspect_hw_rx_at(&b,1u,0,e3,12u,900000u)==P2_HW_RX_ORPHAN_E3_CANDIDATE);
    /* 2: stamp outbound A3 on channel one only. */
    assert(p2_bridge_inspect_tx_at(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,a3,12u,1000000u,&o));
    assert(o.hw_event==P2_HW_A3_TX && b.channels[0].hw_a3_clock_valid);
    assert(b.channels[0].hw_a3_tx_us==1000000u);
    /* 3: the other channel cannot borrow time or phase. */
    assert(p2_bridge_inspect_hw_rx_at(&b,2u,0,e3,12u,1100000u)==P2_HW_RX_ORPHAN_E3_CANDIDATE);
    /* 4: monotonic response BEFORE A3 is a separate mismatch. */
    assert(p2_bridge_inspect_hw_rx_at(&b,1u,0,e3,12u,999999u)==P2_HW_RX_BEFORE_A3_TX_CANDIDATE);
    /* 5: a plausible in-window delivered E3 is still NOT security acceptance. */
    assert(p2_bridge_inspect_hw_rx_at(&b,1u,0,e3,12u,1100000u)==P2_HW_RX_TIMED_LEGACY_ID_CANDIDATE_UNVERIFIED);
    assert(b.channels[0].hw_tx.last_request==1u);
    /* 6: two deliveries of the same candidate are distinguished. */
    assert(p2_bridge_inspect_hw_rx_at(&b,1u,0,e3,12u,1100001u)==P2_HW_RX_DUPLICATE_E3_CANDIDATE);
    /* 7: last microsecond of 5-s window remains a candidate (not a success). */
    assert(p2_bridge_inspect_tx_at(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,a3,12u,2000000u,&o));
    assert(p2_bridge_inspect_hw_rx_at(&b,1u,0,e3,12u,7000000u)==P2_HW_RX_TIMED_LEGACY_ID_CANDIDATE_UNVERIFIED);
    /* 8: 5 seconds + 1 microsecond is stale, with no candidate promotion. */
    assert(p2_bridge_inspect_tx_at(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,a3,12u,2000000u,&o));
    assert(p2_bridge_inspect_hw_rx_at(&b,1u,0,e3,12u,7000001u)==P2_HW_RX_EXPIRED_A3_WINDOW_CANDIDATE);
    /* 9: a separate new B9FB TX invalidates A3 clock (no reply synthesis). */
    assert(p2_bridge_inspect_tx_at(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,a3,12u,3000000u,&o));
    assert(p2_bridge_inspect_tx_at(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,fb,12u,3000010u,&o));
    assert(o.decision==P2_CEM_KEEP_EXISTING);
    assert(!b.channels[0].hw_a3_clock_valid);
    assert(p2_bridge_inspect_hw_rx_at(&b,1u,0,e3,12u,3000020u)==P2_HW_RX_NO_TX_CLOCK_CANDIDATE);
    /* 10: any further ordinary TX also invalidates the previous A3 clock. */
    assert(p2_bridge_inspect_tx_at(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,a3,12u,4000000u,&o));
    assert(p2_bridge_inspect_tx_at(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,dummy,12u,4000001u,&o));
    assert(p2_bridge_inspect_hw_rx_at(&b,1u,0,e3,12u,4000002u)==P2_HW_RX_NO_TX_CLOCK_CANDIDATE);
    /* 11: untimed legacy TX cannot accidentally claim a live time window. */
    p2_bridge_connect(&b,1u,5u,500000u);
    assert(p2_bridge_inspect_tx(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,a3,12u,&o));
    assert(p2_bridge_inspect_hw_rx_at(&b,1u,0,e3,12u,5000000u)==P2_HW_RX_NO_TX_CLOCK_CANDIDATE);
    /* 12: raw-CAN START_OF_MESSAGE indication is never a physical frame. */
    assert(p2_bridge_inspect_hw_rx_at(&b,1u,P2_BRIDGE_RX_START_OF_MESSAGE_FLAG,e3,12u,5000000u)==P2_HW_RX_UNRELATED);
    /* 13: retune invalidates both sequence and recorded monotonic clock. */
    assert(p2_bridge_inspect_tx_at(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,a3,12u,6000000u,&o));
    p2_bridge_connect(&b,1u,5u,125000u);
    assert(!b.channels[0].hw_a3_clock_valid);
    assert(p2_bridge_inspect_hw_rx_at(&b,1u,0,e3,12u,6000001u)==P2_HW_RX_ORPHAN_E3_CANDIDATE);
    /* 14: disconnect + reuse of same numeric channel ID stays isolated. */
    p2_bridge_disconnect(&b,1u);
    p2_bridge_connect(&b,1u,5u,500000u);
    assert(p2_bridge_inspect_hw_rx_at(&b,1u,0,e3,12u,6000002u)==P2_HW_RX_ORPHAN_E3_CANDIDATE);
    /* 15: null output and invalid writes do not retain previous A3 clock. */
    assert(p2_bridge_inspect_tx_at(&b,1u,P2_BRIDGE_CAN_29BIT_FLAG,a3,12u,7000000u,&o));
    assert(!p2_bridge_inspect_tx_at(&b,1u,0,0,0u,7000001u,&o));
    assert(!b.channels[0].hw_a3_clock_valid);
    /* 16: receiver cannot mutate TX phase nor generate authenticated identity. */
    assert(b.vehicle.diagnostic_ignition==P2_DIAG_IGNITION_UNKNOWN);
    assert(b.vehicle.diag_e3_02_candidates==0u);
    assert(b.vehicle.b9fb_seen==1u);
    assert(b.inspected_rx==0u);
    /* 17: metadata label is constant and conspicuously unverified. */
    assert(p2_hw_rx_event_name(P2_HW_RX_TIMED_LEGACY_ID_CANDIDATE_UNVERIFIED)!=0);
    assert(p2_hw_rx_event_name(P2_HW_RX_DUPLICATE_E3_CANDIDATE)!=0);
    puts("PASS 17/17 B3A317 time-scoped Hardware RX candidate groups");
    return 0;
}
