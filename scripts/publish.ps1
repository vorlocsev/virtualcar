# Invoke after manually creating a PRIVATE and EMPTY GitHub repository named vorlocsev/virtualcar.
# Requires Git for Windows authenticated to GitHub. This script never creates the remote repository.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path .git)) {
    git init -b main
    if ($LASTEXITCODE -ne 0) { throw "git init failed" }
    git add .
    git commit -m "Bootstrap Virtual Car dev26 sources"
    if ($LASTEXITCODE -ne 0) { throw "git commit failed. Configure git user.name and user.email." }
}
if (-not (git remote)) { git remote add origin https://github.com/vorlocsev/virtualcar.git }
git push -u origin main
if ($LASTEXITCODE -ne 0) { throw "git push main failed" }
git switch development 2>$null
if ($LASTEXITCODE -ne 0) { git switch -c development }
git push -u origin development
if ($LASTEXITCODE -ne 0) { throw "git push development failed" }
Write-Host "VirtualCar source pushed to main and development. Check GitHub before publishing releases."
