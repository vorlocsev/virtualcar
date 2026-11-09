/* SectorV Virtual Car - J2534 v04.04, x86 Windows DLL.
 * Isolated diagnostic-only simulator. No hardware I/O, secrets, or programming.
 * Build with build.ps1 (MSVC) or build-cross.sh (Clang/LLD).
 */
#ifdef HOST_TEST
#define WINCALL
#define IMPORT
#define EXPORT
#elif defined(CROSS_LLVM)
/* The module .def owns the exact undecorated J2534 export names.
   Do not also emit __declspec(dllexport): x86 __stdcall would add a second,
   decorated export for every PassThru function. */
#define WINCALL __stdcall
#define IMPORT __declspec(dllimport)
#define EXPORT
#else
#define WINCALL __stdcall
#define IMPORT __declspec(dllimport)
#define EXPORT __declspec(dllexport)
#endif
#ifdef CROSS_LLVM
#define ALIAS(x) __asm__(#x)
#else
#define ALIAS(x)
#endif
#ifdef HOST_TEST
typedef unsigned int U32;
#else
typedef unsigned long U32; /* Windows LLP64: 32-bit unsigned long */
#endif
#include "p2core/p2_j2534_bridge.h"
typedef unsigned char U8;
typedef unsigned long long U64;
typedef long long I64;
#ifndef HOST_TEST
/* Minimal CRT-independent floating-point support symbol for MSVC ABI. */
int _fltused = 0;
#endif
typedef void *PTR;
typedef void *HANDLE;
#define MAX_DATA 4128
#define MAX_CHANNELS 8
#define MAX_QUEUE 64
#define MAX_ECUS 8
#define MAX_D2_FRAMES 64
#define MAX_PERIODIC 4
#define MAX_D2_FIXTURES 14
#define BASE_D2_FIXTURES 6
#define MAX_PASSIVE_TRACES 12
#define MAX_EXTRA_DID 192
#define MAX_EXTRA_DID_SLOTS 4
#define MAX_FILTERS 24
#define START_OF_MESSAGE 0x00000002u
#define CAN_29BIT_ID 0x00000100u
#define ISO15765_ADDR_TYPE 0x00000080u /* J2534 5-byte extended address header */
#define ERR_OK 0u
#define ERR_NOT_SUPPORTED 1u
#define ERR_INVALID_CHANNEL_ID 2u
#define ERR_INVALID_PROTOCOL_ID 3u
#define ERR_NULL_PARAMETER 4u
#define ERR_INVALID_IOCTL_VALUE 5u
#define ERR_INVALID_FLAGS 6u
#define ERR_FAILED 7u
#define ERR_DEVICE_NOT_CONNECTED 8u
#define ERR_TIMEOUT 9u
#define ERR_INVALID_MSG 10u
#define ERR_INVALID_TIME_INTERVAL 11u
#define ERR_EXCEEDED_LIMIT 12u
#define ERR_INVALID_MSG_ID 13u
#define ERR_DEVICE_IN_USE 14u
#define ERR_INVALID_IOCTL_ID 15u
#define ERR_BUFFER_EMPTY 16u
#define ERR_BUFFER_FULL 17u
#define ERR_BUFFER_OVERFLOW 18u
#define ERR_PIN_INVALID 19u
#define ERR_CHANNEL_IN_USE 20u
#define ERR_MSG_PROTOCOL_ID 21u
#define ERR_INVALID_FILTER_ID 22u
#define ERR_NO_FLOW_CONTROL 23u
#define ERR_NOT_UNIQUE 24u
#define ERR_INVALID_BAUDRATE 25u
#define ERR_INVALID_DEVICE_ID 26u
#define PROTO_CAN 5u
#define PROTO_ISO15765 6u
#define IO_GET_CONFIG 1u
#define IO_SET_CONFIG 2u
#define IO_READ_VBATT 3u
#define IO_CLEAR_TX_BUFFER 7u
#define IO_CLEAR_RX_BUFFER 8u
#define IO_CLEAR_PERIODIC_MSGS 9u
#define IO_CLEAR_MSG_FILTERS 10u
#define IO_READ_PROG_VOLTAGE 14u
#define INVALID_HANDLE ((HANDLE)(-1))

/* This declaration deliberately has the exact J2534 v04.04 ABI layout. */
typedef struct {
    U32 ProtocolID, RxStatus, TxFlags, Timestamp, DataSize, ExtraDataIndex;
    U8 Data[MAX_DATA];
} PASSTHRU_MSG;
typedef struct { U32 Parameter, Value; } SCONFIG;
typedef struct { U32 NumOfParams; SCONFIG *ConfigPtr; } SCONFIG_LIST;

IMPORT void WINCALL Sleep(U32 ms) ALIAS(Sleep);
IMPORT U32 WINCALL GetTickCount(void) ALIAS(GetTickCount);
IMPORT int WINCALL QueryPerformanceCounter(I64 *count) ALIAS(QueryPerformanceCounter);
IMPORT int WINCALL QueryPerformanceFrequency(I64 *freq) ALIAS(QueryPerformanceFrequency);
IMPORT U32 WINCALL GetCurrentProcessId(void) ALIAS(GetCurrentProcessId);
IMPORT U32 WINCALL GetModuleFileNameA(PTR mod, char *out, U32 n) ALIAS(GetModuleFileNameA);
IMPORT U32 WINCALL GetPrivateProfileStringA(const char *section,const char *key,const char *fallback,char *out,U32 size,const char *path) ALIAS(GetPrivateProfileStringA);
IMPORT U32 WINCALL GetTempPathA(U32 n, char *out) ALIAS(GetTempPathA);
IMPORT U32 WINCALL GetEnvironmentVariableA(const char *name, char *out, U32 n) ALIAS(GetEnvironmentVariableA);
IMPORT int WINCALL CreateDirectoryA(const char *name, PTR sec) ALIAS(CreateDirectoryA);
IMPORT HANDLE WINCALL CreateFileA(const char *path,U32 access,U32 sharing,PTR security,U32 creation,U32 flags,HANDLE templateFile) ALIAS(CreateFileA);
IMPORT U32 WINCALL SetFilePointer(HANDLE file,U32 low,PTR high,U32 method) ALIAS(SetFilePointer);
IMPORT int WINCALL WriteFile(HANDLE file,const void *buf,U32 count,U32 *written,PTR overlap) ALIAS(WriteFile);
IMPORT int WINCALL CloseHandle(HANDLE file) ALIAS(CloseHandle);
IMPORT long WINCALL InterlockedCompareExchange(volatile long *dst,long exchange,long compare) ALIAS(InterlockedCompareExchange);
IMPORT long WINCALL InterlockedExchange(volatile long *dst,long val) ALIAS(InterlockedExchange);

static PTR g_module;
static volatile long g_lock;
static U32 g_open;
static U32 g_last;
static U32 g_filter_counter=1;
static U32 g_periodic_counter=1;
static char g_profile_path[512];
static char g_log_path[512];
static char g_backend_path[512];
static U32 g_backend_enabled=0;
static U32 g_backend_serial=0;
static U64 g_backend_session=0;
static char g_host_name[48]="unknown.exe";
static U32 g_host_pid;
static char g_vin[18]="YV1CZ0002A0000001";
static U32 g_battery_mv=12500;
/* Optional diagnostic traffic is synthetic VCARLAB, never a Volvo CAN trace. */
static U32 g_passive_enabled=0,g_passive_id=0x555,g_passive_period_ms=50;
static U8 g_passive_payload[8]={0x56,0x43,0x41,0x52,0x4C,0x41,0x42,0x00};
/* Optional PASSIVE CAN replay of user-supplied, recorded frames.
   Profiles are empty by default; no vehicle traffic is synthesized. */
typedef struct {U32 id,baud,period_ms;U8 data[8];int enabled;} TRACE_FRAME;
static TRACE_FRAME g_trace[MAX_PASSIVE_TRACES];
static U32 g_trace_count=0;
static U32 g_iso_rx_start=0;
/* Explicit strict receive-filter policy. Legacy behavior is the default. */
static U32 g_strict_j2534_filters=0;
static U32 g_ecu_count=2;
static U32 g_p2_strict_routing=0;
static U32 g_d2_spacing_ms=12; /* 0 means immediate, P2 replay defaults to paced */
typedef struct {U32 req,resp;char part[48];char sw[48]; U8 extra_did[2][MAX_EXTRA_DID]; U32 extra_len[2]; U32 did_code[MAX_EXTRA_DID_SLOTS],did_len[MAX_EXTRA_DID_SLOTS]; U8 did_bytes[MAX_EXTRA_DID_SLOTS][MAX_EXTRA_DID];} ECU;
static ECU g_ecu[MAX_ECUS];
/* Optional read-only replay fixtures: user must supply verified, non-sensitive
   CAN frames. No invented B9 FB vehicle-configuration payloads. */
typedef struct {
    U8 target,subcommand;
    U32 response_id, frame_count, baud;
    U8 frame[MAX_D2_FRAMES][8];
} D2_PROFILE;
static D2_PROFILE g_d2[MAX_D2_FIXTURES];

typedef struct { U32 id,interval_ms; U64 next_us; PASSTHRU_MSG msg; int used; } PERIODIC;
typedef struct { U32 id,type,length; U8 mask[12],pattern[12],flow_id[4]; } FILTER;
/* A recorded abort has to survive queued First/Consecutive Frames.
   At most MAX_QUEUE different aborted requests can have queued frames. */
#define BACKEND_ABORT_FC_OVERFLOW 1u
#define BACKEND_ABORT_SUPERSEDED 2u
typedef struct { U64 rid; U32 cause; } BACKEND_ABORT;
/* Drop causes belong to request IDs, not to a single channel-wide slot.
   At most MAX_QUEUE queued requests plus pending/active requests are live. */
#define BACKEND_DROP_SLOTS (MAX_QUEUE+2u)
#define BACKEND_DROP_QUEUE_FULL 1u
#define BACKEND_DROP_FILTER_REJECT 2u
#define BACKEND_DROP_INVALID_SIZE 3u
typedef struct { U64 rid; U32 cause; } BACKEND_DROP;
typedef struct {
    int used; U32 id,protocol,baud,flags;
    FILTER filters[MAX_FILTERS]; U32 filters_count;
    U32 passive_next_tick;
    U32 trace_next_tick[MAX_PASSIVE_TRACES];
    U64 d2_next_us;
    U32 d2_spacing_ms,d2_response_id,d2_count,d2_pos,d2_generation,d2_frame_number;
    U8 d2_frame[MAX_D2_FRAMES][8];
    PASSTHRU_MSG queue[MAX_QUEUE]; U32 queue_d2_gen[MAX_QUEUE],queue_d2_frame[MAX_QUEUE]; U64 queue_ready_us[MAX_QUEUE]; U32 r,w,count;
    /* Diagnostic correlation metadata. Never sent to the J2534 client. */
    U64 queue_trace[MAX_QUEUE],active_trace,d2_trace,pending_trace;
    BACKEND_ABORT aborted[MAX_QUEUE];
    BACKEND_DROP drops[BACKEND_DROP_SLOTS];
    PERIODIC periodic[MAX_PERIODIC];
    U8 pending[256]; U32 pending_len,pending_pos,pending_id,pending_request_id,pending_sn;
    U64 pending_next_us; U32 pending_stmin_us;
    /* Flow Control CTS grant survives RX FIFO backpressure; zero credit is
       unlimited only while pending_cf_active is set. */
    U32 pending_cf_active,pending_cf_credit,read_timeout_count;
} CHANNEL;
static CHANNEL g_ch[MAX_CHANNELS];
/* Read-only vehicle-state observer, serialized by g_lock. */
static p2_j2534_bridge g_vehicle_bridge;

/* High-resolution monotonic time for D2 scheduling and RX timestamps.
   QueryPerformanceCounter is available on supported Windows versions.
   Dividing first avoids 64-bit overflow in long-lived processes. */
