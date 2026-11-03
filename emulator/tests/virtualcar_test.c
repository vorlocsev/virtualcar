/* Linux host-side protocol test, with Win32 APIs stubbed. */
#define HOST_TEST 1
#include "../src/virtualcar.c"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static U32 tick=0;static I64 qpc_offset_us=0;
static int test_can_ps_config_probe_ini=0;
static const char *test_can_ps_api_outcome_ini="0";
static const char *test_can_ps_a6_selector_ini="0";
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
 if(strcmp(s,"Diagnostics")==0 && strcmp(k,"EnableCanPsConfigProbe")==0)
    d=test_can_ps_config_probe_ini?"1":"0";
 if(strcmp(s,"Diagnostics")==0 && strcmp(k,"CanPsApiOutcomeMask")==0)
    d=test_can_ps_api_outcome_ini;
 if(strcmp(s,"Diagnostics")==0 && strcmp(k,"EnableCanPsA6SelectorProbe")==0)
    d=test_can_ps_a6_selector_ini;
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
long InterlockedCompareExchange(volatile long*dst,long exchange,long compare){long v=*dst;if(v==compare)*dst=exchange;return v;}
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
 /* 3: optional J2534-2 pin-switch protocols are rejected by default,
    never treated as automatic aliases for ordinary CAN/ISO15765. */
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
  static const U32 settings[]={3u,23u,30u,31u,CONFIG_J1962_PINS,0xAA55AA55u};
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

/* Eight groups for opt-in configuration observation, NOT CAN_PS transport.
   No PS request is dispatched and no ECU/profile response may be generated. */
static void test_can_ps_config_probe(U32 *dev){
 U32 ps=0,other=0,std=0,n,output=0xC0DEFACEu,k;
 SCONFIG option={CONFIG_J1962_PINS,0};SCONFIG_LIST list={1,&option};
 PASSTHRU_MSG msg,rx,before_rx;
 const U8 opaque[]={0xDE,0xAD,0xBE,0xEF,0xFA,0xCE,0,0};
 const char *before;U32 saved_backend_len;
 capture_connect_log=1;connect_log_len=0;connect_log_lines[0]=0;
 /* 1: real INI opt-in, validation, output pointer preservation and capacity. */
 REQUIRE(g_can_ps_config_probe==0);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&output)==ERR_INVALID_PROTOCOL_ID);
 REQUIRE(output==0xC0DEFACEu);
 REQUIRE(PassThruClose(*dev)==ERR_OK);
 test_can_ps_config_probe_ini=1;tick+=7;
 REQUIRE(PassThruOpen(0,dev)==ERR_OK&&g_can_ps_config_probe==1);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,0)==ERR_NULL_PARAMETER);
 REQUIRE(PassThruConnect(*dev+1,PROTO_CAN_PS,0,125000,&output)==ERR_INVALID_DEVICE_ID);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0x40,125000,&output)==ERR_INVALID_FLAGS);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0x20000000u,125000,&output)==ERR_INVALID_FLAGS);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,250000,&output)==ERR_INVALID_BAUDRATE);
 REQUIRE(PassThruConnect(*dev,0x8005u,0,125000,&output)==ERR_INVALID_PROTOCOL_ID);
 REQUIRE(output==0xC0DEFACEu);
 {
  U32 ids[MAX_CHANNELS];static const U32 flags[]={0,0x100u,0x800u,0x900u};
  for(k=0;k<MAX_CHANNELS;k++){
   REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,flags[k%4],k<4?125000u:500000u,&ids[k])==ERR_OK);
   REQUIRE(channel(ids[k])->protocol==PROTO_CAN_PS&&channel(ids[k])->can_ps_observed_pins==0);
  }
  REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&output)==ERR_EXCEEDED_LIMIT);
  REQUIRE(output==0xC0DEFACEu);
  for(k=0;k<MAX_CHANNELS;k++)REQUIRE(PassThruDisconnect(ids[k])==ERR_OK);
 }
 /* 2: known hints only, GET zero, idempotence, rejected rebind and atomic lists. */
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0x900,500000,&ps)==ERR_OK);
 option.Value=0xBADu;REQUIRE(PassThruIoctl(ps,IO_GET_CONFIG,&list,0)==ERR_OK&&option.Value==0);
 {
  static const U32 invalid[]={0u,0x0303u,0x030Bu|0x10000u,0xDEADBEEFu};
  for(k=0;k<sizeof(invalid)/sizeof(invalid[0]);k++){
   option.Value=invalid[k];
   REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&list,0)==ERR_INVALID_IOCTL_VALUE);
   REQUIRE(channel(ps)->can_ps_observed_pins==0);
  }
 }
 option.Value=0x030B;REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&list,0)==ERR_OK);
 REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&list,0)==ERR_OK);
 option.Value=0;REQUIRE(PassThruIoctl(ps,IO_GET_CONFIG,&list,0)==ERR_OK&&option.Value==0x030B);
 option.Value=0x060E;REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&list,0)==ERR_NOT_SUPPORTED);
 REQUIRE(channel(ps)->can_ps_observed_pins==0x030B);
 {
  SCONFIG settings[2]={{1u,125000u},{CONFIG_J1962_PINS,0xDEADBEEFu}};
  SCONFIG_LIST pair={2,settings};
  REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&pair,0)==ERR_INVALID_IOCTL_VALUE);
  REQUIRE(channel(ps)->baud==500000u&&channel(ps)->can_ps_observed_pins==0x030B);
  settings[1].Parameter=779u;before=connect_log_lines+connect_log_len;
  REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&pair,0)==ERR_NOT_SUPPORTED);
  REQUIRE(channel(ps)->baud==500000u&&channel(ps)->can_ps_observed_pins==0x030B);
  REQUIRE(strstr(before,"00 00 00 07 00 00 00 00 00 00 00 01")!=NULL);
  settings[0].Value=0xAABBCCDDu;settings[1].Parameter=779u;
  REQUIRE(PassThruIoctl(ps,IO_GET_CONFIG,&pair,0)==ERR_NOT_SUPPORTED);
  REQUIRE(settings[0].Value==0xAABBCCDDu);
 }
 option.Parameter=1;option.Value=250000;
 before=connect_log_lines+connect_log_len;
 REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&list,0)==ERR_INVALID_BAUDRATE&&channel(ps)->baud==500000);
 REQUIRE(strstr(before,"00 00 00 07 00 00 00 01 00 00 00 19")!=NULL);
 option.Parameter=779u;option.Value=0xDEADBEEFu;
 REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&list,0)==ERR_NOT_SUPPORTED);
 REQUIRE(PassThruDisconnect(ps)==ERR_OK);
 /* 3: neither configured nor unconfigured reads can pump or deliver RX,
    including deliberately seeded internal state from every source class. */
 for(k=0;k<2;k++){
  CHANNEL *ch;U32 saved_passive=g_passive_enabled,saved_trace_count=g_trace_count;
  TRACE_FRAME saved_trace=g_trace[0];U32 bridge_tx=g_vehicle_bridge.inspected_tx;
  REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&ps)==ERR_OK);ch=channel(ps);
  option.Parameter=CONFIG_J1962_PINS;option.Value=0x030B;
  if(k)REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&list,0)==ERR_OK);
  g_passive_enabled=1;g_trace_count=1;bytes_zero(&g_trace[0],sizeof(g_trace[0]));
  g_trace[0].enabled=1;g_trace[0].baud=125000;g_trace[0].period_ms=1;
  ch->count=1;ch->w=1;ch->queue[0]=frame(PROTO_CAN_PS,0x555,opaque,8);
  ch->d2_count=1;ch->d2_response_id=0x00800003;ch->d2_next_us=now_us();
  ch->pending_len=20;ch->pending_cf_active=1;ch->pending_cf_credit=1;
  ch->periodic[0].used=1;ch->periodic[0].next_us=now_us();ch->periodic[0].interval_ms=5;
  ch->periodic[0].msg=frame(PROTO_CAN_PS,0x7DF,opaque,8);
  memset(&rx,0xA5,sizeof(rx));before_rx=rx;saved_backend_len=backend_len;
  n=1;REQUIRE(PassThruReadMsgs(ps,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0);
  n=1;REQUIRE(PassThruReadMsgs(ps,&rx,&n,3)==ERR_TIMEOUT&&n==0);
  REQUIRE(memcmp(&rx,&before_rx,sizeof(rx))==0);
  REQUIRE(ch->count==1&&ch->d2_pos==0&&ch->pending_pos==0);
  REQUIRE(ch->periodic[0].next_us<=now_us());
  REQUIRE(backend_len==saved_backend_len&&g_vehicle_bridge.inspected_tx==bridge_tx);
  g_passive_enabled=saved_passive;g_trace_count=saved_trace_count;g_trace[0]=saved_trace;
  REQUIRE(PassThruDisconnect(ps)==ERR_OK);
 }
 /* 4: transport APIs reject every message/protocol with no output IDs,
    no backend root, no filter/periodic registration and no raw payload log. */
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0x900,125000,&ps)==ERR_OK);
 msg=frame(PROTO_CAN_PS,0x000FFFFE,opaque,8);saved_backend_len=backend_len;
 for(k=0;k<2;k++){
  msg.ProtocolID=k?PROTO_CAN:PROTO_CAN_PS;n=1;
  REQUIRE(PassThruWriteMsgs(ps,&msg,&n,0)==ERR_NOT_SUPPORTED&&n==0);
  n=0;REQUIRE(PassThruWriteMsgs(ps,&msg,&n,0)==ERR_NOT_SUPPORTED&&n==0);
  output=0xC0DEFACEu;
  REQUIRE(PassThruStartMsgFilter(ps,1,&msg,&msg,0,&output)==ERR_NOT_SUPPORTED);
  REQUIRE(output==0xC0DEFACEu);
  REQUIRE(PassThruStartPeriodicMsg(ps,&msg,&output,k?0u:5u)==ERR_NOT_SUPPORTED);
  REQUIRE(output==0xC0DEFACEu);
 }
 REQUIRE(channel(ps)->filters_count==0&&channel(ps)->periodic[0].used==0);
 REQUIRE(backend_len==saved_backend_len);
 REQUIRE(PassThruDisconnect(ps)==ERR_OK);
 /* 5: remembered hints and baud are channel-local and do not alter standard CAN. */
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&ps)==ERR_OK);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,500000,&other)==ERR_OK);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN,0,500000,&std)==ERR_OK);
 option.Parameter=CONFIG_J1962_PINS;option.Value=0x030B;
 REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&list,0)==ERR_OK);
 REQUIRE(channel(other)->can_ps_observed_pins==0&&channel(std)->can_ps_observed_pins==0);
 option.Value=0x060E;REQUIRE(PassThruIoctl(other,IO_SET_CONFIG,&list,0)==ERR_OK);
 option.Parameter=1;option.Value=500000;REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&list,0)==ERR_OK);
 REQUIRE(channel(ps)->can_ps_observed_pins==0x030B&&channel(other)->can_ps_observed_pins==0x060E);
 option.Value=125000;REQUIRE(PassThruIoctl(std,IO_SET_CONFIG,&list,0)==ERR_OK);
 REQUIRE(channel(ps)->baud==500000&&channel(other)->baud==500000&&channel(std)->baud==125000);
 REQUIRE(PassThruDisconnect(ps)==ERR_OK&&PassThruDisconnect(other)==ERR_OK&&PassThruDisconnect(std)==ERR_OK);
 /* 6: disconnect/reuse and device Close/Open erase every remembered hint. */
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&ps)==ERR_OK);
 option.Parameter=CONFIG_J1962_PINS;option.Value=0x030B;
 REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&list,0)==ERR_OK);
 REQUIRE(PassThruDisconnect(ps)==ERR_OK);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&other)==ERR_OK&&other==ps);
 REQUIRE(channel(other)->can_ps_observed_pins==0&&channel(other)->count==0);
 option.Value=0x060E;REQUIRE(PassThruIoctl(other,IO_SET_CONFIG,&list,0)==ERR_OK);
 REQUIRE(PassThruClose(*dev)==ERR_OK);tick+=7;REQUIRE(PassThruOpen(0,dev)==ERR_OK);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&ps)==ERR_OK);
 REQUIRE(channel(ps)->can_ps_observed_pins==0);
 /* 7: fixed metadata operations, accepted legacy no-ops and strict redaction.
    0x8001 is J1962_PINS; decimal779 stays an unknown legacy parameter. */
 option.Parameter=CONFIG_J1962_PINS;option.Value=0x030B;
 REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&list,0)==ERR_OK);
 option.Value=0;REQUIRE(PassThruIoctl(ps,IO_GET_CONFIG,&list,0)==ERR_OK&&option.Value==0x030B);
 option.Parameter=23;option.Value=80;REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&list,0)==ERR_OK);
 option.Value=99;REQUIRE(PassThruIoctl(ps,IO_GET_CONFIG,&list,0)==ERR_OK&&option.Value==0);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN,0,500000,&std)==ERR_OK);
 before=connect_log_lines+connect_log_len;
 option.Parameter=CONFIG_J1962_PINS;option.Value=0x030B;
 REQUIRE(PassThruIoctl(std,IO_SET_CONFIG,&list,0)==ERR_OK);
 REQUIRE(strstr(before,"00 00 80 01 00 00 03 0B 00 00 00 00")!=NULL);
 REQUIRE(strstr(before,"CAN_PS config probe")==NULL);
 option.Parameter=779u;option.Value=0xDEADBEEFu;before=connect_log_lines+connect_log_len;
 REQUIRE(PassThruIoctl(std,IO_SET_CONFIG,&list,0)==ERR_OK);
 REQUIRE(strstr(before,"00 00 00 00 00 00 00 00 00 00 00 00")!=NULL);
 REQUIRE(strstr(connect_log_lines,"DE AD BE EF")==NULL);
 REQUIRE(strstr(connect_log_lines,"FA CE")==NULL);
 REQUIRE(strstr(connect_log_lines,"YV1")==NULL);
 REQUIRE(event_count_since(connect_log_lines,"CAN_PS config probe")>20);
 for(k=1;k<=7;k++){
  char op[180];snprintf(op,sizeof(op),"J2534 CAN_PS config probe channel/operation/value/status (BE) 00 00 00 01 00 00 00 %02X",(unsigned)k);
  REQUIRE(strstr(connect_log_lines,op)!=NULL);
 }
 REQUIRE(PassThruDisconnect(ps)==ERR_OK&&PassThruDisconnect(std)==ERR_OK);
 /* 8: standard ISO15765 and existing synthetic B9FB replay remain intact;
    the next Open without opt-in rejects PS again. */
 REQUIRE(PassThruConnect(*dev,PROTO_ISO15765,0,500000,&std)==ERR_OK);
 {const U8 vin[]={0x22,0xF1,0x90};msg=frame(PROTO_ISO15765,0x7E0,vin,3);send(std,&msg);rx=readmsg(std);
  REQUIRE(rx.ProtocolID==PROTO_ISO15765&&rx.DataSize==24&&rx.Data[4]==0x62);}
 REQUIRE(PassThruDisconnect(std)==ERR_OK);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN,0,125000,&std)==ERR_OK);
 {const U8 fb[]={0xCB,0x40,0xB9,0xFB,0,0,0,0};msg=frame(PROTO_CAN,0x000FFFFE,fb,8);send(std,&msg);rx=readmsg(std);
  REQUIRE(rx.ProtocolID==PROTO_CAN&&rx.DataSize==12&&rx.Data[4]==0xCC&&rx.Data[5]==0x40);}
 REQUIRE(PassThruDisconnect(std)==ERR_OK);
 REQUIRE(PassThruClose(*dev)==ERR_OK);test_can_ps_config_probe_ini=0;tick+=7;
 REQUIRE(PassThruOpen(0,dev)==ERR_OK&&g_can_ps_config_probe==0);
 output=0xC0DEFACEu;
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&output)==ERR_INVALID_PROTOCOL_ID&&output==0xC0DEFACEu);
 capture_connect_log=0;
 puts("PASS: eight CAN_PS configuration-probe groups, no transport or ECU response");
}

