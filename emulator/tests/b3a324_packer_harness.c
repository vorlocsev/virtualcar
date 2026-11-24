#include <stdint.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
typedef uint32_t U32;
typedef uint8_t U8;
#include "packer.c"
#include "helper.c"
int main(void){
    const U32 mv[]={12500,10500,14200,14000,14000};
    const U32 raw[2][5]={{0x8000,0x6b85,0x9168,0x8f5c,0x8f5c},{0x0320,0x02a0,0x038d,0x0380,0x0380}};
    const U8 cem[]={0x32,0x2a,0x39,0x38,0x38};
    U8 frames[MAX_D2_FRAMES][8],want[MAX_D2_FRAMES][8],before[MAX_D2_FRAMES][8];
    U32 i,k,n,targets=0;
    for(i=0;i<sizeof(lab_current_routes)/sizeof(lab_current_routes[0]);i++){
        const U8 *q=lab_current_routes[i].req;
        int kind=-1;
        if(q[1]==0x46 && q[2]==0xa6 && q[3]==0x1a && q[4]==2)kind=0;
        if(q[1]==0x29 && q[2]==0xa6 && q[3]==0 && q[4]==0x80)kind=1;
        if(kind>=0)targets++;
        for(k=0;k<5;k++){
            memset(frames,0xa5,sizeof frames);
            n=lab_current_frames(q,8,125000,0x100,0x100,frames);assert(n>0);
            memcpy(before,frames,sizeof frames);memcpy(want,frames,sizeof frames);
            if(kind>=0){assert(n==1 && frames[0][0]==0xce);want[0][5]=(U8)(raw[kind][k]>>8);want[0][6]=(U8)raw[kind][k];}
            lab_supply_voltage_sync(1,mv[k],q,8,n,frames);assert(!memcmp(frames,want,sizeof frames));
            memcpy(frames,before,sizeof frames);lab_supply_voltage_sync(0,mv[k],q,8,n,frames);assert(!memcmp(frames,before,sizeof frames));
        }
        memset(frames,0xa5,sizeof frames);memcpy(before,frames,sizeof frames);
        n=lab_current_frames(q,8,500000,0x100,0x100,frames);assert(n==0);
        lab_supply_voltage_sync(1,14000,q,8,n,frames);assert(!memcmp(frames,before,sizeof frames));
    }
    assert(targets==2);
    for(k=0;k<5;k++)assert(lab_cem_voltage_byte(1,mv[k])==cem[k]);
    printf("B3A324_R2_PACKER_PASS routes=%u targets=%u\n",(unsigned)(sizeof(lab_current_routes)/sizeof(lab_current_routes[0])),targets);
    return 0;
}