static U64 now_us(void){
    I64 count=0,freq=0;
    if(QueryPerformanceFrequency(&freq) && freq>0 && QueryPerformanceCounter(&count) && count>=0)
        return (U64)((double)count*(1000000.0/(double)freq));
    return (U64)GetTickCount()*1000ull;
}
static U64 backend_session_id(U32 pid,U32 tick,U64 counter){
    U64 x=counter^(((U64)pid<<32)|tick)^0x9E3779B97F4A7C15ull;
    x^=x>>30;x*=0xBF58476D1CE4E5B9ull;x^=x>>27;
    x*=0x94D049BB133111EBull;x^=x>>31;
    return x?x:1u;
}
static void append_hex64(char *out,U32 cap,U64 value){
    static const char digits[]="0123456789abcdef";U32 i,n=0;
    while(n<cap&&out[n])n++;
    for(i=0;i<16&&n+1<cap;i++){U32 shift=(15u-i)*4u;out[n++]=digits[(value>>shift)&15u];}
    if(n<cap)out[n]=0;
}
static U32 str_len(const char *s) { U32 i=0;if(!s)return 0;while(s[i] && i<4096)i++;return i; }
static void bytes_copy(void *out,const void *src,U32 n) {U8 *d=(U8*)out;const U8 *s=(const U8*)src;U32 i;for(i=0;i<n;i++)d[i]=s[i];}
static void bytes_zero(void *out,U32 n) {U8 *d=(U8*)out;U32 i;for(i=0;i<n;i++)d[i]=0;}
static void str_copy(char *out,const char *src,U32 cap) {U32 i=0;if(!cap)return;while(src && src[i] && i+1<cap){out[i]=src[i];i++;}out[i]=0;}
static void str_append(char *out,const char *s,U32 cap) {U32 i=str_len(out),j=0;while(s&&s[j]&&i+1<cap)out[i++]=s[j++];out[i]=0;}
static int digit(char c) { if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1; }
static U32 parse_num(const char *s,U32 fallback) {U32 v=0,base=10,i=0;int d,any=0;if(!s)return fallback;if(s[0]=='0'&&(s[1]=='x'||s[1]=='X')){base=16;i=2;}for(;s[i];i++){d=digit(s[i]);if(d<0||((U32)d)>=base) return fallback;any=1;v=v*base+(U32)d;}return any?v:fallback;}
static U32 parse_hex(const char *s,U32 fallback){U32 v=0,i=0;int d,any=0;if(!s)return fallback;if(s[0]=='0'&&(s[1]=='x'||s[1]=='X'))i=2;for(;s[i];i++){d=digit(s[i]);if(d<0)return fallback;any=1;v=(v<<4)|(U32)d;}return any?v:fallback;}
static int parse_frame8(const char *text,U8 *out){
    U32 i=0,n=0;int hi,lo;
    while(text[i]){
        while(text[i]==' '||text[i]=='\t'||text[i]=='-'||text[i]==':')i++;
        if(!text[i])break;
        hi=digit(text[i++]);if(hi<0||!text[i])return 0;
        lo=digit(text[i++]);if(lo<0||n>=8)return 0;
        out[n++]=(U8)((hi<<4)|lo);
    }
    return n==8;
}
/* Parse read-only fixture bytes, e.g. "53 49 4D". Empty means disabled. */
static U32 parse_hex_blob(const char *text,U8 *out,U32 cap){
    U32 i=0,n=0;int hi,lo;
    if(!text)return 0;
    while(text[i]){
        while(text[i]==' '||text[i]=='\t'||text[i]=='-'||text[i]==':'||text[i]==',')i++;
        if(!text[i])break;
        hi=digit(text[i++]);if(hi<0||!text[i])return 0;
        lo=digit(text[i++]);if(lo<0||n>=cap)return 0;
        out[n++]=(U8)((hi<<4)|lo);
    }
    return n;
}
static void u32_be(U8 *d,U32 v){d[0]=(U8)(v>>24);d[1]=(U8)(v>>16);d[2]=(U8)(v>>8);d[3]=(U8)v;}
static void hex_bytes(char *out,U32 cap,const U8 *data,U32 len) {static const char h[]="0123456789ABCDEF";U32 i,p=0;for(i=0;i<len&&p+3<cap;i++){out[p++]=h[data[i]>>4];out[p++]=h[data[i]&15];out[p++]=' ';}out[p]=0;}
static void append_hex32(char *out, U32 cap, U32 v) {
    static const char h[]="0123456789ABCDEF"; char hex[9];U32 i;
    for(i=0;i<8;i++)hex[i]=h[(v>>(28-4*i))&15];
    hex[8]=0;str_append(out,hex,cap);
}
static void lock_state(void) {while(InterlockedCompareExchange(&g_lock,1,0)!=0)Sleep(1);}
static void unlock_state(void) {InterlockedExchange(&g_lock,0);}
static U32 error(U32 e){g_last=e;return e;}
static void logline(const char *message,const U8 *data,U32 len) {
    HANDLE f;U32 written;char line[320];U32 p=0;
    if(!g_log_path[0])return;
    str_copy(line,"[PID=",sizeof(line));append_hex32(line,sizeof(line),g_host_pid);
    str_append(line," ",sizeof(line));str_append(line,g_host_name,sizeof(line));
    str_append(line,"] ",sizeof(line));str_append(line,message,sizeof(line));p=str_len(line);
    if(data&&len&&p+1<sizeof(line)){line[p++]=' ';hex_bytes(line+p,sizeof(line)-p,data,len>52?52:len);p=str_len(line);}
    if(p+2<sizeof(line)){line[p++]='\r';line[p++]='\n';line[p]=0;}
    f=CreateFileA(g_log_path,0x40000000u,3,0,4,0x80,0); /* FILE_APPEND_DATA, OPEN_ALWAYS */
    if(f==INVALID_HANDLE)return;
    SetFilePointer(f,0,0,2);WriteFile(f,line,p,&written,0);CloseHandle(f);
}

/* P3Tool IL evidence: expose Connect's actual outcome even when no channel
   exists. These four big-endian integers are API metadata, NOT CAN payloads;
   changing this log must never change the return code or open a new protocol. */
static U32 connect_result(U32 protocol,U32 flags,U32 baud,U32 status){
    U8 meta[16];
    u32_be(meta,protocol);u32_be(meta+4,flags);
    u32_be(meta+8,baud);u32_be(meta+12,status);
    logline("J2534 Connect result protocol/flags/baud/status (BE)",meta,16);
    return error(status);
}
/* J2534 config reports distinguish implemented baud setting from accepted
   no-op options. Unknown parameter IDs and values are deliberately redacted. */
static void log_set_config(U32 channel_id,U32 parameter,U32 value){
    U8 meta[16];U32 known=0;
    if(parameter==1u || parameter==3u || parameter==23u ||
       parameter==30u || parameter==31u || parameter==779u)known=1;
    u32_be(meta,channel_id);
    u32_be(meta+4,known?parameter:0u);
    u32_be(meta+8,known?value:0u);
    u32_be(meta+12,parameter==1u?1u:0u);
    logline("J2534 SET_CONFIG channel/parameter/value/applied (BE)",meta,16);
}

/* dev49: optional, metadata-only backend events for the single Virtual Car UI.
   Only fixed literals are permitted for kind/route/reason/outcome. No CAN
   payload, VIN, ECU identifiers or profile paths are written to this stream.
   Calls occur under g_lock; failures must never change J2534 behavior. */
static void append_dec64(char *out,U32 cap,U64 value){
    char reversed[24];U32 n=0,i;
    do{reversed[n++]=(char)('0'+value%10u);value/=10u;}while(value && n<sizeof(reversed));
    for(i=0;i<n;i++){char digitstr[2]={reversed[n-1-i],0};str_append(out,digitstr,cap);}
}
static U64 next_backend_request(void) {
    U64 value;
    if(!g_backend_enabled)return 0;
    ++g_backend_serial;if(!g_backend_serial)++g_backend_serial;
    value=((U64)g_host_pid<<32)|g_backend_serial;
    return value?value:1;
}
static void backend_event_with_probe(const CHANNEL *c,U64 rid,const char *kind,const char *route,
                          const char *reason,const char *outcome,const char *probe) {
    char line[640];HANDLE f;U32 written,len;I64 counter=0,freq=0;
    if(!g_backend_enabled||!g_backend_path[0]||!rid||!c)return;
    if(!QueryPerformanceCounter(&counter)||!QueryPerformanceFrequency(&freq)||freq<=0)return;
    str_copy(line,"{\"format\":\"virtualcar-backend-v1\",\"kind\":\"",sizeof(line));
    str_append(line,kind,sizeof(line));
    str_append(line,"\",\"session_id\":\"",sizeof(line));append_hex64(line,sizeof(line),g_backend_session);
    str_append(line,"\",\"request_id\":",sizeof(line));append_dec64(line,sizeof(line),rid);
    str_append(line,",\"tick\":",sizeof(line));append_dec64(line,sizeof(line),counter>0?(U64)counter:1u);
    str_append(line,",\"freq\":",sizeof(line));append_dec64(line,sizeof(line),(U64)freq);
    str_append(line,",\"channel\":",sizeof(line));append_dec64(line,sizeof(line),c->id);
    str_append(line,",\"protocol\":",sizeof(line));append_dec64(line,sizeof(line),c->protocol);
    str_append(line,",\"baud\":",sizeof(line));append_dec64(line,sizeof(line),c->baud);
    str_append(line,",\"route\":\"",sizeof(line));str_append(line,route,sizeof(line));
    str_append(line,"\",\"reason\":\"",sizeof(line));str_append(line,reason,sizeof(line));
    str_append(line,"\",\"outcome\":\"",sizeof(line));str_append(line,outcome,sizeof(line));
    if(probe){
        str_append(line,"\",\"probe\":\"",sizeof(line));
        str_append(line,probe,sizeof(line));
    }
    str_append(line,"\"}\n",sizeof(line));len=str_len(line);
    if(len>=sizeof(line)-1)return;
    f=CreateFileA(g_backend_path,4u,3u,0,4u,0x80u,0);
    if(f==INVALID_HANDLE)return;
    (void)WriteFile(f,line,len,&written,0);(void)CloseHandle(f);
}
static void backend_event(const CHANNEL *c,U64 rid,const char *kind,const char *route,
                          const char *reason,const char *outcome) {
    backend_event_with_probe(c,rid,kind,route,reason,outcome,0);
}
/* Recognize only complete classic-CAN CEM A3/A6 request envelopes.
   C8 + significant-byte count includes target/service; trailing CAN padding
   is allowed. This validates shape only, never ECU acceptance or permission. */
static int cem_d2_probe_shape(const U8 *p,U32 n){
    return p && n>=3u && n<=8u && p[0]>=0xCAu && p[0]<=0xCFu &&
           n>=(U32)(p[0]-0xC8u)+1u &&
           (p[1]==0x40u||p[1]==0x50u) &&
           (p[2]==0xA3u||p[2]==0xA6u);
}
/* Observer only: a bounded catalogue from drpioneer/Volvo-P2-informer
   main@9cd3a6f603915e074ac28c73eccec6b7473e8297. Those frames came from a
   2.5T project, NOT an OEM XC90 V8 identity/response fixture.
   Do not interpret inferred ECU families as confirmation that a module exists. */
static const char *p2_informer_probe_name(const CHANNEL *c,U32 id,const U8 *p,U32 n){
    static const U8 ecm_selectors[][2]={
        {0x10,0xB8},{0x10,0x05},{0x10,0xEF},{0x10,0xAF},
        {0x10,0x01},{0x10,0x02},{0x10,0x93},{0x10,0xF8},
        {0x12,0x48},{0x10,0xAD},{0x15,0x7D},{0x15,0x83},
        {0x10,0x2D},{0x10,0x4E},{0x10,0x9A},{0x13,0x63},
        {0x13,0x62},{0x10,0x2C}};
    static const U8 tcm_selectors[]={
        0x0C,0x06,0x07,0x20,0x21,0x22,0xB2,0xB3,
        0xB4,0x01,0x93,0x15};
    U32 i;
    if(!c||!p||id!=0x000FFFFEu||c->protocol!=PROTO_CAN||n!=8u)return 0;
    if(c->baud==125000u) {
        /* Exact source single-frame VIN TX; no implied RX 62 F1 90. */
        if(p[0]==0x03u && p[1]==0x22u && p[2]==0xF1u && p[3]==0x90u &&
           p[4]==0u && p[5]==0u && p[6]==0u && p[7]==0u)
            return "P2INF_LS_VIN_F190";
        if(p[0]==0xCDu && p[1]==0x46u && p[2]==0xA6u &&
           p[3]==0xD0u && p[4]==0xD4u && p[5]==1u && p[6]==0u && p[7]==0u)
            return "P2INF_LS_REM_A6";
        if(p[0]==0xCDu && p[1]==0x29u && p[2]==0xA6u &&
           p[3]==0u && (p[4]==0x01u||p[4]==0xA1u||p[4]==0x30u) &&
           p[5]==1u && p[6]==0u && p[7]==0u)
            return "P2INF_LS_CCM_A6";
    }
    if(c->baud==500000u) {
        if(p[0]==0xCDu && p[1]==0x7Au && p[2]==0xA6u &&
           p[5]==1u && p[6]==0u && p[7]==0u){
            for(i=0;i<sizeof(ecm_selectors)/sizeof(ecm_selectors[0]);i++)
                if(ecm_selectors[i][0]==p[3] && ecm_selectors[i][1]==p[4])
                    return "P2INF_HS_ECM_A6";
        }
        if(p[0]==0xCCu && p[1]==0x6Eu && p[2]==0xA5u &&
           p[4]==1u && p[5]==0u && p[6]==0u && p[7]==0u){
            for(i=0;i<sizeof(tcm_selectors)/sizeof(tcm_selectors[0]);i++)
                if(tcm_selectors[i]==p[3])return "P2INF_HS_TCM_A5";
        }
        if(p[0]==0xCDu && p[1]==0x1Au && p[2]==0xA6u &&
           p[3]==0u && (p[4]==0x05u||p[4]==0x03u||p[4]==0x02u) &&
           p[5]==1u && p[6]==0u && p[7]==0u)
            return "P2INF_HS_DEM_A6";
    }
    return 0;
}
/* The classifier outputs ONLY literals from this allowlist. These tokens are
   diagnostic request shapes, not evidence of actual ECU capabilities. */
