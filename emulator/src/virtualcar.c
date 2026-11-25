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
#include "p2core/p2_b9f0_fixture_guard.h"
#include "vc054_f106_lab.h"
#include "vc0662_f110.h"
#include "vc0663_identity.h"
typedef unsigned char U8;
typedef unsigned long long U64;
typedef long long I64;
#ifndef HOST_TEST
/* Minimal CRT-independent floating-point support symbol for MSVC ABI. */
int _fltused = 0;
#endif
typedef void *PTR;
typedef void *HANDLE;
typedef struct { U32 low; U32 high; } FILETIME_VALUE;
#define MAX_DATA 4128
#define MAX_CHANNELS 8
#define MAX_QUEUE 64
#define MAX_ECUS 32
#define LEGACY_ECUS 8
#define MAX_D2_FRAMES 64
#define MAX_PERIODIC 4
#define MAX_D2_FIXTURES 134 /* 6 legacy + 128 optional D2_Node slots */
#define BASE_D2_FIXTURES 6
#define MAX_PASSIVE_TRACES 12
#define MAX_EXTRA_DID 192
#define MAX_EXTRA_DID_SLOTS 32
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
/* J2534-2 pin-selectable CAN protocols; disabled unless the adjacent INI opts in. */
#define PROTO_CAN_PS 0x8004u
#define PROTO_ISO15765_PS 0x8005u
#define CONFIG_J1962_PINS 0x8001u
#define PINS_CAN_HS 0x060Eu /* J1962 pins 6 (CAN-H), 14 (CAN-L) */
#define PINS_CAN_MS 0x030Bu /* J1962 pins 3 (CAN-H), 11 (CAN-L) */
static int is_ps_protocol(U32 protocol) {
    return protocol==PROTO_CAN_PS || protocol==PROTO_ISO15765_PS;
}
static U32 canonical_protocol(U32 protocol) {
    return protocol==PROTO_CAN_PS?PROTO_CAN:
           (protocol==PROTO_ISO15765_PS?PROTO_ISO15765:protocol);
}
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
IMPORT HANDLE WINCALL GetCurrentProcess(void) ALIAS(GetCurrentProcess);
IMPORT int WINCALL GetProcessTimes(HANDLE process,FILETIME_VALUE *creation,FILETIME_VALUE *exitTime,FILETIME_VALUE *kernelTime,FILETIME_VALUE *userTime) ALIAS(GetProcessTimes);
IMPORT U32 WINCALL GetModuleFileNameA(PTR mod, char *out, U32 n) ALIAS(GetModuleFileNameA);
IMPORT U32 WINCALL GetPrivateProfileStringA(const char *section,const char *key,const char *fallback,char *out,U32 size,const char *path) ALIAS(GetPrivateProfileStringA);
IMPORT U32 WINCALL GetTempPathA(U32 n, char *out) ALIAS(GetTempPathA);
IMPORT U32 WINCALL GetEnvironmentVariableA(const char *name, char *out, U32 n) ALIAS(GetEnvironmentVariableA);
IMPORT int WINCALL CreateDirectoryA(const char *name, PTR sec) ALIAS(CreateDirectoryA);
IMPORT HANDLE WINCALL CreateFileA(const char *path,U32 access,U32 sharing,PTR security,U32 creation,U32 flags,HANDLE templateFile) ALIAS(CreateFileA);
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
/* B3A150: default OFF; never activates GGD CEM from ECU identity alone. */
static U32 g_b3a150_ggd_cem_lab=0;
static VC054_F106 g_vc054_f106;
static U32 g_vc0662_f110=0u;
static U32 g_vc0663_identity=0u;
/* B3A157 GGD key switch candidate: defaults OFF for all existing profiles. */
static U32 g_b3a157_posii_candidate=0;
/* PS is isolated to an explicitly enabled emulator profile; legacy defaults stay off. */
static U32 g_j2534_ps_enabled=0;
static U32 g_ecu_count=2;
static U32 g_p2_strict_routing=0;
static U32 g_b3a267_current_lab=0;
static U32 g_b3a309_ecm_live_lab=0;
static U32 g_b3a314_ecm_live_lab=0;
static U32 g_b3a320_rem_sync=0;
static U32 g_b3a324_supply_sync=0;
static U32 g_b3a329_dynamic_lab=0;
static U32 g_b3a228_cem40_empty_dtc=0;
static U32 g_d2_spacing_ms=12; /* 0 means immediate, P2 replay defaults to paced */
typedef struct {U32 req,resp,expected_baud; U8 lab_dtc_mask,lab_dtc_single,lab_dtc_details; char part[48];char sw[48]; U8 extra_did[2][MAX_EXTRA_DID]; U32 extra_len[2]; U32 did_code[MAX_EXTRA_DID_SLOTS],did_len[MAX_EXTRA_DID_SLOTS]; U8 did_bytes[MAX_EXTRA_DID_SLOTS][MAX_EXTRA_DID];} ECU;
static ECU g_ecu[MAX_ECUS];
/* Optional read-only replay fixtures: user must supply verified, non-sensitive
   CAN frames. No invented B9 FB vehicle-configuration payloads. */
typedef struct {
    U8 target,subcommand,lab_empty_dtc;
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
/* protocol is internal CAN/ISO15765; api_protocol preserves the client-visible PS ID. */
    U32 api_protocol,ps_pins;
    /* Monotonic private connection lifetime. Reused numeric channel IDs
       must not make an in-flight ReadMsgs consume a new channel's FIFO. */
    U64 session_serial;
    FILTER filters[MAX_FILTERS]; U32 filters_count;
    U32 passive_next_tick;
    U32 trace_next_tick[MAX_PASSIVE_TRACES];
    U64 d2_next_us;
    U32 d2_spacing_ms,d2_response_id,d2_count,d2_pos,d2_generation,d2_frame_number;
    U8 d2_frame[MAX_D2_FRAMES][8];
    PASSTHRU_MSG queue[MAX_QUEUE]; U32 queue_d2_gen[MAX_QUEUE],queue_d2_frame[MAX_QUEUE]; U64 queue_ready_us[MAX_QUEUE]; U32 r,w,count;
    /* Nonzero only for optional passive CAN fixtures generated on a given
       bitrate. Staged trace/tick RX must not cross a later bus retune. */
    U32 queue_passive_baud[MAX_QUEUE];
    /* Source baud of emulator-generated raw CAN UDS SF/FF/CF and
       reassembled J2534 ISO15765 replies. Retune must drop both. */
    U32 queue_raw_response_baud[MAX_QUEUE];
    /* Private exchange generation independent of optional backend telemetry.
       Only unfinished raw CAN FF/CF exchanges may supersede queued frames. */
    U64 queue_raw_exchange[MAX_QUEUE],next_raw_exchange,pending_raw_exchange;
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
/* Never reset on Open/Close: even a device reopen can reuse channel ID 1. */
static U64 g_next_channel_serial;
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
/* Decimal INI indexes 0..31; preserve original names for 0..9. */
static void indexed_ini_key(char *out,U32 cap,const char *prefix,U32 index,const char *suffix){
    char number[3];U32 n=0;
    if(index>=10u)number[n++]=(char)('0'+index/10u);
    number[n++]=(char)('0'+index%10u);number[n]=0;
    str_copy(out,prefix,cap);str_append(out,number,cap);str_append(out,suffix,cap);
}
static int digit(char c) { if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;if(c>='A'&&c<='F')return c-'A'+10;return -1; }
static U32 parse_num(const char *s,U32 fallback) {U32 v=0,base=10,i=0;int d,any=0;if(!s)return fallback;if(s[0]=='0'&&(s[1]=='x'||s[1]=='X')){base=16;i=2;}for(;s[i];i++){d=digit(s[i]);if(d<0||((U32)d)>=base) return fallback;any=1;v=v*base+(U32)d;}return any?v:fallback;}
/* Opt-in physical GGD routes only. CEM retains its dedicated handler. */
static int lab_dtc_route_allowed(U32 req,U32 resp,U32 baud) {
    U32 target=(req>>8)&0xFFu;
    return baud==500000u && (req&0xFFFF00FFu)==0x18DA00F1u &&
           target>0u && target<0xF0u && target!=0x50u &&
           resp==(0x18DAF100u|target);
}
/* Explicit synthetic empty-DTC fixture. Zero means disabled. */
static U8 lab_dtc_status_mask(const char *s) {
    int hi,lo;
    if(!s || str_len(s)!=2u)return 0;
    hi=digit(s[0]);lo=digit(s[1]);
    if(hi<0||lo<0)return 0;
    return (U8)((hi<<4)|lo);
}
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
    /* FILE_APPEND_DATA without FILE_WRITE_DATA makes each WriteFile append.
       The former GENERIC_WRITE + SetFilePointer(FILE_END) pair could race
       with other processes sharing the same native trace file. Preserve
       exactly one write per CRLF-terminated record. */
    f=CreateFileA(g_log_path,0x00100004u,3,0,4,0x80,0); /* SYNCHRONIZE|FILE_APPEND_DATA, OPEN_ALWAYS */
    if(f==INVALID_HANDLE)return;
    WriteFile(f,line,p,&written,0);CloseHandle(f);
}

/* B3A72: bind native log records to the Windows process creation epoch.
   The FILETIME is private log metadata, never a vehicle/CAN payload. */
static void log_process_creation_filetime(void){
    FILETIME_VALUE created,exited,kernel,user;U8 value[8];
    if(!GetProcessTimes(GetCurrentProcess(),&created,&exited,&kernel,&user))return;
    u32_be(value,created.high);u32_be(value+4,created.low);
    logline("Process creation FILETIME (BE)",value,8);
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
        /* The caller cancels cleared RX and any staged raw CAN CF transfer.
           Detach old request attribution before the caller resets transport
           state; a late CTS must never revive a terminally aborted request. */
        if(!d2_only && c->pending_trace==rid)c->pending_trace=0;
        if(c->d2_trace==rid)c->d2_trace=0;
        if(!d2_only)for(j=0;j<c->count;j++){
            U32 slot=(c->r+j)%MAX_QUEUE;
            if(c->queue_trace[slot]==rid)c->queue_trace[slot]=0;
        }
    }
}

