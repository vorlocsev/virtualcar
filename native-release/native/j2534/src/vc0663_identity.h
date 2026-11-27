#ifndef VC0663_IDENTITY_H
#define VC0663_IDENTITY_H
/* Explicit synthetic read-only identities, NOT OEM values or encodings. */
static unsigned int vc0663_identity_answer(unsigned int enabled,
    const unsigned char *req,unsigned int len,unsigned char *res,unsigned int cap){
    const char *value; unsigned int width,i,n=0;
    if(enabled!=1u || !req || !res || len!=3u || req[0]!=0x22u || req[1]!=0xf1u)return 0;
    switch(req[2]){
    case 0x91u:value="LAB-CEM-HW-0001";width=24u;break;
    case 0x88u:value="LAB-CEM-SW-0001";width=24u;break;
    case 0x8cu:value="LAB-CEM-SN-0001";width=16u;break;
    case 0x20u:value="LAB-CEM-EXTRA-0001";width=24u;break;
    default:return 0;
    }
    if(cap<width+3u)return 0;
    while(value[n])n++;
    res[0]=0x62u;res[1]=0xf1u;res[2]=req[2];
    for(i=0;i<width;i++)res[i+3u]=i<n?(unsigned char)value[i]:(unsigned char)' ';
    return width+3u;
}
#endif
