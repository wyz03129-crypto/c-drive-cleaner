$ErrorActionPreference = "Stop"

& "$PSScriptRoot\check.ps1"
python -m build
if ($LASTEXITCODE -ne 0) { throw "Python package build failed" }

Write-Host "Python package artifacts are in dist/. Use build_exe.ps1 for the Windows GUI executable."
