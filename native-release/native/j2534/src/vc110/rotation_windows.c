#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "rotation.h"
#define PATH_CAP 520u
typedef struct { char path[PATH_CAP]; unsigned length; } context;
static int missing(DWORD e){return e==ERROR_FILE_NOT_FOUND;}
static int suffix(const context *c, unsigned slot, char *out){
    unsigned i; if(slot>VC110_ARCHIVES+1u || c->length+6u>=PATH_CAP)return 0;
    for(i=0;i<c->length;i++)out[i]=c->path[i];
    if(slot==VC110_ARCHIVES+1u){out[i++]='.';out[i++]='l';out[i++]='c';out[i++]='k';}
    else if(slot){out[i++]='.';out[i++]=(char)('0'+slot);}
    out[i]=0;return 1;
}
static int ordinary(HANDLE f){
    BY_HANDLE_FILE_INFORMATION info;
    return GetFileType(f)==FILE_TYPE_DISK && GetFileInformationByHandle(f,&info) &&
      !(info.dwFileAttributes&(FILE_ATTRIBUTE_REPARSE_POINT|FILE_ATTRIBUTE_DIRECTORY)) && info.nNumberOfLinks==1;
}
static int file_size(void *v,unsigned slot,uint64_t *n){
    context *c=v;char path[PATH_CAP];HANDLE f;LARGE_INTEGER size;int ok;
    if(!suffix(c,slot,path))return -1;
    f=CreateFileA(path,FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,NULL,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT,NULL);
    if(f==INVALID_HANDLE_VALUE)return missing(GetLastError())?0:-1;
    ok=ordinary(f)&&GetFileSizeEx(f,&size)&&size.QuadPart>=0;
    if(ok)*n=(uint64_t)size.QuadPart;
    CloseHandle(f);return ok?1:-1;
}
static int move_slot(void *v,unsigned from,unsigned to){
    context *c=v;char src[PATH_CAP],dst[PATH_CAP];uint64_t size;int status;
    status=file_size(v,from,&size);if(status<=0)return status==0;
    if(file_size(v,to,&size)<0)return 0;
    if(!suffix(c,from,src)||!suffix(c,to,dst))return 0;
    return MoveFileExA(src,dst,MOVEFILE_REPLACE_EXISTING)!=0;
}
static int append_line(void *v,const char *line,unsigned n){
    context *c=v;HANDLE f;DWORD written=0;int ok;
    f=CreateFileA(c->path,FILE_APPEND_DATA|FILE_READ_ATTRIBUTES,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,NULL,OPEN_ALWAYS,FILE_FLAG_OPEN_REPARSE_POINT,NULL);
    if(f==INVALID_HANDLE_VALUE)return 0;
    ok=ordinary(f)&&WriteFile(f,line,n,&written,NULL)&&written==n;
    CloseHandle(f);return ok;
}
void vc110_write(const char *path,const char *line,unsigned length){
    static const vc110_ops ops={file_size,move_slot,append_line};
    context c;char lock[PATH_CAP];HANDLE f;
    if(!path)return;
    for(c.length=0;c.length<PATH_CAP-6u&&path[c.length];++c.length)c.path[c.length]=path[c.length];
    if(!c.length||path[c.length])return;
    c.path[c.length]=0;
    if(!suffix(&c,VC110_ARCHIVES+1u,lock))return;
    /* Exclusive open is process-safe and released by OS on crash. No spin/wait.
       A concurrent writer loses a diagnostic record, not a CAN response. */
    f=CreateFileA(lock,GENERIC_READ,0,NULL,OPEN_ALWAYS,FILE_FLAG_OPEN_REPARSE_POINT,NULL);
    if(f==INVALID_HANDLE_VALUE)return;
    if(ordinary(f))(void)vc110_record(&ops,&c,VC110_LIMIT,line,length);
    CloseHandle(f);
}