static const char *backend_probe_name(const CHANNEL *c,const PASSTHRU_MSG *m) {
    U32 id,n;const U8 *p;
    static const char *const d2_labels[2][5]={
        {"D2_40_A3","D2_40_A6","D2_40_B9F0","D2_40_B9FB","D2_40_B9FC"},
        {"D2_50_A3","D2_50_A6","D2_50_B9F0","D2_50_B9FB","D2_50_B9FC"}};
    static const char *const p3_labels[2][5]={
        {"P3_726_F114","P3_726_F1B0","P3_726_F1A3","P3_726_F106","P3_726_F190"},
        {"P3_29_F114","P3_29_F1B0","P3_29_F1A3","P3_29_F106","P3_29_F190"}};
    U32 target,which,index;const U8 *uds;U32 size;
    if(!c||!m||m->DataSize<5||m->DataSize>MAX_DATA)return 0;
    id=((U32)m->Data[0]<<24)|((U32)m->Data[1]<<16)|((U32)m->Data[2]<<8)|m->Data[3];
    p=m->Data+4;n=m->DataSize-4;
    /* These source-labelled families are metadata only, never new CAN RX. */
    {
        const char *informer=p2_informer_probe_name(c,id,p,n);
        if(informer)return informer;
    }
    if(id==0x000FFFFEu && c->protocol==PROTO_CAN && cem_d2_probe_shape(p,n)){
        target=p[1]==0x40u?0u:1u;
        return d2_labels[target][p[2]==0xA3u?0u:1u];
    }
    if(id==0x000FFFFEu && c->protocol==PROTO_CAN && n>=3 &&
       (p[0]==0xCBu||p[0]==0xCFu||p[0]==0xCAu) &&
       (p[1]==0x40u||p[1]==0x50u)){
        target=p[1]==0x40u?0u:1u;
        if(p[2]!=0xB9u||n<4)return 0;
        if(p[3]==0xF0u)return d2_labels[target][2];
        if(p[3]==0xFBu)return d2_labels[target][3];
        if(p[3]==0xFCu)return d2_labels[target][4];
        return 0;
    }
    if(id!=0x726u && id!=0x18DA50F1u)return 0;
    if(c->protocol==PROTO_ISO15765){uds=p;size=n;}
    else if(c->protocol==PROTO_CAN){
        /* Only a complete single-frame ReadDataByIdentifier request can be
           classified. Multi-frame TX and Flow Control remain unclassified. */
        if(n<4 || (p[0]&0xF0u)!=0 || (p[0]&0x0Fu)!=3u)return 0;
        uds=p+1;size=3;
    }else return 0;
    /* J2534 ISO15765 may carry multiple DID operands. Do not label a
       compound 22 F1xx F1yy request as if it queried only the first DID. */
    if(size!=3 || uds[0]!=0x22u || uds[1]!=0xF1u)return 0;
    which=id==0x726u?0u:1u;
    if(uds[2]==0x14u)index=0;
    else if(uds[2]==0xB0u)index=1;
    else if(uds[2]==0xA3u)index=2;
    else if(uds[2]==0x06u)index=3;
    else if(uds[2]==0x90u)index=4;
    else return 0;
    return p3_labels[which][index];
}
static void backend_probe_event(const CHANNEL *c,U64 rid,const PASSTHRU_MSG *m){
    const char *probe;
    if(!rid || !g_backend_enabled)return;
    probe=backend_probe_name(c,m);
    if(probe)backend_event_with_probe(c,rid,"probe_classified","UNKNOWN","none","unknown",probe);
}
static const char *backend_abort_cause(U32 cause) {
    if(cause==BACKEND_ABORT_FC_OVERFLOW)return "flow_overflow";
    if(cause==BACKEND_ABORT_SUPERSEDED)return "superseded";
    return "unknown";
}
static const char *backend_drop_cause(U32 cause) {
    if(cause==BACKEND_DROP_QUEUE_FULL)return "queue_full";
    if(cause==BACKEND_DROP_FILTER_REJECT)return "filter_reject";
    return "other";
}
static void backend_note_drop(CHANNEL *c,U64 rid,U32 cause) {
    U32 i,free_slot=BACKEND_DROP_SLOTS;
    if(!rid)return;
    for(i=0;i<BACKEND_DROP_SLOTS;i++){
        if(c->drops[i].rid==rid){
            /* A lost frame due to FIFO exhaustion takes precedence over
               filter rejection if both occur within the same request. */
            if(cause==BACKEND_DROP_QUEUE_FULL ||
               c->drops[i].cause!=BACKEND_DROP_QUEUE_FULL)
                c->drops[i].cause=cause;
            return;
        }
        if(!c->drops[i].rid && free_slot==BACKEND_DROP_SLOTS)free_slot=i;
    }
    if(free_slot<BACKEND_DROP_SLOTS){
        c->drops[free_slot].rid=rid;c->drops[free_slot].cause=cause;
        return;
    }
    /* Bound is normally sufficient: every retained RID has at least one
       queued/staged frame, and there are only MAX_QUEUE queued slots. */
    backend_event(c,rid,"tracking_overflow","UNKNOWN","tracking_limit","unverified");
}
static void backend_forget_drop(CHANNEL *c,U64 rid) {
    U32 i;
    for(i=0;i<BACKEND_DROP_SLOTS;i++)if(c->drops[i].rid==rid) {
        c->drops[i].rid=0;c->drops[i].cause=0;return;
    }
}
static void backend_end_if_drained(CHANNEL *c,U64 rid) {
    U32 j;
    if(!rid)return;
    if((c->d2_count && c->d2_trace==rid) ||
       (c->pending_len && c->pending_trace==rid))return;
    for(j=0;j<c->count;j++)
        if(c->queue_trace[(c->r+j)%MAX_QUEUE]==rid)return;
    /* A delivered FF is not a completed ISO-TP response when CFs were
       discarded by OVERFLOW or replaced by a newer response. */
    for(j=0;j<MAX_QUEUE;j++)if(c->aborted[j].rid==rid) {
        backend_event(c,rid,"request_completed","UNKNOWN",
                      backend_abort_cause(c->aborted[j].cause),"aborted");
        c->aborted[j].rid=0;c->aborted[j].cause=0;
        backend_forget_drop(c,rid);
        return;
    }
    for(j=0;j<BACKEND_DROP_SLOTS;j++)if(c->drops[j].rid==rid) {
        backend_event(c,rid,"request_completed","UNKNOWN",
                      backend_drop_cause(c->drops[j].cause),"dropped");
        c->drops[j].rid=0;c->drops[j].cause=0;
        return;
    }
    backend_event(c,rid,"request_completed","UNKNOWN","none","responded");
}
static void backend_abort_pending(CHANNEL *c,U64 rid,U32 cause) {
    U32 i;
    if(!rid)return; /* Opt-out: no telemetry state or file I/O. */
    backend_event(c,rid,"response_aborted","UNKNOWN",
                  backend_abort_cause(cause),"unknown");
    for(i=0;i<MAX_QUEUE;i++)if(c->aborted[i].rid==rid) {
        backend_end_if_drained(c,rid);return;
    }
    for(i=0;i<MAX_QUEUE;i++)if(!c->aborted[i].rid) {
        c->aborted[i].rid=rid;c->aborted[i].cause=cause;
        backend_end_if_drained(c,rid);return;
    }
    /* Defensive path: never report responded when our evidence table is full.
       Keep actual J2534 frames unchanged, drop only their attribution. */
    for(i=0;i<c->count;i++) {
        U32 slot=(c->r+i)%MAX_QUEUE;
        if(c->queue_trace[slot]==rid)c->queue_trace[slot]=0;
    }
    backend_forget_drop(c,rid);
    backend_event(c,rid,"request_completed","UNKNOWN",
                  "tracking_limit","unverified");
}

/* F11: terminal evidence for frames discarded by an existing lifecycle
   action. Read-side/J2534 behavior is unchanged. All IDs are collected
   before queue compaction or channel reset, so each RID completes once. */
static void backend_collect_rid(U64 *rids,U32 *n,U64 rid) {
    U32 j;
    if(!rid)return;
    for(j=0;j<*n;j++)if(rids[j]==rid)return;
    if(*n<MAX_QUEUE+2u)rids[(*n)++]=rid;
}
static void backend_cancel_channel(CHANNEL *c,const char *reason,int d2_only) {
    U64 rids[MAX_QUEUE+2u];U32 n=0,i,j;
    for(i=0;i<c->count;i++){
        U32 slot=(c->r+i)%MAX_QUEUE;
        if(!d2_only || c->queue_d2_gen[slot])
            backend_collect_rid(rids,&n,c->queue_trace[slot]);
    }
    if(c->d2_trace && c->d2_count)
        backend_collect_rid(rids,&n,c->d2_trace);
    if(!d2_only && c->pending_trace && c->pending_len)
        backend_collect_rid(rids,&n,c->pending_trace);
    /* Record discarded queued frames first. Terminal events must be last
       for each RID and must not imply that dropped RX reached the client. */
    for(i=0;i<c->count;i++){
        U32 slot=(c->r+i)%MAX_QUEUE;
        if((!d2_only || c->queue_d2_gen[slot]) && c->queue_trace[slot])
            backend_event(c,c->queue_trace[slot],"rx_dropped","UNKNOWN",reason,"unknown");
    }
    for(i=0;i<n;i++){
        U64 rid=rids[i];
        const char *resolved=reason;
        int abort_logged=0;
        /* F08 already recorded the precise transport failure: keep that
           cause instead of mislabeling it as a subsequent buffer reset. */
        for(j=0;j<MAX_QUEUE;j++)if(c->aborted[j].rid==rid){
            resolved=backend_abort_cause(c->aborted[j].cause);
            abort_logged=1;
            c->aborted[j].rid=0;c->aborted[j].cause=0;
        }
        if(!abort_logged)
            backend_event(c,rid,"response_aborted","UNKNOWN",resolved,"unknown");
        backend_event(c,rid,"request_completed","UNKNOWN",resolved,"aborted");
        backend_forget_drop(c,rid);
        /* A CLEAR_RX_BUFFER resets the actual queue, not ISO-TP state.
           Keep its legacy transport behavior while detaching stale evidence:
           later CFs after CLEAR must not claim a complete old response. */
        if(!d2_only && c->pending_trace==rid)c->pending_trace=0;
        if(c->d2_trace==rid)c->d2_trace=0;
        if(!d2_only)for(j=0;j<c->count;j++){
            U32 slot=(c->r+j)%MAX_QUEUE;
            if(c->queue_trace[slot]==rid)c->queue_trace[slot]=0;
        }
    }
}

/* Validates framing only. No assertion about undocumented FB semantics. */
static int validate_d2_fixture(const D2_PROFILE *d){
    U32 k;U8 base,seq=1;int final=0;
    if(!d->frame_count || d->frame_count>MAX_D2_FRAMES || d->response_id>0x1FFFFFFFu)return 0;
    if(d->frame_count==1){
        const U8 *f=d->frame[0];
        if((f[0]&0xF8)!=0xC8 || f[1]!=d->target)return 0;
        return (f[2]==0xF9 && f[3]==d->subcommand) ||
               (f[2]==0x7F && f[3]==0xB9);
    }
    if((d->frame[0][0]!=0x8F && d->frame[0][0]!=0x97) ||
       d->frame[0][1]!=d->target || d->frame[0][2]!=0xF9 ||
       d->frame[0][3]!=d->subcommand)return 0;
    base=(d->frame[0][0]&0x10)?0x10:0x08;
    for(k=1;k<d->frame_count;k++){
        U8 header=d->frame[k][0];
        if(header>=0x48 && header<=0x4F){
            if(k!=d->frame_count-1)return 0;
            /* The published 13-frame 0x08-series D2 example carries
               seven data bytes in the last frame (0x4F). A different
               terminal marker would imply a shorter final payload;
               do not silently accept its seven padded bytes as B9FB. */
            if(base==0x08 && d->frame_count==13u && header!=0x4Fu)return 0;
            final=1;continue;
        }
        /* Sub-block ends but the D2 response has not ended. */
        if((header&0xF8)==0x50){
            if(k==d->frame_count-1)return 0;
            continue;
        }
        /* A duplicated first frame after the sub-block boundary is observed
           in VIDA; it is not a new response or a payload segment. */
        if(header==0x8F && k>1 && (d->frame[k-1][0]&0xF8)==0x50 &&
           d->frame[k][1]==d->target && d->frame[k][2]==0xF9 &&
           d->frame[k][3]==d->subcommand)continue;
        if(header!=(U8)(base|seq))return 0;
        seq=(seq+1)&7u;
    }
    return final;
}
/* Validate the observed 142-byte FC layout: 0x8C, sum8, 140 bytes.
   This strict guard applies only to the current laboratory FC profile type.
   The full D2 data stream consists of target+positive echo (3 bytes)
   followed by the 142-byte configuration block. No flash writes occur. */
