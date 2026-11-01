/* Linux host-side protocol test, with Win32 APIs stubbed. */
#define HOST_TEST 1
#include "../src/virtualcar.c"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static U32 tick=0;
static char backend_lines[800000];static U32 backend_len=0;
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
void Sleep(U32 ms){tick+=ms;}
U32 GetTickCount(void){return tick;}
int QueryPerformanceFrequency(I64 *v){*v=1000000;return 1;}
int QueryPerformanceCounter(I64 *v){*v=(I64)tick*1000;return 1;}
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
 return strstr(p,"dev47-backend.jsonl")?(HANDLE)1:INVALID_HANDLE;
}
U32 SetFilePointer(HANDLE file,U32 low,PTR high,U32 method){(void)file;(void)low;(void)high;(void)method;return 0;}
int WriteFile(HANDLE f,const void*b,U32 n,U32*w,PTR o){
 (void)o;
 if(f!=(HANDLE)1 || n+backend_len>=sizeof(backend_lines))return 0;
 memcpy(backend_lines+backend_len,b,n);backend_len+=n;
 backend_lines[backend_len]=0;
 if(w)*w=n;
 return 1;
}
int CloseHandle(HANDLE file){(void)file;return 1;}
long InterlockedCompareExchange(volatile long*dst,long exchange,long compare){long v=*dst;if(v==compare)*dst=exchange;return v;}
long InterlockedExchange(volatile long*dst,long val){long v=*dst;*dst=val;return v;}
#define REQUIRE(expr) do{if(!(expr)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#expr);exit(1);}}while(0)
static PASSTHRU_MSG frame(U32 proto,U32 id,const U8 *data,U32 len){PASSTHRU_MSG m={0};m.ProtocolID=proto;m.DataSize=len+4;m.Data[0]=(U8)(id>>24);m.Data[1]=(U8)(id>>16);m.Data[2]=(U8)(id>>8);m.Data[3]=(U8)id;if(len)memcpy(m.Data+4,data,len);return m;}
static PASSTHRU_MSG readmsg(U32 cid){PASSTHRU_MSG m={0};U32 n=1;REQUIRE(PassThruReadMsgs(cid,&m,&n,0)==ERR_OK);REQUIRE(n==1);return m;}
static void send(U32 cid,PASSTHRU_MSG *m){U32 n=1;REQUIRE(PassThruWriteMsgs(cid,m,&n,10)==ERR_OK);REQUIRE(n==1);}
int main(){
 U32 dev=0,cid=0,batt=0,n=0;
 REQUIRE(PassThruOpen(0,&dev)==ERR_OK);REQUIRE(dev==1);
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
 /* Observer classifies A3, but never fabricates a positive E3 reply. */
 const U8 a3_wire[]={0xCF,0x50,0xA3,0x02,0x03,0xA5,0xA5,0x00};
 m=frame(PROTO_CAN,0x000FFFFE,a3_wire,8);send(cid,&m);
 REQUIRE(g_vehicle_bridge.inspected_tx>0);
 REQUIRE(g_vehicle_bridge.vehicle.a3_shape_seen==1);
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
 REQUIRE(g_vehicle_bridge.vehicle.a3_shape_seen==1);
 REQUIRE(g_vehicle_bridge.vehicle.b9fb_seen>=1);
 const U8 d2f0[]={0xCB,0x50,0xB9,0xF0,0,0,0,0};
 m=frame(PROTO_CAN,0x000FFFFE,d2f0,8);send(cid,&m);r=readmsg(cid);
 REQUIRE(r.Data[0]==0x01 && r.Data[1]==0x00 && r.Data[2]==0x00 && r.Data[3]==0x03);
 REQUIRE(r.Data[4]==0x8F && r.Data[5]==0x50 && r.Data[6]==0xF9 && r.Data[7]==0xF0);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,30)==ERR_OK);REQUIRE(r.Data[4]==0x09);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,30)==ERR_OK);REQUIRE(r.Data[4]==0x4C);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
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
 /* An unsupported 29-bit P3 route must remain unanswered. */
 const U8 missing_p3[]={0x22,0xF1,0x14};
 m=frame(PROTO_ISO15765,0x18DA50F1,missing_p3,3);send(cid,&m);
 n=1;REQUIRE(PassThruReadMsgs(cid,&r,&n,0)==ERR_BUFFER_EMPTY);
 REQUIRE(strstr(backend_lines,"\"route\":\"UNHANDLED\"")!=NULL);
 REQUIRE(strstr(backend_lines,"\"reason\":\"unhandled_request\"")!=NULL);
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
