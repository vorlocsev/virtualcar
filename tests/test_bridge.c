#include "p2_j2534_bridge.h"
#include <stdio.h>
#include <assert.h>
#include <string.h>
static unsigned groups;
#define GROUP() (++groups)
int main(void) {
 p2_j2534_bridge b;
 p2_bridge_tx_result a;
 unsigned k;
 uint8_t frame[12]={0,0x0F,0xFF,0xFE,0xCF,0x50,0xA3,0x02,0x03,0xA5,0xA5,0};
 uint8_t f0[12]={0,0x0F,0xFF,0xFE,0xCB,0x50,0xB9,0xF0,0,0,0,0};
 uint8_t fb[12]={0,0x0F,0xFF,0xFE,0xCB,0x50,0xB9,0xFB,0,0,0,0};
 uint8_t ls[12]={0,0x61,0x7F,0xF8,0,0,0,0,0,0,0xC0,0};
 p2_bridge_init(&b);
 assert(b.vehicle.cfg.hs_bitrate==500000 && b.vehicle.cfg.ls_bitrate==125000);
 assert(!b.vehicle.cfg.enable_community_ls_signals); GROUP();
 /* Unknown ChannelID MUST be ignored, not classified as 500k by default. */
 assert(!p2_bridge_inspect_tx(&b,11,0,frame,12,&a));
 assert(b.unknown_channel_events==1); GROUP();
 p2_bridge_connect(&b,11,5,500000);
 assert(p2_bridge_inspect_tx(&b,11,0,frame,12,&a));
 assert(!strcmp(a.label,"a3_0203_shape") && a.decision==P2_CEM_NEED_EVIDENCE);
 assert(b.vehicle.a3_shape_seen==1); GROUP();
 assert(p2_bridge_inspect_tx(&b,11,0,f0,12,&a));
 assert(a.decision==P2_CEM_NEED_EVIDENCE && b.vehicle.b9f0_seen==1);
 assert(p2_bridge_inspect_tx(&b,11,0,fb,12,&a));
 assert(a.decision==P2_CEM_KEEP_EXISTING && b.vehicle.b9fb_seen==1);
 assert(b.vehicle.diagnostic_ignition==P2_DIAG_IGNITION_UNKNOWN); GROUP();
 /* Reused ChannelID retains the latest protocol & bitrate only. */
 p2_bridge_connect(&b,11,5,125000);
 assert(p2_bridge_inspect_tx(&b,11,0,frame,12,&a));
 assert(a.decision==P2_CEM_ROUTE_MISMATCH && a.baud==125000);
 assert(b.channels[0].generation==2); GROUP();
 /* Non-CAN & invalid framing. */
 p2_bridge_connect(&b,12,2,41600);
 assert(!p2_bridge_inspect_tx(&b,12,0,frame,12,&a));
 assert(!p2_bridge_inspect_tx(&b,11,0,frame,3,&a));
 assert(!p2_bridge_inspect_tx(&b,11,0,frame,4133,&a));
 frame[0]=0xE0;assert(!p2_bridge_inspect_tx(&b,11,0,frame,12,&a)); frame[0]=0;
 GROUP();
 /* Passive LS observation off by default; key state never becomes diagnostic ON. */
 assert(!p2_bridge_inspect_rx(&b,11,0,ls,12,100));
 assert(!b.vehicle.passive_key.valid); GROUP();
 /* Can observe only when explicitly configured for the actual car. */
 b.vehicle.cfg.enable_community_ls_signals=true;
 b.vehicle.cfg.observed_cem_ls_can_id=0x00617FF8;
 /* J2534 transmit indications must not mutate passive key/ignition state. */
 assert(!p2_bridge_inspect_rx(&b,11,0x001u,ls,12,100));
 assert(!p2_bridge_inspect_rx(&b,11,0x009u,ls,12,100));
 assert(!p2_bridge_inspect_rx(&b,11,0x002u,ls,12,100));
 assert(!p2_bridge_inspect_rx(&b,11,0x008u,ls,12,100));
 assert(!p2_bridge_inspect_rx(&b,11,0x200u,ls,12,100));
 assert(!b.vehicle.passive_key.valid);
 assert(b.inspected_rx==0u);
 /* CAN_29BIT_ID is legitimate addressing metadata for actual RX data. */
 assert(!strcmp(p2_bridge_inspect_rx(&b,11,0x100u,ls,12,101),"cem_broadcast_observed"));
 assert(b.vehicle.passive_key.valid && b.vehicle.passive_key.key_position==2);
 assert(b.vehicle.diagnostic_ignition==P2_DIAG_IGNITION_UNKNOWN);
 assert(!p2_bridge_inspect_rx(&b,11,0,ls,11,102)); GROUP();
 /* Disconnect suppresses both TX and RX, including old generations. */
 p2_bridge_disconnect(&b,11);
 assert(!p2_bridge_inspect_tx(&b,11,0,frame,12,&a));
 assert(!p2_bridge_inspect_rx(&b,11,0,ls,12,103)); GROUP();
 /* Bound the channel table; overflow does not overwrite occupied entries. */
 p2_bridge_init(&b);
 for(k=0;k<P2_BRIDGE_MAX_CHANNELS;k++)p2_bridge_connect(&b,100+k,5,500000);
 p2_bridge_connect(&b,999,5,500000);
 assert(b.channels_overflow==1);
 assert(!p2_bridge_inspect_tx(&b,999,0,frame,12,&a));
 assert(p2_bridge_inspect_tx(&b,100,0,frame,12,&a)); GROUP();
 /* Never produces replies or validates E3 on raw fragments. */
 assert(b.vehicle.diag_e3_02_candidates==0);
 assert(b.vehicle.diagnostic_ignition==P2_DIAG_IGNITION_UNKNOWN); GROUP();
 printf("dev26: %u/11 J2534 bridge integration groups OK\n",groups);
 return groups==11?0:1;
}