static int validate_fc140_fixture(const D2_PROFILE *d){
    U8 stream[7*MAX_D2_FRAMES];U32 n=0,k,j,chunk,sum=0;
    if(d->subcommand!=0xFC)return 1;
    if(!validate_d2_fixture(d))return 0;
    if(d->frame_count!=21 || d->frame[0][0]!=0x8F)return 0;
    for(k=0;k<d->frame_count;k++){
        U8 h=d->frame[k][0];
        chunk=(k==d->frame_count-1)?(U32)(h-0x48):7u;
        if(k==d->frame_count-1 && h!=0x4D)return 0;
        if(n+chunk>sizeof(stream))return 0;
        for(j=0;j<chunk;j++)stream[n++]=d->frame[k][j+1];
    }
    if(n!=145u || stream[0]!=d->target || stream[1]!=0xF9 ||
       stream[2]!=0xFC || stream[3]!=0x8C)return 0;
    for(k=0;k<140;k++)sum+=(U32)stream[5+k];
    return stream[4]==(U8)sum;
}
static void load_config(void) {
    U32 n,i;char v[512],key[24];
    /* Include the host executable and PID so GUI self-checks and SectorV
       sessions can be distinguished when they share the same log file. */
    g_host_pid=GetCurrentProcessId();
    {I64 session_counter=0;QueryPerformanceCounter(&session_counter);
     g_backend_session=backend_session_id(g_host_pid,GetTickCount(),session_counter>0?(U64)session_counter:0u);
     g_backend_serial=0;}
    n=GetModuleFileNameA(0,v,sizeof(v));
    if(n>0 && n<sizeof(v)){
        U32 start=0,j;
        for(j=0;j<n;j++)if(v[j]=='\\'||v[j]=='/')start=j+1;
        str_copy(g_host_name,v+start,sizeof(g_host_name));
    }
    g_ecu_count=2;bytes_zero(g_ecu,sizeof(g_ecu));g_ecu[0].req=0x7E0;g_ecu[0].resp=0x7E8;
    g_ecu[1].req=0x726;g_ecu[1].resp=0x72E;
    str_copy(g_ecu[0].part,"VIRTUAL-ECU",sizeof(g_ecu[0].part));
    str_copy(g_ecu[0].sw,"SIM-1.0",sizeof(g_ecu[0].sw));
    n=GetModuleFileNameA(g_module,g_profile_path,sizeof(g_profile_path));
    if(n>=sizeof(g_profile_path)-20)n=0;
    while(n && g_profile_path[n-1]!='\\'&&g_profile_path[n-1]!='/')n--;
    g_profile_path[n]=0;str_append(g_profile_path,"virtualcar.ini",sizeof(g_profile_path));
    /* Explicit opt-in. The GUI can enable [Diagnostics] BackendTelemetryEnabled=1.
       The log location is stable across sessions but contains no private bytes. */
    g_backend_enabled=0;g_backend_path[0]=0;
    GetPrivateProfileStringA("Diagnostics","BackendTelemetryEnabled","0",v,sizeof(v),g_profile_path);
    if(parse_num(v,0)==1u){
        char base[400];U32 bn=GetEnvironmentVariableA("LOCALAPPDATA",base,sizeof(base));
        if(bn>0 && bn<sizeof(base) && bn+32<sizeof(g_backend_path)){
            str_copy(g_backend_path,base,sizeof(g_backend_path));
            str_append(g_backend_path,"\\VirtualCar",sizeof(g_backend_path));
            (void)CreateDirectoryA(g_backend_path,0);
            str_append(g_backend_path,"\\dev47-backend.jsonl",sizeof(g_backend_path));
            g_backend_enabled=1;
        }
    }
    GetPrivateProfileStringA("Vehicle","VIN","YV1CZ0002A0000001",v,sizeof(v),g_profile_path);
    if(str_len(v)==17)str_copy(g_vin,v,sizeof(g_vin));
    GetPrivateProfileStringA("Vehicle","BatteryMv","12500",v,sizeof(v),g_profile_path);
    g_battery_mv=parse_num(v,12500);
    GetPrivateProfileStringA("Vehicle","EmitIsoRxStart","0",v,sizeof(v),g_profile_path);
    g_iso_rx_start=parse_num(v,0)?1:0;
    GetPrivateProfileStringA("Diagnostics","StrictJ2534Filters","0",v,sizeof(v),g_profile_path);
    g_strict_j2534_filters=parse_num(v,0)==1u?1u:0u;
    g_passive_enabled=0;
    GetPrivateProfileStringA("PassiveCAN","Enabled","0",v,sizeof(v),g_profile_path);
    g_passive_enabled=parse_num(v,0)?1:0;
    GetPrivateProfileStringA("PassiveCAN","FrameId","555",v,sizeof(v),g_profile_path);
    g_passive_id=parse_hex(v,0x555);
    if(g_passive_id>0x1FFFFFFFu)g_passive_enabled=0;
    GetPrivateProfileStringA("PassiveCAN","PeriodMs","50",v,sizeof(v),g_profile_path);
    g_passive_period_ms=parse_num(v,50);
    if(g_passive_period_ms<20)g_passive_period_ms=20;
    if(g_passive_period_ms>5000)g_passive_period_ms=5000;
    GetPrivateProfileStringA("PassiveCAN","FrameData","56 43 41 52 4C 41 42 00",v,sizeof(v),g_profile_path);
    if(!parse_frame8(v,g_passive_payload))g_passive_enabled=0;
    GetPrivateProfileStringA("Vehicle","ECUCount","2",v,sizeof(v),g_profile_path);
    g_ecu_count=parse_num(v,2);if(g_ecu_count<1||g_ecu_count>MAX_ECUS)g_ecu_count=1;
    for(i=0;i<g_ecu_count;i++){
        key[0]='E';key[1]='C';key[2]='U';key[3]=(char)('0'+i);key[4]=0;
        GetPrivateProfileStringA(key,"RequestId",i==1?"726":"7E0",v,sizeof(v),g_profile_path);
        g_ecu[i].req=parse_hex(v,i==1?0x726:0x7E0);
        GetPrivateProfileStringA(key,"ResponseId",i==1?"72E":"7E8",v,sizeof(v),g_profile_path);
        g_ecu[i].resp=parse_hex(v,i==1?0x72E:0x7E8);
        GetPrivateProfileStringA(key,"PartNumber","VIRTUAL-ECU",g_ecu[i].part,sizeof(g_ecu[i].part),g_profile_path);
        GetPrivateProfileStringA(key,"Software","SIM-1.0",g_ecu[i].sw,sizeof(g_ecu[i].sw),g_profile_path);
        /* Opt-in read-only, synthetic laboratory replies. No assumption about
           the OEM meaning or encoding of F1B0 and F1A3 is made. */
        GetPrivateProfileStringA(key,"DIDF1B0Hex","",v,sizeof(v),g_profile_path);
        g_ecu[i].extra_len[0]=parse_hex_blob(v,g_ecu[i].extra_did[0],MAX_EXTRA_DID);
        GetPrivateProfileStringA(key,"DIDF1A3Hex","",v,sizeof(v),g_profile_path);
        g_ecu[i].extra_len[1]=parse_hex_blob(v,g_ecu[i].extra_did[1],MAX_EXTRA_DID);
        /* Optional, exact read-only DID responses for verified ECU captures.
           Data are never synthesized from the VIN or another ECU's fixtures.
           Allow only the F1xx identification range; reserved/special DIDs
           retain their explicitly implemented handlers. */
        {U32 slot;
         for(slot=0;slot<MAX_EXTRA_DID_SLOTS;slot++){
             char kcode[20],kbytes[20];
             str_copy(kcode,"DID0Code",sizeof(kcode));kcode[3]=(char)('0'+slot);
             str_copy(kbytes,"DID0Hex",sizeof(kbytes));kbytes[3]=(char)('0'+slot);
             GetPrivateProfileStringA(key,kcode,"",v,sizeof(v),g_profile_path);
             g_ecu[i].did_code[slot]=parse_hex(v,0xFFFFFFFFu);
             if(g_ecu[i].did_code[slot]<0xF100u||g_ecu[i].did_code[slot]>0xF1FFu ||
                g_ecu[i].did_code[slot]==0xF114u||g_ecu[i].did_code[slot]==0xF190u||
                g_ecu[i].did_code[slot]==0xF1B0u||g_ecu[i].did_code[slot]==0xF1A3u){
                 g_ecu[i].did_code[slot]=0;continue;
             }
             GetPrivateProfileStringA(key,kbytes,"",v,sizeof(v),g_profile_path);
             g_ecu[i].did_len[slot]=parse_hex_blob(v,g_ecu[i].did_bytes[slot],MAX_EXTRA_DID);
             if(!g_ecu[i].did_len[slot])g_ecu[i].did_code[slot]=0;
         }}
    }
    /* P2 D2 fixtures: 40/50 CEM x B9FB (vehicle information), B9F0
       (module part number), B9FC (vehicle configuration). No response is
       fabricated when a fixture is absent.
       B9FB response CAN ID 0x01200003 is from a published 2005-era DiCE trace;
       not guaranteed for every P2 model or CAN bus. */
    GetPrivateProfileStringA("P2","StrictRouting","0",v,sizeof(v),g_profile_path);
    g_p2_strict_routing=parse_num(v,0)?1:0;
    /* Recorded bus traffic: exact source frames are configured per network.
       Never enable the trace through a guessed vehicle or part number. */
    bytes_zero(g_trace,sizeof(g_trace));g_trace_count=0;
    GetPrivateProfileStringA("PassiveTrace","Enabled","0",v,sizeof(v),g_profile_path);
    if(parse_num(v,0)==1){
        U32 j,cnt;
        GetPrivateProfileStringA("PassiveTrace","Count","0",v,sizeof(v),g_profile_path);
        cnt=parse_num(v,0);if(cnt>MAX_PASSIVE_TRACES)cnt=0;
        for(j=0;j<cnt;j++){
            char section[24];TRACE_FRAME *t=&g_trace[j];
            str_copy(section,"Trace",sizeof(section));
            {char suffix[3];suffix[0]=(char)('0'+j/10);suffix[1]=(char)('0'+j%10);suffix[2]=0;
             if(j<10)str_append(section,suffix+1,sizeof(section));
             else str_append(section,suffix,sizeof(section));}
            GetPrivateProfileStringA(section,"Id","",v,sizeof(v),g_profile_path);
            t->id=parse_hex(v,0xFFFFFFFFu);
            GetPrivateProfileStringA(section,"Baud","",v,sizeof(v),g_profile_path);
            t->baud=parse_num(v,0);
            GetPrivateProfileStringA(section,"PeriodMs","100",v,sizeof(v),g_profile_path);
            t->period_ms=parse_num(v,0);
            GetPrivateProfileStringA(section,"Data","",v,sizeof(v),g_profile_path);
            if(t->id<=0x1FFFFFFFu && (t->baud==125000u||t->baud==500000u) &&
               t->period_ms>=20u && t->period_ms<=5000u && parse_frame8(v,t->data)){
                t->enabled=1;g_trace_count++;
            }else logline("PassiveTrace invalid recorded frame ignored",0,0);
        }
    }
    GetPrivateProfileStringA("P2","ReplaySpacingMs","12",v,sizeof(v),g_profile_path);
    g_d2_spacing_ms=parse_num(v,12);
    if(g_d2_spacing_ms>250)g_d2_spacing_ms=250;
    for(i=0;i<MAX_D2_FIXTURES;i++){
        U32 j,configured,valid=0;char section[24],entry[32];
        D2_PROFILE *d=&g_d2[i];bytes_zero(d,sizeof(*d));
        /* Preserve legacy fixture indices 0..3 for backwards compatibility.
           New indices 4 and 5 are verified-FC replay slots. */
        d->target=(U8)((i==0||i==1||i==4)?0x40:0x50);
        d->subcommand=(U8)(i>=4?0xFC:((i%2)==0?0xFB:0xF0));
        d->baud=(d->target==0x40?125000u:500000u);
        if(i>=BASE_D2_FIXTURES){
            char digits[3];U32 target,opcode;
            str_copy(section,"D2_Node",sizeof(section));
            digits[0]=(char)('0'+i-BASE_D2_FIXTURES);digits[1]=0;
            str_append(section,digits,sizeof(section));
            GetPrivateProfileStringA(section,"Enabled","0",v,sizeof(v),g_profile_path);
            if(parse_num(v,0)!=1)continue;
            GetPrivateProfileStringA(section,"Target","",v,sizeof(v),g_profile_path);
            target=parse_hex(v,0xFFFFFFFFu);
            GetPrivateProfileStringA(section,"Opcode","",v,sizeof(v),g_profile_path);
            opcode=parse_hex(v,0xFFFFFFFFu);
            GetPrivateProfileStringA(section,"Baud","",v,sizeof(v),g_profile_path);
            d->baud=parse_num(v,0);
            if(target>0xFFu||target==0x40u||target==0x50u||
               (opcode!=0xF0u&&opcode!=0xFBu&&opcode!=0xFCu)||
               (d->baud!=125000u&&d->baud!=500000u)){
                logline("D2 extra ECU fixture invalid target/opcode/baud ignored",0,0);
                continue;
            }
            d->target=(U8)target;d->subcommand=(U8)opcode;
        }
        /* Keep the old B9FB section names for existing users. */
        if(i==0)str_copy(section,"D2_40",sizeof(section));
        else if(i==2)str_copy(section,"D2_50",sizeof(section));
        else if(i==1)str_copy(section,"D2_40_B9F0",sizeof(section));
        else if(i==3)str_copy(section,"D2_50_B9F0",sizeof(section));
        else if(i==4)str_copy(section,"D2_40_B9FC",sizeof(section));
        else if(i==5)str_copy(section,"D2_50_B9FC",sizeof(section));
        /* For optional D2_Node slots, section is already assigned above. */
        d->response_id=(d->target==0x40?0x00800003u:0x01000003u);
        if(d->target==0x50 && d->subcommand==0xFB)d->response_id=0x01200003u;
        GetPrivateProfileStringA(section,"ResponseId","",v,sizeof(v),g_profile_path);
        d->response_id=parse_hex(v,i>=BASE_D2_FIXTURES?0xFFFFFFFFu:d->response_id);
        if(d->response_id>0x1FFFFFFFu){
            if(i>=BASE_D2_FIXTURES)logline("D2 extra ECU invalid ResponseId ignored",0,0);
            continue;
        }
        GetPrivateProfileStringA(section,"FrameCount","",v,sizeof(v),g_profile_path);
        if(!v[0] && d->subcommand==0xFB)
            GetPrivateProfileStringA(section,"B9FBFrameCount","0",v,sizeof(v),g_profile_path);
        configured=parse_num(v,0);if(configured>MAX_D2_FRAMES)configured=0;
        for(j=0;j<configured;j++){
            /* Hex indices 0..3F; legacy 0..F keys remain unchanged. */
            str_copy(entry,d->subcommand==0xFB?"B9FBFrame":"Frame",sizeof(entry));
            {U32 pos=str_len(entry);static const char h[]="0123456789ABCDEF";
             if(j>=16)entry[pos++]=h[(j>>4)&15];
             entry[pos++]=h[j&15];entry[pos]=0;}
            GetPrivateProfileStringA(section,entry,"",v,sizeof(v),g_profile_path);
            if(!v[0] && d->subcommand==0xFB){
                str_copy(entry,"Frame",sizeof(entry));
                {U32 pos=str_len(entry);static const char h[]="0123456789ABCDEF";
                 if(j>=16)entry[pos++]=h[(j>>4)&15];
                 entry[pos++]=h[j&15];entry[pos]=0;}
                GetPrivateProfileStringA(section,entry,"",v,sizeof(v),g_profile_path);
            }
            if(!parse_frame8(v,d->frame[j]))break;
            valid++;
        }
        if(valid==configured)d->frame_count=valid;
    }
    /* B9FC fixtures with the studied 140-parameter layout are additionally
       checked against their observed one-byte sum. This is not an OEM-wide
       checksum specification; unsupported FC shapes are disabled rather than
       guessed. Other fixtures are checked for D2 framing only. */
    U32 invalid_p2=0;
    for(i=0;i<MAX_D2_FIXTURES;i++){
        U32 j;D2_PROFILE *d=&g_d2[i];
        /* Do not permit duplicate optional targets to shadow the first match. */
        if(i>=BASE_D2_FIXTURES && d->frame_count)
            for(j=0;j<i;j++)if(g_d2[j].frame_count && g_d2[j].target==d->target &&
                g_d2[j].subcommand==d->subcommand){d->frame_count=0;invalid_p2++;break;}
        if(d->frame_count && (!validate_d2_fixture(d) || !validate_fc140_fixture(d))){
            d->frame_count=0;invalid_p2++;
        }
    }
    n=GetTempPathA(sizeof(g_log_path)-32,g_log_path);
    if(n==0||n>=sizeof(g_log_path)-32)str_copy(g_log_path,"C:\\Windows\\Temp\\SectorVVirtualCar.log",sizeof(g_log_path));
    else str_append(g_log_path,"SectorVVirtualCar.log",sizeof(g_log_path));
    logline("VirtualCar DLL initialized (v0.3.6.6 extended configuration DID)",0,0);
    {U8 network_counts[8];U32 active_extra=0,k;
     for(k=BASE_D2_FIXTURES;k<MAX_D2_FIXTURES;k++)if(g_d2[k].frame_count)active_extra++;
     u32_be(network_counts,g_trace_count);u32_be(network_counts+4,active_extra);
     logline("Network ACTIVE passive frames / extra D2 fixtures (BE)",network_counts,8);}
    if(invalid_p2){U8 number[4];u32_be(number,invalid_p2);
        logline("P2 invalid D2 fixtures disabled (count, BE)",number,4);}
    {
        U8 opts[16];u32_be(opts,g_passive_enabled);u32_be(opts+4,g_passive_period_ms);
        u32_be(opts+8,g_iso_rx_start);u32_be(opts+12,g_p2_strict_routing);
        logline("Lab options passive-CAN / interval-ms / ISO-RxStart / P2 strict routing (BE)",opts,16);
    }
    /* Show the active configuration loaded by the *client* process, not just
       the GUI's expected directory. This resolves stale Registry32 paths. */
    {
        char detail[320];U8 lengths[8];
        str_copy(detail,"Active INI: ",sizeof(detail));
        str_append(detail,g_profile_path,sizeof(detail));
        logline(detail,0,0);
        u32_be(lengths,g_ecu_count>1?g_ecu[1].extra_len[0]:0);
        u32_be(lengths+4,g_ecu_count>1?g_ecu[1].extra_len[1]:0);
        logline("ECU1 fixture lengths F1B0 / F1A3 (BE)",lengths,8);
        {U32 k;for(k=0;k<MAX_D2_FIXTURES;k++){
            U8 meta[16];u32_be(meta,g_d2[k].target);u32_be(meta+4,g_d2[k].subcommand);
            u32_be(meta+8,g_d2[k].response_id);u32_be(meta+12,g_d2[k].frame_count);
            logline("P2 fixture target/opcode/response-id/frame-count (BE)",meta,16);
        }}
    }
}
static CHANNEL *channel(U32 id){U32 i;for(i=0;i<MAX_CHANNELS;i++)if(g_ch[i].used&&g_ch[i].id==id)return &g_ch[i];return 0;}
/* Strict policy compares CAN ID (first four bytes) and optional raw CAN data.
   ISO15765 is already reassembled in this laboratory simulator, so only the
   flow-control filter's response CAN ID is matched. Extended ISO addressing
   and actual hardware CAN Flow Control are not implemented here. */