static void require_ps_rejected(U32 id,U32 origin,const PASSTHRU_MSG *msg,U32 input_count,
                                U32 pins,U32 protocol,U32 shape,U32 check){
 static const char marker[]="J2534 CAN_PS rejected attempt channel/origin/pins/msg-protocol/shape/check/status (BE)";
 U32 fields[7]={id,origin,pins,protocol,shape,check,ERR_NOT_SUPPORTED};
 U32 n=input_count,output=0xC0DEFACEu,k,saved_backend=backend_len,serial=g_backend_serial;
 char expected[256];const char *line;PASSTHRU_MSG before;
 if(input_count==1u)before=*msg;
 capture_connect_log=1;connect_log_len=0;connect_log_lines[0]=0;
 if(origin==1u)REQUIRE(PassThruWriteMsgs(id,msg,&n,0)==ERR_NOT_SUPPORTED&&n==0u);
 else REQUIRE(PassThruStartPeriodicMsg(id,msg,&output,0)==ERR_NOT_SUPPORTED&&output==0xC0DEFACEu);
 if(input_count==1u)REQUIRE(memcmp(msg,&before,sizeof(before))==0);
 snprintf(expected,sizeof(expected),"%s ",marker);
 for(k=0;k<7u;k++){
  size_t pos=strlen(expected);U32 v=fields[k];
  snprintf(expected+pos,sizeof(expected)-pos,"%02X %02X %02X %02X ",
           (unsigned)(v>>24),(unsigned)((v>>16)&255u),(unsigned)((v>>8)&255u),(unsigned)(v&255u));
 }
 line=strstr(connect_log_lines,expected);REQUIRE(line!=0);
 REQUIRE(strncmp(line+strlen(expected),"\r\n",2)==0);
 REQUIRE(event_count_since(connect_log_lines,marker)==1u);
 REQUIRE(strstr(connect_log_lines,"TX context")==0&&strstr(connect_log_lines,"TX (app request)")==0);
 REQUIRE(strstr(connect_log_lines,"DE AD BE EF")==0&&strstr(connect_log_lines,"FA CE")==0);
 REQUIRE(strstr(connect_log_lines,"00 0F FF FE")==0&&strstr(connect_log_lines,"18 DA 50 F1")==0);
 REQUIRE(strstr(connect_log_lines,"YV1")==0);
 REQUIRE(backend_len==saved_backend&&g_backend_serial==serial);
}

/* Eight groups for bounded metadata about API calls that remain rejected.
   All candidates below are synthetic lexical envelopes, not vehicle traces. */