/* B3A261: exact, read-only virtual routes; no real vehicle I/O. */
/* B3A264: exact CarCom lengths, synthetic read-only fixtures only. */
static U32 lab_extended_size(U32 target,U32 opcode){
    static const U8 layouts[][3]={
        {0x40,0xF5,36u},
        {0x40,0xF8,36u},
        {0x51,0xF5,48u},
        {0x51,0xF8,6u},
        {0x52,0xF5,36u},
        {0x52,0xF8,6u},
        {0x6D,0xF5,36u},
        {0x6D,0xF8,6u},
        {0x29,0xF5,24u},
        {0x29,0xF8,54u},
        {0x43,0xF5,36u},
        {0x43,0xF8,6u},
        {0x54,0xF5,44u},
        {0x54,0xF8,6u},
        {0x45,0xF5,36u},
        {0x45,0xF8,6u},
        {0x2E,0xF5,20u},
        {0x2E,0xF8,6u},
        {0x46,0xF5,48u},
        {0x46,0xF8,12u},
        {0x58,0xF5,24u},
        {0x58,0xF8,30u},
        {0x68,0xF5,24u},
        {0x68,0xF8,6u},
        {0x47,0xF5,36u},
        {0x47,0xF8,6u},
        {0x66,0xF5,24u},
        {0x66,0xF8,6u},
        {0x64,0xF5,36u},
        {0x64,0xF8,6u},
        {0x67,0xF5,24u},
        {0x67,0xF8,12u},
        {0x71,0xF5,36u},
        {0x71,0xF8,6u},
        {0x75,0xF5,36u},
        {0x75,0xF8,6u},
        {0x72,0xF5,24u},
        {0x72,0xF8,6u},
        {0x7B,0xF5,36u},
        {0x7B,0xF8,6u},
        {0x0F,0xD2,4u},
        {0x0F,0xD4,4u},
        {0x40,0x31,1u}, /* B3A302: synthetic impact status, explicit lab fixture only. */
    };
    U32 i;for(i=0;i<sizeof(layouts)/sizeof(layouts[0]);i++)
        if(target==layouts[i][0] && opcode==layouts[i][1])return layouts[i][2];
    return 0;
}
static int lab_special_b9(U32 target,U32 opcode){
    return (target==0x58u && opcode==0x03u) || (target==0x0Fu && opcode==0xD0u) || lab_extended_size(target,opcode)!=0u;
}
static int lab_special_request(const U8 *data,U32 len,U32 baud,U32 flags,U32 tx_flags){
    U32 j;
    if(len!=8u || data[0]!=0xCBu || data[2]!=0xB9u ||
       !lab_special_b9(data[1],data[3]) || baud!=125000u ||
       !(flags&CAN_29BIT_ID) || !(tx_flags&CAN_29BIT_ID))return 0;
    for(j=4;j<8;j++)if(data[j])return 0;
    return 1;
}
static int lab_special_fixture(const D2_PROFILE *d){
    if(!lab_special_b9(d->target,d->subcommand))return 1;
    if(d->baud!=125000u || d->response_id!=0x00800003u)return 0;
    {U32 n=lab_extended_size(d->target,d->subcommand),remaining,k,j;
     if(n){
        if(d->target==0x40u && d->subcommand==0x31u){
            static const U8 synthetic[8]={0xCCu,0x40u,0xF9u,0x31u,0,0,0,0};
            if(d->frame_count!=1u)return 0;
            for(j=0;j<8u;j++)if(d->frame[0][j]!=synthetic[j])return 0;
            return 1;
        }
        if(n==4u)return d->frame_count==1u && d->frame[0][0]==0xCFu && d->frame[0][2]==0xF9u;
        if(d->frame_count!=1u+(n-4u+6u)/7u || d->frame[0][0]!=0x8Fu)return 0;
        remaining=n-4u;
        for(k=1;k<d->frame_count;k++){
            if(remaining<=7u){
                if(k!=d->frame_count-1u || d->frame[k][0]!=(U8)(0x48u+remaining))return 0;
                for(j=remaining+1u;j<8u;j++)if(d->frame[k][j])return 0;
                return 1;
            }
            if(d->frame[k][0]!=(U8)(0x08u|(k&7u)))return 0;
            remaining-=7u;
        }
        return 0;
     }}
    if(d->subcommand==0xD0u)return d->frame_count==1u && d->frame[0][0]==0xCFu && d->frame[0][2]==0xF9u;
    return d->frame_count==2u && d->frame[0][0]==0x8Fu && d->frame[1][0]==0x4Au &&
        !d->frame[1][3] && !d->frame[1][4] && !d->frame[1][5] && !d->frame[1][6] && !d->frame[1][7];
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
static void ecm_lab_select_scenario(U32 enabled,const char *state);
static U32 ecm_lab_battery_mv(U32 configured,U32 sync_enabled,U32 baseline_enabled);
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
    g_b3a150_ggd_cem_lab=0;
    GetPrivateProfileStringA("Diagnostics","EnableGGDCemLab","0",v,sizeof(v),g_profile_path);
    g_b3a150_ggd_cem_lab=parse_num(v,0)==1u?1u:0u;
    GetPrivateProfileStringA("VC0662_F110Lab","Enabled","0",v,sizeof(v),g_profile_path);
    g_vc0662_f110=g_b3a150_ggd_cem_lab && vc0662_f110_enabled(v);
    GetPrivateProfileStringA("VC0663_IdentityLab","Enabled","0",v,sizeof(v),g_profile_path);
    g_vc0663_identity=g_vc0662_f110 && vc0662_f110_enabled(v);
    vc054_clear(&g_vc054_f106);
    GetPrivateProfileStringA("VC054_F106Lab","Enabled","0",v,sizeof(v),g_profile_path);
    if(g_b3a150_ggd_cem_lab && vc054_literal(v,"1")){
        GetPrivateProfileStringA("VC054_F106Lab","Layout","",v,sizeof(v),g_profile_path);
        if(vc054_literal(v,"donor-142")){
            GetPrivateProfileStringA("VC054_F106Lab","BlockHex","",v,sizeof(v),g_profile_path);
            if(vc054_load(&g_vc054_f106,"1","donor-142",v))
                logline("VC054 F106 donor-format LAB enabled (not OEM verified)",0,0);
            else logline("VC054 F106 LAB rejected",0,0);
        }
    }
    g_b3a157_posii_candidate=0u;
    GetPrivateProfileStringA("B3A157_IgnitionLab","Enabled","0",v,sizeof(v),g_profile_path);
    if(parse_num(v,0)==1u){
        GetPrivateProfileStringA("B3A157_IgnitionLab","A45FRawByte","",v,sizeof(v),g_profile_path);
        /* No arbitrary raw-byte injection; must be literal 07. */
        if(v[0]=='0' && v[1]=='7' && v[2]==0)
            g_b3a157_posii_candidate=1u;
        else logline("B3A157 invalid ignition candidate config: baseline retained",0,0);
    }
    /* Only a dedicated new provider profile can advertise J2534-2 virtual pins. */
    g_j2534_ps_enabled=0;
    GetPrivateProfileStringA("J2534_2","Enabled","0",v,sizeof(v),g_profile_path);
    g_j2534_ps_enabled=parse_num(v,0)==1u?1u:0u;
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
        indexed_ini_key(key,sizeof(key),"ECU",i,"");
        GetPrivateProfileStringA(key,"RequestId",i>=LEGACY_ECUS?"":(i==1?"726":"7E0"),v,sizeof(v),g_profile_path);
        g_ecu[i].req=parse_hex(v,i>=LEGACY_ECUS?0xFFFFFFFFu:(i==1?0x726:0x7E0));
        GetPrivateProfileStringA(key,"ResponseId",i>=LEGACY_ECUS?"":(i==1?"72E":"7E8"),v,sizeof(v),g_profile_path);
        g_ecu[i].resp=parse_hex(v,i>=LEGACY_ECUS?0xFFFFFFFFu:(i==1?0x72E:0x7E8));
        if(i>=LEGACY_ECUS && (g_ecu[i].req>0x1FFFFFFFu || g_ecu[i].resp>0x1FFFFFFFu || g_ecu[i].req==0x7DFu)){
            g_ecu[i].req=0xFFFFFFFFu;
            logline("Extended ECU slot missing or invalid physical CAN route: disabled",0,0);
            continue;
        }
        /* Missing ExpectedBaud=0 retains the legacy routing policy.
           Invalid non-numeric values fail closed, never disable this guard. */
        GetPrivateProfileStringA(key,"ExpectedBaud","0",v,sizeof(v),g_profile_path);
        g_ecu[i].expected_baud=parse_num(v,0xFFFFFFFFu);
        if(g_ecu[i].expected_baud==0xFFFFFFFFu)
            logline("Invalid ExpectedBaud: optional ECU route disabled",0,0);
        /* Only explicitly enabled physical GGD lab routes may advertise empty DTCs.
           Missing, malformed or zero mask leaves the old NRC11 behavior. */
        if(lab_dtc_route_allowed(g_ecu[i].req,g_ecu[i].resp,g_ecu[i].expected_baud)){
            GetPrivateProfileStringA(key,"LabDtcEmptyEnabled","0",v,sizeof(v),g_profile_path);
            if(v[0]=='1' && v[1]==0){
                GetPrivateProfileStringA(key,"LabDtcStatusMask","",v,sizeof(v),g_profile_path);
                g_ecu[i].lab_dtc_mask=lab_dtc_status_mask(v);
                if(g_ecu[i].lab_dtc_mask)logline("Synthetic ECU DTC fixture enabled (not OEM verified)",0,0);
                if(g_ecu[i].req==0x18DA18F1u && g_ecu[i].resp==0x18DAF118u && g_ecu[i].lab_dtc_mask==0x20u){
                    GetPrivateProfileStringA("B3A231_TcmDtcLab","Enabled","0",v,sizeof(v),g_profile_path);
                    if(v[0]=='1' && v[1]==0)g_ecu[i].lab_dtc_single=1;
                    if(g_ecu[i].lab_dtc_single){
                        GetPrivateProfileStringA("B3A238_TcmDtcDetailsLab","Enabled","0",v,sizeof(v),g_profile_path);
                        if(v[0]=='1' && v[1]==0)g_ecu[i].lab_dtc_details=1;
                    }
                }
            }
        }
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
             indexed_ini_key(kcode,sizeof(kcode),"DID",slot,"Code");
             indexed_ini_key(kbytes,sizeof(kbytes),"DID",slot,"Hex");
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
             else {U32 previous;
                 for(previous=0;previous<slot;previous++){
                     if(g_ecu[i].did_len[previous] && g_ecu[i].did_code[previous]==g_ecu[i].did_code[slot]){
                         g_ecu[i].did_code[slot]=0;g_ecu[i].did_len[slot]=0;
                         logline("Duplicate configured DID slot ignored (first valid wins)",0,0);break;
                     }
                 }
             }
         }}
    }
    /* P2 D2 fixtures: 40/50 CEM x B9FB (vehicle information), B9F0
       (module part number), B9FC (vehicle configuration). No response is
       fabricated when a fixture is absent.
       B9FB response CAN ID 0x01200003 is from a published 2005-era DiCE trace;
       not guaranteed for every P2 model or CAN bus. */
    GetPrivateProfileStringA("P2","StrictRouting","0",v,sizeof(v),g_profile_path);
    g_p2_strict_routing=parse_num(v,0)?1:0;
    GetPrivateProfileStringA("B3A228_CemDtcLab","Enabled","0",v,sizeof(v),g_profile_path);
    g_b3a228_cem40_empty_dtc=(str_len(v)==1u && v[0]=='1')?1u:0u;
    GetPrivateProfileStringA("B3A267_CurrentDataLab","Enabled","0",v,sizeof(v),g_profile_path);
    g_b3a267_current_lab=(str_len(v)==1u && v[0]=='1')?1u:0u;
    GetPrivateProfileStringA("B3A309_EcmLiveDataLab","Enabled","0",v,sizeof(v),g_profile_path);
    g_b3a309_ecm_live_lab=(str_len(v)==1u && v[0]=='1')?1u:0u;
    GetPrivateProfileStringA("B3A314_EcmExtendedLiveLab","Enabled","0",v,sizeof(v),g_profile_path);
    g_b3a314_ecm_live_lab=(str_len(v)==1u && v[0]=='1')?1u:0u;
    {U32 enabled;
        GetPrivateProfileStringA("B3A316_EcmScenarioLab","Enabled","0",v,sizeof(v),g_profile_path);
        enabled=(str_len(v)==1u && v[0]=='1')?1u:0u;
        GetPrivateProfileStringA("B3A316_EcmScenarioLab","State","0",v,sizeof(v),g_profile_path);
        ecm_lab_select_scenario(enabled,v);
    }
    GetPrivateProfileStringA("B3A319_BatterySyncLab","Enabled","0",v,sizeof(v),g_profile_path);
    {U32 battery_sync=(str_len(v)==1u && v[0]=='1')?1u:0u;
        g_battery_mv=ecm_lab_battery_mv(g_battery_mv,battery_sync,g_b3a309_ecm_live_lab);
        GetPrivateProfileStringA("B3A320_RemVoltageSyncLab","Enabled","0",v,sizeof(v),g_profile_path);
        g_b3a320_rem_sync=(battery_sync && g_b3a309_ecm_live_lab && str_len(v)==1u && v[0]=='1')?1u:0u;
        GetPrivateProfileStringA("B3A324_SupplyVoltageSyncLab","Enabled","0",v,sizeof(v),g_profile_path);
        g_b3a324_supply_sync=(battery_sync && g_b3a309_ecm_live_lab && str_len(v)==1u && v[0]=='1')?1u:0u;
        GetPrivateProfileStringA("B3A329_DynamicEcmLab","Enabled","0",v,sizeof(v),g_profile_path);
        g_b3a329_dynamic_lab=(g_b3a309_ecm_live_lab && g_b3a314_ecm_live_lab &&
            g_b3a267_current_lab && g_b3a150_ggd_cem_lab && g_b3a320_rem_sync &&
            g_b3a324_supply_sync && str_len(v)==1u && v[0]=='1')?1u:0u;
    }
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
            char digits[4];U32 target,opcode;
            str_copy(section,"D2_Node",sizeof(section));
            {U32 slot=i-BASE_D2_FIXTURES,pos=0;
             if(slot>=100u)digits[pos++]=(char)('0'+slot/100u);
             if(slot>=10u)digits[pos++]=(char)('0'+(slot/10u)%10u);
             digits[pos++]=(char)('0'+slot%10u);digits[pos]=0;}
            str_append(section,digits,sizeof(section));
            GetPrivateProfileStringA(section,"Enabled","0",v,sizeof(v),g_profile_path);
            if(parse_num(v,0)!=1)continue;
            GetPrivateProfileStringA(section,"Target","",v,sizeof(v),g_profile_path);
            target=parse_hex(v,0xFFFFFFFFu);
            GetPrivateProfileStringA(section,"Opcode","",v,sizeof(v),g_profile_path);
            opcode=parse_hex(v,0xFFFFFFFFu);
            GetPrivateProfileStringA(section,"Baud","",v,sizeof(v),g_profile_path);
            d->baud=parse_num(v,0);
            if(target>0xFFu||(target==0x40u&&!lab_extended_size(target,opcode))||target==0x50u||
               (opcode!=0xF0u&&opcode!=0xFBu&&opcode!=0xFCu&&!lab_special_b9(target,opcode))||
               (lab_special_b9(target,opcode)&&d->baud!=125000u)||
               (d->baud!=125000u&&d->baud!=500000u)){
                logline("D2 extra ECU fixture invalid target/opcode/baud ignored",0,0);
                continue;
            }
            d->target=(U8)target;d->subcommand=(U8)opcode;
            GetPrivateProfileStringA(section,"LabEmptyDtc","0",v,sizeof(v),g_profile_path);
            d->lab_empty_dtc=(opcode==0xF0u && str_len(v)==1u && v[0]=='1')?1u:0u;
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
        if(d->frame_count && (!validate_d2_fixture(d) ||
            (d->subcommand==0xF0u &&
             (d->target==0x40u || d->target==0x50u) &&
             !p2_b9f0_fixture_allowed(d->frame_count, d->frame, d->target)) ||
            !validate_fc140_fixture(d) || !lab_special_fixture(d))){
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
    /* B3A69: filter policy is a loaded native configuration bit, not a
       statement about original VIDA client acceptance or filter channel. */
    {U8 strict_be[4];u32_be(strict_be,g_strict_j2534_filters);
     logline("J2534 native strict RX filter policy (BE)",strict_be,4);}
    /* Show the active configuration loaded by the *client* process, not just
       the GUI's expected directory. This resolves stale Registry32 paths. */
    {
        char detail[320];U8 lengths[8];
        log_process_creation_filetime();
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
    msg->ProtocolID=c->api_protocol?c->api_protocol:c->protocol;msg->RxStatus=(response_id>0x7FF?CAN_29BIT_ID:0)|status;
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
    c->queue_passive_baud[c->w]=0;
    c->queue_raw_response_baud[c->w]=0;
    c->queue_raw_exchange[c->w]=0;
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
    if(is_ps_protocol(c->api_protocol) && !c->ps_pins)return;
    if(c->protocol!=PROTO_CAN)return;
    now=GetTickCount();
    for(i=0;i<MAX_PASSIVE_TRACES;i++){
        TRACE_FRAME *t=&g_trace[i];
        if(!t->enabled||t->baud!=c->baud||c->count>=MAX_QUEUE)continue;
        if((U32)(now-c->trace_next_tick[i])>=0x80000000u)continue;
        c->trace_next_tick[i]=now+t->period_ms;
        {U32 slot=c->w, before=c->count;
         enqueue(c,t->id,t->data,8);
         /* A rejected/overflowed frame never owns the previous FIFO slot. */
         if(c->count>before)c->queue_passive_baud[slot]=t->baud;
        }
        logline("Passive CAN recorded fixture replay (not OEM-authenticated)",0,0);
    }
}
static void maybe_passive_frame(CHANNEL *c){
    if(is_ps_protocol(c->api_protocol) && !c->ps_pins)return;
    U32 now;
    if(!g_passive_enabled||c->protocol!=PROTO_CAN||c->count>=MAX_QUEUE)return;
    now=GetTickCount();
    if((U32)(now-c->passive_next_tick)>=0x80000000u)return;
    c->passive_next_tick=now+g_passive_period_ms;
    {U32 slot=c->w, before=c->count;
     enqueue(c,g_passive_id,g_passive_payload,8);
     if(c->count>before)c->queue_passive_baud[slot]=c->baud;
    }
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
         if(c->count>before){
             c->queue_ready_us[slot]=due;c->queue[slot].Timestamp=(U32)due;
             c->queue_raw_response_baud[slot]=c->baud;
             c->queue_raw_exchange[slot]=c->pending_raw_exchange;
         }else{
             /* A strict raw-CAN data filter can admit FF while rejecting
                one or more CFs by PCI sequence byte. Never advance past a
                missing CF and emit later frames with a gap in the sequence.
                enqueue() recorded the filter_reject/drop for this RID. */
             U64 interrupted=c->pending_trace;
             logline("Raw CAN ISO-TP CF rejected; remaining CFs cancelled",0,0);
             c->pending_len=0;c->pending_pos=0;c->pending_id=0;
             c->pending_request_id=0;c->pending_sn=0;
             c->pending_trace=0;c->pending_next_us=0;c->pending_stmin_us=0;
             c->pending_cf_active=0;c->pending_cf_credit=0;
             backend_end_if_drained(c,interrupted);
             return;
         }}
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
/* Superseding a *pending* raw CAN ISO-TP reply must also retract its
   not-yet-read FF/CF. Tracking via the actual exchange generation works
   with backend telemetry disabled, unlike a diagnostic request ID. */
static U32 drop_superseded_raw_iso_rx(CHANNEL *c,U64 generation,U64 rid){
    U32 read,keep=0,removed=0,original=c->count;
    if(!generation)return 0;
    for(read=0;read<original;read++){
        U32 from=(c->r+read)%MAX_QUEUE,to=(c->r+keep)%MAX_QUEUE;
        if(c->queue_raw_exchange[from]==generation){
            if(rid)backend_event(c,rid,"rx_dropped","UNKNOWN","superseded","unknown");
            removed++;
            continue;
        }
        if(to!=from){
            bytes_copy(&c->queue[to],&c->queue[from],sizeof(PASSTHRU_MSG));
            c->queue_d2_gen[to]=c->queue_d2_gen[from];
            c->queue_d2_frame[to]=c->queue_d2_frame[from];
            c->queue_ready_us[to]=c->queue_ready_us[from];
            c->queue_trace[to]=c->queue_trace[from];
            c->queue_passive_baud[to]=c->queue_passive_baud[from];
            c->queue_raw_response_baud[to]=c->queue_raw_response_baud[from];
            c->queue_raw_exchange[to]=c->queue_raw_exchange[from];
        }
        keep++;
    }
    c->count=keep;
    c->w=(c->r+keep)%MAX_QUEUE;
    return removed;
}
/* FC OVERFLOW must stop CF emission already staged into the virtual RX FIFO.
   Keep an earlier FF: it models a frame already transmitted before the FC.
   Do not discard unrelated FIFO frames or touch a different channel. */
static U32 drop_overflow_raw_iso_cf_rx(CHANNEL *c,U64 generation,U64 rid){
    U32 read,keep=0,removed=0,original=c->count;
    if(!generation)return 0;
    for(read=0;read<original;read++){
        U32 from=(c->r+read)%MAX_QUEUE,to=(c->r+keep)%MAX_QUEUE;
        if(c->queue_raw_exchange[from]==generation &&
           c->queue[from].DataSize>=5u &&
           (c->queue[from].Data[4]&0xF0u)==0x20u){
            if(rid)backend_event(c,rid,"rx_dropped","UNKNOWN","flow_overflow","unknown");
            removed++;
            continue;
        }
        if(to!=from){
            bytes_copy(&c->queue[to],&c->queue[from],sizeof(PASSTHRU_MSG));
            c->queue_d2_gen[to]=c->queue_d2_gen[from];
            c->queue_d2_frame[to]=c->queue_d2_frame[from];
            c->queue_ready_us[to]=c->queue_ready_us[from];
            c->queue_trace[to]=c->queue_trace[from];
            c->queue_passive_baud[to]=c->queue_passive_baud[from];
            c->queue_raw_response_baud[to]=c->queue_raw_response_baud[from];
            c->queue_raw_exchange[to]=c->queue_raw_exchange[from];
        }
        keep++;
    }
    c->count=keep;c->w=(c->r+keep)%MAX_QUEUE;
    return removed;
}
static void emit_response(CHANNEL *c,U32 response_id,U32 fc_request_id,const U8 *payload,U32 len) {
    U8 f[8];U32 i;
    backend_event(c,c->active_trace,"response_generated","UNKNOWN","none","unknown");
    /* This compact simulator has only one outstanding segmented response per
       channel. Never release stale CFs from an earlier ECU request. */
    if(c->pending_len){
        U64 previous=c->pending_trace,old_exchange=c->pending_raw_exchange;
        U32 dropped;
        logline("ISO-TP pending transfer superseded by a new ECU response",0,0);
        c->pending_len=0;c->pending_pos=0;c->pending_id=0;
        c->pending_request_id=0;c->pending_sn=0;c->pending_trace=0;
        c->pending_next_us=0;c->pending_stmin_us=0;
        c->pending_cf_active=0;c->pending_cf_credit=0;
        c->pending_raw_exchange=0;
        /* A previous FF or granted CF may already be in the RX FIFO.
           Remove only this unfinished raw exchange, not unrelated traffic. */
        dropped=drop_superseded_raw_iso_rx(c,old_exchange,previous);
        if(dropped){U8 count_be[4];u32_be(count_be,dropped);
            logline("Raw CAN ISO-TP stale queued frames dropped (BE)",count_be,4);}
        backend_abort_pending(c,previous,BACKEND_ABORT_SUPERSEDED);
    }else if(c->protocol==PROTO_CAN && c->pending_raw_exchange){
        /* A CTS/BS=0 can stage EVERY CF before the app reads even the FF.
           pending_len is then zero, but the last multi-frame exchange still
           owns unread raw RX. A new reply must not follow those stale FF/CF.
           An exchange with no queued frames was already delivered: never
           rewrite its successful terminal as a supersession. */
        U32 j,found=0;
        U64 previous=0,old_exchange=c->pending_raw_exchange;
        for(j=0;j<c->count;j++){
            U32 slot=(c->r+j)%MAX_QUEUE;
            if(c->queue_raw_exchange[slot]!=old_exchange)continue;
            previous=c->queue_trace[slot];found=1;break;
        }
        if(found){
            U32 dropped=drop_superseded_raw_iso_rx(c,old_exchange,previous);
            c->pending_raw_exchange=0;
            if(dropped){
                U8 count_be[4];u32_be(count_be,dropped);
                logline("Raw CAN ISO-TP fully queued old exchange dropped (BE)",count_be,4);
            }
            backend_abort_pending(c,previous,BACKEND_ABORT_SUPERSEDED);
        }
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
        if(g_iso_rx_start && len>7 && c->count+2<=MAX_QUEUE){
            U32 slot=c->w,before=c->count;
            enqueue_status(c,response_id,0,0,START_OF_MESSAGE);
            if(c->count>before)c->queue_raw_response_baud[slot]=c->baud;
        }
        {U32 slot=c->w,before=c->count;
         enqueue(c,response_id,payload,len);
         if(c->count>before)c->queue_raw_response_baud[slot]=c->baud;
        }
        return;
    }
    if(len<=7){
        U32 slot=c->w,before=c->count;
        bytes_zero(f,8);f[0]=(U8)len;
        for(i=0;i<len;i++)f[i+1]=payload[i];
        enqueue(c,response_id,f,8);
        if(c->count>before)c->queue_raw_response_baud[slot]=c->baud;
        return;
    }
    if(len>sizeof(c->pending))return;
    bytes_zero(f,8);f[0]=(U8)(0x10|(len>>8));f[1]=(U8)len;
    for(i=0;i<6;i++)f[i+2]=payload[i];
    /* ISO-TP CF staging is valid only if the First Frame was actually
       admitted into this channel's RX FIFO. A strict filter can reject
       it, and a full queue can drop it. Without this guard, a later FC
       could produce orphan CFs, falsely resembling an ECU reply. */
    {U32 slot=c->w,before=c->count;
     enqueue(c,response_id,f,8);
     if(c->count==before){
         logline("Raw CAN ISO-TP first frame not queued; CF staging blocked",0,0);
         return;
     }
     c->queue_raw_response_baud[slot]=c->baud;
     ++c->next_raw_exchange;
     if(!c->next_raw_exchange)++c->next_raw_exchange;
     c->pending_raw_exchange=c->next_raw_exchange;
     c->queue_raw_exchange[slot]=c->pending_raw_exchange;
    }
    bytes_copy(c->pending,payload,len);c->pending_len=len;c->pending_pos=6;
    c->pending_id=response_id;c->pending_sn=1;c->pending_trace=c->active_trace;c->pending_next_us=0;c->pending_stmin_us=0;
}
static U32 answer_lab_tcm_details(U8 mask,U8 single,U8 enabled,const U8 *req,U32 len,U8 *res) {
    static const U8 snapshot[]={0x59,0x04,0x05,0x62,0x00,0x20,0x10,0x06,0xDD,0x02,0x26,0xE1,0x02,0x00,0x00,0xE5,0x00,0x00,0x00,0xE0,0x04,0x00,0x19,0xE5,0x03,0x00,0x00,0xDD,0x05,0x3C};
    static const U8 extended[]={0x59,0x06,0x05,0x62,0x00,0x20,0x01,0x00,0x02,0x00,0x03,0x00,0x04,0x00,0x05,0x00,0x10,0x00,0x11,0x00,0x12,0x00};
    U32 i,j;
    if(mask!=0x20u || !single || !enabled || len<2u || req[0]!=0x19u || (req[1]!=4u && req[1]!=6u))return 0;
    res[0]=0x7Fu;res[1]=0x19u;
    if(len!=6u){res[2]=0x13u;return 3u;}
    if(req[2]!=5u || req[3]!=0x62u || req[4]!=0u){res[2]=0x31u;return 3u;}
    if(req[1]==4u){
        if(req[5]!=0x10u){res[2]=0x31u;return 3u;}
        for(i=0;i<sizeof(snapshot);i++)res[i]=snapshot[i];
        return sizeof(snapshot);
    }
    if(req[5]==0xFFu){for(i=0;i<sizeof(extended);i++)res[i]=extended[i];return sizeof(extended);}
    for(i=6u;i<sizeof(extended);i+=2u)if(extended[i]==req[5]){
        for(j=0;j<6u;j++)res[j]=extended[j];
        res[6]=extended[i];res[7]=extended[i+1];return 8u;
    }
    res[2]=0x31u;return 3u;
}
static U32 answer_lab_dtc(U8 mask,U8 single,const U8 *req,U32 len,U8 *res) {
    if(!mask||!len||req[0]!=0x19u)return 0;
    res[0]=0x7Fu;res[1]=0x19u;
    if(len<2u){res[2]=0x13u;return 3;}
    if(req[1]!=0x02u){res[2]=0x12u;return 3;}
    if(len!=3u){res[2]=0x13u;return 3;}
    /* Status availability is a configured capability, not the requested mask.
       Optional fixed synthetic TCM record; include only on matching status mask. */
    res[0]=0x59u;res[1]=0x02u;res[2]=mask;
    if(single && (mask & req[2] & 0x20u)){
        res[3]=0x05u;res[4]=0x62u;res[5]=0x00u;res[6]=0x20u;return 7;
    }
    return 3;
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
            c->queue_trace[to]=c->queue_trace[from];c->queue_ready_us[to]=c->queue_ready_us[from];
            c->queue_passive_baud[to]=c->queue_passive_baud[from];
            c->queue_raw_response_baud[to]=c->queue_raw_response_baud[from];
            c->queue_raw_exchange[to]=c->queue_raw_exchange[from];}
        keep++;
    }
    c->count=keep;c->w=(c->r+keep)%MAX_QUEUE;
    return dropped;
}
/* On effective DATA_RATE retune, passive/recorded CAN frames produced
   for the old bus must not appear on the new bus. 0 means ordinary RX,
   not passive-source metadata. This only compacts FIFO; no ECU writes. */