static U32 can_id_from_data(const U8 *data){
    return ((U32)data[0]<<24)|((U32)data[1]<<16)|((U32)data[2]<<8)|(U32)data[3];
}
static int strict_filter_matches(const FILTER *f,U32 response_id,const U8 *payload,U32 len){
    U8 idbytes[4];U32 j;
    if(f->length<4u||f->length>12u||f->length>len+4u)return 0;
    u32_be(idbytes,response_id);
    for(j=0;j<f->length;j++){
        U8 value=j<4u?idbytes[j]:payload[j-4u];
        if((value&f->mask[j])!=(f->pattern[j]&f->mask[j]))return 0;
    }
    return 1;
}
static int filter_allows(const CHANNEL *c,U32 response_id,const U8 *payload,U32 len){
    U8 idbytes[4];U32 i,j;int has_pass=0,matched_pass=0;
    if(g_strict_j2534_filters){
        for(i=0;i<c->filters_count;i++){
            const FILTER *f=&c->filters[i];
            if(!strict_filter_matches(f,response_id,payload,len))continue;
            if(c->protocol==PROTO_ISO15765){
                if(f->type==3u)return 1;
            } else if(c->protocol==PROTO_CAN){
                if(f->type==2u)return 0;
                if(f->type==1u)matched_pass=1;
            }
        }
        return c->protocol==PROTO_CAN?matched_pass:0;
    }
    /* Historical compatibility: unfiltered CAN/ISO15765 RX is admitted.
       This branch must stay bit-for-bit equivalent in effect for existing labs. */
    u32_be(idbytes,response_id);
    for(i=0;i<c->filters_count;i++){
        const FILTER *f=&c->filters[i];int matched=1;
        for(j=0;j<4;j++)if((idbytes[j]&f->mask[j])!=(f->pattern[j]&f->mask[j])){matched=0;break;}
        if(f->type==2 && matched)return 0;
        if(f->type==1 || f->type==3){has_pass=1;if(matched)matched_pass=1;}
    }
    return !has_pass || matched_pass;
}
static void note_filter_reject(CHANNEL *c,U32 response_id){
    U8 idbytes[4];u32_be(idbytes,response_id);
    backend_event(c,c->active_trace,"filter_drop","UNKNOWN","filter_reject","unknown");
    backend_note_drop(c,c->active_trace,BACKEND_DROP_FILTER_REJECT);
    logline("RX discarded by installed J2534 filter",idbytes,4);
}
static int strict_iso_fc_route_matches(const CHANNEL *c,U32 response_id,U32 request_id,
                                        const U8 *payload,U32 len){
    U32 i,j;
    for(i=0;i<c->filters_count;i++){
        const FILTER *f=&c->filters[i];
        if(f->type!=3u || !strict_filter_matches(f,response_id,payload,len))continue;
        /* A broad RX mask may authorize multiple SingleFrames, not a
           segmented reply with one ambiguous physical CTS destination. */
        for(j=0;j<4u;j++)if(f->mask[j]!=0xFFu)break;
        if(j!=4u)continue;
        if(can_id_from_data(f->flow_id)!=request_id)continue;
        return 1;
    }
    return 0;
}
static void enqueue_status(CHANNEL *c,U32 response_id,const U8 *payload,U32 len,U32 status) {
    PASSTHRU_MSG *msg;U32 i;
    if(c->count>=MAX_QUEUE||len>MAX_DATA-4){
        U32 cause=c->count>=MAX_QUEUE?BACKEND_DROP_QUEUE_FULL:BACKEND_DROP_INVALID_SIZE;
        backend_event(c,c->active_trace,"rx_dropped","UNKNOWN",
                      backend_drop_cause(cause),"unknown");
        backend_note_drop(c,c->active_trace,cause);
        return;
    }
    if(!filter_allows(c,response_id,payload,len)){
        note_filter_reject(c,response_id);
        return;
    }
    msg=&c->queue[c->w];bytes_zero(msg,sizeof(*msg));
    msg->ProtocolID=c->protocol;msg->RxStatus=(response_id>0x7FF?CAN_29BIT_ID:0)|status;
    /* J2534 v04.04 Timestamp is in MICROSECONDS, not GetTickCount() milliseconds.
       A wrapping 32-bit free-running clock is normal for J2534. */
    msg->Timestamp=(U32)now_us();
    msg->DataSize=len+4;
    /* Ordinary RX: no extra bytes, therefore ExtraDataIndex == DataSize.
       START_OF_MESSAGE is an indication, for which the index must be zero. */
    msg->ExtraDataIndex=(status&START_OF_MESSAGE)?0:msg->DataSize;
    msg->Data[0]=(U8)(response_id>>24);msg->Data[1]=(U8)(response_id>>16);
    msg->Data[2]=(U8)(response_id>>8);msg->Data[3]=(U8)response_id;
    for(i=0;i<len;i++)msg->Data[4+i]=payload[i];
    c->queue_d2_gen[c->w]=0;c->queue_d2_frame[c->w]=0;c->queue_ready_us[c->w]=0;
    c->queue_trace[c->w]=c->active_trace;
    c->w=(c->w+1)%MAX_QUEUE;c->count++;
    backend_event(c,c->active_trace,"filter_pass","UNKNOWN","none","unknown");
    backend_event(c,c->active_trace,"rx_queued","UNKNOWN","none","unknown");
    logline(status==START_OF_MESSAGE?"RX START_OF_MESSAGE (ISO15765)":"RX (simulated)",msg->Data,msg->DataSize);
}
static void enqueue(CHANNEL *c,U32 response_id,const U8 *payload,U32 len){enqueue_status(c,response_id,payload,len,0);}
/* Bus-specific recorded traffic. Never cross CAN-LS/HS speed boundaries. */
static void pump_recorded_trace(CHANNEL *c){
    U32 i,now;
    if(c->protocol!=PROTO_CAN)return;
    now=GetTickCount();
    for(i=0;i<MAX_PASSIVE_TRACES;i++){
        TRACE_FRAME *t=&g_trace[i];
        if(!t->enabled||t->baud!=c->baud||c->count>=MAX_QUEUE)continue;
        if((U32)(now-c->trace_next_tick[i])>=0x80000000u)continue;
        c->trace_next_tick[i]=now+t->period_ms;
        enqueue(c,t->id,t->data,8);
        logline("Passive CAN recorded fixture replay (not OEM-authenticated)",0,0);
    }
}
static void maybe_passive_frame(CHANNEL *c){
    U32 now;
    if(!g_passive_enabled||c->protocol!=PROTO_CAN||c->count>=MAX_QUEUE)return;
    now=GetTickCount();
    if((U32)(now-c->passive_next_tick)>=0x80000000u)return;
    c->passive_next_tick=now+g_passive_period_ms;
    enqueue(c,g_passive_id,g_passive_payload,8);
    logline("Passive CAN lab traffic tick (synthetic VCARLAB, not vehicle ignition)",0,0);
}
/* Only a matching ECU Flow Control CTS grants Consecutive Frames.
   Preserve remaining credit if J2534 RX FIFO is full. STmin is scheduled
   using the existing microsecond clock and the queue-ready timestamp. */