static void test_can_ps_rejected_attempts(U32 *dev){
 static const struct {U32 id,shape;U8 data[8];} candidate[]={
  {0x7DFu,1u,{2,9,2,0,0,0,0,0}}, {0x7E0u,2u,{2,9,2,0,0,0,0,0}},
  {0x7DFu,3u,{2,0x3E,0x80,0,0,0,0,0}}, {0x18DB33F1u,4u,{2,0x3E,0x80,0,0,0,0,0}},
  {0xFFFFEu,10u,{0xCF,0x40,0xA3,0xDE,0xAD,0xBE,0xEF,0xFA}},
  {0xFFFFEu,11u,{0xCD,0x40,0xA6,0xDE,0xAD,1,0,0}},
  {0xFFFFEu,12u,{0xCB,0x40,0xB9,0xF0,0,0,0,0}},
  {0xFFFFEu,13u,{0xCB,0x40,0xB9,0xFB,0,0,0,0}},
  {0xFFFFEu,14u,{0xCB,0x40,0xB9,0xFC,0,0,0,0}},
  {0xFFFFEu,15u,{0xCF,0x50,0xA3,0xDE,0xAD,0xBE,0xEF,0xFA}},
  {0xFFFFEu,16u,{0xCD,0x50,0xA6,0xDE,0xAD,1,0,0}},
  {0xFFFFEu,17u,{0xCB,0x50,0xB9,0xF0,0,0,0,0}},
  {0xFFFFEu,18u,{0xCB,0x50,0xB9,0xFB,0,0,0,0}},
  {0xFFFFEu,19u,{0xCB,0x50,0xB9,0xFC,0,0,0,0}},
  {0x726u,20u,{3,0x22,0xF1,0x14,0,0,0,0}},
  {0x726u,21u,{3,0x22,0xF1,0xB0,0,0,0,0}},
  {0x726u,22u,{3,0x22,0xF1,0xA3,0,0,0,0}},
  {0x726u,23u,{3,0x22,0xF1,0x06,0,0,0,0}},
  {0x726u,24u,{3,0x22,0xF1,0x90,0,0,0,0}},
  {0x18DA50F1u,25u,{3,0x22,0xF1,0x14,0,0,0,0}},
  {0x18DA50F1u,26u,{3,0x22,0xF1,0xB0,0,0,0,0}},
  {0x18DA50F1u,27u,{3,0x22,0xF1,0xA3,0,0,0,0}},
  {0x18DA50F1u,28u,{3,0x22,0xF1,0x06,0,0,0,0}},
  {0x18DA50F1u,29u,{3,0x22,0xF1,0x90,0,0,0,0}}
 };
 U32 ps=0,other=0,third=0,std=0,k,j,n,output,serial,backend_before;
 SCONFIG option={CONFIG_J1962_PINS,0};SCONFIG_LIST list={1,&option};
 PASSTHRU_MSG msg,rx,before_rx;const U8 zeros[8]={0};
 REQUIRE(g_can_ps_config_probe==0u);
 REQUIRE(PassThruClose(*dev)==ERR_OK);test_can_ps_config_probe_ini=1;tick+=7;
 REQUIRE(PassThruOpen(0,dev)==ERR_OK&&g_can_ps_config_probe==1u);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0x900u,125000,&ps)==ERR_OK);
 /* 1: every exact candidate, with distinct CAN and CAN_PS declarations. */
 for(k=0;k<sizeof(candidate)/sizeof(candidate[0]);k++){
  U32 protocol=(k&1u)?PROTO_CAN_PS:PROTO_CAN;
  msg=frame(protocol,candidate[k].id,candidate[k].data,8);
  msg.TxFlags=candidate[k].id>0x7FFu?0x100u:0u;
  require_ps_rejected(ps,1u,&msg,1u,0u,protocol,candidate[k].shape,0u);
 }
 msg=frame(PROTO_CAN,0xFFFFEu,candidate[7].data,8);msg.TxFlags=0x100u;
 require_ps_rejected(ps,1u,&msg,1u,0u,PROTO_CAN,13u,0u);
 /* 2: bounded inspection, strict address/flag matching and near misses.
    Supported protocol takes precedence over size, then ID, then flags. */
 {
  static const U32 bad_size[]={0u,4u,13u,MAX_DATA,0xFFFFFFFFu};
  static const U32 bad_protocol[]={PROTO_ISO15765,0u,0xDEADBEEFu};
  static const U32 bad_id[]={0x20000000u,0xFFFFFFFFu};
  static const U32 near_miss[]={0u,3u,4u,5u,7u,14u,19u};
  static const struct {U32 id,flags;} bad_flags[]={
   {0x7DFu,0x100u},{0x18DB33F1u,0u},{0x7DFu,0x800u},
   {0x18DB33F1u,0x900u},{0x18DB33F1u,0x140u},{0x7DFu,0xDEADBEEFu}
  };
  for(k=0;k<sizeof(bad_size)/sizeof(bad_size[0]);k++){
   msg=frame(PROTO_CAN_PS,0x7DFu,candidate[0].data,8);msg.DataSize=bad_size[k];
   require_ps_rejected(ps,1u,&msg,1u,0u,PROTO_CAN_PS,0u,1u);
  }
  for(k=0;k<sizeof(bad_protocol)/sizeof(bad_protocol[0]);k++){
   msg=frame(bad_protocol[k],0x7DFu,candidate[0].data,8);msg.DataSize=0xFFFFFFFFu;
   require_ps_rejected(ps,1u,&msg,1u,0u,bad_protocol[k]==PROTO_ISO15765?PROTO_ISO15765:0u,0u,3u);
  }
  for(k=0;k<sizeof(bad_id)/sizeof(bad_id[0]);k++){
   msg=frame(PROTO_CAN,bad_id[k],zeros,8);msg.TxFlags=0x100u;
   require_ps_rejected(ps,1u,&msg,1u,0u,PROTO_CAN,0u,2u);
  }
  for(k=0;k<sizeof(bad_flags)/sizeof(bad_flags[0]);k++){
   msg=frame(PROTO_CAN,bad_flags[k].id,candidate[2].data,8);msg.TxFlags=bad_flags[k].flags;
   require_ps_rejected(ps,1u,&msg,1u,0u,PROTO_CAN,0u,4u);
  }
  for(k=5u;k<=12u;k++){
   msg=frame(PROTO_CAN,0x7FFu,zeros,8);msg.DataSize=k;
   require_ps_rejected(ps,1u,&msg,1u,0u,PROTO_CAN,0u,0u);
  }
  msg=frame(PROTO_CAN,0x1FFFFFFFu,zeros,8);msg.TxFlags=0x100u;
  require_ps_rejected(ps,1u,&msg,1u,0u,PROTO_CAN,0u,0u);
  for(j=0;j<sizeof(near_miss)/sizeof(near_miss[0]);j++){
   k=near_miss[j];
   msg=frame(PROTO_CAN,candidate[k].id,candidate[k].data,7);msg.TxFlags=candidate[k].id>0x7FFu?0x100u:0u;
   require_ps_rejected(ps,1u,&msg,1u,0u,PROTO_CAN,0u,0u);
   if(candidate[k].shape!=10u&&candidate[k].shape!=15u){
    msg.DataSize=12;msg.Data[11]=1;
    require_ps_rejected(ps,1u,&msg,1u,0u,PROTO_CAN,0u,0u);
   }
  }
  msg=frame(PROTO_CAN,0xFFFFEu,candidate[7].data,8);msg.TxFlags=0x100u;msg.Data[5]=0x60;
  require_ps_rejected(ps,1u,&msg,1u,0u,PROTO_CAN,0u,0u);
 }
 /* 3: zero/batch/huge counts never dereference even the first message.
    Existing null-pointer failures emit no observation and preserve count. */
 {
  static const U32 count[]={0u,2u,64u,0xFFFFFFFFu};
  const PASSTHRU_MSG *unreadable=(const PASSTHRU_MSG *)(size_t)1u;
  for(k=0;k<sizeof(count)/sizeof(count[0]);k++)
   require_ps_rejected(ps,1u,unreadable,count[k],0u,0u,0u,k?6u:5u);
  connect_log_len=0;connect_log_lines[0]=0;n=7u;
  REQUIRE(PassThruWriteMsgs(ps,0,&n,0)==ERR_NULL_PARAMETER&&n==7u);
  REQUIRE(PassThruWriteMsgs(ps,unreadable,0,0)==ERR_NULL_PARAMETER);
  REQUIRE(strstr(connect_log_lines,"CAN_PS rejected attempt")==0);
 }
 /* 4: periodic registration has its own origin, preserves caller output,
    and observes before the same rejection even with an invalid interval. */
 msg=frame(PROTO_CAN_PS,0xFFFFEu,candidate[7].data,8);msg.TxFlags=0x100u;
 require_ps_rejected(ps,2u,&msg,1u,0u,PROTO_CAN_PS,13u,0u);
 msg.ProtocolID=PROTO_CAN;require_ps_rejected(ps,2u,&msg,1u,0u,PROTO_CAN,13u,0u);
 msg.ProtocolID=PROTO_ISO15765;require_ps_rejected(ps,2u,&msg,1u,0u,PROTO_ISO15765,0u,3u);
 msg.ProtocolID=PROTO_CAN;msg.DataSize=13;
 require_ps_rejected(ps,2u,&msg,1u,0u,PROTO_CAN,0u,1u);
 connect_log_len=0;connect_log_lines[0]=0;output=0xC0DEFACEu;
 REQUIRE(PassThruStartPeriodicMsg(ps,0,&output,5)==ERR_NULL_PARAMETER&&output==0xC0DEFACEu);
 REQUIRE(PassThruStartPeriodicMsg(ps,&msg,0,5)==ERR_NULL_PARAMETER);
 REQUIRE(strstr(connect_log_lines,"CAN_PS rejected attempt")==0);
 REQUIRE(channel(ps)->periodic[0].used==0u);
 /* 5: channel-local remembered hints, including the unconfigured channel,
    never become routing or change declared protocol. */
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,500000,&other)==ERR_OK);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&third)==ERR_OK);
 option.Value=0x030Bu;REQUIRE(PassThruIoctl(other,IO_SET_CONFIG,&list,0)==ERR_OK);
 option.Value=0x060Eu;REQUIRE(PassThruIoctl(third,IO_SET_CONFIG,&list,0)==ERR_OK);
 msg=frame(PROTO_CAN,0x726u,candidate[14].data,8);
 for(k=1u;k<=2u;k++){
  require_ps_rejected(ps,k,&msg,1u,0u,PROTO_CAN,20u,0u);
  require_ps_rejected(other,k,&msg,1u,0x030Bu,PROTO_CAN,20u,0u);
  require_ps_rejected(third,k,&msg,1u,0x060Eu,PROTO_CAN,20u,0u);
 }
 REQUIRE(channel(ps)->can_ps_observed_pins==0u&&channel(other)->can_ps_observed_pins==0x030Bu);
 REQUIRE(channel(third)->can_ps_observed_pins==0x060Eu);
 REQUIRE(PassThruDisconnect(other)==ERR_OK&&PassThruDisconnect(third)==ERR_OK);
 /* 6: coarse exclusion categories disclose no control/security operands.
    D8 stays an unverified prefix; incomplete SF and changed D8 are unknown. */
 {
  static const U8 services[]={0x10,0x11,0x27,0x2E,0x31,0x34,0x36,0x37,0x85};
  U8 payload[8]={3,0,0xDE,0xAD,0xBE,0xEF,0xFA,0xCE};
  for(k=0;k<sizeof(services);k++)for(j=0;j<2u;j++){
   payload[1]=services[k];payload[2]=j?0x11:0xDE;payload[3]=j?0x22:0xAD;
   msg=frame(PROTO_CAN,j?0x1234567u:0x7E0u,payload,8);msg.TxFlags=j?0x100u:0u;
   require_ps_rejected(ps,1u,&msg,1u,0u,PROTO_CAN,40u,0u);
  }
  payload[0]=1;payload[1]=0x27;msg=frame(PROTO_CAN,0x7E0u,payload,2);
  require_ps_rejected(ps,2u,&msg,1u,0u,PROTO_CAN,40u,0u);
  payload[0]=7;msg=frame(PROTO_CAN,0x7E0u,payload,7);
  require_ps_rejected(ps,1u,&msg,1u,0u,PROTO_CAN,0u,0u);
  payload[0]=0x17;msg=frame(PROTO_CAN,0x7E0u,payload,8);
  require_ps_rejected(ps,1u,&msg,1u,0u,PROTO_CAN,0u,0u);
  payload[0]=0xFF;payload[1]=0xC8;msg=frame(PROTO_CAN,0xFFFFEu,payload,8);msg.TxFlags=0x100u;
  require_ps_rejected(ps,1u,&msg,1u,0u,PROTO_CAN,41u,0u);
  msg=frame(PROTO_CAN_PS,0xFFFFEu,zeros,8);msg.TxFlags=0x100u;msg.Data[4]=0xD8;
  require_ps_rejected(ps,1u,&msg,1u,0u,PROTO_CAN_PS,42u,0u);
  msg.Data[11]=1;require_ps_rejected(ps,1u,&msg,1u,0u,PROTO_CAN_PS,0u,0u);
 }
 /* 7: no RX, backend root/serial, bridge, dispatch, queue or scheduler effect;
    accepted standard CAN and ISO paths still produce their existing results. */
 {
  CHANNEL *ch=channel(ps),*snapshot=(CHANNEL *)malloc(sizeof(*snapshot));
  U32 bridge_tx=g_vehicle_bridge.inspected_tx;
  REQUIRE(snapshot!=0);ch->count=1;ch->w=1;ch->queue[0]=frame(PROTO_CAN_PS,0x555u,zeros,8);
  ch->d2_count=1;ch->d2_next_us=now_us();ch->pending_len=20;ch->pending_cf_active=1;
  ch->periodic[0].used=1;ch->periodic[0].interval_ms=5;ch->periodic[0].next_us=now_us();
  *snapshot=*ch;msg=frame(PROTO_CAN,0xFFFFEu,candidate[7].data,8);msg.TxFlags=0x100u;
  serial=g_backend_serial;backend_before=backend_len;
  require_ps_rejected(ps,1u,&msg,1u,0u,PROTO_CAN,13u,0u);
  require_ps_rejected(ps,2u,&msg,1u,0u,PROTO_CAN,13u,0u);
  memset(&rx,0xA5,sizeof(rx));before_rx=rx;n=1;
  REQUIRE(PassThruReadMsgs(ps,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);
  REQUIRE(memcmp(&rx,&before_rx,sizeof(rx))==0&&memcmp(ch,snapshot,sizeof(*snapshot))==0);
  REQUIRE(g_vehicle_bridge.inspected_tx==bridge_tx&&backend_len==backend_before&&g_backend_serial==serial);
  free(snapshot);
 }
 REQUIRE(PassThruDisconnect(ps)==ERR_OK);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN,0,125000,&std)==ERR_OK);
 connect_log_len=0;connect_log_lines[0]=0;
 msg=frame(PROTO_CAN,0xFFFFEu,candidate[7].data,8);send(std,&msg);rx=readmsg(std);
 REQUIRE(rx.ProtocolID==PROTO_CAN&&rx.Data[4]==0xCC&&rx.Data[5]==0x40);
 REQUIRE(strstr(connect_log_lines,"CAN_PS rejected attempt")==0);
 REQUIRE(PassThruDisconnect(std)==ERR_OK);
 REQUIRE(PassThruConnect(*dev,PROTO_ISO15765,0,500000,&std)==ERR_OK);
 {const U8 request[]={0x22,0xF1,0x90};msg=frame(PROTO_ISO15765,0x7E0u,request,3);send(std,&msg);rx=readmsg(std);
  REQUIRE(rx.ProtocolID==PROTO_ISO15765&&rx.DataSize==24u&&rx.Data[4]==0x62u);}
 REQUIRE(strstr(connect_log_lines,"CAN_PS rejected attempt")==0);
 REQUIRE(PassThruDisconnect(std)==ERR_OK);
 /* 8: lifecycle erases hints, unknown internal values stay redacted, and
    default-off plus invalid-channel calls cannot emit rejected observations. */
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&ps)==ERR_OK);
 option.Value=0x030Bu;REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&list,0)==ERR_OK);
 REQUIRE(PassThruDisconnect(ps)==ERR_OK);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&other)==ERR_OK&&other==ps);
 msg=frame(PROTO_CAN_PS,0x7DFu,candidate[0].data,8);
 require_ps_rejected(other,1u,&msg,1u,0u,PROTO_CAN_PS,1u,0u);
 channel(other)->can_ps_observed_pins=0xDEADBEEFu;
 require_ps_rejected(other,1u,&msg,1u,0u,PROTO_CAN_PS,1u,0u);
 REQUIRE(PassThruClose(*dev)==ERR_OK);tick+=7;REQUIRE(PassThruOpen(0,dev)==ERR_OK);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&ps)==ERR_OK);
 require_ps_rejected(ps,2u,&msg,1u,0u,PROTO_CAN_PS,1u,0u);
 REQUIRE(PassThruClose(*dev)==ERR_OK);test_can_ps_config_probe_ini=0;tick+=7;
 REQUIRE(PassThruOpen(0,dev)==ERR_OK&&g_can_ps_config_probe==0u);
 connect_log_len=0;connect_log_lines[0]=0;output=0xC0DEFACEu;
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&output)==ERR_INVALID_PROTOCOL_ID&&output==0xC0DEFACEu);
 n=1;REQUIRE(PassThruWriteMsgs(ps,&msg,&n,0)==ERR_INVALID_CHANNEL_ID&&n==1u);
 REQUIRE(PassThruStartPeriodicMsg(ps,&msg,&output,5)==ERR_INVALID_CHANNEL_ID&&output==0xC0DEFACEu);
 REQUIRE(strstr(connect_log_lines,"CAN_PS rejected attempt")==0);
 capture_connect_log=0;
 puts("PASS: eight CAN_PS rejected-attempt groups, metadata only and unchanged rejection");
}

