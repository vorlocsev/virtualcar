#Requires -Version 5.1
<# Offline original B9 ResponseHandler against an explicit private catalog slice.
   No original database constructor, SQL connection, adapter or GUI is invoked.
   This proves neither selection of this catalog variant nor OEM field validity. #>
param(
    [Parameter(Mandatory=$true)][string]$VehicleServicesAssembly,
    [Parameter(Mandatory=$true)][string]$PrivateInput,
    [string]$ScriptingAssembly
)
$ErrorActionPreference='Stop'
$stage='input'
try {
    if ([IntPtr]::Size -ne 4) { throw 'Use original x86 Windows PowerShell' }
    $inputPath=(Resolve-Path -LiteralPath $PrivateInput).Path
    if ((Get-Item -LiteralPath $inputPath).Length -gt 1048576) { throw 'Oversized input' }
    $s=[IO.File]::ReadAllText($inputPath) | ConvertFrom-Json
    if ($s.contract -cne 'private-original-b9fb-parser-v1') { throw 'Unknown contract' }
    $a=[Reflection.Assembly]::LoadFrom((Resolve-Path -LiteralPath $VehicleServicesAssembly).Path)
    $prefix='Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.'
    function Get-VidaType([string]$Name) { return $a.GetType($prefix+$Name,$true) }
    function Set-Field($Object,[string]$Name,$Value) {
        $Object.GetType().GetField($Name,[Reflection.BindingFlags]'Instance,Public,NonPublic').SetValue($Object,$Value)
    }
    # Initialize only the in-memory type maps. The original constructor would
    # initialize application services; it is deliberately not invoked here.
    $stage='catalog'
    $db=[Runtime.Serialization.FormatterServices]::GetUninitializedObject((Get-VidaType 'Data.VehicleServiceDatabase'))
    $byId=@{}; $byName=@{}
    foreach($t in $s.types) { $byId[[int]$t.id]=[string]$t.identifier; $byName[[string]$t.identifier]=[int]$t.id }
    Set-Field $db '_blockTypesId' $byId
    Set-Field $db '_blockTypesName' $byName
    Set-Field $db '_isInitialized' $true
    $bhType=Get-VidaType 'Blocks.BlockHandler'
    $bh=$bhType.GetConstructors()[0].Invoke([object[]]@($db))
    Set-Field $bh '_useFallback' $false
    $flags=[Reflection.BindingFlags]'Instance,NonPublic'
    $blocks=$bhType.GetField('_blocks',$flags).GetValue($bh)
    # Localized display labels are irrelevant to value parsing. Cache empty
    # labels explicitly so original GetText cannot initiate a database lookup.
    $texts=$bhType.GetField('_texts',$flags).GetValue($bh); $texts[[int]0]=''
    foreach($b in $s.blocks) {
        $texts[[int]$b.fkT190_Text]=''
        $ctorArgs=[object[]]@($bh,[int]$b.id,[string]$b.name,[int]$b.fkT190_Text,
            [int]$b.fkT143_BlockDataType,[int]$b.fkT142_BlockType,[int]$b.offset,[int]$b.length,
            [bool]$b.composite,[bool]$b.exclude)
        $block=(Get-VidaType 'Blocks.Block').GetConstructors()[0].Invoke($ctorArgs)
        foreach($v in $b.values) {
            $texts[[int]$v.fkT190_Text_Value]=''; $texts[[int]$v.fkT190_Text_Unit]=''
            $scaling=[string]$v.scaling; $valueText=[int]$v.fkT190_Text_Value; $unitText=[int]$v.fkT190_Text_Unit
            $alt=[string]$v.altDisplayValue
            # Same loading rule as original BlockHandler.addBlocks for PARAM
            # string/BCD fields; numeric fields retain original comparisons.
            if ($b.fkT142_BlockType -eq $byName['PARAM'] -and $b.fkT143_BlockDataType -ge 50) {
                $scaling='x'; $valueText=0; $unitText=0; $alt=''
            }
            $ctorArgs=[object[]]@($bh,[int]$v.Id,[string]$v.CompareValue,[int]$v.Operator,$valueText,$unitText,$scaling,$alt)
            $value=(Get-VidaType 'Blocks.BlockValue').GetConstructors()[0].Invoke($ctorArgs)
            $block.BlockValues.Add($value)
        }
        $blocks[[int]$b.id]=$block.PSObject.BaseObject
    }
    $edges=New-Object Collections.ArrayList
    foreach($e in $s.edges) {
        $ctorArgs=[object[]]@([int]$e.fkT141_Block_Parent,[int]$e.fkT141_Block_Child,[int]$e.SortOrder,[int]$e.fkT100_EcuVariant)
        [void]$edges.Add((Get-VidaType 'Blocks.BlockChild').GetConstructors()[0].Invoke($ctorArgs))
    }
    $bhType.GetField('_ecuIds',$flags).GetValue($bh)[[int]$s.variant]=$true
    $bhType.GetField('_blockChildren',$flags).GetValue($bh)[[int]$s.variant]=$edges.PSObject.BaseObject
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.Remoting.Proxies;
using System.Runtime.Remoting.Messaging;
using System.Collections;
public sealed class VidaCatalogOnly : RealProxy {
    public int Denied;
    private Type requested;
    private object handler;
    private Hashtable types;
    public VidaCatalogOnly(Type t,object h,Hashtable names) : base(t) { requested=t;handler=h;types=names; }
    public override IMessage Invoke(IMessage message) {
        var call=(IMethodCallMessage)message; object result=null;
        if(call.MethodName=="GetType") result=requested;
        else if(call.MethodName=="get_EnableResponseHandler") result=true;
        else if(call.MethodName=="get_BlockHandler") result=handler;
        else if(call.MethodName=="GetBlockType" && call.Args[0] is string && types.Contains(call.Args[0])) result=types[call.Args[0]];
        else { Denied++; return new ReturnMessage(new InvalidOperationException("Uncached operation forbidden"),call); }
        return new ReturnMessage(result,null,0,call.LogicalCallContext,call);
    }
    public static string FindVin(object response,int blockId) {
        var t=response.GetType();
        if(!(bool)t.GetMethod("ContainsChildByName").Invoke(response,new object[]{"Parameters"})) return null;
        var parameters=t.GetMethod("GetChildByName").Invoke(response,new object[]{"Parameters"});
        var iterator=(IEnumerator)parameters.GetType().GetMethod("GetEnumerator").Invoke(parameters,null);
        while(iterator.MoveNext()) {
            var child=iterator.Current; var ct=child.GetType();
            if((int)ct.GetProperty("BlockId").GetValue(child,null)!=blockId) continue;
            var leaf=ct.GetMethod("GetChildByName").Invoke(child,new object[]{"value"});
            return (string)leaf.GetType().GetMethod("GetValue").Invoke(leaf,null);
        }
        return null;
    }
    public static int MatchedCount(object parameters) {
        int count=0;
        var iterator=(IEnumerator)parameters.GetType().GetMethod("GetEnumerator").Invoke(parameters,null);
        while(iterator.MoveNext()) {
            var child=iterator.Current;
            if((int)child.GetType().GetProperty("BlockId").GetValue(child,null)>0) count++;
        }
        return count;
    }
    public static string ScriptVin(object response,object selector,int textId) {
        var flags=System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic;
        var name=selector.GetType().GetMethod("getSelectionValueByName",flags);
        var id=selector.GetType().GetMethod("getSelectionValueById",flags);
        var parameters=name.Invoke(selector,new object[]{response,"Parameters"});
        if(parameters==null) return null;
        var parameter=id.Invoke(selector,new object[]{parameters,textId});
        if(parameter==null) return null;
        var value=name.Invoke(selector,new object[]{parameter,"value"});
        if(value==null) return null;
        // Missing keys yield an empty ResponseComposite, not a value leaf.
        var getter=value.GetType().GetMethod("GetValue");
        return getter==null ? null : (string)getter.Invoke(value,null);
    }
}
'@
    $guard=New-Object VidaCatalogOnly((Get-VidaType 'Data.IVehicleServiceDatabase'),$bh,$byName)
    $proxy=$guard.GetTransparentProxy()
    $doc=New-Object Xml.XmlDocument; $doc.XmlResolver=$null
    $doc.LoadXml('<service id="0">'+$s.definition+'</service>')
    if ($doc.SelectSingleNode('/service/response/dynamiclist').type -cne 'PARAM') { throw 'Unexpected T111 definition' }
    $scriptSelector=$null
    if($s.readvin_binding) {
        if(!$ScriptingAssembly) { throw 'Original scripting assembly required for script-derived input' }
        $scriptAssembly=[Reflection.Assembly]::LoadFrom((Resolve-Path -LiteralPath $ScriptingAssembly).Path)
        $scriptPrefix='Vcc.Vida.DiagSwdl.BizServices.Scripting.Components.'
        $scriptSelector=[Runtime.Serialization.FormatterServices]::GetUninitializedObject($scriptAssembly.GetType($scriptPrefix+'ResultGet',$true))
    }
    function Parse-Bytes([byte[]]$Bytes) {
        $raw=[Activator]::CreateInstance((Get-VidaType 'RawResponse'))
        $arg=New-Object object[] 1; $arg[0]=$Bytes
        [void](Get-VidaType 'RawResponse').GetMethod('AddResponse').Invoke($raw,$arg)
        $ctorArgs=[object[]]@($proxy,[int]$s.variant,$doc.OuterXml,$raw,$null)
        $handler=(Get-VidaType 'ResponseHandler').GetConstructors()[0].Invoke($ctorArgs)
        return ,$handler.GetResponse()
    }
    function Find-Vin($Response) {
        if($scriptSelector) {
            return [VidaCatalogOnly]::ScriptVin($Response.PSObject.BaseObject,$scriptSelector,[int]$s.readvin_binding.result_text_id)
        }
        return [VidaCatalogOnly]::FindVin($Response.PSObject.BaseObject,[int]$s.vin_block)
    }
    $stage='positive'
    $result=Parse-Bytes ([byte[]]$s.raw)
    if ((Find-Vin $result) -cne $s.expected_vin) { throw 'Original parser VIN mismatch' }
    $params=$result.GetChildByName('Parameters')
    $matched=[VidaCatalogOnly]::MatchedCount($params.PSObject.BaseObject)
    $stage='controls'
    $vinBlock=@($s.blocks | Where-Object { $_.id -eq $s.vin_block })[0]
    $changed=[byte[]]$s.raw.Clone(); $changed[1+[int]($vinBlock.offset/8)]=88
    if ((Find-Vin (Parse-Bytes $changed)) -ceq $s.expected_vin) { throw 'Mutation control failed' }
    $truncated=[byte[]]@($s.raw[0..([int]($vinBlock.offset/8))])
    if ((Find-Vin (Parse-Bytes $truncated)) -ceq $s.expected_vin) { throw 'Truncation control failed' }
    $wrong=[byte[]]$s.raw.Clone(); $wrong[0]=0xFA
    if ((Find-Vin (Parse-Bytes $wrong)) -ceq $s.expected_vin) { throw 'Selector control failed' }
    if ((Find-Vin (Parse-Bytes ([byte[]]@()))) -ceq $s.expected_vin) { throw 'Empty control failed' }
    if ($guard.Denied -ne 0) { throw 'Unexpected uncached operation' }
    if($scriptSelector) {
        $stage='script_output'
        # These methods only manipulate the output object. No script scheduler,
        # vehicle service or UI is started; AddVIN itself is not VIN validation.
        $outputType=$scriptAssembly.GetType($scriptPrefix+'VehicleIdentityOutput',$true)
        $identityOutput=[Runtime.Serialization.FormatterServices]::GetUninitializedObject($outputType)
        $outputType.GetMethod('AddVIN').Invoke($identityOutput,[object[]]@((Find-Vin $result)))
        if($identityOutput.GetIdentity() -cne $s.expected_vin -or $identityOutput.IsX40) { throw 'Original identity output mismatch' }
        Write-Output 'PASS: original ResultGet selectors and AddVIN/GetIdentity follow the private ReadVin XML binding.'
        Write-Output ('Original scripting assembly SHA256='+(Get-FileHash -LiteralPath $ScriptingAssembly -Algorithm SHA256).Hash)
    }
    Write-Output ('PASS: 6 original B9FB parser gates; VIN matched without printing identity; body_bytes='+$s.body_bytes+' section_bits='+$s.section_bits+' catalog_parameters='+($s.blocks.Count-1)+' parsed_parameters='+$params.GetChildCount()+' matched_blocks='+$matched)
    Write-Output ('Original assembly SHA256='+(Get-FileHash -LiteralPath $VehicleServicesAssembly -Algorithm SHA256).Hash)
    Write-Output 'Runtime script selection, target ECU identity, remaining field semantics and original VIDA GUI: NOT_VERIFIED.'
} catch {
    Write-Output ('FAIL: original B9FB parser stage='+$stage+' line='+$_.InvocationInfo.ScriptLineNumber+'; private details withheld.')
    exit 1
}
