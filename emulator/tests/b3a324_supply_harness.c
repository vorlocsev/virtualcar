#include <stdint.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
typedef uint32_t U32;
typedef uint8_t U8;
#include "helper.c"
int main(void){
    const U32 mv[]={12500,10500,14200,14000,14000};
    const U32 raw[3][5]={{0x8000,0x6b85,0x9168,0x8f5c,0x8f5c},{0x0320,0x02a0,0x038d,0x0380,0x0380},{0x32,0x2a,0x39,0x38,0x38}};
    U8 req[2][8]={{0xcd,0x46,0xa6,0x1a,2,1,0,0},{0xcd,0x29,0xa6,0,0x80,1,0,0}};
    U8 f[1][8],orig[1][8],want[1][8];
    for(U32 i=0;i<2;i++){
        memcpy(orig[0],req[i],8);orig[0][2]=0xe6;orig[0][5]=(U8)(raw[i][0]>>8);orig[0][6]=(U8)raw[i][0];orig[0][7]=0xaa;
        for(U32 k=0;k<5;k++){
            memcpy(f,orig,8);memcpy(want,orig,8);want[0][5]=(U8)(raw[i][k]>>8);want[0][6]=(U8)raw[i][k];
            lab_supply_voltage_sync(1,mv[k],req[i],8,1,f);assert(!memcmp(f,want,8));
            memcpy(f,orig,8);lab_supply_voltage_sync(0,mv[k],req[i],8,1,f);assert(!memcmp(f,orig,8));
        }
        for(U32 j=0;j<8;j++)for(U32 x=0;x<256;x++){
            U8 save=req[i][j];if(x==save)continue;req[i][j]=(U8)x;memcpy(f,orig,8);
            lab_supply_voltage_sync(1,14000,req[i],8,1,f);assert(!memcmp(f,orig,8));req[i][j]=save;
        }
    }
    for(U32 k=0;k<5;k++){assert(lab_cem_voltage_byte(1,mv[k])==raw[2][k]);assert(lab_cem_voltage_byte(0,mv[k])==0x32);}
    for(U32 x=0;x<=20000;x++){
        int64_t a=(int64_t)lab_voltage_raw(1,x)*25000-(int64_t)x*65535;
        int64_t b=(int64_t)lab_voltage_raw(2,x)*1000-(int64_t)x*64;
        int64_t c=(int64_t)lab_cem_voltage_byte(1,x)*250-x;
        assert(a>=-12500&&a<=12500&&b>=-500&&b<=500&&c>=-125&&c<=125);
    }
    puts("B3A324_SUPPLY_SYNC_PASS");return 0;
}
