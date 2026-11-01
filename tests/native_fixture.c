/* All responses are synthetic fixtures, not vehicle-identification evidence. */
#include <windows.h>
#include "native_fixture.h"
static vc_fixture_state state;
static vc_message sample;
static uint32_t result, returned=1;
void WINAPI TestSetResult(uint32_t status,uint32_t count){result=status;returned=count;}
void WINAPI TestSetRx(const vc_message *m){sample=*m;}
const vc_fixture_state *WINAPI TestGetState(void){return &state;}
uint32_t WINAPI PassThruOpen(void *p,uint32_t *id){
    ++state.calls[F_OPEN];state.p=p;state.q=id;if(!result && id)*id=1;return result;
}
uint32_t WINAPI PassThruClose(uint32_t dev){++state.calls[F_CLOSE];state.channel=dev;return result;}
uint32_t WINAPI PassThruConnect(uint32_t dev,uint32_t proto,uint32_t flags,uint32_t baud,uint32_t *ch){
    ++state.calls[F_CONNECT];state.channel=dev;state.a=proto;state.b=flags;state.c=baud;state.p=ch;
    if(!result && ch)*ch=10;return result;
}
uint32_t WINAPI PassThruDisconnect(uint32_t ch){++state.calls[F_DISCONNECT];state.channel=ch;return result;}
uint32_t WINAPI PassThruReadMsgs(uint32_t ch,vc_message *m,uint32_t *n,uint32_t timeout){
    uint32_t i;++state.calls[F_READ];state.channel=ch;state.p=m;state.q=n;state.a=timeout;
    if((result==0 || result==9 || result==18) && n){
        if(m && returned<=*n)for(i=0;i<returned;i++){m[i]=sample;if(returned>1)m[i].Data[4]=(uint8_t)i;}
        *n=returned;
    }
    return result;
}
uint32_t WINAPI PassThruWriteMsgs(uint32_t ch,vc_message *m,uint32_t *n,uint32_t timeout){
    ++state.calls[F_WRITE];state.channel=ch;state.p=m;state.q=n;state.a=timeout;
    if((result==0 || result==9) && n)*n=returned;
    return result;
}
uint32_t WINAPI PassThruStartPeriodicMsg(uint32_t ch,vc_message *m,uint32_t *id,uint32_t interval){
    ++state.calls[F_START_PERIODIC];state.channel=ch;state.p=m;state.q=id;state.a=interval;
    if(!result && id)*id=77;return result;
}
uint32_t WINAPI PassThruStopPeriodicMsg(uint32_t ch,uint32_t id){
    ++state.calls[F_STOP_PERIODIC];state.channel=ch;state.a=id;return result;
}
uint32_t WINAPI PassThruStartMsgFilter(uint32_t ch,uint32_t type,vc_message *m,vc_message *p,vc_message *f,uint32_t *id){
    ++state.calls[F_START_FILTER];state.channel=ch;state.a=type;state.p=m;state.q=p;state.r=f;state.s=id;
    if(!result && id)*id=7;return result;
}
uint32_t WINAPI PassThruStopMsgFilter(uint32_t ch,uint32_t id){
    ++state.calls[F_STOP_FILTER];state.channel=ch;state.a=id;return result;
}
uint32_t WINAPI PassThruSetProgrammingVoltage(uint32_t dev,uint32_t pin,uint32_t voltage){
    /* Only record arguments; there is no programming implementation. */
    ++state.calls[F_VOLTAGE];state.channel=dev;state.a=pin;state.b=voltage;return result;
}
uint32_t WINAPI PassThruReadVersion(uint32_t dev,char *fw,char *dll,char *api){
    ++state.calls[F_VERSION];state.channel=dev;state.p=fw;state.q=dll;state.r=api;
    if(!result){fw[0]='F';fw[1]=0;dll[0]='D';dll[1]=0;api[0]='A';api[1]=0;}
    return result;
}
uint32_t WINAPI PassThruGetLastError(char *p){
    ++state.calls[F_ERROR];state.p=p;if(p){p[0]='S';p[1]=0;}return result;
}
uint32_t WINAPI PassThruIoctl(uint32_t ch,uint32_t id,void *in,void *out){
    ++state.calls[F_IOCTL];state.channel=ch;state.a=id;state.p=in;state.q=out;return result;
}
BOOL WINAPI DllMain(HINSTANCE inst,DWORD reason,LPVOID reserved){(void)inst;(void)reason;(void)reserved;return TRUE;}
