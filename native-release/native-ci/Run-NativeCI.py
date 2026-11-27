#!/usr/bin/env python3
"""Portable native CI; no installed provider, private profile or VIDA required."""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

def sha(b): return hashlib.sha256(b).hexdigest().upper()
def require(v,m):
    if not v: raise RuntimeError(m)
def normalize_output(raw):
    return raw.decode('utf-8-sig',errors='replace').replace('\r\n','\n').replace('\r','\n')

def run(cmd,log,env=None):
    p=subprocess.run([str(x) for x in cmd],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env,timeout=600)
    log.write_bytes(p.stdout); t=normalize_output(p.stdout); print(t,flush=True)
    require(p.returncode==0,'Command failed: '+str(log)); return t

def patch_fixture(raw):
    # Only the identity mode uses the external staged file. All other test logic is unchanged.
    anchor=b"[IO.File]::WriteAllText((Join-Path $directory 'virtualcar.ini'), $profile, [Text.Encoding]::ASCII)"
    replacement=b"""if ($IdentityReplay) {
    $staged = $env:VC127B3_SYNTHETIC_PROFILE
    if (-not $staged -or -not (Test-Path -LiteralPath $staged -PathType Leaf)) { throw 'Staged profile missing' }
    $bytes = [IO.File]::ReadAllBytes($staged)
    $actual = [Text.Encoding]::ASCII.GetString($bytes).Replace("`r`n", "`n").TrimEnd([char]10)
    $expected = $profile.Replace("`r`n", "`n").TrimEnd([char]10)
    if ($actual -cne $expected) { throw 'Staged profile differs from exact synthetic fixture' }
    if ((Get-FileHash -LiteralPath $staged -Algorithm SHA256).Hash -cne $env:VC127B3_PROFILE_SHA) { throw 'Profile hash mismatch' }
    [IO.File]::WriteAllBytes((Join-Path $directory 'virtualcar.ini'), $bytes)
    Write-Output 'VC127B3_STANDALONE_PROFILE=PASS'
} else {
    [IO.File]::WriteAllText((Join-Path $directory 'virtualcar.ini'), $profile, [Text.Encoding]::ASCII)
}"""
    require(raw.count(anchor)==1,'Fixture patch anchor mismatch')
    return raw.replace(anchor,replacement,1)


def groups(t,prefix,count):
    got=sorted(map(int,re.findall(r'^PASS '+re.escape(prefix)+r' (\d+):',t,re.M)))
    require(got==list(range(1,count+1)),'Unexpected test groups')

