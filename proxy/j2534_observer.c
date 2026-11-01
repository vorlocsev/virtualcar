#include "j2534_observer.h"

static vc_channel *channel_for(vc_observer *o, uint32_t id) {
    unsigned i;
    for(i=0;i<VC_CHANNELS;i++)
        if(o->channels[i].active && o->channels[i].id==id)return &o->channels[i];
    return 0;
}
static uint32_t be32(const uint8_t *d) {
    return ((uint32_t)d[0]<<24)|((uint32_t)d[1]<<16)|((uint32_t)d[2]<<8)|d[3];
}
static unsigned active_filters(vc_observer *o,uint32_t ch) {
    unsigned i,n=0;
    for(i=0;i<VC_FILTERS;i++)if(o->filters[i].active && o->filters[i].channel==ch)++n;
    return n;
}
static vc_event event_for(vc_observer *o,uint32_t ch,uint32_t now,const char *name) {
    vc_event e={0}; vc_channel *c=channel_for(o,ch);
    e.event=name;e.classification="none";e.relation="unpaired";
    e.channel=ch;e.ms=now;e.active_filters=active_filters(o,ch);
    if(c){e.generation=c->generation;e.protocol=c->protocol;e.baud=c->baud;e.incomplete=c->incomplete;}
    return e;
}
static void emit(vc_observer *o,const vc_event *e) {if(o->emit)o->emit(o->context,e);}
static void finish(vc_observer *o,vc_pending *p,uint32_t now,const char *reason) {
    vc_event e=event_for(o,p->channel,now,"iso15765_wait_end");
    e.relation=reason;e.sequence=p->sequence;e.filter_id=p->filter_id;
    e.elapsed_ms=now-p->ms;p->active=0;emit(o,&e);
}
static void expire(vc_observer *o,uint32_t ch,uint32_t now) {
    unsigned i;
    for(i=0;i<VC_PENDING;i++)if(o->pending[i].active && o->pending[i].channel==ch &&
        (uint32_t)(now-o->pending[i].ms)>VC_WINDOW_MS)
        finish(o,&o->pending[i],now,"window_elapsed_no_final_rx");
}
static void end_channel(vc_observer *o,uint32_t ch,uint32_t now,const char *reason) {
    unsigned i;
    for(i=0;i<VC_PENDING;i++)if(o->pending[i].active && o->pending[i].channel==ch)
        finish(o,&o->pending[i],now,reason);
    for(i=0;i<VC_FILTERS;i++)if(o->filters[i].channel==ch)o->filters[i].active=0;
}
void vc_init(vc_observer *o,vc_emit callback,void *context) {
    /* Avoid a large temporary aggregate on the freestanding x86 stack. */
    size_t i;uint8_t *p=(uint8_t *)o;
    for(i=0;i<sizeof(*o);i++)p[i]=0;
    o->emit=callback;o->context=context;
}
void vc_connect(vc_observer *o,uint32_t dev,uint32_t ch,uint32_t protocol,uint32_t baud,uint32_t now) {
    vc_channel *c=channel_for(o,ch);unsigned i;
    if(c)end_channel(o,ch,now,"channel_reused");
    else for(i=0;i<VC_CHANNELS;i++)if(!o->channels[i].active){c=&o->channels[i];break;}
    if(!c){vc_event e=event_for(o,ch,now,"observer_capacity");e.incomplete=1;emit(o,&e);return;}
    c->id=ch;c->device=dev;c->protocol=protocol;c->baud=baud;
    c->generation=++o->generation;c->active=1;c->incomplete=0;
}
void vc_disconnect(vc_observer *o,uint32_t ch,uint32_t now) {
    vc_channel *c=channel_for(o,ch);
    end_channel(o,ch,now,"disconnect_no_final_rx");if(c)c->active=0;
}
void vc_close(vc_observer *o,uint32_t dev,uint32_t now) {
    unsigned i;
    for(i=0;i<VC_CHANNELS;i++)if(o->channels[i].active && o->channels[i].device==dev)
        vc_disconnect(o,o->channels[i].id,now);
}
static void end_filter(vc_observer *o,uint32_t ch,uint32_t id,uint32_t now,const char *reason) {
    unsigned i;
    for(i=0;i<VC_PENDING;i++)if(o->pending[i].active && o->pending[i].channel==ch &&
        o->pending[i].filter_id==id)finish(o,&o->pending[i],now,reason);
}
void vc_filter_start(vc_observer *o,uint32_t ch,uint32_t type,const vc_message *m,
                     const vc_message *p,const vc_message *f,uint32_t id,uint32_t st,uint32_t now) {
    vc_channel *c=channel_for(o,ch);vc_filter *slot=0;unsigned i;
    vc_event e=event_for(o,ch,now,"filter_start");e.status=st;e.filter_id=id;e.filter_type=type;
    if(st==0 && c){
        for(i=0;i<VC_FILTERS;i++)if(o->filters[i].active && o->filters[i].channel==ch && o->filters[i].id==id){
            slot=&o->filters[i];end_filter(o,ch,id,now,"filter_replaced_no_final_rx");break;
        }
        if(!slot)for(i=0;i<VC_FILTERS;i++)if(!o->filters[i].active){slot=&o->filters[i];break;}
        if(!slot)c->incomplete=1;
        else {
            *slot=(vc_filter){0};slot->active=1;slot->channel=ch;slot->id=id;slot->type=type;
            /* Only ID and optional extended address masks can establish a
             * pairing. Payload-sensitive filters are counted but unverified. */
            if(m && p && m->DataSize==p->DataSize && (m->DataSize==4 || m->DataSize==5) &&
               m->ProtocolID==c->protocol && p->ProtocolID==c->protocol &&
               ((m->DataSize==5)==((p->TxFlags&0x80u)!=0))){
                slot->size=m->DataSize;slot->protocol=p->ProtocolID;slot->flags=p->TxFlags;
                for(i=0;i<slot->size;i++){slot->mask[i]=m->Data[i];slot->pattern[i]=p->Data[i];}
                if(type==3 && f && f->ProtocolID==c->protocol && f->DataSize==slot->size &&
                   ((f->DataSize==5)==((f->TxFlags&0x80u)!=0)) && be32(f->Data)<=0x1FFFFFFFu){
                    for(i=0;i<slot->size;i++)slot->flow[i]=f->Data[i];
                    slot->flow_flags=f->TxFlags;slot->usable=1;
                }
            }
            e.filter_usable=slot->usable;e.size=slot->size;e.tx_flags=slot->flags;
            if(slot->size>=4){e.rx_pattern_id=be32(slot->pattern);e.rx_mask_id=be32(slot->mask);}
            if(slot->usable)e.flow_control_id=be32(slot->flow);
        }
    }
    e.active_filters=active_filters(o,ch);e.incomplete=c?c->incomplete:1;emit(o,&e);
}
void vc_filter_stop(vc_observer *o,uint32_t ch,uint32_t id,uint32_t st,uint32_t now) {
    unsigned i;vc_event e;
    if(st==0){
        end_filter(o,ch,id,now,"filter_stopped_no_final_rx");
        for(i=0;i<VC_FILTERS;i++)if(o->filters[i].channel==ch && o->filters[i].id==id)o->filters[i].active=0;
    }
    e=event_for(o,ch,now,"filter_stop");e.status=st;e.filter_id=id;emit(o,&e);
}
void vc_ioctl(vc_observer *o,uint32_t ch,uint32_t id,uint32_t st,uint32_t now) {
    vc_channel *c=channel_for(o,ch);unsigned i;
    if(st || !c)return;
    if(id==10u){end_channel(o,ch,now,"filters_cleared_no_final_rx");c->incomplete=0;}
    if(id==8u || id==10u){
        if(id==8u)for(i=0;i<VC_PENDING;i++)if(o->pending[i].active && o->pending[i].channel==ch)
            finish(o,&o->pending[i],now,"rx_cleared_no_final_rx");
        {vc_event e=event_for(o,ch,now,id==10u?"filters_clear":"rx_clear");emit(o,&e);}
    }
}
static int valid(const vc_channel *c,const vc_message *m) {
    return c && c->protocol==6 && m && m->ProtocolID==6 &&
        m->DataSize>=4 && m->DataSize<=sizeof(m->Data) &&
        (!m->ExtraDataIndex || (m->ExtraDataIndex>=4 && m->ExtraDataIndex<=m->DataSize)) &&
        be32(m->Data)<=0x1FFFFFFFu;
}
static unsigned payload_end(const vc_message *m) {return m->ExtraDataIndex?m->ExtraDataIndex:m->DataSize;}
static unsigned header_size(uint32_t flags) {return (flags&0x80u)?5u:4u;}
static int same_format(uint32_t a,uint32_t b,uint32_t aid,uint32_t bid) {
    return ((a&0x80u)==(b&0x80u)) &&
        (((a&0x100u)!=0 || aid>0x7FFu)==((b&0x100u)!=0 || bid>0x7FFu));
}
static const char *request_class(uint8_t sid) {
    switch(sid){
    case 0x01:return "obd_current_data";
    case 0x02:return "obd_freeze_frame";
    case 0x03:return "obd_read_dtcs";
    case 0x07:return "obd_pending_dtcs";
    case 0x09:return "obd_vehicle_information";
    case 0x0A:return "obd_permanent_dtcs";
    case 0x19:return "uds_read_dtc_information";
    case 0x1A:return "kwp_read_identification";
    case 0x21:return "kwp_read_local_identifier";
    case 0x22:return "uds_read_data_identifier";
    case 0x23:return "uds_read_memory";
    case 0x3E:return "uds_tester_present";
    default:return "other_service";
    }
}
static unsigned selector_size(uint8_t sid) {
    if(sid==0x22)return 2;
    if(sid==1 || sid==2 || sid==9 || sid==0x19 || sid==0x1A || sid==0x21 || sid==0x3E)return 1;
    return 0;
}
static int known_request(uint8_t sid) {
    return sid==1 || sid==2 || sid==3 || sid==7 || sid==9 || sid==10 ||
        sid==0x19 || sid==0x1A || sid==0x21 || sid==0x22 || sid==0x23 || sid==0x3E;
}
void vc_tx(vc_observer *o,uint32_t ch,const vc_message *m,uint32_t now) {
    vc_channel *c=channel_for(o,ch);vc_event e;vc_filter *match=0;vc_pending *p=0;
    unsigned h,n,i,j,select;uint8_t sid;
    if(!c || c->protocol!=6)return;
    expire(o,ch,now);e=event_for(o,ch,now,"iso15765_tx");
    if(!valid(c,m)){e.classification="invalid_metadata";emit(o,&e);return;}
    e.can_id=be32(m->Data);e.size=m->DataSize;e.tx_flags=m->TxFlags;e.device_timestamp=m->Timestamp;
    h=header_size(m->TxFlags);n=payload_end(m);
    if(n<=h){e.classification="incomplete_request";emit(o,&e);return;}
    sid=m->Data[h];e.classification=request_class(sid);select=selector_size(sid);
    if(n<h+1+select){e.classification="incomplete_request";emit(o,&e);return;}
    for(i=0;i<VC_FILTERS;i++){
        vc_filter *f=&o->filters[i];
        if(!f->active || f->channel!=ch || !f->usable || f->size!=h ||
           !same_format(m->TxFlags,f->flow_flags,e.can_id,be32(f->flow)))continue;
        for(j=0;j<h && m->Data[j]==f->flow[j];j++){}
        if(j==h){match=f;++e.candidates;}
    }
    e.relation=e.incomplete?"filter_state_incomplete":e.candidates==0?"no_usable_flow_filter":
        e.candidates>1?"ambiguous_flow_filters":"flow_filter_observed";
    if(e.candidates==1 && !e.incomplete && known_request(sid)){
        e.filter_id=match->id;
        for(i=0;i<VC_PENDING;i++)if(!o->pending[i].active){p=&o->pending[i];break;}
        if(!p){e.relation="pending_capacity";c->incomplete=1;e.incomplete=1;}
        else {
            p->active=1;p->channel=ch;p->sequence=++o->sequence;p->ms=now;p->filter_id=match->id;
            p->sid=sid;p->selector_size=(uint8_t)select;
            for(i=0;i<select;i++)p->selector[i]=m->Data[h+1+i];
            e.sequence=p->sequence;
        }
    }
    emit(o,&e);
}
static int rx_matches(const vc_filter *f,const vc_message *m,unsigned h) {
    unsigned i;
    if(!f->usable || f->size!=h || !same_format(m->RxStatus,f->flags,be32(m->Data),be32(f->pattern)))return 0;
    for(i=0;i<h;i++)if((m->Data[i]&f->mask[i])!=(f->pattern[i]&f->mask[i]))return 0;
    return 1;
}
void vc_rx(vc_observer *o,uint32_t ch,const vc_message *m,uint32_t now) {
    vc_channel *c=channel_for(o,ch);vc_event e;vc_pending *match=0;
    unsigned h,n,i,j;int negative=0,pending=0;
    if(!c || c->protocol!=6)return;
    expire(o,ch,now);e=event_for(o,ch,now,"iso15765_rx");
    if(!valid(c,m)){e.classification="invalid_metadata";emit(o,&e);return;}
    e.can_id=be32(m->Data);e.size=m->DataSize;e.rx_status=m->RxStatus;e.device_timestamp=m->Timestamp;
    h=header_size(m->RxStatus);n=payload_end(m);
    if(m->RxStatus&9u){e.classification="tx_indication";emit(o,&e);return;}
    if(m->RxStatus&2u){e.classification="start_of_message";emit(o,&e);return;}
    if(n<=h){e.classification="incomplete_response";emit(o,&e);return;}
    if(m->Data[h]==0x7F){
        if(n<h+3){e.classification="incomplete_response";emit(o,&e);return;}
        negative=1;pending=m->Data[h+2]==0x78;
    }
    e.classification=negative?(pending?"negative_response_pending":"negative_response"):"response_observed";
    for(i=0;i<VC_PENDING;i++){
        vc_pending *p=&o->pending[i];int filter_match=0;
        if(!p->active || p->channel!=ch)continue;
        for(j=0;j<VC_FILTERS;j++){
            vc_filter *f=&o->filters[j];
            if(f->active && f->channel==ch && f->id==p->filter_id && rx_matches(f,m,h)){filter_match=1;break;}
        }
        if(!filter_match)continue;
        if(negative){if(m->Data[h+1]!=p->sid)continue;}
        else {
            if(m->Data[h]!=(uint8_t)(p->sid+0x40) || n<h+1+p->selector_size)continue;
            for(j=0;j<p->selector_size && m->Data[h+1+j]==p->selector[j];j++){}
            if(j!=p->selector_size)continue;
            /* ReadDataByIdentifier header without any value is partial evidence. */
            if(p->sid==0x22 && n==h+3){e.classification="incomplete_response";continue;}
        }
        match=p;++e.candidates;
    }
    if(e.candidates==1 && !e.incomplete){
        e.sequence=match->sequence;e.filter_id=match->filter_id;e.elapsed_ms=now-match->ms;
        e.relation="filter_time_service_candidate";
        if(!pending)match->active=0;
    }else if(e.candidates>1)e.relation="ambiguous_requests";
    if(e.incomplete)e.relation="filter_state_incomplete";
    emit(o,&e);
}
