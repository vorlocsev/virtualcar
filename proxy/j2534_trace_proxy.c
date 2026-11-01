/* Windows x86 SAE J2534 v04.04 proxy: forwards all calls unchanged and records
   only request categories, channel IDs, timings and status codes. No payload. */
#include <stdint.h>
#include "p2_message_classify.h"
#include "p2_j2534_bridge.h"
#include "j2534_observer.h"
#ifndef VCAR_PROXY_TEST
#if !defined(_WIN32) || !defined(_M_IX86)
#error This proxy must be built for 32-bit Windows x86.
#endif
#define WINAPI __stdcall
#define IMPORT __declspec(dllimport)
#else
#define WINAPI
#define IMPORT
#endif
#define MAX_PATH_SAFE 1024
#define ERR_FAILED 7u
#define FILE_APPEND_DATA 4u
#define FILE_SHARE_READ 1u
#define FILE_SHARE_WRITE 2u
#define FILE_SHARE_DELETE 4u
#define OPEN_ALWAYS 4u
#define FILE_ATTRIBUTE_NORMAL 0x80u
#define INFINITE_WAIT 0xFFFFFFFFu

typedef uint32_t DWORD;
typedef int32_t BOOL;
typedef void *HANDLE;
typedef void *HMODULE;
typedef intptr_t (WINAPI *FARPROC)(void);
typedef struct {void *Ptr;} INIT_ONCE;
/* Win32 x86 CRITICAL_SECTION layout: 24 bytes; initialized once outside DllMain. */
typedef struct { void *DebugInfo; int32_t LockCount,RecursionCount; HANDLE OwningThread,LockSemaphore; uintptr_t SpinCount; } CRITICAL_SECTION;
typedef vc_message PASSTHRU_MSG;
/* stdcall exports resolved from KERNEL32.DLL, no C runtime is linked. */
IMPORT HMODULE WINAPI LoadLibraryA(const char *);
IMPORT FARPROC WINAPI GetProcAddress(HMODULE,const char *);
IMPORT DWORD WINAPI GetEnvironmentVariableA(const char *,char *,DWORD);
IMPORT HANDLE WINAPI CreateFileA(const char *,DWORD,DWORD,void *,DWORD,DWORD,HANDLE);
IMPORT BOOL WINAPI WriteFile(HANDLE,const void *,DWORD,DWORD *,void *);
IMPORT BOOL WINAPI CloseHandle(HANDLE);
IMPORT DWORD WINAPI GetTickCount(void);
IMPORT BOOL WINAPI InitOnceExecuteOnce(INIT_ONCE *,BOOL (WINAPI *)(INIT_ONCE*,void*,void**),void*,void**);
IMPORT DWORD WINAPI GetTempPathA(DWORD,char*);
IMPORT void WINAPI InitializeCriticalSection(CRITICAL_SECTION *);
IMPORT void WINAPI EnterCriticalSection(CRITICAL_SECTION *);
IMPORT void WINAPI LeaveCriticalSection(CRITICAL_SECTION *);

