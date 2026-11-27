// VC115 native standalone controller. Existing owned adapter only.
#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <shellapi.h>
#include <bcrypt.h>
#include <string>
#include <vector>
#include <array>
#include <stdexcept>
#include <algorithm>
#include <cwctype>
#include "provider_hash.h"
#pragma comment(lib,"bcrypt.lib")
#pragma comment(lib,"advapi32.lib")
#pragma comment(lib,"shell32.lib")
#pragma comment(lib,"user32.lib")
#pragma comment(lib,"gdi32.lib")
#pragma comment(linker,"/manifestdependency:\"type='win32' name='Microsoft.Windows.Common-Controls' version='6.0.0.0' processorArchitecture='*' publicKeyToken='6595b64144ccf1df' language='*'\"")
using S=std::wstring;
static constexpr wchar_t oldDir[]=L"C:\\VC099-VIDA-511\\provider";
static constexpr wchar_t keyName[]=L"SOFTWARE\\PassThruSupport.04.04\\J2534 Lab Adapter";
static constexpr wchar_t legacy[]=L"SOFTWARE\\PassThruSupport.04.04\\SectorV Virtual Car";
static constexpr wchar_t dllName[]=L"VirtualCarJ2534.dll";
static S root,exe,original,candidate,profile,sourceProfile,journal;
struct Handle{HANDLE h=INVALID_HANDLE_VALUE; ~Handle(){if(h&&h!=INVALID_HANDLE_VALUE)CloseHandle(h);}};
struct Key{HKEY h=nullptr;~Key(){if(h)RegCloseKey(h);}};
static void require(bool v,const char* m){if(!v)throw std::runtime_error(m);}
static bool same(const S&a,const S&b){return CompareStringOrdinal(a.c_str(),-1,b.c_str(),-1,TRUE)==CSTR_EQUAL;}
static S join(const S&a,const S&b){return a+L"\\"+b;}
static S parent(const S&s){return s.substr(0,s.find_last_of(L'\\'));}
static bool exists(const S&s){DWORD a=GetFileAttributesW(s.c_str());if(a!=INVALID_FILE_ATTRIBUTES)return true;require(GetLastError()==ERROR_FILE_NOT_FOUND||GetLastError()==ERROR_PATH_NOT_FOUND,"Cannot inspect path");return false;}
static void local(const S&s,bool file=true){
    require(s.size()>3&&s.size()<240&&s[1]==L':'&&s[2]==L'\\',"Use a short absolute local path");
    wchar_t canon[MAX_PATH];DWORD n=GetFullPathNameW(s.c_str(),MAX_PATH,canon,nullptr);
    require(n>0&&n<MAX_PATH&&same(s,canon),"Noncanonical path");
    require(GetDriveTypeW(s.substr(0,3).c_str())==DRIVE_FIXED,"Fixed local drive required");
    BOOL lossy=FALSE;require(WideCharToMultiByte(CP_ACP,WC_NO_BEST_FIT_CHARS,s.c_str(),-1,nullptr,0,nullptr,&lossy)>0&&!lossy,"Path is not compatible with the ANSI DLL");
    for(S p=s;;p=parent(p)){
        if(p.size()==2)p+=L"\\";
        DWORD a=GetFileAttributesW(p.c_str());require(a!=INVALID_FILE_ATTRIBUTES&&!(a&FILE_ATTRIBUTE_REPARSE_POINT),"Missing path or reparse point");
        require((p==s&&file)?!(a&FILE_ATTRIBUTE_DIRECTORY):(a&FILE_ATTRIBUTE_DIRECTORY)!=0,"Unexpected file type");
        if(p.size()==3)break;
    }
}
static std::vector<unsigned char> bytes(const S&p,DWORD max=64*1024*1024){
    local(p);Handle f;f.h=CreateFileW(p.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    require(f.h!=INVALID_HANDLE_VALUE,"Cannot open file");LARGE_INTEGER n{};require(GetFileSizeEx(f.h,&n)&&n.QuadPart>0&&n.QuadPart<=max,"Unexpected file size");
    std::vector<unsigned char>b(static_cast<size_t>(n.QuadPart));DWORD got=0;require(ReadFile(f.h,b.data(),static_cast<DWORD>(b.size()),&got,nullptr)&&got==b.size(),"Cannot read file");return b;
}
static S sha(const std::vector<unsigned char>&b){
    std::vector<unsigned char>obj; // buffer outlives the hash handle, including exception paths
    BCRYPT_ALG_HANDLE alg=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;
    struct Cleanup{BCRYPT_ALG_HANDLE&a;BCRYPT_HASH_HANDLE&h;~Cleanup(){if(h)BCryptDestroyHash(h);if(a)BCryptCloseAlgorithmProvider(a,0);}} cleanup{alg,hash};
    require(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,nullptr,0)>=0,"SHA256 unavailable");
    DWORD len=0,n=0;require(BCryptGetProperty(alg,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&len),sizeof(len),&n,0)>=0&&len>0,"SHA256 object");
    obj.resize(len);std::array<unsigned char,32>out{};
    require(BCryptCreateHash(alg,&hash,obj.data(),len,nullptr,0,0)>=0,"SHA256 init");
    require(BCryptHashData(hash,const_cast<PUCHAR>(b.data()),static_cast<ULONG>(b.size()),0)>=0&&BCryptFinishHash(hash,out.data(),32,0)>=0,"SHA256 failed");
    BCryptDestroyHash(hash);hash=nullptr; // hash object must not outlive its buffer
    const wchar_t* digits=L"0123456789ABCDEF";S s;for(auto v:out){s+=digits[v>>4];s+=digits[v&15];}return s;
}
static S digest(const S&p){return sha(bytes(p));}
static S regstr(HKEY h,const wchar_t*n){
    DWORD type=0,size=0;require(RegQueryValueExW(h,n,nullptr,&type,nullptr,&size)==ERROR_SUCCESS&&type==REG_SZ&&size>=2&&size<=4096&&size%2==0,"Invalid adapter registry string");
    std::vector<wchar_t>b(size/2);require(RegQueryValueExW(h,n,nullptr,&type,reinterpret_cast<BYTE*>(b.data()),&size)==ERROR_SUCCESS&&type==REG_SZ&&size==b.size()*2&&b.back()==0,"Registry string changed");
    require(wcslen(b.data())==b.size()-1,"Embedded NUL in registry");return b.data();
}
static DWORD regnum(HKEY h,const wchar_t*n){
    DWORD v=0,t=0,z=sizeof(v);require(RegQueryValueExW(h,n,nullptr,&t,reinterpret_cast<BYTE*>(&v),&z)==ERROR_SUCCESS&&t==REG_DWORD&&z==4,"Invalid registry DWORD");return v;
}
static S ownedAt(Key&k,HKEY hive,const wchar_t*canonical,const wchar_t*previous,bool write=false){
    Key l;auto rc=RegOpenKeyExW(hive,previous,0,KEY_READ|KEY_WOW64_32KEY,&l.h);require(rc==ERROR_FILE_NOT_FOUND||rc==ERROR_PATH_NOT_FOUND,"Legacy adapter conflict");
    require(RegOpenKeyExW(hive,canonical,0,(write?KEY_READ|KEY_SET_VALUE:KEY_READ)|KEY_WOW64_32KEY,&k.h)==ERROR_SUCCESS,"Canonical J2534 adapter unavailable");
    DWORD sub=0,vals=0;require(RegQueryInfoKeyW(k.h,nullptr,nullptr,nullptr,&sub,nullptr,nullptr,&vals,nullptr,nullptr,nullptr,nullptr)==ERROR_SUCCESS&&sub==0&&vals==7,"Unexpected adapter registry layout");
    require(regstr(k.h,L"Vendor")==L"J2534 Lab"&&regstr(k.h,L"Name")==L"J2534 Lab Adapter"&&regstr(k.h,L"ConfigApplication").empty()&&regnum(k.h,L"CAN")==1&&regnum(k.h,L"ISO15765")==1&&regnum(k.h,L"MessageVersion")==0x0404,"Adapter ownership check failed");
    return regstr(k.h,L"FunctionLibrary");
}
#ifdef VC119_SELFTEST
static HKEY testRegistry=nullptr;
#endif
static S owned(Key&k,bool write=false){
#ifdef VC119_SELFTEST
    if(testRegistry)return ownedAt(k,testRegistry,L"Adapter",L"Legacy",write);
#endif
    return ownedAt(k,HKEY_LOCAL_MACHINE,keyName,legacy,write);
}
static S ini(const S&p,const wchar_t*section,const wchar_t*key){wchar_t buf[512];auto n=GetPrivateProfileStringW(section,key,L"",buf,512,p.c_str());require(n<511,"INI value too long");return buf;}
static void validateProfile(const S&p){
    auto b=bytes(p,8*1024*1024);require(!(b.size()>=2&&b[0]==0xfe&&b[1]==0xff),"Unsupported INI encoding");
    wchar_t sec[2048];auto n=GetPrivateProfileSectionW(L"VC108N_ExternalStateLab",sec,2048,p.c_str());require(n==0,"External IPC profile is not supported");
    auto vin=ini(p,L"Vehicle",L"VIN");require(vin.size()==17&&std::all_of(vin.begin(),vin.end(),[](wchar_t c){return(c>=L'A'&&c<=L'Z'&&c!=L'I'&&c!=L'O'&&c!=L'Q')||(c>=L'0'&&c<=L'9');}),"Valid VIN required");
    require(ini(p,L"J2534_2",L"Enabled")==L"1","J2534-2 profile required");
    require(ini(p,L"Diagnostics",L"EnableGGDCemLab")==L"1","CEM lab profile required");
}
static S readJournal(){
    auto b=bytes(journal,64);require(b.size()==64,"Invalid rollback journal");S s(b.begin(),b.end());require(std::all_of(s.begin(),s.end(),[](wchar_t c){return(c>=L'0'&&c<=L'9')||(c>=L'A'&&c<=L'F');}),"Invalid rollback hash");return s;
}
static void saveJournal(const S&hash){
    if(exists(journal)){require(readJournal()==hash,"Existing rollback journal differs");return;}
    require(hash.size()==64,"Invalid rollback hash length");
    std::string b; b.reserve(hash.size());
    for(wchar_t c:hash){
        require((c>=L'0'&&c<=L'9')||(c>=L'A'&&c<=L'F'),"Invalid rollback hash character");
        b.push_back(static_cast<char>(c)); // checked ASCII hex, lossless
    }
    Handle f;f.h=CreateFileW(journal.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    require(f.h!=INVALID_HANDLE_VALUE,"Cannot create rollback journal");DWORD n=0;require(WriteFile(f.h,b.data(),64,&n,nullptr)&&n==64&&FlushFileBuffers(f.h),"Cannot persist rollback journal");
}
static void paths(){
    wchar_t b[MAX_PATH];DWORD n=GetModuleFileNameW(nullptr,b,MAX_PATH);require(n&&n<MAX_PATH,"Cannot locate application");exe=b;root=parent(exe);
    local(exe);original=join(oldDir,dllName);candidate=join(root,dllName);sourceProfile=join(oldDir,L"virtualcar.ini");profile=join(root,L"virtualcar.ini");journal=join(root,L"rollback.sha256");
    require(!same(original,candidate),"Use a separate extracted directory");
}
static void prepareFiles(const S&oldHash){
    validateProfile(sourceProfile);
    if(!exists(profile))require(CopyFileW(sourceProfile.c_str(),profile.c_str(),TRUE)!=0,"Cannot copy profile");
    validateProfile(profile);require(bytes(profile,8*1024*1024)==bytes(sourceProfile,8*1024*1024),"Candidate INI differs; extract a fresh package");
    saveJournal(oldHash);
}
static void verifyRollback(const S&oldHash){require(readJournal()==oldHash,"Original DLL changed since backup");}
static void changeAt(bool undo,HKEY hive,const wchar_t*canonical,const wchar_t*previous,const wchar_t*mutexName){
    Handle mutex;mutex.h=CreateMutexW(nullptr,FALSE,mutexName);require(mutex.h!=nullptr,"Mutex failed");auto wait=WaitForSingleObject(mutex.h,0);require(wait==WAIT_OBJECT_0||wait==WAIT_ABANDONED,"Another operation is running");
    struct Release{HANDLE h;~Release(){ReleaseMutex(h);}} release{mutex.h};
    Key k;S selected=ownedAt(k,hive,canonical,previous,true);
    require(same(selected,undo?candidate:original),"Registration is not the expected source");
    local(original);local(candidate);require(digest(candidate)==VC115_PROVIDER_SHA,"Candidate DLL checksum mismatch");
    S oldHash=digest(original);
    if(undo){verifyRollback(oldHash);}
    else{
        prepareFiles(oldHash);
    }
    const S&next=undo?original:candidate;
    require(same(regstr(k.h,L"FunctionLibrary"),selected),"Adapter changed concurrently");
    require(RegSetValueExW(k.h,L"FunctionLibrary",0,REG_SZ,reinterpret_cast<const BYTE*>(next.c_str()),static_cast<DWORD>((next.size()+1)*sizeof(wchar_t)))==ERROR_SUCCESS,"Cannot update adapter");
    require(RegFlushKey(k.h)==ERROR_SUCCESS&&same(regstr(k.h,L"FunctionLibrary"),next),"Registry readback failed; review adapter before retrying");
}
static void change(bool undo){
    changeAt(undo,HKEY_LOCAL_MACHINE,keyName,legacy,L"Local\\VirtualCarVC115Provider");
}
static HWND status,check,connectBtn,restoreBtn,details,subtitle,detailLabel;static HFONT font,titleFont,statusFont,detailFont;static int scale=96;
static int px(int v){return MulDiv(v,scale,96);}
static S error(const std::exception&e){std::string t=e.what();return S(t.begin(),t.end());}
static void refresh(){
    bool can=false,undo=false;S msg;
    try{Key k;auto s=owned(k);if(same(s,original)){msg=L"Ready to connect";can=true;}else if(same(s,candidate)){msg=L"Driver selected - open VIDA";undo=true;}else msg=L"Different provider selected. Restore it first.";SetWindowTextW(details,s.c_str());}
    catch(const std::exception&e){msg=error(e);SetWindowTextW(details,L"");}
    bool closed=SendMessageW(check,BM_GETCHECK,0,0)==BST_CHECKED;
    EnableWindow(connectBtn,can&&closed);EnableWindow(restoreBtn,undo&&closed);SetWindowTextW(status,msg.c_str());
}
static void invoke(HWND w,bool undo){
    if(SendMessageW(check,BM_GETCHECK,0,0)!=BST_CHECKED)return;
    SHELLEXECUTEINFOW s{};s.cbSize=sizeof(s);s.fMask=SEE_MASK_NOCLOSEPROCESS;s.hwnd=w;s.lpVerb=L"runas";s.lpFile=exe.c_str();s.lpParameters=undo?L"--restore":L"--connect";s.nShow=SW_SHOWNORMAL;
    if(ShellExecuteExW(&s)&&s.hProcess){Handle h;h.h=s.hProcess;WaitForSingleObject(h.h,INFINITE);}
    else if(GetLastError()!=ERROR_CANCELLED)MessageBoxW(w,L"Unable to start elevated helper.",L"Virtual Car",MB_OK|MB_ICONERROR);
    SendMessageW(check,BM_SETCHECK,BST_UNCHECKED,0);refresh();
}
static HWND control(HWND w,const wchar_t*cls,const wchar_t*txt,DWORD style,int x,int y,int width,int h,int id=0){
    HWND c=CreateWindowExW(0,cls,txt,WS_CHILD|WS_VISIBLE|style,px(x),px(y),px(width),px(h),w,reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),GetModuleHandleW(nullptr),nullptr);
    if(c)SendMessageW(c,WM_SETFONT,reinterpret_cast<WPARAM>(font),TRUE);return c;
}
static LRESULT CALLBACK wnd(HWND w,UINT m,WPARAM wp,LPARAM lp){
    switch(m){
    case WM_CREATE:{
        font=CreateFontW(-px(14),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
        titleFont=CreateFontW(-px(27),0,0,0,FW_SEMIBOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
        statusFont=CreateFontW(-px(16),0,0,0,FW_SEMIBOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
        detailFont=CreateFontW(-px(12),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
        if(!font||!titleFont||!statusFont||!detailFont)return -1;
        auto title=control(w,L"STATIC",L"XC90 V8",0,20,16,346,35);
        subtitle=control(w,L"STATIC",L"Standalone virtual car",0,20,52,346,22);
        status=control(w,L"STATIC",L"",0,20,91,346,38);
        check=control(w,L"BUTTON",L"VIDA and other clients are closed",BS_AUTOCHECKBOX|WS_TABSTOP,20,132,346,26,101);
        connectBtn=control(w,L"BUTTON",L"Connect to VIDA",BS_PUSHBUTTON|WS_TABSTOP,20,166,346,38,102);
        restoreBtn=control(w,L"BUTTON",L"Restore previous driver",BS_PUSHBUTTON|WS_TABSTOP,20,212,346,36,103);
        detailLabel=control(w,L"STATIC",L"SELECTED DRIVER",0,20,259,346,17);
        details=control(w,L"STATIC",L"",SS_PATHELLIPSIS|SS_NOPREFIX,20,277,346,20);
        if(!title||!subtitle||!status||!check||!connectBtn||!restoreBtn||!detailLabel||!details)return -1;
        SendMessageW(title,WM_SETFONT,reinterpret_cast<WPARAM>(titleFont),TRUE);
        SendMessageW(status,WM_SETFONT,reinterpret_cast<WPARAM>(statusFont),TRUE);
        SendMessageW(detailLabel,WM_SETFONT,reinterpret_cast<WPARAM>(detailFont),TRUE);
        SendMessageW(details,WM_SETFONT,reinterpret_cast<WPARAM>(detailFont),TRUE);
        refresh();return 0;}
    case WM_CTLCOLORSTATIC:
    case WM_CTLCOLORBTN:{
        auto dc=reinterpret_cast<HDC>(wp);
        SetTextColor(dc,GetSysColor(COLOR_WINDOWTEXT));
        SetBkColor(dc,GetSysColor(COLOR_WINDOW));
        SetBkMode(dc,OPAQUE);
        return reinterpret_cast<LRESULT>(GetSysColorBrush(COLOR_WINDOW));}
    case WM_SYSCOLORCHANGE:InvalidateRect(w,nullptr,TRUE);return DefWindowProcW(w,m,wp,lp);
    case WM_COMMAND:if(HIWORD(wp)==BN_CLICKED){if(LOWORD(wp)==101)refresh();if(LOWORD(wp)==102)invoke(w,false);if(LOWORD(wp)==103)invoke(w,true);}return 0;
    case WM_ACTIVATE:if(status&&LOWORD(wp)!=WA_INACTIVE)refresh();return 0;
    case WM_DESTROY:DeleteObject(font);DeleteObject(titleFont);DeleteObject(statusFont);DeleteObject(detailFont);PostQuitMessage(0);return 0;
    default:return DefWindowProcW(w,m,wp,lp);}
}
int WINAPI wWinMain(HINSTANCE h,HINSTANCE,PWSTR,int show){
    try{
        paths();
        int argc=0;LPWSTR* argv=CommandLineToArgvW(GetCommandLineW(),&argc);require(argv!=nullptr,"Invalid command line");
        S arg=argc==2?argv[1]:L"";LocalFree(argv);require(argc==1||argc==2,"Unexpected arguments");
        if(argc==2){
            require(arg==L"--connect"||arg==L"--restore","Unknown argument");
            bool undo=arg==L"--restore";
            if(MessageBoxW(nullptr,undo?L"Restore the original VC107 adapter? All diagnostic clients must be closed.":L"Connect the standalone Virtual Car adapter? All diagnostic clients must be closed.",L"Virtual Car",MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2)!=IDYES)return 2;
            change(undo);MessageBoxW(nullptr,undo?L"Previous driver restored.":L"Connected. Select J2534 Lab Adapter in VIDA.",L"Virtual Car",MB_OK|MB_ICONINFORMATION);return 0;
        }
        SetProcessDPIAware();HDC dc=GetDC(nullptr);if(dc){scale=GetDeviceCaps(dc,LOGPIXELSX);ReleaseDC(nullptr,dc);}
        WNDCLASSEXW wc{};wc.cbSize=sizeof(wc);wc.lpfnWndProc=wnd;wc.hInstance=h;wc.hCursor=LoadCursorW(nullptr,IDC_ARROW);
        wc.hIcon=static_cast<HICON>(LoadImageW(h,MAKEINTRESOURCEW(101),IMAGE_ICON,GetSystemMetrics(SM_CXICON),GetSystemMetrics(SM_CYICON),LR_SHARED));
        wc.hIconSm=static_cast<HICON>(LoadImageW(h,MAKEINTRESOURCEW(101),IMAGE_ICON,GetSystemMetrics(SM_CXSMICON),GetSystemMetrics(SM_CYSMICON),LR_SHARED));
        require(wc.hIcon&&wc.hIconSm,"Application icon missing");
        wc.hbrBackground=GetSysColorBrush(COLOR_WINDOW);wc.lpszClassName=L"VirtualCarVC115";require(RegisterClassExW(&wc)!=0,"Window class failed");
        RECT r{0,0,px(386),px(312)};DWORD style=WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX;AdjustWindowRect(&r,style,FALSE);
        HWND w=CreateWindowW(wc.lpszClassName,L"Virtual Car",style,CW_USEDEFAULT,CW_USEDEFAULT,r.right-r.left,r.bottom-r.top,nullptr,nullptr,h,nullptr);require(w!=nullptr,"Window creation failed");
        ShowWindow(w,show);MSG msg{};while(GetMessageW(&msg,nullptr,0,0)>0){if(!IsDialogMessageW(w,&msg)){TranslateMessage(&msg);DispatchMessageW(&msg);}}return static_cast<int>(msg.wParam);
    }catch(const std::exception&e){MessageBoxW(nullptr,error(e).c_str(),L"Virtual Car",MB_OK|MB_ICONERROR);return 1;}
}


#ifdef VC119_SELFTEST
#include <cstdio>
static void fixture(const S&p,const std::vector<unsigned char>&b){
    Handle f;f.h=CreateFileW(p.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    require(f.h!=INVALID_HANDLE_VALUE,"Test fixture already exists or cannot be created");
    DWORD n=0;require(WriteFile(f.h,b.data(),static_cast<DWORD>(b.size()),&n,nullptr)&&n==b.size()&&FlushFileBuffers(f.h),"Fixture write failed");
}
static std::vector<unsigned char> ascii(const std::string&s){return {s.begin(),s.end()};}
template<class F>static void reject(F&&fn,const char*expected){
    try{fn();}catch(const std::runtime_error&e){require(std::string(e.what())==expected,"Unexpected rejection reason");return;}
    throw std::runtime_error("Expected rejection but operation succeeded");
}
static void testRegString(HKEY h,const wchar_t*n,const S&v){
    require(RegSetValueExW(h,n,0,REG_SZ,reinterpret_cast<const BYTE*>(v.c_str()),static_cast<DWORD>((v.size()+1)*sizeof(wchar_t)))==ERROR_SUCCESS,"Test registry write failed");
}
static void testRegNumber(HKEY h,const wchar_t*n,DWORD v){
    require(RegSetValueExW(h,n,0,REG_DWORD,reinterpret_cast<const BYTE*>(&v),sizeof(v))==ERROR_SUCCESS,"Test registry DWORD write failed");
}
static void registryTests(const S&dir,const S&dll,const std::string&valid){
    // Unique private HKCU key. Never create or open a production adapter for writing.
    const S name=L"Software\\VirtualCarVC120-Test-"+std::to_wstring(GetCurrentProcessId())+L"-"+std::to_wstring(GetTickCount64());
    Key base;
    DWORD disposition=0;
    require(RegCreateKeyExW(HKEY_CURRENT_USER,name.c_str(),0,nullptr,REG_OPTION_VOLATILE,KEY_ALL_ACCESS|KEY_WOW64_32KEY,nullptr,&base.h,&disposition)==ERROR_SUCCESS,"Test registry root failed");
    require(disposition==REG_CREATED_NEW_KEY,"Test registry root already exists");
    struct Cleanup{
        Key&key;const S&name;
        ~Cleanup(){
            testRegistry=nullptr;
            if(key.h){
                RegDeleteKeyW(key.h,L"Legacy");
                RegDeleteKeyW(key.h,L"Adapter");
                RegCloseKey(key.h);key.h=nullptr;
                RegDeleteKeyExW(HKEY_CURRENT_USER,name.c_str(),KEY_WOW64_32KEY,0);
            }
        }
    }cleanup{base,name};
    testRegistry=base.h;
    const S mutexName=L"Local\\VC120-test-"+std::to_wstring(GetCurrentProcessId());
    auto select=[&](){Key k;return ownedAt(k,base.h,L"Adapter",L"Legacy");};
    auto changeTest=[&](bool undo){changeAt(undo,base.h,L"Adapter",L"Legacy",mutexName.c_str());};
    int count=0;auto pass=[&](const char*n){++count;std::printf("VC120_TEST %02d PASS %s\n",count,n);};
    reject([&]{select();},"Canonical J2534 adapter unavailable");pass("Missing adapter refused");
    const S old=join(dir,L"old-provider"),next=join(dir,L"new-provider");
    require(CreateDirectoryW(old.c_str(),nullptr)&&CreateDirectoryW(next.c_str(),nullptr),"Test provider directory creation failed");
    original=join(old,dllName);candidate=join(next,dllName);sourceProfile=join(old,L"virtualcar.ini");profile=join(next,L"virtualcar.ini");journal=join(next,L"rollback.sha256");
    fixture(original,ascii("abc"));fixture(sourceProfile,ascii(valid));fixture(candidate,bytes(dll));
    {
        Key k;require(RegCreateKeyExW(base.h,L"Adapter",0,nullptr,REG_OPTION_VOLATILE,KEY_ALL_ACCESS,nullptr,&k.h,nullptr)==ERROR_SUCCESS,"Test adapter creation failed");
        testRegString(k.h,L"Vendor",L"J2534 Lab");testRegString(k.h,L"Name",L"J2534 Lab Adapter");
        testRegString(k.h,L"ConfigApplication",L"");testRegString(k.h,L"FunctionLibrary",original);
        testRegNumber(k.h,L"CAN",1);testRegNumber(k.h,L"ISO15765",1);testRegNumber(k.h,L"MessageVersion",0x0404);
    }
    require(select()==original,"Owned fixture mismatch");pass("Canonical registry layout recognized");
    changeTest(false);
    require(select()==candidate&&bytes(profile)==bytes(sourceProfile)&&readJournal()==digest(original),"Connect readback mismatch");pass("Connect changes only FunctionLibrary");
    reject([&]{changeTest(false);},"Registration is not the expected source");require(select()==candidate,"Repeated connect changed selection");pass("Repeated connect refused");
    require(DeleteFileW(original.c_str())!=0,"Test original removal failed");fixture(original,ascii("modified"));
    reject([&]{changeTest(true);},"Original DLL changed since backup");require(select()==candidate,"Rejected rollback changed selection");
    require(DeleteFileW(original.c_str())!=0,"Test original reset failed");fixture(original,ascii("abc"));pass("Changed original blocks rollback");
    changeTest(true);require(select()==original,"Rollback readback mismatch");pass("Rollback restores original path");
    {
        Key k;require(RegCreateKeyExW(base.h,L"Legacy",0,nullptr,REG_OPTION_VOLATILE,KEY_ALL_ACCESS,nullptr,&k.h,nullptr)==ERROR_SUCCESS,"Legacy fixture failed");
    }
    reject([&]{changeTest(false);},"Legacy adapter conflict");
    require(RegDeleteKeyW(base.h,L"Legacy")==ERROR_SUCCESS&&select()==original,"Legacy cleanup failed");pass("Legacy conflict refused");
    {
        Key k;require(RegOpenKeyExW(base.h,L"Adapter",0,KEY_ALL_ACCESS,&k.h)==ERROR_SUCCESS,"Test key open failed");testRegString(k.h,L"Unexpected",L"value");
        reject([&]{changeTest(false);},"Unexpected adapter registry layout");
        require(RegDeleteValueW(k.h,L"Unexpected")==ERROR_SUCCESS,"Extra value cleanup failed");
    }
    require(select()==original,"Extra value refusal changed selection");pass("Extra registry value refused");
    {
        Key k;require(RegOpenKeyExW(base.h,L"Adapter",0,KEY_ALL_ACCESS,&k.h)==ERROR_SUCCESS,"Test key open failed");
        testRegString(k.h,L"FunctionLibrary",join(dir,L"unrelated.dll"));
        reject([&]{changeTest(false);},"Registration is not the expected source");
        require(regstr(k.h,L"FunctionLibrary")==join(dir,L"unrelated.dll"),"Unexpected provider overwritten");
        testRegString(k.h,L"FunctionLibrary",original);
    }
    pass("Unexpected provider preserved");
    require(DeleteFileW(candidate.c_str())!=0,"Test candidate removal failed");fixture(candidate,ascii("modified"));
    reject([&]{changeTest(false);},"Candidate DLL checksum mismatch");require(select()==original,"Bad DLL changed selection");
    require(DeleteFileW(candidate.c_str())!=0,"Test candidate reset failed");fixture(candidate,bytes(dll));pass("Changed candidate blocks connect");
    // Exercise the same WM_CREATE, controls and refresh logic, without showing
    // a window or invoking the elevated helper. No desktop screenshot claim.
    HINSTANCE instance=GetModuleHandleW(nullptr);WNDCLASSW wc{};
    wc.lpfnWndProc=wnd;wc.hInstance=instance;wc.hCursor=LoadCursorW(nullptr,IDC_ARROW);
    wc.hbrBackground=reinterpret_cast<HBRUSH>(COLOR_WINDOW+1);wc.lpszClassName=L"VC120TestWindow";
    require(RegisterClassW(&wc)!=0,"Test window class failed");
    HWND w=CreateWindowW(wc.lpszClassName,L"Virtual Car",WS_OVERLAPPEDWINDOW,0,0,430,350,nullptr,nullptr,instance,nullptr);
    require(w!=nullptr,"Hidden window creation failed");
    struct WindowCleanup{HWND w;~WindowCleanup(){DestroyWindow(w);}} windowCleanup{w};
    require(IsWindow(check)&&IsWindow(status)&&IsWindow(connectBtn)&&IsWindow(restoreBtn)&&!IsWindowVisible(w),"Control creation failed");
    require(!IsWindowEnabled(connectBtn)&&!IsWindowEnabled(restoreBtn),"Unchecked controls enabled");pass("Hidden Win32 window and initial control states");
    SendMessageW(check,BM_SETCHECK,BST_CHECKED,0);refresh();
    require(IsWindowEnabled(connectBtn)&&!IsWindowEnabled(restoreBtn),"Ready control state incorrect");
    changeTest(false);refresh();
    require(!IsWindowEnabled(connectBtn)&&IsWindowEnabled(restoreBtn),"Connected control state incorrect");
    changeTest(true);refresh();
    require(IsWindowEnabled(connectBtn)&&!IsWindowEnabled(restoreBtn)&&select()==original,"Restored control state incorrect");pass("Connect and restore control states");
    require(count==12,"Registry/UI test count mismatch");
    HDC dc=GetDC(status);require(dc!=nullptr,"Test device context failed");
    LRESULT brush=SendMessageW(w,WM_CTLCOLORSTATIC,reinterpret_cast<WPARAM>(dc),reinterpret_cast<LPARAM>(status));
    bool colors=brush==reinterpret_cast<LRESULT>(GetSysColorBrush(COLOR_WINDOW))&&GetBkColor(dc)==GetSysColor(COLOR_WINDOW)&&GetTextColor(dc)==GetSysColor(COLOR_WINDOWTEXT);
    ReleaseDC(status,dc);require(colors,"Static background does not match window");
    std::puts("VC122_UI_COLORS=PASS");
    std::puts("VC120_REGISTRY_UI_SELFTEST=PASS 12/12; private HKCU and hidden window only");
}
int wmain(int argc,wchar_t**argv){
    try{
        require(argc==3,"Expected new test directory and packaged DLL");
        const S dir=argv[1],dll=argv[2];
        require(!exists(dir),"Self-test requires a new directory");
        local(parent(dir),false);
        require(CreateDirectoryW(dir.c_str(),nullptr)!=0,"Cannot create test directory");
        local(dir,false);
        const S expected=L"BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD";
        const S other(64,L'0');
        const std::string valid="[Vehicle]\r\nVIN=YV1CZ0002A0000001\r\n[J2534_2]\r\nEnabled=1\r\n[Diagnostics]\r\nEnableGGDCemLab=1\r\n";
        int count=0;
        auto pass=[&](const char*name){++count;std::printf("VC119_TEST %02d PASS %s\n",count,name);};
        require(sha(ascii("abc"))==expected,"SHA256 known answer mismatch");pass("SHA256 known answer");
        require(digest(dll)==VC115_PROVIDER_SHA,"Packaged DLL mismatch");pass("Exact packaged DLL hash");
        sourceProfile=join(dir,L"ansi-source.ini");profile=join(dir,L"ansi-copy.ini");journal=join(dir,L"ansi-journal.sha256");
        fixture(sourceProfile,ascii(valid));prepareFiles(expected);
        require(bytes(profile)==ascii(valid)&&readJournal()==expected,"ANSI preservation failed");pass("ANSI byte-exact preparation");
        prepareFiles(expected);verifyRollback(expected);pass("Idempotent preparation and rollback guard");
        reject([&]{verifyRollback(other);},"Original DLL changed since backup");pass("Changed original DLL hash refused");
        reject([&]{saveJournal(other);},"Existing rollback journal differs");pass("Conflicting journal refused");
        sourceProfile=join(dir,L"utf16-source.ini");profile=join(dir,L"utf16-copy.ini");journal=join(dir,L"utf16-journal.sha256");
        std::vector<unsigned char>wide{0xff,0xfe};for(unsigned char c:valid){wide.push_back(c);wide.push_back(0);}
        fixture(sourceProfile,wide);prepareFiles(expected);require(bytes(profile)==wide,"UTF16 preservation failed");pass("UTF16LE byte-exact preparation");
        const S ipc=join(dir,L"ipc.ini");fixture(ipc,ascii(valid+"[VC108N_ExternalStateLab]\r\nEnabled=1\r\n"));
        reject([&]{validateProfile(ipc);},"External IPC profile is not supported");pass("External IPC profile refused");
        const S bad=join(dir,L"invalid-vin.ini");auto invalid=valid;invalid.replace(invalid.find("YV1CZ0002A0000001"),17,"INVALID");
        fixture(bad,ascii(invalid));reject([&]{validateProfile(bad);},"Valid VIN required");pass("Invalid VIN refused");
        profile=join(dir,L"different.ini");fixture(profile,ascii(valid+";different\r\n"));sourceProfile=join(dir,L"ansi-source.ini");
        reject([&]{prepareFiles(expected);},"Candidate INI differs; extract a fresh package");pass("Modified candidate profile refused");
        journal=join(dir,L"corrupt.sha256");fixture(journal,ascii(std::string(64,'x')));
        reject([&]{readJournal();},"Invalid rollback hash");pass("Corrupt journal refused");
        journal=join(dir,L"missing.sha256");reject([&]{saveJournal(S(64,L'Z'));},"Invalid rollback hash character");
        require(!exists(journal),"Invalid hash created journal");pass("Invalid journal hash refused before write");
        require(count==12,"Self-test count mismatch");
        std::puts("VC119_CONTROLLER_SELFTEST=PASS 12/12; no registry, no VIDA");
        registryTests(dir,dll,valid);return 0;
    }catch(const std::exception&e){std::fprintf(stderr,"VC119_CONTROLLER_SELFTEST=FAIL %s\n",e.what());return 1;}
}
#endif
