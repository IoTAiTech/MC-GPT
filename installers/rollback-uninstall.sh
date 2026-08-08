#!/usr/bin/env sh
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.4 | Date: 2026-08-08
set -eu
[ "$#" -ge 1 ] || { echo "usage: $0 <backup-dir> [--home <home>]" >&2; exit 2; }
BACKUP="$1"; shift
HOME_DIR="${HOME}"
while [ "$#" -gt 0 ]; do case "$1" in --home) shift; HOME_DIR="$1" ;; *) echo "unknown option: $1" >&2; exit 2 ;; esac; shift; done
DATA_HOME="${XDG_DATA_HOME:-$HOME_DIR/.local/share}"
RUNTIME_ROOT="$DATA_HOME/iot-ai-tech/iot-ai-suite/v1/suite/6.7.0-beta.4"
[ -d "$BACKUP/runtime" ] || { echo "invalid backup" >&2; exit 1; }
rm -rf "$RUNTIME_ROOT"
mkdir -p "$(dirname "$RUNTIME_ROOT")"
cp -a "$BACKUP/runtime" "$RUNTIME_ROOT"
"$RUNTIME_ROOT/venv/bin/iot-ai" --home "$HOME_DIR" package rollback --apply
"$RUNTIME_ROOT/venv/bin/iot-ai" --home "$HOME_DIR" package verify