static INIT_ONCE g_once={0};
static CRITICAL_SECTION g_bridge_lock;
static p2_j2534_bridge g_bridge;
static vc_observer g_observer;
static void diagnostic_log(void *,const vc_event *);
static int g_bridge_ready=0;
static HMODULE g_self=0,g_real=0;
static char g_log_path[MAX_PATH_SAFE]={0};
typedef DWORD (WINAPI *PTOPEN)(void*,DWORD*);
typedef DWORD (WINAPI *PTCLOSE)(DWORD);
typedef DWORD (WINAPI *PTCONNECT)(DWORD,DWORD,DWORD,DWORD,DWORD*);
typedef DWORD (WINAPI *PTDISCONNECT)(DWORD);
typedef DWORD (WINAPI *PTREADMSGS)(DWORD,PASSTHRU_MSG*,DWORD*,DWORD);
typedef DWORD (WINAPI *PTWRITEMSGS)(DWORD,PASSTHRU_MSG*,DWORD*,DWORD);
typedef DWORD (WINAPI *PTSTARTPERIODICMSG)(DWORD,PASSTHRU_MSG*,DWORD*,DWORD);
typedef DWORD (WINAPI *PTSTOPPERIODICMSG)(DWORD,DWORD);
typedef DWORD (WINAPI *PTSTARTMSGFILTER)(DWORD,DWORD,PASSTHRU_MSG*,PASSTHRU_MSG*,PASSTHRU_MSG*,DWORD*);
typedef DWORD (WINAPI *PTSTOPMSGFILTER)(DWORD,DWORD);
typedef DWORD (WINAPI *PTSETPROGRAMMINGVOLTAGE)(DWORD,DWORD,DWORD);
typedef DWORD (WINAPI *PTREADVERSION)(DWORD,char*,char*,char*);
typedef DWORD (WINAPI *PTGETLASTERROR)(char*);
typedef DWORD (WINAPI *PTIOCTL)(DWORD,DWORD,void*,void*);
static PTOPEN real_open=0;
static PTCLOSE real_close=0;
static PTCONNECT real_connect=0;
static PTDISCONNECT real_disconnect=0;
static PTREADMSGS real_read=0;
static PTWRITEMSGS real_write=0;
static PTSTARTPERIODICMSG real_startperiodic=0;
static PTSTOPPERIODICMSG real_stopperiodic=0;
static PTSTARTMSGFILTER real_startfilter=0;
static PTSTOPMSGFILTER real_stopfilter=0;
static PTSETPROGRAMMINGVOLTAGE real_voltage=0;
static PTREADVERSION real_version=0;
static PTGETLASTERROR real_error=0;
static PTIOCTL real_ioctl=0;