static const char ps_filter_marker[]="J2534 CAN_PS rejected filter channel/type/protocols/sizes/flags/flow/mask/pattern/status (BE)";
static const char ps_periodic_marker[]="J2534 CAN_PS rejected periodic channel/protocol/interval/check/status (BE)";
static const char *require_ps_metadata(const char *marker,const U32 *fields,U32 count){
 char expected[256];U32 k;const char *line;
 snprintf(expected,sizeof(expected),"%s ",marker);
 for(k=0;k<count;k++){
  size_t pos=strlen(expected);U32 v=fields[k];
  snprintf(expected+pos,sizeof(expected)-pos,"%02X %02X %02X %02X ",
           (unsigned)(v>>24),(unsigned)((v>>16)&255u),(unsigned)((v>>8)&255u),(unsigned)(v&255u));
 }
 line=strstr(connect_log_lines,expected);REQUIRE(line!=0);
 REQUIRE(strncmp(line+strlen(expected),"\r\n",2)==0);
 REQUIRE(event_count_since(connect_log_lines,marker)==1u);
 REQUIRE(strstr(connect_log_lines,"DE AD BE EF")==0&&strstr(connect_log_lines,"FA CE")==0);
 REQUIRE(strstr(connect_log_lines,"TX context")==0&&strstr(connect_log_lines,"TX (app request)")==0);
 REQUIRE(strstr(connect_log_lines,"  filter mask")==0&&strstr(connect_log_lines,"  filter pattern")==0);
 REQUIRE(strstr(connect_log_lines,"  flow control")==0&&strstr(connect_log_lines,"YV1")==0);
 return line;
}
static void require_ps_filter(U32 id,U32 type,const PASSTHRU_MSG *mask,const PASSTHRU_MSG *pattern,
                              const PASSTHRU_MSG *flow,U32 protocols,U32 sizes,U32 flags,U32 mask_kind,U32 pattern_kind){
 U32 fields[9]={id,type>=1u&&type<=3u?type:0u,protocols,sizes,flags,flow?1u:0u,mask_kind,pattern_kind,ERR_NOT_SUPPORTED};
 U32 output=0xC0DEFACEu,serial=g_backend_serial,backend_before=backend_len;
 PASSTHRU_MSG before_mask=*mask,before_pattern=*pattern;const char *line,*old;
 capture_connect_log=1;connect_log_len=0;connect_log_lines[0]=0;
 REQUIRE(PassThruStartMsgFilter(id,type,mask,pattern,flow,&output)==ERR_NOT_SUPPORTED&&output==0xC0DEFACEu);
 REQUIRE(memcmp(mask,&before_mask,sizeof(*mask))==0&&memcmp(pattern,&before_pattern,sizeof(*pattern))==0);
 line=require_ps_metadata(ps_filter_marker,fields,9u);
 old=strstr(connect_log_lines,"J2534 CAN_PS config probe channel/operation/value/status (BE)");
 REQUIRE(old!=0&&line<old&&event_count_since(connect_log_lines,"CAN_PS config probe")==1u);
 REQUIRE(strstr(connect_log_lines,"CAN_PS rejected periodic")==0&&strstr(connect_log_lines,"CAN_PS rejected attempt")==0);
 REQUIRE(backend_len==backend_before&&g_backend_serial==serial);
}
static void require_ps_periodic(U32 id,const PASSTHRU_MSG *msg,U32 interval,U32 protocol,U32 value,U32 check){
 U32 fields[5]={id,protocol,value,check,ERR_NOT_SUPPORTED};
 U32 output=0xC0DEFACEu,serial=g_backend_serial,backend_before=backend_len;
 PASSTHRU_MSG before=*msg;const char *line,*attempt,*old;
 capture_connect_log=1;connect_log_len=0;connect_log_lines[0]=0;
 REQUIRE(PassThruStartPeriodicMsg(id,msg,&output,interval)==ERR_NOT_SUPPORTED&&output==0xC0DEFACEu);
 REQUIRE(memcmp(msg,&before,sizeof(before))==0);
 line=require_ps_metadata(ps_periodic_marker,fields,5u);
 attempt=strstr(connect_log_lines,"J2534 CAN_PS rejected attempt channel/origin/pins/msg-protocol/shape/check/status (BE)");
 old=strstr(connect_log_lines,"J2534 CAN_PS config probe channel/operation/value/status (BE)");
 REQUIRE(attempt!=0&&old!=0&&line<attempt&&attempt<old);
 REQUIRE(event_count_since(connect_log_lines,"CAN_PS rejected attempt")==1u);
 REQUIRE(event_count_since(connect_log_lines,"CAN_PS config probe")==1u);
 REQUIRE(strstr(connect_log_lines,ps_filter_marker)==0);
 REQUIRE(backend_len==backend_before&&g_backend_serial==serial);
}

/* Eight synthetic groups for the arguments of rejected setup calls. This is
   observation only: no filter, timer, CAN dispatch or ECU answer is enabled. */
