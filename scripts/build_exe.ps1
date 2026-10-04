$ErrorActionPreference = "Stop"

$python = (Get-Command python -ErrorAction Stop).Source
$originalPath = $env:PATH
$originalBuildCache = $env:PYINSTALLER_CONFIG_DIR
try {
  # Foreign PATH entries (for example Poppler/Conda ICU DLLs) can silently poison
  # dependency collection. Qt must use the Windows ICU implementation.
  $env:PATH = @(
    (Split-Path -Parent $python),
    [Environment]::GetFolderPath('System'),
    [Environment]::GetFolderPath('Windows')
  ) -join [IO.Path]::PathSeparator
  $env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot '..\build\pyinstaller-cache'
  & $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name CDriveCleaner `
    --hidden-import PySide6.support.deprecated `
    --version-file packaging/windows/version_info.txt `
    --paths src `
    src/cdrive_cleaner/gui_main.py
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
} finally {
  $env:PATH = $originalPath
  $env:PYINSTALLER_CONFIG_DIR = $originalBuildCache
}

$smoke = Start-Process -FilePath .\dist\CDriveCleaner.exe -ArgumentList '--smoke-test' -WindowStyle Hidden -PassThru
if (-not $smoke.WaitForExit(60000)) {
  $smoke.Kill($true)
  throw 'Frozen GUI smoke timed out; no verified package was produced'
}
if ($smoke.ExitCode -ne 0) { throw "Frozen GUI failed: $($smoke.ExitCode)" }

$hash = (Get-FileHash -Algorithm SHA256 dist/CDriveCleaner.exe).Hash.ToLowerInvariant()
"$hash  CDriveCleaner.exe" | Set-Content -Encoding ascii dist/CDriveCleaner.exe.sha256
Write-Host "Built dist/CDriveCleaner.exe and SHA-256 checksum."
