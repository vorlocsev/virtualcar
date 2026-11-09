/* Host-side protocol test, with deterministic Win32 API shims. */
#define HOST_TEST 1
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/*
 * Keep the simulator's Win32 shims in a private namespace. On a Windows
 * host the default link also brings in Kernel32 import symbols for several
 * names (notably GetCurrentProcessId, QueryPerformanceCounter, WriteFile and
 * CloseHandle). Defining test shims with those public names makes LLD report
 * duplicate symbols. Renaming only this translation unit's calls and
 * shim definitions preserves the Linux-host behavior while allowing the
 * same deterministic regression executable to run on Windows.
 */
#define Sleep vc_test_Sleep
#define GetTickCount vc_test_GetTickCount
#define QueryPerformanceCounter vc_test_QueryPerformanceCounter
#define QueryPerformanceFrequency vc_test_QueryPerformanceFrequency
#define GetCurrentProcessId vc_test_GetCurrentProcessId
#define GetModuleFileNameA vc_test_GetModuleFileNameA
#define GetPrivateProfileStringA vc_test_GetPrivateProfileStringA
#define GetTempPathA vc_test_GetTempPathA
#define GetEnvironmentVariableA vc_test_GetEnvironmentVariableA
#define CreateDirectoryA vc_test_CreateDirectoryA
#define CreateFileA vc_test_CreateFileA
#define SetFilePointer vc_test_SetFilePointer
#define WriteFile vc_test_WriteFile
#define CloseHandle vc_test_CloseHandle
#define InterlockedCompareExchange vc_test_InterlockedCompareExchange
#define InterlockedExchange vc_test_InterlockedExchange

#include "../src/virtualcar.c"
static U32 tick=0;static I64 qpc_offset_us=0;
static char backend_lines[800000];static U32 backend_len=0;
static int capture_connect_log=0;
static char connect_log_lines[32000];static U32 connect_log_len=0;
static U32 event_count_since(const char *start,const char *pattern){
 U32 count=0;const char *p=start;
 while((p=strstr(p,pattern))!=0){++count;p+=strlen(pattern);}
 return count;
}
static U32 event_count(const char *pattern){return event_count_since(backend_lines,pattern);}
static int field_within_line(const char *line,const char *end,const char *field){
 const char *p=strstr(line,field);return p && p<end;
}
static U32 terminal_for(const char *start,U64 rid,const char *cause,const char *outcome){
 char request[80],reason[96],result[96];U32 count=0;
 const char *line=start;
 snprintf(request,sizeof(request),"\"request_id\":%llu,",(unsigned long long)rid);
 snprintf(reason,sizeof(reason),"\"reason\":\"%s\"",cause);
 snprintf(result,sizeof(result),"\"outcome\":\"%s\"",outcome);
 while(*line){
  const char *end=strchr(line,'\n');
  if(!end)break;
  if(field_within_line(line,end,"\"kind\":\"request_completed\"") &&
     field_within_line(line,end,request) &&
     field_within_line(line,end,reason) &&
     field_within_line(line,end,result))++count;
  line=end+1;
 }
 return count;
}
static U32 terminal_count_for(const char *start,U64 rid){
 char request[80];U32 count=0;const char *line=start;
 snprintf(request,sizeof(request),"\"request_id\":%llu,",(unsigned long long)rid);
 while(*line){const char *end=strchr(line,'\n');if(!end)break;
  if(field_within_line(line,end,"\"kind\":\"request_completed\"")&&field_within_line(line,end,request))count++;
  line=end+1;
 }
 return count;
}
static U64 last_tx_request(const char *start){
 const char *line=start,*found=0;
 while(*line){const char *end=strchr(line,'\n');if(!end)break;
  if(field_within_line(line,end,"\"kind\":\"tx_received\""))found=line;
  line=end+1;
 }
 if(found){const char *p=strstr(found,"\"request_id\":");if(p){U64 value=0;p+=13;while(*p>='0'&&*p<='9'){value=value*10u+(U64)(*p-'0');p++;}return value;}}
 return 0;
}

void Sleep(U32 ms){tick+=ms;}
U32 GetTickCount(void){return tick;}
int QueryPerformanceFrequency(I64 *v){*v=1000000;return 1;}
int QueryPerformanceCounter(I64 *v){*v=(I64)tick*1000+qpc_offset_us;return 1;}
static void advance_test_us(U32 us){tick+=us/1000u;qpc_offset_us+=(I64)(us%1000u);if(qpc_offset_us>=1000){tick+=(U32)(qpc_offset_us/1000);qpc_offset_us%=1000;}}
U32 GetCurrentProcessId(void){return 0xAABBCCDD;}
U32 GetModuleFileNameA(PTR mod,char*out,U32 n){(void)mod;strncpy(out,"C:\\SectorV\\VirtualCarJ2534.dll",n);return (U32)strlen(out);}
U32 GetPrivateProfileStringA(const char*s,const char*k,const char*d,char*out,U32 n,const char*path){
 (void)path;
 /* Only host-test fixture: the distributed INI keeps count=0 by default. */
 if(strcmp(s,"Diagnostics")==0 && strcmp(k,"BackendTelemetryEnabled")==0)d="1";
 if(strcmp(s,"D2_40")==0 && strcmp(k,"B9FBFrameCount")==0)d="1";
 if(strcmp(s,"D2_40")==0 && strcmp(k,"B9FBFrame0")==0)d="CC 40 7F B9 31 00 00 00";
 if(strcmp(s,"D2_50_B9F0")==0 && strcmp(k,"FrameCount")==0)d="3";
 if(strcmp(s,"D2_50_B9F0")==0 && strcmp(k,"Frame0")==0)d="8F 50 F9 F0 00 08 68 85";
 if(strcmp(s,"D2_50_B9F0")==0 && strcmp(k,"Frame1")==0)d="09 13 20 20 41 30 65 70";
 if(strcmp(s,"D2_50_B9F0")==0 && strcmp(k,"Frame2")==0)d="4C 24 20 20 41 00 00 00";
 if(strcmp(s,"ECU1")==0 && strcmp(k,"DIDF1B0Hex")==0)d="53 49 4D 2D 43 45 4D";
 if(strcmp(s,"ECU1")==0 && strcmp(k,"DIDF1A3Hex")==0)d="53 49 4D 2D 31 2E 30";
 if(strcmp(s,"ECU1")==0 && strcmp(k,"DID0Code")==0)d="F18C";
 if(strcmp(s,"ECU1")==0 && strcmp(k,"DID0Hex")==0)d="4C 41 42 2D 49 44";
 if(strcmp(s,"ECU1")==0 && strcmp(k,"DID1Code")==0)d="F106";
 if(strcmp(s,"ECU1")==0 && strcmp(k,"DID1Hex")==0){
    for(U32 z=0;z<142;z++){
      snprintf(out+z*3,n-z*3,"%02X%s",(unsigned)z,z+1<142?" ":"");
    }
    return (U32)strlen(out);
 }
 snprintf(out,n,"%s",d);return (U32)strlen(out);
}
U32 GetTempPathA(U32 n,char*out){snprintf(out,n,"/tmp/");return 5;}
U32 GetEnvironmentVariableA(const char *name,char*out,U32 n){
 if(strcmp(name,"LOCALAPPDATA")!=0)return 0;
 snprintf(out,n,"/tmp");return 4;
}
int CreateDirectoryA(const char *p,PTR sec){(void)p;(void)sec;return 1;}
HANDLE CreateFileA(const char *p,U32 a,U32 sh,PTR sec,U32 creation,U32 flags,HANDLE template){
 (void)a;(void)sh;(void)sec;(void)creation;(void)flags;(void)template;
 if(strstr(p,"dev47-backend.jsonl"))return (HANDLE)1;
 if(capture_connect_log && strstr(p,"SectorVVirtualCar.log"))return (HANDLE)2;
 return INVALID_HANDLE;
}
U32 SetFilePointer(HANDLE file,U32 low,PTR high,U32 method){(void)file;(void)low;(void)high;(void)method;return 0;}
int WriteFile(HANDLE f,const void*b,U32 n,U32*w,PTR o){
 (void)o;
 if(f==(HANDLE)2){
  if(n+connect_log_len>=sizeof(connect_log_lines))return 0;
  memcpy(connect_log_lines+connect_log_len,b,n);connect_log_len+=n;
  connect_log_lines[connect_log_len]=0;
 }else if(f==(HANDLE)1){
  if(n+backend_len>=sizeof(backend_lines))return 0;
  memcpy(backend_lines+backend_len,b,n);backend_len+=n;
  backend_lines[backend_len]=0;
 }else return 0;
 if(w)*w=n;
 return 1;
}
int CloseHandle(HANDLE file){(void)file;return 1;}
/* Deterministic lifecycle contention at the precise lock-entry boundary.
   The host test never uses actual threads or simulates physical hardware. */
static U32 lifecycle_race_on_next_lock=0;
long InterlockedCompareExchange(volatile long*dst,long exchange,long compare){
 if(dst==&g_lock && compare==0 && lifecycle_race_on_next_lock){
  U32 transition=lifecycle_race_on_next_lock;
  lifecycle_race_on_next_lock=0;
  if(transition==1u){
   /* Another thread completed Close just before this lock was obtained. */
   g_open=0;bytes_zero(g_ch,sizeof(g_ch));
  }else if(transition==2u){
   /* Another thread completed its first Open and allocated channel 1. */
   g_open=1;bytes_zero(g_ch,sizeof(g_ch));
   g_ch[0].used=1;g_ch[0].id=1;
   g_ch[0].protocol=PROTO_CAN;g_ch[0].baud=500000u;
  }
 }
 {long v=*dst;if(v==compare)*dst=exchange;return v;}
}
long InterlockedExchange(volatile long*dst,long val){long v=*dst;*dst=val;return v;}
#define REQUIRE(expr) do{if(!(expr)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#expr);exit(1);}}while(0)
static void fill_untraced_rx(CHANNEL *ch,U32 target){
 static const U8 fake_frame[8]={0x56,0x43,0x41,0x52,0x4C,0x41,0x42,0};
 U64 prior=ch->active_trace;
 ch->active_trace=0;
 while(ch->count<target){
  REQUIRE(ch->count<MAX_QUEUE);
  enqueue(ch,0x555,fake_frame,8);
 }
 ch->active_trace=prior;
}
static PASSTHRU_MSG frame(U32 proto,U32 id,const U8 *data,U32 len){PASSTHRU_MSG m={0};m.ProtocolID=proto;m.DataSize=len+4;m.Data[0]=(U8)(id>>24);m.Data[1]=(U8)(id>>16);m.Data[2]=(U8)(id>>8);m.Data[3]=(U8)id;if(len)memcpy(m.Data+4,data,len);return m;}
static PASSTHRU_MSG readmsg(U32 cid){PASSTHRU_MSG m={0};U32 n=1;REQUIRE(PassThruReadMsgs(cid,&m,&n,0)==ERR_OK);REQUIRE(n==1);return m;}
static void send(U32 cid,PASSTHRU_MSG *m){U32 n=1;REQUIRE(PassThruWriteMsgs(cid,m,&n,10)==ERR_OK);REQUIRE(n==1);}
/* Synthetic VMware audit regressions: compare actual emitted events, not
   guesses about the unidentified requests in a redacted user report. */
static void require_route(const char *start,const char *route,U32 selected){
 char field[64];const char *line=start;
 snprintf(field,sizeof(field),"\"route\":\"%s\"",route);
 REQUIRE(event_count_since(start,"\"kind\":\"route_selected\"")==selected);
 REQUIRE(event_count_since(start,"\"kind\":\"request_completed\"")==1);
 while(*line){const char *end=strchr(line,'\n');if(!end)break;
  if(!field_within_line(line,end,"\"route\":\"UNKNOWN\"") &&
     !field_within_line(line,end,field)){
   const char *actual=strstr(line,"\"route\":\"");
   if(actual && actual<end)actual+=9;
   fprintf(stderr,"route mismatch expected %s, actual %.*s\\n",route,
           actual?(int)(end-actual):0,actual?actual:"");
   exit(1);
  }
  line=end+1;
 }
}
static void test_vmware_route_evidence(U32 dev){
 ECU saved_ecu[MAX_ECUS];D2_PROFILE saved_d2[MAX_D2_FIXTURES];
 U32 saved_count=g_ecu_count,saved_strict=g_p2_strict_routing;
 U32 hs=0,ls=0,iso=0,k,j;PASSTHRU_MSG m,rx;const char *start;
 const U8 suppressed[]={0x3E,0x80},sf_suppressed[]={2,0x3E,0x80};
 const U8 d2[]={0xCB,0x60,0xB9,0xFB,0,0,0,0};
 const char *fixture_start=backend_lines+backend_len;
 memcpy(saved_ecu,g_ecu,sizeof(saved_ecu));memcpy(saved_d2,g_d2,sizeof(saved_d2));
 g_ecu_count=3;g_ecu[2]=g_ecu[0];g_ecu[2].req=0x740;g_ecu[2].resp=0x748;
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0x800,500000,&hs)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0x800,125000,&ls)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,500000,&iso)==ERR_OK);
 /* 1: physical suppressed TesterPresent, ECM/CEM/other, both protocols
    and simultaneous HS/LS channels: one consistent terminal and no RX. */
 for(k=0;k<3;k++)for(j=0;j<3;j++){
  U32 cid=j==0?hs:(j==1?ls:iso);U32 count=1;
  m=frame(j==2?PROTO_ISO15765:PROTO_CAN,g_ecu[k].req,
          j==2?suppressed:sf_suppressed,j==2?2:3);
  start=backend_lines+backend_len;send(cid,&m);
  require_route(start,k==0?"ECM":(k==1?"CEM":"ECU_OTHER"),1);
  REQUIRE(terminal_for(start,last_tx_request(start),"no_response","no_response")==1);
  REQUIRE(PassThruReadMsgs(cid,&rx,&count,0)==ERR_BUFFER_EMPTY&&count==0);
 }
 /* 2: optional non-CEM D2 target with no configured fixture. */
 m=frame(PROTO_CAN,0x000FFFFE,d2,8);start=backend_lines+backend_len;send(hs,&m);
 require_route(start,"ECU_OTHER",1);
 REQUIRE(terminal_for(start,last_tx_request(start),"missing_profile","no_response")==1);
 /* 3: optional non-CEM fixture exists on a different bus. */
 bytes_zero(&g_d2[6],sizeof(g_d2[6]));g_d2[6].target=0x60;g_d2[6].subcommand=0xFB;
 g_d2[6].baud=500000;start=backend_lines+backend_len;send(ls,&m);
 require_route(start,"ECU_OTHER",1);
 REQUIRE(terminal_for(start,last_tx_request(start),"unsupported_bus","no_response")==1);
 /* 4: exact synthetic non-CEM fixture, including terminal after dequeue. */
 g_d2[6].frame_count=1;g_d2[6].response_id=0x01000003;
 {const U8 marker[8]={0xCC,0x60,0x7F,0xB9,0x31,0,0,0};
  memcpy(g_d2[6].frame[0],marker,8);start=backend_lines+backend_len;send(hs,&m);
  rx=readmsg(hs);REQUIRE(rx.DataSize==12&&memcmp(rx.Data+4,marker,8)==0);}
 require_route(start,"ECU_OTHER",1);
 REQUIRE(terminal_for(start,last_tx_request(start),"none","responded")==1);
 /* 5: functional suppression/protected services keep one aggregate route. */
 for(k=0;k<2;k++){
  const U8 protected_req[2]={0x11,0x81};U32 count=1;
  m=frame(PROTO_ISO15765,0x7DF,k?protected_req:suppressed,2);
  start=backend_lines+backend_len;send(iso,&m);require_route(start,"ECU_OTHER",1);
  REQUIRE(PassThruReadMsgs(iso,&rx,&count,0)==ERR_BUFFER_EMPTY&&count==0);
 }
 /* 6: functional short replies still fan out without conflicting routes. */
 {const U8 tester[2]={0x3E,0};
  m=frame(PROTO_ISO15765,0x7DF,tester,2);start=backend_lines+backend_len;send(iso,&m);
  for(k=0;k<g_ecu_count;k++){rx=readmsg(iso);REQUIRE(rx.Data[4]==0x7E&&rx.Data[5]==0);}
  require_route(start,"ECU_OTHER",1);}
 /* 7: VMware no_fixture/unsupported outcomes stay silent, with no new CEM. */
 g_ecu_count=1;g_p2_strict_routing=1;g_d2[0].frame_count=0;g_d2[2].frame_count=0;
 for(k=0;k<3;k++){
  U8 probe[8]={0xCB,k==0?0x40:0x50,0xB9,0xFB,0,0,0,0};
  U32 cid=k==0?ls:hs,count=1;
  if(k==2){const U8 p3[3]={0x22,0xF1,0x14};m=frame(PROTO_ISO15765,0x726,p3,3);cid=iso;}
  else m=frame(PROTO_CAN,0x000FFFFE,probe,8);
  start=backend_lines+backend_len;send(cid,&m);require_route(start,"CEM",1);
  REQUIRE(terminal_for(start,last_tx_request(start),k==2?"unimplemented_probe":"missing_profile","no_response")==1);
  REQUIRE(PassThruReadMsgs(cid,&rx,&count,0)==ERR_BUFFER_EMPTY&&count==0);
 }
 /* 8: opt-out changes neither suppression nor transport behavior. */
 {U32 before=backend_len,count=1;g_backend_enabled=0;
  m=frame(PROTO_CAN,0x7E0,sf_suppressed,3);send(hs,&m);
  REQUIRE(PassThruReadMsgs(hs,&rx,&count,0)==ERR_BUFFER_EMPTY&&count==0);
  REQUIRE(backend_len==before);g_backend_enabled=1;}
 {const char *path=getenv("VIRTUALCAR_ROUTE_EVIDENCE");
  if(path){FILE *f=fopen(path,"wb");REQUIRE(f!=0);
   REQUIRE(fwrite(fixture_start,1,strlen(fixture_start),f)==strlen(fixture_start));REQUIRE(fclose(f)==0);}}
 REQUIRE(PassThruDisconnect(hs)==ERR_OK);REQUIRE(PassThruDisconnect(ls)==ERR_OK);
 REQUIRE(PassThruDisconnect(iso)==ERR_OK);
 memcpy(g_ecu,saved_ecu,sizeof(saved_ecu));memcpy(g_d2,saved_d2,sizeof(saved_d2));
 g_ecu_count=saved_count;g_p2_strict_routing=saved_strict;
 puts("PASS: eight VMware route evidence groups (synthetic, no new ECU replies)");
}
/* Synthetic RX occupancy for testing ISO-TP backpressure without real CAN. */
static void fill_lab_rx(CHANNEL *c,U32 amount){
 static const U8 marker[8]={0x46,0x49,0x4C,0x4C,0x54,0x45,0x53,0x54};
 for(U32 i=0;i<amount;i++){
   REQUIRE(c->count<MAX_QUEUE);
   enqueue(c,0x555u,marker,8);
 }
}

/* Eight observer-only groups derived from published 2.5T source shapes.
   No private vehicle identification, no invented CEM positive response. */
static void test_p2_informer_observer(U32 dev){
 U32 ls=0,hs=0,wrong=0,iso=0,n,old_enabled=g_backend_enabled;
 const char *tag,*start;U64 rid;PASSTHRU_MSG m,rx;
 const U8 vin[]={0x03,0x22,0xF1,0x90,0,0,0,0};
 const U8 ecm[]={0xCD,0x7A,0xA6,0x10,0xB8,0x01,0,0};
 const U8 tcm[]={0xCC,0x6E,0xA5,0x0C,0x01,0,0,0};
 const U8 dem[]={0xCD,0x1A,0xA6,0x00,0x05,0x01,0,0};
 const U8 rem[]={0xCD,0x46,0xA6,0xD0,0xD4,0x01,0,0};
 const U8 ccm[]={0xCD,0x29,0xA6,0x00,0x01,0x01,0,0};
 const U8 d2[]={0xCB,0x50,0xB9,0xFB,0,0,0,0};
 const U8 p3[]={0x03,0x22,0xF1,0x14,0,0,0,0};
 U8 bad[8];U32 j;
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,125000,&ls)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&hs)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,250000,&wrong)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,125000,&iso)==ERR_OK);
 g_backend_enabled=1;
 /* 1: Source VIN TX is LS-only 29-bit CAN, never a CEM B9FB fixture. */
 m=frame(PROTO_CAN,0x000FFFFE,vin,8);
 tag=backend_probe_name(channel(ls),&m);
 REQUIRE(tag && strcmp(tag,"P2INF_LS_VIN_F190")==0);
 REQUIRE(backend_probe_name(channel(hs),&m)==NULL);
 /* 2: source HS ECM / TCM / DEM selectors remain separate. */
 {
  const U8 *requests[]={ecm,tcm,dem};
  const char *tags[]={"P2INF_HS_ECM_A6","P2INF_HS_TCM_A5","P2INF_HS_DEM_A6"};
  for(j=0;j<3;j++){
   m=frame(PROTO_CAN,0x000FFFFE,requests[j],8);
   tag=backend_probe_name(channel(hs),&m);
   REQUIRE(tag && strcmp(tag,tags[j])==0);
  }
 }
 /* 3: source LS REM / CCM selectors cannot masquerade as CEM probes. */
 m=frame(PROTO_CAN,0x000FFFFE,rem,8);
 REQUIRE(strcmp(backend_probe_name(channel(ls),&m),"P2INF_LS_REM_A6")==0);
 m=frame(PROTO_CAN,0x000FFFFE,ccm,8);
 REQUIRE(strcmp(backend_probe_name(channel(ls),&m),"P2INF_LS_CCM_A6")==0);
 /* 4: wrong baud or ISO15765 transport cannot gain source provenance. */
 m=frame(PROTO_CAN,0x000FFFFE,vin,8);
 REQUIRE(backend_probe_name(channel(wrong),&m)==NULL);
 m=frame(PROTO_ISO15765,0x000FFFFE,vin,8);
 REQUIRE(backend_probe_name(channel(iso),&m)==NULL);
 m=frame(PROTO_CAN,0x000FFFFE,ecm,8);
 REQUIRE(backend_probe_name(channel(ls),&m)==NULL);
 /* 5: 11-bit/unrelated request IDs cannot be attributed to 29-bit source. */
 m=frame(PROTO_CAN,0x726,vin,8);
 /* Existing P3 11-bit F190 classifier remains authoritative, not P2 Informer. */
 REQUIRE(strcmp(backend_probe_name(channel(ls),&m),"P3_726_F190")==0);
 m=frame(PROTO_CAN,0x7E0,vin,8);
 REQUIRE(backend_probe_name(channel(ls),&m)==NULL);
 /* 6: truncated, non-listed selectors, nonzero padding are unclassified. */
 m=frame(PROTO_CAN,0x000FFFFE,ecm,7);
 REQUIRE(backend_probe_name(channel(hs),&m)==NULL);
 memcpy(bad,ecm,8);bad[4]=0xFF;
 m=frame(PROTO_CAN,0x000FFFFE,bad,8);
 REQUIRE(backend_probe_name(channel(hs),&m)==NULL);
 memcpy(bad,vin,8);bad[7]=0x99;
 m=frame(PROTO_CAN,0x000FFFFE,bad,8);
 REQUIRE(backend_probe_name(channel(ls),&m)==NULL);
 memcpy(bad,tcm,8);bad[6]=0x01;
 m=frame(PROTO_CAN,0x000FFFFE,bad,8);
 REQUIRE(backend_probe_name(channel(hs),&m)==NULL);
 /* 7: existing D2 and P3 labels are unchanged by source-only catalogue. */
 m=frame(PROTO_CAN,0x000FFFFE,d2,8);
 REQUIRE(strcmp(backend_probe_name(channel(hs),&m),"D2_50_B9FB")==0);
 m=frame(PROTO_CAN,0x726,p3,8);
 REQUIRE(strcmp(backend_probe_name(channel(hs),&m),"P3_726_F114")==0);
 /* 8: J2534 TX yields only one allowlisted token and a silent terminal.
    There is no generated ECU response, no exposed payload and no RX. */
 {
  const U8 *payloads[]={vin,ecm,tcm,dem,rem,ccm};
  const char *tags[]={"P2INF_LS_VIN_F190","P2INF_HS_ECM_A6","P2INF_HS_TCM_A5",
                     "P2INF_HS_DEM_A6","P2INF_LS_REM_A6","P2INF_LS_CCM_A6"};
  for(j=0;j<6;j++){
   U32 cid=(j==0||j>=4)?ls:hs;
   m=frame(PROTO_CAN,0x000FFFFE,payloads[j],8);
   start=backend_lines+backend_len;send(cid,&m);rid=last_tx_request(start);
   REQUIRE(rid!=0);
   REQUIRE(event_count_since(start,"\"kind\":\"probe_classified\"")==1);
   REQUIRE(strstr(start,tags[j])!=NULL);
   REQUIRE(terminal_for(start,rid,"unhandled_request","no_response")==1);
   REQUIRE(event_count_since(start,"\"kind\":\"response_generated\"")==0);
   REQUIRE(strstr(start,"\"raw_payload\"")==NULL);
   n=1;REQUIRE(PassThruReadMsgs(cid,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0);
  }
  /* Optional telemetry must not alter emulator responses or produce events. */
  g_backend_enabled=0;
  start=backend_lines+backend_len;
  m=frame(PROTO_CAN,0x000FFFFE,vin,8);send(ls,&m);
  REQUIRE(backend_lines+backend_len==start);
  n=1;REQUIRE(PassThruReadMsgs(ls,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0);
 }
 g_backend_enabled=old_enabled;
 REQUIRE(PassThruDisconnect(iso)==ERR_OK);
 REQUIRE(PassThruDisconnect(wrong)==ERR_OK);
 REQUIRE(PassThruDisconnect(hs)==ERR_OK);
 REQUIRE(PassThruDisconnect(ls)==ERR_OK);
}


/* Eight read-only J2534 compatibility/preflight groups derived from the
   uploaded P3Tool IL report. These are API checks, not P2 ECU evidence. */
static void test_p3tool_j2534_preflight(U32 dev){
 U32 hs=0,raw=0,ls=0,lsraw=0,failed=0xC0DEFACEu,batt=0;
 PASSTHRU_MSG rx;U32 n;
 SCONFIG option;SCONFIG_LIST values={1,&option};
 const char *before;
 capture_connect_log=1;connect_log_len=0;connect_log_lines[0]=0;
 /* 1: standard HS ISO15765 and CAN connect; metadata includes exact results. */
 REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,500000,&hs)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&raw)==ERR_OK);
 REQUIRE(hs && raw && hs!=raw);
 REQUIRE(strstr(connect_log_lines,"J2534 Connect result protocol/flags/baud/status (BE) 00 00 00 06 00 00 00 00 00 07 A1 20 00 00 00 00")!=NULL);
 REQUIRE(strstr(connect_log_lines,"J2534 Connect result protocol/flags/baud/status (BE) 00 00 00 05 00 00 00 00 00 07 A1 20 00 00 00 00")!=NULL);
 /* 2: 125k ISO15765 with observed VOLVO_CH2 flag and raw CAN remain
    independent channels; flags are recorded, not translated into a bus. */
 REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0x20000000u,125000,&ls)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,125000,&lsraw)==ERR_OK);
 REQUIRE(ls!=lsraw && lsraw!=raw && lsraw!=hs && channel(ls)->flags==0x20000000u);
 REQUIRE(channel(ls)->baud==125000 && channel(hs)->baud==500000);
 REQUIRE(strstr(connect_log_lines,"00 00 00 06 20 00 00 00 00 01 E8 48 00 00 00 00")!=NULL);
 /* 3: 0x8004 and 0x8005 are vendor-specific, not automatic aliases. */
 before=connect_log_lines+connect_log_len;
 REQUIRE(PassThruConnect(dev,0x8004u,0,125000,&failed)==ERR_INVALID_PROTOCOL_ID);
 REQUIRE(PassThruConnect(dev,0x8005u,0,125000,&failed)==ERR_INVALID_PROTOCOL_ID);
 REQUIRE(failed==0xC0DEFACEu);
 REQUIRE(strstr(before,"00 00 80 04 00 00 00 00 00 01 E8 48 00 00 00 03")!=NULL);
 REQUIRE(strstr(before,"00 00 80 05 00 00 00 00 00 01 E8 48 00 00 00 03")!=NULL);
 /* 4: 0x10000001 is not rebranded as raw CAN even with published flags. */
 before=connect_log_lines+connect_log_len;
 REQUIRE(PassThruConnect(dev,0x10000001u,0x600u,500000,&failed)==ERR_INVALID_PROTOCOL_ID);
 REQUIRE(PassThruConnect(dev,0x10000001u,0x20000600u,125000,&failed)==ERR_INVALID_PROTOCOL_ID);
 REQUIRE(strstr(before,"10 00 00 01 00 00 06 00 00 07 A1 20 00 00 00 03")!=NULL);
 REQUIRE(strstr(before,"10 00 00 01 20 00 06 00 00 01 E8 48 00 00 00 03")!=NULL);
 /* 5: NULL out pointer and invalid device explicitly report failure.
    Neither error changes valid channel IDs or writes caller output. */
 before=connect_log_lines+connect_log_len;
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,0)==ERR_NULL_PARAMETER);
 REQUIRE(PassThruConnect(dev+999u,PROTO_CAN,0,500000,&failed)==ERR_INVALID_DEVICE_ID);
 REQUIRE(failed==0xC0DEFACEu);
 REQUIRE(strstr(before,"00 00 00 05 00 00 00 00 00 07 A1 20 00 00 00 04")!=NULL);
 REQUIRE(strstr(before,"00 00 00 05 00 00 00 00 00 07 A1 20 00 00 00 1A")!=NULL);
 /* 6: SET_CONFIG 1 changes the selected channel baud only; other known
    parameters are accepted by legacy API but are not implemented. */
 before=connect_log_lines+connect_log_len;
 option.Parameter=1u;option.Value=125000u;
 REQUIRE(PassThruIoctl(hs,IO_SET_CONFIG,&values,0)==ERR_OK);
 REQUIRE(channel(hs)->baud==125000u && channel(raw)->baud==500000u);
 REQUIRE(strstr(before,"J2534 SET_CONFIG channel/parameter/value/applied (BE)")!=NULL);
 REQUIRE(strstr(before,"00 00 00 01 00 01 E8 48 00 00 00 01")!=NULL);
 option.Value=0;REQUIRE(PassThruIoctl(hs,IO_GET_CONFIG,&values,0)==ERR_OK);
 REQUIRE(option.Value==125000u);
 /* 7: explicitly show no-op config for P3Tool's sample point, pins,
    loopback, BS and STmin. Unknown parameter values are redacted. */
 {
  static const U32 settings[]={3u,23u,30u,31u,779u,0xAA55AA55u};
  U32 i;
  for(i=0;i<sizeof(settings)/sizeof(settings[0]);i++){
   option.Parameter=settings[i];option.Value=(i==5)?0xDEADBEEFu:((i==4)?0x030Bu:(i==1?80u:0u));
   before=connect_log_lines+connect_log_len;
   REQUIRE(PassThruIoctl(hs,IO_SET_CONFIG,&values,0)==ERR_OK);
   REQUIRE(strstr(before,"J2534 SET_CONFIG channel/parameter/value/applied (BE)")!=NULL);
   REQUIRE(strstr(before,"00 00 00 00")!=NULL);
  }
  REQUIRE(strstr(connect_log_lines,"DE AD BE EF")==NULL);
  REQUIRE(strstr(connect_log_lines,"AA 55 AA 55")==NULL);
 }
 /* 8: no telemetry side effects on battery, RX or other channels. */
 REQUIRE(PassThruIoctl(dev,IO_READ_VBATT,0,&batt)==ERR_OK && batt==12500);
 n=1;REQUIRE(PassThruReadMsgs(ls,&rx,&n,0)==ERR_BUFFER_EMPTY && n==0);
 n=1;REQUIRE(PassThruReadMsgs(raw,&rx,&n,0)==ERR_BUFFER_EMPTY && n==0);
 REQUIRE(PassThruDisconnect(lsraw)==ERR_OK);
 REQUIRE(PassThruDisconnect(ls)==ERR_OK);
 REQUIRE(PassThruDisconnect(raw)==ERR_OK);
 REQUIRE(PassThruDisconnect(hs)==ERR_OK);
 REQUIRE(strstr(connect_log_lines,"YV1CZ0002A0000001")==NULL);
 capture_connect_log=0;
}