static U32 drop_old_bus_passive_rx(CHANNEL *c){
    U32 read,keep=0,removed=0,original=c->count;
    for(read=0;read<original;read++){
        U32 from=(c->r+read)%MAX_QUEUE,to=(c->r+keep)%MAX_QUEUE;
        U32 origin=c->queue_passive_baud[from];
        if(origin && origin!=c->baud){removed++;continue;}
        if(to!=from){
            bytes_copy(&c->queue[to],&c->queue[from],sizeof(PASSTHRU_MSG));
            c->queue_d2_gen[to]=c->queue_d2_gen[from];
            c->queue_d2_frame[to]=c->queue_d2_frame[from];
            c->queue_trace[to]=c->queue_trace[from];
            c->queue_ready_us[to]=c->queue_ready_us[from];
            c->queue_passive_baud[to]=origin;
            c->queue_raw_response_baud[to]=c->queue_raw_response_baud[from];
            c->queue_raw_exchange[to]=c->queue_raw_exchange[from];
        }
        keep++;
    }
    c->count=keep;c->w=(c->r+keep)%MAX_QUEUE;
    return removed;
}
/* Emulator-generated raw CAN and reassembled ISO15765 replies belong to
   their original bitrate. Cancel pending raw CF and compact only marked
   queue slots. Keep passive/ordinary RX, D2 and other channels intact.
   Report discarded request evidence as aborted rather than responded. */
