$ErrorActionPreference = "Stop"

& "$PSScriptRoot\check.ps1"
python -m build

Write-Host "Build artifacts are in dist/. M0 builds Python packages, not a Windows EXE."

