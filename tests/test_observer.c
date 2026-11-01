/* All fixtures in this file are synthetic. */
#include "j2534_observer.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static vc_observer o;
static vc_event events[2048];
static unsigned count,groups;
static vc_message mask,pattern,flow,tx,rx;
static void capture(void *ctx,const vc_event *e){(void)ctx;assert(count<2048);events[count++]=*e;}
static vc_event *last(void){assert(count);return &events[count-1];}
static void id(vc_message *m,uint32_t v){m->Data[0]=(uint8_t)(v>>24);m->Data[1]=(uint8_t)(v>>16);m->Data[2]=(uint8_t)(v>>8);m->Data[3]=(uint8_t)v;}
static void setup(void){
    count=0;vc_init(&o,capture,0);vc_connect(&o,1,10,6,500000,0);
    memset(&mask,0,sizeof(mask));mask.ProtocolID=6;mask.DataSize=4;id(&mask,0xFFFFFFFFu);
    pattern=mask;id(&pattern,0x18DAF150);flow=mask;id(&flow,0x18DA50F1);
    vc_filter_start(&o,10,3,&mask,&pattern,&flow,7,0,1);
    tx=flow;tx.DataSize=7;tx.Data[4]=0x22;tx.Data[5]=0xF1;tx.Data[6]=0x90;
    rx=pattern;rx.DataSize=8;rx.Data[4]=0x62;rx.Data[5]=0xF1;rx.Data[6]=0x90;rx.Data[7]=0xAB;
}
int main(void){
    unsigned i;uint32_t seq;
    /* 1. ISO15765 ID, service, identifier and time candidate; NRC78 stays open. */
    setup();vc_tx(&o,10,&tx,100);seq=last()->sequence;
    assert(seq && last()->active_filters==1 && !strcmp(last()->classification,"uds_read_data_identifier"));
    rx.Data[4]=0x7F;rx.Data[5]=0x22;rx.Data[6]=0x78;rx.DataSize=7;
    vc_rx(&o,10,&rx,120);assert(last()->sequence==seq && last()->elapsed_ms==20);
    assert(!strcmp(last()->classification,"negative_response_pending"));
    rx.Data[4]=0x62;rx.Data[5]=0xF1;rx.Data[6]=0x90;rx.DataSize=7;
    vc_rx(&o,10,&rx,130);assert(!last()->sequence && !strcmp(last()->classification,"incomplete_response"));
    rx.DataSize=8;vc_rx(&o,10,&rx,140);assert(last()->sequence==seq && last()->elapsed_ms==40);
    vc_rx(&o,10,&rx,141);assert(!last()->sequence);++groups;
    /* 2. Failed filter operations preserve state; stop/clear report observed wait. */
    setup();vc_tx(&o,10,&tx,10);vc_filter_stop(&o,10,7,7,20);assert(last()->active_filters==1);
    vc_ioctl(&o,10,10,7,21);assert(o.filters[0].active);
    vc_filter_stop(&o,10,7,0,1050);assert(!strcmp(events[count-2].relation,"filter_stopped_no_final_rx"));
    assert(events[count-2].elapsed_ms==1040 && last()->active_filters==0);
    vc_filter_start(&o,10,1,&mask,&pattern,0,8,0,1051);assert(last()->active_filters==1);
    vc_filter_start(&o,10,2,&mask,&pattern,0,9,0,1052);assert(last()->active_filters==2);
    vc_filter_start(&o,10,3,&mask,&pattern,&flow,10,7,1053);assert(last()->active_filters==2);
    vc_ioctl(&o,10,10,0,1054);assert(last()->active_filters==0);++groups;
    /* 3. Channel/device scope, reuse, baud and protocol are never inferred. */
    setup();vc_connect(&o,2,11,6,125000,0);vc_tx(&o,10,&tx,10);
    vc_rx(&o,11,&rx,20);assert(!last()->sequence && last()->baud==125000);
    vc_close(&o,2,21);assert(o.channels[0].active && !o.channels[1].active);
    vc_connect(&o,1,10,6,250000,22);vc_rx(&o,10,&rx,23);
    assert(!last()->sequence && last()->active_filters==0 && last()->generation==3);
    vc_connect(&o,1,10,5,500000,24);i=count;vc_tx(&o,10,&tx,25);vc_rx(&o,10,&rx,26);assert(i==count);
    vc_disconnect(&o,10,27);vc_tx(&o,10,&tx,28);assert(i==count);++groups;
    /* 4. Duplicate outstanding requests/filters remain ambiguous, never latest-wins. */
    setup();vc_tx(&o,10,&tx,100);vc_tx(&o,10,&tx,110);vc_rx(&o,10,&rx,120);
    assert(last()->candidates==2 && !last()->sequence && !strcmp(last()->relation,"ambiguous_requests"));
    vc_filter_start(&o,10,3,&mask,&pattern,&flow,8,0,130);vc_tx(&o,10,&tx,140);
    assert(last()->candidates==2 && !last()->sequence && !strcmp(last()->relation,"ambiguous_flow_filters"));++groups;
    /* 5. Indications, malformed messages, wrong SID/DID/ID, extra data boundary. */
    setup();vc_tx(&o,10,&tx,100);seq=last()->sequence;
    for(i=0;i<3;i++){rx.RxStatus=i==0?1:i==1?8:2;vc_rx(&o,10,&rx,101+i);assert(!last()->sequence);}
    rx.RxStatus=0;rx.Data[6]=0x91;vc_rx(&o,10,&rx,104);assert(!last()->sequence);
    rx.Data[6]=0x90;id(&rx,0x18DAF151);vc_rx(&o,10,&rx,105);assert(!last()->sequence);
    id(&rx,0x18DAF150);rx.ExtraDataIndex=7;vc_rx(&o,10,&rx,106);assert(!last()->sequence);
    rx.ExtraDataIndex=99;vc_rx(&o,10,&rx,107);assert(!strcmp(last()->classification,"invalid_metadata"));
    rx.ExtraDataIndex=0;rx.ProtocolID=5;vc_rx(&o,10,&rx,108);assert(!last()->sequence);
    rx.ProtocolID=6;rx.DataSize=4129;vc_rx(&o,10,&rx,109);assert(!last()->sequence);
    rx.DataSize=8;vc_rx(&o,10,&rx,110);assert(last()->sequence==seq);++groups;
    /* 6. Standard vs extended CAN format and ISO15765 extended addressing. */
    setup();id(&pattern,0x7E8);id(&flow,0x7E0);pattern.TxFlags=0x100;
    vc_filter_start(&o,10,3,&mask,&pattern,&flow,7,0,1);id(&tx,0x7E0);id(&rx,0x7E8);
    vc_tx(&o,10,&tx,10);vc_rx(&o,10,&rx,11);assert(!last()->sequence);
    rx.RxStatus=0x100;vc_rx(&o,10,&rx,12);assert(last()->sequence);
    setup();mask.DataSize=pattern.DataSize=flow.DataSize=5;mask.Data[4]=0xFF;
    pattern.TxFlags=flow.TxFlags=0x80;pattern.Data[4]=0xF1;flow.Data[4]=0x50;
    vc_filter_start(&o,10,3,&mask,&pattern,&flow,7,0,1);
    tx=flow;tx.DataSize=8;tx.Data[5]=0x22;tx.Data[6]=0xF1;tx.Data[7]=0x90;
    rx=pattern;rx.RxStatus=0x80;rx.DataSize=9;rx.Data[5]=0x62;rx.Data[6]=0xF1;rx.Data[7]=0x90;rx.Data[8]=1;
    vc_tx(&o,10,&tx,10);assert(last()->sequence);
    rx.Data[4]=0xF2;vc_rx(&o,10,&rx,11);assert(!last()->sequence);
    rx.Data[4]=0xF1;vc_rx(&o,10,&rx,12);assert(last()->sequence);++groups;
    /* 7. Host clock wrap, expiry, RX clear and final negative response. */
    setup();vc_tx(&o,10,&tx,0xFFFFFFF0u);vc_rx(&o,10,&rx,20);assert(last()->elapsed_ms==36);
    vc_tx(&o,10,&tx,100);vc_rx(&o,10,&rx,5101);assert(!last()->sequence);
    assert(!strcmp(events[count-2].relation,"window_elapsed_no_final_rx"));
    vc_tx(&o,10,&tx,5200);vc_ioctl(&o,10,8,0,5201);assert(last()->active_filters==1);
    vc_rx(&o,10,&rx,5202);assert(!last()->sequence);
    vc_tx(&o,10,&tx,5300);rx.Data[4]=0x7F;rx.Data[5]=0x22;rx.Data[6]=0x31;rx.DataSize=7;
    vc_rx(&o,10,&rx,5301);assert(last()->sequence && !strcmp(last()->classification,"negative_response"));++groups;
    /* 8. Capacity never overwrites live state or manufactures a unique pair. */
    setup();for(i=1;i<VC_FILTERS;i++)vc_filter_start(&o,10,1,&mask,&pattern,0,100+i,0,2);
    vc_filter_start(&o,10,1,&mask,&pattern,0,999,0,3);assert(last()->incomplete && last()->active_filters==VC_FILTERS);
    vc_tx(&o,10,&tx,4);assert(!last()->sequence);
    vc_ioctl(&o,10,10,0,5);assert(!last()->incomplete && !last()->active_filters);
    setup();for(i=0;i<VC_PENDING+1;i++)vc_tx(&o,10,&tx,100+i);
    assert(last()->incomplete && !last()->sequence);vc_rx(&o,10,&rx,300);assert(!last()->sequence);
    setup();for(i=1;i<VC_CHANNELS;i++)vc_connect(&o,1,10+i,6,500000,0);
    vc_connect(&o,1,999,6,500000,0);assert(!strcmp(last()->event,"observer_capacity"));++groups;
    printf("dev46: %u/8 observer groups OK\n",groups);return groups==8?0:1;
}