static U32 cancel_old_bus_raw_iso_rx(CHANNEL *c){
    U64 rids[MAX_QUEUE+2u];U32 n=0,read,keep=0,removed=0,original=c->count,i;
    U64 pending_rid=c->pending_len?c->pending_trace:0;
    for(read=0;read<original;read++){
        U32 from=(c->r+read)%MAX_QUEUE,to=(c->r+keep)%MAX_QUEUE;
        U32 origin=c->queue_raw_response_baud[from];
        if(origin && origin!=c->baud){
            U64 rid=c->queue_trace[from];
            if(rid){
                backend_event(c,rid,"rx_dropped","UNKNOWN","bus_rate_change","unknown");
                backend_collect_rid(rids,&n,rid);
            }
            removed++;continue;
        }
        if(to!=from){
            bytes_copy(&c->queue[to],&c->queue[from],sizeof(PASSTHRU_MSG));
            c->queue_d2_gen[to]=c->queue_d2_gen[from];
            c->queue_d2_frame[to]=c->queue_d2_frame[from];
            c->queue_trace[to]=c->queue_trace[from];
            c->queue_ready_us[to]=c->queue_ready_us[from];
            c->queue_passive_baud[to]=c->queue_passive_baud[from];
            c->queue_raw_response_baud[to]=origin;
            c->queue_raw_exchange[to]=c->queue_raw_exchange[from];
        }
        keep++;
    }
    c->count=keep;c->w=(c->r+keep)%MAX_QUEUE;
    if(c->protocol==PROTO_CAN && c->pending_len){
        /* Do not release stored CTS grants after retuning the bus. */
        c->pending_len=0;c->pending_pos=0;c->pending_id=0;
        c->pending_request_id=0;c->pending_sn=0;
        c->pending_trace=0;c->pending_next_us=0;c->pending_stmin_us=0;
        c->pending_cf_active=0;c->pending_cf_credit=0;
        backend_collect_rid(rids,&n,pending_rid);
    }
    for(i=0;i<n;i++)
        backend_abort_pending(c,rids[i],BACKEND_ABORT_SUPERSEDED);
    return removed;
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
    /* A strict CAN data-byte filter may admit frame N but reject N+1.
       A recorded D2 exchange must never skip N+1 and deliver later
       frames as if they were consecutive. enqueue() already recorded
       filter_reject against the originating request; drain accepted
       earlier frames with the eventual terminal outcome 'dropped'. */
    if(c->w==slot){
        U64 rejected=c->d2_trace;
        c->d2_count=0;c->d2_pos=0;c->d2_trace=0;
        logline("P2 D2 frame filtered; remaining recorded frames cancelled",0,0);
        backend_end_if_drained(c,rejected);
        return;
    }
    c->queue_d2_gen[slot]=c->d2_generation;
    c->queue_d2_frame[slot]=c->d2_pos+1;
    c->d2_pos++;
    if(c->d2_pos>=c->d2_count){
        U64 finished=c->d2_trace;
        c->d2_count=0;c->d2_pos=0;c->d2_trace=0;
        backend_end_if_drained(c,finished);
    }
    else c->d2_next_us+=(U64)c->d2_spacing_ms*1000ull;
}
/* A recognized D2 discovery request supersedes the previous D2 exchange
   on this J2534 channel, regardless of whether its own response is recorded.
   Keep unrelated queued RX in FIFO order, and do not synthesize A3/A6 data. */
static void supersede_d2_exchange(CHANNEL *c){
    U32 discarded;
    backend_cancel_channel(c,"d2_superseded",1);
    c->d2_count=0;c->d2_pos=0;c->d2_trace=0;
    discarded=drop_queued_d2(c);
    if(discarded){U8 count_be[4];u32_be(count_be,discarded);
        logline("P2 D2 stale queued frames dropped (BE)",count_be,4);}
}
/* B3A248: synthetic opt-in empty DTC only for an active extra B9F0 route. */
static int lab_d2_empty_reply(const D2_PROFILE *d,const U8 *data,U32 len,U32 baud,U32 flags,U32 tx_flags,U8 *reply){
    U32 j;
    if(!d->lab_empty_dtc || !d->frame_count || d->subcommand!=0xF0u || d->target==0x40u || d->target==0x50u || d->response_id>0x1FFFFFFFu || len!=8u || data[0]!=0xCBu || data[1]!=d->target || data[2]!=0xAEu || (data[3]!=0x1Bu && !(d->target==0x58u && data[3]==0x11u)) || baud!=d->baud || !(flags&CAN_29BIT_ID) || !(tx_flags&CAN_29BIT_ID))return 0;
    for(j=4;j<8;j++)if(data[j])return 0;
    reply[0]=0xCBu;reply[1]=d->target;reply[2]=0xEEu;reply[3]=data[3];
    for(j=4;j<8;j++)reply[j]=0;
    return 1;
}
/* B3A267: opt-in synthetic A5/A6 once-only fixtures. E5/E6 framing is a hypothesis, not OEM evidence. */
typedef struct { U8 req[8]; U8 size; U8 payload[115]; } LAB_CURRENT;
static const LAB_CURRENT lab_current_routes[]={
    {{0xCC,0x51,0xA5,0x0C,0x01,0x00,0x00,0x00},3,{0x01,0xE2,0x40}},
    {{0xCD,0x29,0xA6,0x00,0x11,0x01,0x00,0x00},10,{0x01,0xF4,0x01,0xF4,0x01,0xF4,0x01,0xF4,0x01,0xF4}},
    {{0xCD,0x29,0xA6,0x00,0x12,0x01,0x00,0x00},10,{0x01,0xF4,0x01,0xF4,0x01,0xF4,0x01,0xF4,0x01,0xF4}},
    {{0xCD,0x29,0xA6,0x00,0x13,0x01,0x00,0x00},8,{0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0x16,0x01,0x00,0x00},8,{0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0x17,0x01,0x00,0x00},8,{0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0x48,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0x50,0x01,0x00,0x00},2,{0x00,0x16}},
    {{0xCD,0x29,0xA6,0x00,0x51,0x01,0x00,0x00},2,{0x00,0x16}},
    {{0xCD,0x29,0xA6,0x00,0xA1,0x01,0x00,0x00},2,{0x1E,0x80}},
    {{0xCD,0x29,0xA6,0x00,0xE0,0x01,0x00,0x00},40,{0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0xE1,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0xE2,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0xE3,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0xE4,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0xE5,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0xE6,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0xE7,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0xE8,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0xE9,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0xEA,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0xEB,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0xFB,0x01,0x00,0x00},10,{0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0xFC,0x01,0x00,0x00},6,{0x00,0x00,0x00,0x00,0x00,0x00}},
    {{0xCD,0x29,0xA6,0xD0,0xD6,0x01,0x00,0x00},12,{0x00,0x00,0x00,0x00,0x00,0x16,0x00,0x50,0x64,0x01,0xE2,0x40}},
    {{0xCD,0x40,0xA6,0x1A,0x04,0x01,0x00,0x00},1,{0x06}},
    {{0xCD,0x40,0xA6,0xD0,0xD1,0x01,0x00,0x00},4,{0x00,0x00,0x03,0xE8}},
    {{0xCD,0x46,0xA6,0x6A,0x0A,0x01,0x00,0x00},18,{0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0x05,0x01,0x00,0x00},2,{0x01,0xF4}},
    {{0xCD,0x29,0xA6,0x00,0x06,0x01,0x00,0x00},2,{0x01,0xF4}},
    {{0xCD,0x29,0xA6,0x00,0x07,0x01,0x00,0x00},2,{0x01,0xF4}},
    {{0xCD,0x29,0xA6,0x00,0x08,0x01,0x00,0x00},2,{0x01,0xF4}},
    {{0xCD,0x29,0xA6,0x00,0x09,0x01,0x00,0x00},2,{0x01,0xF4}},
    {{0xCD,0x29,0xA6,0x00,0x0B,0x01,0x00,0x00},2,{0x01,0xF4}},
    {{0xCD,0x29,0xA6,0x00,0x0C,0x01,0x00,0x00},2,{0x01,0xF4}},
    {{0xCD,0x29,0xA6,0x00,0x0D,0x01,0x00,0x00},2,{0x01,0xF4}},
    {{0xCD,0x29,0xA6,0x00,0x0E,0x01,0x00,0x00},2,{0x01,0xF4}},
    {{0xCD,0x29,0xA6,0x00,0x0F,0x01,0x00,0x00},2,{0x01,0xF4}},
    {{0xCD,0x29,0xA6,0x00,0x30,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0x40,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0x47,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x29,0xA6,0x00,0x64,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x29,0xA6,0x00,0x65,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x29,0xA6,0x00,0x72,0x01,0x00,0x00},1,{0x01}},
    {{0xCD,0x29,0xA6,0x00,0x77,0x01,0x00,0x00},7,{0x00,0x00,0x00,0x00,0x00,0x00,0x40}},
    {{0xCD,0x29,0xA6,0x00,0x80,0x01,0x00,0x00},2,{0x03,0x20}},
    {{0xCD,0x46,0xA6,0x1A,0x21,0x01,0x00,0x00},1,{0x01}},
    {{0xCD,0x46,0xA6,0xD0,0xD4,0x01,0x00,0x00},1,{0x64}},
    {{0xCD,0x46,0xA6,0x1A,0x02,0x01,0x00,0x00},2,{0x80,0x00}},
    {{0xCD,0x40,0xA6,0xD0,0xD5,0x01,0x00,0x00},3,{0x01,0xE2,0x40}},
    {{0xCD,0x46,0xA6,0x3C,0x01,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x46,0xA6,0x3F,0x01,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x46,0xA6,0x8F,0x61,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x27,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x31,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x32,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x01,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x04,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x05,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x06,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x10,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x11,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x12,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x13,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x21,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x24,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x26,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x28,0x01,0x00,0x00},1,{0x50}},
    {{0xCD,0x40,0xA6,0x1C,0x29,0x01,0x00,0x00},3,{0x00,0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x30,0x01,0x00,0x00},3,{0x00,0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x33,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x34,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x35,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x36,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x37,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x38,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x39,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x3A,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x3B,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x3C,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x3D,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x40,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1C,0x41,0x01,0x00,0x00},2,{0x00,0x00}},
    {{0xCD,0x40,0xA6,0x1D,0x0B,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1D,0x0C,0x01,0x00,0x00},3,{0x00,0x00,0x00}},
    /* B3A299: 115-byte synthetic reset history, CarCom size only. */
    {{0xCD,0x40,0xA6,0x1D,0x0D,0x01,0x00,0x00},115,{0x00}},
    {{0xCD,0x40,0xA6,0x1E,0x10,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1E,0x11,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1E,0x12,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1E,0x13,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1E,0x14,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1E,0x20,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1E,0x21,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1E,0x22,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1E,0x23,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1E,0x24,0x01,0x00,0x00},1,{0x00}},
    {{0xCD,0x40,0xA6,0x1A,0x02,0x01,0x00,0x00},2,{0x80,0x00}},
    {{0xCD,0x40,0xA6,0xD0,0xD2,0x01,0x00,0x00},1,{0x52}},
 };