static BOOL WINAPI init_real(INIT_ONCE *once,void *param,void **ctx) {
    char real_path[MAX_PATH_SAFE]; DWORD n, logn;
    (void)once;(void)param;(void)ctx;
    InitializeCriticalSection(&g_bridge_lock);
    p2_bridge_init(&g_bridge);
    vc_init(&g_observer,diagnostic_log,0);
    g_bridge_ready=1;
    n=GetEnvironmentVariableA("VCAR_TRACE_REAL_DLL",real_path,MAX_PATH_SAFE);
    if(n<4 || n>=MAX_PATH_SAFE)return 1;
    /* Only an absolute drive path or UNC; prevent self-referential relative paths. */
    if(!((real_path[1]==':' && (real_path[2]=='\\'||real_path[2]=='/')) || (real_path[0]=='\\'&&real_path[1]=='\\')))return 1;
    g_real=LoadLibraryA(real_path);
    if(!g_real || g_real==g_self) {g_real=0;return 1;}
    /* Function-pointer conversions are permitted by C; the void(void)
       intermediate also supports strict GCC host tests. Invoke only through
       the resolved, correctly typed stdcall pointer. */
#define RESOLVE(name,field,type) field=(type)(void (WINAPI *)(void))GetProcAddress(g_real,name)
    RESOLVE("PassThruOpen",real_open,PTOPEN);
    RESOLVE("PassThruClose",real_close,PTCLOSE);
    RESOLVE("PassThruConnect",real_connect,PTCONNECT);
    RESOLVE("PassThruDisconnect",real_disconnect,PTDISCONNECT);
    RESOLVE("PassThruReadMsgs",real_read,PTREADMSGS);
    RESOLVE("PassThruWriteMsgs",real_write,PTWRITEMSGS);
    RESOLVE("PassThruStartPeriodicMsg",real_startperiodic,PTSTARTPERIODICMSG);
    RESOLVE("PassThruStopPeriodicMsg",real_stopperiodic,PTSTOPPERIODICMSG);
    RESOLVE("PassThruStartMsgFilter",real_startfilter,PTSTARTMSGFILTER);
    RESOLVE("PassThruStopMsgFilter",real_stopfilter,PTSTOPMSGFILTER);
    RESOLVE("PassThruSetProgrammingVoltage",real_voltage,PTSETPROGRAMMINGVOLTAGE);
    RESOLVE("PassThruReadVersion",real_version,PTREADVERSION);
    RESOLVE("PassThruGetLastError",real_error,PTGETLASTERROR);
    RESOLVE("PassThruIoctl",real_ioctl,PTIOCTL);
#undef RESOLVE
    logn=GetEnvironmentVariableA("VCAR_TRACE_LOG_PATH",g_log_path,MAX_PATH_SAFE);
    if(logn==0 || logn>=MAX_PATH_SAFE){
        DWORD length=GetTempPathA(MAX_PATH_SAFE,g_log_path);
        const char *file="VirtualCarJ2534Trace.jsonl";
        unsigned i=0;
        if(length==0||length>=MAX_PATH_SAFE-40){g_log_path[0]=0;return 1;}
        while(file[i]){g_log_path[length+i]=file[i];++i;}
        g_log_path[length+i]=0;
    }
    return 1;
}
static void ensure_loaded(void){InitOnceExecuteOnce(&g_once,init_real,0,0);}
static void push_char(char *buf,unsigned *n,char c) {if(*n<1024) buf[(*n)++]=c;}
static void push_text(char *buf,unsigned *n,const char *t) {unsigned i=0;while(t&&t[i]&&*n<1024)push_char(buf,n,t[i++]);}
static void push_num(char *b,unsigned *n,DWORD val) {
    char t[12];unsigned i=0;do{t[i++]=(char)('0'+val%10u);val/=10u;}while(val&&i<11);
    while(i)push_char(b,n,t[--i]);
}
static void push_hex(char *b,unsigned *n,DWORD val) {
    static const char *digits="0123456789ABCDEF";unsigned s;
    push_text(b,n,"0x");for(s=0;s<8;++s)push_char(b,n,digits[(val>>(28-4*s))&15]);
}
/* Never logs paths, raw CAN bytes, VIN, request parameters, credentials or tokens. */
static void event_log_extra(const char *ev,DWORD channel,DWORD status,DWORD requested,DWORD count,
                      p2_kind kind,DWORD canid,DWORD size,DWORD misc,DWORD protocol,DWORD ioctlid,DWORD voltage,
                      const char *core_name,DWORD core_decision) {
    char b[1088];unsigned n=0;HANDLE h;DWORD written;
    if(!g_log_path[0])return;
    push_text(b,&n,"{\"schema\":15,\"ms\":");push_num(b,&n,GetTickCount());
    push_text(b,&n,",\"event\":\"");push_text(b,&n,ev);push_text(b,&n,"\",\"channel\":");push_num(b,&n,channel);
    push_text(b,&n,",\"status\":");push_num(b,&n,status);
    push_text(b,&n,",\"requested\":");push_num(b,&n,requested);
    push_text(b,&n,",\"count\":");push_num(b,&n,count);
    push_text(b,&n,",\"class\":\"");push_text(b,&n,p2_kind_name(kind));push_text(b,&n,"\",\"can_id\":\"");
    push_hex(b,&n,canid);push_text(b,&n,"\",\"size\":");push_num(b,&n,size);
    push_text(b,&n,",\"value\":");push_num(b,&n,misc);
    push_text(b,&n,",\"core_version\":26");
    if(protocol){push_text(b,&n,",\"protocol_id\":");push_num(b,&n,protocol);}
    if(ioctlid){push_text(b,&n,",\"ioctl_id\":");push_num(b,&n,ioctlid);}
    if(ioctlid==3u && status==0u){push_text(b,&n,",\"vbatt_mv\":");push_num(b,&n,voltage);}
    if(core_name && core_name[0]){
      push_text(b,&n,",\"core_class\":\"");push_text(b,&n,core_name);
      push_text(b,&n,"\",\"core_decision\":");push_num(b,&n,core_decision);
    }
    push_text(b,&n,"}\n");
    h=CreateFileA(g_log_path,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,0,
                  OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,0);
    if(h==(HANDLE)(intptr_t)-1)return;
    WriteFile(h,b,n,&written,0);CloseHandle(h);
}
static void event_log(const char *ev,DWORD channel,DWORD status,DWORD requested,DWORD count,
                      p2_kind kind,DWORD canid,DWORD size,DWORD misc){
    event_log_extra(ev,channel,status,requested,count,kind,canid,size,misc,0,0,0,0,0);
}
static p2_kind msg_kind(PASSTHRU_MSG *m,int rx){
    if(!m || m->DataSize>4128u)return P2_OTHER;
    return p2_classify(m->Data,m->DataSize,rx);
}
static DWORD msg_canid(PASSTHRU_MSG *m){return (!m||m->DataSize>4128u)?0:p2_can_id(m->Data,m->DataSize);}
static DWORD msg_len(PASSTHRU_MSG *m){return (!m||m->DataSize>4128u)?0:m->DataSize;}
/* A separate bounded schema keeps legacy schema-15 consumers compatible.
 * All strings originate in observer code, never in vehicle payloads. */
