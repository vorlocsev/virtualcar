// VC122 native installer/controller; x86, no runtime outside Windows.
#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <shlobj.h>
#include <bcrypt.h>
#include <string>
#include <vector>
#include <array>
#include <stdexcept>
#include <algorithm>
#pragma comment(lib,"bcrypt.lib")
#pragma comment(lib,"advapi32.lib")
#pragma comment(lib,"shell32.lib")
#pragma comment(lib,"user32.lib")
#pragma comment(lib,"gdi32.lib")
using S=std::wstring;
constexpr wchar_t kHash[]=L"C9792583ED670612EB430208BCE443E42B0E71C6FA9322983B63A752EE938AFF";
constexpr wchar_t kParent[]=L"SOFTWARE\\PassThruSupport.04.04";
constexpr wchar_t kName[]=L"J2534 Lab Adapter";
constexpr wchar_t kLegacy[]=L"SectorV Virtual Car";
constexpr wchar_t kDll[]=L"VirtualCarJ2534.dll";
S root,dir,dll,ini,seal;
struct Key { HKEY h=nullptr; ~Key(){if(h)RegCloseKey(h);} Key()=default; Key(const Key&)=delete; Key& operator=(const Key&)=delete; };
struct File { HANDLE h=INVALID_HANDLE_VALUE; ~File(){if(h!=INVALID_HANDLE_VALUE&&h)CloseHandle(h);} File()=default; File(const File&)=delete; File& operator=(const File&)=delete; };
void need(bool ok,const char*why){if(!ok)throw std::runtime_error(why);}
S join(const S&a,const S&b){return a+L"\\"+b;}
S parent(const S&s){return s.substr(0,s.find_last_of(L'\\'));}
bool same(const S&a,const S&b){return CompareStringOrdinal(a.c_str(),-1,b.c_str(),-1,TRUE)==CSTR_EQUAL;}
bool missing(LONG rc){return rc==ERROR_FILE_NOT_FOUND||rc==ERROR_PATH_NOT_FOUND;}
bool exists(const S&p){DWORD a=GetFileAttributesW(p.c_str());if(a!=INVALID_FILE_ATTRIBUTES)return true;need(missing(static_cast<LONG>(GetLastError())),"Cannot inspect file path");return false;}
void plain(const S&s,bool file){
    need(s.size()>3&&s.size()<240&&s[1]==L':'&&s[2]==L'\\',"Short local absolute path required");
    wchar_t b[MAX_PATH]{};DWORD n=GetFullPathNameW(s.c_str(),MAX_PATH,b,nullptr);
    need(n>0&&n<MAX_PATH&&same(b,s)&&GetDriveTypeW(s.substr(0,3).c_str())==DRIVE_FIXED,"Unsafe path");
    for(S p=s;;p=parent(p)){
        if(p.size()==2)p+=L"\\";
        DWORD a=GetFileAttributesW(p.c_str());
        need(a!=INVALID_FILE_ATTRIBUTES&&!(a&FILE_ATTRIBUTE_REPARSE_POINT),"Missing path or reparse point");
        need((p==s&&file)?!(a&FILE_ATTRIBUTE_DIRECTORY):(a&FILE_ATTRIBUTE_DIRECTORY)!=0,"Unexpected path type");
        if(p.size()==3)break;
    }
}
std::vector<unsigned char> read(const S&p,DWORD max=64*1024*1024){
    plain(p,true);File f;f.h=CreateFileW(p.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
    LARGE_INTEGER n{};need(f.h!=INVALID_HANDLE_VALUE&&GetFileSizeEx(f.h,&n)&&n.QuadPart>0&&n.QuadPart<=max,"Invalid file size or open failure");
    std::vector<unsigned char>b(static_cast<size_t>(n.QuadPart));DWORD got=0;
    need(ReadFile(f.h,b.data(),static_cast<DWORD>(b.size()),&got,nullptr)&&got==b.size(),"File read failed");return b;
}
void writeNew(const S&p,const std::vector<unsigned char>&b){
    plain(parent(p),false);File f;f.h=CreateFileW(p.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
    need(f.h!=INVALID_HANDLE_VALUE,"Refusing overwrite or file creation failed");DWORD got=0;
    need(WriteFile(f.h,b.data(),static_cast<DWORD>(b.size()),&got,nullptr)&&got==b.size()&&FlushFileBuffers(f.h),"File write failed");
}
S hash(const std::vector<unsigned char>&b){
    std::vector<unsigned char> obj;BCRYPT_ALG_HANDLE a=nullptr;BCRYPT_HASH_HANDLE h=nullptr;
    struct Cleanup{BCRYPT_ALG_HANDLE&a;BCRYPT_HASH_HANDLE&h;~Cleanup(){if(h)BCryptDestroyHash(h);if(a)BCryptCloseAlgorithmProvider(a,0);}} cleanup{a,h};
    need(BCryptOpenAlgorithmProvider(&a,BCRYPT_SHA256_ALGORITHM,nullptr,0)>=0,"SHA256 unavailable");DWORD n=0,z=0;
    need(BCryptGetProperty(a,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&n),sizeof(n),&z,0)>=0&&n>0,"SHA256 object failed");obj.resize(n);std::array<unsigned char,32> out{};
    need(BCryptCreateHash(a,&h,obj.data(),n,nullptr,0,0)>=0&&BCryptHashData(h,const_cast<PUCHAR>(b.data()),static_cast<ULONG>(b.size()),0)>=0&&BCryptFinishHash(h,out.data(),32,0)>=0,"SHA256 failed");
    const wchar_t*hex=L"0123456789ABCDEF";S s;for(auto x:out){s+=hex[x>>4];s+=hex[x&15];}return s;
}
std::vector<unsigned char> hashBytes(){std::vector<unsigned char>b;for(wchar_t c:S(kHash))b.push_back(static_cast<unsigned char>(c));return b;}
void validateProfile(const S&p){
    const auto b=read(p,8*1024*1024);need(!(b.size()>=2&&b[0]==0xfe&&b[1]==0xff),"UTF16BE profile unsupported");
    wchar_t v[512]{};auto get=[&](const wchar_t*s,const wchar_t*k){DWORD n=GetPrivateProfileStringW(s,k,L"",v,512,p.c_str());need(n<511,"INI value too long");return S(v);};
    auto vin=get(L"Vehicle",L"VIN");need(vin.size()==17&&std::all_of(vin.begin(),vin.end(),[](wchar_t c){return(c>=L'A'&&c<=L'Z'&&c!=L'I'&&c!=L'O'&&c!=L'Q')||(c>=L'0'&&c<=L'9');}),"Working VIN profile required");
    need(get(L"J2534_2",L"Enabled")==L"1"&&get(L"Diagnostics",L"EnableGGDCemLab")==L"1","Working CEM/J2534 profile required");
    wchar_t names[32768]{};DWORD n=GetPrivateProfileSectionNamesW(names,32768,p.c_str());need(n>0&&n<32766,"INI section enumeration failed");
    for(const wchar_t*q=names;*q;q+=wcslen(q)+1)need(!same(q,L"VC108N_ExternalStateLab"),"External IPC profile not supported");
}
void paths(){
    wchar_t p[MAX_PATH]{};DWORD n=GetModuleFileNameW(nullptr,p,MAX_PATH);need(n>0&&n<MAX_PATH,"Cannot locate application");root=parent(p);plain(root,false);
    need(SHGetFolderPathW(nullptr,CSIDL_PROGRAM_FILESX86,nullptr,SHGFP_TYPE_CURRENT,p)==S_OK,"Program Files x86 unavailable");plain(p,false);
    dir=join(p,L"VirtualCar-VC121");dll=join(dir,kDll);ini=join(dir,L"virtualcar.ini");seal=join(dir,L"provider.sha256");
}
S regstr(HKEY h,const wchar_t*n){DWORD t=0,z=0;need(RegQueryValueExW(h,n,nullptr,&t,nullptr,&z)==ERROR_SUCCESS&&t==REG_SZ&&z>=2&&z<=4096&&z%2==0,"Registry string invalid");std::vector<wchar_t>b(z/2);need(RegQueryValueExW(h,n,nullptr,&t,reinterpret_cast<BYTE*>(b.data()),&z)==ERROR_SUCCESS&&t==REG_SZ&&z==b.size()*2&&b.back()==0&&wcslen(b.data())==b.size()-1,"Registry string changed");return b.data();}
DWORD regnum(HKEY h,const wchar_t*n){DWORD v=0,t=0,z=sizeof(v);need(RegQueryValueExW(h,n,nullptr,&t,reinterpret_cast<BYTE*>(&v),&z)==ERROR_SUCCESS&&t==REG_DWORD&&z==sizeof(v),"Registry DWORD invalid");return v;}
void setstr(HKEY h,const wchar_t*n,const S&v){need(RegSetValueExW(h,n,0,REG_SZ,reinterpret_cast<const BYTE*>(v.c_str()),static_cast<DWORD>((v.size()+1)*sizeof(wchar_t)))==ERROR_SUCCESS,"Registry string write failed");}
void setnum(HKEY h,const wchar_t*n,DWORD v){need(RegSetValueExW(h,n,0,REG_DWORD,reinterpret_cast<const BYTE*>(&v),sizeof(v))==ERROR_SUCCESS,"Registry DWORD write failed");}
// Empty result only means key absent. Any foreign or malformed key fails closed.
S selected(HKEY hive,const wchar_t*base,bool write=false){
    Key p,k,l;LONG rc=RegOpenKeyExW(hive,base,0,KEY_READ|KEY_WOW64_32KEY,&p.h);if(missing(rc))return {};need(rc==ERROR_SUCCESS,"Cannot open J2534 registry");
    rc=RegOpenKeyExW(p.h,kLegacy,0,KEY_READ,&l.h);need(missing(rc),"Legacy adapter conflict");
    rc=RegOpenKeyExW(p.h,kName,0,KEY_READ|(write?KEY_SET_VALUE:0),&k.h);if(missing(rc))return {};need(rc==ERROR_SUCCESS,"Cannot open adapter");
    DWORD sub=0,vals=0;need(RegQueryInfoKeyW(k.h,nullptr,nullptr,nullptr,&sub,nullptr,nullptr,&vals,nullptr,nullptr,nullptr,nullptr)==ERROR_SUCCESS&&sub==0&&vals==7,"Unexpected adapter layout");
    need(regstr(k.h,L"Vendor")==L"J2534 Lab"&&regstr(k.h,L"Name")==kName&&regstr(k.h,L"ConfigApplication").empty()&&regnum(k.h,L"CAN")==1&&regnum(k.h,L"ISO15765")==1&&regnum(k.h,L"MessageVersion")==0x404,"Adapter ownership mismatch");
    auto s=regstr(k.h,L"FunctionLibrary");need(!s.empty(),"Empty registered DLL path");return s;
}
void checkFiles(){need(hash(read(dll))==kHash,"Installed DLL SHA256 mismatch");need(read(seal,64)==hashBytes(),"Installed provider seal mismatch");validateProfile(ini);}
void prepare(){
    if(exists(dir)){plain(dir,false);checkFiles();return;}
    // Source DLL pinned, profile is user-local. Nothing in Program Files is overwritten.
    const S source=join(root,kDll),profile=join(root,L"virtualcar.ini");auto bin=read(source);need(hash(bin)==kHash,"Package DLL SHA256 mismatch");validateProfile(profile);auto cfg=read(profile,8*1024*1024);
    need(CreateDirectoryW(dir.c_str(),nullptr)!=0,"Install directory creation failed");plain(dir,false);
    writeNew(dll,bin);writeNew(ini,cfg);writeNew(seal,hashBytes());checkFiles();need(read(ini,8*1024*1024)==cfg,"Profile copy mismatch");
}
void createRegistration(){
    Key p,k;DWORD d=0;need(RegCreateKeyExW(HKEY_LOCAL_MACHINE,kParent,0,nullptr,0,KEY_READ|KEY_CREATE_SUB_KEY|KEY_WOW64_32KEY,nullptr,&p.h,nullptr)==ERROR_SUCCESS,"Cannot open registry for install");
    need(selected(HKEY_LOCAL_MACHINE,kParent).empty(),"Registration appeared concurrently");
    need(RegCreateKeyExW(p.h,kName,0,nullptr,0,KEY_READ|KEY_SET_VALUE,nullptr,&k.h,&d)==ERROR_SUCCESS&&d==REG_CREATED_NEW_KEY,"Adapter already exists or cannot be created");
    try{setstr(k.h,L"Vendor",L"J2534 Lab");setstr(k.h,L"Name",kName);setstr(k.h,L"ConfigApplication",L"");setnum(k.h,L"CAN",1);setnum(k.h,L"ISO15765",1);setnum(k.h,L"MessageVersion",0x404);setstr(k.h,L"FunctionLibrary",dll);need(RegFlushKey(k.h)==ERROR_SUCCESS,"Registry flush failed");}
    catch(...){RegCloseKey(k.h);k.h=nullptr;RegDeleteKeyW(p.h,kName);throw;}
    need(same(selected(HKEY_LOCAL_MACHINE,kParent),dll),"Registry readback failed; inspect before retrying");
}
void operate(bool remove){
    File mutex;mutex.h=CreateMutexW(nullptr,FALSE,L"Global\\VirtualCarVC121Registration");need(mutex.h!=nullptr,"Registration mutex failed");DWORD w=WaitForSingleObject(mutex.h,0);need(w==WAIT_OBJECT_0||w==WAIT_ABANDONED,"Another registration operation is running");struct Unlock{HANDLE h;~Unlock(){ReleaseMutex(h);}} unlock{mutex.h};
    const S current=selected(HKEY_LOCAL_MACHINE,kParent);need(current.empty()||same(current,dll),"Unrelated adapter selected; no changes made");
    if(!remove){prepare();if(current.empty())createRegistration();else need(same(selected(HKEY_LOCAL_MACHINE,kParent),dll),"Registry changed concurrently");return;}
    need(same(current,dll),"Only our installed adapter can be removed");
    // Preserve all installed files, including INI. Removal still works if DLL is corrupted.
    validateProfile(ini);auto cfg=read(ini,8*1024*1024);S backup=join(dir,L"profile-before-remove-"+std::to_wstring(GetCurrentProcessId())+L"-"+std::to_wstring(GetTickCount64())+L".ini");writeNew(backup,cfg);need(read(backup,8*1024*1024)==cfg,"Profile backup mismatch");
    Key p;need(RegOpenKeyExW(HKEY_LOCAL_MACHINE,kParent,0,KEY_READ|KEY_WRITE|KEY_WOW64_32KEY,&p.h)==ERROR_SUCCESS,"Registry write access denied");need(same(selected(HKEY_LOCAL_MACHINE,kParent),dll),"Registry changed concurrently");need(RegDeleteKeyW(p.h,kName)==ERROR_SUCCESS,"Adapter removal failed");need(RegFlushKey(p.h)==ERROR_SUCCESS&&selected(HKEY_LOCAL_MACHINE,kParent).empty(),"Removal readback failed");
}
HWND state=nullptr,install=nullptr,removeBtn=nullptr,check=nullptr;HFONT font=nullptr;int dpi=96;
int px(int n){return MulDiv(n,dpi,96);}
S error(const std::exception&e){std::string s=e.what();return S(s.begin(),s.end());}
void refresh(){S msg;bool i=false,r=false;try{auto s=selected(HKEY_LOCAL_MACHINE,kParent);if(s.empty()){msg=L"Not registered";i=true;}else if(same(s,dll)){r=true;checkFiles();msg=L"Installed - ready for VIDA";}else msg=L"Different adapter selected - no changes allowed";}catch(const std::exception&e){msg=error(e);}const bool ok=SendMessageW(check,BM_GETCHECK,0,0)==BST_CHECKED;EnableWindow(install,i&&ok);EnableWindow(removeBtn,r&&ok);SetWindowTextW(state,msg.c_str());}
HWND ctl(HWND w,const wchar_t*c,const wchar_t*t,DWORD style,int x,int y,int width,int height,int id){HWND h=CreateWindowExW(0,c,t,WS_CHILD|WS_VISIBLE|style,px(x),px(y),px(width),px(height),w,reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),GetModuleHandleW(nullptr),nullptr);SendMessageW(h,WM_SETFONT,reinterpret_cast<WPARAM>(font),TRUE);return h;}
LRESULT CALLBACK wnd(HWND w,UINT m,WPARAM wp,LPARAM lp){switch(m){
case WM_CREATE:font=CreateFontW(-px(16),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");ctl(w,L"STATIC",L"XC90 V8 | Virtual Car",0,16,16,370,28,0);state=ctl(w,L"STATIC",L"",0,16,58,370,50,0);check=ctl(w,L"BUTTON",L"VIDA and other clients are closed",BS_AUTOCHECKBOX|WS_TABSTOP,16,116,370,28,101);install=ctl(w,L"BUTTON",L"Install / Connect to VIDA",BS_PUSHBUTTON|WS_TABSTOP,16,154,370,38,102);removeBtn=ctl(w,L"BUTTON",L"Remove registration (keep files)",BS_PUSHBUTTON|WS_TABSTOP,16,202,370,38,103);ctl(w,L"STATIC",L"J2534 Lab Adapter | x86 | VC122",0,16,256,370,24,0);refresh();return 0;
case WM_COMMAND:if(HIWORD(wp)==BN_CLICKED){int id=LOWORD(wp);if(id==101)refresh();if((id==102||id==103)&&SendMessageW(check,BM_GETCHECK,0,0)==BST_CHECKED){bool rem=id==103;if(MessageBoxW(w,rem?L"Remove only the Virtual Car registration? Files and profile will be retained.":L"Install the verified Virtual Car J2534 adapter?",L"Virtual Car",MB_YESNO|MB_DEFBUTTON2|MB_ICONQUESTION)==IDYES){try{operate(rem);MessageBoxW(w,rem?L"Registration removed. Files retained.":L"Adapter installed. Open VIDA.",L"Virtual Car",MB_OK|MB_ICONINFORMATION);}catch(const std::exception&e){MessageBoxW(w,error(e).c_str(),L"Virtual Car",MB_OK|MB_ICONERROR);}}SendMessageW(check,BM_SETCHECK,BST_UNCHECKED,0);refresh();}}return 0;
case WM_ACTIVATE:if(state&&LOWORD(wp)!=WA_INACTIVE)refresh();return 0;
case WM_DESTROY:DeleteObject(font);PostQuitMessage(0);return 0;
default:return DefWindowProcW(w,m,wp,lp);}}
int WINAPI wWinMain(HINSTANCE h,HINSTANCE,PWSTR,int show){try{paths();SetProcessDPIAware();HDC dc=GetDC(nullptr);if(dc){dpi=GetDeviceCaps(dc,LOGPIXELSX);ReleaseDC(nullptr,dc);}WNDCLASSW wc{};wc.lpfnWndProc=wnd;wc.hInstance=h;wc.hCursor=LoadCursorW(nullptr,IDC_ARROW);wc.hbrBackground=reinterpret_cast<HBRUSH>(COLOR_WINDOW+1);wc.lpszClassName=L"VirtualCarVC122";need(RegisterClassW(&wc)!=0,"Window registration failed");RECT r{0,0,px(402),px(294)};DWORD style=WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX;need(AdjustWindowRect(&r,style,FALSE)!=0,"Window sizing failed");HWND w=CreateWindowW(wc.lpszClassName,L"Virtual Car",style,CW_USEDEFAULT,CW_USEDEFAULT,r.right-r.left,r.bottom-r.top,nullptr,nullptr,h,nullptr);need(w!=nullptr,"Window creation failed");ShowWindow(w,show);MSG msg{};BOOL rc=0;while((rc=GetMessageW(&msg,nullptr,0,0))>0){if(!IsDialogMessageW(w,&msg)){TranslateMessage(&msg);DispatchMessageW(&msg);}}return rc<0?1:static_cast<int>(msg.wParam);}catch(const std::exception&e){MessageBoxW(nullptr,error(e).c_str(),L"Virtual Car",MB_OK|MB_ICONERROR);return 1;}}
