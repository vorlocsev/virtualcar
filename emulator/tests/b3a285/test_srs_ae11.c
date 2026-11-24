#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef unsigned int U32; typedef unsigned char U8;
#define CAN_29BIT_ID 0x100u
typedef struct {U8 target,subcommand,lab_empty_dtc; U32 frame_count,response_id,baud;} D2_PROFILE;
static int lab_d2_empty_reply(const D2_PROFILE *d,const U8 *data,U32 len,U32 baud,U32 flags,U32 tx_flags,U8 *reply){
    U32 j;
    if(!d->lab_empty_dtc || !d->frame_count || d->subcommand!=0xF0u || d->target==0x40u || d->target==0x50u || d->response_id>0x1FFFFFFFu || len!=8u || data[0]!=0xCBu || data[1]!=d->target || data[2]!=0xAEu || (data[3]!=0x1Bu && !(d->target==0x58u && data[3]==0x11u)) || baud!=d->baud || !(flags&CAN_29BIT_ID) || !(tx_flags&CAN_29BIT_ID))return 0;
    for(j=4;j<8;j++)if(data[j])return 0;
    reply[0]=0xCBu;reply[1]=d->target;reply[2]=0xEEu;reply[3]=data[3];
    for(j=4;j<8;j++)reply[j]=0;
    return 1;
}

int main(void){
 D2_PROFILE d={0x58,0xF0,1,3,0x00800003,125000}; U8 q[8]={0xCB,0x58,0xAE,0x11,0,0,0,0},r[8];
 const U8 expected[]={0xCB,0x58,0xEE,0x11,0,0,0,0};
 assert(lab_d2_empty_reply(&d,q,8,125000,256,256,r)&&!memcmp(r,expected,8));
 q[3]=0x1B; assert(lab_d2_empty_reply(&d,q,8,125000,256,256,r)&&r[3]==0x1B);q[3]=0x11;
 q[4]=1;assert(!lab_d2_empty_reply(&d,q,8,125000,256,256,r));q[4]=0;
 assert(!lab_d2_empty_reply(&d,q,7,125000,256,256,r));
 assert(!lab_d2_empty_reply(&d,q,8,500000,256,256,r));
 assert(!lab_d2_empty_reply(&d,q,8,125000,0,256,r));
 assert(!lab_d2_empty_reply(&d,q,8,125000,256,0,r));
 d.lab_empty_dtc=0;assert(!lab_d2_empty_reply(&d,q,8,125000,256,256,r));d.lab_empty_dtc=1;
 d.frame_count=0;assert(!lab_d2_empty_reply(&d,q,8,125000,256,256,r));d.frame_count=3;
 q[3]=0x18;assert(!lab_d2_empty_reply(&d,q,8,125000,256,256,r));q[3]=0x11;
 d.target=q[1]=0x51;assert(!lab_d2_empty_reply(&d,q,8,125000,256,256,r));
 q[3]=0x1B;assert(lab_d2_empty_reply(&d,q,8,125000,256,256,r)&&r[1]==0x51&&r[3]==0x1B);
 puts("B3A277_HELPER=12/12_PASS");return 0;
}