static void pump_can_cf(CHANNEL *c) {
    U8 f[8];U32 i,sz;U64 now,due;
    if(c->protocol!=PROTO_CAN || !c->pending_cf_active || !c->pending_len)return;
    while(c->pending_cf_active && c->pending_pos<c->pending_len && c->count<MAX_QUEUE){
        sz=c->pending_len-c->pending_pos;if(sz>7)sz=7;
        bytes_zero(f,8);f[0]=(U8)(0x20 | (c->pending_sn&15));
        for(i=0;i<sz;i++)f[i+1]=c->pending[c->pending_pos+i];
        now=now_us();due=c->pending_next_us>now?c->pending_next_us:now;
        {U32 slot=c->w,before=c->count;U64 previous=c->active_trace;c->active_trace=c->pending_trace;
         enqueue(c,c->pending_id,f,8);c->active_trace=previous;
         if(c->count>before){c->queue_ready_us[slot]=due;c->queue[slot].Timestamp=(U32)due;}}
        c->pending_next_us=due+(U64)c->pending_stmin_us;
        c->pending_pos+=sz;c->pending_sn++;
        if(c->pending_cf_credit && --c->pending_cf_credit==0)
            c->pending_cf_active=0;
    }
    if(c->pending_pos==c->pending_len){
        U64 previous=c->pending_trace;
        c->pending_len=0;c->pending_pos=0;c->pending_request_id=0;
        c->pending_trace=0;c->pending_next_us=0;c->pending_stmin_us=0;
        c->pending_cf_active=0;c->pending_cf_credit=0;
        backend_end_if_drained(c,previous);
    }
}
static void send_can_cf(CHANNEL *c,U32 block_size) {
    c->pending_cf_active=1;
    c->pending_cf_credit=block_size; /* BS=0: unlimited until final CF. */
    pump_can_cf(c);
}
static void emit_response(CHANNEL *c,U32 response_id,U32 fc_request_id,const U8 *payload,U32 len) {
    U8 f[8];U32 i;
    backend_event(c,c->active_trace,"response_generated","UNKNOWN","none","unknown");
    /* This compact simulator has only one outstanding segmented response per
       channel. Never release stale CFs from an earlier ECU request. */
    if(c->pending_len){
        U64 previous=c->pending_trace;
        logline("ISO-TP pending transfer superseded by a new ECU response",0,0);
        c->pending_len=0;c->pending_pos=0;c->pending_request_id=0;c->pending_trace=0;c->pending_next_us=0;c->pending_stmin_us=0;
        c->pending_cf_active=0;c->pending_cf_credit=0;
        backend_abort_pending(c,previous,BACKEND_ABORT_SUPERSEDED);
    }
    if(c->protocol==PROTO_ISO15765){
        /* Gate the optional START_OF_MESSAGE and the complete response
           together; never emit START_OF_MESSAGE for a rejected response. */
        if(g_strict_j2534_filters && !filter_allows(c,response_id,payload,len)){
            enqueue(c,response_id,payload,len);return;
        }
        if(g_strict_j2534_filters && len>7u){
            /* This emulator returns reassembled UDS data. Its synthetic
               segmentation must be authorized by one exact RX CAN ID and
               the physical ECU request CAN ID used for Flow Control.
               No real FC CTS is transmitted on CAN or USB. */
            if(!strict_iso_fc_route_matches(c,response_id,fc_request_id,payload,len)){
                note_filter_reject(c,response_id);
                return;
            }
            logline("ISO15765 synthetic multi-frame FC route verified (no CAN TX)",0,0);
        }
        /* START_OF_MESSAGE and its reassembled payload are one logical RX.
           In strict mode never enqueue only half when FIFO has one slot. */
        if(g_strict_j2534_filters && g_iso_rx_start && len>7u &&
           c->count>MAX_QUEUE-2u){
            backend_event(c,c->active_trace,"rx_dropped","UNKNOWN","queue_full","unknown");
            backend_note_drop(c,c->active_trace,BACKEND_DROP_QUEUE_FULL);
            logline("Strict ISO15765 RX pair dropped atomically (FIFO full)",0,0);
            return;
        }
        if(g_iso_rx_start && len>7 && c->count+2<=MAX_QUEUE)
            enqueue_status(c,response_id,0,0,START_OF_MESSAGE);
        enqueue(c,response_id,payload,len);return;
    }
    if(len<=7){bytes_zero(f,8);f[0]=(U8)len;for(i=0;i<len;i++)f[i+1]=payload[i];enqueue(c,response_id,f,8);return;}
    if(len>sizeof(c->pending))return;
    bytes_zero(f,8);f[0]=(U8)(0x10|(len>>8));f[1]=(U8)len;
    for(i=0;i<6;i++)f[i+2]=payload[i];
    enqueue(c,response_id,f,8);
    bytes_copy(c->pending,payload,len);c->pending_len=len;c->pending_pos=6;
    c->pending_id=response_id;c->pending_sn=1;c->pending_trace=c->active_trace;c->pending_next_us=0;c->pending_stmin_us=0;
}
static U32 answer_uds(const ECU *ecu,const U8 *req,U32 len,U8 *res) {
    U32 i,n;U8 service;
    if(len==0)return 0;
    service=req[0];
    if(service==0x22 && len>=3){
        /* Volvo P3 CEM identification requests F114 rather than the generic F190.
           The laboratory profile supplies a synthetic 17-byte ASCII VIN. The
           complete OEM response layout may vary by model and is not claimed. */
        if(req[1]==0xF1&&(req[2]==0x90||(req[2]==0x14&&ecu->req==0x726u))){
            res[0]=0x62;res[1]=0xF1;res[2]=req[2];
            for(i=0;i<17;i++)res[i+3]=(U8)g_vin[i];
            if(req[2]==0x14)logline("P3 CEM F114 VIN reply (synthetic lab data)",0,0);
            return 20;
        }
        /* Exact configured identification replies take precedence over
           synthetic F187/F189 labels, but cannot override VIN/F114 or B0/A3.
           Duplicate code slots: first explicit fixture wins. */
        {U32 did=((U32)req[1]<<8)|req[2];
         for(i=0;i<MAX_EXTRA_DID_SLOTS;i++)if(ecu->did_len[i]&&ecu->did_code[i]==did){
             res[0]=0x62;res[1]=req[1];res[2]=req[2];
             bytes_copy(res+3,ecu->did_bytes[i],ecu->did_len[i]);
             logline("Read-only configured ECU DID reply (not OEM verified)",req+1,2);
             return 3+ecu->did_len[i];
         }}
        if(req[1]==0xF1&&(req[2]==0x87||req[2]==0x89)){
            const char *s=req[2]==0x87?ecu->part:ecu->sw;n=str_len(s);if(n>48)n=48;
            res[0]=0x62;res[1]=0xF1;res[2]=req[2];for(i=0;i<n;i++)res[i+3]=(U8)s[i];return 3+n;
        }
        if(req[1]==0xF1&&(req[2]==0xB0||req[2]==0xA3)){
            U32 idx=req[2]==0xB0?0:1;
            if(ecu->extra_len[idx]){
                res[0]=0x62;res[1]=0xF1;res[2]=req[2];
                bytes_copy(res+3,ecu->extra_did[idx],ecu->extra_len[idx]);
                logline(idx==0?"P3 CEM F1B0 configured lab fixture":"P3 CEM F1A3 configured lab fixture",0,0);
                return 3+ecu->extra_len[idx];
            }
            logline(idx==0?"P3 CEM F1B0 unavailable (no fixture)":"P3 CEM F1A3 unavailable (no fixture)",0,0);
        }
        res[0]=0x7F;res[1]=service;res[2]=0x31;return 3;
    }
    if(service==0x10&&len>=2){res[0]=0x50;res[1]=req[1]&0x7F;res[2]=0x00;res[3]=0x32;res[4]=0x01;res[5]=0xF4;return 6;}
    if(service==0x3E){res[0]=0x7E;res[1]=len>=2?(req[1]&0x7F):0;return (len>=2&&(req[1]&0x80))?0:2;}
    if(service==0x09&&len>=2&&req[1]==0x02&&ecu->req==0x7E0u){res[0]=0x49;res[1]=0x02;res[2]=0x01;for(i=0;i<17;i++)res[i+3]=(U8)g_vin[i];return 20;}
    /* Never simulate unlocking, coding, resetting or ECU reflashing. */
    if(service==0x27||service==0x2E||service==0x31||service==0x34||service==0x36||service==0x37||service==0x11||service==0x14){
        res[0]=0x7F;res[1]=service;res[2]=0x33;return 3;
    }
    res[0]=0x7F;res[1]=service;res[2]=0x11;return 3;
}
/* A recorded D2 exchange must not leak already queued frames into the next
   B9FB attempt. Keep unrelated RX frames in FIFO order. */
static U32 drop_queued_d2(CHANNEL *c){
    U32 read,keep=0,dropped=0,original=c->count;
    for(read=0;read<original;read++){
        U32 from=(c->r+read)%MAX_QUEUE,to=(c->r+keep)%MAX_QUEUE;
        if(c->queue_d2_gen[from]){
            /* backend_cancel_channel emitted ordered rx_dropped evidence for
               this D2 retry before terminal; do not log it twice. */
            dropped++;continue;
        }
        if(to!=from){bytes_copy(&c->queue[to],&c->queue[from],sizeof(PASSTHRU_MSG));
            c->queue_d2_gen[to]=0;c->queue_d2_frame[to]=0;
            c->queue_trace[to]=c->queue_trace[from];c->queue_ready_us[to]=c->queue_ready_us[from];}
        keep++;
    }
    c->count=keep;c->w=(c->r+keep)%MAX_QUEUE;
    return dropped;
}
/* Precise schedule: increment by the configured period from the planned time,
   not the last polling tick. Delivery remains bounded by client polling. */
static void pump_d2(CHANNEL *c){
    U64 now;U32 slot;
    if(c->d2_pos>=c->d2_count || c->count>=MAX_QUEUE)return;
    now=now_us();
    if(now<c->d2_next_us)return;
    slot=c->w;
    {U64 previous=c->active_trace;c->active_trace=c->d2_trace;
     enqueue(c,c->d2_response_id,c->d2_frame[c->d2_pos],8);
     c->active_trace=previous;}
    /* Filters can discard a frame; never mark an older queue slot as new. */
    if(c->w!=slot){
        c->queue_d2_gen[slot]=c->d2_generation;
        c->queue_d2_frame[slot]=c->d2_pos+1;
    }
    c->d2_pos++;
    if(c->d2_pos>=c->d2_count){
        U64 finished=c->d2_trace;
        c->d2_count=0;c->d2_pos=0;c->d2_trace=0;
        backend_end_if_drained(c,finished);
    }
    else c->d2_next_us+=(U64)c->d2_spacing_ms*1000ull;
}
static int process_d2(CHANNEL *c,U32 id,const U8 *data,U32 len){
    U32 i;D2_PROFILE *d;const char *route;
    if(id!=0x000FFFFEu || c->protocol!=PROTO_CAN)return 0;
    /* Issue #4: A3/A6 are recognizable CEM *requests*, not implemented ECU
       responses. Keep them silent, but distinguish the known missing emulator
       implementation from an arbitrary CAN ID or an absent B9 fixture.
       Never synthesize E3/E6, an ignition state, or a module identity. */
    if(cem_d2_probe_shape(data,len)){
        backend_event(c,c->active_trace,"route_selected","CEM","none","unknown");
        /* The strict D2 bus policy already gates recorded B9 replies.
           Apply the same *read-only classification* to A3/A6 request
           shapes before calling an unsupported bus "unimplemented".
           This never creates any CEM response or changes loose mode. */
        if(g_p2_strict_routing &&
           ((data[1]==0x40u && c->baud!=125000u) ||
            (data[1]==0x50u && c->baud!=500000u))){
            logline("P2 D2 CEM A3/A6 strict bus mismatch: no response",0,0);
            backend_event(c,c->active_trace,"request_completed","CEM",
                          "unsupported_bus","no_response");
        }else{
            logline("P2 D2 CEM A3/A6: no verified response implementation",0,0);
            backend_event(c,c->active_trace,"request_completed","CEM",
                          "unimplemented_probe","no_response");
        }
        return 1;
    }
    if(len<4 || data[0]!=0xCBu || data[2]!=0xB9u ||
       (data[3]!=0xFBu&&data[3]!=0xF0u&&data[3]!=0xFCu))return 0;
    route=(data[1]==0x40u||data[1]==0x50u)?"CEM":"ECU_OTHER";
    backend_event(c,c->active_trace,"route_selected",route,"none","unknown");
    {U8 detail[16];
     u32_be(detail,data[1]);u32_be(detail+4,data[3]);
     u32_be(detail+8,c->baud);u32_be(detail+12,c->flags);
     logline("P2 D2 request target/opcode/baud/flags (BE)",detail,16);}
    for(i=0;i<MAX_D2_FIXTURES;i++){
        U32 j,discarded;
        d=&g_d2[i];if(data[1]!=d->target||data[3]!=d->subcommand)continue;
        backend_cancel_channel(c,"d2_superseded",1);
        c->d2_count=0;c->d2_pos=0;c->d2_trace=0;
        discarded=drop_queued_d2(c);
        if(discarded){U8 count_be[4];u32_be(count_be,discarded);
            logline("P2 D2 stale queued frames dropped (BE)",count_be,4);}
        if((g_p2_strict_routing || i>=BASE_D2_FIXTURES) && c->baud!=d->baud){
            logline("P2 D2 strict route rejected (no fixture emitted)",data,4);
            backend_event(c,c->active_trace,"request_completed",route,"unsupported_bus","no_response");
            return 1;
        }
        if(d->frame_count){
            c->d2_trace=c->active_trace;
            backend_event(c,c->active_trace,"response_generated",route,"none","unknown");
            c->d2_generation++;
            if(!c->d2_generation)c->d2_generation=1;
            c->d2_response_id=d->response_id;c->d2_count=d->frame_count;
            c->d2_spacing_ms=g_d2_spacing_ms;c->d2_next_us=now_us();
            for(j=0;j<d->frame_count;j++)bytes_copy(c->d2_frame[j],d->frame[j],8);
            logline("P2 D2 read-only recorded frames staged",data,4);
            pump_d2(c);
        }else {
            logline("P2 D2 read command: no validated response fixture",data,4);
            backend_event(c,c->active_trace,"request_completed",route,"missing_profile","no_response");
        }
        return 1;
    }
    logline("P2 D2 command: no recorded ECU fixture for target",data,4);
    backend_event(c,c->active_trace,"request_completed",route,"missing_profile","no_response");
    return 1;
}
static void process_request(CHANNEL *c,const PASSTHRU_MSG *msg){
    U32 id,i,n,sz;U8 payload[256],answer[256];const ECU *ecu;
    const char *route;
    int matched=0,answered=0;
    const U8 *data;
    if(msg->DataSize<5||msg->DataSize>MAX_DATA)return;
    id=((U32)msg->Data[0]<<24)|((U32)msg->Data[1]<<16)|((U32)msg->Data[2]<<8)|msg->Data[3];
    if(process_d2(c,id,msg->Data+4,msg->DataSize-4))return;
    /* FF C8 is documented as a broadcast ECU reset in published P2 logs.
       We do not emulate a physical reset or fabricate an acknowledgment. */
    if(id==0x000FFFFEu && msg->DataSize>=6 && msg->Data[4]==0xFF && msg->Data[5]==0xC8){
        logline("P2 FF C8 broadcast reset: no physical ECU; intentionally silent",msg->Data,msg->DataSize);
        backend_event(c,c->active_trace,"route_selected","CEM","none","unknown");
        backend_event(c,c->active_trace,"request_completed","CEM","no_response","no_response");
        return;
    }
    for(i=0;i<g_ecu_count;i++){
        ecu=&g_ecu[i];if(id!=ecu->req&&id!=0x7DF)continue;
        n=msg->DataSize-4;data=msg->Data+4;
        if(c->protocol==PROTO_CAN){
            if((data[0]&0xF0)==0x30 && c->pending_len){
                if(n<3){
                    logline("ISO-TP FC ignored (missing block size or STmin)",msg->Data,msg->DataSize);
                    return;
                }
                if(id!=c->pending_request_id){
                    logline("ISO-TP FC ignored (different request CAN ID)",msg->Data,msg->DataSize);
                    return;
                }
                if((data[0]&15)==1){
                    /* WAIT suspends an outstanding grant; another CTS is required. */
                    c->pending_cf_active=0;c->pending_cf_credit=0;
                    logline("ISO-TP FC WAIT received",msg->Data,msg->DataSize);return;
                }
                if((data[0]&15)==2){
                    U64 previous=c->pending_trace;
                    logline("ISO-TP FC OVERFLOW received; pending response discarded",msg->Data,msg->DataSize);
                    c->pending_len=0;c->pending_pos=0;c->pending_request_id=0;c->pending_trace=0;c->pending_next_us=0;c->pending_stmin_us=0;
                    c->pending_cf_active=0;c->pending_cf_credit=0;
                    backend_abort_pending(c,previous,BACKEND_ABORT_FC_OVERFLOW);
                    return;
                }
                if((data[0]&15)!=0){logline("ISO-TP FC invalid status",msg->Data,msg->DataSize);return;}
                if((data[2]>=0x80 && data[2]<=0xF0) || data[2]>=0xFA){
                    logline("ISO-TP FC ignored (reserved STmin)",msg->Data,msg->DataSize);
                    return;
                }
                c->pending_stmin_us=data[2]<=0x7F?(U32)data[2]*1000u:(U32)(data[2]-0xF0u)*100u;
                logline("ISO-TP FC CTS received; sending bounded CFs",msg->Data,msg->DataSize);
                send_can_cf(c,n>=2?data[1]:0);return;
            }
            if((data[0]&0xF0)!=0 || n<2)continue;
            sz=data[0]&0x0F;if(sz==0||sz>n-1||sz>sizeof(payload))continue;
            bytes_copy(payload,data+1,sz);n=sz;
        }else if(n<=sizeof(payload)){bytes_copy(payload,data,n);}
        else continue;
        /* One physical route must survive a silent completion. Functional
           fanout is a single aggregate transaction, not conflicting ECU routes. */
        route=id==0x7DFu?"ECU_OTHER":
              (ecu->req==0x726u?"CEM":(ecu->req==0x7E0u?"ECM":"ECU_OTHER"));
        if(!matched)backend_event(c,c->active_trace,"route_selected",route,"none","unknown");
        matched=1;
        /* Never synthesize acknowledgments for protected functional requests:
           functional diagnostic resets and protected services are not supported.
           This also prevents the prior contradictory 'Unmatched' log line. */
        if(id==0x7DF && n && (payload[0]==0x11||payload[0]==0x27||payload[0]==0x2E||payload[0]==0x31||payload[0]==0x34||payload[0]==0x36||payload[0]==0x37||payload[0]==0x14)){
            /* 0x11 0x81 requests hard reset with positive response suppressed.
               No actual reset is possible here, and silence is intentional. */
            if(n>=2 && payload[0]==0x11 && payload[1]==0x81)
                logline("Functional ECUReset 11 81: silent, no physical ECU to reset",msg->Data,msg->DataSize);
            else logline("Functional protected request ignored by lab emulator",msg->Data,msg->DataSize);
            backend_event(c,c->active_trace,"request_completed",route,"no_response","no_response");
            return;
        }
        sz=answer_uds(ecu,payload,n,answer);
        if(sz){answered=1;emit_response(c,ecu->resp,id==0x7DFu?ecu->req:id,answer,sz);if(c->pending_len)c->pending_request_id=id;
            /* Functional requests visit every configured ECU. Complete their
               shared telemetry record only after all responders were checked. */
            if(id!=0x7DF)backend_end_if_drained(c,c->active_trace);
        }
        else if(id!=0x7DF)backend_event(c,c->active_trace,"request_completed",route,"no_response","no_response");
        if(id!=0x7DF)return;
    }
    if(id==0x7DF && matched){
        if(answered)backend_end_if_drained(c,c->active_trace);
        else backend_event(c,c->active_trace,"request_completed","ECU_OTHER","no_response","no_response");
    }
    if(!matched) {
        /* A missing P3 CEM profile is distinguishable from an arbitrary ID.
           Classify only the exact read-only F114 request on the two known
           P3 CEM addressing forms. This adds evidence, never an ECU reply. */
        if(c->protocol==PROTO_ISO15765 &&
           (id==0x726u || id==0x18DA50F1u) &&
           msg->DataSize==7u && msg->Data[4]==0x22u &&
           msg->Data[5]==0xF1u && msg->Data[6]==0x14u) {
            backend_event(c,c->active_trace,"route_selected","CEM","none","unknown");
            logline("P3 CEM F114 probe: no configured CEM fixture; no response",0,0);
            backend_event(c,c->active_trace,"request_completed","CEM",
                          "unimplemented_probe","no_response");
            return;
        }
        logline("Unmatched request ID / protocol, no response",msg->Data,msg->DataSize);
        backend_event(c,c->active_trace,"route_selected","UNHANDLED","none","unknown");
        backend_event(c,c->active_trace,"request_completed","UNHANDLED","unhandled_request","no_response");
    }
}

