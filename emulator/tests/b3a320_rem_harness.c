#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
typedef uint32_t U32;
typedef uint8_t U8;
#include "helper.c"
int main(void){
    U8 req[8]={0xCD,0x46,0xA6,0xD0,0xD4,1,0,0};
    U8 frames[2][8]={{0xCD,0x46,0xE6,0xD0,0xD4,0x64,0,0},{1,2,3,4,5,6,7,8}};
    U8 orig[2][8],expected[2][8];
    const U32 mv[]={12500,10500,14200,14000,14000};
    const U8 raw[]={0x64,0x54,0x72,0x70,0x70};
    U32 i,j;
    memcpy(orig,frames,sizeof frames);
    for(i=0;i<5;i++){
        memcpy(frames,orig,sizeof frames);memcpy(expected,orig,sizeof expected);expected[0][5]=raw[i];
        lab_rem_voltage_sync(1,mv[i],req,8,1,frames);assert(!memcmp(frames,expected,sizeof frames));
        memcpy(frames,orig,sizeof frames);lab_rem_voltage_sync(0,mv[i],req,8,1,frames);assert(!memcmp(frames,orig,sizeof frames));
    }
    for(i=0;i<=20000;i++){
        int err;memcpy(frames,orig,sizeof frames);lab_rem_voltage_sync(1,i,req,8,1,frames);
        err=(int)frames[0][5]*125-(int)i;assert(err>=-62&&err<=62);
    }
    for(i=0;i<8;i++){for(j=0;j<256;j++){U8 save=req[i];if(j==save)continue;req[i]=(U8)j;memcpy(frames,orig,sizeof frames);lab_rem_voltage_sync(1,14000,req,8,1,frames);assert(!memcmp(frames,orig,sizeof frames));req[i]=save;}}
    for(i=0;i<5;i++){memcpy(frames,orig,sizeof frames);frames[0][i]^=1;memcpy(expected,frames,sizeof frames);lab_rem_voltage_sync(1,14000,req,8,1,frames);assert(!memcmp(frames,expected,sizeof frames));}
    memcpy(frames,orig,sizeof frames);lab_rem_voltage_sync(1,20001,req,8,1,frames);lab_rem_voltage_sync(1,14000,req,7,1,frames);lab_rem_voltage_sync(1,14000,req,8,2,frames);lab_rem_voltage_sync(2,14000,req,8,1,frames);lab_rem_voltage_sync(1,14000,0,8,1,frames);lab_rem_voltage_sync(1,14000,req,8,1,0);assert(!memcmp(frames,orig,sizeof frames));
    puts("B3A320_REM_SYNC_PASS");return 0;
}