static U32 lab_current_frames(const U8 *data,U32 len,U32 baud,U32 flags,U32 tx_flags,U8 frames[][8]){
    U32 i,j,k,n,header,cap,take,pos,count;const LAB_CURRENT *r=0;
    if(len!=8u || baud!=125000u || !(flags&CAN_29BIT_ID) || !(tx_flags&CAN_29BIT_ID))return 0;
    for(i=0;i<sizeof(lab_current_routes)/sizeof(lab_current_routes[0]);i++){
        for(j=0;j<8u;j++)if(data[j]!=lab_current_routes[i].req[j])break;
        if(j==8u){r=&lab_current_routes[i];break;}
    }
    if(!r)return 0;
    if(!r->size || r->size>sizeof(r->payload))return 0;
    n=r->size;header=data[2]==0xA6u?4u:3u;cap=7u-header;
    count=n<=cap?1u:1u+(n-cap+6u)/7u;
    if(count>MAX_D2_FRAMES)return 0;
    for(i=0;i<count;i++)for(j=0;j<8u;j++)frames[i][j]=0;
    frames[0][0]=(U8)(count==1u?0xC8u+header+n:0x8Fu);
    frames[0][1]=data[1];frames[0][2]=(U8)(data[2]+0x40u);frames[0][3]=data[3];
    if(header==4u)frames[0][4]=data[4];
    take=n<cap?n:cap;
    for(j=0;j<take;j++)frames[0][1u+header+j]=r->payload[j];
    pos=take;
    for(k=1;k<count;k++){
        take=n-pos>7u?7u:n-pos;
        frames[k][0]=(U8)(k==count-1u?0x48u+take:(0x08u|(k&7u)));
        for(j=0;j<take;j++)frames[k][1u+j]=r->payload[pos+j];
        pos+=take;
    }
    return count;
}

/* B3A320: exact existing REM voltage response only, nearest 125 mV. */
static void lab_rem_voltage_sync(U32 enabled,U32 mv,const U8 *req,U32 len,U32 count,U8 frames[][8]){
    static const U8 target[8]={0xCD,0x46,0xA6,0xD0,0xD4,1,0,0};
    static const U8 header[5]={0xCD,0x46,0xE6,0xD0,0xD4};
    U32 i;
    if(enabled!=1u || !req || !frames || len!=8u || count!=1u || mv>20000u)return;
    for(i=0;i<8u;i++)if(req[i]!=target[i])return;
    for(i=0;i<5u;i++)if(frames[0][i]!=header[i])return;
    frames[0][5]=(U8)((mv+62u)/125u);
}

