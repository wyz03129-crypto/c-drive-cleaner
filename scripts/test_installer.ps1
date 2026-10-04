$ErrorActionPreference = "Stop"

$installer = Get-ChildItem "$PSScriptRoot\..\dist\CDriveCleaner-Setup-*-unsigned.exe" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1
if (-not $installer) { throw "Installer was not found." }

if (-not $env:RUNNER_TEMP) { throw 'Installer smoke requires an isolated CI runner temp directory.' }
$runnerRoot = (Resolve-Path -LiteralPath $env:RUNNER_TEMP).Path
$testRoot = [IO.Path]::GetFullPath((Join-Path $runnerRoot ("CDriveCleanerInstallTest-" + [guid]::NewGuid().ToString('N'))))
if (-not $testRoot.StartsWith($runnerRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
  throw 'Installer smoke target escaped the runner temp directory.'
}
if (Test-Path -LiteralPath $testRoot) { throw 'Installer smoke target must not already exist.' }

$process = Start-Process $installer.FullName -ArgumentList @(
  "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=$testRoot"
) -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Silent install failed with exit code $($process.ExitCode)." }

$installedExe = Join-Path $testRoot "CDriveCleaner.exe"
$uninstaller = Join-Path $testRoot "unins000.exe"
if (-not (Test-Path $installedExe)) { throw "Installed executable is missing." }
if (-not (Test-Path $uninstaller)) { throw "Uninstaller is missing." }

$process = Start-Process $uninstaller -ArgumentList @(
  "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"
) -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Silent uninstall failed with exit code $($process.ExitCode)." }
if (Test-Path $installedExe) { throw "Installed executable remains after uninstall." }

Write-Host "Silent install and uninstall smoke test passed."
