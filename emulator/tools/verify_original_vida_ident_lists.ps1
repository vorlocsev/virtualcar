#Requires -Version 5.1
# Offline original D2Interpreter only. Public synthetic bytes; no ECU identities.
param([Parameter(Mandatory=$true)][string]$ScriptingAssembly)
$ErrorActionPreference='Stop'
try {
    if([IntPtr]::Size -ne 4) { throw 'x86 PowerShell required' }
    $assembly=[Reflection.Assembly]::LoadFrom((Resolve-Path -LiteralPath $ScriptingAssembly).Path)
    $type=$assembly.GetType('Vcc.Vida.DiagSwdl.BizServices.Scripting.Components.D2Interpreter',$true)
    function Interpret([string]$Hex,[string]$Method) {
        $obj=$type.GetConstructors()[0].Invoke([object[]]@($Hex))
        return ,$type.GetMethod($Method).Invoke($obj,$null)
    }
    if((Interpret 'F5' 'B9F5GetSwNumbers').Length -ne 0) { throw 'Empty software list failed' }
    if((Interpret 'F8' 'B9F8GetSerialNumbers').Length -ne 0) { throw 'Empty serial list failed' }
    $one=Interpret 'F8000000000000' 'B9F8GetSerialNumbers'
    if($one.Length -ne 1 -or $one[0] -cne '000000000000') { throw 'Synthetic serial control failed' }
    if((Interpret 'F80000000000' 'B9F8GetSerialNumbers').Length -ne 0) { throw 'Truncated serial control failed' }
    if((Interpret 'F50000000000' 'B9F5GetSwNumbers').Length -ne 0) { throw 'Truncated software control failed' }
    # The existing F0 lab placeholder is parseable but produces NUL suffixes.
    # This check does not turn zero bytes into valid diagnostic/part numbers.
    $hw=Interpret ('F0'+('00'*15)) 'B9F0GetHwPartNumber'
    $diag=Interpret ('F0'+('00'*15)) 'B9F0GetDiagnoseNumber'
    if($hw.Length -ne 13 -or $diag.Length -ne 11 -or !$diag.Contains([string][char]0)) { throw 'F0 placeholder control failed' }
    Write-Output 'PASS: 6 original D2 identification-list gates; F5/F8 empty lists accepted offline.'
    Write-Output 'Truncated lists also yield empty; zero F0 has NUL suffixes. OEM identity and ECU presence NOT_VERIFIED.'
} catch {
    Write-Output 'FAIL: original identification-list checks; details withheld.'
    exit 1
}
