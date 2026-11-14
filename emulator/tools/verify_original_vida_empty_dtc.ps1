#Requires -Version 5.1
<# Offline original ResponseHandler with a database interface that forbids
   all data access. DefinitionXml is a private, unchanged T111 AE/1B fragment.
   No adapter, SQL connection, real ECU or GUI is touched. #>
param(
    [Parameter(Mandatory=$true)][string]$VehicleServicesAssembly,
    [Parameter(Mandatory=$true)][string]$DefinitionXml
)
$ErrorActionPreference = 'Stop'
try {
    $text = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $DefinitionXml).Path)
    if ($text.Length -gt 65536) { throw 'Oversized definition' }
    $doc = New-Object Xml.XmlDocument
    $doc.XmlResolver = $null
    $doc.LoadXml('<service id="0">' + $text + '</service>')
    $mode = $doc.SelectSingleNode('/service/response/item')
    $list = $doc.SelectSingleNode('/service/response/fixedlist')
    if ($mode.name -cne 'Mode' -or $mode.length -ne '8' -or $list.name -cne 'DtcList') {
        throw 'Unexpected response structure'
    }
    $blocks = @($list.SelectNodes('block'))
    if ($blocks.Count -ne 7 -or (($blocks | ForEach-Object { $_.length }) -join ',') -cne '16,16,16,16,0,0,0') {
        throw 'Unexpected DTC record structure'
    }
    $assembly = [Reflection.Assembly]::LoadFrom((Resolve-Path -LiteralPath $VehicleServicesAssembly).Path)
    $prefix = 'Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.'
    $interface = $assembly.GetType($prefix + 'Data.IVehicleServiceDatabase', $true)
    $rawType = $assembly.GetType($prefix + 'RawResponse', $true)
    $handlerType = $assembly.GetType($prefix + 'ResponseHandler', $true)
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.Remoting.Proxies;
using System.Runtime.Remoting.Messaging;
public sealed class VidaNoDatabase : RealProxy {
    public int Denied;
    private Type requested;
    public VidaNoDatabase(Type t) : base(t) { requested=t; }
    public override IMessage Invoke(IMessage message) {
        var call = (IMethodCallMessage)message;
        if (call.MethodName == "GetType")
            return new ReturnMessage(requested, null, 0, call.LogicalCallContext, call);
        if (call.MethodName == "get_EnableResponseHandler")
            return new ReturnMessage(true, null, 0, call.LogicalCallContext, call);
        Denied++;
        return new ReturnMessage(new InvalidOperationException("Offline database access forbidden"), call);
    }
}
'@
    $proxy = New-Object VidaNoDatabase($interface)
    $database = $proxy.GetTransparentProxy()
    function Parse-Bytes([byte[]]$Bytes) {
        $raw = [Activator]::CreateInstance($rawType)
        $arg = New-Object object[] 1
        $arg[0] = $Bytes
        [void]$rawType.GetMethod('AddResponse').Invoke($raw, $arg)
        $arguments = New-Object object[] 5
        $arguments[0]=$database; $arguments[1]=[int]0; $arguments[2]=$doc.OuterXml
        $arguments[3]=$raw; $arguments[4]=$null
        $handler = $handlerType.GetConstructors()[0].Invoke($arguments)
        return ,$handler.GetResponse()
    }
    # 1/2: real constructor and unchanged original AE1B response definition.
    $result = Parse-Bytes ([byte[]]@(0x1B))
    if ($result.GetChildByName('Mode').GetValue().ToString() -ine '1B') { throw 'Mode mismatch' }
    if ($result.GetChildByName('DtcList').GetChildCount() -ne 0) { throw 'List not empty' }
    # 3: no block lookup/SQL access was needed to parse the empty list.
    if ($proxy.Denied -ne 0) { throw 'Unexpected database access' }
    # 4: the response grammar does not itself enforce requested mode.
    $other = Parse-Bytes ([byte[]]@(0))
    if ($other.GetChildByName('DtcList').GetChildCount() -ne 0) { throw 'Mode control failed' }
    # 5: original parser tolerates an absent mode. This is why the
    # emulator's own significant-length preflight remains necessary.
    $missing = Parse-Bytes ([byte[]]@())
    if ($missing.GetChildByName('DtcList').GetChildCount() -ne 0) { throw 'Empty-buffer control failed' }
    # 6: a nonempty record must leave the empty-list path. Our database guard
    # deliberately blocks its lookup; this is NOT a malformed-DTC verdict.
    try { [void](Parse-Bytes ([byte[]]@(0x1B,0,0,0,0,0,0,0,0))) } catch {}
    if ($proxy.Denied -eq 0) { throw 'Nonempty control did not access block metadata' }
    Write-Output 'PASS: 6 original VIDA empty-DTC parser gates; synthetic payload 1B only.'
    Write-Output 'CEM presence, T111 invocation, ReadVin and GUI acceptance: NOT_VERIFIED.'
} catch {
    Write-Output 'FAIL: original empty-DTC parser check; private details withheld.'
    exit 1
}