static void require_lab_cf(const PASSTHRU_MSG *m,U32 sn){
 REQUIRE(m->DataSize==12 && m->Data[4]==(0x20u | (sn&15u)));
 REQUIRE(m->Data[2]==0x07 && m->Data[3]==0x2Eu);
}
/* Stage 42: eight focused host groups for deterministic ISO15765 FC routing.
   All requests and responses are synthetic and read-only. */
static void test_stage42_multiecu_fc(U32 dev){
 U32 ch=0,peer=0,f_ecm=0,f_cem=0,f_other=0,old_count=g_ecu_count;
 U32 old_start=g_iso_rx_start,old_counter=g_filter_counter;
 U32 prior_count,prior_id,n;
 PASSTHRU_MSG mask,pat,flow,ecm_req,cem_req,functional,short_req,rx;
 const U8 read_vin[3]={0x22,0xF1,0x90},f114[3]={0x22,0xF1,0x14};
 const U8 tester[2]={0x3E,0x00};
 ECU saved0=g_ecu[0],saved1=g_ecu[1];
 g_strict_j2534_filters=1;g_iso_rx_start=0;g_ecu_count=2;
 g_ecu[0].req=0x7E0;g_ecu[0].resp=0x7E8;
 g_ecu[1].req=0x726;g_ecu[1].resp=0x72E;
 REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,500000,&ch)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,500000,&peer)==ERR_OK);
 mask=frame(PROTO_ISO15765,0xFFFFFFFFu,0,0);
 pat=frame(PROTO_ISO15765,0x7E8u,0,0);
 flow=frame(PROTO_ISO15765,0x7E0u,0,0);
 ecm_req=frame(PROTO_ISO15765,0x7E0u,read_vin,3);
 cem_req=frame(PROTO_ISO15765,0x726u,f114,3);
 functional=frame(PROTO_ISO15765,0x7DFu,read_vin,3);
 short_req=frame(PROTO_ISO15765,0x7E0u,tester,2);
 /* Group 1: duplicate response CAN ID is not unique; no filter is allocated. */
 REQUIRE(PassThruStartMsgFilter(ch,3,&mask,&pat,&flow,&f_ecm)==ERR_OK);
 prior_count=channel(ch)->filters_count;prior_id=g_filter_counter;
 flow.Data[3]=0xE1;
 REQUIRE(PassThruStartMsgFilter(ch,3,&mask,&pat,&flow,&f_other)==ERR_NOT_UNIQUE);
 REQUIRE(channel(ch)->filters_count==prior_count&&g_filter_counter==prior_id);
 puts("PASS stage42 group 1: duplicate RX CAN ID");
 /* Group 2: duplicated FC ID and crossed RX/FC identifiers are rejected. */
 pat.Data[3]=0x2E;flow.Data[3]=0xE0;
 REQUIRE(PassThruStartMsgFilter(ch,3,&mask,&pat,&flow,&f_other)==ERR_NOT_UNIQUE);
 pat.Data[3]=0xE0;flow.Data[3]=0x25;
 REQUIRE(PassThruStartMsgFilter(ch,3,&mask,&pat,&flow,&f_other)==ERR_NOT_UNIQUE);
 pat.Data[3]=0x2E;flow.Data[3]=0xE8;
 REQUIRE(PassThruStartMsgFilter(ch,3,&mask,&pat,&flow,&f_other)==ERR_NOT_UNIQUE);
 REQUIRE(channel(ch)->filters_count==1&&g_filter_counter==prior_id);
 puts("PASS stage42 group 2: duplicate FC and crossed IDs");
 /* Group 3: valid distinct ECM/CEM FC routes carry the correct multi-frame. */
 pat.Data[3]=0x2E;flow.Data[3]=0x26;
 REQUIRE(PassThruStartMsgFilter(ch,3,&mask,&pat,&flow,&f_cem)==ERR_OK);
 send(ch,&ecm_req);rx=readmsg(ch);REQUIRE(rx.DataSize==24 && rx.Data[3]==0xE8);
 send(ch,&cem_req);rx=readmsg(ch);REQUIRE(rx.DataSize==24 && rx.Data[3]==0x2E);
 puts("PASS stage42 group 3: independent ECM and CEM responses");
 /* Group 4: mismatched physical CTS destination blocks segmented response. */
 REQUIRE(PassThruStopMsgFilter(ch,f_cem)==ERR_OK);
 flow.Data[3]=0x25;
 REQUIRE(PassThruStartMsgFilter(ch,3,&mask,&pat,&flow,&f_cem)==ERR_OK);
 send(ch,&cem_req);n=1;
 REQUIRE(PassThruReadMsgs(ch,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0);
 REQUIRE(PassThruStopMsgFilter(ch,f_cem)==ERR_OK);
 flow.Data[3]=0x26;
 REQUIRE(PassThruStartMsgFilter(ch,3,&mask,&pat,&flow,&f_cem)==ERR_OK);
 send(ch,&cem_req);rx=readmsg(ch);REQUIRE(rx.Data[3]==0x2E);
 puts("PASS stage42 group 4: physical CTS request ID");
 /* Group 5: functional fanout uses each physical ECU's CTS ID, not 0x7DF. */
 send(ch,&functional);
 rx=readmsg(ch);REQUIRE(rx.DataSize==24&&rx.Data[3]==0xE8);
 rx=readmsg(ch);REQUIRE(rx.DataSize==24&&rx.Data[3]==0x2E);
 n=1;REQUIRE(PassThruReadMsgs(ch,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0);
 puts("PASS stage42 group 5: functional dual-ECU fanout");
 /* Group 6: broad receive masks can admit a short reply, not a segmented VIN. */
 REQUIRE(PassThruStopMsgFilter(ch,f_ecm)==ERR_OK);
 REQUIRE(PassThruStopMsgFilter(ch,f_cem)==ERR_OK);
 mask.Data[3]=0xFE;pat.Data[3]=0xE8;flow.Data[3]=0xE0;
 REQUIRE(PassThruStartMsgFilter(ch,3,&mask,&pat,&flow,&f_ecm)==ERR_OK);
 send(ch,&ecm_req);n=1;
 REQUIRE(PassThruReadMsgs(ch,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0);
 send(ch,&short_req);rx=readmsg(ch);
 REQUIRE(rx.DataSize==6&&rx.Data[4]==0x7E&&rx.Data[5]==0);
 puts("PASS stage42 group 6: wildcard single-frame only");
 /* Group 7: matching pairs may be reused on a different connected channel. */
 mask.Data[3]=0xFF;
 REQUIRE(PassThruStartMsgFilter(peer,3,&mask,&pat,&flow,&f_other)==ERR_OK);
 send(peer,&ecm_req);rx=readmsg(peer);REQUIRE(rx.DataSize==24&&rx.Data[3]==0xE8);
 REQUIRE(PassThruIoctl(ch,IO_CLEAR_MSG_FILTERS,0,0)==ERR_OK);
 send(ch,&ecm_req);n=1;
 REQUIRE(PassThruReadMsgs(ch,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0);
 send(peer,&ecm_req);rx=readmsg(peer);REQUIRE(rx.DataSize==24);
 puts("PASS stage42 group 7: channel isolation and CLEAR");
 /* Group 8: re-create after clear, retired IDs and channel lifecycle. */
 pat.Data[3]=0xE8;flow.Data[3]=0xE0;
 REQUIRE(PassThruStartMsgFilter(ch,3,&mask,&pat,&flow,&f_ecm)==ERR_OK);
 REQUIRE(PassThruStopMsgFilter(ch,f_ecm)==ERR_OK);
 REQUIRE(PassThruStopMsgFilter(ch,f_ecm)==ERR_INVALID_FILTER_ID);
 REQUIRE(PassThruDisconnect(ch)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,500000,&ch)==ERR_OK);
 REQUIRE(PassThruStopMsgFilter(ch,f_ecm)==ERR_INVALID_FILTER_ID);
 send(ch,&ecm_req);n=1;
 REQUIRE(PassThruReadMsgs(ch,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0);
 REQUIRE(PassThruDisconnect(ch)==ERR_OK);
 REQUIRE(PassThruDisconnect(peer)==ERR_OK);
 puts("PASS stage42 group 8: reset and stale ID");
 g_ecu[0]=saved0;g_ecu[1]=saved1;g_ecu_count=old_count;
 g_iso_rx_start=old_start;g_strict_j2534_filters=0;
 /* A failed attempt must not consume a filter ID; successful ones may. */
 REQUIRE(g_filter_counter>=old_counter);
}

/* Stage 43: extended address safety and all-or-nothing ISO15765 RX pairs.
   The emulator does NOT implement physical fifth-byte ISO-TP addressing. */
static void test_stage43_iso_rx_boundaries(U32 dev){
 const U8 read_vin[]={0x22,0xF1,0x90},short_req[]={0x3E,0x00};
 const U8 synthetic_short[]={0x7E,0x00};
 U32 iso=0,peer=0,id=0,z,count,prior_id,prior_n;
 U32 old_start=g_iso_rx_start;
 PASSTHRU_MSG mask,pat,flow,request,shortmsg,rx;
 PASSTHRU_MSG *batch;
 CHANNEL *c,*other;
 g_strict_j2534_filters=1;g_iso_rx_start=1;
 REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,500000,&iso)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,500000,&peer)==ERR_OK);
 c=channel(iso);other=channel(peer);
 mask=frame(PROTO_ISO15765,0xFFFFFFFFu,0,0);
 pat=frame(PROTO_ISO15765,0x7E8u,0,0);
 flow=frame(PROTO_ISO15765,0x7E0u,0,0);
 request=frame(PROTO_ISO15765,0x7E0u,read_vin,3);
 shortmsg=frame(PROTO_ISO15765,0x7E0u,short_req,2);
 /* Group 1: a flagged extended-address filter fails without mutation. */
 prior_id=g_filter_counter;
 mask.TxFlags=ISO15765_ADDR_TYPE;
 REQUIRE(PassThruStartMsgFilter(iso,3,&mask,&pat,&flow,&id)==ERR_NOT_SUPPORTED);
 REQUIRE(c->filters_count==0&&g_filter_counter==prior_id);
 mask.TxFlags=0;pat.TxFlags=ISO15765_ADDR_TYPE;
 REQUIRE(PassThruStartMsgFilter(iso,3,&mask,&pat,&flow,&id)==ERR_NOT_SUPPORTED);
 pat.TxFlags=0;flow.TxFlags=ISO15765_ADDR_TYPE;
 REQUIRE(PassThruStartMsgFilter(iso,3,&mask,&pat,&flow,&id)==ERR_NOT_SUPPORTED);
 flow.TxFlags=0;
 puts("PASS stage43 group 1: extended address flags are explicitly unsupported");
 /* Group 2: unsupported five-byte headers cannot allocate a filter. */
 mask.DataSize=5;pat.DataSize=5;flow.DataSize=5;
 mask.Data[4]=0xFF;pat.Data[4]=0xA1;flow.Data[4]=0xA2;
 REQUIRE(PassThruStartMsgFilter(iso,3,&mask,&pat,&flow,&id)==ERR_INVALID_MSG);
 REQUIRE(c->filters_count==0&&g_filter_counter==prior_id);
 mask.DataSize=pat.DataSize=flow.DataSize=4;
 puts("PASS stage43 group 2: no accidental five-byte route");
 /* Group 3: a flagged ISO15765 TX is rejected before producing RX. */
 request.TxFlags=ISO15765_ADDR_TYPE;
 request.Data[7]=request.Data[6];request.Data[6]=request.Data[5];
 request.Data[5]=request.Data[4];request.Data[4]=0xA2;request.DataSize=8;
 count=1;REQUIRE(PassThruWriteMsgs(iso,&request,&count,0)==ERR_NOT_SUPPORTED&&count==0);
 REQUIRE(c->count==0);request=frame(PROTO_ISO15765,0x7E0u,read_vin,3);
 puts("PASS stage43 group 3: extended-address TX never enters normal route");
 /* Group 4: normal 4-byte FC filter and short UDS still work. */
 REQUIRE(PassThruStartMsgFilter(iso,3,&mask,&pat,&flow,&id)==ERR_OK);
 send(iso,&shortmsg);rx=readmsg(iso);
 REQUIRE(rx.DataSize==6&&rx.Data[4]==0x7E&&rx.Data[5]==0);
 REQUIRE(c->count==0);
 puts("PASS stage43 group 4: normal ISO single response preserved");
 /* Group 5: 63/64 slots must not produce an orphan full message. */
 {U64 trace=c->active_trace;c->active_trace=0;
  for(z=0;z<63;z++)enqueue(c,0x7E8u,synthetic_short,2);
  c->active_trace=trace;
 }
 REQUIRE(c->count==63u);
 prior_n=c->count;send(iso,&request);
 REQUIRE(c->count==prior_n && (c->queue[(c->w+MAX_QUEUE-1u)%MAX_QUEUE].RxStatus&START_OF_MESSAGE)==0);
 puts("PASS stage43 group 5: one free slot drops the whole RX pair");
 /* Group 6: at 62/64, START_OF_MESSAGE + full response land together. */
 REQUIRE(PassThruIoctl(iso,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);
 {U64 trace=c->active_trace;c->active_trace=0;
  for(z=0;z<62;z++)enqueue(c,0x7E8u,synthetic_short,2);
  c->active_trace=trace;
 }
 send(iso,&request);REQUIRE(c->count==64u);
 REQUIRE((c->queue[62].RxStatus&START_OF_MESSAGE)!=0&&c->queue[62].DataSize==4);
 REQUIRE(c->queue[63].DataSize==24&&c->queue[63].Data[4]==0x62);
 batch=(PASSTHRU_MSG*)calloc(64,sizeof(*batch));REQUIRE(batch!=0);
 count=64;REQUIRE(PassThruReadMsgs(iso,batch,&count,0)==ERR_OK&&count==64);
 REQUIRE((batch[62].RxStatus&START_OF_MESSAGE)!=0&&batch[63].DataSize==24);
 free(batch);
 puts("PASS stage43 group 6: two slots accept atomic START + payload");
 /* Group 7: a completely full queue never overwrites existing entries. */
 {U64 trace=c->active_trace;c->active_trace=0;
  for(z=0;z<64;z++)enqueue(c,0x7E8u,synthetic_short,2);
  c->active_trace=trace;
 }
 REQUIRE(c->count==64u);
 prior_n=c->w;send(iso,&request);
 REQUIRE(c->count==64u&&c->w==prior_n);
 REQUIRE(PassThruIoctl(iso,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);
 send(iso,&request);rx=readmsg(iso);
 REQUIRE((rx.RxStatus&START_OF_MESSAGE)!=0);
 rx=readmsg(iso);REQUIRE(rx.DataSize==24);
 puts("PASS stage43 group 7: full FIFO drop and recovery");
 /* Group 8: overflow in one channel must not leak to another channel. */
 REQUIRE(PassThruStartMsgFilter(peer,3,&mask,&pat,&flow,&prior_id)==ERR_OK);
 send(peer,&request);REQUIRE(other->count==2);
 REQUIRE(c->count==0u);
 rx=readmsg(peer);REQUIRE((rx.RxStatus&START_OF_MESSAGE)!=0);
 rx=readmsg(peer);REQUIRE(rx.DataSize==24&&rx.Data[3]==0xE8);
 REQUIRE(PassThruDisconnect(peer)==ERR_OK);
 REQUIRE(PassThruDisconnect(iso)==ERR_OK);
 g_iso_rx_start=old_start;g_strict_j2534_filters=0;
 puts("PASS stage43 group 8: independent channel queue and cleanup");
}

/* Native J2534 baud guard: reject unconfigured transport without
   reserving a channel or partially applying SET_CONFIG. Synthetic only. */
static void test_zero_baud_guard(U32 dev){
 U32 untouched=0xA5A5A5A5u,cid=0;
 SCONFIG rates[2]={{1u,500000u},{1u,0u}};
 SCONFIG_LIST list={2u,rates};
 SCONFIG get={1u,0u};
 SCONFIG_LIST one={1u,&get};
 /* 1-2: both supported transport families reject a zero bit rate. */
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,0,&untouched)==ERR_INVALID_BAUDRATE);
 REQUIRE(untouched==0xA5A5A5A5u);
 REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,0,&untouched)==ERR_INVALID_BAUDRATE);
 REQUIRE(untouched==0xA5A5A5A5u);
 /* 3: null output pointer remains a parameter error. */
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,0,0)==ERR_NULL_PARAMETER);
 /* 4: unknown protocols are not reclassified as invalid speed. */
 REQUIRE(PassThruConnect(dev,0x8004u,0,0,&untouched)==ERR_INVALID_PROTOCOL_ID);
 /* 5: invalid attempts must not occupy a native channel slot. */
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,125000,&cid)==ERR_OK);
 REQUIRE(cid==1u && channel(cid)->baud==125000u);
 /* 6: reading effective rate must still report the original speed. */
 REQUIRE(PassThruIoctl(cid,IO_GET_CONFIG,&one,0)==ERR_OK);
 REQUIRE(get.Value==125000u);
 /* 7: refuse a zero rate without mutating channel or observer state. */
 get.Value=0;
 REQUIRE(PassThruIoctl(cid,IO_SET_CONFIG,&one,0)==ERR_INVALID_BAUDRATE);
 REQUIRE(channel(cid)->baud==125000u);
 /* 8: reject a later zero rate atomically, not after applying 500 kbit/s. */
 REQUIRE(PassThruIoctl(cid,IO_SET_CONFIG,&list,0)==ERR_INVALID_BAUDRATE);
 REQUIRE(channel(cid)->baud==125000u);
 get.Value=0;
 REQUIRE(PassThruIoctl(cid,IO_GET_CONFIG,&one,0)==ERR_OK);
 REQUIRE(get.Value==125000u);
 /* 9-10: a subsequent valid rate remains writable and observable. */
 rates[0].Value=500000u;list.NumOfParams=1u;
 REQUIRE(PassThruIoctl(cid,IO_SET_CONFIG,&list,0)==ERR_OK);
 REQUIRE(channel(cid)->baud==500000u);
 get.Value=0;
 REQUIRE(PassThruIoctl(cid,IO_GET_CONFIG,&one,0)==ERR_OK&&get.Value==500000u);
 REQUIRE(PassThruDisconnect(cid)==ERR_OK);
}

/* P0 write isolation: mismatched J2534 ProtocolID and invalid classic
   CAN payloads cannot enter the read-only vehicle observer or RX FIFO. */
