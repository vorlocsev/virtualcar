#ifndef VC0662_F110_H
#define VC0662_F110_H
/* Catalog identifier, 24-byte ASCII hypothesis; not an OEM wire capture. */
static unsigned int vc0662_f110_enabled(const char *s) {
    return s && s[0]=='1' && s[1]==0;
}
static unsigned int vc0662_f110_answer(unsigned int enabled,
    const unsigned char *req, unsigned int len, unsigned char *res, unsigned int cap) {
    static const unsigned char identity[]="30682825  A";
    unsigned int i;
    if(enabled!=1u || !req || !res || len!=3u || cap<27u ||
       req[0]!=0x22u || req[1]!=0xF1u || req[2]!=0x10u)return 0;
    res[0]=0x62u;res[1]=0xF1u;res[2]=0x10u;
    for(i=0;i<24u;i++)res[i+3u]=i<sizeof(identity)-1u?identity[i]:(unsigned char)' ';
    return 27u;
}
#endif
