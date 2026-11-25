#ifndef VC054_F106_LAB_H
#define VC054_F106_LAB_H
/* Virtual-only PDU helper. No transport, hardware, writes or security access.
 * Donor-142 is a lab format, not a verified MY2009 ECU response. */
#define VC054_BLOCK_LEN 142u
#define VC054_PDU_LEN 145u
typedef struct { unsigned int enabled; unsigned char block[VC054_BLOCK_LEN]; } VC054_F106;
static void vc054_clear(VC054_F106 *s) {
    unsigned int i;
    if (!s) return;
    s->enabled=0;
    for(i=0;i<VC054_BLOCK_LEN;i++) s->block[i]=0;
}
static int vc054_literal(const char *a,const char *b) {
    if(!a||!b) return 0;
    while(*a && *a==*b){a++;b++;}
    return *a==0 && *b==0;
}
static int vc054_nibble(char c) {
    if(c>='0'&&c<='9')return c-'0';
    if(c>='A'&&c<='F')return c-'A'+10;
    if(c>='a'&&c<='f')return c-'a'+10;
    return -1;
}
static int vc054_valid(const unsigned char *b,unsigned int n) {
    unsigned int i,sum=0;
    if(!b||n!=VC054_BLOCK_LEN||b[0]!=0x8c)return 0;
    for(i=2;i<n;i++)sum+=b[i];
    return b[1]==(unsigned char)(sum&255u);
}
/* The caller supplies a bounded, NUL-terminated INI value. Exactly 284 hex digits. */
static int vc054_load(VC054_F106 *s,const char *enabled,const char *layout,const char *hex) {
    unsigned int i,n=0; int hi,lo;
    if(!s)return 0;
    vc054_clear(s);
    if(!vc054_literal(enabled,"1")||!vc054_literal(layout,"donor-142")||!hex)return 0;
    while(n<=2u*VC054_BLOCK_LEN && hex[n])n++;
    if(n!=2u*VC054_BLOCK_LEN)return 0;
    for(i=0;i<VC054_BLOCK_LEN;i++){
        hi=vc054_nibble(hex[2u*i]);lo=vc054_nibble(hex[2u*i+1u]);
        if(hi<0||lo<0){vc054_clear(s);return 0;}
        s->block[i]=(unsigned char)((hi<<4)|lo);
    }
    if(!vc054_valid(s->block,VC054_BLOCK_LEN)){vc054_clear(s);return 0;}
    s->enabled=1;return 1;
}
/* Only called after the existing exact physical GGD route guard succeeds.
 * Returns 0 (silence) without modifying output on every rejected input. */
static unsigned int vc054_answer(const VC054_F106 *s,const unsigned char *req,unsigned int n,
                                  unsigned char *out,unsigned int cap) {
    unsigned int i;
    if(!s||s->enabled!=1u||!req||n!=3u||!out||cap<VC054_PDU_LEN||
       req[0]!=0x22||req[1]!=0xf1||req[2]!=0x06||!vc054_valid(s->block,VC054_BLOCK_LEN))return 0;
    out[0]=0x62;out[1]=0xf1;out[2]=0x06;
    for(i=0;i<VC054_BLOCK_LEN;i++)out[i+3u]=s->block[i];
    return VC054_PDU_LEN;
}
#endif