HARNESS='#define wWinMain vc127b5_unused_gui_entry\n#include "VirtualCar.bound.cpp"\n#undef wWinMain\n#include <iostream>\n// Only file/profile routines are called. No paths(), operate(), createRegistration(),\n// selected(), refresh(), wnd(), or GUI entry point is called.\nvoid testdir(const S&p){need(CreateDirectoryW(p.c_str(),nullptr)!=0,"Test directory creation failed");plain(p,false);}\nstd::vector<unsigned char> bytes(const std::string&s){return {s.begin(),s.end()};}\nvoid gate(int n,const char*label){std::cout<<"VC127B5_TEST "<<n<<" PASS "<<label<<std::endl;}\ntemplate<class F> void reject(F f,const char*expected){bool ok=false;try{f();}catch(const std::exception&e){ok=std::string(e.what())==expected;}need(ok,"Expected refusal not observed");}\nvoid bindTarget(const S&p){dir=p;dll=join(dir,kDll);ini=join(dir,L"virtualcar.ini");seal=join(dir,L"provider.sha256");}\nint wmain(int argc,wchar_t**argv){try{\n    need(argc==3,"Expected new test directory and isolated DLL");\n    const S lab=argv[1];plain(lab,false);const auto bin=read(argv[2]);need(hash(bin)==kHash,"Harness provider hash mismatch");gate(1,"bound provider SHA256");\n    const auto good=bytes("; synthetic validation-only fixture, NOT a VIDA profile\\r\\n[Vehicle]\\r\\nVIN=YV1CZ0002A0000001\\r\\n[J2534_2]\\r\\nEnabled=1\\r\\n[Diagnostics]\\r\\nEnableGGDCemLab=1\\r\\n");\n    root=join(lab,L"package");testdir(root);writeNew(join(root,kDll),bin);writeNew(join(root,L"virtualcar.ini"),good);\n    validateProfile(join(root,L"virtualcar.ini"));gate(2,"minimal synthetic installer gate fixture");\n    const S transport=join(lab,L"transport.ini");writeNew(transport,read(join(parent(S(argv[2])),L"transport-replay.ini")));reject([&]{validateProfile(transport);},"Working CEM/J2534 profile required");gate(3,"transport-only fixture rejected");\n    const S invalid=join(lab,L"bad-vin.ini");writeNew(invalid,bytes("[Vehicle]\\r\\nVIN=INVALID\\r\\n"));reject([&]{validateProfile(invalid);},"Working VIN profile required");gate(4,"invalid VIN rejected");\n    const S external=join(lab,L"external.ini");auto ext=good;auto extra=bytes("[VC108N_ExternalStateLab]\\r\\nEnabled=1\\r\\n");ext.insert(ext.end(),extra.begin(),extra.end());writeNew(external,ext);reject([&]{validateProfile(external);},"External IPC profile not supported");gate(5,"external IPC rejected");\n    bindTarget(join(lab,L"installed"));prepare();need(read(dll)==bin&&read(ini)==good&&read(seal)==hashBytes(),"Fresh copy mismatch");gate(6,"fresh file preparation and seal");\n    prepare();need(read(dll)==bin&&read(ini)==good&&read(seal)==hashBytes(),"Existing files changed");gate(7,"existing exact files reused");\n    reject([&]{writeNew(ini,good);},"Refusing overwrite or file creation failed");need(read(ini)==good,"Existing INI changed");gate(8,"overwrite refused");\n    bindTarget(join(lab,L"bad-source-target"));root=join(lab,L"bad-source");testdir(root);auto bad=bin;bad[0]^=1;writeNew(join(root,kDll),bad);writeNew(join(root,L"virtualcar.ini"),good);reject([&]{prepare();},"Package DLL SHA256 mismatch");need(!exists(dir),"Invalid source created target");gate(9,"wrong package DLL refused before creation");\n    bindTarget(join(lab,L"bad-seal"));testdir(dir);writeNew(dll,bin);writeNew(ini,good);writeNew(seal,bytes(std::string(64,\'0\')));reject([&]{prepare();},"Installed provider seal mismatch");need(read(seal)==bytes(std::string(64,\'0\'))&&read(ini)==good,"Bad seal target changed");gate(10,"invalid existing seal refused without overwrite");\n    std::cout<<"VC127B5_CONTROLLER_FILES=PASS 10/10; isolated files only"<<std::endl;return 0;\n}catch(const std::exception&e){std::cerr<<"VC127B5_FAIL "<<e.what()<<std::endl;return 1;}}\n'
HARNESS_BUILD='param([string]$Root)\n$ErrorActionPreference=\'Stop\'\n$vswhere=Join-Path ${env:ProgramFiles(x86)} \'Microsoft Visual Studio\\Installer\\vswhere.exe\'\n$v=& $vswhere -latest -products \'*\' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath\nif($LASTEXITCODE -ne 0 -or !$v){throw \'MSVC not found\'}\nImport-Module (Join-Path $v \'Common7\\Tools\\Microsoft.VisualStudio.DevShell.dll\')\nEnter-VsDevShell -VsInstallPath $v -SkipAutomaticLocation -DevCmdArguments \'-arch=x86 -host_arch=x64\'\nif($env:VSCMD_ARG_TGT_ARCH -ne \'x86\'){throw \'Incorrect target architecture\'}\n$src=Join-Path $Root \'ControllerTest.cpp\';$exe=Join-Path $Root \'ControllerTest.exe\';$obj=Join-Path $Root \'ControllerTest.obj\'\n& cl.exe /nologo /std:c++17 /EHsc /O1 /GL /MT /W4 /WX /utf-8 "/Fo$obj" $src /link /LTCG /OPT:REF /OPT:ICF /SUBSYSTEM:CONSOLE /MACHINE:X86 /DYNAMICBASE /NXCOMPAT "/OUT:$exe"\nif($LASTEXITCODE -ne 0){throw \'Harness compilation failed\'}\nWrite-Host \'VC127B5_HARNESS_BUILD=PASS x86 /W4 /WX\'\n& $exe (Join-Path $Root \'lab\') (Join-Path $Root \'VirtualCarJ2534.dll\')\nif($LASTEXITCODE -ne 0){throw \'Harness failed\'}\n'