static void diagnostic_log(void *context,const vc_event *e){
    char b[1088];unsigned n=0;HANDLE h;DWORD written;
    (void)context;
    if(!g_log_path[0])return;
    push_text(b,&n,"{\"schema\":46,\"event\":\"");push_text(b,&n,e->event);
    push_text(b,&n,"\",\"class\":\"");push_text(b,&n,e->classification);
    push_text(b,&n,"\",\"relation\":\"");push_text(b,&n,e->relation);push_text(b,&n,"\"");
#define FIELD(name,val) push_text(b,&n,",\"" name "\":");push_num(b,&n,val)
    FIELD("ms",e->ms);FIELD("channel",e->channel);FIELD("generation",e->generation);
    FIELD("protocol_id",e->protocol);FIELD("baud",e->baud);FIELD("status",e->status);
    FIELD("can_id",e->can_id);FIELD("size",e->size);
    FIELD("rx_status",e->rx_status);FIELD("tx_flags",e->tx_flags);
    FIELD("device_timestamp_us",e->device_timestamp);
    FIELD("filter_id",e->filter_id);FIELD("filter_type",e->filter_type);
    FIELD("rx_pattern_id",e->rx_pattern_id);FIELD("rx_mask_id",e->rx_mask_id);
    FIELD("flow_control_id",e->flow_control_id);FIELD("filter_usable",e->filter_usable);
    FIELD("active_filters",e->active_filters);FIELD("incomplete",e->incomplete);
    FIELD("sequence",e->sequence);FIELD("candidates",e->candidates);FIELD("elapsed_ms",e->elapsed_ms);
#undef FIELD
    push_text(b,&n,"}\n");
    h=CreateFileA(g_log_path,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,0,
                  OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,0);
    if(h==(HANDLE)(intptr_t)-1)return;
    WriteFile(h,b,n,&written,0);CloseHandle(h);
}
BOOL WINAPI DllMain(void *inst,DWORD reason,void *reserved){(void)reserved;if(reason==1)g_self=inst;return 1;}
DWORD WINAPI PassThruOpen(void *name,DWORD *device){DWORD st;ensure_loaded();st=real_open?real_open(name,device):ERR_FAILED;event_log("open",(st==0 && device)?*device:0,st,0,0,P2_OTHER,0,0,0);return st;}
DWORD WINAPI PassThruClose(DWORD dev){DWORD st;unsigned i;ensure_loaded();st=real_close?real_close(dev):ERR_FAILED;
  if(st==0 && g_bridge_ready){EnterCriticalSection(&g_bridge_lock);
    for(i=0;i<VC_CHANNELS;i++)if(g_observer.channels[i].active && g_observer.channels[i].device==dev)
      p2_bridge_disconnect(&g_bridge,g_observer.channels[i].id);
    vc_close(&g_observer,dev,GetTickCount());LeaveCriticalSection(&g_bridge_lock);}
  event_log("close",dev,st,0,0,P2_OTHER,0,0,0);return st;}