static void test_can_ps_rejected_setup(U32 *dev){
 U32 ps=0,std=0,k,n,output=0xC0DEFACEu,handle;
 PASSTHRU_MSG mask,pattern,msg,rx,before_rx;const U8 zeros[8]={0};
 /* 1: default-off and rejection precedence remain intact; known and unknown
    filter types all retain ERR_NOT_SUPPORTED once a PS channel exists. */
 REQUIRE(g_can_ps_config_probe==0u);
 capture_connect_log=1;connect_log_len=0;connect_log_lines[0]=0;
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&output)==ERR_INVALID_PROTOCOL_ID&&output==0xC0DEFACEu);
 REQUIRE(strstr(connect_log_lines,ps_filter_marker)==0&&strstr(connect_log_lines,ps_periodic_marker)==0);
 REQUIRE(PassThruClose(*dev)==ERR_OK);test_can_ps_config_probe_ini=1;tick+=7;
 REQUIRE(PassThruOpen(0,dev)==ERR_OK&&g_can_ps_config_probe==1u);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&ps)==ERR_OK);
 mask=frame(PROTO_CAN_PS,0xFFFFFFFFu,0,0);pattern=frame(PROTO_CAN_PS,0u,0,0);
 {static const U32 type[]={1u,2u,3u,0u,4u,0xDEADBEEFu};
  for(k=0;k<sizeof(type)/sizeof(type[0]);k++)require_ps_filter(ps,type[k],&mask,&pattern,0,1u,1u,1u,2u,1u);}
 /* 2: every known protocol pairing; unknown declarations are redacted and
    only same raw-CAN declarations permit ID-only body classification. */
 {
  static const struct {U32 mask_protocol,pattern_protocol,pair;} protocol[]={
   {PROTO_CAN_PS,PROTO_CAN_PS,1u},{PROTO_CAN,PROTO_CAN,2u},{PROTO_ISO15765,PROTO_ISO15765,3u},
   {PROTO_CAN_PS,PROTO_CAN,4u},{PROTO_CAN,PROTO_CAN_PS,4u},
   {PROTO_CAN_PS,PROTO_ISO15765,4u},{PROTO_ISO15765,PROTO_CAN_PS,4u},
   {PROTO_CAN,PROTO_ISO15765,4u},{PROTO_ISO15765,PROTO_CAN,4u},
   {0u,PROTO_CAN_PS,0u},{PROTO_CAN,0xDEADBEEFu,0u},{0xDEADBEEFu,0xDEADBEEFu,0u}
  };
  for(k=0;k<sizeof(protocol)/sizeof(protocol[0]);k++){
   mask=frame(protocol[k].mask_protocol,0xDEADBEEFu,0,0);
   pattern=frame(protocol[k].pattern_protocol,0x20000000u,0,0);
   require_ps_filter(ps,1u,&mask,&pattern,0,protocol[k].pair,1u,1u,
                     protocol[k].pair==1u||protocol[k].pair==2u?5u:0u,
                     protocol[k].pair==1u||protocol[k].pair==2u?4u:0u);
  }
 }
 /* 3: descriptor lengths are finite categories, never exported numbers.
    Equal non-ID lengths, unequal valid lengths and both bounds stay opaque. */
 {
  static const struct {U32 mask_size,pattern_size,category;} size[]={
   {4u,4u,1u},{12u,12u,2u},{5u,5u,3u},{11u,11u,3u},
   {4u,12u,4u},{12u,4u,4u},{5u,11u,4u},
   {3u,4u,0u},{4u,13u,0u},{0xFFFFFFFFu,4u,0u},{0u,0u,0u}
  };
  for(k=0;k<sizeof(size)/sizeof(size[0]);k++){
   mask=frame(PROTO_CAN_PS,0xFFFFFFFFu,zeros,8);pattern=frame(PROTO_CAN_PS,0u,zeros,8);
   mask.DataSize=size[k].mask_size;pattern.DataSize=size[k].pattern_size;
   require_ps_filter(ps,2u,&mask,&pattern,0,1u,size[k].category,1u,
                     size[k].category==1u?2u:0u,size[k].category==1u?1u:0u);
  }
 }
 /* 4: filter TxFlags are header categories, independent of mask and pattern
    interpretation. Mixed allowed flags and unsupported bits remain distinct. */
 {
  static const struct {U32 mask_flags,pattern_flags,category;} flags[]={
   {0u,0u,1u},{0x100u,0x100u,2u},{0u,0x100u,3u},{0x100u,0u,3u},
   {0x800u,0u,0u},{0x100u,0x900u,0u},{0xDEADBEEFu,0x100u,0u}
  };
  mask=frame(PROTO_CAN,0xFFFFFFFFu,0,0);pattern=frame(PROTO_CAN,0u,0,0);
  for(k=0;k<sizeof(flags)/sizeof(flags[0]);k++){
   mask.TxFlags=flags[k].mask_flags;pattern.TxFlags=flags[k].pattern_flags;
   require_ps_filter(ps,3u,&mask,&pattern,0,2u,1u,flags[k].category,2u,1u);
  }
 }
 /* 5: FFFFFFFF is a valid exact-mask category, not an out-of-range ID.
    Only four bytes are observed; a non-null flow pointer is never read. */
 {
  static const struct {U32 mask_value,pattern_value,mask_kind,pattern_kind;} value[]={
   {0u,0u,1u,1u},{0xFFFFFFFFu,0x7FFu,2u,2u},{0x1FFFFFFFu,0x800u,3u,3u},
   {0x7FFu,0x1FFFFFFFu,4u,3u},{0xDEADBEEFu,0x20000000u,5u,4u},
   {1u,0xFFFFFFFFu,5u,4u},{0u,1u,1u,2u}
  };
  const PASSTHRU_MSG *unreadable_flow=(const PASSTHRU_MSG *)(size_t)1u;
  for(k=0;k<sizeof(value)/sizeof(value[0]);k++){
   mask=frame(PROTO_CAN_PS,value[k].mask_value,0,0);pattern=frame(PROTO_CAN_PS,value[k].pattern_value,0,0);
   memset(mask.Data+4,0xDE,8);memset(pattern.Data+4,0xFA,8);
   require_ps_filter(ps,3u,&mask,&pattern,unreadable_flow,1u,1u,1u,value[k].mask_kind,value[k].pattern_kind);
  }
 }
 /* 6: only the fixed interval allowlist is exported. Other valid values and
    invalid bounds are separate checks, with unknown protocol/size redacted. */
 {
  static const U32 allowed[]={5u,100u,250u,500u,1000u,2000u,4000u,5000u,10000u,60000u};
  static const struct {U32 interval,check;} other_interval[]={
   {6u,1u},{12345u,1u},{59999u,1u},{0u,2u},{1u,2u},{4u,2u},{60001u,2u},{0xFFFFFFFFu,2u}
  };
  static const U32 protocol[]={PROTO_CAN,PROTO_ISO15765,PROTO_CAN_PS,0xDEADBEEFu};
  msg=frame(PROTO_CAN_PS,0xFFFFEu,zeros,8);msg.Data[4]=0xD8;msg.TxFlags=0x100u;
  for(k=0;k<sizeof(allowed)/sizeof(allowed[0]);k++)require_ps_periodic(ps,&msg,allowed[k],PROTO_CAN_PS,allowed[k],0u);
  for(k=0;k<sizeof(other_interval)/sizeof(other_interval[0]);k++)
   require_ps_periodic(ps,&msg,other_interval[k].interval,PROTO_CAN_PS,0u,other_interval[k].check);
  for(k=0;k<sizeof(protocol)/sizeof(protocol[0]);k++){
   msg.ProtocolID=protocol[k];msg.DataSize=0xDEADBEEFu;
   require_ps_periodic(ps,&msg,4000u,k==3u?0u:protocol[k],4000u,0u);
  }
 }
 /* 7: errors preserve outputs, message bytes, registration counters and all
    channel state. Null and invalid-channel calls cannot emit new markers. */
 {
  CHANNEL *ch=channel(ps),*snapshot=(CHANNEL *)malloc(sizeof(*snapshot));
  U32 filters=g_filter_counter,periodics=g_periodic_counter,serial=g_backend_serial;
  U32 backend_before=backend_len,bridge_tx=g_vehicle_bridge.inspected_tx;
  REQUIRE(snapshot!=0);ch->count=1;ch->w=1;ch->queue[0]=frame(PROTO_CAN_PS,0x555u,zeros,8);
  *snapshot=*ch;mask=frame(PROTO_CAN_PS,0xFFFFFFFFu,0,0);pattern=frame(PROTO_CAN_PS,0u,0,0);
  msg=frame(PROTO_CAN_PS,0xFFFFEu,zeros,8);msg.Data[4]=0xD8;msg.TxFlags=0x100u;
  require_ps_filter(ps,1u,&mask,&pattern,0,1u,1u,1u,2u,1u);
  require_ps_periodic(ps,&msg,4000u,PROTO_CAN_PS,4000u,0u);
  memset(&rx,0xA5,sizeof(rx));before_rx=rx;n=1u;
  REQUIRE(PassThruReadMsgs(ps,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);
  REQUIRE(memcmp(&rx,&before_rx,sizeof(rx))==0&&memcmp(ch,snapshot,sizeof(*snapshot))==0);
  REQUIRE(g_filter_counter==filters&&g_periodic_counter==periodics&&g_backend_serial==serial);
  REQUIRE(backend_len==backend_before&&g_vehicle_bridge.inspected_tx==bridge_tx);free(snapshot);
  connect_log_len=0;connect_log_lines[0]=0;output=0xC0DEFACEu;
  REQUIRE(PassThruStartMsgFilter(ps,1u,0,&pattern,0,&output)==ERR_NULL_PARAMETER&&output==0xC0DEFACEu);
  REQUIRE(PassThruStartMsgFilter(ps,1u,&mask,0,0,&output)==ERR_NULL_PARAMETER&&output==0xC0DEFACEu);
  REQUIRE(PassThruStartMsgFilter(ps,1u,&mask,&pattern,0,0)==ERR_NULL_PARAMETER);
  REQUIRE(PassThruStartPeriodicMsg(ps,0,&output,4000u)==ERR_NULL_PARAMETER&&output==0xC0DEFACEu);
  REQUIRE(PassThruStartPeriodicMsg(ps,&msg,0,4000u)==ERR_NULL_PARAMETER);
  REQUIRE(PassThruStartMsgFilter(MAX_CHANNELS+1u,0u,&mask,&pattern,0,&output)==ERR_INVALID_CHANNEL_ID&&output==0xC0DEFACEu);
  REQUIRE(PassThruStartPeriodicMsg(MAX_CHANNELS+1u,&msg,&output,0u)==ERR_INVALID_TIME_INTERVAL&&output==0xC0DEFACEu);
  msg.DataSize=0u;
  REQUIRE(PassThruStartPeriodicMsg(MAX_CHANNELS+1u,&msg,&output,4000u)==ERR_INVALID_MSG&&output==0xC0DEFACEu);
  msg.DataSize=12u;
  REQUIRE(PassThruStartPeriodicMsg(MAX_CHANNELS+1u,&msg,&output,4000u)==ERR_INVALID_CHANNEL_ID&&output==0xC0DEFACEu);
  REQUIRE(strstr(connect_log_lines,ps_filter_marker)==0&&strstr(connect_log_lines,ps_periodic_marker)==0);
 }
 /* 8: standard CAN still installs/stops filters and periodic registrations;
    disconnect/Open erases PS state and the next default-off rejects it. */
 REQUIRE(PassThruDisconnect(ps)==ERR_OK);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN,0,125000,&std)==ERR_OK);
 mask=frame(PROTO_CAN,0xFFFFFFFFu,0,0);pattern=frame(PROTO_CAN,0u,0,0);handle=0u;
 connect_log_len=0;connect_log_lines[0]=0;
 REQUIRE(PassThruStartMsgFilter(std,1u,&mask,&pattern,0,&handle)==ERR_OK&&handle!=0u);
 REQUIRE(channel(std)->filters_count==1u&&PassThruStopMsgFilter(std,handle)==ERR_OK);
 msg=frame(PROTO_CAN,0x555u,zeros,8);handle=0u;
 REQUIRE(PassThruStartPeriodicMsg(std,&msg,&handle,5u)==ERR_OK&&handle!=0u);
 REQUIRE(PassThruStopPeriodicMsg(std,handle)==ERR_OK);
 REQUIRE(strstr(connect_log_lines,ps_filter_marker)==0&&strstr(connect_log_lines,ps_periodic_marker)==0);
 REQUIRE(PassThruDisconnect(std)==ERR_OK);
 REQUIRE(PassThruClose(*dev)==ERR_OK);test_can_ps_config_probe_ini=0;tick+=7;
 REQUIRE(PassThruOpen(0,dev)==ERR_OK&&g_can_ps_config_probe==0u);
 output=0xC0DEFACEu;REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&output)==ERR_INVALID_PROTOCOL_ID&&output==0xC0DEFACEu);
 capture_connect_log=0;
 puts("PASS: eight CAN_PS rejected-setup groups, bounded arguments and no registrations");
}

static const char ps_api_marker[]="J2534 CAN_PS API outcome channel/mask/operation/pins/baud/shape/status (BE)";
static void ps_api_reset_log(void){capture_connect_log=1;connect_log_len=0;connect_log_lines[0]=0;}
static void require_ps_api(U32 id,U32 mode,U32 operation,U32 pins,U32 baud,U32 shape,U32 status){
 U32 fields[7]={id,mode,operation,pins,baud,shape,status};
 const char *line=require_ps_metadata(ps_api_marker,fields,7u);
 if(operation>=2u&&operation<=4u){
  REQUIRE(event_count_since(connect_log_lines,"CAN_PS config probe")== (status==ERR_NOT_SUPPORTED?1u:0u));
  REQUIRE(event_count_since(connect_log_lines,"CAN_PS rejected filter")== (status==ERR_NOT_SUPPORTED&&operation==2u?1u:0u));
  REQUIRE(event_count_since(connect_log_lines,"CAN_PS rejected attempt")== (status==ERR_NOT_SUPPORTED&&operation!=2u?1u:0u));
  REQUIRE(event_count_since(connect_log_lines,"CAN_PS rejected periodic")== (status==ERR_NOT_SUPPORTED&&operation==4u?1u:0u));
  if(status==ERR_NOT_SUPPORTED)REQUIRE(line<strstr(connect_log_lines,"CAN_PS config probe"));
 }
}
static U32 ps_api_open(U32 *dev,const char *setting,U32 expected,U32 pins,U32 baud){
 U32 id=0;SCONFIG option={CONFIG_J1962_PINS,pins};SCONFIG_LIST list={1,&option};
 REQUIRE(PassThruClose(*dev)==ERR_OK);test_can_ps_config_probe_ini=1;test_can_ps_api_outcome_ini=setting;tick+=7;
 REQUIRE(PassThruOpen(0,dev)==ERR_OK&&g_can_ps_api_outcome_mask==expected);
 ps_api_reset_log();REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,baud,&id)==ERR_OK);
 REQUIRE(channel(id)->can_ps_api_outcome_mask==expected);
 require_ps_api(id,expected,1u,0u,baud,0u,ERR_OK);
 if(pins)REQUIRE(PassThruIoctl(id,IO_SET_CONFIG,&list,0)==ERR_OK);
 ps_api_reset_log();return id;
}
static U32 ps_api_filter_call(U32 id,U32 mode,U32 pins,U32 baud,U32 type,
                              PASSTHRU_MSG *mask,PASSTHRU_MSG *pattern,const PASSTHRU_MSG *flow,U32 shape,U32 expected){
 U32 output=0xC0DEFACEu;PASSTHRU_MSG before_mask=*mask,before_pattern=*pattern;ps_api_reset_log();
 REQUIRE(PassThruStartMsgFilter(id,type,mask,pattern,flow,&output)==expected);
 REQUIRE(memcmp(mask,&before_mask,sizeof(*mask))==0&&memcmp(pattern,&before_pattern,sizeof(*pattern))==0);
 REQUIRE(expected==ERR_OK?(output>0u&&output<0x7FFFFFFFu):output==0xC0DEFACEu);
 require_ps_api(id,mode,2u,pins,baud,shape,expected);return output;
}
static void ps_api_write_call(U32 id,U32 mode,U32 pins,U32 baud,const PASSTHRU_MSG *msg,U32 input,U32 shape,U32 expected){
 U32 n=input;PASSTHRU_MSG before;if(input==1u)before=*msg;
 ps_api_reset_log();REQUIRE(PassThruWriteMsgs(id,msg,&n,0)==expected);
 if(input==1u)REQUIRE(memcmp(msg,&before,sizeof(before))==0);
 REQUIRE(n==(expected==ERR_OK?1u:0u));require_ps_api(id,mode,3u,pins,baud,shape,expected);
}
static U32 ps_api_periodic_call(U32 id,U32 mode,U32 pins,U32 baud,PASSTHRU_MSG *msg,U32 interval,U32 shape,U32 expected){
 U32 output=0xC0DEFACEu;PASSTHRU_MSG before=*msg;ps_api_reset_log();
 REQUIRE(PassThruStartPeriodicMsg(id,msg,&output,interval)==expected);
 REQUIRE(memcmp(msg,&before,sizeof(before))==0);
 REQUIRE(expected==ERR_OK?(output>0u&&output<0x7FFFFFFFu):output==0xC0DEFACEu);
 require_ps_api(id,mode,4u,pins,baud,shape,expected);return output;
}
/* Eight synthetic groups for independent API outcomes. No success below is
   evidence of CAN transmission, an ECU response or a diagnostic readiness ACK. */
