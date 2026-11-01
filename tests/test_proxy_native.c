/* True x86 Windows loader/stdcall/import test. Uses only SyntheticJ2534.dll. */
#include <windows.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "native_fixture.h"
typedef uint32_t (WINAPI *open_fn)(void*,uint32_t*);
typedef uint32_t (WINAPI *one_fn)(uint32_t);
typedef uint32_t (WINAPI *connect_fn)(uint32_t,uint32_t,uint32_t,uint32_t,uint32_t*);
typedef uint32_t (WINAPI *msgs_fn)(uint32_t,vc_message*,uint32_t*,uint32_t);
typedef uint32_t (WINAPI *periodic_fn)(uint32_t,vc_message*,uint32_t*,uint32_t);
typedef uint32_t (WINAPI *stop_fn)(uint32_t,uint32_t);
typedef uint32_t (WINAPI *filter_fn)(uint32_t,uint32_t,vc_message*,vc_message*,vc_message*,uint32_t*);
typedef uint32_t (WINAPI *voltage_fn)(uint32_t,uint32_t,uint32_t);
typedef uint32_t (WINAPI *version_fn)(uint32_t,char*,char*,char*);
typedef uint32_t (WINAPI *error_fn)(char*);
typedef uint32_t (WINAPI *ioctl_fn)(uint32_t,uint32_t,void*,void*);
typedef void (WINAPI *set_result_fn)(uint32_t,uint32_t);
typedef void (WINAPI *set_rx_fn)(const vc_message*);
typedef const vc_fixture_state *(WINAPI *state_fn)(void);
static void can_id(vc_message *m,uint32_t v){
    m->Data[0]=(uint8_t)(v>>24);m->Data[1]=(uint8_t)(v>>16);m->Data[2]=(uint8_t)(v>>8);m->Data[3]=(uint8_t)v;
}
static void absolute(const char *input,char *output){
    DWORD n=GetFullPathNameA(input,1024,output,0);assert(n && n<1024);
}
int main(int argc,char **argv){
    char fixture_path[1024],proxy_path[1024],log_path[1024],fw[80],dll[80],api[80];
    uint32_t dev=0,ch=0,n,filter,periodic;unsigned groups=0,i;
    vc_message mask={0},pattern={0},flow={0},tx={0},rx={0},before;
    static vc_message batch[128];
    HMODULE fixture,proxy;const vc_fixture_state *state;
    open_fn pt_open;one_fn pt_close,pt_disconnect;connect_fn pt_connect;msgs_fn pt_read,pt_write;
    periodic_fn pt_start_periodic;stop_fn pt_stop_periodic,pt_stop_filter;filter_fn pt_start_filter;
    voltage_fn pt_voltage;version_fn pt_version;error_fn pt_error;ioctl_fn pt_ioctl;
    set_result_fn set_result;set_rx_fn set_rx;state_fn get_state;
    assert((argc==4 || argc==5) && sizeof(void*)==4 && sizeof(vc_message)==4152);
    absolute(argv[1],proxy_path);absolute(argv[2],fixture_path);absolute(argv[3],log_path);
    assert(strcmp(proxy_path,fixture_path)!=0);
    /* Require a fresh, explicitly named synthetic output; never overwrite logs. */
    assert(GetFileAttributesA(log_path)==INVALID_FILE_ATTRIBUTES);
    assert(SetEnvironmentVariableA("VCAR_TRACE_REAL_DLL",fixture_path));
    assert(SetEnvironmentVariableA("VCAR_TRACE_LOG_PATH",log_path));
#define LOAD(module,name,type,dest) dest=(type)(void (WINAPI *)(void))GetProcAddress(module,name);assert(dest)
    if(argc==5){
        if(!strcmp(argv[4],"self"))assert(SetEnvironmentVariableA("VCAR_TRACE_REAL_DLL",proxy_path));
        else if(!strcmp(argv[4],"relative"))assert(SetEnvironmentVariableA("VCAR_TRACE_REAL_DLL","SyntheticJ2534.dll"));
        else {assert(!strcmp(argv[4],"missing"));assert(GetFileAttributesA(fixture_path)==INVALID_FILE_ATTRIBUTES);}
        proxy=LoadLibraryA(proxy_path);assert(proxy);
        LOAD(proxy,"PassThruOpen",open_fn,pt_open);LOAD(proxy,"PassThruGetLastError",error_fn,pt_error);
        assert(pt_open(0,&dev)==7 && dev==0);
        assert(pt_error(fw)==7 && strstr(fw,"not loaded"));
        assert(GetFileAttributesA(log_path)==INVALID_FILE_ATTRIBUTES);
        assert(FreeLibrary(proxy));
        printf("dev46: native loader rejects %s target without recursion or fake RX\n",argv[4]);return 0;
    }
    fixture=LoadLibraryA(fixture_path);assert(fixture);
    LOAD(fixture,"TestSetResult",set_result_fn,set_result);
    LOAD(fixture,"TestSetRx",set_rx_fn,set_rx);LOAD(fixture,"TestGetState",state_fn,get_state);
    state=get_state();proxy=LoadLibraryA(proxy_path);assert(proxy);
    LOAD(proxy,"PassThruOpen",open_fn,pt_open);LOAD(proxy,"PassThruClose",one_fn,pt_close);
    LOAD(proxy,"PassThruConnect",connect_fn,pt_connect);LOAD(proxy,"PassThruDisconnect",one_fn,pt_disconnect);
    LOAD(proxy,"PassThruReadMsgs",msgs_fn,pt_read);LOAD(proxy,"PassThruWriteMsgs",msgs_fn,pt_write);
    LOAD(proxy,"PassThruStartPeriodicMsg",periodic_fn,pt_start_periodic);
    LOAD(proxy,"PassThruStopPeriodicMsg",stop_fn,pt_stop_periodic);
    LOAD(proxy,"PassThruStartMsgFilter",filter_fn,pt_start_filter);
    LOAD(proxy,"PassThruStopMsgFilter",stop_fn,pt_stop_filter);
    LOAD(proxy,"PassThruSetProgrammingVoltage",voltage_fn,pt_voltage);
    LOAD(proxy,"PassThruReadVersion",version_fn,pt_version);
    LOAD(proxy,"PassThruGetLastError",error_fn,pt_error);LOAD(proxy,"PassThruIoctl",ioctl_fn,pt_ioctl);
#undef LOAD
    /* 1. Actual InitOnce/LoadLibrary/GetProcAddress and undecorated exports. */
    assert(pt_open(fw,&dev)==0 && dev==1 && state->p==fw && state->q==&dev);
    assert(pt_error(fw)==0 && !strcmp(fw,"S"));++groups;
    /* 2. ABI and exact filter/channel argument forwarding. */
    assert(pt_connect(dev,6,0x100,500000,&ch)==0 && ch==10);
    assert(state->channel==dev && state->a==6 && state->b==0x100 && state->c==500000 && state->p==&ch);
    mask.ProtocolID=6;mask.DataSize=4;can_id(&mask,0xFFFFFFFFu);
    pattern=mask;can_id(&pattern,0x18DAF150);flow=mask;can_id(&flow,0x18DA50F1);before=mask;
    assert(pt_start_filter(ch,3,&mask,&pattern,&flow,&filter)==0 && filter==7);
    assert(state->p==&mask && state->q==&pattern && state->r==&flow && state->s==&filter && state->a==3);
    assert(!memcmp(&mask,&before,sizeof(mask)));++groups;
    /* 3. Partial accepted TX and delivered RX, through real Win32 locks/log IO. */
    tx=flow;tx.DataSize=7;tx.Data[4]=0x22;tx.Data[5]=0xF1;tx.Data[6]=0x90;before=tx;
    set_result(9,1);n=2;assert(pt_write(ch,&tx,&n,123)==9 && n==1);
    assert(state->p==&tx && state->q==&n && state->a==123 && !memcmp(&tx,&before,sizeof(tx)));
    rx=pattern;rx.DataSize=8;rx.Data[4]=0x62;rx.Data[5]=0xF1;rx.Data[6]=0x90;rx.Data[7]=0xAB;
    rx.Timestamp=987654;set_rx(&rx);set_result(0,1);n=128;
    assert(pt_read(ch,batch,&n,456)==0 && n==1 && state->a==456 && !memcmp(&batch[0],&rx,sizeof(rx)));
    set_result(9,1);n=128;assert(pt_read(ch,batch,&n,1)==9 && n==1);++groups;
    /* 4. Bad result counts / failed reads never dereference unreturned memory. */
    set_result(7,1);n=1;assert(pt_read(ch,(vc_message *)(uintptr_t)1,&n,1)==7 && n==1);
    set_result(0,2);n=1;assert(pt_read(ch,(vc_message *)(uintptr_t)1,&n,1)==0 && n==2);++groups;
    /* 5. Successful and failed filter lifecycle operations. */
    set_result(7,1);assert(pt_stop_filter(ch,filter)==7 && state->a==filter);
    assert(pt_ioctl(ch,10,0,0)==7);set_result(0,1);
    assert(pt_ioctl(ch,10,0,0)==0 && pt_disconnect(ch)==0);++groups;
    /* 6. Raw CAN B9FB / 13 frames / READ128, no extra ISO15765 interpretation. */
    assert(pt_connect(dev,5,0,500000,&ch)==0);
    tx.ProtocolID=5;tx.DataSize=12;can_id(&tx,0x000FFFFE);
    tx.Data[4]=0xCB;tx.Data[5]=0x50;tx.Data[6]=0xB9;tx.Data[7]=0xFB;
    n=1;assert(pt_write(ch,&tx,&n,1)==0);
    rx=tx;can_id(&rx,0x01200003);set_rx(&rx);set_result(0,13);n=128;
    assert(pt_read(ch,batch,&n,100)==0 && n==13);
    for(i=0;i<13;i++){rx.Data[4]=(uint8_t)i;assert(!memcmp(&batch[i],&rx,sizeof(rx)));}
    set_result(0,1);assert(pt_close(dev)==0);++groups;
    /* 7. Remaining ABI entrypoints; errors/results propagate without mutation. */
    set_result(37,1);
    assert(pt_start_periodic(ch,&tx,&periodic,25)==37 && state->p==&tx && state->q==&periodic && state->a==25);
    assert(pt_stop_periodic(ch,88)==37 && state->a==88);
    assert(pt_voltage(dev,6,0xFFFFFFFFu)==37 && state->channel==dev && state->a==6 && state->b==0xFFFFFFFFu);
    assert(pt_version(dev,fw,dll,api)==37 && state->p==fw && state->q==dll && state->r==api);
    set_result(0,1);assert(pt_version(dev,fw,dll,api)==0 && !strcmp(fw,"F") && !strcmp(dll,"D") && !strcmp(api,"A"));
    assert(pt_ioctl(ch,99,&tx,&rx)==0 && state->p==&tx && state->q==&rx);
    for(i=0;i<14;i++)assert(state->calls[i]>0);++groups;
    /* 8. Caller strings/payload never appear in the JSON log (Python checks it). */
    assert(pt_connect(dev,6,0,500000,&ch)==0);tx=flow;tx.DataSize=40;
    memcpy(tx.Data+4,"SYNTHETIC_PRIVATE_PAYLOAD_NEVER_LOG",33);n=1;
    assert(pt_write(ch,&tx,&n,1)==0 && pt_close(dev)==0);
    assert(GetFileAttributesA(log_path)!=INVALID_FILE_ATTRIBUTES);
    assert(FreeLibrary(proxy));assert(FreeLibrary(fixture));++groups;
    printf("dev46: %u/8 native Windows x86 DLL integration groups OK (synthetic only)\n",groups);
    return groups==8?0:1;
}
