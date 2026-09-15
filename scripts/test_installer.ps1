$ErrorActionPreference = "Stop"

$installer = Get-ChildItem "$PSScriptRoot\..\dist\CDriveCleaner-Setup-*-unsigned.exe" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1
if (-not $installer) { throw "Installer was not found." }

$testRoot = Join-Path $env:RUNNER_TEMP "CDriveCleanerInstallTest"
if (Test-Path $testRoot) { Remove-Item -LiteralPath $testRoot -Recurse -Force }

$process = Start-Process $installer.FullName -ArgumentList @(
  "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=$testRoot"
) -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Silent install failed with exit code $($process.ExitCode)." }

$installedExe = Join-Path $testRoot "CDriveCleaner.exe"
$uninstaller = Join-Path $testRoot "unins000.exe"
if (-not (Test-Path $installedExe)) { throw "Installed executable is missing." }
if (-not (Test-Path $uninstaller)) { throw "Uninstaller is missing." }

$process = Start-Process $uninstaller -ArgumentList @(
  "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"
) -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Silent uninstall failed with exit code $($process.ExitCode)." }
if (Test-Path $installedExe) { throw "Installed executable remains after uninstall." }

Write-Host "Silent install and uninstall smoke test passed."