static void test_write_transport_boundaries(U32 dev){
 const U8 uds_vin[]={0x22u,0xF1u,0x90u};
 const U8 tester_long[]={0x3Eu,0u,0u,0u,0u,0u,0u,0u,0u};
 const U8 can_unknown[]={0x56u,0x43u,0x41u,0x52u,0x4Cu,0x41u,0x42u,0u};
 const U8 can_nine[]={0x03u,0x22u,0xF1u,0x90u,0u,0u,0u,0u,0u};
 U32 can=0,iso=0,n,prior_events,prior_tx,prior_a3;
 PASSTHRU_MSG msg,rx,batch[2];
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000u,&can)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,500000u,&iso)==ERR_OK);
 prior_events=backend_len;prior_tx=g_vehicle_bridge.inspected_tx;
 prior_a3=g_vehicle_bridge.vehicle.a3_shape_seen;
 /* 1. ISO message cannot be silently interpreted on a raw CAN channel. */
 msg=frame(PROTO_ISO15765,0x7E0u,uds_vin,3u);
 n=1;REQUIRE(PassThruWriteMsgs(can,&msg,&n,0)==ERR_MSG_PROTOCOL_ID&&n==0);
 REQUIRE(backend_len==prior_events && g_vehicle_bridge.inspected_tx==prior_tx);
 REQUIRE(channel(can)->count==0);
 /* 2. Raw CAN message cannot enter a reassembled ISO15765 channel. */
 msg=frame(PROTO_CAN,0x7E0u,can_unknown,8u);
 n=1;REQUIRE(PassThruWriteMsgs(iso,&msg,&n,0)==ERR_MSG_PROTOCOL_ID&&n==0);
 REQUIRE(backend_len==prior_events && g_vehicle_bridge.inspected_tx==prior_tx);
 REQUIRE(channel(iso)->count==0);
 /* 3. Unknown vendor protocol in PASSTHRU_MSG is not silently aliased. */
 msg=frame(0x8004u,0x7E0u,uds_vin,3u);
 n=1;REQUIRE(PassThruWriteMsgs(can,&msg,&n,0)==ERR_MSG_PROTOCOL_ID&&n==0);
 REQUIRE(backend_len==prior_events && g_vehicle_bridge.inspected_tx==prior_tx);
 /* 4. A raw CAN DLC of nine is invalid, with no diagnostic side effect. */
 msg=frame(PROTO_CAN,0x7E0u,can_nine,9u);
 n=1;REQUIRE(PassThruWriteMsgs(can,&msg,&n,0)==ERR_INVALID_MSG&&n==0);
 REQUIRE(backend_len==prior_events && g_vehicle_bridge.inspected_tx==prior_tx);
 REQUIRE(channel(can)->count==0);
 /* 5. Existing minimum J2534 payload guard still rejects short data. */
 msg=frame(PROTO_CAN,0x7E0u,can_unknown,8u);msg.DataSize=4u;
 n=1;REQUIRE(PassThruWriteMsgs(can,&msg,&n,0)==ERR_INVALID_MSG&&n==0);
 REQUIRE(backend_len==prior_events && g_vehicle_bridge.inspected_tx==prior_tx);
 /* 6. Normal eight-byte unmatched lab CAN TX stays valid but silent. */
 msg=frame(PROTO_CAN,0x000FFFFEu,can_unknown,8u);
 n=1;REQUIRE(PassThruWriteMsgs(can,&msg,&n,0)==ERR_OK&&n==1);
 REQUIRE(g_vehicle_bridge.inspected_tx>prior_tx);
 REQUIRE(channel(can)->count==0);
 n=1;REQUIRE(PassThruReadMsgs(can,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0);
 /* 7. A longer ISO15765 UDS payload remains valid and receives a reply. */
 msg=frame(PROTO_ISO15765,0x7E0u,tester_long,9u);
 n=1;REQUIRE(PassThruWriteMsgs(iso,&msg,&n,0)==ERR_OK&&n==1);
 rx=readmsg(iso);REQUIRE(rx.ProtocolID==PROTO_ISO15765);
 REQUIRE(rx.DataSize==6u&&rx.Data[4]==0x7Eu&&rx.Data[5]==0u);
 /* 8. A mixed batch preserves the count already written, but the invalid
    next message cannot produce extra events, RX or observer evidence. */
 batch[0]=frame(PROTO_CAN,0x000FFFFEu,can_unknown,8u);
 batch[1]=frame(PROTO_ISO15765,0x7E0u,uds_vin,3u);
 prior_tx=g_vehicle_bridge.inspected_tx;
 n=2;REQUIRE(PassThruWriteMsgs(can,batch,&n,0)==ERR_MSG_PROTOCOL_ID&&n==1);
 REQUIRE(g_vehicle_bridge.inspected_tx==prior_tx+1u);
 REQUIRE(channel(can)->count==0);
 /* 9. A bad first batch entry leaves a valid later entry unprocessed. */
 batch[0]=frame(PROTO_ISO15765,0x7E0u,uds_vin,3u);
 batch[1]=frame(PROTO_CAN,0x000FFFFEu,can_unknown,8u);
 prior_events=backend_len;prior_tx=g_vehicle_bridge.inspected_tx;
 n=2;REQUIRE(PassThruWriteMsgs(can,batch,&n,0)==ERR_MSG_PROTOCOL_ID&&n==0);
 REQUIRE(backend_len==prior_events && g_vehicle_bridge.inspected_tx==prior_tx);
 /* 10. Ordinary ISO VIN read remains available on the correct channel. */
 msg=frame(PROTO_ISO15765,0x7E0u,uds_vin,3u);
 n=1;REQUIRE(PassThruWriteMsgs(iso,&msg,&n,0)==ERR_OK&&n==1);
 rx=readmsg(iso);REQUIRE(rx.ProtocolID==PROTO_ISO15765);
 REQUIRE(rx.Data[4]==0x62u&&rx.Data[5]==0xF1u&&rx.Data[6]==0x90u);
 REQUIRE(channel(can)->count==0);
 REQUIRE(PassThruDisconnect(iso)==ERR_OK);
 REQUIRE(PassThruDisconnect(can)==ERR_OK);
 /* This transport regression must not pre-seed the later exact A3 counter. */
 REQUIRE(g_vehicle_bridge.vehicle.a3_shape_seen==prior_a3);
 puts("PASS J2534 WriteMsgs: protocol isolation, classic CAN DLC and batch boundaries");
}

/* J2534 TX identifiers are bounded by 29 CAN bits independently of
   the driver flags. These are synthetic lab requests, not OEM traffic. */
static void test_can_id_range_guard(U32 dev){
 const U8 marker[8]={0x56u,0x43u,0x41u,0x52u,0x4Cu,0x41u,0x42u,0u};
 const U8 uds_vin[3]={0x22u,0xF1u,0x90u};
 U32 can=0,iso=0,n,prior_events,prior_tx,prior_a3;
 PASSTHRU_MSG msg,rx,batch[2];
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000u,&can)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,500000u,&iso)==ERR_OK);
 prior_events=backend_len;
 prior_tx=g_vehicle_bridge.inspected_tx;
 prior_a3=g_vehicle_bridge.vehicle.a3_shape_seen;
 /* 1. First out-of-range ID on CAN: no backend event or observer mutation. */
 msg=frame(PROTO_CAN,0x20000000u,marker,8u);
 n=1;REQUIRE(PassThruWriteMsgs(can,&msg,&n,0)==ERR_INVALID_MSG&&n==0);
 REQUIRE(backend_len==prior_events&&g_vehicle_bridge.inspected_tx==prior_tx);
 REQUIRE(channel(can)->count==0);
 /* 2. All-one ID is invalid even if the CAN_29BIT_ID flag is set. */
 msg=frame(PROTO_CAN,0xFFFFFFFFu,marker,8u);
 msg.TxFlags=CAN_29BIT_ID;
 n=1;REQUIRE(PassThruWriteMsgs(can,&msg,&n,0)==ERR_INVALID_MSG&&n==0);
 REQUIRE(backend_len==prior_events&&g_vehicle_bridge.inspected_tx==prior_tx);
 /* 3. ISO15765 must enforce the same physical CAN identifier boundary. */
 msg=frame(PROTO_ISO15765,0x20000000u,uds_vin,3u);
 n=1;REQUIRE(PassThruWriteMsgs(iso,&msg,&n,0)==ERR_INVALID_MSG&&n==0);
 REQUIRE(backend_len==prior_events&&g_vehicle_bridge.inspected_tx==prior_tx);
 REQUIRE(channel(iso)->count==0);
 /* 4. The extended-ID flag cannot override an invalid 30-bit identifier. */
 msg.TxFlags=CAN_29BIT_ID;
 n=1;REQUIRE(PassThruWriteMsgs(iso,&msg,&n,0)==ERR_INVALID_MSG&&n==0);
 REQUIRE(backend_len==prior_events&&g_vehicle_bridge.inspected_tx==prior_tx);
 /* 5. The exact 29-bit maximum is valid on raw CAN (no fabricated ECU). */
 msg=frame(PROTO_CAN,0x1FFFFFFFu,marker,8u);
 n=1;REQUIRE(PassThruWriteMsgs(can,&msg,&n,0)==ERR_OK&&n==1);
 n=1;REQUIRE(PassThruReadMsgs(can,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0);
 /* 6. The same maximum identifier is valid on ISO15765. */
 msg=frame(PROTO_ISO15765,0x1FFFFFFFu,uds_vin,3u);
 n=1;REQUIRE(PassThruWriteMsgs(iso,&msg,&n,0)==ERR_OK&&n==1);
 n=1;REQUIRE(PassThruReadMsgs(iso,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0);
 /* 7. A regular 11-bit CAN ID is not blocked by the range guard. */
 msg=frame(PROTO_CAN,0x7FFu,marker,8u);
 n=1;REQUIRE(PassThruWriteMsgs(can,&msg,&n,0)==ERR_OK&&n==1);
 n=1;REQUIRE(PassThruReadMsgs(can,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0);
 /* 8. Mixed valid-then-invalid batch returns the successful count and
    never attributes the invalid second ID to a vehicle request. */
 batch[0]=frame(PROTO_CAN,0x1FFFFFFFu,marker,8u);
 batch[1]=frame(PROTO_CAN,0x20000000u,marker,8u);
 prior_tx=g_vehicle_bridge.inspected_tx;
 n=2;REQUIRE(PassThruWriteMsgs(can,batch,&n,0)==ERR_INVALID_MSG&&n==1);
 REQUIRE(g_vehicle_bridge.inspected_tx==prior_tx+1u);
 REQUIRE(channel(can)->count==0);
 /* 9. Invalid first entry does not send the following valid message. */
 batch[0]=frame(PROTO_CAN,0xE0000000u,marker,8u);
 batch[1]=frame(PROTO_CAN,0x1FFFFFFFu,marker,8u);
 prior_tx=g_vehicle_bridge.inspected_tx;prior_events=backend_len;
 n=2;REQUIRE(PassThruWriteMsgs(can,batch,&n,0)==ERR_INVALID_MSG&&n==0);
 REQUIRE(backend_len==prior_events&&g_vehicle_bridge.inspected_tx==prior_tx);
 /* 10. A normal read-only ISO F190 is unaffected. */
 msg=frame(PROTO_ISO15765,0x7E0u,uds_vin,3u);
 n=1;REQUIRE(PassThruWriteMsgs(iso,&msg,&n,0)==ERR_OK&&n==1);
 rx=readmsg(iso);REQUIRE(rx.ProtocolID==PROTO_ISO15765);
 REQUIRE(rx.Data[4]==0x62u&&rx.Data[5]==0xF1u&&rx.Data[6]==0x90u);
 REQUIRE(g_vehicle_bridge.vehicle.a3_shape_seen==prior_a3);
 REQUIRE(PassThruDisconnect(iso)==ERR_OK);
 REQUIRE(PassThruDisconnect(can)==ERR_OK);
 puts("PASS J2534 CAN ID range: 29-bit bounds, valid IDs and batch isolation");
}

/* The observed 13-frame D2 transport must not silently interpret 0x48..0x4E
   final markers as seven data bytes. This guards only the 0x08-series example;
   different documented sub-block forms remain transport-unverified. */
static void test_known_b9fb_13frame_final_marker(void){
 D2_PROFILE d={0};
 U32 i;
 d.target=0x50u;d.subcommand=0xFBu;d.response_id=0x01200003u;
 d.frame_count=13u;
 d.frame[0][0]=0x8Fu;d.frame[0][1]=0x50u;
 d.frame[0][2]=0xF9u;d.frame[0][3]=0xFBu;
 for(i=1;i<12u;i++)d.frame[i][0]=(U8)(0x08u|(i&7u));
 /* 1: published final frame marker is exactly 0x4F. */
 d.frame[12][0]=0x4Fu;REQUIRE(validate_d2_fixture(&d));
 /* 2: all seven alternative 4x terminal lengths are refused. */
 for(i=0x48u;i<=0x4Eu;i++){
  d.frame[12][0]=(U8)i;REQUIRE(!validate_d2_fixture(&d));
 }
 /* 3: valid terminal is still accepted after invalid probes. */
 d.frame[12][0]=0x4Fu;REQUIRE(validate_d2_fixture(&d));
 /* 4: an early terminal in the 13-frame exchange never succeeds. */
 d.frame[4][0]=0x4Fu;REQUIRE(!validate_d2_fixture(&d));
 d.frame[4][0]=0x0Cu;
 /* 5: intermediate sequence tampering still fails. */
 d.frame[7][0]=0x0Au;REQUIRE(!validate_d2_fixture(&d));
 d.frame[7][0]=0x0Fu;REQUIRE(validate_d2_fixture(&d));
 /* 6: the same published 13-frame header shape works for target 0x40. */
 d.target=0x40u;d.frame[0][1]=0x40u;
 REQUIRE(validate_d2_fixture(&d));
 /* 7: a different frame count keeps its existing general final framing. */
 d.target=0x50u;d.frame[0][1]=0x50u;
 d.frame_count=12u;d.frame[11][0]=0x48u;
 REQUIRE(validate_d2_fixture(&d));
 /* 8: separately encoded 0x10-series transport is not generalized into
    the observed 0x08-series 4F rule. It is not proven to match an OEM ECU. */
 d.frame_count=13u;d.frame[0][0]=0x97u;
 for(i=1;i<12u;i++)d.frame[i][0]=(U8)(0x10u|(i&7u));
 d.frame[12][0]=0x48u;
 REQUIRE(validate_d2_fixture(&d));
 puts("PASS D2 B9FB 13-frame final 4F boundary, synthetic native audit");
}

/* A follow-up D2 read-only request supersedes the old exchange on the
   same J2534 channel even if its target/opcode has no recorded fixture.
   No real CEM identity or positive A3/A6 response is synthesized. */
/* P0: a B9FB replay is bound to the channel bitrate at request time.
   A DATA_RATE change must never deliver its queued/staged D2 frames on
   the new bus. All fixtures here are synthetic and read-only. */
static void test_d2_replay_isolation_on_set_config(U32 dev){
 D2_PROFILE saved_fb=g_d2[2];U32 saved_strict=g_p2_strict_routing;
 p2_j2534_bridge saved_bridge=g_vehicle_bridge;
 U32 hs=0,peer=0,n=1;U64 rid,prior;CHANNEL *ch,*other;
 PASSTHRU_MSG m,rx;const char *start;
 const U8 fb[]={0xCBu,0x50u,0xB9u,0xFBu,0,0,0,0};
 SCONFIG rate={1u,500000u},noop={779u,0u};
 SCONFIG_LIST single={1u,&rate},nonrate={1u,&noop};
 SCONFIG pair[2]={{1u,125000u},{1u,0u}},reversible[2]={{1u,125000u},{1u,500000u}};
 SCONFIG_LIST batch={2u,pair},roundtrip={2u,reversible};
 bytes_zero(&g_d2[2],sizeof(g_d2[2]));
 g_d2[2].target=0x50u;g_d2[2].subcommand=0xFBu;
 g_d2[2].response_id=0x01200003u;g_d2[2].baud=500000u;
 g_d2[2].frame_count=3u;
 g_d2[2].frame[0][0]=0x8Fu;g_d2[2].frame[0][1]=0x50u;
 g_d2[2].frame[0][2]=0xF9u;g_d2[2].frame[0][3]=0xFBu;
 g_d2[2].frame[1][0]=0x09u;g_d2[2].frame[2][0]=0x4Cu;
 REQUIRE(validate_d2_fixture(&g_d2[2]));
 g_p2_strict_routing=1u;
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000u,&hs)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000u,&peer)==ERR_OK);
 ch=channel(hs);other=channel(peer);
 m=frame(PROTO_CAN,0x000FFFFEu,fb,8);

 /* 1. A changed DATA_RATE cancels staged frames and first queued frame. */
 start=backend_lines+backend_len;send(hs,&m);
 rid=last_tx_request(start);REQUIRE(rid && ch->count==1u&&ch->d2_count==3u);
 rate.Value=125000u;REQUIRE(PassThruIoctl(hs,IO_SET_CONFIG,&single,0)==ERR_OK);
 REQUIRE(ch->baud==125000u&&ch->count==0u&&ch->d2_count==0u);
 REQUIRE(terminal_for(start,rid,"d2_superseded","aborted")==1u);
 tick+=100;n=1;
 REQUIRE(PassThruReadMsgs(hs,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);

 /* 2. Already queued old-bus D2 frames are removed; unrelated CAN
    entries survive compaction in their original FIFO order. */
 rate.Value=500000u;REQUIRE(PassThruIoctl(hs,IO_SET_CONFIG,&single,0)==ERR_OK);
 fill_untraced_rx(ch,1u);
 start=backend_lines+backend_len;send(hs,&m);rid=last_tx_request(start);
 REQUIRE(ch->count==2u);
 tick+=100; pump_d2(ch);pump_d2(ch);
 REQUIRE(ch->d2_count==0u&&ch->count==4u);
 rate.Value=125000u;REQUIRE(PassThruIoctl(hs,IO_SET_CONFIG,&single,0)==ERR_OK);
 REQUIRE(ch->count==1u && ch->d2_count==0u);
 REQUIRE(terminal_for(start,rid,"d2_superseded","aborted")==1u);
 rx=readmsg(hs);REQUIRE(rx.Data[2]==0x05u&&rx.Data[3]==0x55u);
 n=1;REQUIRE(PassThruReadMsgs(hs,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0);

 /* 3. Retuning one channel cannot abort a different channel's B9FB. */
 rate.Value=500000u;REQUIRE(PassThruIoctl(hs,IO_SET_CONFIG,&single,0)==ERR_OK);
 send(peer,&m);prior=other->d2_trace;
 REQUIRE(prior&&other->count==1u&&other->d2_count==3u);
 rate.Value=125000u;REQUIRE(PassThruIoctl(hs,IO_SET_CONFIG,&single,0)==ERR_OK);
 REQUIRE(other->d2_trace==prior&&other->count==1u&&other->d2_count==3u);
 rx=readmsg(peer);REQUIRE(rx.Data[4]==0x8Fu);
 REQUIRE(PassThruIoctl(peer,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);

 /* 4. A non-DATA_RATE SET_CONFIG is not a bus retune. */
 rate.Value=500000u;REQUIRE(PassThruIoctl(hs,IO_SET_CONFIG,&single,0)==ERR_OK);
 send(hs,&m);prior=ch->d2_trace;
 REQUIRE(PassThruIoctl(hs,IO_SET_CONFIG,&nonrate,0)==ERR_OK);
 REQUIRE(prior && ch->d2_trace==prior && ch->count==1u);
 rx=readmsg(hs);REQUIRE(rx.Data[4]==0x8Fu);
 REQUIRE(PassThruIoctl(hs,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);

 /* 5. Reapplying the current rate leaves the staged reply intact. */
 send(hs,&m);prior=ch->d2_trace;
 REQUIRE(PassThruIoctl(hs,IO_SET_CONFIG,&single,0)==ERR_OK);
 REQUIRE(ch->d2_trace==prior&&ch->count==1u&&ch->d2_count==3u);
 REQUIRE(PassThruIoctl(hs,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);

 /* 6. A zero baud in a later list entry is rejected atomically. */
 send(hs,&m);prior=ch->d2_trace;
 REQUIRE(PassThruIoctl(hs,IO_SET_CONFIG,&batch,0)==ERR_INVALID_BAUDRATE);
 REQUIRE(ch->baud==500000u&&ch->d2_trace==prior&&ch->count==1u);
 REQUIRE(PassThruIoctl(hs,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);

 /* 7. Intermediate rate changes ending at the original bitrate are
    not a real retune: preserve staged B9FB and observer generation. */
 send(hs,&m);prior=ch->d2_trace;
 {U32 observer_gen=g_vehicle_bridge.next_generation;
  REQUIRE(PassThruIoctl(hs,IO_SET_CONFIG,&roundtrip,0)==ERR_OK);
  REQUIRE(g_vehicle_bridge.next_generation==observer_gen);
 }
 REQUIRE(ch->baud==500000u&&ch->d2_trace==prior&&ch->count==1u);
 REQUIRE(PassThruIoctl(hs,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);

 /* 8. After retuning away and back, a NEW read-only B9FB request
    delivers its own 8F / 09 / 4C frames, never stale prior attempts. */
 start=backend_lines+backend_len;send(hs,&m);rid=last_tx_request(start);
 rate.Value=125000u;REQUIRE(PassThruIoctl(hs,IO_SET_CONFIG,&single,0)==ERR_OK);
 REQUIRE(terminal_for(start,rid,"d2_superseded","aborted")==1u);
 rate.Value=500000u;REQUIRE(PassThruIoctl(hs,IO_SET_CONFIG,&single,0)==ERR_OK);
 start=backend_lines+backend_len;send(hs,&m);prior=last_tx_request(start);
 REQUIRE(prior && prior!=rid);
 rx=readmsg(hs);REQUIRE(rx.Data[4]==0x8Fu);
 tick+=25;rx=readmsg(hs);REQUIRE(rx.Data[4]==0x09u);
 tick+=25;rx=readmsg(hs);REQUIRE(rx.Data[4]==0x4Cu);
 REQUIRE(terminal_for(start,prior,"none","responded")==1u);
 REQUIRE(terminal_count_for(start,prior)==1u);
 n=1;REQUIRE(PassThruReadMsgs(hs,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);

 REQUIRE(PassThruDisconnect(peer)==ERR_OK);
 REQUIRE(PassThruDisconnect(hs)==ERR_OK);
 g_d2[2]=saved_fb;g_p2_strict_routing=saved_strict;
 g_vehicle_bridge=saved_bridge;
 puts("PASS P0 D2 DATA_RATE retune isolation: 8 read-only host cases");
}

static void test_d2_unknown_target_supersession(U32 dev){
 D2_PROFILE saved_fb=g_d2[2],saved_fc=g_d2[5];
 U32 saved_strict=g_p2_strict_routing;
 U32 ch1=0,ch2=0,n,i;
 U64 first,second;
 CHANNEL *ch;
 PASSTHRU_MSG rx,msg;
 const char *start;
 const U8 fb[]={0xCBu,0x50u,0xB9u,0xFBu,0,0,0,0};
 const U8 unknown[]={0xCBu,0x61u,0xB9u,0xFBu,0,0,0,0};
 const U8 missing_fc[]={0xCBu,0x50u,0xB9u,0xFCu,0,0,0,0};
 const U8 other_can[]={0x56u,0x43u,0x41u,0x52u,0x4Cu,0x41u,0x42u,0u};
 /* Explicit opt-in synthetic lab fixture on known HS target 0x50. */
 bytes_zero(&g_d2[2],sizeof(g_d2[2]));
 g_d2[2].target=0x50u;g_d2[2].subcommand=0xFBu;
 g_d2[2].response_id=0x01200003u;g_d2[2].baud=500000u;
 g_d2[2].frame_count=3u;
 g_d2[2].frame[0][0]=0x8Fu;g_d2[2].frame[0][1]=0x50u;
 g_d2[2].frame[0][2]=0xF9u;g_d2[2].frame[0][3]=0xFBu;
 g_d2[2].frame[1][0]=0x09u;g_d2[2].frame[2][0]=0x4Cu;
 REQUIRE(validate_d2_fixture(&g_d2[2]));
 g_d2[5].frame_count=0u;g_p2_strict_routing=1u;
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000u,&ch1)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000u,&ch2)==ERR_OK);
 ch=channel(ch1);

 /* 1. A missing, unconfigured D2 target must abort staged and queued FB
    before it can erroneously deliver old B9FB bytes as a new reply. */
 start=backend_lines+backend_len;
 msg=frame(PROTO_CAN,0x000FFFFEu,fb,8);send(ch1,&msg);
 first=last_tx_request(start);REQUIRE(first&&ch->d2_count==3u&&ch->count==1u);
 msg=frame(PROTO_CAN,0x000FFFFEu,unknown,8);send(ch1,&msg);
 second=last_tx_request(start);
 REQUIRE(second&&second!=first);
 REQUIRE(terminal_for(start,first,"d2_superseded","aborted")==1);
 REQUIRE(terminal_for(start,second,"missing_profile","no_response")==1);
 REQUIRE(terminal_count_for(start,first)==1&&terminal_count_for(start,second)==1);
 REQUIRE(ch->d2_count==0u&&ch->d2_trace==0u&&ch->count==0u);
 tick+=100;n=1;REQUIRE(PassThruReadMsgs(ch1,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);

 /* 2. Even if all old D2 frames are queued, the absent target removes
    them, not just the staged tail. */
 start=backend_lines+backend_len;
 msg=frame(PROTO_CAN,0x000FFFFEu,fb,8);send(ch1,&msg);
 first=last_tx_request(start);
 tick+=100;for(i=0;i<2;i++)pump_d2(ch);
 REQUIRE(ch->count==3u&&ch->d2_count==0u);
 msg=frame(PROTO_CAN,0x000FFFFEu,unknown,8);send(ch1,&msg);
 REQUIRE(ch->count==0u);
 REQUIRE(terminal_for(start,first,"d2_superseded","aborted")==1);
 REQUIRE(event_count_since(start,"\"kind\":\"rx_dropped\"")==3u);

 /* 3. A *known* target but unconfigured B9FC also cancels old B9FB.
    No accidental B9FC or B9FB positive reply is generated. */
 start=backend_lines+backend_len;
 msg=frame(PROTO_CAN,0x000FFFFEu,fb,8);send(ch1,&msg);
 first=last_tx_request(start);
 msg=frame(PROTO_CAN,0x000FFFFEu,missing_fc,8);send(ch1,&msg);
 second=last_tx_request(start);
 REQUIRE(terminal_for(start,first,"d2_superseded","aborted")==1);
 REQUIRE(terminal_for(start,second,"missing_profile","no_response")==1);
 REQUIRE(ch->count==0u&&ch->d2_count==0u);

 /* 4. Missing D2 on channel 2 does not cancel a pending response on 1. */
 msg=frame(PROTO_CAN,0x000FFFFEu,fb,8);send(ch1,&msg);
 first=ch->d2_trace;REQUIRE(first&&ch->count==1u);
 msg=frame(PROTO_CAN,0x000FFFFEu,unknown,8);send(ch2,&msg);
 REQUIRE(ch->d2_trace==first&&ch->count==1u);
 rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x8Fu);
 tick+=20;rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x09u);
 tick+=20;rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x4Cu);

 /* 5. Unrelated raw CAN traffic must not cancel a staged D2 reply. */
 msg=frame(PROTO_CAN,0x000FFFFEu,fb,8);send(ch1,&msg);
 first=ch->d2_trace;REQUIRE(first);
 msg=frame(PROTO_CAN,0x555u,other_can,8);send(ch1,&msg);
 REQUIRE(ch->d2_trace==first&&ch->count==1u);
 rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x8Fu);
 tick+=20;rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x09u);
 tick+=20;rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x4Cu);

 /* 6. An untraced, unrelated RX remains FIFO-ordered after cancellation. */
 fill_untraced_rx(ch,1u);
 start=backend_lines+backend_len;
 msg=frame(PROTO_CAN,0x000FFFFEu,fb,8);send(ch1,&msg);
 first=last_tx_request(start);REQUIRE(ch->count==2u);
 msg=frame(PROTO_CAN,0x000FFFFEu,unknown,8);send(ch1,&msg);
 REQUIRE(ch->count==1u&&ch->d2_count==0u);
 REQUIRE(terminal_for(start,first,"d2_superseded","aborted")==1);
 rx=readmsg(ch1);REQUIRE(rx.Data[2]==0x05u&&rx.Data[3]==0x55u);
 n=1;REQUIRE(PassThruReadMsgs(ch1,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);

 /* 7. The first D2 frame already delivered cannot be revoked; only its
    remaining staged frames are cancelled with a single old terminal. */
 start=backend_lines+backend_len;
 msg=frame(PROTO_CAN,0x000FFFFEu,fb,8);send(ch1,&msg);
 first=last_tx_request(start);
 rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x8Fu);
 msg=frame(PROTO_CAN,0x000FFFFEu,unknown,8);send(ch1,&msg);
 REQUIRE(terminal_for(start,first,"d2_superseded","aborted")==1);
 REQUIRE(terminal_count_for(start,first)==1);
 tick+=100;n=1;REQUIRE(PassThruReadMsgs(ch1,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);

 /* 8. Retrying the *same* known target still supersedes the old reply
    and emits only the new recorded, read-only three-frame fixture. */
 start=backend_lines+backend_len;
 msg=frame(PROTO_CAN,0x000FFFFEu,fb,8);send(ch1,&msg);
 first=last_tx_request(start);
 send(ch1,&msg);second=last_tx_request(start);
 REQUIRE(first&&second&&first!=second);
 REQUIRE(terminal_for(start,first,"d2_superseded","aborted")==1);
 REQUIRE(ch->count==1u&&ch->d2_count==3u);
 rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x8Fu);
 tick+=20;rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x09u);
 tick+=20;rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x4Cu);
 REQUIRE(terminal_for(start,second,"none","responded")==1);
 REQUIRE(terminal_count_for(start,second)==1);
 n=1;REQUIRE(PassThruReadMsgs(ch1,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);

 REQUIRE(PassThruDisconnect(ch2)==ERR_OK);
 REQUIRE(PassThruDisconnect(ch1)==ERR_OK);
 g_d2[2]=saved_fb;g_d2[5]=saved_fc;g_p2_strict_routing=saved_strict;
 puts("PASS P0 D2 retry isolation: unconfigured target, B9FC and channel FIFO");
}