/* B3A324: only existing observed synthetic voltage reads; catalog-based rounding. */
static U32 lab_voltage_raw(U32 kind,U32 mv){
    if(kind==1u)return (mv*65535u+12500u)/25000u;
    if(kind==2u)return (mv*64u+500u)/1000u;
    return (mv+125u)/250u;
}
static void lab_supply_voltage_sync(U32 enabled,U32 mv,const U8 *req,U32 len,U32 count,U8 frames[][8]){
    static const U8 targets[2][8]={{0xCD,0x46,0xA6,0x1A,0x02,1,0,0},{0xCD,0x29,0xA6,0x00,0x80,1,0,0}};
    U32 i,j,raw;
    if(enabled!=1u || !req || !frames || len!=8u || count!=1u || mv>20000u)return;
    for(i=0;i<2u;i++){
        for(j=0;j<8u;j++)if(req[j]!=targets[i][j])break;
        if(j!=8u)continue;
        if(frames[0][0]!=0xCEu || frames[0][1]!=req[1] || frames[0][2]!=0xE6u ||
           frames[0][3]!=req[3] || frames[0][4]!=req[4])return;
        raw=lab_voltage_raw(i+1u,mv);
        frames[0][5]=(U8)(raw>>8);frames[0][6]=(U8)raw;
        return;
    }
}
static U8 lab_cem_voltage_byte(U32 enabled,U32 mv){
    return enabled==1u && mv<=20000u ? (U8)lab_voltage_raw(3u,mv) : 0x32u;
}
/* B3A324 helper end */
static int process_d2(CHANNEL *c,U32 id,const U8 *data,U32 len,U32 tx_flags){
    U32 i;D2_PROFILE *d;const char *route;
    if(id!=0x000FFFFEu || c->protocol!=PROTO_CAN)return 0;
    /* Only this separate lab switch permits A5/A6 responses. Never answer A3. */
    if(g_b3a267_current_lab && len>=3u && (data[2]==0xA5u||data[2]==0xA6u) &&
       (data[1]==0x29u||data[1]==0x40u||data[1]==0x46u||data[1]==0x51u)){
        U32 count;
        supersede_d2_exchange(c);
        route=data[1]==0x40u?"CEM":"ECU_OTHER";
        backend_event(c,c->active_trace,"route_selected",route,"none","unknown");
        count=lab_current_frames(data,len,c->baud,c->flags,tx_flags,c->d2_frame);
        lab_rem_voltage_sync(g_b3a320_rem_sync,g_battery_mv,data,len,count,c->d2_frame);
        lab_supply_voltage_sync(g_b3a324_supply_sync,g_battery_mv,data,len,count,c->d2_frame);
        if(!count){logline("B3A267 LAB current data unsupported shape/bus/mode",data,len);
            backend_event(c,c->active_trace,"request_completed",route,"no_response","no_response");return 1;}
        c->d2_trace=c->active_trace;
        backend_event(c,c->active_trace,"response_generated",route,"none","unknown");
        c->d2_generation++;if(!c->d2_generation)c->d2_generation=1;
        c->d2_response_id=0x00800003u;c->d2_count=count;
        c->d2_spacing_ms=g_d2_spacing_ms;c->d2_next_us=now_us();
        logline("B3A267 LAB current data synthetic E5/E6 (not OEM verified)",data,len);
        pump_d2(c);return 1;
    }

    /* Issue #4: A3/A6 are recognizable CEM *requests*, not implemented ECU
       responses. Keep them silent, but distinguish the known missing emulator
       implementation from an arbitrary CAN ID or an absent B9 fixture.
       Never synthesize E3/E6, an ignition state, or a module identity. */
    if(cem_d2_probe_shape(data,len)){
        /* A3/A6 must not inherit old B9FB frames as a false probe reply. */
        supersede_d2_exchange(c);
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
    /* B3A228: isolated synthetic hypothesis for CEM40 AE 1B only.
       Empty reply layout inferred from public D2 evidence for another ECU.
       Response ID borrowed from the existing CEM40 B9F0 lab fixture.
       Not a recorded or OEM-verified CEM DTC response. Disabled by default. */
    if(g_b3a228_cem40_empty_dtc && len>=4u && data[1]==0x40u && data[2]==0xAEu && data[3]==0x1Bu){
        static const U8 empty_frame[8]={0xCBu,0x40u,0xEEu,0x1Bu,0,0,0,0};
        supersede_d2_exchange(c);
        backend_event(c,c->active_trace,"route_selected","CEM","none","unknown");
        if(len!=8u || data[0]!=0xCBu ||
           data[4] || data[5] || data[6] || data[7] ||
           c->baud!=125000u || !(c->flags&CAN_29BIT_ID) ||
           !(tx_flags&CAN_29BIT_ID)){
            logline("B3A228 LAB CEM40 AE1B route/shape rejected",data,4);
            backend_event(c,c->active_trace,"request_completed","CEM","no_response","no_response");
            return 1;
        }
        c->d2_trace=c->active_trace;
        backend_event(c,c->active_trace,"response_generated","CEM","none","unknown");
        c->d2_generation++;
        if(!c->d2_generation)c->d2_generation=1;
        c->d2_response_id=0x00800003u;c->d2_count=1u;
        c->d2_spacing_ms=g_d2_spacing_ms;c->d2_next_us=now_us();
        bytes_copy(c->d2_frame[0],empty_frame,8);
        logline("B3A228 LAB CEM40 AE1B empty candidate (not OEM verified)",data,4);
        pump_d2(c);
        return 1;
    }
    /* Do not infer DTC support from identification alone. */
    if(len>=4u && data[2]==0xAEu && (data[3]==0x1Bu || (data[1]==0x58u && data[3]==0x11u))){
        for(i=BASE_D2_FIXTURES;i<MAX_D2_FIXTURES;i++){
            U8 reply[8];
            d=&g_d2[i];
            if(!d->lab_empty_dtc || !d->frame_count || d->target!=data[1] || d->subcommand!=0xF0u)continue;
            supersede_d2_exchange(c);
            backend_event(c,c->active_trace,"route_selected","ECU_OTHER","none","unknown");
            if(!lab_d2_empty_reply(d,data,len,c->baud,c->flags,tx_flags,reply)){
                logline("B3A248 LAB D2 AE1B route/shape rejected",data,4);
                backend_event(c,c->active_trace,"request_completed","ECU_OTHER","no_response","no_response");
                return 1;
            }
            c->d2_trace=c->active_trace;
            backend_event(c,c->active_trace,"response_generated","ECU_OTHER","none","unknown");
            c->d2_generation++;if(!c->d2_generation)c->d2_generation=1;
            c->d2_response_id=d->response_id;c->d2_count=1u;
            c->d2_spacing_ms=g_d2_spacing_ms;c->d2_next_us=now_us();
            bytes_copy(c->d2_frame[0],reply,8);
            logline(data[3]==0x11u?"B3A277 LAB SRS AE11 empty candidate (not OEM verified)":"B3A248 LAB D2 AE1B empty candidate (not OEM verified)",data,4);
            pump_d2(c);return 1;
        }
    }
    if(len<4 || data[0]!=0xCBu || data[2]!=0xB9u ||
       (data[3]!=0xFBu&&data[3]!=0xF0u&&data[3]!=0xFCu&&!lab_special_b9(data[1],data[3])))return 0;
    if(lab_special_b9(data[1],data[3]) && !lab_special_request(data,len,c->baud,c->flags,tx_flags)){
        supersede_d2_exchange(c);
        logline("B3A261 LAB special B9 shape/bus rejected",data,4);
        return 1;
    }
    route=(data[1]==0x40u||data[1]==0x50u)?"CEM":"ECU_OTHER";
    backend_event(c,c->active_trace,"route_selected",route,"none","unknown");
    {U8 detail[16];
     u32_be(detail,data[1]);u32_be(detail+4,data[3]);
     u32_be(detail+8,c->baud);u32_be(detail+12,c->flags);
     logline("P2 D2 request target/opcode/baud/flags (BE)",detail,16);}
    /* B9 reads and known A3/A6 probes use the same old-D2 cancellation.
       Do it before fixture lookup, even if the new target is unconfigured. */
    supersede_d2_exchange(c);
    for(i=0;i<MAX_D2_FIXTURES;i++){
        U32 j;
        d=&g_d2[i];if(data[1]!=d->target||data[3]!=d->subcommand)continue;
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
            logline(data[1]==0x40u && data[3]==0x31u ? "B3A302 LAB synthetic B9 31 (not OEM verified)" : "P2 D2 read-only recorded frames staged",data,4);
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
/* B3A148: Optional, fail-closed physical ECU route binding.
   Unconfigured legacy ECUs keep their established functional behavior. */
static int ecu_bus_route_allows(const ECU *ecu,const CHANNEL *c,U32 tx_id,U32 tx_flags){
    if(!ecu->expected_baud)return 1;
    if(c->baud!=ecu->expected_baud)return 0;
    /* An extended physical target must not be reached through 11-bit
       functional fanout or a TX lacking CAN_29BIT_ID. */
    if(ecu->req>0x7FFu && (tx_id!=ecu->req || !(tx_flags&CAN_29BIT_ID)))return 0;
    return 1;
}
/* B3A150: synthetic, opt-in CarCom CEM GGD 529 / Config 541 evidence.
   EXACT 29-bit physical ISO15765/500k route, not OEM-recorded ECU values.
   Empty result means silence; never fall through to generic NRC 7F 22 31. */
static U32 answer_b3a150_ggd_cem50_lab(const CHANNEL *c,const ECU *ecu,
                                        U32 can_id,U32 tx_flags,
                                        const U8 *req,U32 len,U8 *res){
    if(!g_b3a150_ggd_cem_lab || !c || !ecu || !req || !res ||
       c->api_protocol!=PROTO_ISO15765 || c->protocol!=PROTO_ISO15765 ||
       c->baud!=500000u || c->flags!=CAN_29BIT_ID ||
       (tx_flags&CAN_29BIT_ID)==0u ||
       (tx_flags&~(CAN_29BIT_ID|0x40u))!=0u ||
       can_id!=0x18DA50F1u || ecu->req!=0x18DA50F1u ||
       ecu->resp!=0x18DAF150u || ecu->expected_baud!=500000u ||
       len!=3u || req[0]!=0x22u)return 0;
    if(req[1]==0xF1u && req[2]==0x10u){
        U32 n=vc0662_f110_answer(g_vc0662_f110,req,len,res,256u);
        if(n)logline("VC0662 CEM529 F110 catalog LAB reply (not OEM verified)",0,0);
        return n;
    }
    if(req[1]==0xF1u && (req[2]==0x91u || req[2]==0x88u || req[2]==0x8Cu || req[2]==0x20u)){
        U32 n=vc0663_identity_answer(g_vc0663_identity,req,len,res,256u);
        if(n)logline("VC0663 CEM529 synthetic identity LAB reply (not OEM verified)",req,len);
        return n;
    }
    if(req[1]==0xF1u && req[2]==0x06u){
        U32 n=vc054_answer(&g_vc054_f106,req,len,res,256u);
        if(n)logline("VC054 F106 donor-format LAB reply (not OEM verified)",0,0);
        return n;
    }
    if(req[1]==0xA4u && req[2]==0x5Fu){
        /* B3A157: raw 0x07 is only a laboratory hypothesis about switch bits.
           Original B3A150 0x04 remains the default for every existing INI. */
        res[0]=0x62u;res[1]=0xA4u;res[2]=0x5Fu;
        res[3]=g_b3a157_posii_candidate?0x07u:0x04u;
        logline("B3A150 LAB GGD CEM A45F positive (synthetic)",req,len);
        return 4u;
    }
    if(req[1]==0xDDu && req[2]==0x02u){
        /* LAB-only 0x32 * 0.25 V = 12.50 V; not OEM-captured voltage. */
        res[0]=0x62u;res[1]=0xDDu;res[2]=0x02u;res[3]=lab_cem_voltage_byte(g_b3a324_supply_sync,g_battery_mv);
        logline("B3A150 LAB GGD CEM DD02 positive (synthetic)",req,len);
        return 4u;
    }
    return 0;
}
/* B3A315 shared synthetic ECM snapshot; immutable until a separately tested state source exists. */
typedef struct {
    U32 battery_mv,rpm,speed_kph,pedal_permille,load_permille,maf_centi_gps;
    U32 ambient_kpa,manifold_kpa;
    int coolant_c,intake_c,ecm_c;
} ECM_LAB_STATE;
/* B3A316: owner-selected fixed synthetic snapshots, not an OEM calibration. */
static const ECM_LAB_STATE g_ecm_lab_scenarios[]={
    {12500u,0u,0u,0u,0u,0u,100u,100u,20,20,20},
    {10500u,200u,0u,0u,150u,200u,100u,90u,20,20,20},
    {14200u,1100u,0u,0u,250u,900u,100u,45u,20,20,25},
    {14000u,900u,0u,0u,200u,700u,100u,38u,60,25,35},
    {14000u,700u,0u,0u,180u,550u,100u,35u,90,30,45}
};
static U32 g_ecm_lab_scenario=0u;
static ECM_LAB_STATE g_ecm_lab_dynamic_state;
static U32 g_ecm_lab_dynamic_active=0u;
static void ecm_lab_select_scenario(U32 enabled,const char *state){
    g_ecm_lab_dynamic_active=0u;
    g_ecm_lab_scenario=0u;
    if(enabled==1u && state && state[0]>='0' && state[0]<='4' && state[1]=='\0')
        g_ecm_lab_scenario=(U32)(state[0]-'0');
}
#define g_ecm_lab_state (*(g_ecm_lab_dynamic_active?&g_ecm_lab_dynamic_state:&g_ecm_lab_scenarios[g_ecm_lab_scenario]))
/* B3A319: explicit lab opt-in; preserve configured voltage outside ECM baseline mode. */
static U32 ecm_lab_battery_mv(U32 configured,U32 sync_enabled,U32 baseline_enabled){
    return sync_enabled==1u && baseline_enabled==1u ? g_ecm_lab_state.battery_mv : configured;
}
static U32 ecm_lab_temperature_valid(int t){return t>=-40 && t<=119;}
static U32 ecm_lab_state_valid(const ECM_LAB_STATE *s){
    return s && s->battery_mv<=20000u && s->rpm<=16383u && s->speed_kph<=255u &&
        s->pedal_permille<=1000u && s->load_permille<=1000u && s->maf_centi_gps<=65535u &&
        s->ambient_kpa<=127u && s->manifold_kpa<=255u && ecm_lab_temperature_valid(s->coolant_c) &&
        ecm_lab_temperature_valid(s->intake_c) && ecm_lab_temperature_valid(s->ecm_c);
}
/* Encode integer rpm as candidate IEEE binary32, big endian; nonzero wire format is not VIDA-verified. */
static U32 ecm_lab_rpm_bits(U32 rpm){
    U32 e=0u,v=rpm;
    if(!rpm)return 0u;
    while(v>1u){v>>=1;e++;}
    return ((127u+e)<<23)|((rpm<<(23u-e))&0x7FFFFFu);
}
/* Candidate IEEE binary32 for centi-g/s, rounded to nearest/even. No CRT or FP dependency. */
static U32 ecm_lab_maf_bits(U32 centi){
    U32 num=centi,den=100u,frac=0u,i,rem;int exponent=127;
    if(!num)return 0u;
    while(num<den){num*=2u;exponent--;}
    while(num>=2u*den){den*=2u;exponent++;}
    rem=num-den;
    for(i=0;i<23u;i++){
        rem*=2u;frac<<=1;
        if(rem>=den){frac|=1u;rem-=den;}
    }
    if(rem*2u>den || (rem*2u==den && (frac&1u)))frac++;
    return ((U32)exponent<<23)+frac;
}
static U32 ecm_lab_encode(const ECM_LAB_STATE *s,U32 extended,U32 did,U8 *out){
    U32 raw=0u,n=0u,i;
    if(!out||!ecm_lab_state_valid(s))return 0;
    if(!extended){
        switch(did){
        case 0x120Du: n=2u;raw=(s->battery_mv*65536u+10000u)/20000u;if(raw>65535u)raw=65535u;break;
        case 0xD998u: n=1u;raw=((U32)(s->intake_c+40)*8u+2u)/5u;break;
        case 0xD99Bu: n=1u;raw=((U32)(s->coolant_c+40)*8u+2u)/5u;break;
        case 0xDA48u: n=4u;raw=ecm_lab_rpm_bits(s->rpm);break;
        case 0xF40Cu: n=2u;raw=s->rpm*4u;break;
        case 0xF40Du: n=1u;raw=s->speed_kph;break;
        case 0xF40Fu: n=1u;raw=(U32)(s->intake_c+40);break;
        default:return 0;
        }
    }else{
        switch(did){
        case 0xD9ACu: case 0xD9ADu: n=2u;raw=s->pedal_permille;break;
        case 0xD9B8u: n=1u;raw=((U32)(s->ecm_c+40)*8u+2u)/5u;break;
        case 0xF404u: n=1u;raw=(s->load_permille*255u+500u)/1000u;break;
        case 0xF405u: n=1u;raw=(U32)(s->coolant_c+40);break;
        case 0xF410u: n=2u;raw=s->maf_centi_gps;break;
        /* B3A318: observed VIDA reads; equal load values are a simplified lab assumption. */
        case 0xF443u: n=2u;raw=(s->load_permille*255u+500u)/1000u;break;
        case 0xD994u: n=4u;raw=ecm_lab_maf_bits(s->maf_centi_gps);break;
        case 0xF433u: n=1u;raw=s->ambient_kpa;break;
        case 0xF449u: case 0xF44Au: n=1u;raw=(s->pedal_permille*255u+500u)/1000u;break;
        case 0xF40Bu: n=1u;raw=s->manifold_kpa;break;
        case 0xD9A4u: n=1u;raw=s->ambient_kpa*2u;break;
        case 0xDA47u: n=2u;raw=(s->manifold_kpa*65536u+250u)/500u;break;
        default:return 0;
        }
    }
    for(i=0;i<n;i++)out[i]=(U8)(raw>>(8u*(n-1u-i)));
    return n;
}
/* B3A315 shared ECM snapshot end */
/* B3A329 deterministic synthetic timeline; no diagnostic writes. */
static int ecm_lab_lerp(int a,int b,U32 pos,U32 span){
    return a+(b-a)*(int)pos/(int)span;
}
static void ecm_lab_sample(U32 elapsed,ECM_LAB_STATE *out){
    static const U32 times[]={0u,2000u,4000u,60000u,180000u};
    U32 i=0u,pos,span;
    const ECM_LAB_STATE *a,*b;
    while(i<3u && elapsed>=times[i+1u])i++;
    a=&g_ecm_lab_scenarios[i];b=&g_ecm_lab_scenarios[i+1u];
    span=times[i+1u]-times[i];pos=elapsed>=times[i+1u]?span:elapsed-times[i];
#define MIX(field) out->field=ecm_lab_lerp((int)a->field,(int)b->field,pos,span)
    MIX(battery_mv);MIX(rpm);MIX(speed_kph);MIX(pedal_permille);MIX(load_permille);MIX(maf_centi_gps);
    MIX(ambient_kpa);MIX(manifold_kpa);MIX(coolant_c);MIX(intake_c);MIX(ecm_c);
#undef MIX
}
static U32 g_ecm_lab_epoch=0u,g_ecm_lab_finished=0u;
static void ecm_lab_dynamic_start(U32 enabled,U32 now){
    g_ecm_lab_dynamic_active=enabled==1u;
    g_ecm_lab_epoch=now;g_ecm_lab_finished=0u;
    if(g_ecm_lab_dynamic_active)ecm_lab_sample(0u,&g_ecm_lab_dynamic_state);
}
static void ecm_lab_dynamic_tick(U32 now){
    U32 elapsed;
    if(!g_ecm_lab_dynamic_active||g_ecm_lab_finished)return;
    elapsed=now-g_ecm_lab_epoch;
    ecm_lab_sample(elapsed,&g_ecm_lab_dynamic_state);
    if(elapsed>=180000u)g_ecm_lab_finished=1u;
}
/* B3A329 timeline end */
/* All callers hold the state lock; one snapshot per processed request/IOCTL. */
static void ecm_lab_refresh(void){
    if(g_open && g_ecm_lab_dynamic_active){
        ecm_lab_dynamic_tick(GetTickCount());
        g_battery_mv=g_ecm_lab_state.battery_mv;
    }
}
/* B3A309: synthetic stationary ECM 30670321 AA live data. Catalog
   scaling and runtime requests are evidence; payloads are not OEM captures.
   Keep this independent of the generic F1xx identification whitelist. */
static U32 answer_b3a309_ecm_live_lab(const CHANNEL *c,const ECU *ecu,
                                        U32 can_id,U32 tx_flags,
                                        const U8 *req,U32 len,U8 *res){
    U32 did,n;
    if(!g_b3a309_ecm_live_lab || !c || !ecu || !req || !res ||
       c->api_protocol!=PROTO_ISO15765 || c->protocol!=PROTO_ISO15765 ||
       c->baud!=500000u || c->flags!=CAN_29BIT_ID ||
       !(tx_flags&CAN_29BIT_ID) || (tx_flags&~(CAN_29BIT_ID|0x40u)) ||
       can_id!=0x18DA10F1u || ecu->req!=0x18DA10F1u ||
       ecu->resp!=0x18DAF110u || ecu->expected_baud!=500000u ||
       len!=3u || req[0]!=0x22u)return 0;
    did=((U32)req[1]<<8)|req[2];
    n=ecm_lab_encode(&g_ecm_lab_state,0u,did,res+3u);
    if(!n)return 0;
    res[0]=0x62u;res[1]=req[1];res[2]=req[2];
    logline("B3A309 ECM live data positive (synthetic)",req,len);
    return 3u+n;
}
/* B3A314: catalog-derived synthetic stopped-engine candidates; not OEM wire captures. */
static U32 answer_b3a314_ecm_live_lab(const CHANNEL *c,const ECU *ecu,
                                        U32 can_id,U32 tx_flags,
                                        const U8 *req,U32 len,U8 *res){
    U32 did,n;
    if(!g_b3a314_ecm_live_lab || !c || !ecu || !req || !res ||
       c->api_protocol!=PROTO_ISO15765 || c->protocol!=PROTO_ISO15765 ||
       c->baud!=500000u || c->flags!=CAN_29BIT_ID ||
       !(tx_flags&CAN_29BIT_ID) || (tx_flags&~(CAN_29BIT_ID|0x40u)) ||
       can_id!=0x18DA10F1u || ecu->req!=0x18DA10F1u ||
       ecu->resp!=0x18DAF110u || ecu->expected_baud!=500000u ||
       len!=3u || req[0]!=0x22u)return 0;
    did=((U32)req[1]<<8)|req[2];
    n=ecm_lab_encode(&g_ecm_lab_state,1u,did,res+3u);
    if(!n)return 0;
    res[0]=0x62u;res[1]=req[1];res[2]=req[2];
    logline("B3A314 ECM extended live data positive (synthetic)",req,len);
    return 3u+n;
}
static void process_request(CHANNEL *c,const PASSTHRU_MSG *msg){
    U32 id,i,n,sz;U8 payload[256],answer[256];const ECU *ecu;
    const char *route;
    int matched=0,answered=0;
    const U8 *data;
    if(msg->DataSize<5||msg->DataSize>MAX_DATA)return;
    ecm_lab_refresh();
    id=((U32)msg->Data[0]<<24)|((U32)msg->Data[1]<<16)|((U32)msg->Data[2]<<8)|msg->Data[3];
    if(process_d2(c,id,msg->Data+4,msg->DataSize-4,msg->TxFlags))return;
    /* FF C8 is documented as a broadcast ECU reset in published P2 logs.
       We do not emulate a physical reset or fabricate an acknowledgment. */
    if(id==0x000FFFFEu && msg->DataSize>=6 && msg->Data[4]==0xFF && msg->Data[5]==0xC8){
        logline("P2 FF C8 broadcast reset: no physical ECU; intentionally silent",msg->Data,msg->DataSize);
        backend_event(c,c->active_trace,"route_selected","CEM","none","unknown");
        backend_event(c,c->active_trace,"request_completed","CEM","no_response","no_response");
        return;
    }
    for(i=0;i<g_ecu_count;i++){
        ecu=&g_ecu[i];if(ecu->req==0xFFFFFFFFu)continue;
        if(id!=ecu->req&&id!=0x7DF)continue;
        if(!ecu_bus_route_allows(ecu,c,id,msg->TxFlags)){
            logline("ECU route rejected: baud or physical TX flags",0,0);
            continue; /* A route mismatch is SILENT; no negative UDS reply. */
        }
        n=msg->DataSize-4;data=msg->Data+4;
        if(c->protocol==PROTO_CAN){
            if((data[0]&0xF0)==0x30 && c->pending_len){
                if(id!=c->pending_request_id){
                    /* A FC-like frame for another ECU is not the Flow
                       Control of this exchange. Leave the old transfer
                       intact, then classify this TX as unhandled exactly
                       once (including a short or malformed FC frame). */
                    logline("ISO-TP FC ignored (different request CAN ID)",msg->Data,msg->DataSize);
                    continue;
                }
                if(n<3){
                    logline("ISO-TP FC ignored (missing block size or STmin)",msg->Data,msg->DataSize);
                    return;
                }
                if((data[0]&15)==1){
                    /* WAIT suspends an outstanding grant; another CTS is required. */
                    c->pending_cf_active=0;c->pending_cf_credit=0;
                    logline("ISO-TP FC WAIT received",msg->Data,msg->DataSize);return;
                }
                if((data[0]&15)==2){
                    U64 previous=c->pending_trace,old_exchange=c->pending_raw_exchange;
                    U32 dropped;
                    logline("ISO-TP FC OVERFLOW received; pending response discarded",msg->Data,msg->DataSize);
                    /* A prior BS grant may have staged CF into RX already.
                       Retract its unread CF, but preserve the previously sent
                       FF and unrelated FIFO frames. Never resume old credits. */
                    dropped=drop_overflow_raw_iso_cf_rx(c,old_exchange,previous);
                    c->pending_len=0;c->pending_pos=0;c->pending_id=0;
                    c->pending_request_id=0;c->pending_sn=0;c->pending_trace=0;
                    c->pending_next_us=0;c->pending_stmin_us=0;
                    c->pending_cf_active=0;c->pending_cf_credit=0;
                    c->pending_raw_exchange=0;
                    if(dropped){U8 count_be[4];u32_be(count_be,dropped);
                        logline("Raw CAN ISO-TP FC OVERFLOW queued CF dropped (BE)",count_be,4);}
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
              ((ecu->req==0x726u||ecu->req==0x18DA50F1u)?"CEM":
               ((ecu->req==0x7E0u||ecu->req==0x18DA10F1u)?"ECM":"ECU_OTHER"));
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
        if(id==0x18DA50F1u && ecu->req==id){
            /* Disabled/wrong channel/unknown DID => no generic synthetic NRC. */
            sz=answer_b3a150_ggd_cem50_lab(c,ecu,id,msg->TxFlags,payload,n,answer);
            if(!sz){
                logline("B3A150 GGD CEM disabled/unverified request: silent",0,0);
                backend_event(c,c->active_trace,"request_completed",route,"no_response","no_response");
                return;
            }
        } else if(ecu->req==id && ecu->lab_dtc_mask && lab_dtc_route_allowed(ecu->req,ecu->resp,ecu->expected_baud) && n && payload[0]==0x19u){
            sz=answer_lab_tcm_details(ecu->lab_dtc_mask,ecu->lab_dtc_single,ecu->lab_dtc_details,payload,n,answer);
            if(!sz)sz=answer_lab_dtc(ecu->lab_dtc_mask,ecu->lab_dtc_single,payload,n,answer);
            if(sz && answer[0]==0x59u && answer[1]!=0x02u)logline("B3A238 synthetic TCM DTC details (not OEM verified)",0,0);
            else if(sz && answer[0]==0x59u)logline(sz==7u?"B3A231 synthetic TCM 056200 DTC record (not OEM verified)":"Synthetic ECU empty DTC list (not OEM verified)",0,0);
        } else {
            sz=answer_b3a314_ecm_live_lab(c,ecu,id,msg->TxFlags,payload,n,answer);
            if(!sz)sz=answer_b3a309_ecm_live_lab(c,ecu,id,msg->TxFlags,payload,n,answer);
            if(!sz)sz=answer_uds(ecu,payload,n,answer);
        }
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

/* Every actual read-only request needs one transaction ID, including
   requests emitted by the periodic scheduler. Only a CAN ISO-TP Flow Control
   for this channel's ACTIVE, exact physical ECU request grants/stops the
   previous response and must NOT create a fresh diagnostic request. A late
   or misaddressed FC-like frame instead receives ordinary unhandled TX
   evidence; never disguise its presence by checking PCI alone. */
static void begin_tx_evidence(CHANNEL *c,const PASSTHRU_MSG *msg){
    if(c->protocol==PROTO_CAN && c->pending_len && msg->DataSize>=5u &&
       (msg->Data[4]&0xF0u)==0x30u &&
       can_id_from_data(msg->Data)==c->pending_request_id){
        c->active_trace=0;return;
    }
    c->active_trace=next_backend_request();
    backend_event(c,c->active_trace,"tx_received","UNKNOWN","none","unknown");
    backend_probe_event(c,c->active_trace,msg);
}
/* No physical bus: periodic requests are replayed only while the client
   polls ReadMsgs. Never spawn a background vehicle writer. */
static void pump_periodic(CHANNEL *c){
    U32 i;U64 now=now_us();
    if(is_ps_protocol(c->api_protocol) && !c->ps_pins)return;
    for(i=0;i<MAX_PERIODIC;i++){
        PERIODIC *p=&c->periodic[i];
        if(!p->used || now<p->next_us || c->count>=MAX_QUEUE)continue;
        p->next_us=now+(U64)p->interval_ms*1000ull;
        /* Give text-log triage an exact channel/protocol/timing scope for
           scheduled TX without disguising the tick as PassThruWriteMsgs.
           The context contains no VIN, CAN payload or ECU identity. */
        {U8 meta[20];u32_be(meta,c->id);u32_be(meta+4,c->protocol);
         u32_be(meta+8,p->msg.TxFlags);u32_be(meta+12,c->baud);
         u32_be(meta+16,(U32)now);
         logline("Periodic TX context channel/protocol/flags/baud/time-us (BE)",meta,20);}
        logline("J2534 periodic TX (read-only simulator)",p->msg.Data,p->msg.DataSize);
        /* Periodic D2 reads previously replayed frames with RID=0, so no
           tx_received/probe/terminal evidence could be attributed to them.
           Keep the distinct periodic log marker: this is a scheduler tick,
           not a fresh direct PassThruWriteMsgs call from the GUI. */
        {
            p2_bridge_tx_result observed;
            if(p2_bridge_inspect_tx_at(&g_vehicle_bridge,c->id,p->msg.TxFlags,
                    p->msg.Data,p->msg.DataSize,now_us(),&observed)) {
                if(observed.label && observed.decision!=P2_CEM_KEEP_EXISTING)
                    logline(observed.label,0,0);
                if(observed.hw_event!=P2_HW_UNRELATED)
                    logline(p2_hw_tx_event_name(observed.hw_event),0,0);
            }
        }
        begin_tx_evidence(c,&p->msg);
        process_request(c,&p->msg);
        c->active_trace=0;
    }
}
/* Standard 04.04 API. Undecorated export names are defined in virtualcar.def. */
EXPORT U32 WINCALL PassThruOpen(PTR name,U32 *device) {
    (void)name;if(!device)return error(ERR_NULL_PARAMETER);
    /* Open must test the device under the same lock that resets channels.
       A concurrent first Open may finish after an earlier unlocked check. */
    lock_state();
    if(g_open){unlock_state();return error(ERR_DEVICE_IN_USE);}
    g_open=1;bytes_zero(g_ch,sizeof(g_ch));p2_bridge_init(&g_vehicle_bridge);load_config();
    ecm_lab_dynamic_start(g_b3a329_dynamic_lab,GetTickCount());ecm_lab_refresh();*device=1;
    logline("PassThruOpen -> device 1",0,0);unlock_state();return error(ERR_OK);
}
EXPORT U32 WINCALL PassThruClose(U32 device) {
    U32 i;
    if(device!=1)return error(ERR_INVALID_DEVICE_ID);
    /* Do not close state that another thread already closed after an
       unlocked g_open check. The close operation owns the state lock. */
    lock_state();
    if(!g_open){unlock_state();return error(ERR_INVALID_DEVICE_ID);}
    for(i=0;i<MAX_CHANNELS;i++)if(g_ch[i].used)
        backend_cancel_channel(&g_ch[i],"device_close",0);
    g_open=0;bytes_zero(g_ch,sizeof(g_ch));p2_bridge_init(&g_vehicle_bridge);
    logline("PassThruClose",0,0);unlock_state();return error(ERR_OK);
}
EXPORT U32 WINCALL PassThruConnect(U32 device,U32 protocol,U32 flags,U32 baud,U32 *channel_id){
    U32 i;
    if(!channel_id)return connect_result(protocol,flags,baud,ERR_NULL_PARAMETER);
    if(device!=1)return connect_result(protocol,flags,baud,ERR_INVALID_DEVICE_ID);
    /* Check open state and allocate a channel in one critical section.
       Otherwise a simultaneous Close can clear g_open between the unlocked
       check and this allocation, creating a live channel on a closed device. */
    lock_state();
    if(!g_open){unlock_state();return connect_result(protocol,flags,baud,ERR_INVALID_DEVICE_ID);}
    /* PS aliases are accepted ONLY for an explicitly configured laboratory provider.
       No unknown vendor protocol may be reclassified into a CAN channel. */
    if(protocol!=PROTO_CAN && protocol!=PROTO_ISO15765 &&
       !(g_j2534_ps_enabled && is_ps_protocol(protocol))){
        unlock_state();return connect_result(protocol,flags,baud,ERR_INVALID_PROTOCOL_ID);
    }
    /* PS is restricted to our two tested virtual J1962 CAN bus rates. */
    if(baud==0u || (is_ps_protocol(protocol) && baud!=500000u && baud!=125000u)){
        unlock_state();return connect_result(protocol,flags,baud,ERR_INVALID_BAUDRATE);
    }
    for(i=0;i<MAX_CHANNELS;i++)if(!g_ch[i].used)break;
    if(i==MAX_CHANNELS){unlock_state();return connect_result(protocol,flags,baud,ERR_EXCEEDED_LIMIT);}
    bytes_zero(&g_ch[i],sizeof(CHANNEL));g_ch[i].used=1;g_ch[i].id=i+1;
    ++g_next_channel_serial;
    if(!g_next_channel_serial)++g_next_channel_serial;
    g_ch[i].session_serial=g_next_channel_serial;
    g_ch[i].protocol=canonical_protocol(protocol);
    g_ch[i].api_protocol=protocol;
    g_ch[i].ps_pins=0u; /* Fail closed until SET_CONFIG(J1962_PINS). */
    g_ch[i].flags=flags;g_ch[i].baud=baud;
    g_ch[i].passive_next_tick=GetTickCount()+g_passive_period_ms;
    {U32 k;for(k=0;k<MAX_PASSIVE_TRACES;k++)
        g_ch[i].trace_next_tick[k]=GetTickCount()+g_trace[k].period_ms+(k%4)*3u;}
    *channel_id=i+1;
    p2_bridge_connect(&g_vehicle_bridge,i+1,canonical_protocol(protocol),baud);
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
/* Shared transport validation for immediate and periodic J2534 TX.
   Both APIs eventually dispatch through process_request; periodic messages
   must not bypass protocol, classic CAN DLC, physical ID and addressing
   guards by entering through a different scheduling API. */
static U32 validate_tx_message(const CHANNEL *c,const PASSTHRU_MSG *m){
    if(m->ProtocolID!=(c->api_protocol?c->api_protocol:c->protocol))return ERR_MSG_PROTOCOL_ID;
    if(is_ps_protocol(c->api_protocol) && !c->ps_pins)return ERR_PIN_INVALID;
    if(m->DataSize>MAX_DATA||m->DataSize<5u||
       (c->protocol==PROTO_CAN && m->DataSize>12u))return ERR_INVALID_MSG;
    if((m->Data[0]&0xE0u)!=0u)return ERR_INVALID_MSG;
    if(g_strict_j2534_filters && c->protocol==PROTO_ISO15765 &&
       (m->TxFlags&ISO15765_ADDR_TYPE))return ERR_NOT_SUPPORTED;
    return ERR_OK;
}
EXPORT U32 WINCALL PassThruWriteMsgs(U32 id,const PASSTHRU_MSG *msgs,U32 *count,U32 timeout){
    U32 i,n;(void)timeout;if(!msgs||!count)return error(ERR_NULL_PARAMETER);
    lock_state();CHANNEL *c=channel(id);if(!c){unlock_state();return error(ERR_INVALID_CHANNEL_ID);}
    n=*count;if(n>64){unlock_state();return error(ERR_EXCEEDED_LIMIT);}
    for(i=0;i<n;i++){
        U32 validity=validate_tx_message(c,&msgs[i]);
        if(validity!=ERR_OK){
            *count=i;unlock_state();return error(validity);
        }
        {U8 meta[20];u32_be(meta,id);u32_be(meta+4,c->protocol);
         u32_be(meta+8,msgs[i].TxFlags);u32_be(meta+12,c->baud);
         u32_be(meta+16,(U32)now_us());
         logline("TX context channel/protocol/flags/baud/time-us (BE)",meta,20);}
        logline("TX (app request)",msgs[i].Data,msgs[i].DataSize);
        /* The observer cannot affect J2534 return codes or ECU responses. */
        {
            p2_bridge_tx_result observed;
            if (p2_bridge_inspect_tx_at(&g_vehicle_bridge,id,msgs[i].TxFlags,
                    msgs[i].Data,msgs[i].DataSize,now_us(),&observed)) {
                if(observed.label && observed.decision!=P2_CEM_KEEP_EXISTING)
                    logline(observed.label,0,0);
                if(observed.hw_event!=P2_HW_UNRELATED)
                    logline(p2_hw_tx_event_name(observed.hw_event),0,0);
            }
        }
        begin_tx_evidence(c,&msgs[i]);
        process_request(c,&msgs[i]);
        c->active_trace=0;
    }
    *count=n;unlock_state();return error(ERR_OK);
}
EXPORT U32 WINCALL PassThruReadMsgs(U32 id,PASSTHRU_MSG *msgs,U32 *count,U32 timeout){
    U32 want,actual=0,started;
    U64 original_session=0;
    if(!msgs||!count)return error(ERR_NULL_PARAMETER);
    /* NumMsgs is the caller buffer capacity; MAX_QUEUE is only our internal queue. */
    want=*count;if(want==0)return error(ERR_INVALID_MSG);
    started=GetTickCount();
    for(;;){
        CHANNEL *c;lock_state();c=channel(id);
        if(!c || (original_session && c->session_serial!=original_session)){
            unlock_state();*count=0;return error(ERR_INVALID_CHANNEL_ID);
        }
        if(!original_session)original_session=c->session_serial;
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
            /* Observe delivered RX only: E3 remains an unverified header,
               not ECU authentication or a generated positive reply. */
            {
                p2_hw_rx_event hw_rx=p2_bridge_inspect_hw_rx_at(
                    &g_vehicle_bridge,id,msgs[actual].RxStatus,
                    msgs[actual].Data,msgs[actual].DataSize,now_us());
                if(hw_rx!=P2_HW_RX_UNRELATED)
                    logline(p2_hw_rx_event_name(hw_rx),0,0);
            }
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
             c->queue_passive_baud[c->r]=0;
             c->queue_raw_response_baud[c->r]=0;
             c->queue_raw_exchange[c->r]=0;
             c->r=(c->r+1)%MAX_QUEUE;c->count--;actual++;
             /* Resume only previously granted CFs after this slot is freed. */
             pump_can_cf(c);
             backend_end_if_drained(c,rid);
            }
        }
        unlock_state();
        if(actual){
            /* Frames were delivered from original_session under the lock.
               A concurrent new connection must not inherit its counter. */
            lock_state();c=channel(id);
            if(c && c->session_serial==original_session)c->read_timeout_count=0;
            unlock_state();*count=actual;return error(ERR_OK);
        }
        if((U32)(GetTickCount()-started)>=timeout){
            U32 failures=0; U8 info[12];
            /* The channel can be disconnected and reused after our last
               polling lock, even at the exact timeout boundary. Check
               its identity before recording another timeout. */
            lock_state();c=channel(id);
            if(!c || c->session_serial!=original_session){
                unlock_state();*count=0;return error(ERR_INVALID_CHANNEL_ID);
            }
            if(timeout)failures=++c->read_timeout_count;
            unlock_state();
            if(timeout && (failures<=3||(failures%25u)==0)){
                u32_be(info,id);u32_be(info+4,timeout);u32_be(info+8,failures);
                logline("PassThruReadMsgs timeout: channel / wait-ms / consecutive-count (BE)",info,12);
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
    /* PS always preserves the client-visible protocol ID, including when the
       historical loose-filter policy is selected for legacy laboratory runs. */
    if(is_ps_protocol(c->api_protocol) &&
       (mask->ProtocolID!=c->api_protocol ||
        pattern->ProtocolID!=c->api_protocol ||
        (flow && flow->ProtocolID!=c->api_protocol))){
        unlock_state();return error(ERR_MSG_PROTOCOL_ID);
    }
    if(g_strict_j2534_filters){
        if(c->protocol==PROTO_CAN && type==3u){unlock_state();return error(ERR_NO_FLOW_CONTROL);}
        if(c->protocol==PROTO_ISO15765 && type!=3u){unlock_state();return error(ERR_INVALID_FLAGS);}
        if(mask->ProtocolID!=(c->api_protocol?c->api_protocol:c->protocol)||
           pattern->ProtocolID!=(c->api_protocol?c->api_protocol:c->protocol)){
            unlock_state();return error(ERR_MSG_PROTOCOL_ID);
        }
        if(type==3u && !flow){unlock_state();return error(ERR_NULL_PARAMETER);}
        if(type==3u && flow->ProtocolID!=(c->api_protocol?c->api_protocol:c->protocol)){unlock_state();return error(ERR_MSG_PROTOCOL_ID);}
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
    /* A filter pattern and optional FC source are actual physical CAN IDs.
       Reject IDs outside the 29-bit wire range *before* consuming a filter
       slot or emitting filter evidence. Deliberately do NOT restrict the
       32-bit mask: 0xFFFFFFFF is a legitimate J2534 match mask. */
    if((pattern->Data[0]&0xE0u)!=0u ||
       (type==3u && flow && flow->DataSize>=4u &&
        (flow->Data[0]&0xE0u)!=0u)){
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
    /* B3A69: accepted filter lifecycle evidence, source-only. A channel ID
       is necessary to distinguish simultaneous CAN_PS/ISO15765 filters in
       one VIDA host process. Only metadata; no VIN or filter payload here.
       Keep the original type/id, mask and pattern log markers unchanged. */
    {U8 lifecycle[20];
     u32_be(lifecycle,id);u32_be(lifecycle+4,type);
     u32_be(lifecycle+8,*filter_id);
     u32_be(lifecycle+12,c->api_protocol?c->api_protocol:c->protocol);
     u32_be(lifecycle+16,c->baud);
     logline("J2534 filter accepted channel/type/id/protocol/baud (BE)",lifecycle,20);}
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
        /* Only a successful Stop changes active filter lifetime. */
        {U8 released[8];u32_be(released,id);u32_be(released+4,filter_id);
         logline("J2534 filter stopped channel/id (BE)",released,8);}
        unlock_state();return error(ERR_OK);
    }
    unlock_state();return error(ERR_INVALID_FILTER_ID);
}
EXPORT U32 WINCALL PassThruStartPeriodicMsg(U32 id,const PASSTHRU_MSG *msg,U32 *period_id,U32 interval){
    U32 i;if(!msg||!period_id)return error(ERR_NULL_PARAMETER);
    if(interval<5 || interval>60000)return error(ERR_INVALID_TIME_INTERVAL);
    if(msg->DataSize<5 || msg->DataSize>MAX_DATA)return error(ERR_INVALID_MSG);
    lock_state();CHANNEL *c=channel(id);if(!c){unlock_state();return error(ERR_INVALID_CHANNEL_ID);}
    /* Validate before reserving a slot or incrementing the periodic ID. */
    {U32 validity=validate_tx_message(c,msg);
     if(validity!=ERR_OK){unlock_state();return error(validity);}}
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
        lock_state();ecm_lab_refresh();
        *(U32*)output=g_battery_mv;u32_be(value,g_battery_mv);
        logline("PassThruIoctl READ_VBATT (mV, BE)",value,4);
        unlock_state();return error(ERR_OK);
    }
    if(ioctl==IO_READ_PROG_VOLTAGE){if(!output)return error(ERR_NULL_PARAMETER);*(U32*)output=0;return error(ERR_OK);}
    lock_state();CHANNEL *c=channel(id);if(!c){unlock_state();return error(ERR_INVALID_CHANNEL_ID);}
    if(ioctl==IO_CLEAR_RX_BUFFER){
        /* Clear queued RX AND any staged raw-CAN ISO-TP continuation.
           Without this, a later CTS or an already granted block can emit
           orphan CFs after the FF was discarded. Cancel evidence first. */
        backend_cancel_channel(c,"clear_rx_buffer",0);
        c->r=c->w=c->count=0;c->d2_count=0;c->d2_pos=0;c->d2_trace=0;
        c->pending_len=0;c->pending_pos=0;c->pending_id=0;
        c->pending_request_id=0;c->pending_sn=0;c->pending_trace=0;
        c->pending_next_us=0;c->pending_stmin_us=0;
        c->pending_cf_active=0;c->pending_cf_credit=0;
        c->pending_raw_exchange=0;
        bytes_zero(c->queue_d2_gen,sizeof(c->queue_d2_gen));
        bytes_zero(c->queue_d2_frame,sizeof(c->queue_d2_frame));
        bytes_zero(c->queue_ready_us,sizeof(c->queue_ready_us));
        bytes_zero(c->queue_passive_baud,sizeof(c->queue_passive_baud));
        bytes_zero(c->queue_raw_response_baud,sizeof(c->queue_raw_response_baud));
        bytes_zero(c->queue_raw_exchange,sizeof(c->queue_raw_exchange));
        bytes_zero(c->queue_trace,sizeof(c->queue_trace));
        {U8 meta[20];u32_be(meta,id);u32_be(meta+4,c->protocol);
         u32_be(meta+8,c->flags);u32_be(meta+12,c->baud);
         u32_be(meta+16,(U32)now_us());
         logline("CLEAR_RX context channel/protocol/flags/baud/time-us (BE)",meta,20);}
        logline("J2534 CLEAR_RX_BUFFER: queued D2/raw ISO-TP and staged CF dropped",0,0);
        unlock_state();return error(ERR_OK);}
    if(ioctl==IO_CLEAR_MSG_FILTERS){c->filters_count=0;unlock_state();return error(ERR_OK);}
    if(ioctl==IO_CLEAR_PERIODIC_MSGS){bytes_zero(c->periodic,sizeof(c->periodic));unlock_state();return error(ERR_OK);}
    if(ioctl==IO_CLEAR_TX_BUFFER){unlock_state();return error(ERR_OK);}
    if(ioctl==IO_SET_CONFIG||ioctl==IO_GET_CONFIG){
        SCONFIG_LIST *list=(SCONFIG_LIST*)input;
        U32 initial_baud=c->baud,desired_baud=c->baud,desired_pins=c->ps_pins;
        int ps=is_ps_protocol(c->api_protocol);
        if(!list||(!list->ConfigPtr&&list->NumOfParams)){unlock_state();return error(ERR_NULL_PARAMETER);}
        if(list->NumOfParams>64){unlock_state();return error(ERR_INVALID_IOCTL_VALUE);}
        /* Preflight the COMPLETE batch before changing any channel state.
           A partial DATA_RATE/PINS update could otherwise expose an invalid bus. */
        if(ioctl==IO_SET_CONFIG){
            for(i=0;i<list->NumOfParams;i++){
                SCONFIG *cfg=&list->ConfigPtr[i];
                if(cfg->Parameter==1u){
                    if(cfg->Value==0u){unlock_state();return error(ERR_INVALID_BAUDRATE);}
                    desired_baud=cfg->Value;
                }else if(ps && cfg->Parameter==CONFIG_J1962_PINS){
                    if(cfg->Value!=PINS_CAN_HS && cfg->Value!=PINS_CAN_MS){
                        unlock_state();return error(ERR_PIN_INVALID);
                    }
                    desired_pins=cfg->Value;
                }
            }
            if(ps && desired_pins){
                if((desired_pins==PINS_CAN_HS && desired_baud!=500000u) ||
                   (desired_pins==PINS_CAN_MS && desired_baud!=125000u)){
                    unlock_state();return error(ERR_INVALID_BAUDRATE);
                }
                /* A pin change requires a fresh virtual channel. This prevents
                   cross-bus queued RX/FC and avoids silent CAN-MS/HS re-routing. */
                if(c->ps_pins && desired_pins!=c->ps_pins){
                    unlock_state();return error(ERR_CHANNEL_IN_USE);
                }
            }
            if(ps && desired_baud!=500000u && desired_baud!=125000u){
                unlock_state();return error(ERR_INVALID_BAUDRATE);
            }
        }
        for(i=0;i<list->NumOfParams;i++){
            SCONFIG *cfg=&list->ConfigPtr[i];
            if(ioctl==IO_SET_CONFIG){
                if(cfg->Parameter==1u)c->baud=cfg->Value;
                if(ps && cfg->Parameter==CONFIG_J1962_PINS)c->ps_pins=cfg->Value;
                log_set_config(id,cfg->Parameter,cfg->Value);
            }else if(ioctl==IO_GET_CONFIG){
                if(cfg->Parameter==1u)cfg->Value=c->baud;
                else if(ps && cfg->Parameter==CONFIG_J1962_PINS)cfg->Value=c->ps_pins;
                else cfg->Value=0u;
            }
        }
        if(ioctl==IO_SET_CONFIG && c->baud!=initial_baud){
            supersede_d2_exchange(c);
            {U32 removed=drop_old_bus_passive_rx(c);
             if(removed){U8 count_be[4];u32_be(count_be,removed);
              logline("J2534 DATA_RATE stale passive RX dropped (BE)",count_be,4);}
            }
            {U32 removed=cancel_old_bus_raw_iso_rx(c);
             if(removed){U8 count_be[4];u32_be(count_be,removed);
              logline("J2534 DATA_RATE stale raw ISO-TP RX dropped (BE)",count_be,4);}
            }
            logline("J2534 DATA_RATE changed; old-bus D2 replay disallowed",0,0);
            p2_bridge_connect(&g_vehicle_bridge,id,c->protocol,c->baud);
        }
        unlock_state();return error(ERR_OK);
    }
    unlock_state();return error(ERR_INVALID_IOCTL_ID);
}
/* DLL_PROCESS_ATTACH, no work under loader lock. */
int WINCALL DllMain(PTR module,U32 reason,PTR reserved) {(void)reserved;if(reason==1)g_module=module;return 1;}


