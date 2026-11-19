#include "p2_j2534_bridge.h"

static p2_bridge_channel *find_channel(p2_j2534_bridge *b, uint32_t id) {
    size_t k;
    for (k=0;k<P2_BRIDGE_MAX_CHANNELS;k++)
        if (b->channels[k].active && b->channels[k].id==id)
            return &b->channels[k];
    return 0;
}
static uint32_t be32(const uint8_t *d) {
    return ((uint32_t)d[0]<<24)|((uint32_t)d[1]<<16)|
           ((uint32_t)d[2]<<8)|(uint32_t)d[3];
}
void p2_bridge_init(p2_j2534_bridge *b) {
    if (!b) return;
    *b = (p2_j2534_bridge){0};
    p2_vehicle_init(&b->vehicle, 0);
}
void p2_bridge_connect(p2_j2534_bridge *b,uint32_t id,
                       uint32_t protocol_id,uint32_t baud) {
    size_t k; p2_bridge_channel *c;
    if (!b) return;
    c = find_channel(b,id);
    if (!c) {
        for (k=0;k<P2_BRIDGE_MAX_CHANNELS;k++)
            if (!b->channels[k].active) {c=&b->channels[k];break;}
    }
    if (!c) {++b->channels_overflow;return;}
    c->active=true; c->id=id; c->protocol_id=protocol_id;
    c->baud=baud; c->generation=++b->next_generation;
    c->hw_tx=(p2_hw_tx_trace){0}; /* stale TX never crosses reconnect */
}
void p2_bridge_disconnect(p2_j2534_bridge *b,uint32_t id) {
    p2_bridge_channel *c;
    if (!b) return;
    c=find_channel(b,id);
    if(c) {c->active=false; c->hw_tx=(p2_hw_tx_trace){0};}
}
bool p2_bridge_inspect_tx(p2_j2534_bridge *b,uint32_t id,uint32_t flags,
                          const uint8_t *data,size_t size,
                          p2_bridge_tx_result *out) {
    p2_bridge_channel *c;
    p2_vehicle_tx_assessment a;
    uint32_t can_id;
    bool extended;
    if (out) *out=(p2_bridge_tx_result){0};
    if (!b||!out||!data||size<4||size>4128) return false;
    c=find_channel(b,id);
    if (!c) {++b->unknown_channel_events;return false;}
    if (c->protocol_id!=5u && c->protocol_id!=6u) return false;
    can_id=be32(data);
    if(can_id>0x1FFFFFFFu) return false;
    /* A CAN ID > 0x7FF is necessarily extended; some J2534 clients omit
       CAN_29BIT_ID on individual writes. Never infer from low-numbered IDs. */
    extended=(flags&P2_BRIDGE_CAN_29BIT_FLAG)!=0 || can_id>0x7FFu;
    if(!p2_vehicle_observe_passthru_tx(&b->vehicle,c->protocol_id,c->baud,
                                       extended,data,size,&a)) return false;
    /* CAN-only metadata. Neither a positive reply nor CEM authentication. */
    if(c->protocol_id==5u)
        out->hw_event=p2_hw_observe_tx(&c->hw_tx,can_id,c->baud,data+4,size-4);
    out->label=p2_cem_request_name(a.classified.request);
    out->decision=a.classified.decision;
    out->baud=c->baud;
    out->bus=(c->baud==b->vehicle.cfg.ls_bitrate)?P2_BUS_LS:P2_BUS_HS;
    out->observed=true;
    ++b->inspected_tx;
    return true;
}
const char *p2_bridge_inspect_rx(p2_j2534_bridge *b,uint32_t id,uint32_t flags,
                                  const uint8_t *data,size_t size,uint64_t now) {
    p2_bridge_channel *c;
    p2_ls_observation result;
    uint32_t can_id;
    bool extended;
    if (!b||!data||size!=12) return 0; /* one 8-byte raw CAN frame */
    c=find_channel(b,id);
    if(!c){++b->unknown_channel_events;return 0;}
    if(c->protocol_id!=5u || c->baud!=b->vehicle.cfg.ls_bitrate) return 0;
    can_id=be32(data);
    extended=(flags&P2_BRIDGE_CAN_29BIT_FLAG)!=0 || can_id>0x7FFu;
    if(!p2_vehicle_observe_rx(&b->vehicle,P2_BUS_LS,c->baud,extended,
                              can_id,data+4,8,now,&result))return 0;
    ++b->inspected_rx;
    switch(result.kind) {
    case P2_LS_CEM_IGNITION:return "cem_broadcast_observed";
    case P2_LS_GEARBOX:return "gearbox_broadcast";
    case P2_LS_CCM:return "ccm_broadcast";
    case P2_LS_REM:return "rem_broadcast";
    case P2_LS_SWM:return "swm_broadcast";
    default:return 0;
    }
}
