# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-05
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
