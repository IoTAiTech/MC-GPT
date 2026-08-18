# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-18
[CmdletBinding()]
param(
  [switch]$Apply,
  [switch]$Uninstall,
  [switch]$Rollback,
  [switch]$DeepScan,
  [Alias("Home")]
  [string]$HomePath = $env:USERPROFILE,
  [string]$Hosts = "all",
  [string]$PackageStore = "",
  [string]$CurrentPackage = "",
  [string]$PackageArchive = ""
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DataRoot = Join-Path $env:LOCALAPPDATA "IoT-AI.Tech\IOT-AI-Suite\v1"
$SuiteBase = Join-Path $DataRoot "suite"
$RuntimeRoot = Join-Path $SuiteBase "6.8.0-beta.1"
$TxId = "powershell-install-{0}-{1}" -f ([DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")), $PID
$TxRoot = Join-Path $DataRoot "update-transactions\$TxId"
$LogRoot = Join-Path $DataRoot "logs"
$Venv = Join-Path $RuntimeRoot "venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$VenvCli = Join-Path $Venv "Scripts\iot-ai.exe"
$WheelRoot = Join-Path $Root "wheels"
if (-not (Test-Path $WheelRoot)) { $WheelRoot = Join-Path $Root "installers\wheels" }

$commands = @('claude','codex','gemini','grok','ollama')
$found = [ordered]@{}
foreach ($name in $commands) {
  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  $found[$name] = if ($cmd) { $cmd.Source } else { $null }
}
if ($DeepScan) {
  $roots = @($HomePath, $env:LOCALAPPDATA, $env:APPDATA, $env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique
  foreach ($scanRoot in $roots) {
    Get-ChildItem -Path $scanRoot -File -ErrorAction SilentlyContinue -Recurse -Depth 5 |
      Where-Object { $_.BaseName -in $commands -and $_.Extension -in @('.exe','.cmd','.bat','.ps1') } |
      ForEach-Object { if (-not $found[$_.BaseName]) { $found[$_.BaseName] = $_.FullName } }
  }
}

$result = [ordered]@{
  schema="iot-ai.windows-install-plan.v3"; version="6.8.0-beta.1"; home=$HomePath; runtime=$RuntimeRoot;
  apply=[bool]$Apply; uninstall=[bool]$Uninstall; rollback=[bool]$Rollback; clean_install=$true;
  deep_scan=[bool]$DeepScan; executables=$found; pep668_safe=$true; logs_root=$LogRoot
}
$result | ConvertTo-Json -Depth 5
if (-not $Apply) { exit 0 }

if ($Rollback) {
  if (-not (Test-Path $VenvCli)) { throw "Suite runtime not found" }
  & $VenvCli --home $HomePath package rollback --apply
  & $VenvCli --home $HomePath package verify
  & $VenvCli --home $HomePath status --logs
  exit 0
}
if ($Uninstall) {
  if (-not (Test-Path $VenvCli)) { throw "Suite runtime not found" }
  & $VenvCli --home $HomePath package uninstall --apply
  Remove-Item -Recurse -Force $RuntimeRoot
  Write-Host "uninstall complete; logs: $LogRoot"
  exit 0
}

New-Item -ItemType Directory -Force -Path $SuiteBase, $TxRoot | Out-Null
$Previous = ""
$AdapterMutated = $false
try {
  if (Test-Path $RuntimeRoot) {
    $Previous = Join-Path $TxRoot "previous-current"
    Move-Item -Path $RuntimeRoot -Destination $Previous
  }
  $BasePython = (Get-Command python -ErrorAction Stop).Source
  & $BasePython -m venv $Venv
  & $VenvPython -m pip install --no-index --disable-pip-version-check --no-input --find-links $WheelRoot "iot-ai-coder-suite==6.8.0b1"
  & $VenvCli --home $HomePath package install --hosts $Hosts --apply
  $AdapterMutated = $true
  & $VenvCli --home $HomePath package verify
  if (($PackageStore -and -not $CurrentPackage) -or ($CurrentPackage -and -not $PackageStore)) {
    throw "-PackageStore and -CurrentPackage must be supplied together"
  }
  if ($PackageStore) {
    $CleanArgs = @("--home",$HomePath,"package","clean","--current-version","6.8.0-beta.1","--package-store",$PackageStore,"--current-package",$CurrentPackage)
    if ($PackageArchive) { $CleanArgs += @("--package-archive",$PackageArchive) }
    $CleanArgs += "--apply"
    & $VenvCli @CleanArgs
  } else {
    & $VenvCli --home $HomePath package clean --current-version "6.8.0-beta.1" --apply
  }
  & $VenvCli --home $HomePath status --logs
  [ordered]@{
    schema="iot-ai.powershell-install-receipt.v1"; transaction_id=$TxId; version="6.8.0-beta.1";
    home=$HomePath; runtime=$RuntimeRoot; previous_runtime_archive=$Previous; clean_install=$true;
    logs_root=$LogRoot; decision="pass"
  } | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $TxRoot "POWERSHELL_INSTALL_RECEIPT.json") -Encoding utf8
  Write-Host "install complete; logs: $LogRoot; receipt: $(Join-Path $TxRoot 'POWERSHELL_INSTALL_RECEIPT.json')"
} catch {
  if ($AdapterMutated -and (Test-Path $VenvCli)) {
    try { & $VenvCli --home $HomePath package rollback --apply | Out-Null } catch {}
  }
  if (Test-Path $RuntimeRoot) { Remove-Item -Recurse -Force $RuntimeRoot }
  if ($Previous -and (Test-Path $Previous)) { Move-Item -Path $Previous -Destination $RuntimeRoot }
  Write-Error "install failed; rollback attempted; logs: $LogRoot; $($_.Exception.Message)"
  exit 1
}