/* Recognized CEM A3/A6 probes have NO validated positive OEM reply.
   They must also close the previous same-channel B9 exchange, otherwise a
   stale 8F/09/4C fragment could look like an A3/A6 discovery response. */
static void test_d2_a3_a6_supersession(U32 dev){
 /* The passive P2 observer is global: this synthetic replay intentionally
    sends additional A3/A6 requests. Restore the complete pre-test bridge
    after disconnect so later observer tests keep their original baselines. */
 p2_j2534_bridge saved_bridge=g_vehicle_bridge;
 D2_PROFILE saved=g_d2[2];U32 strict=g_p2_strict_routing;
 U32 ch1=0,ch2=0,n,i;U64 old,newrid;
 CHANNEL *ch;PASSTHRU_MSG m,rx;const char *start;
 const U8 fb[]={0xCBu,0x50u,0xB9u,0xFBu,0,0,0,0};
 const U8 a3[]={0xCFu,0x50u,0xA3u,0x02u,0x03u,0xA5u,0xA5u,0};
 const U8 a6[]={0xCFu,0x50u,0xA6u,0x1Au,0x04u,0x01u,0,0};
 bytes_zero(&g_d2[2],sizeof(g_d2[2]));
 g_d2[2].target=0x50u;g_d2[2].subcommand=0xFBu;
 g_d2[2].response_id=0x01200003u;g_d2[2].baud=500000u;
 g_d2[2].frame_count=3u;
 g_d2[2].frame[0][0]=0x8Fu;g_d2[2].frame[0][1]=0x50u;
 g_d2[2].frame[0][2]=0xF9u;g_d2[2].frame[0][3]=0xFBu;
 g_d2[2].frame[1][0]=0x09u;g_d2[2].frame[2][0]=0x4Cu;
 REQUIRE(validate_d2_fixture(&g_d2[2]));
 g_p2_strict_routing=1u;
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000u,&ch1)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000u,&ch2)==ERR_OK);
 ch=channel(ch1);

 /* 1: A3 cancels queued first B9FB and staged tail, and finishes
    as an unsupported read-only probe with no simulated CEM RX. */
 start=backend_lines+backend_len;
 m=frame(PROTO_CAN,0x000FFFFEu,fb,8);send(ch1,&m);
 old=last_tx_request(start);REQUIRE(old&&ch->count==1u&&ch->d2_count==3u);
 m=frame(PROTO_CAN,0x000FFFFEu,a3,8);send(ch1,&m);
 newrid=last_tx_request(start);
 REQUIRE(newrid&&newrid!=old);
 REQUIRE(terminal_for(start,old,"d2_superseded","aborted")==1);
 REQUIRE(terminal_for(start,newrid,"unimplemented_probe","no_response")==1);
 REQUIRE(terminal_count_for(start,old)==1&&terminal_count_for(start,newrid)==1);
 REQUIRE(ch->count==0u&&ch->d2_count==0u&&ch->d2_trace==0u);
 tick+=100;n=1;
 REQUIRE(PassThruReadMsgs(ch1,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);

 /* 2: A6 also cancels B9FB with no invented E6 reply. */
 start=backend_lines+backend_len;
 m=frame(PROTO_CAN,0x000FFFFEu,fb,8);send(ch1,&m);
 old=last_tx_request(start);
 m=frame(PROTO_CAN,0x000FFFFEu,a6,8);send(ch1,&m);
 newrid=last_tx_request(start);
 REQUIRE(terminal_for(start,old,"d2_superseded","aborted")==1);
 REQUIRE(terminal_for(start,newrid,"unimplemented_probe","no_response")==1);
 REQUIRE(ch->count==0u&&ch->d2_count==0u);

 /* 3: all 3 old B9FB frames already queued must be dropped together. */
 start=backend_lines+backend_len;
 m=frame(PROTO_CAN,0x000FFFFEu,fb,8);send(ch1,&m);
 old=last_tx_request(start);
 tick+=100;for(i=0;i<2u;i++)pump_d2(ch);
 REQUIRE(ch->count==3u&&ch->d2_count==0u);
 m=frame(PROTO_CAN,0x000FFFFEu,a3,8);send(ch1,&m);
 REQUIRE(ch->count==0u);
 REQUIRE(event_count_since(start,"\"kind\":\"rx_dropped\"")==3u);
 REQUIRE(terminal_for(start,old,"d2_superseded","aborted")==1);

 /* 4: a first frame already delivered is not revocable, only remaining
    response tail is cancelled by the new A6 probe. */
 start=backend_lines+backend_len;
 m=frame(PROTO_CAN,0x000FFFFEu,fb,8);send(ch1,&m);
 old=last_tx_request(start);
 rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x8Fu);
 m=frame(PROTO_CAN,0x000FFFFEu,a6,8);send(ch1,&m);
 REQUIRE(terminal_for(start,old,"d2_superseded","aborted")==1);
 REQUIRE(terminal_count_for(start,old)==1);
 tick+=100;n=1;
 REQUIRE(PassThruReadMsgs(ch1,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);

 /* 5: A3 on another J2534 channel cannot stop channel one's reply. */
 m=frame(PROTO_CAN,0x000FFFFEu,fb,8);send(ch1,&m);
 old=ch->d2_trace;REQUIRE(old&&ch->count==1u);
 m=frame(PROTO_CAN,0x000FFFFEu,a3,8);send(ch2,&m);
 REQUIRE(ch->d2_trace==old&&ch->count==1u);
 rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x8Fu);
 tick+=20;rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x09u);
 tick+=20;rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x4Cu);

 /* 6: a matching byte pattern on an unrelated CAN ID is not a D2
    discovery request and cannot cancel a staged B9FB reply. */
 m=frame(PROTO_CAN,0x000FFFFEu,fb,8);send(ch1,&m);
 old=ch->d2_trace;REQUIRE(old&&ch->count==1u);
 m=frame(PROTO_CAN,0x555u,a3,8);send(ch1,&m);
 REQUIRE(ch->d2_trace==old&&ch->count==1u);
 rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x8Fu);
 tick+=20;rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x09u);
 tick+=20;rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x4Cu);

 /* 7: unrelated RX remains FIFO ordered across A3 cancellation. */
 fill_untraced_rx(ch,1u);
 m=frame(PROTO_CAN,0x000FFFFEu,fb,8);send(ch1,&m);
 REQUIRE(ch->count==2u);
 m=frame(PROTO_CAN,0x000FFFFEu,a3,8);send(ch1,&m);
 REQUIRE(ch->count==1u&&ch->d2_count==0u);
 rx=readmsg(ch1);REQUIRE(rx.Data[2]==0x05u&&rx.Data[3]==0x55u);
 n=1;REQUIRE(PassThruReadMsgs(ch1,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);

 /* 8: a fresh B9FB after an unsupported A6 probe still delivers only
    its own 3 recorded frames, with a single successful terminal. */
 start=backend_lines+backend_len;
 m=frame(PROTO_CAN,0x000FFFFEu,a6,8);send(ch1,&m);
 old=last_tx_request(start);
 REQUIRE(terminal_for(start,old,"unimplemented_probe","no_response")==1);
 m=frame(PROTO_CAN,0x000FFFFEu,fb,8);send(ch1,&m);
 newrid=last_tx_request(start);REQUIRE(newrid&&newrid!=old);
 rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x8Fu);
 tick+=20;rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x09u);
 tick+=20;rx=readmsg(ch1);REQUIRE(rx.Data[4]==0x4Cu);
 REQUIRE(terminal_for(start,newrid,"none","responded")==1);
 REQUIRE(terminal_count_for(start,newrid)==1);
 n=1;REQUIRE(PassThruReadMsgs(ch1,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);
 REQUIRE(PassThruDisconnect(ch2)==ERR_OK);
 REQUIRE(PassThruDisconnect(ch1)==ERR_OK);
 g_d2[2]=saved;g_p2_strict_routing=strict;
 g_vehicle_bridge=saved_bridge;
 REQUIRE(g_vehicle_bridge.vehicle.a3_shape_seen==
         saved_bridge.vehicle.a3_shape_seen);
 REQUIRE(g_vehicle_bridge.inspected_tx==saved_bridge.inspected_tx);
 puts("PASS P0 D2 CEM A3/A6 supersede stale B9 without invented replies");
}

/* Periodic TX previously bypassed the immediate WriteMsgs transport guards.
   Reject malformed schedules before installing a repeating transmitter, and
   keep the ordinary read-only periodic lab request working on both transports. */
static void test_periodic_tx_transport_parity(U32 dev){
 const U8 can_tester[]={0x02u,0x3Eu,0x00u,0,0,0,0,0};
 const U8 can_nine[]={0x03u,0x22u,0xF1u,0x90u,0,0,0,0,0};
 const U8 iso_long[]={0x3Eu,0u,0u,0u,0u,0u,0u,0u,0u};
 U32 can=0,iso=0,id=0xA5A5A5A5u,serial=g_periodic_counter;
 U32 i,prior_events,prior_observer,saved_strict=g_strict_j2534_filters;
 PASSTHRU_MSG m,rx;
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000u,&can)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,500000u,&iso)==ERR_OK);
 prior_events=backend_len;prior_observer=g_vehicle_bridge.inspected_tx;
 /* 1: ISO15765 cannot be scheduled on a raw CAN channel. */
 m=frame(PROTO_ISO15765,0x7E0u,iso_long,9u);
 REQUIRE(PassThruStartPeriodicMsg(can,&m,&id,15)==ERR_MSG_PROTOCOL_ID);
 REQUIRE(id==0xA5A5A5A5u&&g_periodic_counter==serial);
 /* 2: raw CAN cannot be scheduled on a reassembled ISO15765 channel. */
 m=frame(PROTO_CAN,0x7E0u,can_tester,8u);
 REQUIRE(PassThruStartPeriodicMsg(iso,&m,&id,15)==ERR_MSG_PROTOCOL_ID);
 REQUIRE(id==0xA5A5A5A5u&&g_periodic_counter==serial);
 /* 3: malformed nine-byte classic CAN must not be scheduled. */
 m=frame(PROTO_CAN,0x7E0u,can_nine,9u);
 REQUIRE(PassThruStartPeriodicMsg(can,&m,&id,15)==ERR_INVALID_MSG);
 /* 4: 30-bit and all-one CAN identifiers are never periodic routes. */
 m=frame(PROTO_CAN,0x20000000u,can_tester,8u);
 REQUIRE(PassThruStartPeriodicMsg(can,&m,&id,15)==ERR_INVALID_MSG);
 m=frame(PROTO_CAN,0xFFFFFFFFu,can_tester,8u);m.TxFlags=CAN_29BIT_ID;
 REQUIRE(PassThruStartPeriodicMsg(can,&m,&id,15)==ERR_INVALID_MSG);
 /* 5: physical 29-bit ID also bounds periodic ISO15765 requests. */
 m=frame(PROTO_ISO15765,0x20000000u,iso_long,9u);
 REQUIRE(PassThruStartPeriodicMsg(iso,&m,&id,15)==ERR_INVALID_MSG);
 /* 6: strict ISO extended-addressing remains unsupported via either API. */
 g_strict_j2534_filters=1u;
 m=frame(PROTO_ISO15765,0x7E0u,iso_long,9u);
 m.TxFlags=ISO15765_ADDR_TYPE;
 REQUIRE(PassThruStartPeriodicMsg(iso,&m,&id,15)==ERR_NOT_SUPPORTED);
 g_strict_j2534_filters=saved_strict;
 for(i=0;i<MAX_PERIODIC;i++){
  REQUIRE(!channel(can)->periodic[i].used);
  REQUIRE(!channel(iso)->periodic[i].used);
 }
 REQUIRE(id==0xA5A5A5A5u&&g_periodic_counter==serial);
 /* Invalid schedules never reach the backend or virtual CEM observer. */
 REQUIRE(backend_len==prior_events);
 REQUIRE(g_vehicle_bridge.inspected_tx==prior_observer);
 tick+=50;
 {U32 n=1;REQUIRE(PassThruReadMsgs(can,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0);}
 /* 7: exact maximum 29-bit CAN ID remains scheduleable. */
 m=frame(PROTO_CAN,0x1FFFFFFFu,can_tester,8u);
 REQUIRE(PassThruStartPeriodicMsg(can,&m,&id,15)==ERR_OK&&id==serial);
 REQUIRE(PassThruStopPeriodicMsg(can,id)==ERR_OK);
 /* 8: long reassembled ISO15765 payload remains scheduleable. */
 m=frame(PROTO_ISO15765,0x1FFFFFFFu,iso_long,9u);
 REQUIRE(PassThruStartPeriodicMsg(iso,&m,&id,15)==ERR_OK);
 REQUIRE(PassThruStopPeriodicMsg(iso,id)==ERR_OK);
 /* 9: ordinary 11-bit CAN tester-present periodic request still produces
    a bounded read-only response after the scheduled interval. */
 m=frame(PROTO_CAN,0x7E0u,can_tester,8u);
 REQUIRE(PassThruStartPeriodicMsg(can,&m,&id,15)==ERR_OK);
 tick+=16;rx=readmsg(can);
 REQUIRE(rx.ProtocolID==PROTO_CAN&&rx.Data[2]==0x07u&&rx.Data[3]==0xE8u);
 REQUIRE(rx.Data[4]==0x02u&&rx.Data[5]==0x7Eu&&rx.Data[6]==0x00u);
 REQUIRE(PassThruStopPeriodicMsg(can,id)==ERR_OK);
 /* 10: STOP really prevents further periodic ECU responses. */
 tick+=50;
 {U32 n=1;REQUIRE(PassThruReadMsgs(can,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0);}
 REQUIRE(PassThruDisconnect(iso)==ERR_OK);
 REQUIRE(PassThruDisconnect(can)==ERR_OK);
 puts("PASS J2534 periodic TX: shared protocol, CAN DLC/ID, ISO and valid repeat");
}

/* Periodic J2534 TX must produce one per-tick backend RID, just like a
   direct WriteMsgs request. Raw CAN Flow Control is NOT a new transaction.
   These are synthetic read-only requests; no actual SectorV GUI observed. */
static void test_periodic_d2_backend_evidence(U32 dev){
 D2_PROFILE saved=g_d2[2];
 p2_j2534_bridge saved_bridge=g_vehicle_bridge;
 U32 strict=g_p2_strict_routing,telemetry=g_backend_enabled,can=0,period=0,n;
 U32 saved_capture=capture_connect_log,log_offset=0;
 PASSTHRU_MSG m,rx;const char *start;U64 rid;
 const U8 fb[]={0xCBu,0x50u,0xB9u,0xFBu,0,0,0,0};
 const U8 a3[]={0xCFu,0x50u,0xA3u,0x02u,0x03u,0xA5u,0xA5u,0};
 const U8 a6[]={0xCFu,0x50u,0xA6u,0x1Au,0x04u,0x01u,0,0};
 const U8 tester[]={0x02u,0x3Eu,0x00u,0,0,0,0,0};
 const U8 vin_sf[]={0x03u,0x22u,0xF1u,0x90u,0,0,0,0};
 const U8 fc[]={0x30u,0,0,0,0,0,0,0};
 g_backend_enabled=1;g_p2_strict_routing=1;
 bytes_zero(&g_d2[2],sizeof(g_d2[2]));
 g_d2[2].target=0x50u;g_d2[2].subcommand=0xFBu;
 g_d2[2].response_id=0x01200003u;g_d2[2].baud=500000u;
 g_d2[2].frame_count=3u;
 g_d2[2].frame[0][0]=0x8Fu;g_d2[2].frame[0][1]=0x50u;
 g_d2[2].frame[0][2]=0xF9u;g_d2[2].frame[0][3]=0xFBu;
 g_d2[2].frame[1][0]=0x09u;g_d2[2].frame[2][0]=0x4Cu;
 REQUIRE(validate_d2_fixture(&g_d2[2]));
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000u,&can)==ERR_OK);

 /* 1: periodic B9FB gets a real backend RID and P0 probe category. */
 m=frame(PROTO_CAN,0x000FFFFEu,fb,8);
 REQUIRE(PassThruStartPeriodicMsg(can,&m,&period,100u)==ERR_OK);
 start=backend_lines+backend_len;
 log_offset=connect_log_len;capture_connect_log=1;
 tick+=101;rx=readmsg(can);REQUIRE(rx.Data[4]==0x8Fu);
 capture_connect_log=saved_capture;
 /* A periodic tick has its own 20-byte context, not a fabricated
    PassThruWriteMsgs event. The exact marker is consumed by Python audit. */
 REQUIRE(strstr(connect_log_lines+log_offset,
                "Periodic TX context channel/protocol/flags/baud/time-us (BE)")!=0);
 REQUIRE(strstr(connect_log_lines+log_offset,
                "J2534 periodic TX (read-only simulator)")!=0);
 REQUIRE(strstr(connect_log_lines+log_offset,"TX (app request)")==0);
 rid=last_tx_request(start);REQUIRE(rid!=0);
 REQUIRE(event_count_since(start,"\"kind\":\"tx_received\"")==1u);
 REQUIRE(strstr(start,"\"probe\":\"D2_50_B9FB\"")!=0);
 REQUIRE(terminal_count_for(start,rid)==0u);
 tick+=20;rx=readmsg(can);REQUIRE(rx.Data[4]==0x09u);
 tick+=20;rx=readmsg(can);REQUIRE(rx.Data[4]==0x4Cu);
 REQUIRE(terminal_for(start,rid,"none","responded")==1u);
 REQUIRE(terminal_count_for(start,rid)==1u);
 REQUIRE(PassThruStopPeriodicMsg(can,period)==ERR_OK);

 /* 2: unconfigured periodic B9FB is counted but remains silent. */
 g_d2[2].frame_count=0u;
 m=frame(PROTO_CAN,0x000FFFFEu,fb,8);
 REQUIRE(PassThruStartPeriodicMsg(can,&m,&period,50u)==ERR_OK);
 start=backend_lines+backend_len;tick+=51;n=1;
 REQUIRE(PassThruReadMsgs(can,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);
 rid=last_tx_request(start);REQUIRE(rid!=0);
 REQUIRE(terminal_for(start,rid,"missing_profile","no_response")==1u);
 REQUIRE(event_count_since(start,"\"kind\":\"rx_queued\"")==0u);
 REQUIRE(PassThruStopPeriodicMsg(can,period)==ERR_OK);

 /* 3: an unsupported periodic A3 is classified, never answered. */
 m=frame(PROTO_CAN,0x000FFFFEu,a3,8);
 REQUIRE(PassThruStartPeriodicMsg(can,&m,&period,50u)==ERR_OK);
 start=backend_lines+backend_len;tick+=51;n=1;
 REQUIRE(PassThruReadMsgs(can,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);
 rid=last_tx_request(start);REQUIRE(rid!=0);
 REQUIRE(strstr(start,"\"probe\":\"D2_50_A3\"")!=0);
 REQUIRE(terminal_for(start,rid,"unimplemented_probe","no_response")==1u);
 REQUIRE(PassThruStopPeriodicMsg(can,period)==ERR_OK);

 /* 4: an unsupported periodic A6 has its own trace, no positive E6. */
 m=frame(PROTO_CAN,0x000FFFFEu,a6,8);
 REQUIRE(PassThruStartPeriodicMsg(can,&m,&period,50u)==ERR_OK);
 start=backend_lines+backend_len;tick+=51;n=1;
 REQUIRE(PassThruReadMsgs(can,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);
 rid=last_tx_request(start);REQUIRE(rid!=0);
 REQUIRE(strstr(start,"\"probe\":\"D2_50_A6\"")!=0);
 REQUIRE(terminal_for(start,rid,"unimplemented_probe","no_response")==1u);
 REQUIRE(PassThruStopPeriodicMsg(can,period)==ERR_OK);

 /* 5: normal periodic tester-present receives one matching RX terminal. */
 m=frame(PROTO_CAN,0x7E0u,tester,8);
 REQUIRE(PassThruStartPeriodicMsg(can,&m,&period,50u)==ERR_OK);
 start=backend_lines+backend_len;tick+=51;
 rx=readmsg(can);REQUIRE(rx.Data[4]==0x02u&&rx.Data[5]==0x7Eu);
 rid=last_tx_request(start);REQUIRE(rid!=0);
 REQUIRE(terminal_for(start,rid,"none","responded")==1u);
 REQUIRE(terminal_count_for(start,rid)==1u);
 REQUIRE(PassThruStopPeriodicMsg(can,period)==ERR_OK);

 /* 6: periodic raw CAN FC can release pending CF, but never creates
    a separate tx_received/probe or terminal request record. */
 m=frame(PROTO_CAN,0x7E0u,vin_sf,8);send(can,&m);
 rx=readmsg(can);REQUIRE(rx.Data[4]==0x10u);
 m=frame(PROTO_CAN,0x7E0u,fc,8);
 REQUIRE(PassThruStartPeriodicMsg(can,&m,&period,100u)==ERR_OK);
 start=backend_lines+backend_len;tick+=101;
 rx=readmsg(can);REQUIRE(rx.Data[4]==0x21u);
 rx=readmsg(can);REQUIRE(rx.Data[4]==0x22u);
 REQUIRE(event_count_since(start,"\"kind\":\"tx_received\"")==0u);
 REQUIRE(event_count_since(start,"\"kind\":\"probe_classified\"")==0u);
 REQUIRE(PassThruStopPeriodicMsg(can,period)==ERR_OK);

 /* 7: stopped periodic requests cannot create telemetry after interval. */
 m=frame(PROTO_CAN,0x000FFFFEu,a3,8);
 REQUIRE(PassThruStartPeriodicMsg(can,&m,&period,50u)==ERR_OK);
 REQUIRE(PassThruStopPeriodicMsg(can,period)==ERR_OK);
 start=backend_lines+backend_len;tick+=51;n=1;
 REQUIRE(PassThruReadMsgs(can,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);
 REQUIRE(event_count_since(start,"\"kind\":\"tx_received\"")==0u);

 /* 8: explicit opt-out keeps ordinary periodic tester RX functional
    with no new backend JSONL request/terminal event whatsoever. */
 g_backend_enabled=0u;
 m=frame(PROTO_CAN,0x7E0u,tester,8);
 REQUIRE(PassThruStartPeriodicMsg(can,&m,&period,50u)==ERR_OK);
 {U32 prior=backend_len;tick+=51;
  rx=readmsg(can);
  REQUIRE(rx.Data[4]==0x02u&&rx.Data[5]==0x7Eu);
  REQUIRE(backend_len==prior);}
 REQUIRE(PassThruStopPeriodicMsg(can,period)==ERR_OK);
 REQUIRE(PassThruDisconnect(can)==ERR_OK);
 g_d2[2]=saved;g_p2_strict_routing=strict;
 g_backend_enabled=telemetry;g_vehicle_bridge=saved_bridge;
 puts("PASS P0 periodic J2534 D2 backend attribution and FC isolation");
}

/* Filter IDs have the same 29-bit physical CAN bound as TX frames.
   The 32-bit all-ones mask remains valid (it is a bit mask, not an ID).
   Every request in these checks is synthetic and read-only. */
static void test_filter_can_id_boundaries(U32 dev){
 U32 can=0,iso=0,id=0xABCDEF01u,first_id,prior=0;
 U32 saved_strict=g_strict_j2534_filters;
 PASSTHRU_MSG mask,pat,flow,m,rx;
 const U8 vin[]={0x22u,0xF1u,0x90u};
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000u,&can)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,500000u,&iso)==ERR_OK);
 prior=g_filter_counter;
 mask=frame(PROTO_CAN,0xFFFFFFFFu,0,0);
 pat=frame(PROTO_CAN,0x20000000u,0,0);
 /* 1: impossible 30-bit CAN pattern, even with a full 32-bit mask. */
 g_strict_j2534_filters=1u;
 REQUIRE(PassThruStartMsgFilter(can,1,&mask,&pat,0,&id)==ERR_INVALID_MSG);
 REQUIRE(id==0xABCDEF01u&&g_filter_counter==prior);
 REQUIRE(channel(can)->filters_count==0u);
 /* 2: same invalid CAN pattern is rejected in legacy relaxed mode. */
 g_strict_j2534_filters=0u;
 REQUIRE(PassThruStartMsgFilter(can,1,&mask,&pat,0,&id)==ERR_INVALID_MSG);
 REQUIRE(id==0xABCDEF01u&&g_filter_counter==prior);
 /* 3: ISO15765 cannot install an FC filter with 30-bit response ID. */
 g_strict_j2534_filters=1u;
 mask=frame(PROTO_ISO15765,0xFFFFFFFFu,0,0);
 pat=frame(PROTO_ISO15765,0x20000000u,0,0);
 flow=frame(PROTO_ISO15765,0x7E0u,0,0);
 REQUIRE(PassThruStartMsgFilter(iso,3,&mask,&pat,&flow,&id)==ERR_INVALID_MSG);
 REQUIRE(id==0xABCDEF01u&&g_filter_counter==prior);
 REQUIRE(channel(iso)->filters_count==0u);
 /* 4: a valid response pattern cannot hide an invalid FC request ID. */
 pat=frame(PROTO_ISO15765,0x7E8u,0,0);
 flow=frame(PROTO_ISO15765,0xFFFFFFFFu,0,0);
 REQUIRE(PassThruStartMsgFilter(iso,3,&mask,&pat,&flow,&id)==ERR_INVALID_MSG);
 REQUIRE(id==0xABCDEF01u&&g_filter_counter==prior);
 /* 5: exact maximum 29-bit ID remains valid for ordinary CAN filters. */
 mask=frame(PROTO_CAN,0xFFFFFFFFu,0,0);
 pat=frame(PROTO_CAN,0x1FFFFFFFu,0,0);
 REQUIRE(PassThruStartMsgFilter(can,1,&mask,&pat,0,&id)==ERR_OK);
 REQUIRE(id==prior&&channel(can)->filters_count==1u);
 REQUIRE(PassThruStopMsgFilter(can,id)==ERR_OK);
 /* 6: ISO15765 allows both response and flow-control IDs at 29-bit max
    (distinct values avoid intentional duplicate/overlap rejection). */
 mask=frame(PROTO_ISO15765,0xFFFFFFFFu,0,0);
 pat=frame(PROTO_ISO15765,0x1FFFFFFEu,0,0);
 flow=frame(PROTO_ISO15765,0x1FFFFFFFu,0,0);
 REQUIRE(PassThruStartMsgFilter(iso,3,&mask,&pat,&flow,&id)==ERR_OK);
 REQUIRE(channel(iso)->filters_count==1u);
 REQUIRE(PassThruStopMsgFilter(iso,id)==ERR_OK);
 /* 7: normal 11-bit ISO15765 filter still passes a UDS VIN request. */
 pat=frame(PROTO_ISO15765,0x7E8u,0,0);
 flow=frame(PROTO_ISO15765,0x7E0u,0,0);
 REQUIRE(PassThruStartMsgFilter(iso,3,&mask,&pat,&flow,&id)==ERR_OK);
 first_id=id;
 m=frame(PROTO_ISO15765,0x7E0u,vin,3u);
 send(iso,&m);
 rx=readmsg(iso);
 REQUIRE(rx.ProtocolID==PROTO_ISO15765);
 REQUIRE(rx.Data[4]==0x62u&&rx.Data[5]==0xF1u&&rx.Data[6]==0x90u);
 /* 8: an invalid pattern after successful installation cannot
    allocate a second filter or disrupt the first. */
 pat=frame(PROTO_ISO15765,0xE0000000u,0,0);
 REQUIRE(PassThruStartMsgFilter(iso,3,&mask,&pat,&flow,&id)==ERR_INVALID_MSG);
 REQUIRE(id==first_id&&channel(iso)->filters_count==1u);
 REQUIRE(PassThruStopMsgFilter(iso,first_id)==ERR_OK);
 REQUIRE(channel(iso)->filters_count==0u);
 REQUIRE(channel(can)->filters_count==0u);
 REQUIRE(PassThruDisconnect(iso)==ERR_OK);
 REQUIRE(PassThruDisconnect(can)==ERR_OK);
 g_strict_j2534_filters=saved_strict;
 puts("PASS J2534 filters: physical CAN ID bounds, full-width masks and ISO FC");
}

