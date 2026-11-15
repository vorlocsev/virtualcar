#Requires -Version 5.1
<# Offline EcuIdentificationOutput state transitions using synthetic function
   group 0 and public raw responses. No DB, script execution, adapter or GUI.
   Collection membership is NOT original VIDA NETWORK acceptance. #>
param(
    [Parameter(Mandatory=$true)][string]$ScriptingAssembly,
    [Parameter(Mandatory=$true)][string]$VehicleServicesAssembly
)
$ErrorActionPreference='Stop'
$stage='load'
try {
    if([IntPtr]::Size -ne 4) { throw 'x86 PowerShell required' }
    $scripts=[Reflection.Assembly]::LoadFrom((Resolve-Path -LiteralPath $ScriptingAssembly).Path)
    $services=[Reflection.Assembly]::LoadFrom((Resolve-Path -LiteralPath $VehicleServicesAssembly).Path)
    $outputType=$scripts.GetType('Vcc.Vida.DiagSwdl.BizServices.Scripting.Components.EcuIdentificationOutput',$true)
    $prefix='Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.Responses.'
    $responseType=$services.GetType($prefix+'ResponseComposite',$true)
    $leafType=$services.GetType($prefix+'ResponseStringLeaf',$true)
    function New-Output {
        $obj=[Activator]::CreateInstance($outputType)
        $obj.EcuType=0
        return ,$obj
    }
    function Add-Raw($Output,[string]$Hex) {
        $response=$responseType.GetConstructors()[0].Invoke([object[]]@([int]0))
        $leaf=$leafType.GetConstructor([type[]]@([string],[int])).Invoke([object[]]@($Hex,[int]0))
        $response.AddChildByName('raw',$leaf)
        $Output.AddIdentificationD2($response)
    }
    function Check-Counts($Output,[int]$Alive,[int]$NotAlive) {
        if($Output.GetAliveEcus().Count -ne $Alive -or $Output.GetNotAliveEcus().Count -ne $NotAlive) {
            throw 'Original collection mismatch'
        }
    }
    $stage='initial'
    $fresh=New-Output; Check-Counts $fresh 0 0
    $stage='missing_reply'
    $missing=New-Output; $missing.SetEcuNotAlive(); Check-Counts $missing 0 1
    $stage='synthetic_f0'
    $positive=New-Output; Add-Raw $positive ('F0'+('00'*15))
    $stage='synthetic_f0_counts'; Check-Counts $positive 1 0
    $stage='synthetic_f0_fields'
    $data=$positive.GetEcudataForEcu(0)
    if($data.DiagPartNumber.Length -ne 11 -or $data.HwPartNumber.Length -ne 13 -or
       !$data.DiagPartNumber.Contains([string][char]0)) { throw 'Unexpected zero-placeholder interpretation' }
    $stage='empty_followups'
    Add-Raw $positive 'F5'; Add-Raw $positive 'F8'; Check-Counts $positive 1 0
    if($data.SwSerialNumbers.Count -ne 0 -or $data.HwSerialNumbers.Count -ne 0) { throw 'Empty list changed identifiers' }
    $stage='truncated_f0'
    $truncated=New-Output; Add-Raw $truncated 'F0'; Check-Counts $truncated 1 0
    if($truncated.GetEcudataForEcu(0).DiagPartNumber -ne '') { throw 'Truncation control changed' }
    $stage='conflicting_calls'
    $conflict=New-Output; $conflict.SetEcuNotAlive(); Add-Raw $conflict ('F0'+('00'*15))
    Check-Counts $conflict 1 1
    Write-Output 'PASS: 6 original EcuIdentificationOutput state gates using synthetic group 0.'
    Write-Output 'F0 creates alive membership even when truncated; missing-reply calls populate a separate not-alive list.'
    Write-Output 'Collection membership, zero placeholders and empty F5/F8 do NOT prove OEM identity or NETWORK acceptance.'
} catch {
    Write-Output ('FAIL: original ECU state stage='+$stage+' line='+$_.InvocationInfo.ScriptLineNumber+'; details withheld.')
    exit 1
}
