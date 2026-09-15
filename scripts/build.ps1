$ErrorActionPreference = "Stop"

& "$PSScriptRoot\check.ps1"
python -m build

Write-Host "Python package artifacts are in dist/. Use build_exe.ps1 for the Windows GUI executable."
