#include <stdint.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
typedef uint32_t U32;
typedef uint8_t U8;
#include "model.c"
static void check(const ECM_LAB_STATE *s,U32 group,U32 did,U32 n,U32 raw){
    U8 b[5];U32 i,v=0;memset(b,0xcc,sizeof(b));
    assert(ecm_lab_encode(s,group,did,b)==n);
    for(i=0;i<n;i++)v=(v<<8)|b[i];
    assert(v==raw && b[n]==0xcc);
}
int main(void){
    ECM_LAB_STATE s=g_ecm_lab_state;
    const U32 cases[][4]={{0,0x120d,2,0xa000},{0,0xd998,1,0x60},{0,0xd99b,1,0x60},{0,0xda48,4,0},{0,0xf40c,2,0},{0,0xf40d,1,0},{0,0xf40f,1,0x3c},{1,0xd9ac,2,0},{1,0xd9ad,2,0},{1,0xd9b8,1,0x60},{1,0xf404,1,0},{1,0xf405,1,0x3c},{1,0xf410,2,0},{1,0xf433,1,100},{1,0xf449,1,0},{1,0xf44a,1,0},{1,0xf40b,1,100},{1,0xd9a4,1,200},{1,0xda47,2,0x3333}};
    U32 i;U8 b[4]={0xcc,0xcc,0xcc,0xcc};
    for(i=0;i<19;i++){check(&s,cases[i][0],cases[i][1],cases[i][2],cases[i][3]);assert(ecm_lab_encode(&s,1u-cases[i][0],cases[i][1],b)==0 && b[0]==0xcc);}
    s.rpm=800;s.battery_mv=14000;s.coolant_c=90;s.intake_c=30;s.ecm_c=45;s.speed_kph=50;s.pedal_permille=200;s.load_permille=400;s.maf_centi_gps=550;s.ambient_kpa=98;s.manifold_kpa=35;
    check(&s,0,0xda48,4,0x44480000);check(&s,0,0xf40c,2,3200);check(&s,0,0x120d,2,45875);check(&s,0,0xf40d,1,50);
    check(&s,0,0xd99b,1,208);check(&s,1,0xf405,1,130);check(&s,0,0xd998,1,112);check(&s,0,0xf40f,1,70);check(&s,1,0xd9b8,1,136);
    check(&s,1,0xd9ac,2,200);check(&s,1,0xd9ad,2,200);check(&s,1,0xf449,1,51);check(&s,1,0xf44a,1,51);check(&s,1,0xf404,1,102);check(&s,1,0xf410,2,550);
    check(&s,1,0xf433,1,98);check(&s,1,0xd9a4,1,196);check(&s,1,0xf40b,1,35);check(&s,1,0xda47,2,4588);
    s.battery_mv=20000;check(&s,0,0x120d,2,65535);s.battery_mv=20001;assert(!ecm_lab_encode(&s,0,0x120d,b));s.battery_mv=14000;
    s.coolant_c=-40;check(&s,0,0xd99b,1,0);s.coolant_c=119;check(&s,0,0xd99b,1,254);s.coolant_c=120;assert(!ecm_lab_encode(&s,0,0xd99b,b));s.coolant_c=-41;assert(!ecm_lab_encode(&s,0,0xd99b,b));s.coolant_c=90;
    s.rpm=16383;check(&s,0,0xf40c,2,65532);s.rpm=16384;assert(!ecm_lab_encode(&s,0,0xda48,b));s.rpm=800;
    assert(!ecm_lab_encode(&s,0,0x1234,b)&&!ecm_lab_encode(0,0,0x120d,b)&&!ecm_lab_encode(&s,0,0x120d,0)&&b[0]==0xcc);
    puts("B3A315_MODEL_PASS");return 0;
}