static void test_can_ps_api_outcomes(U32 *dev){
 U32 ps=0,other=0,std=0,k,j,n,filter_id,period_id,output;
 PASSTHRU_MSG mask=frame(PROTO_CAN_PS,0xFFFFFFFFu,0,0),pattern=frame(PROTO_CAN_PS,0u,0,0),msg,exact;
 const U8 d8[8]={0xD8,0,0,0,0,0,0,0};
 SCONFIG option={CONFIG_J1962_PINS,0x030Bu};SCONFIG_LIST list={1,&option};
 mask.TxFlags=pattern.TxFlags=0x100u;exact=frame(PROTO_CAN_PS,0xFFFFEu,d8,8);exact.TxFlags=0x100u;
 /* 1: strict single-character decimal opt-in, prerequisite, reload, and
    channel snapshots. Editing the INI does not alter an already-open device. */
 REQUIRE(PassThruClose(*dev)==ERR_OK);test_can_ps_api_outcome_ini="7";test_can_ps_config_probe_ini=0;tick+=7;
 REQUIRE(PassThruOpen(0,dev)==ERR_OK&&g_can_ps_api_outcome_mask==0u);
 output=0xC0DEFACEu;REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&output)==ERR_INVALID_PROTOCOL_ID&&output==0xC0DEFACEu);
 {static const char *invalid[]={"","8","-1","+1","01","7 "," 7","0x7","4294967297","99999999999999999999999999","2\n"};
  for(k=0;k<sizeof(invalid)/sizeof(invalid[0]);k++)ps=ps_api_open(dev,invalid[k],0u,0u,125000u);}
 ps=ps_api_open(dev,"3",3u,0x030Bu,125000u);test_can_ps_api_outcome_ini="7";
 ps_api_reset_log();REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&other)==ERR_OK);
 require_ps_api(other,3u,1u,0u,125000u,0u,ERR_OK);
 REQUIRE(channel(ps)->can_ps_api_outcome_mask==3u&&g_can_ps_api_outcome_mask==3u);
 ps=ps_api_open(dev,"7",7u,0x030Bu,125000u);
 /* 2: bits are independent, and exact shapes remain observable when a bit,
    remembered pin hint or current baud prevents API success. */
 for(k=0;k<8u;k++){
  static const char *setting[]={"0","1","2","3","4","5","6","7"};
  ps=ps_api_open(dev,setting[k],k,0x030Bu,125000u);
  ps_api_filter_call(ps,k,0x030Bu,125000u,1u,&mask,&pattern,0,1u,(k&1u)?ERR_OK:ERR_NOT_SUPPORTED);
  ps_api_write_call(ps,k,0x030Bu,125000u,&exact,1u,42u,(k&2u)?ERR_OK:ERR_NOT_SUPPORTED);
  ps_api_periodic_call(ps,k,0x030Bu,125000u,&exact,1000u,42u,(k&4u)?ERR_OK:ERR_NOT_SUPPORTED);
 }
 {static const struct {U32 pins,baud;} ineligible[]={{0u,125000u},{0x060Eu,125000u},{0x030Bu,500000u}};
  for(k=0;k<sizeof(ineligible)/sizeof(ineligible[0]);k++){
   ps=ps_api_open(dev,"7",7u,ineligible[k].pins,ineligible[k].baud);
   ps_api_filter_call(ps,7u,ineligible[k].pins,ineligible[k].baud,1u,&mask,&pattern,0,1u,ERR_NOT_SUPPORTED);
   ps_api_write_call(ps,7u,ineligible[k].pins,ineligible[k].baud,&exact,1u,42u,ERR_NOT_SUPPORTED);
   ps_api_periodic_call(ps,7u,ineligible[k].pins,ineligible[k].baud,&exact,1000u,42u,ERR_NOT_SUPPORTED);
  }}
 /* 3: PASS descriptors only, mask unrestricted as a bitmask, exact standard
    versus extended pattern bounds, and unsupported descriptors stay rejected. */
 ps=ps_api_open(dev,"1",1u,0x030Bu,125000u);
 {static const struct {U32 mask,id,flags,shape;} descriptor[]={
   {0u,0u,0u,1u},{0xFFFFFFFFu,0x7FFu,0u,1u},{0xDEADBEEFu,0u,0x100u,1u},
   {0xFFFFFFFFu,0x800u,0u,0u},{0u,0x1FFFFFFFu,0x100u,1u},
   {0xFFFFFFFFu,0x20000000u,0x100u,0u},{0u,0xFFFFFFFFu,0x100u,0u}};
  for(k=0;k<sizeof(descriptor)/sizeof(descriptor[0]);k++){
   mask=frame(PROTO_CAN_PS,descriptor[k].mask,0,0);pattern=frame(PROTO_CAN_PS,descriptor[k].id,0,0);
   mask.TxFlags=pattern.TxFlags=descriptor[k].flags;
   ps_api_filter_call(ps,1u,0x030Bu,125000u,1u,&mask,&pattern,0,descriptor[k].shape,descriptor[k].shape?ERR_OK:ERR_NOT_SUPPORTED);
  }}
 {U32 before=g_can_ps_filter_counter;
  for(k=0;k<10u;k++){
   U32 type=1u;const PASSTHRU_MSG *flow=0;
   mask=frame(PROTO_CAN_PS,0xFFFFFFFFu,0,0);pattern=frame(PROTO_CAN_PS,0u,0,0);mask.TxFlags=pattern.TxFlags=0x100u;
   switch(k){case 0:type=2u;break;case 1:type=3u;break;case 2:mask.ProtocolID=PROTO_CAN;break;
    case 3:pattern.ProtocolID=PROTO_ISO15765;break;case 4:mask.DataSize=12u;break;
    case 5:pattern.DataSize=3u;break;case 6:mask.TxFlags=0u;break;
    case 7:mask.TxFlags=pattern.TxFlags=0x900u;break;case 8:flow=(const PASSTHRU_MSG *)(size_t)1u;break;
    default:type=0xDEADBEEFu;break;}
   ps_api_filter_call(ps,1u,0x030Bu,125000u,type,&mask,&pattern,flow,0u,ERR_NOT_SUPPORTED);
  }
  REQUIRE(g_can_ps_filter_counter==before&&channel(ps)->filters_count==0u);}
 /* 4: only exact single D8 gets count1; zero/batch never dereference even
    msgs[0], and nearby protocol/flag/length/ID/padding forms remain rejected. */
 ps=ps_api_open(dev,"2",2u,0x030Bu,125000u);
 ps_api_write_call(ps,2u,0x030Bu,125000u,&exact,1u,42u,ERR_OK);
 for(k=0;k<11u;k++){
  msg=exact;switch(k){case 0:msg.ProtocolID=PROTO_CAN;break;case 1:msg.ProtocolID=PROTO_ISO15765;break;
   case 2:msg.ProtocolID=0xDEADBEEFu;break;case 3:msg.TxFlags=0u;break;case 4:msg.TxFlags=0x900u;break;
   case 5:msg.DataSize=11u;break;case 6:msg.DataSize=13u;break;case 7:msg.DataSize=0xFFFFFFFFu;break;
   case 8:msg.Data[3]=0xFF;break;case 9:msg.Data[4]=0xD9;break;default:msg.Data[11]=1u;break;}
  ps_api_write_call(ps,2u,0x030Bu,125000u,&msg,1u,0u,ERR_NOT_SUPPORTED);
 }
 {static const U32 count[]={0u,2u,64u,0xFFFFFFFFu};
  for(k=0;k<sizeof(count)/sizeof(count[0]);k++)
   ps_api_write_call(ps,2u,0x030Bu,125000u,(const PASSTHRU_MSG *)(size_t)1u,count[k],0u,ERR_NOT_SUPPORTED);}
 ps_api_reset_log();n=7u;
 REQUIRE(PassThruWriteMsgs(ps,0,&n,0)==ERR_NULL_PARAMETER&&n==7u);
 REQUIRE(PassThruWriteMsgs(ps,&exact,0,0)==ERR_NULL_PARAMETER);
 REQUIRE(PassThruWriteMsgs(MAX_CHANNELS+1u,&exact,&n,0)==ERR_INVALID_CHANNEL_ID&&n==7u);
 REQUIRE(strstr(connect_log_lines,ps_api_marker)==0);
 /* 5: periodic registration requires exactly1000ms and exact D8; it stores
    only a handle, no generic PERIODIC/message/deadline or delivery state. */
 ps=ps_api_open(dev,"4",4u,0x030Bu,125000u);
 period_id=ps_api_periodic_call(ps,4u,0x030Bu,125000u,&exact,1000u,42u,ERR_OK);
 REQUIRE(channel(ps)->can_ps_periodic_handles[0]==period_id);
 {static const U32 interval[]={0u,5u,999u,1001u,4000u,60000u,60001u,0xFFFFFFFFu};
  for(k=0;k<sizeof(interval)/sizeof(interval[0]);k++)ps_api_periodic_call(ps,4u,0x030Bu,125000u,&exact,interval[k],0u,ERR_NOT_SUPPORTED);}
 for(k=0;k<3u;k++){
  msg=exact;if(k==0u)msg.ProtocolID=PROTO_CAN;else if(k==1u)msg.DataSize=4u;else msg.Data[5]=1u;
  ps_api_periodic_call(ps,4u,0x030Bu,125000u,&msg,1000u,0u,ERR_NOT_SUPPORTED);
 }
 for(k=0;k<MAX_PERIODIC;k++)REQUIRE(channel(ps)->periodic[k].used==0u&&channel(ps)->periodic[k].next_us==0u);
 /* 6: local capacities, API/channel scope, stale handles, cleanup after baud
    changes, persistent counters and fail-closed positive31-bit exhaustion. */
 ps=ps_api_open(dev,"7",7u,0x030Bu,125000u);
 mask=frame(PROTO_CAN_PS,0xFFFFFFFFu,0,0);pattern=frame(PROTO_CAN_PS,0u,0,0);mask.TxFlags=pattern.TxFlags=0x100u;
 for(k=0;k<MAX_FILTERS;k++)ps_api_filter_call(ps,7u,0x030Bu,125000u,1u,&mask,&pattern,0,1u,ERR_OK);
 filter_id=channel(ps)->can_ps_filter_handles[3];
 ps_api_filter_call(ps,7u,0x030Bu,125000u,1u,&mask,&pattern,0,1u,ERR_EXCEEDED_LIMIT);
 ps_api_filter_call(ps,7u,0x030Bu,125000u,2u,&mask,&pattern,0,0u,ERR_NOT_SUPPORTED);
 ps_api_reset_log();REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&other)==ERR_OK);
 ps_api_reset_log();REQUIRE(PassThruStopMsgFilter(other,filter_id)==ERR_INVALID_FILTER_ID);
 require_ps_api(other,7u,5u,0u,125000u,0u,ERR_INVALID_FILTER_ID);
 ps_api_reset_log();REQUIRE(PassThruStopPeriodicMsg(ps,filter_id)==ERR_INVALID_MSG_ID);
 require_ps_api(ps,7u,6u,0x030Bu,125000u,0u,ERR_INVALID_MSG_ID);
 option.Parameter=1u;option.Value=500000u;REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&list,0)==ERR_OK);
 ps_api_reset_log();REQUIRE(PassThruStopMsgFilter(ps,filter_id)==ERR_OK);
 require_ps_api(ps,7u,5u,0x030Bu,500000u,0u,ERR_OK);
 ps_api_reset_log();REQUIRE(PassThruStopMsgFilter(ps,filter_id)==ERR_INVALID_FILTER_ID);
 require_ps_api(ps,7u,5u,0x030Bu,500000u,0u,ERR_INVALID_FILTER_ID);
 ps_api_reset_log();REQUIRE(PassThruIoctl(ps,IO_CLEAR_MSG_FILTERS,0,0)==ERR_OK);
 require_ps_api(ps,7u,7u,0x030Bu,500000u,0u,ERR_OK);
 option.Value=125000u;REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&list,0)==ERR_OK);
 for(k=0;k<MAX_PERIODIC;k++)ps_api_periodic_call(ps,7u,0x030Bu,125000u,&exact,1000u,42u,ERR_OK);
 period_id=channel(ps)->can_ps_periodic_handles[0];
 ps_api_periodic_call(ps,7u,0x030Bu,125000u,&exact,1000u,42u,ERR_EXCEEDED_LIMIT);
 option.Value=500000u;REQUIRE(PassThruIoctl(ps,IO_SET_CONFIG,&list,0)==ERR_OK);
 ps_api_reset_log();REQUIRE(PassThruStopPeriodicMsg(ps,period_id)==ERR_OK);
 require_ps_api(ps,7u,6u,0x030Bu,500000u,0u,ERR_OK);
 ps_api_reset_log();REQUIRE(PassThruIoctl(ps,IO_CLEAR_PERIODIC_MSGS,0,0)==ERR_OK);
 require_ps_api(ps,7u,8u,0x030Bu,500000u,0u,ERR_OK);
 {U32 fc=g_can_ps_filter_counter,pc=g_can_ps_periodic_counter;
  ps=ps_api_open(dev,"7",7u,0x030Bu,125000u);REQUIRE(g_can_ps_filter_counter==fc&&g_can_ps_periodic_counter==pc);
  ps_api_reset_log();REQUIRE(PassThruStopMsgFilter(ps,filter_id)==ERR_INVALID_FILTER_ID);
  require_ps_api(ps,7u,5u,0x030Bu,125000u,0u,ERR_INVALID_FILTER_ID);
  ps_api_reset_log();REQUIRE(PassThruStopPeriodicMsg(ps,period_id)==ERR_INVALID_MSG_ID);
  require_ps_api(ps,7u,6u,0x030Bu,125000u,0u,ERR_INVALID_MSG_ID);
  for(j=0;j<2u;j++){
   U32 *counter=j?&g_can_ps_periodic_counter:&g_can_ps_filter_counter;*counter=0x7FFFFFFEu;
   if(j)REQUIRE(ps_api_periodic_call(ps,7u,0x030Bu,125000u,&exact,1000u,42u,ERR_OK)==0x7FFFFFFEu);
   else REQUIRE(ps_api_filter_call(ps,7u,0x030Bu,125000u,1u,&mask,&pattern,0,1u,ERR_OK)==0x7FFFFFFEu);
   REQUIRE(*counter==0x7FFFFFFFu);
   if(j)ps_api_periodic_call(ps,7u,0x030Bu,125000u,&exact,1000u,42u,ERR_EXCEEDED_LIMIT);
   else ps_api_filter_call(ps,7u,0x030Bu,125000u,1u,&mask,&pattern,0,1u,ERR_EXCEEDED_LIMIT);
   REQUIRE(*counter==0x7FFFFFFFu);*counter=0u;
   if(j)ps_api_periodic_call(ps,7u,0x030Bu,125000u,&exact,1000u,42u,ERR_EXCEEDED_LIMIT);
   else ps_api_filter_call(ps,7u,0x030Bu,125000u,1u,&mask,&pattern,0,1u,ERR_EXCEEDED_LIMIT);
   REQUIRE(*counter==0u);
  }
  /* Restore fault-injected globals; no public API can reset these counters. */
  g_can_ps_filter_counter=fc;g_can_ps_periodic_counter=pc;
 }
 filter_id=ps_api_filter_call(ps,7u,0x030Bu,125000u,1u,&mask,&pattern,0,1u,ERR_OK);
 period_id=ps_api_periodic_call(ps,7u,0x030Bu,125000u,&exact,1000u,42u,ERR_OK);
 REQUIRE(PassThruDisconnect(ps)==ERR_OK);ps_api_reset_log();
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000u,&other)==ERR_OK&&other==ps);
 require_ps_api(other,7u,1u,0u,125000u,0u,ERR_OK);ps=other;
 ps_api_reset_log();REQUIRE(PassThruStopMsgFilter(ps,filter_id)==ERR_INVALID_FILTER_ID);
 require_ps_api(ps,7u,5u,0u,125000u,0u,ERR_INVALID_FILTER_ID);
 ps_api_reset_log();REQUIRE(PassThruStopPeriodicMsg(ps,period_id)==ERR_INVALID_MSG_ID);
 require_ps_api(ps,7u,6u,0u,125000u,0u,ERR_INVALID_MSG_ID);
 /* 7: forced generic state cannot be pumped. API-only changes are confined
    to PS handle slots; clear leaves generic filters/timers and all RX intact. */
 ps=ps_api_open(dev,"7",7u,0x030Bu,125000u);
 {
  CHANNEL *ch=channel(ps),*snapshot=(CHANNEL *)malloc(sizeof(*snapshot));PASSTHRU_MSG rx,before_rx;
  U32 serial=g_backend_serial,backend_before=backend_len,bridge_tx=g_vehicle_bridge.inspected_tx;
  U32 standard_filters=g_filter_counter,standard_periodics=g_periodic_counter;
  REQUIRE(snapshot!=0);ch->filters_count=1;ch->filters[0].id=123u;
  ch->periodic[0].used=1;ch->periodic[0].id=456u;ch->periodic[0].interval_ms=5u;
  ch->periodic[0].next_us=now_us();ch->periodic[0].msg=exact;
  ch->count=1;ch->w=1;ch->queue[0]=exact;ch->d2_count=1;ch->pending_len=20;memcpy(snapshot,ch,sizeof(*snapshot));
  filter_id=ps_api_filter_call(ps,7u,0x030Bu,125000u,1u,&mask,&pattern,0,1u,ERR_OK);
  ps_api_write_call(ps,7u,0x030Bu,125000u,&exact,1u,42u,ERR_OK);
  period_id=ps_api_periodic_call(ps,7u,0x030Bu,125000u,&exact,1000u,42u,ERR_OK);
  snapshot->can_ps_filter_handles[0]=filter_id;snapshot->can_ps_periodic_handles[0]=period_id;
  pump_periodic(ch);memset(&rx,0xA5,sizeof(rx));before_rx=rx;n=1u;
  REQUIRE(PassThruReadMsgs(ps,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);
  REQUIRE(memcmp(&rx,&before_rx,sizeof(rx))==0&&memcmp(ch,snapshot,sizeof(*snapshot))==0);
  ps_api_reset_log();REQUIRE(PassThruIoctl(ps,IO_CLEAR_MSG_FILTERS,0,0)==ERR_OK);
  require_ps_api(ps,7u,7u,0x030Bu,125000u,0u,ERR_OK);
  ps_api_reset_log();REQUIRE(PassThruIoctl(ps,IO_CLEAR_PERIODIC_MSGS,0,0)==ERR_OK);
  require_ps_api(ps,7u,8u,0x030Bu,125000u,0u,ERR_OK);
  memset(snapshot->can_ps_filter_handles,0,sizeof(snapshot->can_ps_filter_handles));
  memset(snapshot->can_ps_periodic_handles,0,sizeof(snapshot->can_ps_periodic_handles));
  REQUIRE(memcmp(ch,snapshot,sizeof(*snapshot))==0);free(snapshot);
  REQUIRE(g_backend_serial==serial&&backend_len==backend_before&&g_vehicle_bridge.inspected_tx==bridge_tx);
  REQUIRE(g_filter_counter==standard_filters&&g_periodic_counter==standard_periodics);
 }
 /* 8: unknown metadata stays redacted; mode0 cleanup keeps its old behavior,
    standard registrations remain independent, and the final Open disables PS. */
 channel(ps)->can_ps_observed_pins=0xDEADBEEFu;channel(ps)->baud=0xDEADBEEFu;
 ps_api_write_call(ps,7u,0u,0u,&exact,1u,42u,ERR_NOT_SUPPORTED);
 ps=ps_api_open(dev,"0",0u,0x030Bu,125000u);
 ps_api_write_call(ps,0u,0x030Bu,125000u,&exact,1u,42u,ERR_NOT_SUPPORTED);
 channel(ps)->filters_count=1;channel(ps)->filters[0].id=123u;
 channel(ps)->periodic[0].used=1;channel(ps)->periodic[0].id=456u;
 ps_api_reset_log();REQUIRE(PassThruStopMsgFilter(ps,123u)==ERR_OK&&PassThruStopPeriodicMsg(ps,456u)==ERR_OK);
 channel(ps)->filters_count=1;channel(ps)->periodic[0].used=1;
 REQUIRE(PassThruIoctl(ps,IO_CLEAR_MSG_FILTERS,0,0)==ERR_OK&&PassThruIoctl(ps,IO_CLEAR_PERIODIC_MSGS,0,0)==ERR_OK);
 REQUIRE(channel(ps)->filters_count==0u&&channel(ps)->periodic[0].used==0u&&strstr(connect_log_lines,ps_api_marker)==0);
 REQUIRE(PassThruDisconnect(ps)==ERR_OK&&PassThruConnect(*dev,PROTO_CAN,0,125000,&std)==ERR_OK);
 {U32 fc=g_filter_counter,pc=g_periodic_counter;
  mask.ProtocolID=pattern.ProtocolID=PROTO_CAN;ps_api_reset_log();output=0u;
  REQUIRE(PassThruStartMsgFilter(std,1u,&mask,&pattern,0,&output)==ERR_OK&&output==fc&&g_filter_counter==fc+1u);
  REQUIRE(PassThruStopMsgFilter(std,output)==ERR_OK);msg=exact;msg.ProtocolID=PROTO_CAN;output=0u;
  REQUIRE(PassThruStartPeriodicMsg(std,&msg,&output,1000u)==ERR_OK&&output==pc&&g_periodic_counter==pc+1u);
  REQUIRE(PassThruStopPeriodicMsg(std,output)==ERR_OK&&strstr(connect_log_lines,ps_api_marker)==0);}
 REQUIRE(PassThruDisconnect(std)==ERR_OK&&PassThruClose(*dev)==ERR_OK);
 test_can_ps_config_probe_ini=0;test_can_ps_api_outcome_ini="0";tick+=7;
 REQUIRE(PassThruOpen(0,dev)==ERR_OK&&g_can_ps_api_outcome_mask==0u);
 capture_connect_log=0;
 puts("PASS: eight CAN_PS API-outcome groups, local handles only and no transmission");
}

