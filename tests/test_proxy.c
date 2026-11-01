/* Host harness for the actual wrapper. Every message is synthetic. */
#define VCAR_PROXY_TEST
#define LoadLibraryA test_LoadLibraryA
#define GetProcAddress test_GetProcAddress
#define GetEnvironmentVariableA test_GetEnvironmentVariableA
#define CreateFileA test_CreateFileA
#define WriteFile test_WriteFile
#define CloseHandle test_CloseHandle
#define GetTickCount test_GetTickCount
#define InitOnceExecuteOnce test_InitOnceExecuteOnce
#define GetTempPathA test_GetTempPathA
#define InitializeCriticalSection test_InitializeCriticalSection
#define EnterCriticalSection test_EnterCriticalSection
#define LeaveCriticalSection test_LeaveCriticalSection
#include "../proxy/j2534_trace_proxy.c"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static DWORD now=100, result, returned=1, calls, observed;
static DWORD seen_ch,seen_a,seen_b,seen_c;
static void *seen_p,*seen_q,*seen_r,*seen_s;
static PASSTHRU_MSG sample;
HMODULE WINAPI LoadLibraryA(const char *p){(void)p;return 0;}
FARPROC WINAPI GetProcAddress(HMODULE h,const char *p){(void)h;(void)p;return 0;}
DWORD WINAPI GetEnvironmentVariableA(const char *p,char *b,DWORD n){(void)p;(void)b;(void)n;return 0;}
HANDLE WINAPI CreateFileA(const char *p,DWORD a,DWORD s,void *v,DWORD d,DWORD f,HANDLE h){
    (void)p;(void)a;(void)s;(void)v;(void)d;(void)f;(void)h;return (HANDLE)(uintptr_t)1;
}
BOOL WINAPI WriteFile(HANDLE h,const void *p,DWORD n,DWORD *written,void *v){
    const char *b=(const char *)p;(void)h;(void)v;
    assert(n<1024 && n>=2 && b[n-2]=='}' && b[n-1]=='\n');
    assert(fwrite(p,1,n,stdout)==n);*written=n;return 1;
}
BOOL WINAPI CloseHandle(HANDLE h){(void)h;return 1;}
DWORD WINAPI GetTickCount(void){return now;}
BOOL WINAPI InitOnceExecuteOnce(INIT_ONCE *o,BOOL (WINAPI *cb)(INIT_ONCE*,void*,void**),void *p,void **c){
    (void)o;(void)cb;(void)p;(void)c;return 1;
}
DWORD WINAPI GetTempPathA(DWORD n,char *p){(void)n;(void)p;return 0;}
void WINAPI InitializeCriticalSection(CRITICAL_SECTION *p){(void)p;}
void WINAPI EnterCriticalSection(CRITICAL_SECTION *p){(void)p;}
void WINAPI LeaveCriticalSection(CRITICAL_SECTION *p){(void)p;}
static DWORD WINAPI mock_open(void *p,DWORD *id){++calls;seen_p=p;seen_q=id;if(!result)*id=1;return result;}
static DWORD WINAPI mock_one(DWORD ch){++calls;seen_ch=ch;return result;}
static DWORD WINAPI mock_connect(DWORD dev,DWORD proto,DWORD flags,DWORD baud,DWORD *ch){
    ++calls;seen_ch=dev;seen_a=proto;seen_b=flags;seen_c=baud;seen_p=ch;if(!result)*ch=10;return result;
}
static DWORD WINAPI mock_read(DWORD ch,PASSTHRU_MSG *m,DWORD *n,DWORD timeout){
    DWORD i;
    ++calls;seen_ch=ch;seen_p=m;seen_q=n;seen_a=timeout;
    if(result==0 || result==9 || result==18){
        if(returned<=*n)for(i=0;i<returned;i++){m[i]=sample;if(returned>1)m[i].Data[4]=(uint8_t)i;}
        *n=returned;
    }
    return result;
}
static DWORD WINAPI mock_write(DWORD ch,PASSTHRU_MSG *m,DWORD *n,DWORD timeout){
    ++calls;seen_ch=ch;seen_p=m;seen_q=n;seen_a=timeout;
    if(result==0 || result==9)*n=returned;
    return result;
}
static DWORD WINAPI mock_start(DWORD ch,PASSTHRU_MSG *m,DWORD *id,DWORD interval){
    ++calls;seen_ch=ch;seen_p=m;seen_q=id;seen_a=interval;if(!result)*id=77;return result;
}
static DWORD WINAPI mock_stop(DWORD ch,DWORD id){++calls;seen_ch=ch;seen_a=id;return result;}
static DWORD WINAPI mock_filter(DWORD ch,DWORD type,PASSTHRU_MSG *m,PASSTHRU_MSG *p,PASSTHRU_MSG *f,DWORD *id){
    ++calls;seen_ch=ch;seen_a=type;seen_p=m;seen_q=p;seen_r=f;seen_s=id;if(!result)*id=7;return result;
}
static DWORD WINAPI mock_voltage(DWORD dev,DWORD pin,DWORD voltage){++calls;seen_ch=dev;seen_a=pin;seen_b=voltage;return result;}
static DWORD WINAPI mock_version(DWORD dev,char *f,char *d,char *a){++calls;seen_ch=dev;seen_p=f;seen_q=d;seen_r=a;return result;}
static DWORD WINAPI mock_error(char *p){++calls;seen_p=p;return result;}
static DWORD WINAPI mock_ioctl(DWORD ch,DWORD id,void *in,void *out){++calls;seen_ch=ch;seen_a=id;seen_p=in;seen_q=out;return result;}
static void observe(void *ctx,const vc_event *e){++observed;diagnostic_log(ctx,e);}
int main(void){
    DWORD device=0,ch=0,n,idout;unsigned groups=0,old;char fw[80],dll[80],api[80];
    PASSTHRU_MSG m={0},pat={0},flowmsg={0},before;
    static PASSTHRU_MSG batch[128];
    real_open=mock_open;real_close=mock_one;real_connect=mock_connect;real_disconnect=mock_one;
    real_read=mock_read;real_write=mock_write;real_startperiodic=mock_start;real_stopperiodic=mock_stop;
    real_startfilter=mock_filter;real_stopfilter=mock_stop;real_voltage=mock_voltage;
    real_version=mock_version;real_error=mock_error;real_ioctl=mock_ioctl;
    p2_bridge_init(&g_bridge);vc_init(&g_observer,observe,0);g_bridge_ready=1;g_log_path[0]='x';
    /* 1. Every J2534 argument and result is forwarded through actual exports. */
    assert(PassThruOpen(fw,&device)==0 && device==1 && seen_p==fw && seen_q==&device);
    assert(PassThruConnect(device,6,0x100,500000,&ch)==0 && ch==10);
    assert(seen_ch==device && seen_a==6 && seen_b==0x100 && seen_c==500000 && seen_p==&ch);
    result=37;
    assert(PassThruStartPeriodicMsg(ch,&m,&idout,25)==37 && seen_p==&m && seen_q==&idout && seen_a==25);
    assert(PassThruStopPeriodicMsg(ch,88)==37 && seen_ch==ch && seen_a==88);
    assert(PassThruSetProgrammingVoltage(device,6,0xFFFFFFFFu)==37 && seen_ch==device && seen_a==6 && seen_b==0xFFFFFFFFu);
    assert(PassThruReadVersion(device,fw,dll,api)==37 && seen_p==fw && seen_q==dll && seen_r==api);
    assert(PassThruGetLastError(fw)==37 && seen_p==fw);
    assert(PassThruIoctl(ch,99,&m,&pat)==37 && seen_a==99 && seen_p==&m && seen_q==&pat);
    assert(PassThruDisconnect(ch)==37 && seen_ch==ch && g_observer.channels[0].active);
    assert(PassThruClose(device)==37 && g_observer.channels[0].active);++groups;
    /* 2. Filter ownership, success-only transitions, unchanged input messages. */
    m.ProtocolID=pat.ProtocolID=flowmsg.ProtocolID=6;m.DataSize=pat.DataSize=flowmsg.DataSize=4;
    memset(m.Data,255,4);pat.Data[0]=0x18;pat.Data[1]=0xDA;pat.Data[2]=0xF1;pat.Data[3]=0x50;
    flowmsg.Data[0]=0x18;flowmsg.Data[1]=0xDA;flowmsg.Data[2]=0x50;flowmsg.Data[3]=0xF1;
    before=m;result=0;
    assert(PassThruStartMsgFilter(ch,3,&m,&pat,&flowmsg,&idout)==0 && idout==7);
    assert(seen_p==&m && seen_q==&pat && seen_r==&flowmsg && seen_s==&idout && seen_a==3);
    assert(!memcmp(&m,&before,sizeof(m)) && g_observer.filters[0].active);
    result=7;assert(PassThruStopMsgFilter(ch,idout)==7 && g_observer.filters[0].active);++groups;
    /* 3. Partial writes register only the accepted prefix; caller buffer unchanged. */
    m=flowmsg;m.DataSize=7;m.Data[4]=0x22;m.Data[5]=0xF1;m.Data[6]=0x90;
    before=m;result=9;returned=1;n=2;old=observed;
    assert(PassThruWriteMsgs(ch,&m,&n,123)==9 && n==1 && seen_a==123 && seen_p==&m && seen_q==&n);
    assert(observed==old+1 && !memcmp(&m,&before,sizeof(m)) && g_observer.pending[0].active);++groups;
    /* 4. Read128 success and a timeout-delivered prefix both reach observation. */
    sample=pat;sample.DataSize=8;sample.Data[4]=0x62;sample.Data[5]=0xF1;sample.Data[6]=0x90;sample.Data[7]=0xAB;
    sample.Timestamp=987654;result=0;n=128;old=observed;now=145;
    assert(PassThruReadMsgs(ch,&m,&n,456)==0 && n==1 && seen_a==456 && seen_p==&m && seen_q==&n);
    assert(observed==old+1 && !g_observer.pending[0].active);
    result=9;n=128;old=observed;assert(PassThruReadMsgs(ch,&m,&n,1)==9 && observed==old+1);++groups;
    /* 5. Failed/oversized-count reads must never inspect stale or invalid memory. */
    result=7;n=1;old=observed;
    assert(PassThruReadMsgs(ch,(PASSTHRU_MSG *)(uintptr_t)1,&n,1)==7 && observed==old);
    result=0;returned=2;n=1;
    assert(PassThruReadMsgs(ch,(PASSTHRU_MSG *)(uintptr_t)1,&n,1)==0 && observed==old);
    result=7;n=1;assert(PassThruWriteMsgs(ch,&m,&n,1)==7 && observed==old);++groups;
    /* 6. Failed clears keep state; clear filters, close, reused ID drop old state. */
    result=7;assert(PassThruIoctl(ch,10,0,0)==7 && g_observer.filters[0].active);
    result=0;assert(PassThruIoctl(ch,10,0,0)==0 && !g_observer.filters[0].active);
    assert(PassThruStopMsgFilter(ch,7)==0);
    assert(PassThruDisconnect(ch)==0 && !g_observer.channels[0].active);
    assert(PassThruConnect(device,6,0,125000,&ch)==0 && g_observer.channels[0].generation==2);
    assert(PassThruClose(device)==0 && !g_observer.channels[0].active && !g_bridge.channels[0].active);
    /* Existing raw CAN B9FB goes through unchanged, including READ128/13 RX. */
    assert(PassThruConnect(device,5,0,500000,&ch)==0);
    m=flowmsg;m.ProtocolID=5;m.DataSize=12;m.Data[0]=0;m.Data[1]=0x0F;m.Data[2]=0xFF;m.Data[3]=0xFE;
    m.Data[4]=0xCB;m.Data[5]=0x50;m.Data[6]=0xB9;m.Data[7]=0xFB;
    returned=1;n=1;assert(PassThruWriteMsgs(ch,&m,&n,1)==0 && g_bridge.vehicle.b9fb_seen==1);
    sample=m;sample.Data[0]=1;sample.Data[1]=0x20;sample.Data[2]=0;sample.Data[3]=3;
    returned=13;n=128;old=observed;assert(PassThruReadMsgs(ch,batch,&n,100)==0 && n==13 && observed==old);
    for(old=0;old<13;old++)assert(batch[old].DataSize==12 && batch[old].Data[4]==old && batch[old].Data[7]==0xFB);
    assert(PassThruDisconnect(ch)==0);++groups;
    /* 7. Output cannot include request/response bodies or caller strings. */
    assert(PassThruConnect(device,6,0,500000,&ch)==0);
    m=flowmsg;m.DataSize=40;memcpy(m.Data+4,"SYNTHETIC_PRIVATE_PAYLOAD_NEVER_LOG",33);
    result=0;returned=1;n=1;assert(PassThruWriteMsgs(ch,&m,&n,1)==0);++groups;
    /* 8. Maximal metadata remains a complete JSON object, including long labels. */
    {vc_event e={0};e.event="iso15765_wait_end";e.classification="negative_response_pending";
     e.relation="filter_replaced_no_final_rx";e.ms=e.channel=e.generation=e.protocol=e.baud=e.status=0xFFFFFFFFu;
     e.can_id=e.size=e.rx_status=e.tx_flags=e.device_timestamp=e.filter_id=e.filter_type=e.active_filters=
       e.incomplete=e.sequence=e.candidates=e.elapsed_ms=0xFFFFFFFFu;diagnostic_log(0,&e);}
    assert(calls==30);++groups;
    fprintf(stderr,"dev46: %u/8 actual proxy forwarding groups OK\n",groups);
    return groups==8?0:1;
}