BUILD_DLL=r"""param([string]$Root,[string]$Python)
$ErrorActionPreference='Stop'
$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$v=& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if($LASTEXITCODE -ne 0 -or !$v){throw 'MSVC not found'}
Import-Module (Join-Path $v 'Common7\Tools\Microsoft.VisualStudio.DevShell.dll')
Enter-VsDevShell -VsInstallPath $v -SkipAutomaticLocation -DevCmdArguments '-arch=x86 -host_arch=x64'
if($env:VSCMD_ARG_TGT_ARCH -ne 'x86'){throw 'Incorrect target architecture'}
if(-not(Get-Command clang-cl.exe -ErrorAction SilentlyContinue)){
 foreach($d in @((Join-Path $v 'VC\Tools\Llvm\x64\bin'),(Join-Path $env:ProgramFiles 'LLVM\bin'))){if(Test-Path (Join-Path $d 'clang-cl.exe')){$env:PATH="$d;$env:PATH";break}}
}
& (Join-Path $Root 'native\j2534\Build-J2534.ps1') -Python $Python
"""
def verify_build_evidence(t,dll,digest):
    # The unified source manifest pins the B3 build tool, not B2.
    matches=re.findall(r'^VC127B3_BUILD=PASS; DLL=(.+) SHA256=([0-9A-F]{64})[ \t]*$',t,re.M)
    require(len(matches)==1,'Expected one B3 build marker')
    path,reported=matches[0]
    require(Path(path).resolve()==dll.resolve() and reported==digest,'Build path or SHA256 mismatch')
    require(len(re.findall(r'^VC108P_PE=PASS x86 exports=14 imports=kernel32\.dll[ \t]*$',t,re.M))==1,'Expected one PE audit marker')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);a=ap.parse_args()
    require(os.name=='nt','Windows required'); source=a.source.resolve()
    manifest=json.loads((source/'manifest.json').read_bytes())
    require(manifest['schema']=='VC127B4-source-v1' and len(manifest['files'])==28,'Unexpected manifest')
    out=Path(tempfile.mkdtemp(prefix='VC127C2-CI-'));work=out/'source';work.mkdir();print('VC127C2_WORK='+str(out),flush=True)
    for n,h in manifest['files'].items():
        require(not Path(n).is_absolute() and '..' not in Path(n).parts and '\\' not in n and ':' not in n,'Unsafe source path')
        data=(source/n).read_bytes();require(sha(data)==h,'Source hash mismatch: '+n);p=work/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    report={'schema':'VC127C2-native-ci-v1','source_manifest_sha256':sha((source/'manifest.json').read_bytes()),'status':'INCOMPLETE','transport_groups':0,'controller_groups':0,'vida':'NOT_TESTED','registration':'NOT_TESTED','registry_writes':False}
    try:
        print('VC127C2_SOURCE=PASS 28/28 exact files',flush=True)
        ps=Path(os.environ['WINDIR'])/'System32/WindowsPowerShell/v1.0/powershell.exe';ps32=Path(os.environ['WINDIR'])/'SysWOW64/WindowsPowerShell/v1.0/powershell.exe'
        require(ps.is_file() and ps32.is_file(),'Windows PowerShell missing')
        def psargs(exe,script,*args):return [exe,'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',script,*args]
        boot=out/'Build-Dll.ps1';boot.write_text(BUILD_DLL,encoding='utf-8')
        t=run(psargs(ps,boot,'-Root',work,'-Python',sys.executable),out/'dll-build.log')
        dlls=list((work/'native/j2534').glob('build-*/VirtualCarJ2534.dll'));require(len(dlls)==1,'Expected one built DLL');dll=dlls[0];digest=sha(dll.read_bytes())
        verify_build_evidence(t,dll,digest)
        report['provider_sha256']=digest
        print('VC127C2_DLL_BUILD=PASS exact reported SHA256 and PE audit',flush=True)
        tests=work/'native/tests';profile=work/'profiles/synthetic/transport-replay.ini';profile_sha=sha(profile.read_bytes())
        runner=out/'verify_native_routes_package.ps1';runner.write_bytes(patch_fixture((tests/'verify_native_routes.ps1').read_bytes()))
        env=dict(os.environ,VC127B3_SYNTHETIC_PROFILE=str(profile),VC127B3_PROFILE_SHA=profile_sha)
        for mode,flags,prefix,count in [('silence',[],'group',8),('identity',['-IdentityReplay'],'group',9),('can-ms',['-CanMsPreflight'],'B3A331 gate',8)]:
            dest=out/mode;t=run(psargs(ps32,runner,'-DllPath',dll,'-OutputDirectory',dest,*flags),out/(mode+'.log'),env);groups(t,prefix,count)
            require(sha((dest/'VirtualCarJ2534.dll').read_bytes())==digest,'Test DLL mismatch')
            if mode=='identity':require('VC127B3_STANDALONE_PROFILE=PASS' in t and sha((dest/'virtualcar.ini').read_bytes())==profile_sha,'Profile test mismatch')
            report['transport_groups']+=count
        audit=out/'route-audit.json';run([sys.executable,'-B',tests/'verify_native_routes.py',out/'silence/VirtualCar/dev47-backend.jsonl','--output',audit],out/'route-audit.log');require(json.loads(audit.read_bytes())['native_route_regression_verified'] is True,'Audit failed')
        print('VC127C2_TRANSPORT=PASS 25/25',flush=True)
        built=out/'controller';t=run(psargs(ps,work/'native/controller/Build-Controller.ps1','-DllPath',dll,'-OutputDirectory',built),out/'controller-build.log');require('VC127B4_CONTROLLER_BUILD=PASS' in t,'Controller build marker missing')
        require(digest.encode('utf-16le') in (built/'VirtualCar.exe').read_bytes(),'Controller binding missing')
        harness=out/'harness';harness.mkdir();(harness/'lab').mkdir()
        for src,n in [(built/'VirtualCar.bound.cpp','VirtualCar.bound.cpp'),(dll,'VirtualCarJ2534.dll'),(profile,'transport-replay.ini')]:shutil.copyfile(src,harness/n)
        (harness/'ControllerTest.cpp').write_bytes(HARNESS.encode());(harness/'Build-Test.ps1').write_bytes(HARNESS_BUILD.encode())
        t=run(psargs(ps,harness/'Build-Test.ps1','-Root',harness),out/'controller-test.log');require(re.findall(r'^VC127B5_TEST (\d+) PASS ',t,re.M)==[str(i) for i in range(1,11)] and 'VC127B5_CONTROLLER_FILES=PASS 10/10' in t,'Harness failed');report['controller_groups']=10
        require(sha(dll.read_bytes())==digest,'DLL changed');print('VC127C2_CONTROLLER=PASS 10/10',flush=True);report['status']='PASS';print('VC127C2_CI=PASS 35/35; synthetic transport and isolated files only; VIDA NOT_TESTED')
    finally:
        (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print('VC127C2_SUMMARY='+str(out/'summary.json'))
if __name__=='__main__':main()
