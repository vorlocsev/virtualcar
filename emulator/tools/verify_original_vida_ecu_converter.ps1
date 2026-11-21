#Requires -Version 5.1
<# Runs original ScriptOutputConverter.GetAliveEcus with synthetic repository
   answers only. No SQL, original script execution, adapter, GUI or OEM identity.
   The converter constructor is bypassed to prevent application logger setup. #>
param([Parameter(Mandatory=$true)][string]$DiagnosticsDirectory)
$ErrorActionPreference='Stop'
try {
    if([IntPtr]::Size -ne 4) { throw 'x86 PowerShell required' }
    $root=(Resolve-Path -LiteralPath $DiagnosticsDirectory).Path
    $assemblies=@{}
    foreach($name in @('Core','BizServices.CarCom.DB','BizServices.CarCom.VehicleServices','BizServices.Scripting','AppServices.VehicleAccess')) {
        $assemblies[$name]=[Reflection.Assembly]::LoadFrom((Join-Path $root ($name+'.dll')))
    }
    Add-Type -TypeDefinition @'
using System;
using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.Serialization;
using System.Runtime.Remoting.Proxies;
using System.Runtime.Remoting.Messaging;

public sealed class VidaSyntheticCatalog : RealProxy {
    public readonly List<string> Calls = new List<string>();
    public int Match, Default, Denied;
    public object Variant;
    public bool FailLookup;
    public string ExpectedDiagnostic;
    private readonly Type target;
    private readonly bool logger;
    public VidaSyntheticCatalog(Type type, bool log) : base(type) { target=type; logger=log; }
    public override IMessage Invoke(IMessage message) {
        var call=(IMethodCallMessage)message;
        if(call.MethodName=="GetType") return new ReturnMessage(target,null,0,call.LogicalCallContext,call);
        Calls.Add(call.MethodName);
        object result=null;
        bool allowed=false;
        if(logger) allowed=call.MethodName=="Warning";
        else if(call.MethodName=="GetEcuId" && call.ArgCount==1 &&
                String.Equals(call.Args[0] as string,ExpectedDiagnostic,StringComparison.Ordinal)) {
            if(FailLookup) return new ReturnMessage(new InvalidOperationException("Synthetic lookup failure"),call);
            result=Match; allowed=true;
        } else if(call.MethodName=="GetDefaultEcuId" && call.ArgCount==2 &&
                  (int)call.Args[0]==0 && call.Args[1]==null) {
            result=Default; allowed=true;
        } else if(call.MethodName=="GetEcuVariantData" && call.ArgCount==1 &&
                  (int)call.Args[0]==(Match==0 ? Default : Match)) {
            result=Variant; allowed=true;
        }
        if(!allowed) { Denied++; return new ReturnMessage(new InvalidOperationException("Unexpected offline interface operation"),call); }
        return new ReturnMessage(result,null,0,call.LogicalCallContext,call);
    }
}

public static class VidaConverterProbe {
    private const BindingFlags Fields=BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic;
    private static void Require(bool value) { if(!value) throw new InvalidOperationException("Synthetic contract mismatch"); }
    public static void CheckDefaultCache(Assembly db) {
        Type type=db.GetType("Vcc.Vida.DiagSwdl.BizServices.CarCom.DB.DefaultEcuVariantCache",true);
        object cache=Activator.CreateInstance(type,true);
        MethodInfo add=type.GetMethod("AddMapping"), get=type.GetMethod("GetDefaultEcuVariant"),
            diag=type.GetMethod("GetDefaultDiagNumber"), initialized=type.GetMethod("IsInitializedForProfile");
        Require((int)get.Invoke(cache,new object[]{0,"SYNTHETIC-A"})==0 &&
            !(bool)initialized.Invoke(cache,new object[]{"SYNTHETIC-A"}));
        add.Invoke(cache,new object[]{"SYNTHETIC-A",0,101,"SYNTHETIC-FIRST"});
        Require((int)get.Invoke(cache,new object[]{0,"SYNTHETIC-A"})==101 &&
            (bool)initialized.Invoke(cache,new object[]{"SYNTHETIC-A"}));
        add.Invoke(cache,new object[]{"SYNTHETIC-A",0,202,"SYNTHETIC-SECOND"});
        Require((int)get.Invoke(cache,new object[]{0,"SYNTHETIC-A"})==101 &&
            (string)diag.Invoke(cache,new object[]{0,"SYNTHETIC-A"})=="SYNTHETIC-FIRST");
        add.Invoke(cache,new object[]{"SYNTHETIC-B",0,202,"SYNTHETIC-SECOND"});
        add.Invoke(cache,new object[]{"SYNTHETIC-B",0,101,"SYNTHETIC-FIRST"});
        Require((int)get.Invoke(cache,new object[]{0,"SYNTHETIC-B"})==202);
        add.Invoke(cache,new object[]{"SYNTHETIC-A",1,303,"SYNTHETIC-OTHER-GROUP"});
        Require((int)get.Invoke(cache,new object[]{0,"SYNTHETIC-A"})==101 &&
            (int)get.Invoke(cache,new object[]{1,"SYNTHETIC-A"})==303 &&
            (int)get.Invoke(cache,new object[]{1,"SYNTHETIC-B"})==0);
        add.Invoke(cache,new object[]{"SYNTHETIC-A",0,101,"SYNTHETIC-FIRST"});
        Require((int)get.Invoke(cache,new object[]{0,"SYNTHETIC-A"})==101 &&
            (int)get.Invoke(cache,new object[]{0,"SYNTHETIC-MISSING"})==0);
        Console.WriteLine("PASS: 6 original default-cache gates; first mapping wins, profiles and function groups are isolated.");
    }
    private static object Output(Type output, Type response, Type leaf, bool missing, bool fresh) {
        object obj=Activator.CreateInstance(output);
        output.GetProperty("EcuType").SetValue(obj,0,null);
        if(missing) output.GetMethod("SetEcuNotAlive").Invoke(obj,null);
        else if(!fresh) {
            object raw=Activator.CreateInstance(response,new object[]{0});
            object value=Activator.CreateInstance(leaf,new object[]{"F0"+new string('0',30),0});
            response.GetMethod("AddChildByName").Invoke(raw,new object[]{"raw",value});
            output.GetMethod("AddIdentificationD2").Invoke(obj,new object[]{raw});
        }
        return obj;
    }
    public static void Run(Assembly app, Assembly db, Assembly scripts, Assembly services) {
        Type converter=app.GetType("Vcc.Vida.DiagSwdl.AppServices.VehicleAccess.ScriptOutputConverter",true);
        Type variantType=db.GetType("Vcc.Vida.DiagSwdl.BizServices.CarCom.DB.EcuData.EcuVariant",true);
        Type output=scripts.GetType("Vcc.Vida.DiagSwdl.BizServices.Scripting.Components.EcuIdentificationOutput",true);
        string prefix="Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.Responses.";
        Type response=services.GetType(prefix+"ResponseComposite",true), leaf=services.GetType(prefix+"ResponseStringLeaf",true);
        FieldInfo repoField=converter.GetField("_carcomRepository",Fields), logField=converter.GetField("Log",Fields);
        MethodInfo getAlive=converter.GetMethod("GetAliveEcus",Fields);
        string diagnostic="00000000"+new string('\0',3);
        string[] labels={"fresh output","direct catalog match","default variant fallback",
            "missing default variant","empty variant addresses","repository failure","no-response output"};
        // Each scenario starts with a new original output and isolated in-memory repository.
        for(int scenario=0;scenario<7;scenario++) {
            object obj=Output(output,response,leaf,scenario==6,scenario==0);
            object variant=FormatterServices.GetUninitializedObject(variantType);
            variantType.GetField("DiagnosticNumber").SetValue(variant,"SYNTHETIC-CATALOG-ONLY");
            variantType.GetField("EcuName").SetValue(variant,"SYNTHETIC");
            var addresses=new ArrayList();
            if(scenario!=4) addresses.Add(Activator.CreateInstance(
                variantType.GetNestedType("EcuAddressConfigMap",BindingFlags.Public|BindingFlags.NonPublic),
                new object[]{(byte)0x40,0}));
            variantType.GetField("_ecuAddressList",Fields).SetValue(variant,addresses);
            var repo=new VidaSyntheticCatalog(repoField.FieldType,false) {
                Match=scenario==1 ? 101 : 0, Default=scenario==3 ? 0 : 202,
                Variant=scenario==3 ? null : variant, FailLookup=scenario==5,
                ExpectedDiagnostic=diagnostic
            };
            var log=new VidaSyntheticCatalog(logField.FieldType,true);
            object conv=FormatterServices.GetUninitializedObject(converter);
            repoField.SetValue(conv,repo.GetTransparentProxy()); logField.SetValue(conv,log.GetTransparentProxy());
            object result=null; Exception failure=null;
            try { result=getAlive.Invoke(conv,new object[]{obj,null}); }
            catch(TargetInvocationException ex) { failure=ex.InnerException; }
            Require(repo.Denied==0 && log.Denied==0);
            if(scenario==0 || scenario==6) {
                Require(failure==null && ((ICollection)result).Count==0 && repo.Calls.Count==0 && log.Calls.Count==0);
            } else {
                string expected=scenario==1 ? "GetEcuId,GetEcuVariantData" :
                    scenario==5 ? "GetEcuId" : "GetEcuId,GetDefaultEcuId,GetEcuVariantData";
                Require(String.Join(",",repo.Calls.ToArray())==expected);
                Require(log.Calls.Count==((scenario==1 || scenario==5) ? 0 : 1));
                if(scenario==3) Require(failure is NullReferenceException);
                else if(scenario==4) Require(failure is IndexOutOfRangeException);
                else if(scenario==5) Require(failure is InvalidOperationException);
                else {
                    Require(failure==null && ((ICollection)result).Count==1);
                    IEnumerator it=((IEnumerable)result).GetEnumerator(); Require(it.MoveNext());
                    object info=it.Current; Type t=info.GetType();
                    Require((byte)t.GetProperty("EcuAddress").GetValue(info,null)==0x40);
                    Require((string)t.GetProperty("DiagNumber").GetValue(info,null)==diagnostic);
                    Require((string)t.GetProperty("EcuVariantIdentifier").GetValue(info,null)=="SYNTHETIC-CATALOG-ONLY");
                }
            }
            Console.WriteLine("PASS: original converter "+labels[scenario]);
        }
    }
}
'@
    [VidaConverterProbe]::Run($assemblies['AppServices.VehicleAccess'],$assemblies['BizServices.CarCom.DB'],
        $assemblies['BizServices.Scripting'],$assemblies['BizServices.CarCom.VehicleServices'])
    [VidaConverterProbe]::CheckDefaultCache($assemblies['BizServices.CarCom.DB'])
    foreach($name in ($assemblies.Keys | Sort-Object)) {
        Write-Output ($name+' SHA256='+(Get-FileHash -LiteralPath $assemblies[$name].Location -Algorithm SHA256).Hash)
    }
    Write-Output 'PASS: 7 original ECU converter gates; catalog and profile are synthetic stubs.'
    Write-Output 'Unknown diagnostic number uses a default variant; this does NOT verify the real profile, catalog match or GUI.'
} catch {
    Write-Output ('FAIL: original ECU converter line='+$_.InvocationInfo.ScriptLineNumber+'; details withheld.')
    exit 1
}
