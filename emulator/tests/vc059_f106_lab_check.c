#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "vc054_f106_lab.h"
static unsigned int tests=0;
#define CHECK(x) do {assert(x);tests++;}while(0)
static void tohex(const unsigned char *b,char *h){unsigned int i;for(i=0;i<142;i++)sprintf(h+2*i,"%02X",b[i]);}
static int untouched(const unsigned char *b,unsigned int n){unsigned int i;for(i=0;i<n;i++)if(b[i]!=0xa5)return 0;return 1;}
int main(void){
    VC054_F106 s={0}; unsigned char b[142]={0x8c,0},out[256],req[4]={0x22,0xf1,6,0};char h[286];unsigned int i,sum=0;
    for(i=2;i<142;i++){b[i]=(unsigned char)(i*17u+3u);sum+=b[i];}b[1]=(unsigned char)sum;tohex(b,h);
    memset(out,0xa5,sizeof(out));
    CHECK(vc054_answer(&s,req,3,out,sizeof(out))==0 && untouched(out,sizeof(out)));
    CHECK(!vc054_load(&s,"0","donor-142",h)&&!s.enabled);
    CHECK(!vc054_load(&s,"01","donor-142",h)&&!s.enabled);
    CHECK(!vc054_load(&s,"1","metadata-130",h)&&!s.enabled);
    CHECK(vc054_load(&s,"1","donor-142",h)&&s.enabled);
    CHECK(vc054_answer(&s,req,3,out,sizeof(out))==145 && out[0]==0x62 && out[1]==0xf1 && out[2]==6 && !memcmp(out+3,b,142) && untouched(out+145,111));
    memset(out,0xa5,sizeof(out));
    CHECK(!vc054_answer(&s,req,2,out,sizeof(out)) && untouched(out,sizeof(out)));
    CHECK(!vc054_answer(&s,req,4,out,sizeof(out)) && untouched(out,sizeof(out)));
    CHECK(!vc054_answer(&s,req,3,out,144) && untouched(out,sizeof(out)));
    req[2]=7;CHECK(!vc054_answer(&s,req,3,out,sizeof(out)) && untouched(out,sizeof(out)));req[2]=6;
    req[0]=0x2e;CHECK(!vc054_answer(&s,req,3,out,sizeof(out)) && untouched(out,sizeof(out)));req[0]=0x22;
    CHECK(!vc054_answer(&s,NULL,3,out,sizeof(out)) && !vc054_answer(&s,req,3,NULL,sizeof(out)));
    s.block[25]^=1;CHECK(!vc054_answer(&s,req,3,out,sizeof(out)) && untouched(out,sizeof(out)));
    h[260]=0;CHECK(!vc054_load(&s,"1","donor-142",h)&&!s.enabled&&s.block[0]==0);tohex(b,h);
    h[284]='0';h[285]=0;CHECK(!vc054_load(&s,"1","donor-142",h)&&!s.enabled);tohex(b,h);
    h[9]='G';CHECK(!vc054_load(&s,"1","donor-142",h)&&!s.enabled);tohex(b,h);
    h[0]='9';CHECK(!vc054_load(&s,"1","donor-142",h)&&!s.enabled);tohex(b,h);
    h[2]=h[2]=='0'?'1':'0';CHECK(!vc054_load(&s,"1","donor-142",h)&&!s.enabled);tohex(b,h);
    CHECK(vc054_load(&s,"1","donor-142",h));vc054_clear(&s);CHECK(!s.enabled && !vc054_answer(&s,req,3,out,sizeof(out)) && untouched(out,sizeof(out)));
    printf("VC054_C_CHECKS=%u PASS\n",tests);return 0;
}