/* No physical bus: periodic requests are replayed only while the client
   polls ReadMsgs. Never spawn a background vehicle writer. */
static void pump_periodic(CHANNEL *c){
    U32 i;U64 now=now_us();
    for(i=0;i<MAX_PERIODIC;i++){
        PERIODIC *p=&c->periodic[i];
        if(!p->used || now<p->next_us || c->count>=MAX_QUEUE)continue;
        p->next_us=now+(U64)p->interval_ms*1000ull;
        logline("J2534 periodic TX (read-only simulator)",p->msg.Data,p->msg.DataSize);
        process_request(c,&p->msg);
    }
}
/* Standard 04.04 API. Undecorated export names are defined in virtualcar.def. */
EXPORT U32 WINCALL PassThruOpen(PTR name,U32 *device) {
    (void)name;if(!device)return error(ERR_NULL_PARAMETER);
    lock_state();if(g_open){unlock_state();return error(ERR_DEVICE_IN_USE);}
    g_open=1;bytes_zero(g_ch,sizeof(g_ch));p2_bridge_init(&g_vehicle_bridge);load_config();*device=1;
    logline("PassThruOpen -> device 1",0,0);unlock_state();return error(ERR_OK);
}
EXPORT U32 WINCALL PassThruClose(U32 device) {
    U32 i;
    if(device!=1||!g_open)return error(ERR_INVALID_DEVICE_ID);
    lock_state();
    for(i=0;i<MAX_CHANNELS;i++)if(g_ch[i].used)
        backend_cancel_channel(&g_ch[i],"device_close",0);
    g_open=0;bytes_zero(g_ch,sizeof(g_ch));p2_bridge_init(&g_vehicle_bridge);
    logline("PassThruClose",0,0);unlock_state();return error(ERR_OK);
}
EXPORT U32 WINCALL PassThruConnect(U32 device,U32 protocol,U32 flags,U32 baud,U32 *channel_id){
    U32 i;
    if(!channel_id)return connect_result(protocol,flags,baud,ERR_NULL_PARAMETER);
    if(!g_open||device!=1)return connect_result(protocol,flags,baud,ERR_INVALID_DEVICE_ID);
    /* P3Tool also contains driver-specific 0x8004/0x8005/0x10000001 modes.
       Do not silently reinterpret them as standard CAN/ISO15765. */
    if(protocol!=PROTO_CAN&&protocol!=PROTO_ISO15765)
        return connect_result(protocol,flags,baud,ERR_INVALID_PROTOCOL_ID);
    /* Zero cannot represent a configured CAN bit rate. Reject before
       allocating a channel or notifying the passive vehicle observer. */
    if(baud==0u)return connect_result(protocol,flags,baud,ERR_INVALID_BAUDRATE);
    lock_state();for(i=0;i<MAX_CHANNELS;i++)if(!g_ch[i].used)break;
    if(i==MAX_CHANNELS){unlock_state();return connect_result(protocol,flags,baud,ERR_EXCEEDED_LIMIT);}
    bytes_zero(&g_ch[i],sizeof(CHANNEL));g_ch[i].used=1;g_ch[i].id=i+1;
    g_ch[i].protocol=protocol;g_ch[i].flags=flags;g_ch[i].baud=baud;
    g_ch[i].passive_next_tick=GetTickCount()+g_passive_period_ms;
    {U32 k;for(k=0;k<MAX_PASSIVE_TRACES;k++)
        g_ch[i].trace_next_tick[k]=GetTickCount()+g_trace[k].period_ms+(k%4)*3u;}
    *channel_id=i+1;
    p2_bridge_connect(&g_vehicle_bridge,i+1,protocol,baud);
    {U8 details[12];u32_be(details,protocol);u32_be(details+4,flags);u32_be(details+8,baud);
     logline("PassThruConnect protocol / flags / baud (BE)",details,12);}
    unlock_state();return connect_result(protocol,flags,baud,ERR_OK);
}
EXPORT U32 WINCALL PassThruDisconnect(U32 id) {
    CHANNEL *c;lock_state();c=channel(id);if(!c){unlock_state();return error(ERR_INVALID_CHANNEL_ID);}
    {U8 channel_be[4];u32_be(channel_be,id);
     logline("PassThruDisconnect channel (BE)",channel_be,4);}
    backend_cancel_channel(c,"channel_disconnect",0);
    p2_bridge_disconnect(&g_vehicle_bridge,id);bytes_zero(c,sizeof(*c));logline("PassThruDisconnect",0,0);unlock_state();return error(ERR_OK);
}
EXPORT U32 WINCALL PassThruWriteMsgs(U32 id,const PASSTHRU_MSG *msgs,U32 *count,U32 timeout){
    U32 i,n;(void)timeout;if(!msgs||!count)return error(ERR_NULL_PARAMETER);
    lock_state();CHANNEL *c=channel(id);if(!c){unlock_state();return error(ERR_INVALID_CHANNEL_ID);}
    n=*count;if(n>64){unlock_state();return error(ERR_EXCEEDED_LIMIT);}
    for(i=0;i<n;i++){
        /* A channel's transport must agree with each J2534 message. Do not
           silently reinterpret CAN as ISO15765 (or vice versa) and create
           spurious CEM/ECU receive evidence on an unrelated route. */
        if(msgs[i].ProtocolID!=c->protocol){
            *count=i;unlock_state();return error(ERR_MSG_PROTOCOL_ID);
        }
        /* Classic CAN carries at most eight payload bytes after the 4-byte
           identifier; ISO15765 may hold a longer reassembled UDS payload. */
        if(msgs[i].DataSize>MAX_DATA||msgs[i].DataSize<5 ||
           (c->protocol==PROTO_CAN && msgs[i].DataSize>12u)){
            *count=i;unlock_state();return error(ERR_INVALID_MSG);
        }
        /* The J2534 data header contains a physical 11/29-bit CAN ID.
           Reject identifiers outside the 29-bit wire range *before*
           forwarding, logging or collecting ECU/discovery evidence.
           Keep legitimate high 29-bit P2 D2 IDs and normal ISO15765. */
        if((msgs[i].Data[0]&0xE0u)!=0u){
            *count=i;unlock_state();return error(ERR_INVALID_MSG);
        }
        /* Extended ISO15765 addressing needs a real fifth-byte transport
           mapping, not a silent normal-addressing UDS interpretation. */
        if(g_strict_j2534_filters && c->protocol==PROTO_ISO15765 &&
           (msgs[i].TxFlags&ISO15765_ADDR_TYPE)){
            *count=i;unlock_state();return error(ERR_NOT_SUPPORTED);
        }
        {U8 meta[20];u32_be(meta,id);u32_be(meta+4,c->protocol);
         u32_be(meta+8,msgs[i].TxFlags);u32_be(meta+12,c->baud);
         u32_be(meta+16,(U32)now_us());
         logline("TX context channel/protocol/flags/baud/time-us (BE)",meta,20);}
        logline("TX (app request)",msgs[i].Data,msgs[i].DataSize);
        /* The observer cannot affect J2534 return codes or ECU responses. */
        {
            p2_bridge_tx_result observed;
            if (p2_bridge_inspect_tx(&g_vehicle_bridge,id,msgs[i].TxFlags,
                    msgs[i].Data,msgs[i].DataSize,&observed) &&
                observed.label && observed.decision!=P2_CEM_KEEP_EXISTING)
                logline(observed.label,0,0);
        }
        /* Flow-control frames continue a previous response, not a new ECU
           diagnostic request. They are intentionally not assigned a new ID. */
        if(!(c->protocol==PROTO_CAN && msgs[i].DataSize>=5 &&
             (msgs[i].Data[4]&0xF0u)==0x30u)){
            c->active_trace=next_backend_request();
            backend_event(c,c->active_trace,"tx_received","UNKNOWN","none","unknown");
            backend_probe_event(c,c->active_trace,&msgs[i]);
        } else c->active_trace=0;
        process_request(c,&msgs[i]);
        c->active_trace=0;
    }
    *count=n;unlock_state();return error(ERR_OK);
}
EXPORT U32 WINCALL PassThruReadMsgs(U32 id,PASSTHRU_MSG *msgs,U32 *count,U32 timeout){
    U32 want,actual=0,started;if(!msgs||!count)return error(ERR_NULL_PARAMETER);
    /* NumMsgs is the caller buffer capacity; MAX_QUEUE is only our internal queue. */
    want=*count;if(want==0)return error(ERR_INVALID_MSG);
    started=GetTickCount();
    for(;;){
        CHANNEL *c;lock_state();c=channel(id);
        if(!c){unlock_state();return error(ERR_INVALID_CHANNEL_ID);}
        maybe_passive_frame(c);
        pump_recorded_trace(c);
        pump_periodic(c);
        pump_d2(c);
        pump_can_cf(c);
        while(c->count&&actual<want){
            if(c->queue_ready_us[c->r] && now_us()<c->queue_ready_us[c->r])break;
            bytes_copy(&msgs[actual],&c->queue[c->r],sizeof(PASSTHRU_MSG));
            {U8 meta[20];u32_be(meta,id);u32_be(meta+4,c->protocol);
             u32_be(meta+8,msgs[actual].RxStatus);u32_be(meta+12,c->baud);
             u32_be(meta+16,(U32)now_us());
             logline("RX context channel/protocol/status/baud/time-us (BE)",meta,20);}
            logline("PassThruReadMsgs -> delivered",msgs[actual].Data,msgs[actual].DataSize);
            /* Community LS signal inference is disabled by default. */
            if(g_vehicle_bridge.vehicle.cfg.enable_community_ls_signals)
                (void)p2_bridge_inspect_rx(&g_vehicle_bridge,id,msgs[actual].RxStatus,
                    msgs[actual].Data,msgs[actual].DataSize,
                    (U64)msgs[actual].Timestamp/1000u);
            if(c->queue_d2_gen[c->r]){
                U8 d2_meta[20];u32_be(d2_meta,id);u32_be(d2_meta+4,c->queue_d2_gen[c->r]);
                u32_be(d2_meta+8,c->queue_d2_frame[c->r]);
                u32_be(d2_meta+12,msgs[actual].Timestamp);u32_be(d2_meta+16,(U32)now_us());
                logline("P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE)",d2_meta,20);
                c->queue_d2_gen[c->r]=0;
            }
            if(c->protocol==PROTO_ISO15765){
                U8 meta[20];u32_be(meta,msgs[actual].ProtocolID);u32_be(meta+4,msgs[actual].RxStatus);
                u32_be(meta+8,msgs[actual].DataSize);u32_be(meta+12,msgs[actual].ExtraDataIndex);
                u32_be(meta+16,msgs[actual].Timestamp);
                logline("PassThruReadMsgs ISO15765 protocol/status/size/extra-index/timestamp-us (BE)",meta,20);
            }
            {U64 rid=c->queue_trace[c->r];
             backend_event(c,rid,"rx_dequeued","UNKNOWN","none","unknown");
             c->queue_trace[c->r]=0;c->queue_ready_us[c->r]=0;
             c->r=(c->r+1)%MAX_QUEUE;c->count--;actual++;
             /* Resume only previously granted CFs after this slot is freed. */
             pump_can_cf(c);
             backend_end_if_drained(c,rid);
            }
        }
        unlock_state();
        if(actual){
            lock_state();c=channel(id);if(c)c->read_timeout_count=0;unlock_state();
            *count=actual;return error(ERR_OK);
        }
        if((U32)(GetTickCount()-started)>=timeout){
            /* Record bounded timeout telemetry, not every polling call. */
            if(timeout){
                U32 failures=0; U8 info[12];
                lock_state();c=channel(id);if(c)failures=++c->read_timeout_count;unlock_state();
                if(failures<=3||(failures%25u)==0){
                    u32_be(info,id);u32_be(info+4,timeout);u32_be(info+8,failures);
                    logline("PassThruReadMsgs timeout: channel / wait-ms / consecutive-count (BE)",info,12);
                }
            }
            *count=0;return error(timeout?ERR_TIMEOUT:ERR_BUFFER_EMPTY);
        }
        Sleep(1);
    }
}
EXPORT U32 WINCALL PassThruStartMsgFilter(U32 id,U32 type,const PASSTHRU_MSG *mask,const PASSTHRU_MSG *pattern,const PASSTHRU_MSG *flow,U32 *filter_id){
    if(!filter_id||!mask||!pattern)return error(ERR_NULL_PARAMETER);
    lock_state();CHANNEL *c=channel(id);if(!c){unlock_state();return error(ERR_INVALID_CHANNEL_ID);}
    if(type<1||type>3){unlock_state();return error(ERR_INVALID_FLAGS);}
    if(g_strict_j2534_filters){
        if(c->protocol==PROTO_CAN && type==3u){unlock_state();return error(ERR_NO_FLOW_CONTROL);}
        if(c->protocol==PROTO_ISO15765 && type!=3u){unlock_state();return error(ERR_INVALID_FLAGS);}
        if(mask->ProtocolID!=c->protocol||pattern->ProtocolID!=c->protocol){
            unlock_state();return error(ERR_MSG_PROTOCOL_ID);
        }
        if(type==3u && !flow){unlock_state();return error(ERR_NULL_PARAMETER);}
        if(type==3u && flow->ProtocolID!=c->protocol){unlock_state();return error(ERR_MSG_PROTOCOL_ID);}
        if(c->protocol==PROTO_ISO15765 &&
           ((mask->TxFlags|pattern->TxFlags|(flow?flow->TxFlags:0u))&ISO15765_ADDR_TYPE)){
            unlock_state();return error(ERR_NOT_SUPPORTED);
        }
        if(mask->DataSize!=pattern->DataSize || mask->DataSize<4u ||
           (c->protocol==PROTO_ISO15765 && mask->DataSize!=4u) ||
           (c->protocol==PROTO_CAN && mask->DataSize>12u) ||
           (type==3u && flow->DataSize!=4u)){
            unlock_state();return error(ERR_INVALID_MSG);
        }
    } else if(mask->DataSize<4u||pattern->DataSize<4u){
        unlock_state();return error(ERR_INVALID_MSG);
    }
    /* 0x18: Pattern and FlowControl CAN IDs must not collide with either
       side of any existing ISO15765 FC filter on this channel. Overlapping
       RX masks are also ambiguous, including wildcard/specific pairs. */
    if(g_strict_j2534_filters && c->protocol==PROTO_ISO15765 && type==3u){
        U32 i,new_pattern=can_id_from_data(pattern->Data);
        U32 new_flow=can_id_from_data(flow->Data);
        U32 new_mask=can_id_from_data(mask->Data);
        for(i=0;i<c->filters_count;i++){
            const FILTER *f=&c->filters[i];
            U32 old_pattern,old_flow,old_mask;
            if(f->type!=3u)continue;
            old_pattern=can_id_from_data(f->pattern);
            old_flow=can_id_from_data(f->flow_id);
            old_mask=can_id_from_data(f->mask);
            if(new_pattern==old_pattern||new_pattern==old_flow||
               new_flow==old_pattern||new_flow==old_flow||
               (((new_pattern^old_pattern)&new_mask&old_mask)==0u)){
                unlock_state();return error(ERR_NOT_UNIQUE);
            }
        }
    }
    if(c->filters_count>=MAX_FILTERS){unlock_state();return error(ERR_EXCEEDED_LIMIT);}
    *filter_id=g_filter_counter++;
    {
        FILTER *f=&c->filters[c->filters_count++];U32 length=g_strict_j2534_filters?mask->DataSize:4u;
        bytes_zero(f,sizeof(*f));f->id=*filter_id;f->type=type;f->length=length;
        bytes_copy(f->mask,mask->Data,length);bytes_copy(f->pattern,pattern->Data,length);
        if(g_strict_j2534_filters && type==3u)bytes_copy(f->flow_id,flow->Data,4u);
    }
    {U8 descriptor[8];u32_be(descriptor,type);u32_be(descriptor+4,*filter_id);
     logline("PassThruStartMsgFilter type / id (BE)",descriptor,8);}
    if(mask && mask->DataSize<=MAX_DATA)
        logline("  filter mask",mask->Data,mask->DataSize);
    if(pattern && pattern->DataSize<=MAX_DATA)
        logline("  filter pattern",pattern->Data,pattern->DataSize);
    if(flow && flow->DataSize<=MAX_DATA)
        logline("  flow control",flow->Data,flow->DataSize);
    unlock_state();return error(ERR_OK);
}
EXPORT U32 WINCALL PassThruStopMsgFilter(U32 id,U32 filter_id){
    U32 i;CHANNEL *c;lock_state();c=channel(id);if(!c){unlock_state();return error(ERR_INVALID_CHANNEL_ID);}
    for(i=0;i<c->filters_count;i++)if(c->filters[i].id==filter_id){
        U32 j;for(j=i+1;j<c->filters_count;j++)c->filters[j-1]=c->filters[j];c->filters_count--;
        unlock_state();return error(ERR_OK);
    }
    unlock_state();return error(ERR_INVALID_FILTER_ID);
}
EXPORT U32 WINCALL PassThruStartPeriodicMsg(U32 id,const PASSTHRU_MSG *msg,U32 *period_id,U32 interval){
    U32 i;if(!msg||!period_id)return error(ERR_NULL_PARAMETER);
    if(interval<5 || interval>60000)return error(ERR_INVALID_TIME_INTERVAL);
    if(msg->DataSize<5 || msg->DataSize>MAX_DATA)return error(ERR_INVALID_MSG);
    lock_state();CHANNEL *c=channel(id);if(!c){unlock_state();return error(ERR_INVALID_CHANNEL_ID);}
    for(i=0;i<MAX_PERIODIC;i++)if(!c->periodic[i].used)break;
    if(i==MAX_PERIODIC){unlock_state();return error(ERR_EXCEEDED_LIMIT);}
    PERIODIC *p=&c->periodic[i];bytes_zero(p,sizeof(*p));
    p->used=1;p->id=g_periodic_counter++;p->interval_ms=interval;
    p->next_us=now_us()+(U64)interval*1000ull;
    bytes_copy(&p->msg,msg,sizeof(PASSTHRU_MSG));*period_id=p->id;
    unlock_state();return error(ERR_OK);
}
EXPORT U32 WINCALL PassThruStopPeriodicMsg(U32 id,U32 periodic_id){
    U32 i;lock_state();CHANNEL *c=channel(id);if(!c){unlock_state();return error(ERR_INVALID_CHANNEL_ID);}
    for(i=0;i<MAX_PERIODIC;i++)if(c->periodic[i].used&&c->periodic[i].id==periodic_id){
        c->periodic[i].used=0;unlock_state();return error(ERR_OK);
    }
    unlock_state();return error(ERR_INVALID_MSG_ID);
}
EXPORT U32 WINCALL PassThruSetProgrammingVoltage(U32 device,U32 pin,U32 voltage){
    (void)device;(void)pin;(void)voltage;return error(ERR_NOT_SUPPORTED);
}
EXPORT U32 WINCALL PassThruReadVersion(U32 device,char *firmware,char *dll,char *api){
    if(device!=1||!g_open)return error(ERR_INVALID_DEVICE_ID);
    if(!firmware||!dll||!api)return error(ERR_NULL_PARAMETER);
    str_copy(firmware,"SIMULATED-1.6",80);str_copy(dll,"VirtualCar-0.3.6.6",80);str_copy(api,"04.04",80);return error(ERR_OK);
}
EXPORT U32 WINCALL PassThruGetLastError(char *description){
    static const char *names[]={"STATUS_NOERROR","ERR_NOT_SUPPORTED","ERR_INVALID_CHANNEL_ID","ERR_INVALID_PROTOCOL_ID","ERR_NULL_PARAMETER","ERR_INVALID_IOCTL_VALUE","ERR_INVALID_FLAGS","ERR_FAILED","ERR_DEVICE_NOT_CONNECTED","ERR_TIMEOUT","ERR_INVALID_MSG","ERR_INVALID_TIME_INTERVAL","ERR_EXCEEDED_LIMIT","ERR_INVALID_MSG_ID","ERR_DEVICE_IN_USE","ERR_INVALID_IOCTL_ID","ERR_BUFFER_EMPTY","ERR_BUFFER_FULL","ERR_BUFFER_OVERFLOW","ERR_PIN_INVALID","ERR_CHANNEL_IN_USE","ERR_MSG_PROTOCOL_ID","ERR_INVALID_FILTER_ID","ERR_NO_FLOW_CONTROL","ERR_NOT_UNIQUE","ERR_INVALID_BAUDRATE","ERR_INVALID_DEVICE_ID"};
    if(!description)return ERR_NULL_PARAMETER;
    str_copy(description,g_last<=26?names[g_last]:"UNKNOWN",80);return ERR_OK;
}
EXPORT U32 WINCALL PassThruIoctl(U32 id,U32 ioctl,void *input,void *output){
    U32 i;
    if(ioctl==IO_READ_VBATT){
        U8 value[4];if(!output)return error(ERR_NULL_PARAMETER);
        *(U32*)output=g_battery_mv;u32_be(value,g_battery_mv);
        logline("PassThruIoctl READ_VBATT (mV, BE)",value,4);
        return error(ERR_OK);
    }
    if(ioctl==IO_READ_PROG_VOLTAGE){if(!output)return error(ERR_NULL_PARAMETER);*(U32*)output=0;return error(ERR_OK);}
    lock_state();CHANNEL *c=channel(id);if(!c){unlock_state();return error(ERR_INVALID_CHANNEL_ID);}
    if(ioctl==IO_CLEAR_RX_BUFFER){
        backend_cancel_channel(c,"clear_rx_buffer",0);
        c->r=c->w=c->count=0;c->d2_count=0;c->d2_pos=0;c->d2_trace=0;
        bytes_zero(c->queue_d2_gen,sizeof(c->queue_d2_gen));
        {U8 meta[20];u32_be(meta,id);u32_be(meta+4,c->protocol);
         u32_be(meta+8,c->flags);u32_be(meta+12,c->baud);
         u32_be(meta+16,(U32)now_us());
         logline("CLEAR_RX context channel/protocol/flags/baud/time-us (BE)",meta,20);}
        logline("J2534 CLEAR_RX_BUFFER: queued and staged D2 dropped",0,0);
        unlock_state();return error(ERR_OK);}
    if(ioctl==IO_CLEAR_MSG_FILTERS){c->filters_count=0;unlock_state();return error(ERR_OK);}
    if(ioctl==IO_CLEAR_PERIODIC_MSGS){bytes_zero(c->periodic,sizeof(c->periodic));unlock_state();return error(ERR_OK);}
    if(ioctl==IO_CLEAR_TX_BUFFER){unlock_state();return error(ERR_OK);}
    if(ioctl==IO_SET_CONFIG||ioctl==IO_GET_CONFIG){
        SCONFIG_LIST *list=(SCONFIG_LIST*)input;
        U32 speed_changed=0;
        if(!list||(!list->ConfigPtr&&list->NumOfParams)){unlock_state();return error(ERR_NULL_PARAMETER);}
        if(list->NumOfParams>64){unlock_state();return error(ERR_INVALID_IOCTL_VALUE);}
        /* Validate every DATA_RATE before mutating any parameter. A zero
           speed is invalid, including when it appears after a valid rate
           in the same list; leave baud and observer state unchanged. */
        if(ioctl==IO_SET_CONFIG){
            for(i=0;i<list->NumOfParams;i++)
                if(list->ConfigPtr[i].Parameter==1u &&
                   list->ConfigPtr[i].Value==0u){
                    unlock_state();return error(ERR_INVALID_BAUDRATE);
                }
        }
        for(i=0;i<list->NumOfParams;i++){
            SCONFIG *s=&list->ConfigPtr[i];
            if(ioctl==IO_SET_CONFIG){
                if(s->Parameter==1){
                    if(c->baud!=s->Value)speed_changed=1;
                    c->baud=s->Value;
                }
                log_set_config(id,s->Parameter,s->Value);
            }
            if(ioctl==IO_GET_CONFIG)s->Value=s->Parameter==1?c->baud:0;
        }
        /* The passive CEM observer must see the same effective channel speed
           as the J2534 transport after SET_CONFIG. Never create ECU RX. */
        if(speed_changed)
            p2_bridge_connect(&g_vehicle_bridge,id,c->protocol,c->baud);
        unlock_state();return error(ERR_OK);
    }
    unlock_state();return error(ERR_INVALID_IOCTL_ID);
}
/* DLL_PROCESS_ATTACH, no work under loader lock. */
int WINCALL DllMain(PTR module,U32 reason,PTR reserved) {(void)reserved;if(reason==1)g_module=module;return 1;}


