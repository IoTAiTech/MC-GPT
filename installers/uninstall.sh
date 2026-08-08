#!/usr/bin/env sh
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.4 | Date: 2026-08-08
set -eu
HOME_DIR="${HOME}"
while [ "$#" -gt 0 ]; do
  case "$1" in --home) shift; HOME_DIR="$1" ;; *) echo "unknown option: $1" >&2; exit 2 ;; esac
  shift
done
DATA_HOME="${XDG_DATA_HOME:-$HOME_DIR/.local/share}"
RUNTIME_ROOT="$DATA_HOME/iot-ai-tech/iot-ai-suite/v1/suite/6.7.0-beta.4"
VENV="$RUNTIME_ROOT/venv"
[ -x "$VENV/bin/iot-ai" ] || { echo "Suite runtime not found: $VENV" >&2; exit 1; }
BACKUP="$DATA_HOME/iot-ai-tech/iot-ai-suite/v1/uninstall-backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP"
cp -a "$RUNTIME_ROOT" "$BACKUP/runtime"
"$VENV/bin/iot-ai" --home "$HOME_DIR" package uninstall --apply
rm -rf "$RUNTIME_ROOT"
printf '{"decision":"pass","backup":"%s"}\n' "$BACKUP"
