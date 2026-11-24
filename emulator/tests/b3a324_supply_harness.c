#include <stdint.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
typedef uint32_t U32;
typedef uint8_t U8;
#include "helper.c"
int main(void){
    const U32 mv[]={12500,10500,14200,14000,14000};
    const U32 expected[3][5]={{0x8000,0x6b85,0x9168,0x8f5c,0x8f5c},{0x0320,0x02a0,0x038d,0x0380,0x0380},{0x32,0x2a,0x39,0x38,0x38}};
    U8 reqs[2][8]={{0xcd,0x46,0xa6,0x1a,0x02,1,0,0},{0xcd,0x29,0xa6,0x00,0x80,1,0,0}};
    U8 frames[2][8],orig[2][8],want[2][8];
    U32 i,j,k,x;
    for(i=0;i<2;i++){
        U8 *req=reqs[i];
        memset(orig,0,sizeof orig);memcpy(orig[0],req,5);orig[0][2]=0xe6;
        orig[0][5]=(U8)(expected[i][0]>>8);orig[0][6]=(U8)expected[i][0];orig[1][7]=0xaa;
        for(k=0;k<5;k++){
            memcpy(frames,orig,sizeof frames);memcpy(want,orig,sizeof want);
            want[0][5]=(U8)(expected[i][k]>>8);want[0][6]=(U8)expected[i][k];
            lab_supply_voltage_sync(1,mv[k],req,8,1,frames);assert(!memcmp(frames,want,sizeof frames));
            memcpy(frames,orig,sizeof frames);lab_supply_voltage_sync(0,mv[k],req,8,1,frames);assert(!memcmp(frames,orig,sizeof frames));
        }
        for(j=0;j<8;j++)for(x=0;x<256;x++){U8 save=req[j];if(x==save)continue;req[j]=(U8)x;memcpy(frames,orig,sizeof frames);lab_supply_voltage_sync(1,14000,req,8,1,frames);assert(!memcmp(frames,orig,sizeof frames));req[j]=save;}
        for(j=0;j<5;j++){memcpy(frames,orig,sizeof frames);frames[0][j]^=1;memcpy(want,frames,sizeof want);lab_supply_voltage_sync(1,14000,req,8,1,frames);assert(!memcmp(frames,want,sizeof frames));}
        memcpy(frames,orig,sizeof frames);lab_supply_voltage_sync(1,14000,req,7,1,frames);lab_supply_voltage_sync(1,14000,req,8,2,frames);lab_supply_voltage_sync(1,20001,req,8,1,frames);lab_supply_voltage_sync(2,14000,req,8,1,frames);lab_supply_voltage_sync(1,14000,0,8,1,frames);lab_supply_voltage_sync(1,14000,req,8,1,0);assert(!memcmp(frames,orig,sizeof frames));
    }
    for(k=0;k<5;k++){assert(lab_cem_voltage_byte(1,mv[k])==expected[2][k]);assert(lab_cem_voltage_byte(0,mv[k])==0x32);}
    assert(lab_cem_voltage_byte(1,20001)==0x32&&lab_cem_voltage_byte(2,14000)==0x32);
    for(x=0;x<=20000;x++){
        int64_t a=(int64_t)lab_voltage_raw(1,x)*25000-(int64_t)x*65535;
        int64_t b=(int64_t)lab_voltage_raw(2,x)*1000-(int64_t)x*64;
        int64_t c=(int64_t)lab_cem_voltage_byte(1,x)*250-x;
        assert(a>=-12500&&a<=12500&&b>=-500&&b<=500&&c>=-125&&c<=125);
    }
    puts("B3A324_SUPPLY_SYNC_PASS");return 0;
}
