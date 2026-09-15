$ErrorActionPreference = "Stop"

& "$PSScriptRoot\build_exe.ps1"

$isccCandidates = @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
  throw "Inno Setup 6 was not found. Install it before building the installer."
}

& $iscc "$PSScriptRoot\..\packaging\windows\CDriveCleaner.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }

$installer = Get-ChildItem "$PSScriptRoot\..\dist\CDriveCleaner-Setup-*-unsigned.exe" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1
$hash = (Get-FileHash -Algorithm SHA256 $installer.FullName).Hash.ToLowerInvariant()
"$hash  $($installer.Name)" | Set-Content -Encoding ascii "$($installer.FullName).sha256"
Write-Host "Built $($installer.Name) and SHA-256 checksum."