DWORD WINAPI PassThruConnect(DWORD dev,DWORD protocol,DWORD flags,DWORD baud,DWORD *channel){DWORD st;ensure_loaded();st=real_connect?real_connect(dev,protocol,flags,baud,channel):ERR_FAILED;if(st==0 && channel && g_bridge_ready){
    EnterCriticalSection(&g_bridge_lock);p2_bridge_connect(&g_bridge,*channel,protocol,baud);
    vc_connect(&g_observer,dev,*channel,protocol,baud,GetTickCount());
    LeaveCriticalSection(&g_bridge_lock);
  }
  event_log_extra("connect",(st==0 && channel)?*channel:0,st,0,0,P2_OTHER,0,0,baud,protocol,0,0,0,0);return st;}
DWORD WINAPI PassThruDisconnect(DWORD channel){DWORD st;ensure_loaded();st=real_disconnect?real_disconnect(channel):ERR_FAILED;
  if(st==0 && g_bridge_ready){EnterCriticalSection(&g_bridge_lock);p2_bridge_disconnect(&g_bridge,channel);
    vc_disconnect(&g_observer,channel,GetTickCount());LeaveCriticalSection(&g_bridge_lock);}
  event_log("disconnect",channel,st,0,0,P2_OTHER,0,0,0);return st;}
