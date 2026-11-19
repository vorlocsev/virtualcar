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
    c->hw_a3_tx_us=0; c->hw_a3_clock_valid=false; c->hw_e3_candidate_seen=false;
}
void p2_bridge_disconnect(p2_j2534_bridge *b,uint32_t id) {
    p2_bridge_channel *c;
    if (!b) return;
    c=find_channel(b,id);
    if(c) {
        c->active=false; c->hw_tx=(p2_hw_tx_trace){0};
        c->hw_a3_tx_us=0; c->hw_a3_clock_valid=false; c->hw_e3_candidate_seen=false;
    }
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
/* Caller supplies only an RX *delivered* through PassThruReadMsgs.
   Per-channel A3 chronology came from TX, but no ECU acceptance is inferred. */
p2_hw_rx_event p2_bridge_inspect_hw_rx(p2_j2534_bridge *b,
                                        uint32_t channel,uint32_t rx_status,
                                        const uint8_t *data,size_t size){
    p2_bridge_channel *c;
    uint32_t id;
    if((rx_status&P2_BRIDGE_RX_START_OF_MESSAGE_FLAG)!=0u)
        return P2_HW_RX_UNRELATED;
    if(!b || !data || size!=12u)return P2_HW_RX_UNRELATED;
    c=find_channel(b,channel);
    if(!c || c->protocol_id!=5u)return P2_HW_RX_UNRELATED;
    id=be32(data);
    if(id<=0x7FFu || id>0x1FFFFFFFu)return P2_HW_RX_UNRELATED;
    return p2_hw_inspect_e3_rx_candidate(&c->hw_tx,c->baud,id,data+4,8u);
}
/* A3 monotonic timestamp is private channel metadata, not an ECU response.
   Any subsequent TX on the channel ends the pending observation window. */
bool p2_bridge_inspect_tx_at(p2_j2534_bridge *b,uint32_t channel,
                             uint32_t flags,const uint8_t *data,
                             size_t size,uint64_t observed_us,
                             p2_bridge_tx_result *out){
    bool ok=p2_bridge_inspect_tx(b,channel,flags,data,size,out);
    p2_bridge_channel *c=b?find_channel(b,channel):0;
    if(c){
        bool is_a3=(ok && out && out->hw_event==P2_HW_A3_TX);
        c->hw_a3_clock_valid=is_a3;
        c->hw_a3_tx_us=is_a3?observed_us:0u;
        c->hw_e3_candidate_seen=false;
    }
    return ok;
}
/* A plausible legacy E3 header gets only a time-scoped diagnostic label.
   This API cannot report successful session/authorization and never emits RX. */
p2_hw_rx_event p2_bridge_inspect_hw_rx_at(p2_j2534_bridge *b,
                                           uint32_t channel,
                                           uint32_t rx_status,
                                           const uint8_t *data,size_t size,
                                           uint64_t delivered_us){
    p2_hw_rx_event ev=p2_bridge_inspect_hw_rx(b,channel,rx_status,data,size);
    p2_bridge_channel *c;
    if(ev!=P2_HW_RX_LEGACY_ID_CANDIDATE_UNVERIFIED)return ev;
    c=b?find_channel(b,channel):0;
    if(!c || !c->hw_a3_clock_valid)
        return P2_HW_RX_NO_TX_CLOCK_CANDIDATE;
    if(delivered_us<c->hw_a3_tx_us)
        return P2_HW_RX_BEFORE_A3_TX_CANDIDATE;
    if(delivered_us-c->hw_a3_tx_us>P2_BRIDGE_HW_E3_WINDOW_US)
        return P2_HW_RX_EXPIRED_A3_WINDOW_CANDIDATE;
    if(c->hw_e3_candidate_seen)
        return P2_HW_RX_DUPLICATE_E3_CANDIDATE;
    c->hw_e3_candidate_seen=true;
    return P2_HW_RX_TIMED_LEGACY_ID_CANDIDATE_UNVERIFIED;
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