static const char ps_a6_selector_marker[]="J2534 CAN_PS A6 selector channel/origin/pins/baud/protocol/target/selector/mask/status (BE)";
static U32 ps_selector_open(U32 *dev,const char *setting,const char *mask,U32 expected_mask,U32 pins,U32 baud){
 test_can_ps_a6_selector_ini=setting;
 return ps_api_open(dev,mask,expected_mask,pins,baud);
}
static PASSTHRU_MSG ps_selector_frame(U32 protocol,U32 target,U32 selector){
 U8 payload[8]={0xCD,0,0xA6,0,0,1,0,0};PASSTHRU_MSG msg;
 payload[1]=(U8)target;payload[3]=(U8)(selector>>8);payload[4]=(U8)selector;
 msg=frame(protocol,0xFFFFEu,payload,8);msg.TxFlags=0x100u;return msg;
}
static void ps_selector_call(U32 ps,U32 origin,PASSTHRU_MSG *msg,U32 observed,U32 pins,U32 baud,U32 selected,U32 mode){
 U32 output=0xC0DEFACEu,n=1u;PASSTHRU_MSG before=*msg;ps_api_reset_log();
 if(origin==1u)REQUIRE(PassThruWriteMsgs(ps,msg,&n,0)==ERR_NOT_SUPPORTED&&n==0u);
 else REQUIRE(PassThruStartPeriodicMsg(ps,msg,&output,1000u)==ERR_NOT_SUPPORTED&&output==0xC0DEFACEu);
 REQUIRE(memcmp(msg,&before,sizeof(before))==0);
 if(observed){
  U32 fields[9]={ps,origin,pins,baud,msg->ProtocolID,(U32)msg->Data[5],selected,mode,ERR_NOT_SUPPORTED};
  require_ps_metadata(ps_a6_selector_marker,fields,9u);
  REQUIRE(event_count_since(connect_log_lines,ps_a6_selector_marker)==1u);
 }else REQUIRE(strstr(connect_log_lines,ps_a6_selector_marker)==0);
 REQUIRE(event_count_since(connect_log_lines,"CAN_PS rejected attempt")==1u);
}
/* Eight synthetic groups. Catalog selectors identify request bytes only;
   no parameter meaning, reply or diagnostic readiness is assigned. */