DWORD WINAPI PassThruReadMsgs(DWORD channel,PASSTHRU_MSG *msgs,DWORD *num,DWORD timeout){
    DWORD st,count=0,requested=num?*num:0,i,idx=0,delivered; p2_kind kind=P2_OTHER;
    const char *core_rx=0;
    ensure_loaded();st=real_read?real_read(channel,msgs,num,timeout):ERR_FAILED;
    count=num?*num:0;
    /* Failed calls may leave NumMsgs unchanged: never inspect that buffer.
     * TIMEOUT/BUFFER_OVERFLOW can report a delivered prefix. */
    delivered=(st==0 || st==9u || st==18u) && msgs && num && count<=requested && count<=128u;
    if(delivered && count>0 && g_bridge_ready){
      EnterCriticalSection(&g_bridge_lock);
      for(i=0;i<count;++i){
        const char *v;
        vc_rx(&g_observer,channel,&msgs[i],GetTickCount());
        if(msgs[i].DataSize>sizeof(msgs[i].Data)) continue;
        v=p2_bridge_inspect_rx(&g_bridge,channel,msgs[i].RxStatus,
                               msgs[i].Data,msgs[i].DataSize,GetTickCount());
        if(v && !core_rx)core_rx=v;
      }
      LeaveCriticalSection(&g_bridge_lock);
    }
    if(delivered && count>0){
      for(i=0;i<count;++i){p2_kind k=msg_kind(&msgs[i],1);if(k!=P2_OTHER){kind=k;idx=i;break;}}
    }
    event_log_extra("read",channel,st,requested,count,kind,
              (delivered&&count>idx)?msg_canid(&msgs[idx]):0,
              (delivered&&count>idx)?msg_len(&msgs[idx]):0,0,
              0,0,0,core_rx,0);
    return st;
}
DWORD WINAPI PassThruWriteMsgs(DWORD channel,PASSTHRU_MSG *msgs,DWORD *num,DWORD timeout){
    DWORD requested=num?*num:0,st,count=0,i,idx=0; p2_kind kind=P2_OTHER;
    const char *core_name=0;
    DWORD core_decision=0;
    if(msgs && requested>0 && requested<=128){
      for(i=0;i<requested;++i){p2_kind k=msg_kind(&msgs[i],0);if(k!=P2_OTHER){kind=k;idx=i;break;}}
    }
    ensure_loaded();st=real_write?real_write(channel,msgs,num,timeout):ERR_FAILED;
    count=num?*num:0;
    /* Observe only successfully accepted messages; observer never changes TX. */
    if((st==0 || st==9u) && msgs && num && g_bridge_ready && count<=128u && count<=requested){
      EnterCriticalSection(&g_bridge_lock);
      for(i=0;i<count;++i){
         p2_bridge_tx_result a;
         vc_tx(&g_observer,channel,&msgs[i],GetTickCount());
         if(msgs[i].DataSize>sizeof(msgs[i].Data))continue;
         if(p2_bridge_inspect_tx(&g_bridge,channel,msgs[i].TxFlags,
                                 msgs[i].Data,msgs[i].DataSize,&a) &&
            a.label && a.label[0] && a.label[0]!='n' && !core_name){
            core_name=a.label;core_decision=(DWORD)a.decision;
         }
      }
      LeaveCriticalSection(&g_bridge_lock);
    }
    event_log_extra("write",channel,st,requested,count,kind,
              (msgs&&requested>idx&&requested<=128)?msg_canid(&msgs[idx]):0,
              (msgs&&requested>idx&&requested<=128)?msg_len(&msgs[idx]):0,0,
              0,0,0,core_name,core_decision);
    return st;
}
DWORD WINAPI PassThruStartPeriodicMsg(DWORD ch,PASSTHRU_MSG *m,DWORD *id,DWORD interval){ensure_loaded();return real_startperiodic?real_startperiodic(ch,m,id,interval):ERR_FAILED;}
DWORD WINAPI PassThruStopPeriodicMsg(DWORD ch,DWORD id){ensure_loaded();return real_stopperiodic?real_stopperiodic(ch,id):ERR_FAILED;}
DWORD WINAPI PassThruStartMsgFilter(DWORD ch,DWORD type,PASSTHRU_MSG *mask,PASSTHRU_MSG *pattern,PASSTHRU_MSG *flow,DWORD *id){
    DWORD st;ensure_loaded();st=real_startfilter?real_startfilter(ch,type,mask,pattern,flow,id):ERR_FAILED;
    if(g_bridge_ready){EnterCriticalSection(&g_bridge_lock);
      vc_filter_start(&g_observer,ch,type,mask,pattern,flow,(st==0 && id)?*id:0,st,GetTickCount());
      LeaveCriticalSection(&g_bridge_lock);}
    return st;
}
DWORD WINAPI PassThruStopMsgFilter(DWORD ch,DWORD id){
    DWORD st;ensure_loaded();st=real_stopfilter?real_stopfilter(ch,id):ERR_FAILED;
    if(g_bridge_ready){EnterCriticalSection(&g_bridge_lock);vc_filter_stop(&g_observer,ch,id,st,GetTickCount());LeaveCriticalSection(&g_bridge_lock);}
    return st;
}
DWORD WINAPI PassThruSetProgrammingVoltage(DWORD dev,DWORD pin,DWORD voltage){ensure_loaded();return real_voltage?real_voltage(dev,pin,voltage):ERR_FAILED;}
DWORD WINAPI PassThruReadVersion(DWORD dev,char *fw,char *dll,char *api){ensure_loaded();return real_version?real_version(dev,fw,dll,api):ERR_FAILED;}
DWORD WINAPI PassThruGetLastError(char *msg){
    static const char *err="VirtualCar trace proxy: original J2534 DLL not loaded";
    unsigned i=0;ensure_loaded();if(real_error)return real_error(msg);
    if(msg){while(err[i]&&i<75){msg[i]=err[i];++i;}msg[i]=0;}return ERR_FAILED;
}
DWORD WINAPI PassThruIoctl(DWORD ch,DWORD id,void *in,void *out){
    DWORD st,v=0;ensure_loaded();st=real_ioctl?real_ioctl(ch,id,in,out):ERR_FAILED;
    if(g_bridge_ready){EnterCriticalSection(&g_bridge_lock);vc_ioctl(&g_observer,ch,id,st,GetTickCount());LeaveCriticalSection(&g_bridge_lock);}
    if(id==3u && st==0u && out)v=*(const DWORD*)out;
    event_log_extra("ioctl",ch,st,0,0,P2_OTHER,0,0,id,0,id,v,0,0);
    return st;
}
