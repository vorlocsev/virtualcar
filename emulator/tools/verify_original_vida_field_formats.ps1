#Requires -Version 5.1
# Original field formatter only, NOT full B9 response/catalog/ReadVin acceptance.
param([Parameter(Mandatory=$true)][string]$VehicleServicesAssembly)
$ErrorActionPreference='Stop'
try {
    $assembly=[Reflection.Assembly]::LoadFrom((Resolve-Path -LiteralPath $VehicleServicesAssembly).Path)
    $prefix='Vcc.Vida.DiagSwdl.BizServices.CarCom.VehicleServices.'
    $formatter=$assembly.GetType($prefix+'Formatter',$true)
    $enum=$assembly.GetType($prefix+'Data.BlockDataType',$true)
    $method=$formatter.GetMethod('Format',[Reflection.BindingFlags]'Static,Public,NonPublic')
    $cases=@(
        @{Bytes=[byte[]]@(0,0,0,0,0);Type=52;Expected='0000000000'},
        @{Bytes=[Text.Encoding]::ASCII.GetBytes('YV1CZ000290000001');Type=51;Expected='YV1CZ000290000001'},
        @{Bytes=[Text.Encoding]::ASCII.GetBytes('LAB');Type=51;Expected='LAB'},
        @{Bytes=[Text.Encoding]::ASCII.GetBytes('000000000');Type=51;Expected='000000000'},
        @{Bytes=[Text.Encoding]::ASCII.GetBytes('000');Type=51;Expected='000'},
        @{Bytes=[Text.Encoding]::ASCII.GetBytes('000000');Type=51;Expected='000000'}
    )
    foreach($case in $cases) {
        $hex='0x'+([BitConverter]::ToString($case.Bytes).Replace('-',''))
        $arguments=New-Object object[] 2
        $arguments[0]=$hex; $arguments[1]=[Enum]::ToObject($enum,$case.Type)
        if($method.Invoke($null,$arguments) -cne $case.Expected) { throw 'Field format mismatch' }
    }
    Write-Output 'PASS: 6 original VIDA field-format cases using public synthetic bytes.'
    Write-Output 'Selected ECU catalog, full B9 parser and ReadVin acceptance: NOT_VERIFIED.'
} catch {
    Write-Output 'FAIL: original field-format check; private details withheld.'
    exit 1
}