static void test_can_ps_a6_selectors(U32 *dev){
 U32 ps=0,other=0,std=0,k,j,t,n,output,serial,before_backend,bridge;
 PASSTHRU_MSG msg,changed,rx,before_rx;SCONFIG option={CONFIG_J1962_PINS,0x030Bu};SCONFIG_LIST list={1,&option};
 /* 1: strict independent opt-in, master prerequisite and Open snapshot. */
 ps=ps_selector_open(dev,"0","4",4u,0x030Bu,125000u);msg=ps_selector_frame(PROTO_CAN_PS,0x40u,0x1A04u);
 ps_selector_call(ps,1u,&msg,0u,0,0,0,0);
 {static const char *invalid[]={"","01","2","-1","+1","1 "," 1","0x1","4294967297","1\n"};
  for(k=0;k<sizeof(invalid)/sizeof(invalid[0]);k++){
   ps=ps_selector_open(dev,invalid[k],"4",4u,0x030Bu,125000u);
   REQUIRE(g_can_ps_a6_selector_probe==0u&&channel(ps)->can_ps_a6_selector_probe==0u);
   ps_selector_call(ps,1u,&msg,0u,0,0,0,0);
  }}
 REQUIRE(PassThruClose(*dev)==ERR_OK);test_can_ps_config_probe_ini=0;test_can_ps_a6_selector_ini="1";tick+=7;
 REQUIRE(PassThruOpen(0,dev)==ERR_OK&&g_can_ps_a6_selector_probe==0u);
 output=0xC0DEFACEu;REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&output)==ERR_INVALID_PROTOCOL_ID&&output==0xC0DEFACEu);
 ps=ps_selector_open(dev,"1","4",4u,0x030Bu,125000u);
 REQUIRE(g_can_ps_a6_selector_probe==1u&&channel(ps)->can_ps_a6_selector_probe==1u);
 test_can_ps_a6_selector_ini="0";REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000,&other)==ERR_OK);
 REQUIRE(channel(other)->can_ps_a6_selector_probe==1u);REQUIRE(PassThruDisconnect(other)==ERR_OK);
 /* 2: complete closed catalog, unknown redaction, both targets/protocols
    and rejected API origins, with self-contained current mask metadata. */
 {static const U32 selectors[]={0x1A02u,0x1A04u,0xD0D1u,0xBEEFu};
  for(k=0;k<4u;k++)for(j=0;j<2u;j++)for(t=0;t<2u;t++){
   msg=ps_selector_frame(j?PROTO_CAN:PROTO_CAN_PS,t?0x50u:0x40u,selectors[k]);
   ps_selector_call(ps,1u,&msg,1u,0x030Bu,125000u,k<3u?k+1u:0u,4u);
   ps_selector_call(ps,2u,&msg,1u,0x030Bu,125000u,k<3u?k+1u:0u,4u);
  }}
 /* 3: every request-envelope boundary stays opaque, without a selector
    marker for malformed, security/control or unrelated messages. */
 msg=ps_selector_frame(PROTO_CAN_PS,0x40u,0x1A04u);
 for(k=0;k<13u;k++){
  changed=msg;
  switch(k){
   case 0:changed.DataSize=11u;break;case 1:changed.DataSize=13u;break;
   case 2:changed.Data[3]^=1u;break;case 3:changed.TxFlags=0u;break;
   case 4:changed.ProtocolID=PROTO_ISO15765;break;case 5:changed.Data[4]=0xCCu;break;
   case 6:changed.Data[5]=0x7Au;break;case 7:changed.Data[6]=0xA3u;break;
   case 8:changed.Data[9]=2u;break;case 9:changed.Data[10]=1u;break;
   case 10:changed.Data[11]=1u;break;case 11:changed.Data[4]=3u;changed.Data[5]=0x27u;break;
   default:changed.Data[4]=0xFFu;changed.Data[5]=0xC8u;break;
  }
  ps_selector_call(ps,k&1u?2u:1u,&changed,0u,0,0,0,0);
 }
 /* 4: non-single counts never dereference msg; nulls and invalid channels
    retain existing statuses and caller outputs without a selector event. */
 for(k=0;k<3u;k++){
  n=k==0u?0u:k==1u?2u:0xFFFFFFFFu;ps_api_reset_log();
  REQUIRE(PassThruWriteMsgs(ps,(PASSTHRU_MSG *)1,&n,0)==ERR_NOT_SUPPORTED&&n==0u);
  REQUIRE(strstr(connect_log_lines,ps_a6_selector_marker)==0);
 }
 ps_api_reset_log();n=1u;output=0xC0DEFACEu;
 REQUIRE(PassThruWriteMsgs(ps,0,&n,0)==ERR_NULL_PARAMETER&&n==1u);
 REQUIRE(PassThruStartPeriodicMsg(ps,0,&output,1000u)==ERR_NULL_PARAMETER&&output==0xC0DEFACEu);
 REQUIRE(PassThruStartPeriodicMsg(ps,&msg,0,1000u)==ERR_NULL_PARAMETER);
 REQUIRE(PassThruWriteMsgs(99u,&msg,&n,0)==ERR_INVALID_CHANNEL_ID&&n==1u);
 REQUIRE(strstr(connect_log_lines,ps_a6_selector_marker)==0);
 /* 5: pins and baud are observed independently, unknown values redacted;
    channel reuse cannot retain the previous probe or route hint. */
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,500000u,&other)==ERR_OK);
 ps_selector_call(other,1u,&msg,1u,0u,500000u,2u,4u);
 option.Value=0x060Eu;REQUIRE(PassThruIoctl(other,IO_SET_CONFIG,&list,0)==ERR_OK);
 ps_selector_call(other,1u,&msg,1u,0x060Eu,500000u,2u,4u);
 channel(other)->can_ps_observed_pins=0xDEADBEEFu;channel(other)->baud=250000u;
 ps_selector_call(other,2u,&msg,1u,0u,0u,2u,4u);
 REQUIRE(PassThruDisconnect(other)==ERR_OK);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN_PS,0,125000u,&other)==ERR_OK);
 ps_selector_call(other,1u,&msg,1u,0u,125000u,2u,4u);
 REQUIRE(PassThruDisconnect(other)==ERR_OK);
 /* 6: instrumentation changes no state, scheduler, bridge, backend or RX.
    READ128 never returns a response to an observed selector. */
 {CHANNEL *ch=channel(ps),*snapshot=(CHANNEL *)malloc(sizeof(*snapshot));
  REQUIRE(snapshot!=0);*snapshot=*ch;serial=g_backend_serial;before_backend=backend_len;bridge=g_vehicle_bridge.inspected_tx;
  ps_selector_call(ps,1u,&msg,1u,0x030Bu,125000u,2u,4u);
  ps_selector_call(ps,2u,&msg,1u,0x030Bu,125000u,2u,4u);
  memset(&rx,0xA5,sizeof(rx));before_rx=rx;n=128u;
  REQUIRE(PassThruReadMsgs(ps,&rx,&n,0)==ERR_BUFFER_EMPTY&&n==0u);
  REQUIRE(memcmp(&rx,&before_rx,sizeof(rx))==0&&memcmp(snapshot,ch,sizeof(*ch))==0);
  REQUIRE(serial==g_backend_serial&&before_backend==backend_len&&bridge==g_vehicle_bridge.inspected_tx);free(snapshot);
 }
 /* 7: a different API mask never accepts A6, and standard CAN is outside
    this probe even when the new global option is enabled. */
 ps=ps_selector_open(dev,"1","0",0u,0x030Bu,125000u);
 ps_selector_call(ps,1u,&msg,1u,0x030Bu,125000u,2u,0u);
 REQUIRE(PassThruConnect(*dev,PROTO_CAN,0,125000u,&std)==ERR_OK);
 changed=msg;changed.ProtocolID=PROTO_CAN;ps_api_reset_log();send(std,&changed);
 REQUIRE(strstr(connect_log_lines,ps_a6_selector_marker)==0);
 REQUIRE(PassThruDisconnect(std)==ERR_OK);
 /* 8: raw selectors/operands are absent from text, catalog events are
    opt-in only, and a new Open disables the previous channel snapshot. */
 msg=ps_selector_frame(PROTO_CAN_PS,0x50u,0xBEEFu);ps_selector_call(ps,1u,&msg,1u,0x030Bu,125000u,0u,0u);
 REQUIRE(strstr(connect_log_lines,"BE EF")==0&&strstr(connect_log_lines,"DE AD BE EF")==0);
 ps=ps_selector_open(dev,"0","0",0u,0x030Bu,125000u);
 ps_selector_call(ps,1u,&msg,0u,0,0,0,0);
 REQUIRE(PassThruClose(*dev)==ERR_OK);test_can_ps_config_probe_ini=0;test_can_ps_a6_selector_ini="0";test_can_ps_api_outcome_ini="0";tick+=7;
 REQUIRE(PassThruOpen(0,dev)==ERR_OK&&g_can_ps_a6_selector_probe==0u);capture_connect_log=0;
 puts("PASS: eight CAN_PS A6 selector groups, closed catalog and no transmission");
}

static void require_lab_cf(const PASSTHRU_MSG *m,U32 sn){
 REQUIRE(m->DataSize==12 && m->Data[4]==(0x20u | (sn&15u)));
 REQUIRE(m->Data[2]==0x07 && m->Data[3]==0x2Eu);
}
int main(){
 U32 dev=0,cid=0,batt=0,n=0;
 REQUIRE(PassThruOpen(0,&dev)==ERR_OK);REQUIRE(dev==1);
 test_vmware_route_evidence(dev);
 test_p2_informer_observer(dev);
 test_p3tool_j2534_preflight(dev);
 test_can_ps_config_probe(&dev);
 test_can_ps_rejected_attempts(&dev);
 test_can_ps_rejected_setup(&dev);
 test_can_ps_api_outcomes(&dev);
 test_can_ps_a6_selectors(&dev);
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