/* Eight source-backed host regressions for J2534 lifecycle linearization.
   The lock hook models an interleaving exactly between the former unlocked
   g_open precheck and acquisition of g_lock. No OEM or GUI claims. */
static void test_j2534_lifecycle_lock_races(void){
 U32 dev=0,ch=0,untouched=0xC0DEu;
 REQUIRE(g_open==0u && g_lock==0);
 /* 1: null Open never changes global device state. */
 REQUIRE(PassThruOpen(0,0)==ERR_NULL_PARAMETER);
 REQUIRE(g_open==0u && channel(1)==0);
 /* 2: re-opening an already opened device cannot drop a live channel. */
 REQUIRE(PassThruOpen(0,&dev)==ERR_OK && dev==1u);
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000u,&ch)==ERR_OK);
 REQUIRE(channel(ch)!=0);
 REQUIRE(PassThruOpen(0,&untouched)==ERR_DEVICE_IN_USE);
 REQUIRE(channel(ch)!=0 && g_open==1u);
 /* 3: wrong Close handle never tears down the active channel. */
 REQUIRE(PassThruClose(dev+1u)==ERR_INVALID_DEVICE_ID);
 REQUIRE(channel(ch)!=0 && g_open==1u);
 /* 4: Close makes stale Connect handles invalid and leaves its output alone. */
 REQUIRE(PassThruClose(dev)==ERR_OK);
 ch=0xC0DEu;
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000u,&ch)==ERR_INVALID_DEVICE_ID);
 REQUIRE(ch==0xC0DEu && g_open==0u && channel(1)==0);
 /* 5: concurrent first Open wins just before our own Open takes the lock. */
 lifecycle_race_on_next_lock=2u;
 REQUIRE(PassThruOpen(0,&untouched)==ERR_DEVICE_IN_USE);
 REQUIRE(lifecycle_race_on_next_lock==0u && g_open==1u);
 REQUIRE(channel(1)!=0 && channel(1)->baud==500000u);
 REQUIRE(PassThruClose(dev)==ERR_OK);
 /* 6: another thread closing before our Connect takes the lock prevents
    creation of a channel on an already-closed J2534 device. */
 REQUIRE(PassThruOpen(0,&dev)==ERR_OK);
 lifecycle_race_on_next_lock=1u;ch=0xC0DEu;
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000u,&ch)==ERR_INVALID_DEVICE_ID);
 REQUIRE(lifecycle_race_on_next_lock==0u && g_open==0u);
 REQUIRE(channel(1)==0 && ch==0xC0DEu);
 /* 7: another Close ahead of our Close must not be reported as success. */
 REQUIRE(PassThruOpen(0,&dev)==ERR_OK);
 lifecycle_race_on_next_lock=1u;
 REQUIRE(PassThruClose(dev)==ERR_INVALID_DEVICE_ID);
 REQUIRE(lifecycle_race_on_next_lock==0u && g_open==0u);
 /* 8: normal Open/Connect/Disconnect/Close survives all interrupted races. */
 REQUIRE(PassThruOpen(0,&dev)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000u,&ch)==ERR_OK);
 REQUIRE(channel(ch)!=0);
 REQUIRE(PassThruDisconnect(ch)==ERR_OK);
 REQUIRE(PassThruClose(dev)==ERR_OK && g_open==0u);
 puts("PASS P0 J2534 lifecycle: atomic Open/Close/Connect and lock-entry races");
}

