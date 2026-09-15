$ErrorActionPreference = "Stop"

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name CDriveCleaner `
  --version-file packaging/windows/version_info.txt `
  --paths src `
  src/cdrive_cleaner/gui_main.py

$hash = (Get-FileHash -Algorithm SHA256 dist/CDriveCleaner.exe).Hash.ToLowerInvariant()
"$hash  CDriveCleaner.exe" | Set-Content -Encoding ascii dist/CDriveCleaner.exe.sha256
Write-Host "Built dist/CDriveCleaner.exe and SHA-256 checksum."
