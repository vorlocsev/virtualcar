# Windows PowerShell 5.1 compatible native process logging.
# Separate stderr from stdout; only the actual process exit code decides success.
function Invoke-VCNativeLogged {
    param(
        [Parameter(Mandatory=$true)][string]$Executable,
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [Parameter(Mandatory=$true)][string]$WorkingDirectory,
        [Parameter(Mandatory=$true)][string]$Log
    )
    $quoted = @(
        foreach ($argument in $Arguments) {
            if ($argument.Contains('"')) { throw 'Unexpected quote in native argument.' }
            # Windows argv: double trailing backslashes before the closing quote.
            '"' + ($argument -replace '(\\+)$','$1$1') + '"'
        }
    )
    $stderr = $Log + '.stderr'
    $process = Start-Process -FilePath $Executable -ArgumentList ($quoted -join ' ') `
        -WorkingDirectory $WorkingDirectory -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $Log -RedirectStandardError $stderr
    try {
        $exitCode = $process.ExitCode
        if ($null -eq $exitCode) { throw 'Native exit code unavailable.' }
        return [int]$exitCode
    }
    finally { $process.Dispose() }
}
