# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
# Deprecated compatibility launcher; use Install-IotAiSuite.ps1.
param(
  [switch]$Apply,
  [switch]$Uninstall,
  [switch]$Rollback,
  [switch]$DeepScan,
  [string]$Home = $env:USERPROFILE,
  [string]$Hosts = "all"
)
& (Join-Path $PSScriptRoot "Install-IotAiSuite.ps1") `
  -Apply:$Apply `
  -Uninstall:$Uninstall `
  -Rollback:$Rollback `
  -DeepScan:$DeepScan `
  -Home $Home `
  -Hosts $Hosts