int main(){
 U32 dev=0,cid=0,batt=0,n=0;
 test_j2534_lifecycle_lock_races();
 REQUIRE(PassThruOpen(0,&dev)==ERR_OK);REQUIRE(dev==1);
 test_zero_baud_guard(dev);
 test_d2_replay_isolation_on_set_config(dev);
 test_write_transport_boundaries(dev);
 test_can_id_range_guard(dev);
 test_periodic_tx_transport_parity(dev);
 test_periodic_d2_backend_evidence(dev);
 test_filter_can_id_boundaries(dev);
 test_known_b9fb_13frame_final_marker();
 test_d2_unknown_target_supersession(dev);
 test_d2_a3_a6_supersession(dev);
 test_vmware_route_evidence(dev);
 test_p2_informer_observer(dev);
 test_p3tool_j2534_preflight(dev);
 REQUIRE(PassThruIoctl(dev,IO_READ_VBATT,0,&batt)==ERR_OK);REQUIRE(batt==12500);
 REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,500000,&cid)==ERR_OK);
 const U8 vin_req[]={0x22,0xF1,0x90};PASSTHRU_MSG m=frame(PROTO_ISO15765,0x7E0,vin_req,3);
 /* J2534 NumMsgs 128, larger than MAX_QUEUE 64, is legal. */
 PASSTHRU_MSG *batch=(PASSTHRU_MSG*)calloc(128,sizeof(*batch));REQUIRE(batch!=0);
 n=128;REQUIRE(PassThruReadMsgs(cid,batch,&n,0)==ERR_BUFFER_EMPTY && n==0);
 n=128;REQUIRE(PassThruReadMsgs(cid,batch,&n,3)==ERR_TIMEOUT && n==0);
 tick=1234;send(cid,&m);
 n=128;REQUIRE(PassThruReadMsgs(cid,batch,&n,0)==ERR_OK && n==1);
 PASSTHRU_MSG r=batch[0];free(batch);REQUIRE(r.DataSize==24);REQUIRE(r.Data[4]==0x62&&r.Data[5]==0xF1&&r.Data[6]==0x90);
 REQUIRE(r.ExtraDataIndex==r.DataSize);REQUIRE(r.Timestamp==1234000u);
 REQUIRE(memcmp(r.Data+7,"YV1CZ0002A0000001",17)==0);
 const U8 bad_req[]={0x27,0x01};m=frame(PROTO_ISO15765,0x7E0,bad_req,2);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.DataSize==7&&r.Data[4]==0x7F&&r.Data[5]==0x27&&r.Data[6]==0x33);
 SCONFIG c={1,0};SCONFIG_LIST cfg={1,&c};REQUIRE(PassThruIoctl(cid,IO_GET_CONFIG,&cfg,0)==ERR_OK);REQUIRE(c.Value==500000);
 const U8 part_req[]={0x22,0xF1,0x87};m=frame(PROTO_ISO15765,0x7E0,part_req,3);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.Data[4]==0x62&&r.Data[5]==0xF1&&r.Data[6]==0x87);
 REQUIRE(memcmp(r.Data+7,"VIRTUAL-ECU",11)==0);
 const U8 denied_write[]={0x2E,0xF1,0x90,0x00};m=frame(PROTO_ISO15765,0x7E0,denied_write,4);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.Data[4]==0x7F&&r.Data[5]==0x2E&&r.Data[6]==0x33);
 /* The P3 CEM address seen in SectorV's log must return a UDS response. */
 const U8 cem_req[]={0x22,0xF1,0x14};m=frame(PROTO_ISO15765,0x726,cem_req,3);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.Data[2]==0x07&&r.Data[3]==0x2E);
 REQUIRE(r.DataSize==24);
 REQUIRE(r.Data[4]==0x62&&r.Data[5]==0xF1&&r.Data[6]==0x14);
 REQUIRE(memcmp(r.Data+7,"YV1CZ0002A0000001",17)==0);
 /* User-supplied, read-only DID fixtures must echo exactly, not be invented. */
 const U8 b0req[]={0x22,0xF1,0xB0};m=frame(PROTO_ISO15765,0x726,b0req,3);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.DataSize==14 && r.Data[4]==0x62 && r.Data[5]==0xF1 && r.Data[6]==0xB0);
 REQUIRE(memcmp(r.Data+7,"SIM-CEM",7)==0);
 const U8 a3req[]={0x22,0xF1,0xA3};m=frame(PROTO_ISO15765,0x726,a3req,3);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.DataSize==14 && r.Data[4]==0x62 && r.Data[5]==0xF1 && r.Data[6]==0xA3);
 REQUIRE(memcmp(r.Data+7,"SIM-1.0",7)==0);
 /* Additional diagnostic DID replays are opt-in, per-ECU and read-only.
    F18C is a laboratory test marker, not a real Volvo module identifier. */
 const U8 extra_req[]={0x22,0xF1,0x8C};m=frame(PROTO_ISO15765,0x726,extra_req,3);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.DataSize==13 && r.Data[4]==0x62 && r.Data[5]==0xF1 && r.Data[6]==0x8C);
 REQUIRE(memcmp(r.Data+7,"LAB-ID",6)==0);
 m=frame(PROTO_ISO15765,0x7E0,extra_req,3);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.DataSize==7 && r.Data[4]==0x7F && r.Data[5]==0x22 && r.Data[6]==0x31);
 /* F106 A/B fixture: full 142-byte read-only config must remain intact. */
 const U8 f106_req[]={0x22,0xF1,0x06};m=frame(PROTO_ISO15765,0x726,f106_req,3);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.DataSize==149 && r.Data[4]==0x62 && r.Data[5]==0xF1 && r.Data[6]==0x06);
 for(U32 z=0;z<142;z++)REQUIRE(r.Data[7+z]==(U8)z);
 /* ECM without opt-in fixtures still returns 7F 22 31. */
 m=frame(PROTO_ISO15765,0x7E0,b0req,3);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.DataSize==7 && r.Data[4]==0x7F && r.Data[5]==0x22 && r.Data[6]==0x31);
 REQUIRE(PassThruDisconnect(cid)==ERR_OK);
 REQUIRE(PassThruConnect(dev,PROTO_CAN,CAN_29BIT_ID,500000,&cid)==ERR_OK);
 const U8 sf[]={0x03,0x22,0xF1,0x90,0,0,0,0};m=frame(PROTO_CAN,0x7E0,sf,8);send(cid,&m);r=readmsg(cid);
 REQUIRE((r.Data[4]&0xF0)==0x10&&r.Data[5]==20);
 const U8 fc[]={0x30,0,0,0,0,0,0,0};m=frame(PROTO_CAN,0x7E0,fc,8);send(cid,&m);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x21);r=readmsg(cid);REQUIRE(r.Data[4]==0x22);
 /* Exact P3 single-frame CAN request observed in the SectorV trace. */
 const U8 cem_sf[]={0x03,0x22,0xF1,0x14,0,0,0,0};
 m=frame(PROTO_CAN,0x726,cem_sf,8);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.Data[2]==0x07 && r.Data[3]==0x2E);
 REQUIRE(r.Data[4]==0x10 && r.Data[5]==0x14);
 REQUIRE(r.Data[6]==0x62 && r.Data[7]==0xF1 && r.Data[8]==0x14);
 /* Raw CAN transport must not release Consecutive Frames before FC. */
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 m=frame(PROTO_CAN,0x726,fc,8);send(cid,&m);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x21);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x22);
 /* ISO-TP FC must match the ECU request ID; obey nonzero block size. */
 m=frame(PROTO_CAN,0x726,cem_sf,8);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.Data[4]==0x10); /* FF */
 const U8 fc1[]={0x30,0x01,0,0,0,0,0,0};
 m=frame(PROTO_CAN,0x7E0,fc1,8);send(cid,&m);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 m=frame(PROTO_CAN,0x726,fc1,8);send(cid,&m);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x21);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 m=frame(PROTO_CAN,0x726,fc1,8);send(cid,&m);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x22);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 /* WAIT does not release CFs; OVERFLOW cancels the transfer. */
 m=frame(PROTO_CAN,0x726,cem_sf,8);send(cid,&m);r=readmsg(cid);
 const U8 fcwait[]={0x31,0,0,0,0,0,0,0};
 m=frame(PROTO_CAN,0x726,fcwait,8);send(cid,&m);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 const U8 fcover[]={0x32,0,0,0,0,0,0,0};
 m=frame(PROTO_CAN,0x726,fcover,8);send(cid,&m);
 m=frame(PROTO_CAN,0x726,fc,8);send(cid,&m);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 /* Raw CAN multi-frame F106: initial FF plus 20 CF on matching FC. */
 const U8 f106_sf[]={0x03,0x22,0xF1,0x06,0,0,0,0};
 m=frame(PROTO_CAN,0x726,f106_sf,8);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.Data[4]==0x10 && r.Data[5]==0x91 && r.Data[6]==0x62 && r.Data[7]==0xF1 && r.Data[8]==0x06);
 REQUIRE(channel(cid)->pending_len==145 && channel(cid)->pending_pos==6);
 m=frame(PROTO_CAN,0x726,fc,8);send(cid,&m);
 U8 assembled[145];memcpy(assembled,r.Data+6,6);U32 offset=6;
 for(U32 z=0;z<20;z++){
   r=readmsg(cid);REQUIRE((r.Data[4]&0xF0)==0x20);
   REQUIRE((r.Data[4]&15)==((z+1)&15));
   U32 bytes=145-offset;if(bytes>7)bytes=7;
   memcpy(assembled+offset,r.Data+5,bytes);offset+=bytes;
 }
 REQUIRE(offset==145 && channel(cid)->pending_len==0);
 REQUIRE(assembled[0]==0x62&&assembled[1]==0xF1&&assembled[2]==0x06);
 for(U32 z=0;z<142;z++)REQUIRE(assembled[3+z]==(U8)z);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 /* F02: a granted ISO-TP burst resumes only after RX backpressure eases.
    All frames and bus occupancy in this test are synthetic. */
 {
  U32 bp_cid=0,other_cid=0,got=0;
  CHANNEL *bp;
  PASSTHRU_MSG *batch=(PASSTHRU_MSG*)calloc(128,sizeof(*batch));
  REQUIRE(batch!=0);
  const U8 bs2[]={0x30,0x02,0,0,0,0,0,0};
  const U8 wait_fc[]={0x31,0,0,0,0,0,0,0};
  const U8 overflow_fc[]={0x32,0,0,0,0,0,0,0};
  const U8 tester[]={0x02,0x3E,0x00,0,0,0,0,0};
  /* 1+2: 64-entry FIFO before FC; BS=0 must preserve the grant.
     One ReadMsgs(NumMsgs=128) drains 64 old frames plus all 20 CFs,
     without corrupting the existing 142-byte F106 read-only fixture. */
  REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&bp_cid)==ERR_OK);
  bp=channel(bp_cid);
  m=frame(PROTO_CAN,0x726,f106_sf,8);send(bp_cid,&m);
  REQUIRE(bp->count==1 && bp->pending_len==145 && bp->pending_pos==6);
  fill_lab_rx(bp,MAX_QUEUE-1);
  REQUIRE(bp->count==MAX_QUEUE && !bp->pending_cf_active);
  m=frame(PROTO_CAN,0x726,fc,8);send(bp_cid,&m);
  REQUIRE(bp->pending_cf_active && bp->pending_pos==6 && bp->count==MAX_QUEUE);
  got=128;REQUIRE(PassThruReadMsgs(bp_cid,batch,&got,0)==ERR_OK && got==84);
  REQUIRE(batch[0].Data[4]==0x10 && batch[0].Data[5]==0x91);
  for(U32 z=1;z<MAX_QUEUE;z++)REQUIRE(batch[z].Data[2]==0x05 && batch[z].Data[3]==0x55);
  U8 restored[145];memcpy(restored,batch[0].Data+6,6);U32 pos=6;
  for(U32 z=0;z<20;z++){
    const PASSTHRU_MSG *part=&batch[MAX_QUEUE+z];
    require_lab_cf(part,z+1);
    U32 remain=145-pos;if(remain>7)remain=7;
    memcpy(restored+pos,part->Data+5,remain);pos+=remain;
  }
  REQUIRE(pos==145 && restored[0]==0x62 && restored[1]==0xF1 && restored[2]==0x06);
  for(U32 z=0;z<142;z++)REQUIRE(restored[3+z]==(U8)z);
  REQUIRE(bp->count==0 && bp->pending_len==0 && !bp->pending_cf_active);
  REQUIRE(PassThruDisconnect(bp_cid)==ERR_OK);
  /* 3+4: BS=2 when full grants exactly two CFs after draining;
     each subsequent new grant is necessary, even after FIFO empties. */
  REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&bp_cid)==ERR_OK);
  bp=channel(bp_cid);
  m=frame(PROTO_CAN,0x726,f106_sf,8);send(bp_cid,&m);fill_lab_rx(bp,MAX_QUEUE-1);
  m=frame(PROTO_CAN,0x726,bs2,8);send(bp_cid,&m);
  REQUIRE(bp->pending_cf_active && bp->pending_cf_credit==2 && bp->pending_pos==6);
  got=128;REQUIRE(PassThruReadMsgs(bp_cid,batch,&got,0)==ERR_OK && got==66);
  require_lab_cf(&batch[64],1);require_lab_cf(&batch[65],2);
  REQUIRE(bp->pending_len==145 && bp->pending_pos==20);
  REQUIRE(!bp->pending_cf_active && bp->pending_cf_credit==0);
  got=128;REQUIRE(PassThruReadMsgs(bp_cid,batch,&got,0)==ERR_BUFFER_EMPTY && got==0);
  m=frame(PROTO_CAN,0x726,fc1,8);send(bp_cid,&m);
  got=128;REQUIRE(PassThruReadMsgs(bp_cid,batch,&got,0)==ERR_OK && got==1);
  require_lab_cf(&batch[0],3);
  REQUIRE(!bp->pending_cf_active && bp->pending_pos==27);
  m=frame(PROTO_CAN,0x726,fc,8);send(bp_cid,&m);
  got=128;REQUIRE(PassThruReadMsgs(bp_cid,batch,&got,0)==ERR_OK && got==17);
  for(U32 z=0;z<17;z++)require_lab_cf(&batch[z],z+4);
  REQUIRE(bp->pending_len==0 && !bp->pending_cf_active);
  REQUIRE(PassThruDisconnect(bp_cid)==ERR_OK);
  /* 5: a physical FC for a different ECU must not release a grant. */
  REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&bp_cid)==ERR_OK);
  bp=channel(bp_cid);
  m=frame(PROTO_CAN,0x726,f106_sf,8);send(bp_cid,&m);fill_lab_rx(bp,MAX_QUEUE-1);
  m=frame(PROTO_CAN,0x7E0,fc,8);send(bp_cid,&m);
  REQUIRE(!bp->pending_cf_active && bp->pending_pos==6);
  got=128;REQUIRE(PassThruReadMsgs(bp_cid,batch,&got,0)==ERR_OK && got==64);
  REQUIRE(bp->pending_len==145 && bp->pending_pos==6);
  m=frame(PROTO_CAN,0x726,fc,8);send(bp_cid,&m);
  got=128;REQUIRE(PassThruReadMsgs(bp_cid,batch,&got,0)==ERR_OK && got==20);
  for(U32 z=0;z<20;z++)require_lab_cf(&batch[z],z+1);
  REQUIRE(PassThruDisconnect(bp_cid)==ERR_OK);
  /* 6: WAIT and then OVERFLOW cancel a stored CTS grant without
     emitting any CF after a queued FF is read. */
  REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&bp_cid)==ERR_OK);
  bp=channel(bp_cid);
  m=frame(PROTO_CAN,0x726,f106_sf,8);send(bp_cid,&m);fill_lab_rx(bp,MAX_QUEUE-1);
  m=frame(PROTO_CAN,0x726,wait_fc,8);send(bp_cid,&m);
  REQUIRE(!bp->pending_cf_active);
  m=frame(PROTO_CAN,0x726,fc,8);send(bp_cid,&m);
  REQUIRE(bp->pending_cf_active && bp->pending_pos==6);
  m=frame(PROTO_CAN,0x726,wait_fc,8);send(bp_cid,&m);
  REQUIRE(!bp->pending_cf_active && bp->pending_cf_credit==0);
  m=frame(PROTO_CAN,0x726,fc,8);send(bp_cid,&m);
  REQUIRE(bp->pending_cf_active && bp->pending_pos==6);
  m=frame(PROTO_CAN,0x726,overflow_fc,8);send(bp_cid,&m);
  REQUIRE(!bp->pending_cf_active && bp->pending_len==0);
  got=128;REQUIRE(PassThruReadMsgs(bp_cid,batch,&got,0)==ERR_OK && got==64);
  REQUIRE(batch[0].Data[4]==0x10 && batch[63].Data[3]==0x55);
  got=1;REQUIRE(PassThruReadMsgs(bp_cid,batch,&got,0)==ERR_BUFFER_EMPTY && got==0);
  REQUIRE(PassThruDisconnect(bp_cid)==ERR_OK);
  /* 7: a fresh response must cancel a stored grant for superseded
     transfer, and must not leak old CFs on the next ReadMsgs call. */
  REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&bp_cid)==ERR_OK);
  bp=channel(bp_cid);
  m=frame(PROTO_CAN,0x726,f106_sf,8);send(bp_cid,&m);fill_lab_rx(bp,MAX_QUEUE-1);
  m=frame(PROTO_CAN,0x726,fc,8);send(bp_cid,&m);
  REQUIRE(bp->pending_cf_active);
  m=frame(PROTO_CAN,0x726,tester,8);send(bp_cid,&m);
  REQUIRE(!bp->pending_cf_active && bp->pending_len==0);
  got=128;REQUIRE(PassThruReadMsgs(bp_cid,batch,&got,0)==ERR_OK && got==64);
  got=1;REQUIRE(PassThruReadMsgs(bp_cid,batch,&got,0)==ERR_BUFFER_EMPTY && got==0);
  REQUIRE(PassThruDisconnect(bp_cid)==ERR_OK);
  /* 8: RX drain on another ChannelID does not consume the pending
     grant or alter the first channel's CF sequence. */
  REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&bp_cid)==ERR_OK);
  REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&other_cid)==ERR_OK);
  bp=channel(bp_cid);
  m=frame(PROTO_CAN,0x726,f106_sf,8);send(bp_cid,&m);fill_lab_rx(bp,MAX_QUEUE-1);
  m=frame(PROTO_CAN,0x726,fc,8);send(bp_cid,&m);
  m=frame(PROTO_CAN,0x726,tester,8);send(other_cid,&m);
  got=128;REQUIRE(PassThruReadMsgs(other_cid,batch,&got,0)==ERR_OK && got==1);
  REQUIRE(batch[0].Data[4]==0x02 && batch[0].Data[5]==0x7E);
  REQUIRE(bp->count==MAX_QUEUE && bp->pending_pos==6 && bp->pending_cf_active);
  got=128;REQUIRE(PassThruReadMsgs(bp_cid,batch,&got,0)==ERR_OK && got==84);
  for(U32 z=0;z<20;z++)require_lab_cf(&batch[64+z],z+1);
  REQUIRE(bp->pending_len==0 && !bp->pending_cf_active);
  REQUIRE(PassThruDisconnect(other_cid)==ERR_OK);
  REQUIRE(PassThruDisconnect(bp_cid)==ERR_OK);
  free(batch);
 }
 /* F02/STmin integration: a drained full RX queue must preserve the
    5-ms schedule, even when one ReadMsgs call requests 128 entries. */
 {
  U32 bp_cid=0,got=0,last_timestamp=0;
  PASSTHRU_MSG *batch=(PASSTHRU_MSG*)calloc(128,sizeof(PASSTHRU_MSG));
  const U8 fc5ms[]={0x30,0x00,0x05,0,0,0,0,0};
  REQUIRE(batch!=0);
  REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&bp_cid)==ERR_OK);
  CHANNEL *bp=channel(bp_cid);
  m=frame(PROTO_CAN,0x726,f106_sf,8);send(bp_cid,&m);
  fill_lab_rx(bp,MAX_QUEUE-1);
  m=frame(PROTO_CAN,0x726,fc5ms,8);send(bp_cid,&m);
  REQUIRE(bp->pending_cf_active && bp->pending_pos==6);
  got=128;REQUIRE(PassThruReadMsgs(bp_cid,batch,&got,0)==ERR_OK && got==65);
  require_lab_cf(&batch[64],1);
  REQUIRE(bp->pending_len==0 && bp->count==19);
  last_timestamp=batch[64].Timestamp;
  for(U32 z=2;z<=20;z++){
   got=128;REQUIRE(PassThruReadMsgs(bp_cid,batch,&got,0)==ERR_BUFFER_EMPTY && got==0);
   advance_test_us(5000);
   got=128;REQUIRE(PassThruReadMsgs(bp_cid,batch,&got,0)==ERR_OK && got==1);
   require_lab_cf(&batch[0],z);
   REQUIRE((U32)(batch[0].Timestamp-last_timestamp)>=5000u);
   last_timestamp=batch[0].Timestamp;
  }
  REQUIRE(bp->count==0 && bp->pending_len==0 && !bp->pending_cf_active);
  REQUIRE(PassThruDisconnect(bp_cid)==ERR_OK);
  free(batch);
 }
 /* Issue #4: deterministic allowlisted metadata, not synthetic ECU
    capability. These groups never expose a VIN or raw data in JSONL. */
 {
  const U8 p40[]={0xCB,0x40,0xB9,0xFB,0,0,0,0};
  const U8 p50[]={0xCB,0x50,0xB9,0xF0,0,0,0,0};
  const U8 pfc[]={0xCB,0x40,0xB9,0xFC,0,0,0,0};
  const U8 pa3[]={0xCF,0x50,0xA3,0x02,0x03,0xA5,0xA5,0};
  const U8 pa6[]={0xCF,0x50,0xA6,0x1A,0x04,0x01,0,0};
  const U8 p3sf[]={0x03,0x22,0xF1,0x14,0,0,0,0};
  const U8 p3iso[]={0x22,0xF1,0xB0};
  const U8 fcframe[]={0x30,0,0,0,0,0,0,0};
  const U8 uunknown[]={0x03,0x22,0xF1,0x23,0,0,0,0};
  const char *label;
  /* 1: two D2 routes with different vehicle/module-info opcodes. */
  m=frame(PROTO_CAN,0xFFFFE,p40,8);
  label=backend_probe_name(channel(cid),&m);
  REQUIRE(label && strcmp(label,"D2_40_B9FB")==0);
  m=frame(PROTO_CAN,0xFFFFE,p50,8);
  label=backend_probe_name(channel(cid),&m);
  REQUIRE(label && strcmp(label,"D2_50_B9F0")==0);
  /* 2: B9FC must remain distinct from B9FB. */
  m=frame(PROTO_CAN,0xFFFFE,pfc,8);
  label=backend_probe_name(channel(cid),&m);
  REQUIRE(label && strcmp(label,"D2_40_B9FC")==0);
  /* 3: A3 and A6 are observed request shapes, never positive replies. */
  m=frame(PROTO_CAN,0xFFFFE,pa3,8);
  label=backend_probe_name(channel(cid),&m);
  REQUIRE(label && strcmp(label,"D2_50_A3")==0);
  m=frame(PROTO_CAN,0xFFFFE,pa6,8);
  label=backend_probe_name(channel(cid),&m);
  REQUIRE(label && strcmp(label,"D2_50_A6")==0);
  /* 4: both P3 addressing types are independently categorized. */
  m=frame(PROTO_CAN,0x726,p3sf,8);
  label=backend_probe_name(channel(cid),&m);
  REQUIRE(label && strcmp(label,"P3_726_F114")==0);
  m=frame(PROTO_CAN,0x18DA50F1,p3sf,8);
  label=backend_probe_name(channel(cid),&m);
  REQUIRE(label && strcmp(label,"P3_29_F114")==0);
  /* 5: ISO15765 provides UDS without CAN Single Frame PCI. */
  {
   U32 iso=0;
   REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,500000,&iso)==ERR_OK);
   m=frame(PROTO_ISO15765,0x726,p3iso,3);
   label=backend_probe_name(channel(iso),&m);
   REQUIRE(label && strcmp(label,"P3_726_F1B0")==0);
   /* 5b: P3 multi-DID, trailing bytes and truncated requests must remain
      unattributed, since a one-DID label would be misleading. */
   {
    const U8 multi[]={0x22,0xF1,0xB0,0xF1,0x14};
    const U8 trailing[]={0x22,0xF1,0xB0,0x00};
    m=frame(PROTO_ISO15765,0x726,multi,5);
    REQUIRE(backend_probe_name(channel(iso),&m)==0);
    m=frame(PROTO_ISO15765,0x18DA50F1,multi,5);
    REQUIRE(backend_probe_name(channel(iso),&m)==0);
    m=frame(PROTO_ISO15765,0x726,trailing,4);
    REQUIRE(backend_probe_name(channel(iso),&m)==0);
    m=frame(PROTO_ISO15765,0x726,p3iso,2);
    REQUIRE(backend_probe_name(channel(iso),&m)==0);
   }
   REQUIRE(PassThruDisconnect(iso)==ERR_OK);
  }
  /* 6: flow control, unsupported DID and arbitrary CAN are never tagged. */
  m=frame(PROTO_CAN,0x726,fcframe,8);
  REQUIRE(backend_probe_name(channel(cid),&m)==0);
  m=frame(PROTO_CAN,0x726,uunknown,8);
  REQUIRE(backend_probe_name(channel(cid),&m)==0);
  m=frame(PROTO_CAN,0x555,pa3,8);
  REQUIRE(backend_probe_name(channel(cid),&m)==0);
  /* 7: malformed short P3/ D2 shapes cannot earn a known service tag. */
  m=frame(PROTO_CAN,0x726,p3sf,2);
  REQUIRE(backend_probe_name(channel(cid),&m)==0);
  m=frame(PROTO_CAN,0xFFFFE,p40,2);
  REQUIRE(backend_probe_name(channel(cid),&m)==0);
  /* 8: real request produces one metadata-only probe event, no ECU reply. */
  const char *begin=backend_lines+backend_len;
  m=frame(PROTO_CAN,0xFFFFE,pa3,8);send(cid,&m);
  REQUIRE(event_count_since(begin,"\"kind\":\"probe_classified\"")==1);
  REQUIRE(strstr(begin,"\"probe\":\"D2_50_A3\"")!=NULL);
  REQUIRE(strstr(begin,"\"data\"")==NULL);
  n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 }
 /* Observer classifies A3, but never fabricates a positive E3 reply. */
 const U8 a3_wire[]={0xCF,0x50,0xA3,0x02,0x03,0xA5,0xA5,0x00};
 m=frame(PROTO_CAN,0x000FFFFE,a3_wire,8);send(cid,&m);
 REQUIRE(g_vehicle_bridge.inspected_tx>0);
 REQUIRE(g_vehicle_bridge.vehicle.a3_shape_seen==2);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 /* P2/P1 29-bit D2 B9 FB read-only replay fixture. */
 REQUIRE(g_d2[0].frame_count==1);
 const U8 synthetic[]={0xCC,0x40,0x7F,0xB9,0x31,0,0,0};
 const U8 d2req[]={0xCB,0x40,0xB9,0xFB,0,0,0,0};
 m=frame(PROTO_CAN,0x000FFFFE,d2req,8);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.Data[0]==0x00&&r.Data[1]==0x80&&r.Data[2]==0x00&&r.Data[3]==0x03);
 REQUIRE((r.RxStatus&CAN_29BIT_ID)==CAN_29BIT_ID);
 REQUIRE(memcmp(r.Data+4,synthetic,8)==0);
 /* Published D2 B9 F0 example uses response ID 0x01000003, three frames.
    Frames are paced; they must NOT arrive all at once. */
 REQUIRE(g_d2[3].frame_count==3);
 REQUIRE(g_vehicle_bridge.vehicle.a3_shape_seen==2);
 REQUIRE(g_vehicle_bridge.vehicle.b9fb_seen>=1);
 const U8 d2f0[]={0xCB,0x50,0xB9,0xF0,0,0,0,0};
 m=frame(PROTO_CAN,0x000FFFFE,d2f0,8);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.Data[0]==0x01 && r.Data[1]==0x00 && r.Data[2]==0x00 && r.Data[3]==0x03);
 REQUIRE(r.Data[4]==0x8F && r.Data[5]==0x50 && r.Data[6]==0xF9 && r.Data[7]==0xF0);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,30)==ERR_OK);REQUIRE(r.Data[4]==0x09);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,30)==ERR_OK);REQUIRE(r.Data[4]==0x4C);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 /* Issue #4: A3/A6 are known CEM probes with NO validated response
    implementation. Nine read-only routing checks. The telemetry must not
    mistake them for arbitrary CAN IDs, missing B9 replay fixtures, or real
    positive acknowledgments. */
 {
  static const struct {
   U32 id;U8 prefix,target,opcode;int recognized;
  } cases[]={
   {0x000FFFFEu,0xCF,0x40,0xA3,1}, /* 1: CEM 40 A3 */
   {0x000FFFFEu,0xCF,0x50,0xA3,1}, /* 2: CEM 50 A3 */
   {0x000FFFFEu,0xCF,0x40,0xA6,1}, /* 3: CEM 40 A6 */
   {0x000FFFFEu,0xCF,0x50,0xA6,1}, /* 4: CEM 50 A6 */
   {0x000FFFFEu,0xCA,0x50,0xA6,1}, /* 5: recorded alternative preamble */
   {0x000FFFFEu,0xCB,0x40,0xA3,1}, /* 6: other known preamble */
   {0x000FFFFEu,0xCF,0x60,0xA3,0}, /* 7: unknown target */
   {0x000FFFFEu,0xCF,0x50,0xA7,0}, /* 8: unknown opcode */
   {0x00000555u,0xCF,0x50,0xA3,0}, /* 9: unrelated CAN identifier */
  };
  U32 z;
  for(z=0;z<sizeof(cases)/sizeof(cases[0]);z++){
   U8 request[]={0,0,0,0,0,0,0,0};
   const char *start=backend_lines+backend_len;
   U64 request_id;
   request[0]=cases[z].prefix;request[1]=cases[z].target;
   request[2]=cases[z].opcode;
   m=frame(PROTO_CAN,cases[z].id,request,8);
   REQUIRE((backend_probe_name(channel(cid),&m)!=0)==cases[z].recognized);
   send(cid,&m);request_id=last_tx_request(start);
   REQUIRE(request_id!=0);
   if(cases[z].recognized){
    REQUIRE(terminal_for(start,request_id,"unimplemented_probe","no_response")==1);
    REQUIRE(strstr(start,"\"route\":\"CEM\"")!=NULL);
   }else{
    REQUIRE(terminal_for(start,request_id,"unhandled_request","no_response")==1);
    REQUIRE(strstr(start,"\"route\":\"UNHANDLED\"")!=NULL);
   }
   REQUIRE(terminal_count_for(start,request_id)==1);
   REQUIRE(strstr(start,"\"kind\":\"response_generated\"")==NULL);
   n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY && n==0);
  }
 }
 /* Eight groups: synthetic request shapes only; no ECU/security responses. */
 {
  U32 prefix,target,service,length,group;
  for(group=0;group<8;group++){
   for(prefix=0xCA;prefix<=0xCF;prefix++){
    for(target=0x40;target<=0x50;target+=0x10){
     for(service=0xA3;service<=0xA6;service+=3){
      U8 request[9]={0};U32 id=0x000FFFFE;int expected=group<2;
      const char *start;U64 rid;const char *label;
      request[0]=(U8)prefix;request[1]=(U8)target;request[2]=(U8)service;
      length=prefix-0xC8+1;
      switch(group){
       case 0: break; /* exact declared length, including CD A6 */
       case 1: length=8;break; /* CAN padding */
       case 2: length--;break; /* declared bytes truncated */
       case 3: length=9;break; /* exceeds classic CAN */
       case 4: request[0]=(prefix&1)?0xC9:0xD0;break;
       case 5: request[1]=0x60;break;
       case 6: request[2]=0xA7;break;
       case 7: id=0x555;break;
      }
      m=frame(PROTO_CAN,id,request,length);
      label=backend_probe_name(channel(cid),&m);
      REQUIRE((label!=NULL)==expected);
      /* An overlong raw CAN payload is now rejected by J2534 before
         CEM classification, backend telemetry or vehicle observation. */
      if(group==3u){
       U32 written=1u,prior_tx=g_vehicle_bridge.inspected_tx;
       U32 prior_events=backend_len;
       REQUIRE(PassThruWriteMsgs(cid,&m,&written,0)==ERR_INVALID_MSG);
       REQUIRE(written==0u&&backend_len==prior_events);
       REQUIRE(g_vehicle_bridge.inspected_tx==prior_tx);
       n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY&&n==0);
       continue;
      }
      start=backend_lines+backend_len;send(cid,&m);rid=last_tx_request(start);
      REQUIRE(rid!=0 && terminal_count_for(start,rid)==1);
      REQUIRE(terminal_for(start,rid,expected?"unimplemented_probe":"unhandled_request","no_response")==1);
      REQUIRE(event_count_since(start,"\"kind\":\"probe_classified\"")== (U32)expected);
      REQUIRE(strstr(start,"\"kind\":\"response_generated\"")==NULL);
      n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY && n==0);
     }
    }
   }
  }
  /* Identical bytes on ISO15765 are not D2 CAN requests. */
  {
   static CHANNEL wrong;U8 request[8]={0xCD,0x50,0xA6,0,0,0,0,0};
   wrong=*channel(cid);wrong.protocol=PROTO_ISO15765;m=frame(PROTO_ISO15765,0x000FFFFE,request,8);
   REQUIRE(backend_probe_name(&wrong,&m)==NULL);
   REQUIRE(process_d2(&wrong,0x000FFFFE,request,8)==0);
  }
 }
 /* Issue #4: A3/A6 requests stay silent regardless of bus. In strict mode
    distinguish wrong 125/500/250 kbit/s route from the missing CEM reply.
    In loose mode retain the existing unimplemented_probe classification. */
 {
  static const U32 bitrates[]={125000u,500000u,250000u};
  static const U8 targets[]={0x40u,0x50u};
  static const U8 services[]={0xA3u,0xA6u};
  U32 mode,bi,ti,si,saved_strict=g_p2_strict_routing;
  SCONFIG probe_speed={1,500000u};
  SCONFIG_LIST speed_options={1,&probe_speed};
  for(mode=0;mode<2;mode++) {
   g_p2_strict_routing=mode;
   for(bi=0;bi<3;bi++) {
    probe_speed.Value=bitrates[bi];
    REQUIRE(PassThruIoctl(cid,IO_SET_CONFIG,&speed_options,0)==ERR_OK);
    REQUIRE(channel(cid)->baud==bitrates[bi]);
    /* J2534 SetConfig and passive bridge must agree after each switch. */
    {
     U32 k,synced=0;
     for(k=0;k<P2_BRIDGE_MAX_CHANNELS;k++){
      const p2_bridge_channel *bc=&g_vehicle_bridge.channels[k];
      if(bc->active && bc->id==cid){
       REQUIRE(bc->baud==bitrates[bi]);synced++;
      }
     }
     REQUIRE(synced==1u);
    }
    for(ti=0;ti<2;ti++)for(si=0;si<2;si++) {
     U8 request[8]={0xCF,targets[ti],services[si],0,0,0,0,0};
     int wrong_bus=(targets[ti]==0x40u?bitrates[bi]!=125000u:
                                              bitrates[bi]!=500000u);
     const char *expected=(mode && wrong_bus)?"unsupported_bus":"unimplemented_probe";
     const char *start;U64 rid;
     m=frame(PROTO_CAN,0x000FFFFEu,request,8);
     REQUIRE(backend_probe_name(channel(cid),&m)!=NULL);
     start=backend_lines+backend_len;send(cid,&m);rid=last_tx_request(start);
     REQUIRE(rid!=0 && terminal_count_for(start,rid)==1);
     REQUIRE(terminal_for(start,rid,expected,"no_response")==1);
     REQUIRE(event_count_since(start,"\"kind\":\"route_selected\"")==1);
     REQUIRE(event_count_since(start,"\"kind\":\"response_generated\"")==0);
     REQUIRE(strstr(start,"\"route\":\"CEM\"")!=NULL);
     n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY&&n==0);
    }
   }
  }
  probe_speed.Value=500000u;
  REQUIRE(PassThruIoctl(cid,IO_SET_CONFIG,&speed_options,0)==ERR_OK);
  g_p2_strict_routing=saved_strict;
 }
 /* One configured B9FB fixture must not be misapplied to B9F0. */
 REQUIRE(g_d2[2].frame_count==0);
 /* B9FB with an explicit synthetic, non-sensitive fixture: verify 29-bit
    response ID 0x01200003 and paced multi-frame delivery. */
 g_d2[2].frame_count=3;
 g_d2[2].frame[0][0]=0x8F;g_d2[2].frame[0][1]=0x50;g_d2[2].frame[0][2]=0xF9;g_d2[2].frame[0][3]=0xFB;
 g_d2[2].frame[1][0]=0x09;g_d2[2].frame[1][1]='S';g_d2[2].frame[1][2]='I';g_d2[2].frame[1][3]='M';
 g_d2[2].frame[2][0]=0x4F;
 const U8 d2fb[]={0xCB,0x50,0xB9,0xFB,0,0,0,0};
 m=frame(PROTO_CAN,0x000FFFFE,d2fb,8);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.Data[0]==0x01&&r.Data[1]==0x20&&r.Data[2]==0x00&&r.Data[3]==0x03);
 REQUIRE((r.RxStatus&CAN_29BIT_ID)==CAN_29BIT_ID);
 REQUIRE(r.Data[4]==0x8F&&r.Data[7]==0xFB);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,35)==ERR_OK);REQUIRE(r.Data[4]==0x09);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,35)==ERR_OK);REQUIRE(r.Data[4]==0x4F);
 /* Regression: a published-frame-shaped 13-frame B9FB response must
    arrive in exact sequence with explicit pacing (no truncated VIN). */
 static const U8 lab_b9fb[13][8]={
  {0x8F,0x50,0xF9,0xFB,0x57,0x00,0x30,0x66},
  {0x09,0x70,0x28,0x30,0x30,0x35,0x0D,0x0A},
  {0x0A,0x59,0x56,0x31,0x43,0x5A,0x30,0x30},
  {0x0B,0x30,0x32,0x41,0x30,0x30,0x30,0x30},
  {0x0C,0x30,0x30,0x31,0x0D,0x0A,0x32,0x35},
  {0x0D,0x31,0x35,0x36,0x38,0x39,0x35,0x32},
  {0x0E,0x0D,0x0A,0x32,0x39,0x35,0x0D,0x0A},
  {0x0F,0x31,0x39,0x38,0x36,0x32,0x35,0x0D},
  {0x08,0x0A,0x32,0x31,0x0D,0x0A,0x32,0x30},
  {0x09,0x30,0x35,0x31,0x32,0x0D,0x0A,0x30},
  {0x0A,0x30,0x30,0x30,0x34,0x33,0x33,0x38},
  {0x0B,0x36,0x30,0x34,0x30,0x38,0x32,0x32},
  {0x4F,0x30,0x36,0x39,0x33,0x31,0x0D,0x0A},
 };
 g_d2[2].frame_count=13;
 for(U32 z=0;z<13;z++)memcpy(g_d2[2].frame[z],lab_b9fb[z],8);
 U32 completed_before_fb=event_count("\"kind\":\"request_completed\"");
 m=frame(PROTO_CAN,0x000FFFFE,d2fb,8);send(cid,&m);
 REQUIRE(event_count("\"kind\":\"request_completed\"")==completed_before_fb);
 for(U32 z=0;z<13;z++){
   n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,35)==ERR_OK);REQUIRE(n==1);
   REQUIRE(r.DataSize==12 && r.ProtocolID==PROTO_CAN);
   REQUIRE(memcmp(r.Data+4,lab_b9fb[z],8)==0);
   if(z<12) REQUIRE(event_count("\"kind\":\"request_completed\"")==completed_before_fb);
 }
 REQUIRE(event_count("\"kind\":\"request_completed\"")==completed_before_fb+1);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 /* Regression 0.3.5: switching to strict 125/500 CEM routes. */
 g_p2_strict_routing=1;
 SCONFIG speed={1,125000};SCONFIG_LIST config={1,&speed};
 REQUIRE(PassThruIoctl(cid,IO_SET_CONFIG,&config,0)==ERR_OK);
 m=frame(PROTO_CAN,0x000FFFFE,d2fb,8);send(cid,&m);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 m=frame(PROTO_CAN,0x000FFFFE,d2req,8);send(cid,&m);
 r=readmsg(cid);REQUIRE(r.Data[5]==0x40 && r.Data[6]==0x7F);
 speed.Value=500000;REQUIRE(PassThruIoctl(cid,IO_SET_CONFIG,&config,0)==ERR_OK);
 m=frame(PROTO_CAN,0x000FFFFE,d2req,8);send(cid,&m);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 g_p2_strict_routing=0;
 /* Regression: new B9FB attempt must discard old queued D2 frames. */
 m=frame(PROTO_CAN,0x000FFFFE,d2fb,8);send(cid,&m);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x8F);
 tick+=100;for(U32 z=0;z<3;z++)pump_d2(channel(cid));
 REQUIRE(channel(cid)->count==3);
 m=frame(PROTO_CAN,0x000FFFFE,d2fb,8);send(cid,&m);
 REQUIRE(channel(cid)->count==1);r=readmsg(cid);
 REQUIRE(r.Data[4]==0x8F && r.Data[5]==0x50);
 /* CLEAR_RX_BUFFER must cancel staged and queued D2 frames. */
 REQUIRE(PassThruIoctl(cid,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);
 tick+=100;n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 /* Alternate VIDA D2 base 0x10, including intermediate end 0x55 and
    repeated first marker, must validate as one response. */
 D2_PROFILE synthetic_series={0};synthetic_series.target=0x50;
 synthetic_series.subcommand=0xFB;synthetic_series.response_id=0x01200003;
 synthetic_series.frame_count=5;
 const U8 series_frame[5][8]={
  {0x97,0x50,0xF9,0xFB,0x57,0x00,0x31,0x82},
  {0x11,0x17,0x96,'0','0','2',0x0D,0x0A},
  {0x55,0xFF,0xFF,0xFF,0xFF,0,0,0},
  {0x8F,0x50,0xF9,0xFB,0xFF,0xFF,0xFF,0xFF},
  {0x4C,0xFF,0xFF,0xFF,0xFF,0,0,0}
 };
 for(U32 z=0;z<5;z++)memcpy(synthetic_series.frame[z],series_frame[z],8);
 REQUIRE(validate_d2_fixture(&synthetic_series));
 synthetic_series.frame[1][0]=0x12;REQUIRE(!validate_d2_fixture(&synthetic_series));
 synthetic_series.frame[1][0]=0x11;
 synthetic_series.frame[4][0]=0x55;REQUIRE(!validate_d2_fixture(&synthetic_series));
 /* Periodic API must run repeatedly until Stop or CLEAR_PERIODIC_MSGS. */
 U32 periodid=0;
 const U8 period_req[]={0x03,0x22,0xF1,0x87,0,0,0,0};
 m=frame(PROTO_CAN,0x7E0,period_req,8);
 REQUIRE(PassThruStartPeriodicMsg(cid,&m,&periodid,4)==ERR_INVALID_TIME_INTERVAL);
 REQUIRE(PassThruStartPeriodicMsg(cid,&m,&periodid,15)==ERR_OK);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 tick+=16;r=readmsg(cid);REQUIRE(r.Data[4]==0x10 || r.Data[4]==0x0E);
 /* If the read-only response is multi-frame, consume FF and abort staged
    ISO-TP transfer before the next periodic tick. */
 if(channel(cid)->pending_len){channel(cid)->pending_len=0;channel(cid)->pending_pos=0;}
 tick+=16;r=readmsg(cid);REQUIRE(r.Data[2]==0x07 && r.Data[3]==0xE8);
 REQUIRE(PassThruStopPeriodicMsg(cid,periodid)==ERR_OK);
 tick+=50;n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 REQUIRE(PassThruStopPeriodicMsg(cid,periodid)==ERR_INVALID_MSG_ID);
 REQUIRE(PassThruStartPeriodicMsg(cid,&m,&periodid,15)==ERR_OK);
 REQUIRE(PassThruIoctl(cid,IO_CLEAR_PERIODIC_MSGS,0,0)==ERR_OK);
 tick+=50;n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 /* FC140 replay derived from an internally consistent synthetic lab block.
    Use 21 D2 frames for 145-byte stream (echo + 142-byte configuration).
    This test is NOT evidence of a real B9FC response CAN identifier. */
 D2_PROFILE fc_fixture={0};fc_fixture.target=0x50;fc_fixture.subcommand=0xFC;
 fc_fixture.response_id=0x01200003;fc_fixture.frame_count=21;
 U8 fc_stream[145]={0};fc_stream[0]=0x50;fc_stream[1]=0xF9;fc_stream[2]=0xFC;
 fc_stream[3]=0x8C;
 for(U32 z=0;z<140;z++)fc_stream[5+z]=(U8)(z%3u);
 U32 fc_sum=0;for(U32 z=0;z<140;z++)fc_sum+=fc_stream[5+z];
 fc_stream[4]=(U8)fc_sum;
 for(U32 z=0;z<21;z++){
   U32 len=(z==20?5:7);
   fc_fixture.frame[z][0]=(U8)(z==0?0x8F:(z==20?0x4D:(0x08|(z&7))));
   memcpy(fc_fixture.frame[z]+1,fc_stream+7*z,len);
 }
 REQUIRE(validate_d2_fixture(&fc_fixture));
 REQUIRE(validate_fc140_fixture(&fc_fixture));
 fc_fixture.frame[2][4]^=1;
 REQUIRE(!validate_fc140_fixture(&fc_fixture));
 fc_fixture.frame[2][4]^=1;
 fc_fixture.frame[20][0]=0x4F;
 REQUIRE(!validate_fc140_fixture(&fc_fixture));
 fc_fixture.frame[20][0]=0x4D;
 g_d2[5]=fc_fixture;
 const U8 fc_req[]={0xCB,0x50,0xB9,0xFC,0,0,0,0};
 m=frame(PROTO_CAN,0x000FFFFE,fc_req,8);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.Data[4]==0x8F && r.Data[5]==0x50 && r.Data[6]==0xF9 && r.Data[7]==0xFC);
 tick+=500;
 for(U32 z=0;z<20;z++){
    r=readmsg(cid);
    REQUIRE(r.Data[4]==fc_fixture.frame[z+1][0]);
 }
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 /* Wrong baud must NOT emit the XC90 HS fixture when strict P2 is enabled. */
 U32 previous_strict=g_p2_strict_routing;g_p2_strict_routing=1;
 channel(cid)->baud=125000;
 m=frame(PROTO_CAN,0x000FFFFE,fc_req,8);send(cid,&m);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 channel(cid)->baud=500000;g_p2_strict_routing=previous_strict;
 g_d2[5].frame_count=0;
 g_d2[2].frame_count=0;
 /* A second CEM target with no fixture must remain silent, not invent data. */
 const U8 d2req50[]={0xCB,0x50,0xB9,0xFB,0,0,0,0};
 m=frame(PROTO_CAN,0x000FFFFE,d2req50,8);send(cid,&m);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,2)==ERR_TIMEOUT);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 /* Functional protected request must be ignored, not return two fake NRCs. */
 const U8 freset[]={0x02,0x11,0x81,0,0,0,0,0};
 m=frame(PROTO_CAN,0x7DF,freset,8);send(cid,&m);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 /* D2 FF C8 discovery probe must never receive a made-up acknowledgment. */
 const U8 ff_c8[]={0xFF,0xC8,0,0,0,0,0,0};
 m=frame(PROTO_CAN,0x000FFFFE,ff_c8,8);send(cid,&m);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 /* VDASH first passively monitors CAN: enable opt-in synthetic bench frames. */
 g_passive_enabled=1;g_passive_period_ms=50;g_passive_id=0x555;
 g_ch[cid-1].passive_next_tick=GetTickCount()+50;
 PASSTHRU_MSG mask=frame(PROTO_CAN,0,0,0);mask.DataSize=4;
 PASSTHRU_MSG pat=mask;
 U32 filterID=0;
 REQUIRE(PassThruStartMsgFilter(cid,1,&mask,&pat,0,&filterID)==ERR_OK);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,100)==ERR_OK);
 REQUIRE(r.Data[2]==0x05&&r.Data[3]==0x55&&r.DataSize==12);
 REQUIRE(memcmp(r.Data+4,"VCARLAB",7)==0);
 REQUIRE(PassThruStopMsgFilter(cid,filterID)==ERR_OK);
 g_passive_enabled=0;
 /* v0.3.6.4: extensible network node, recorded D2 fixture only.
    Synthetic bytes are used for tests, never placed in the shipping profile. */
 D2_PROFILE *node=&g_d2[6];bytes_zero(node,sizeof(*node));
 node->target=0x11;node->subcommand=0xF0;node->baud=500000u;
 node->response_id=0x01A00003u;node->frame_count=2;
 const U8 node_ff[8]={0x8F,0x11,0xF9,0xF0,'T','E','S','T'};
 const U8 node_end[8]={0x4F,'N','O','D','E',0,0,0};
 memcpy(node->frame[0],node_ff,8);memcpy(node->frame[1],node_end,8);
 REQUIRE(validate_d2_fixture(node));
 const U8 node_req[]={0xCB,0x11,0xB9,0xF0,0,0,0,0};
 m=frame(PROTO_CAN,0x000FFFFE,node_req,8);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.Data[0]==0x01&&r.Data[1]==0xA0&&r.Data[2]==0&&r.Data[3]==3);
 REQUIRE(r.RxStatus&CAN_29BIT_ID);
 REQUIRE(memcmp(r.Data+4,node_ff,8)==0);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,30)==ERR_OK);
 REQUIRE(memcmp(r.Data+4,node_end,8)==0);
 /* Extra nodes must be network-specific even when global strict mode is off. */
 channel(cid)->baud=125000u;send(cid,&m);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 channel(cid)->baud=500000u;
 node->frame[0][1]=0x50;REQUIRE(!validate_d2_fixture(node));
 node->frame[0][1]=0x11;REQUIRE(validate_d2_fixture(node));
 node->frame_count=0;
 /* v0.3.6.4: passive recorded CAN fixture is strictly bus-specific. */
 TRACE_FRAME *trace=&g_trace[0];bytes_zero(trace,sizeof(*trace));
 trace->id=0x321;trace->baud=125000;trace->period_ms=40;trace->enabled=1;
 for(U32 z=0;z<8;z++)trace->data[z]=(U8)(0xA0+z);
 channel(cid)->trace_next_tick[0]=GetTickCount()+40;
 tick+=50;
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 channel(cid)->baud=125000u;
 r=readmsg(cid);REQUIRE(r.Data[2]==3 && r.Data[3]==0x21);
 REQUIRE(memcmp(r.Data+4,trace->data,8)==0);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 /* Disabling the fixture is silent even on the correct network. */
 trace->enabled=0;tick+=50;
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 channel(cid)->baud=500000u;
 REQUIRE(PassThruDisconnect(cid)==ERR_OK);
 /* VDASH ISO15765 request 0x7DF 09 02: one ECM answer and optional RxStart. */
 REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0x800,500000,&cid)==ERR_OK);
 mask=frame(PROTO_ISO15765,0xFFFFFFFF,0,0);mask.DataSize=4;
 pat=frame(PROTO_ISO15765,0x7E8,0,0);pat.DataSize=4;
 PASSTHRU_MSG flow=frame(PROTO_ISO15765,0x7E0,0,0);flow.DataSize=4;
 REQUIRE(PassThruStartMsgFilter(cid,3,&mask,&pat,&flow,&filterID)==ERR_OK);
 g_iso_rx_start=1;
 const U8 obd_vin[]={0x09,0x02};m=frame(PROTO_ISO15765,0x7DF,obd_vin,2);send(cid,&m);
 r=readmsg(cid);
 REQUIRE(r.RxStatus==START_OF_MESSAGE&&r.DataSize==4&&r.Data[3]==0xE8);
 REQUIRE(r.ExtraDataIndex==0);REQUIRE(r.Timestamp==tick*1000u);
 r=readmsg(cid);
 REQUIRE(r.RxStatus==0&&r.DataSize==24&&r.Data[3]==0xE8);
 REQUIRE(r.ExtraDataIndex==r.DataSize);REQUIRE(r.Timestamp==tick*1000u);
 REQUIRE(r.Data[4]==0x49&&r.Data[5]==0x02&&r.Data[6]==0x01);
 REQUIRE(memcmp(r.Data+7,"YV1CZ0002A0000001",17)==0);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 g_iso_rx_start=0;
 /* P3 F114 evidence matrix using a MY2005-style profile without CEM.
    Exact known P3 probes are classified CEM/unimplemented with zero RX;
    nearby or malformed requests remain UNHANDLED. All bytes are synthetic. */
 {
  U32 saved_count=g_ecu_count,p3cid=0,canid=0,k;
  ECU saved_ecus[MAX_ECUS];
  const char *p3_log;
  memcpy(saved_ecus,g_ecu,sizeof(saved_ecus));
  const U8 f114[]={0x22,0xF1,0x14};
  const U8 f190[]={0x22,0xF1,0x90};
  const U8 trailing[]={0x22,0xF1,0x14,0x00};
  const U8 short_req[]={0x22,0xF1};
  const U8 can_sf[]={0x03,0x22,0xF1,0x14,0,0,0,0};
  struct p3_case {U32 proto,id;const U8 *data;U32 len;const char *route,*reason;} cases[]={
   /* 1 */ {PROTO_ISO15765,0x726,f114,3,"CEM","unimplemented_probe"},
   /* 2 */ {PROTO_ISO15765,0x18DA50F1,f114,3,"CEM","unimplemented_probe"},
   /* 3 */ {PROTO_ISO15765,0x726,f190,3,"UNHANDLED","unhandled_request"},
   /* 4 */ {PROTO_ISO15765,0x726,trailing,4,"UNHANDLED","unhandled_request"},
   /* 5 */ {PROTO_ISO15765,0x726,short_req,2,"UNHANDLED","unhandled_request"},
   /* 6 */ {PROTO_ISO15765,0x18DA51F1,f114,3,"UNHANDLED","unhandled_request"},
   /* 7 */ {PROTO_CAN,0x726,can_sf,8,"UNHANDLED","unhandled_request"}
  };
  g_ecu_count=1; /* MY2005 donor profile has ECM only; no CEM fixture. */
  g_ecu[0].req=0x7E0;g_ecu[0].resp=0x7E8;
  REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&canid)==ERR_OK);
  for(k=0;k<sizeof(cases)/sizeof(cases[0]);k++){
   p3_log=backend_lines+backend_len;
   m=frame(cases[k].proto,cases[k].id,cases[k].data,cases[k].len);
   send(cases[k].proto==PROTO_CAN?canid:cid,&m);
   require_route(p3_log,cases[k].route,1);
   REQUIRE(terminal_for(p3_log,last_tx_request(p3_log),cases[k].reason,"no_response")==1);
   n=1;REQUIRE(PassThruReadMsgs(cases[k].proto==PROTO_CAN?canid:cid,&r,&n,0)==ERR_BUFFER_EMPTY);
   REQUIRE(n==0);
  }
  REQUIRE(PassThruDisconnect(canid)==ERR_OK);
  /* 8: the pre-existing configured CEM F114 lab handler still answers;
     this is a regression guard, not a claim about OEM response bytes. */
  g_ecu_count=1;g_ecu[0].req=0x726;g_ecu[0].resp=0x72E;
  REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,500000,&p3cid)==ERR_OK);
  p3_log=backend_lines+backend_len;
  m=frame(PROTO_ISO15765,0x726,f114,3);send(p3cid,&m);
  r=readmsg(p3cid);
  REQUIRE(r.Data[0]==0&&r.Data[1]==0&&r.Data[2]==0x07&&r.Data[3]==0x2E);
  REQUIRE(r.DataSize==24&&r.Data[4]==0x62&&r.Data[5]==0xF1&&r.Data[6]==0x14);
  require_route(p3_log,"CEM",1);
  REQUIRE(terminal_for(p3_log,last_tx_request(p3_log),"none","responded")==1);
  REQUIRE(PassThruDisconnect(p3cid)==ERR_OK);
  memcpy(g_ecu,saved_ecus,sizeof(saved_ecus));g_ecu_count=saved_count;
 }
 /* J2534 BLOCK filter must be distinguishable from missing ECU fixture. */
 U32 blocked_filter=0;
 REQUIRE(PassThruStartMsgFilter(cid,2,&mask,&pat,0,&blocked_filter)==ERR_OK);
 m=frame(PROTO_ISO15765,0x7E0,vin_req,3);send(cid,&m);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 REQUIRE(strstr(backend_lines,"\"kind\":\"filter_drop\"")!=NULL);
 REQUIRE(strstr(backend_lines,"\"outcome\":\"dropped\"")!=NULL);
 REQUIRE(PassThruStopMsgFilter(cid,blocked_filter)==ERR_OK);
 REQUIRE(PassThruStopMsgFilter(cid,filterID)==ERR_OK);
 REQUIRE(PassThruDisconnect(cid)==ERR_OK);
 /* dev49 F08: ISO-TP telemetry must not report complete when FF is
    delivered but pending Consecutive Frames were aborted. */
 REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&cid)==ERR_OK);
 const U8 iso_vin_sf[]={0x03,0x22,0xF1,0x90,0,0,0,0};
 const U8 iso_fc_over[]={0x32,0,0,0,0,0,0,0};
 const U8 iso_fc_cts[]={0x30,0,0,0,0,0,0,0};
 const U8 tester_present[]={0x02,0x3E,0x00,0,0,0,0,0};
 const char *case_log;
 /* Group A: OVERFLOW before the client dequeues the First Frame.
    Terminal cannot be emitted until the still-queued FF is read. */
 case_log=backend_lines+backend_len;
 m=frame(PROTO_CAN,0x7E0,iso_vin_sf,8);send(cid,&m);
 REQUIRE(channel(cid)->pending_len==20);
 REQUIRE(event_count_since(case_log,"\"kind\":\"request_completed\"")==0);
 m=frame(PROTO_CAN,0x7E0,iso_fc_over,8);send(cid,&m);
 REQUIRE(channel(cid)->pending_len==0);
 REQUIRE(strstr(case_log,"\"kind\":\"response_aborted\"")!=NULL);
 REQUIRE(event_count_since(case_log,"\"kind\":\"request_completed\"")==0);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x10);
 REQUIRE(strstr(case_log,"\"reason\":\"flow_overflow\",\"outcome\":\"aborted\"")!=NULL);
 REQUIRE(event_count_since(case_log,"\"kind\":\"request_completed\"")==1);
 REQUIRE(strstr(case_log,"\"outcome\":\"responded\"")==NULL);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 /* Group B: if FF was already read, OVERFLOW completes the abort now. */
 case_log=backend_lines+backend_len;
 m=frame(PROTO_CAN,0x7E0,iso_vin_sf,8);send(cid,&m);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x10);
 REQUIRE(event_count_since(case_log,"\"kind\":\"request_completed\"")==0);
 m=frame(PROTO_CAN,0x7E0,iso_fc_over,8);send(cid,&m);
 REQUIRE(strstr(case_log,"\"reason\":\"flow_overflow\",\"outcome\":\"aborted\"")!=NULL);
 REQUIRE(event_count_since(case_log,"\"kind\":\"request_completed\"")==1);
 REQUIRE(strstr(case_log,"\"outcome\":\"responded\"")==NULL);
 /* Group C: a new SF response supersedes a pending FF still in RX FIFO.
    The old request is aborted; the new complete response may succeed. */
 case_log=backend_lines+backend_len;
 m=frame(PROTO_CAN,0x7E0,iso_vin_sf,8);send(cid,&m);
 m=frame(PROTO_CAN,0x7E0,tester_present,8);send(cid,&m);
 REQUIRE(channel(cid)->pending_len==0);
 REQUIRE(event_count_since(case_log,"\"kind\":\"request_completed\"")==0);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x10);
 REQUIRE(strstr(case_log,"\"reason\":\"superseded\",\"outcome\":\"aborted\"")!=NULL);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x02 && r.Data[5]==0x7E);
 REQUIRE(event_count_since(case_log,"\"kind\":\"request_completed\"")==2);
 REQUIRE(event_count_since(case_log,"\"outcome\":\"aborted\"")==1);
 REQUIRE(event_count_since(case_log,"\"outcome\":\"responded\"")==1);
 /* Group D: supersede after FF dequeue must immediately abort old RID. */
 case_log=backend_lines+backend_len;
 m=frame(PROTO_CAN,0x7E0,iso_vin_sf,8);send(cid,&m);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x10);
 m=frame(PROTO_CAN,0x7E0,tester_present,8);send(cid,&m);
 REQUIRE(strstr(case_log,"\"reason\":\"superseded\",\"outcome\":\"aborted\"")!=NULL);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x02 && r.Data[5]==0x7E);
 REQUIRE(event_count_since(case_log,"\"kind\":\"request_completed\"")==2);
 /* Group E: ordinary FF+CTS+2 CF still yields one successful terminal. */
 case_log=backend_lines+backend_len;
 m=frame(PROTO_CAN,0x7E0,iso_vin_sf,8);send(cid,&m);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x10);
 REQUIRE(event_count_since(case_log,"\"kind\":\"request_completed\"")==0);
 m=frame(PROTO_CAN,0x7E0,iso_fc_cts,8);send(cid,&m);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x21);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x22);
 REQUIRE(event_count_since(case_log,"\"kind\":\"request_completed\"")==1);
 REQUIRE(event_count_since(case_log,"\"outcome\":\"responded\"")==1);
 REQUIRE(event_count_since(case_log,"\"outcome\":\"aborted\"")==0);
 /* Group F: wrong-channel-address Flow Control cannot finish a transfer. */
 case_log=backend_lines+backend_len;
 m=frame(PROTO_CAN,0x7E0,iso_vin_sf,8);send(cid,&m);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x10);
 m=frame(PROTO_CAN,0x726,iso_fc_cts,8);send(cid,&m);
 REQUIRE(event_count_since(case_log,"\"kind\":\"request_completed\"")==0);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 m=frame(PROTO_CAN,0x7E0,iso_fc_cts,8);send(cid,&m);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x21);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x22);
 REQUIRE(event_count_since(case_log,"\"outcome\":\"responded\"")==1);
 /* Group G: telemetry is disabled by default in production and explicit
    opt-out cannot change PassThru responses or generate a journal record. */
 g_backend_enabled=0;
 U32 log_before_opt_out=backend_len;
 m=frame(PROTO_CAN,0x7E0,tester_present,8);send(cid,&m);
 r=readmsg(cid);REQUIRE(r.Data[4]==0x02 && r.Data[5]==0x7E);
 REQUIRE(backend_len==log_before_opt_out);
 g_backend_enabled=1;
 REQUIRE(PassThruDisconnect(cid)==ERR_OK);

 /* dev49 F09: real CHANNEL RX-loss evidence must retain per-request
    causes, not a single dropped_trace shared across transactions.
    All frames below are synthetic; no ECU addresses are asserted as OEM. */
 {
  U32 loss_channel=0,loss_filter=0;
  CHANNEL *loss;
  PASSTHRU_MSG *batch=(PASSTHRU_MSG*)calloc(128,sizeof(*batch));
  const U8 lab_bytes[8]={0x56,0x43,0x41,0x52,0x4C,0x41,0x42,0};
  PASSTHRU_MSG loss_mask=frame(PROTO_CAN,0xFFFFFFFFu,0,0),loss_pat=frame(PROTO_CAN,0x7E8,0,0);
  U64 ridA,ridB,ridC,ridD,ridE,ridF;
  REQUIRE(batch!=0);
  REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&loss_channel)==ERR_OK);
  loss=channel(loss_channel);
  loss_mask.DataSize=4;loss_pat.DataSize=4;
  /* 1: an entirely full RX FIFO produces queue_full, not filter_reject. */
  fill_untraced_rx(loss,MAX_QUEUE);
  case_log=backend_lines+backend_len;
  ridA=next_backend_request();loss->active_trace=ridA;
  enqueue(loss,0x7E8,lab_bytes,8);loss->active_trace=0;
  backend_end_if_drained(loss,ridA);
  REQUIRE(terminal_for(case_log,ridA,"queue_full","dropped")==1);
  REQUIRE(terminal_for(case_log,ridA,"filter_reject","dropped")==0);
  n=128;REQUIRE(PassThruReadMsgs(loss_channel,batch,&n,0)==ERR_OK&&n==MAX_QUEUE);
  REQUIRE(loss->count==0);
  /* 2: BLOCK filter without pressure is reported as filter_reject. */
  REQUIRE(PassThruStartMsgFilter(loss_channel,2,&loss_mask,&loss_pat,0,&loss_filter)==ERR_OK);
  case_log=backend_lines+backend_len;
  ridB=next_backend_request();loss->active_trace=ridB;
  enqueue(loss,0x7E8,lab_bytes,8);loss->active_trace=0;
  backend_end_if_drained(loss,ridB);
  REQUIRE(terminal_for(case_log,ridB,"filter_reject","dropped")==1);
  REQUIRE(terminal_for(case_log,ridB,"queue_full","dropped")==0);
  REQUIRE(PassThruStopMsgFilter(loss_channel,loss_filter)==ERR_OK);
  /* 3: two RIDs can fail while one is already queued; their terminals
     must not overwrite each other's reason or arrive before dequeue. */
  case_log=backend_lines+backend_len;
  ridA=next_backend_request();loss->active_trace=ridA;
  enqueue(loss,0x7E8,lab_bytes,8);loss->active_trace=0;
  fill_untraced_rx(loss,MAX_QUEUE);
  ridB=next_backend_request();loss->active_trace=ridB;
  enqueue(loss,0x7E8,lab_bytes,8);loss->active_trace=0;
  backend_end_if_drained(loss,ridB);
  loss->active_trace=ridA;enqueue(loss,0x7E8,lab_bytes,8);loss->active_trace=0;
  backend_end_if_drained(loss,ridA);
  REQUIRE(terminal_for(case_log,ridB,"queue_full","dropped")==1);
  REQUIRE(terminal_for(case_log,ridA,"queue_full","dropped")==0);
  n=128;REQUIRE(PassThruReadMsgs(loss_channel,batch,&n,0)==ERR_OK&&n==MAX_QUEUE);
  REQUIRE(batch[0].Data[2]==0x07&&batch[0].Data[3]==0xE8);
  REQUIRE(terminal_for(case_log,ridA,"queue_full","dropped")==1);
  REQUIRE(terminal_for(case_log,ridB,"queue_full","dropped")==1);
  /* 4: filter rejection followed by queue_full for the same RID
     yields a single terminal, prioritising loss caused by FIFO pressure. */
  REQUIRE(PassThruStartMsgFilter(loss_channel,2,&loss_mask,&loss_pat,0,&loss_filter)==ERR_OK);
  case_log=backend_lines+backend_len;
  ridC=next_backend_request();loss->active_trace=ridC;
  enqueue(loss,0x7E8,lab_bytes,8);
  REQUIRE(PassThruStopMsgFilter(loss_channel,loss_filter)==ERR_OK);
  fill_untraced_rx(loss,MAX_QUEUE);
  enqueue(loss,0x7E8,lab_bytes,8);loss->active_trace=0;
  backend_end_if_drained(loss,ridC);
  REQUIRE(terminal_for(case_log,ridC,"queue_full","dropped")==1);
  REQUIRE(terminal_for(case_log,ridC,"filter_reject","dropped")==0);
  n=128;REQUIRE(PassThruReadMsgs(loss_channel,batch,&n,0)==ERR_OK&&n==MAX_QUEUE);
  /* 5: queue_full followed by filter rejection retains the same
     priority, independent of the order of observed failures. */
  fill_untraced_rx(loss,MAX_QUEUE);
  case_log=backend_lines+backend_len;
  ridD=next_backend_request();loss->active_trace=ridD;
  enqueue(loss,0x7E8,lab_bytes,8);loss->active_trace=0;
  n=128;REQUIRE(PassThruReadMsgs(loss_channel,batch,&n,0)==ERR_OK&&n==MAX_QUEUE);
  REQUIRE(PassThruStartMsgFilter(loss_channel,2,&loss_mask,&loss_pat,0,&loss_filter)==ERR_OK);
  loss->active_trace=ridD;enqueue(loss,0x7E8,lab_bytes,8);loss->active_trace=0;
  backend_end_if_drained(loss,ridD);
  REQUIRE(terminal_for(case_log,ridD,"queue_full","dropped")==1);
  REQUIRE(terminal_for(case_log,ridD,"filter_reject","dropped")==0);
  REQUIRE(PassThruStopMsgFilter(loss_channel,loss_filter)==ERR_OK);
  /* 6: F08 aborted lifecycle always wins over an earlier queue drop;
     stale per-RID drop metadata must be released after terminal. */
  case_log=backend_lines+backend_len;
  ridE=next_backend_request();loss->active_trace=ridE;
  enqueue(loss,0x7E8,lab_bytes,8);loss->active_trace=0;
  fill_untraced_rx(loss,MAX_QUEUE);
  loss->active_trace=ridE;enqueue(loss,0x7E8,lab_bytes,8);loss->active_trace=0;
  backend_abort_pending(loss,ridE,BACKEND_ABORT_SUPERSEDED);
  REQUIRE(terminal_for(case_log,ridE,"superseded","aborted")==0);
  n=128;REQUIRE(PassThruReadMsgs(loss_channel,batch,&n,0)==ERR_OK&&n==MAX_QUEUE);
  REQUIRE(terminal_for(case_log,ridE,"superseded","aborted")==1);
  REQUIRE(terminal_for(case_log,ridE,"queue_full","dropped")==0);
  for(U32 j=0;j<BACKEND_DROP_SLOTS;j++)REQUIRE(loss->drops[j].rid!=ridE);
  /* 7: ordinary queued delivery still completes exactly once as
     responded, with no false queue_full or filter_reject attribution. */
  case_log=backend_lines+backend_len;
  ridF=next_backend_request();loss->active_trace=ridF;
  enqueue(loss,0x7E8,lab_bytes,8);loss->active_trace=0;
  backend_end_if_drained(loss,ridF);
  REQUIRE(terminal_for(case_log,ridF,"none","responded")==0);
  n=1;REQUIRE(PassThruReadMsgs(loss_channel,batch,&n,0)==ERR_OK&&n==1);
  REQUIRE(terminal_for(case_log,ridF,"none","responded")==1);
  REQUIRE(terminal_for(case_log,ridF,"queue_full","dropped")==0);
  /* 8: with telemetry explicitly disabled, the same RX queue still
     delivers frames but writes no new JSONL entries. */
  {
   U32 journal_before=backend_len;
   g_backend_enabled=0;
   loss->active_trace=next_backend_request();
   REQUIRE(loss->active_trace==0);
   enqueue(loss,0x7E8,lab_bytes,8);
   n=1;REQUIRE(PassThruReadMsgs(loss_channel,batch,&n,0)==ERR_OK&&n==1);
   REQUIRE(backend_len==journal_before);
   g_backend_enabled=1;
   loss->active_trace=0;
  }
  REQUIRE(PassThruDisconnect(loss_channel)==ERR_OK);
  free(batch);
 }
 /* dev49 F11: lifecycle records must survive queue resets and be emitted
    at most once per request_id. These are synthetic lab fixture tests. */
 {
  U32 lc=0,lc2=0;U64 first,second;
  CHANNEL *ch;
  const char *start;
  PASSTHRU_MSG tmp;
  const U8 lc_req[]={0xCB,0x50,0xB9,0xF0,0,0,0,0};
  const U8 sf_tester[]={0x02,0x3E,0x00,0,0,0,0,0};
  const U8 fc_over[]={0x32,0,0,0,0,0,0,0};
  REQUIRE(g_d2[3].frame_count==3);
  REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&lc)==ERR_OK);
  ch=channel(lc);
  /* 1: queued, never-dequeued single frame cancelled by CLEAR_RX. */
  start=backend_lines+backend_len;
  tmp=frame(PROTO_CAN,0x7E0,sf_tester,8);send(lc,&tmp);
  REQUIRE(ch->count==1);
  first=ch->queue_trace[ch->r];REQUIRE(first!=0);
  REQUIRE(PassThruIoctl(lc,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);
  REQUIRE(terminal_for(start,first,"clear_rx_buffer","aborted")==1);
  REQUIRE(event_count_since(start,"\"kind\":\"rx_dropped\"")==1);
  REQUIRE(strstr(start,"\"kind\":\"rx_dropped\"")<strstr(start,"\"kind\":\"request_completed\""));
  REQUIRE(terminal_for(start,first,"none","responded")==0);
  n=1;REQUIRE(PassThruReadMsgs(lc,&r,&n,0)==ERR_BUFFER_EMPTY&&n==0);
  /* 2: CLEAR_RX cancels both queued first D2 frame and staged tail.
     No stale frame may emerge from a later ReadMsgs. */
  start=backend_lines+backend_len;
  tmp=frame(PROTO_CAN,0x000FFFFE,lc_req,8);send(lc,&tmp);
  first=ch->d2_trace;REQUIRE(first && ch->d2_count==3 && ch->count==1);
  REQUIRE(PassThruIoctl(lc,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);
  REQUIRE(terminal_for(start,first,"clear_rx_buffer","aborted")==1);
  REQUIRE(ch->d2_trace==0 && ch->d2_count==0 && ch->count==0);
  tick+=100;n=1;REQUIRE(PassThruReadMsgs(lc,&r,&n,0)==ERR_BUFFER_EMPTY&&n==0);
  /* 3: clearing an already-queued FF invalidates its delivery evidence.
     Historical pending ISO-TP transport behavior remains unchanged. */
  start=backend_lines+backend_len;
  tmp=frame(PROTO_CAN,0x7E0,iso_vin_sf,8);send(lc,&tmp);
  first=ch->pending_trace;REQUIRE(first && ch->pending_len==20);
  REQUIRE(PassThruIoctl(lc,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);
  REQUIRE(ch->pending_len==20 && ch->pending_trace==0);
  REQUIRE(terminal_for(start,first,"clear_rx_buffer","aborted")==1);
  tmp=frame(PROTO_CAN,0x7E0,iso_fc_cts,8);send(lc,&tmp);
  r=readmsg(lc);REQUIRE(r.Data[4]==0x21);
  r=readmsg(lc);REQUIRE(r.Data[4]==0x22);
  REQUIRE(terminal_for(start,first,"clear_rx_buffer","aborted")==1);
  REQUIRE(terminal_for(start,first,"none","responded")==0);
  /* 4: new D2 attempt supersedes staged and queued old D2 bytes. */
  start=backend_lines+backend_len;
  tmp=frame(PROTO_CAN,0x000FFFFE,lc_req,8);send(lc,&tmp);
  first=ch->d2_trace;REQUIRE(first && ch->count==1);
  send(lc,&tmp);second=ch->d2_trace;
  REQUIRE(second && second!=first);
  REQUIRE(terminal_for(start,first,"d2_superseded","aborted")==1);
  REQUIRE(event_count_since(start,"\"kind\":\"rx_dropped\"")==1);
  REQUIRE(strstr(start,"\"kind\":\"rx_dropped\"")<strstr(start,"\"kind\":\"request_completed\""));
  r=readmsg(lc);REQUIRE(r.Data[4]==0x8F);
  tick+=40;r=readmsg(lc);REQUIRE(r.Data[4]==0x09);
  tick+=40;r=readmsg(lc);REQUIRE(r.Data[4]==0x4C);
  REQUIRE(terminal_for(start,second,"none","responded")==1);
  REQUIRE(terminal_for(start,first,"d2_superseded","aborted")==1);
  /* 5: D2 retry drops only its old frames, preserving unrelated FIFO. */
  start=backend_lines+backend_len;
  fill_untraced_rx(ch,1);
  tmp=frame(PROTO_CAN,0x000FFFFE,lc_req,8);send(lc,&tmp);
  first=ch->d2_trace;
  send(lc,&tmp);second=ch->d2_trace;
  REQUIRE(first && second && second!=first);
  REQUIRE(terminal_for(start,first,"d2_superseded","aborted")==1);
  r=readmsg(lc);REQUIRE(r.Data[2]==0x05 && r.Data[3]==0x55);
  r=readmsg(lc);REQUIRE(r.Data[4]==0x8F);
  tick+=40;r=readmsg(lc);REQUIRE(r.Data[4]==0x09);
  tick+=40;r=readmsg(lc);REQUIRE(r.Data[4]==0x4C);
  REQUIRE(terminal_for(start,second,"none","responded")==1);
  /* 6: Disconnect aborts queued SF once. Reusing ChannelID gets fresh
     transaction ID, not an old terminal record. */
  start=backend_lines+backend_len;
  tmp=frame(PROTO_CAN,0x7E0,sf_tester,8);send(lc,&tmp);
  first=ch->queue_trace[ch->r];REQUIRE(first);
  REQUIRE(PassThruDisconnect(lc)==ERR_OK);
  REQUIRE(terminal_for(start,first,"channel_disconnect","aborted")==1);
  REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&lc)==ERR_OK);
  ch=channel(lc);
  tmp=frame(PROTO_CAN,0x7E0,sf_tester,8);send(lc,&tmp);
  second=ch->queue_trace[ch->r];REQUIRE(second && second!=first);
  r=readmsg(lc);REQUIRE(r.Data[4]==0x02 && r.Data[5]==0x7E);
  REQUIRE(terminal_for(start,second,"none","responded")==1);
  REQUIRE(terminal_for(start,first,"channel_disconnect","aborted")==1);
  /* 7: one device Close cancels active transactions on *both* channels,
     including FF/pending and staged D2; no channel is silently discarded. */
  REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&lc2)==ERR_OK);
  start=backend_lines+backend_len;
  tmp=frame(PROTO_CAN,0x7E0,iso_vin_sf,8);send(lc,&tmp);
  first=channel(lc)->pending_trace;
  tmp=frame(PROTO_CAN,0x000FFFFE,lc_req,8);send(lc2,&tmp);
  second=channel(lc2)->d2_trace;
  REQUIRE(first && second && first!=second);
  REQUIRE(PassThruClose(dev)==ERR_OK);
  REQUIRE(terminal_for(start,first,"device_close","aborted")==1);
  REQUIRE(terminal_for(start,second,"device_close","aborted")==1);
  REQUIRE(terminal_for(start,first,"none","responded")==0);
  REQUIRE(PassThruOpen(0,&dev)==ERR_OK);
  /* 8: F08 abort precedence survives CLEAR_RX, and telemetry opt-out
     remains completely inert while the J2534 transport still operates. */
  REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&lc)==ERR_OK);
  ch=channel(lc);start=backend_lines+backend_len;
  tmp=frame(PROTO_CAN,0x7E0,iso_vin_sf,8);send(lc,&tmp);
  first=ch->pending_trace;REQUIRE(first);
  tmp=frame(PROTO_CAN,0x7E0,fc_over,8);send(lc,&tmp);
  REQUIRE(terminal_for(start,first,"flow_overflow","aborted")==0);
  REQUIRE(PassThruIoctl(lc,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);
  REQUIRE(terminal_for(start,first,"flow_overflow","aborted")==1);
  REQUIRE(terminal_for(start,first,"clear_rx_buffer","aborted")==0);
  {
   U32 before=backend_len;
   g_backend_enabled=0;
   tmp=frame(PROTO_CAN,0x7E0,sf_tester,8);send(lc,&tmp);
   REQUIRE(PassThruIoctl(lc,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);
   REQUIRE(PassThruDisconnect(lc)==ERR_OK);
   REQUIRE(backend_len==before);
   g_backend_enabled=1;
  }
  /* F13: one functional request fans out to both configured ECUs, but gets
     exactly one terminal event after every response/filter decision. */
  {
   static const struct {const char *name;U32 block_mask;int reverse;U8 service;} f13[]={
    {"both blocked",3,0,0x02},{"ECM blocked",1,0,0x02},{"CEM response blocked",2,0,0x02},
    {"both pass",0,0,0x02},{"reverse ECU order",1,1,0x02},{"duplicate ECM block",5,0,0x02},
    {"short functional reply",1,0,0x0C},{"unsupported service fanout",3,0,0x55}
   };
   U32 case_no;
   REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0x800,500000,&lc)==ERR_OK);
   ch=channel(lc);
   for(case_no=0;case_no<sizeof(f13)/sizeof(f13[0]);case_no++){
    U32 f1=0,f2=0,f3=0,k;U64 rid;
    PASSTHRU_MSG fm=frame(PROTO_ISO15765,0xFFFFFFFFu,0,0),fp;
    PASSTHRU_MSG request;
    REQUIRE(PassThruIoctl(lc,IO_CLEAR_MSG_FILTERS,0,0)==ERR_OK);
    g_ecu[0].req=0x7E0;g_ecu[0].resp=0x7E8;g_ecu[1].req=0x726;g_ecu[1].resp=0x72E;
    if(f13[case_no].reverse){ECU swap=g_ecu[0];g_ecu[0]=g_ecu[1];g_ecu[1]=swap;}
    if(f13[case_no].block_mask&1){fp=frame(PROTO_ISO15765,0x7E8,0,0);REQUIRE(PassThruStartMsgFilter(lc,2,&fm,&fp,0,&f1)==ERR_OK);}
    if(f13[case_no].block_mask&2){fp=frame(PROTO_ISO15765,0x72E,0,0);REQUIRE(PassThruStartMsgFilter(lc,2,&fm,&fp,0,&f2)==ERR_OK);}
    if(f13[case_no].block_mask&4){fp=frame(PROTO_ISO15765,0x7E8,0,0);REQUIRE(PassThruStartMsgFilter(lc,2,&fm,&fp,0,&f3)==ERR_OK);}
    {U8 service_req[2]={0x09,f13[case_no].service};request=frame(PROTO_ISO15765,0x7DF,service_req,2);}
    start=backend_lines+backend_len;send(lc,&request);rid=last_tx_request(start);REQUIRE(rid);
    for(k=0;k<4;k++){
     n=1;
     if(PassThruReadMsgs(lc,&r,&n,0)==ERR_BUFFER_EMPTY)break;
     REQUIRE(n==1);
    }
    n=1;REQUIRE(PassThruReadMsgs(lc,&r,&n,0)==ERR_BUFFER_EMPTY);
    REQUIRE(terminal_count_for(start,rid)==1);
    if(f13[case_no].block_mask==3)REQUIRE(terminal_for(start,rid,"filter_reject","dropped")==1);
    if(f1)REQUIRE(PassThruStopMsgFilter(lc,f1)==ERR_OK);
    if(f2)REQUIRE(PassThruStopMsgFilter(lc,f2)==ERR_OK);
    if(f3)REQUIRE(PassThruStopMsgFilter(lc,f3)==ERR_OK);
   }
   g_ecu[0].req=0x7E0;g_ecu[0].resp=0x7E8;g_ecu[1].req=0x726;g_ecu[1].resp=0x72E;
   REQUIRE(PassThruDisconnect(lc)==ERR_OK);
  }
  /* F12: same PID and request serial after a DLL reload still gets a distinct
     session ID, so appended JSONL records cannot alias old request IDs. */
  {
   static const U32 ticks[]={1,2,17,100,1000,60000,0x7FFFFFFFu,0xFFFFFFFFu};
   U64 seen[8],rid0,rid;U32 z;char *capture;
   REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&lc2)==ERR_OK);
   ch=channel(lc2);
   start=backend_lines+backend_len;
   g_host_pid=0xAABBCCDDu;
   for(z=0;z<8;z++){
    g_backend_session=backend_session_id(g_host_pid,ticks[z],0x123456789ABCDEF0ull);
    g_backend_serial=0;rid0=next_backend_request();
    if(z==0)rid=rid0;else REQUIRE(rid0==rid);
    seen[z]=g_backend_session;
    backend_event(ch,rid0,"session_probe","UNKNOWN","none","unknown");
    REQUIRE(strstr(backend_lines,"\"session_id\":\"")!=NULL);
   }
   for(z=0;z<8;z++){U32 k;for(k=z+1;k<8;k++)REQUIRE(seen[z]!=seen[k]);}
   capture=(char*)start;
   for(z=0;z<8;z++){
    char marker[48];
    snprintf(marker,sizeof(marker),"\"session_id\":\"%016llx\"",(unsigned long long)seen[z]);
    REQUIRE(strstr(capture,marker)!=NULL);
   }
   g_backend_session=backend_session_id(g_host_pid,GetTickCount(),0x123456789ABCDEF1ull);
   REQUIRE(PassThruDisconnect(lc2)==ERR_OK);
  }

  /* F03: an FC needs FS, BS and STmin; rejected short frames leave the
     pending response intact until a complete CTS arrives. */
  {
   static const struct {const char *name;U32 id;U8 bytes[3];U32 len;int valid;} cases[]={
    {"PCI only",0x7E0,{0x30,0,0},1,0},{"missing STmin BS0",0x7E0,{0x30,0,0},2,0},
    {"missing STmin BS1",0x7E0,{0x30,1,0},2,0},{"wrong physical ID",0x7E1,{0x30,0,0},3,0},
    {"WAIT",0x7E0,{0x31,0,0},3,0},{"reserved status",0x7E0,{0x33,0,0},3,0},
    {"OVERFLOW",0x7E0,{0x32,0,0},3,0},{"complete CTS",0x7E0,{0x30,0,0},3,1}
   };
   U32 z;
   REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&lc)==ERR_OK);
   for(z=0;z<sizeof(cases)/sizeof(cases[0]);z++){
    U32 before_pos,before_count;PASSTHRU_MSG flow;
    ch=channel(lc);
    REQUIRE(PassThruIoctl(lc,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);
    tmp=frame(PROTO_CAN,0x7E0,iso_vin_sf,8);send(lc,&tmp);
    tmp=readmsg(lc);REQUIRE(tmp.Data[4]==0x10);
    REQUIRE(ch->pending_len==20&&ch->pending_pos==6&&ch->count==0);
    before_pos=ch->pending_pos;before_count=ch->count;
    flow=frame(PROTO_CAN,cases[z].id,cases[z].bytes,cases[z].len);send(lc,&flow);
    if(cases[z].valid){
     REQUIRE(ch->pending_len==0&&ch->count>before_count);
    }else if(cases[z].bytes[0]==0x32){
     REQUIRE(ch->pending_len==0&&ch->pending_pos==0);
    }else{
     REQUIRE(ch->pending_len==20&&ch->pending_pos==before_pos&&ch->count==before_count);
    }
    REQUIRE(PassThruIoctl(lc,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);
   }
   REQUIRE(PassThruDisconnect(lc)==ERR_OK);

  /* F04: reserved STmin values cannot release pending Consecutive Frames;
     valid millisecond and sub-millisecond ranges still work. */
  {
   static const struct {const char *name;U8 stmin;int valid;} cases[]={
    {"zero milliseconds",0x00,1},{"127 milliseconds",0x7F,1},
    {"reserved low boundary",0x80,0},{"reserved high boundary",0xF0,0},
    {"100 microseconds",0xF1,1},{"900 microseconds",0xF9,1},
    {"reserved microsecond boundary",0xFA,0},{"reserved maximum",0xFF,0}
   };
   U32 z;
   REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&lc)==ERR_OK);
   ch=channel(lc);
   for(z=0;z<sizeof(cases)/sizeof(cases[0]);z++){
    U8 fc_bytes[3]={0x30,0,cases[z].stmin};
    PASSTHRU_MSG fc;
    REQUIRE(PassThruIoctl(lc,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);
    tmp=frame(PROTO_CAN,0x7E0,iso_vin_sf,8);send(lc,&tmp);
    tmp=readmsg(lc);REQUIRE(tmp.Data[4]==0x10);
    REQUIRE(ch->pending_len==20&&ch->pending_pos==6&&ch->count==0);
    fc=frame(PROTO_CAN,0x7E0,fc_bytes,3);send(lc,&fc);
    if(cases[z].valid){
     REQUIRE(ch->pending_len==0&&ch->count==2);
    }else{
     REQUIRE(ch->pending_len==20&&ch->pending_pos==6&&ch->count==0);
     fc=frame(PROTO_CAN,0x7E0,iso_fc_cts,8);send(lc,&fc);
     REQUIRE(ch->pending_len==0&&ch->count==2);
    }
   }
   REQUIRE(PassThruDisconnect(lc)==ERR_OK);
  }
  }

  /* F05: valid STmin gates CF delivery and timestamps at millisecond and
     sub-millisecond precision. Polling before the due time returns empty. */
  {
   static const struct {const char *name;U8 stmin;U32 delay_us;} cases[]={
    {"no separation",0x00,0},{"one millisecond",0x01,1000},
    {"127 milliseconds",0x7F,127000},{"100 microseconds",0xF1,100},
    {"500 microseconds",0xF5,500},{"900 microseconds",0xF9,900}
   };
   U32 z;
   REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&lc)==ERR_OK);
   ch=channel(lc);qpc_offset_us=0;
   for(z=0;z<sizeof(cases)/sizeof(cases[0]);z++){
    U8 fc_bytes[3]={0x30,0,cases[z].stmin};
    PASSTHRU_MSG fc,rx;U32 count=1;
    REQUIRE(PassThruIoctl(lc,IO_CLEAR_RX_BUFFER,0,0)==ERR_OK);
    tmp=frame(PROTO_CAN,0x7E0,iso_vin_sf,8);send(lc,&tmp);
    tmp=readmsg(lc);REQUIRE(tmp.Data[4]==0x10);
    fc=frame(PROTO_CAN,0x7E0,fc_bytes,3);send(lc,&fc);
    REQUIRE(ch->pending_len==0&&ch->count==2);
    REQUIRE(PassThruReadMsgs(lc,&rx,&count,0)==ERR_OK&&count==1&&rx.Data[4]==0x21);
    if(cases[z].delay_us){
     count=1;REQUIRE(PassThruReadMsgs(lc,&rx,&count,0)==ERR_BUFFER_EMPTY&&count==0);
     advance_test_us(cases[z].delay_us-1);
     count=1;REQUIRE(PassThruReadMsgs(lc,&rx,&count,0)==ERR_BUFFER_EMPTY&&count==0);
     advance_test_us(1);
    }
    count=1;REQUIRE(PassThruReadMsgs(lc,&rx,&count,0)==ERR_OK&&count==1&&rx.Data[4]==0x22);
    REQUIRE((U32)(rx.Timestamp-tmp.Timestamp)>=cases[z].delay_us);
   }
   REQUIRE(PassThruDisconnect(lc)==ERR_OK);
  }
 }
 /* Stage 41: opt-in strict receive filters. All original legacy checks
    above run with strict disabled; restore the default before closing. */
 {
  const U8 vin_read[]={0x22,0xF1,0x90};
  PASSTHRU_MSG msg,rx,mask,pattern,flow,canmask,canpattern;
  U32 can=0,iso=0,filter=0,allow=0,block=0,count=1,old_start=g_iso_rx_start;
  REQUIRE(g_strict_j2534_filters==0);
  g_strict_j2534_filters=1;
  g_iso_rx_start=1;
  REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,500000,&iso)==ERR_OK);
  REQUIRE(PassThruConnect(dev,PROTO_CAN,0,500000,&can)==ERR_OK);
  msg=frame(PROTO_ISO15765,0x7E0,vin_read,3);
  send(iso,&msg);count=1;
  REQUIRE(PassThruReadMsgs(iso,&rx,&count,0)==ERR_BUFFER_EMPTY && count==0);
  mask=frame(PROTO_ISO15765,0xFFFFFFFFu,0,0);
  pattern=frame(PROTO_ISO15765,0x7E8u,0,0);
  flow=frame(PROTO_ISO15765,0x7E0u,0,0);
  canmask=frame(PROTO_CAN,0xFFFFFFFFu,0,0);
  canpattern=frame(PROTO_CAN,0x7E8u,0,0);
  REQUIRE(PassThruStartMsgFilter(can,3,&canmask,&canpattern,&flow,&filter)==ERR_NO_FLOW_CONTROL);
  REQUIRE(PassThruStartMsgFilter(iso,1,&mask,&pattern,0,&filter)==ERR_INVALID_FLAGS);
  REQUIRE(PassThruStartMsgFilter(iso,2,&mask,&pattern,0,&filter)==ERR_INVALID_FLAGS);
  REQUIRE(PassThruStartMsgFilter(iso,3,&mask,&pattern,0,&filter)==ERR_NULL_PARAMETER);
  mask.DataSize=5;
  REQUIRE(PassThruStartMsgFilter(iso,3,&mask,&pattern,&flow,&filter)==ERR_INVALID_MSG);
  mask.DataSize=4;
  flow.DataSize=5;
  REQUIRE(PassThruStartMsgFilter(iso,3,&mask,&pattern,&flow,&filter)==ERR_INVALID_MSG);
  flow.DataSize=4;
  flow.ProtocolID=PROTO_CAN;
  REQUIRE(PassThruStartMsgFilter(iso,3,&mask,&pattern,&flow,&filter)==ERR_MSG_PROTOCOL_ID);
  flow.ProtocolID=PROTO_ISO15765;
  pattern.Data[3]=0xE9;
  REQUIRE(PassThruStartMsgFilter(iso,3,&mask,&pattern,&flow,&filter)==ERR_OK);
  send(iso,&msg);count=1;
  REQUIRE(PassThruReadMsgs(iso,&rx,&count,0)==ERR_BUFFER_EMPTY && count==0);
  REQUIRE(PassThruStopMsgFilter(iso,filter)==ERR_OK);
  pattern.Data[3]=0xE8;
  REQUIRE(PassThruStartMsgFilter(iso,3,&mask,&pattern,&flow,&filter)==ERR_OK);
  send(iso,&msg);
  rx=readmsg(iso);
  REQUIRE(rx.RxStatus & START_OF_MESSAGE);
  REQUIRE(rx.DataSize==4&&rx.ExtraDataIndex==0);
  rx=readmsg(iso);
  REQUIRE(rx.ProtocolID==PROTO_ISO15765&&rx.DataSize==24);
  REQUIRE(rx.Data[4]==0x62&&rx.Data[5]==0xF1&&rx.Data[6]==0x90);
  REQUIRE(rx.ExtraDataIndex==rx.DataSize);
  REQUIRE(PassThruIoctl(iso,IO_CLEAR_MSG_FILTERS,0,0)==ERR_OK);
  REQUIRE(PassThruStopMsgFilter(iso,filter)==ERR_INVALID_FILTER_ID);
  send(iso,&msg);count=1;
  REQUIRE(PassThruReadMsgs(iso,&rx,&count,0)==ERR_BUFFER_EMPTY && count==0);
  REQUIRE(PassThruDisconnect(iso)==ERR_OK);
  REQUIRE(PassThruConnect(dev,PROTO_ISO15765,0,500000,&iso)==ERR_OK);
  send(iso,&msg);count=1;
  REQUIRE(PassThruReadMsgs(iso,&rx,&count,0)==ERR_BUFFER_EMPTY && count==0);
  /* Strict raw CAN: no PASS means no RX; BLOCK overrides PASS. */
  {
   const U8 raw_read[8]={3,0x22,0xF1,0x90,0,0,0,0};
   PASSTHRU_MSG rawmsg=frame(PROTO_CAN,0x7E0,raw_read,8);
   send(can,&rawmsg);count=1;
   REQUIRE(PassThruReadMsgs(can,&rx,&count,0)==ERR_BUFFER_EMPTY && count==0);
   REQUIRE(PassThruStartMsgFilter(can,1,&canmask,&canpattern,0,&allow)==ERR_OK);
   REQUIRE(PassThruStartMsgFilter(can,2,&canmask,&canpattern,0,&block)==ERR_OK);
   send(can,&rawmsg);count=1;
   REQUIRE(PassThruReadMsgs(can,&rx,&count,0)==ERR_BUFFER_EMPTY && count==0);
   REQUIRE(PassThruStopMsgFilter(can,block)==ERR_OK);
   send(can,&rawmsg);rx=readmsg(can);
   REQUIRE(rx.Data[4]==0x10);
   REQUIRE(PassThruStopMsgFilter(can,allow)==ERR_OK);
   canmask.DataSize=12;canpattern.DataSize=12;
   for(U32 j=4;j<12;j++){canmask.Data[j]=0;canpattern.Data[j]=0;}
   canmask.Data[4]=0xFF;canpattern.Data[4]=0x10;
   REQUIRE(PassThruStartMsgFilter(can,1,&canmask,&canpattern,0,&allow)==ERR_OK);
   send(can,&rawmsg);rx=readmsg(can);
   REQUIRE(rx.Data[4]==0x10);
   REQUIRE(PassThruStopMsgFilter(can,allow)==ERR_OK);
  }
  REQUIRE(PassThruDisconnect(can)==ERR_OK);
  REQUIRE(PassThruDisconnect(iso)==ERR_OK);
  g_iso_rx_start=old_start;
  g_strict_j2534_filters=0;
  REQUIRE(g_strict_j2534_filters==0);
 }
 test_stage42_multiecu_fc(dev);
 test_stage43_iso_rx_boundaries(dev);
 REQUIRE(PassThruClose(dev)==ERR_OK);
 /* Existing B9FB 13-frame/READ128 and privacy tests are retained. */
 REQUIRE(strstr(backend_lines,"\"format\":\"virtualcar-backend-v1\"")!=NULL);
 REQUIRE(event_count("\"kind\":\"tx_received\"")>0);
 REQUIRE(event_count("\"kind\":\"route_selected\"")>0);
 REQUIRE(strstr(backend_lines,"\"reason\":\"missing_profile\"")!=NULL);
 REQUIRE(event_count("\"kind\":\"rx_queued\"")>0);
 REQUIRE(event_count("\"kind\":\"rx_dequeued\"")>0);
 REQUIRE(event_count("\"outcome\":\"responded\"")>0);
 REQUIRE(strstr(backend_lines,"YV1CZ0002A0000001")==NULL);
 REQUIRE(strstr(backend_lines,"SIM-CEM")==NULL);
 REQUIRE(strstr(backend_lines,"\"can_id\"")==NULL);
 puts("PASS: 0.3.6.6 142-byte F106, ECU nodes, recorded bus fixtures, FC140, P3/VDASH, read-only");return 0;
}


