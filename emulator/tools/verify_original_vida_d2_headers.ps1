#Requires -Version 5.1
# Offline original interpreter only. No channel, adapter, SQL or GUI calls.
param([Parameter(Mandatory=$true)][string]$VehComAssembly)
$ErrorActionPreference = 'Stop'
try {
    $assembly = [Reflection.Assembly]::LoadFrom((Resolve-Path -LiteralPath $VehComAssembly).Path)
    $type = $assembly.GetType('Vcc.Vida.DiagSwdl.VehCom2.J2534.Diagnostics.D2ResponseInterpreter', $true)
    $ctor = $type.GetConstructor([type[]]@([byte[]]))
    function Check-Header($Request, $Frame, $Method, $Expected) {
        $args1 = New-Object object[] 1
        $args1[0] = [byte[]]$Request
        $instance = $ctor.Invoke($args1)
        $args1[0] = [byte[]]$Frame
        if ($type.GetMethod($Method).Invoke($instance, $args1) -ne $Expected) {
            throw 'Original interpreter header mismatch'
        }
    }
    $f0 = [byte[]](0,128,0,3,143,64,249,240,0,0,0,0)
    $fb = [byte[]](0,128,0,3,143,64,249,251,0,0,0,0)
    $ae = [byte[]](0,128,0,3,203,64,238,27,0,0,0,0)
    Check-Header @(64,185,240) $f0 IsPositiveResponse $true
    Check-Header @(64,185,240) $fb IsPositiveResponse $false
    Check-Header @(64,185,251) $fb IsPositiveResponse $true
    Check-Header @(64,174,27) $ae IsPositiveResponse $true
    Check-Header @(64,174,27) $ae IsSingleFrame $true
    Check-Header @(64,185,240) $f0 IsFirstFrame $true
    $last = [byte[]](0,128,0,3,79,0,0,0,0,0,0,0)
    Check-Header @(64,185,251) $last IsLastFrame $true
    $hsF0 = [byte[]](1,0,0,3,143,80,249,240,0,0,0,0)
    Check-Header @(80,185,240) $hsF0 IsPositiveResponse $true
    Check-Header @(80,185,251) $hsF0 IsPositiveResponse $false
    Check-Header @(80,185,240) $hsF0 IsFirstFrame $true
    Write-Output 'PASS: 10 original VIDA D2 interpreter header checks; synthetic inputs only.'
    Write-Output 'Payload semantics, empty DTC list, ReadVin, T111/T122 and GUI acceptance: NOT_VERIFIED.'
} catch {
    Write-Output 'FAIL: original interpreter unavailable or header check failed; private details withheld.'
    exit 1
}
