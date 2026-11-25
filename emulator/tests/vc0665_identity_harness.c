#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "vc054_f106_lab.h"
#include "vc0662_f110.h"
#include "vc0663_identity.h"
typedef unsigned int U32;
typedef unsigned char U8;
typedef struct {U32 api_protocol,protocol,baud,flags;} CHANNEL;
typedef struct {U32 req,resp,expected_baud;} ECU;
#define PROTO_ISO15765 6u
#define CAN_29BIT_ID 0x100u
static U32 g_b3a150_ggd_cem_lab=1,g_b3a157_posii_candidate=0,g_b3a324_supply_sync=0,g_battery_mv=12500;
static U32 g_vc0662_f110=1,g_vc0663_identity=0;
static VC054_F106 g_vc054_f106;
static void logline(const char *s,const U8 *b,U32 n){(void)s;(void)b;(void)n;}
static U8 lab_cem_voltage_byte(U32 a,U32 b){(void)a;(void)b;return 0x32;}
#include "route_under_test.h"
static U32 tests=0;
#define CHECK(x) do{assert(x);tests++;}while(0)
static int intact(const U8 *p,U32 n){U32 i;for(i=0;i<n;i++)if(p[i]!=0xa5)return 0;return 1;}
int main(void){
    const U8 dids[]={0x91,0x88,0x8c,0x20};
    const char *values[]={"LAB-CEM-HW-0001         ","LAB-CEM-SW-0001         ","LAB-CEM-SN-0001 ","LAB-CEM-EXTRA-0001      "};
    const U32 widths[]={24,24,16,24};
    CHANNEL c={6,6,500000,0x100};ECU e={0x18da50f1,0x18daf150,500000};
    U8 q[4]={0x22,0xf1,0,0},out[256];U32 i,w;char h[285];
#define RUN() answer_b3a150_ggd_cem50_lab(&c,&e,0x18da50f1,0x100,q,3,out)
    CHECK(vc0662_f110_enabled("1") && !vc0662_f110_enabled("01") && !vc0662_f110_enabled(NULL));
    for(i=0;i<4;i++){
        q[2]=dids[i];w=widths[i];g_vc0663_identity=0;memset(out,0xa5,sizeof(out));
        CHECK(RUN()==0 && intact(out,sizeof(out)));
        g_vc0663_identity=1;
        CHECK(RUN()==w+3 && out[0]==0x62 && out[1]==0xf1 && out[2]==dids[i] && !memcmp(out+3,values[i],w) && intact(out+w+3,sizeof(out)-w-3));
        memset(out,0xa5,sizeof(out));
        CHECK(vc0663_identity_answer(1,q,3,out,w+2)==0 && intact(out,sizeof(out)));
        CHECK(vc0663_identity_answer(2,q,3,out,sizeof(out))==0 && intact(out,sizeof(out)));
        CHECK(vc0663_identity_answer(1,q,2,out,sizeof(out))==0 && intact(out,sizeof(out)));
        CHECK(vc0663_identity_answer(1,q,4,out,sizeof(out))==0 && intact(out,sizeof(out)));
        CHECK(vc0663_identity_answer(1,NULL,3,out,sizeof(out))==0 && intact(out,sizeof(out)));
        CHECK(vc0663_identity_answer(1,q,3,NULL,sizeof(out))==0);
        CHECK(answer_b3a150_ggd_cem50_lab(&c,&e,0x18da51f1,0x100,q,3,out)==0 && intact(out,sizeof(out)));
        c.baud=125000;CHECK(RUN()==0 && intact(out,sizeof(out)));c.baud=500000;
        c.api_protocol=0x8005;CHECK(RUN()==0 && intact(out,sizeof(out)));c.api_protocol=6;
        c.protocol=5;CHECK(RUN()==0 && intact(out,sizeof(out)));c.protocol=6;
        c.flags=0;CHECK(RUN()==0 && intact(out,sizeof(out)));c.flags=0x100;
        CHECK(answer_b3a150_ggd_cem50_lab(&c,&e,0x18da50f1,0,q,3,out)==0 && intact(out,sizeof(out)));
        CHECK(answer_b3a150_ggd_cem50_lab(&c,&e,0x18da50f1,0x140,q,3,out)==w+3);
        g_b3a150_ggd_cem_lab=0;CHECK(RUN()==0);g_b3a150_ggd_cem_lab=1;
        e.resp=0x18daf151;CHECK(RUN()==0);e.resp=0x18daf150;
    }
    q[2]=0x10;CHECK(RUN()==27 && !memcmp(out+3,"30682825  A             ",24));
    g_vc0663_identity=0;CHECK(RUN()==27);g_vc0663_identity=1;
    for(i=0;i<142;i++)sprintf(h+i*2,"%02X",i==0?0x8c:0);
    CHECK(vc054_load(&g_vc054_f106,"1","donor-142",h));q[2]=6;CHECK(RUN()==145);
    q[1]=0xa4;q[2]=0x5f;CHECK(RUN()==4 && out[3]==4);
    q[1]=0xdd;q[2]=2;CHECK(RUN()==4 && out[3]==0x32);
    q[1]=0xf1;q[2]=0x07;CHECK(RUN()==0);
    q[0]=0x2e;q[2]=0x91;CHECK(RUN()==0);
    q[0]=0x22;q[1]=0xf2;CHECK(RUN()==0);
    printf("VC0663_C_CHECKS=%u PASS\n",tests);return 0;
}
