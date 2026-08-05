#!/usr/bin/env sh
# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-05
set -eu

APPLY=false
HOME_DIR="${HOME}"
HOSTS="all"
PACKAGE_STORE=""
CURRENT_PACKAGE=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --apply) APPLY=true ;;
    --home) shift; HOME_DIR="$1" ;;
    --hosts) shift; HOSTS="$1" ;;
    --package-store) shift; PACKAGE_STORE="$1" ;;
    --current-package) shift; CURRENT_PACKAGE="$1" ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DATA_HOME="${XDG_DATA_HOME:-$HOME_DIR/.local/share}"
STATE_HOME="${XDG_STATE_HOME:-$HOME_DIR/.local/state}"
SUITE_BASE="$DATA_HOME/ai-iot-tech/iot-ai-suite/v1/suite"
RUNTIME_ROOT="$SUITE_BASE/6.5.0-beta.2"
TX_ID="shell-install-$(date -u +%Y%m%dT%H%M%SZ)-$$"
TX_ROOT="$DATA_HOME/ai-iot-tech/iot-ai-suite/v1/update-transactions/$TX_ID"
LOG_ROOT="$STATE_HOME/ai-iot-tech/iot-ai-suite/v1/logs"
VENV="$RUNTIME_ROOT/venv"
WHEEL_ROOT="$ROOT/wheels"
[ -d "$WHEEL_ROOT" ] || WHEEL_ROOT="$ROOT/installers/wheels"

printf '%s\n' '{"schema":"iot-ai.install-plan.v3","version":"6.5.0-beta.2","home":"'"$HOME_DIR"'","runtime":"'"$RUNTIME_ROOT"'","apply":'"$APPLY"',"clean_install":true,"pep668_safe":true,"logs_root":"'"$LOG_ROOT"'"}'
[ "$APPLY" = true ] || exit 0

mkdir -p "$SUITE_BASE" "$TX_ROOT"
PREVIOUS=""
ADAPTER_MUTATED=false
rollback_on_error() {
  code=$?
  trap - EXIT HUP INT TERM
  if [ "$code" -ne 0 ]; then
    if [ "$ADAPTER_MUTATED" = true ] && [ -x "$VENV/bin/iot-ai" ]; then
      "$VENV/bin/iot-ai" --home "$HOME_DIR" package rollback --apply >/dev/null 2>&1 || true
    fi
    rm -rf "$RUNTIME_ROOT"
    if [ -n "$PREVIOUS" ] && [ -d "$PREVIOUS" ]; then
      mv "$PREVIOUS" "$RUNTIME_ROOT"
    fi
    printf '%s\n' "install failed; rollback attempted; logs: $LOG_ROOT" >&2
  fi
  exit "$code"
}
trap rollback_on_error EXIT HUP INT TERM

if [ -e "$RUNTIME_ROOT" ]; then
  PREVIOUS="$TX_ROOT/previous-current"
  mv "$RUNTIME_ROOT" "$PREVIOUS"
fi

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --no-index --disable-pip-version-check --no-input --find-links "$WHEEL_ROOT" "iot-ai-coder-suite==6.5.0b2"
"$VENV/bin/iot-ai" --home "$HOME_DIR" package install --hosts "$HOSTS" --apply
ADAPTER_MUTATED=true
"$VENV/bin/iot-ai" --home "$HOME_DIR" package verify

if [ -n "$PACKAGE_STORE" ] || [ -n "$CURRENT_PACKAGE" ]; then
  if [ -z "$PACKAGE_STORE" ] || [ -z "$CURRENT_PACKAGE" ]; then
    echo "--package-store and --current-package must be supplied together" >&2
    exit 2
  fi
  "$VENV/bin/iot-ai" --home "$HOME_DIR" package clean \
    --current-version "6.5.0-beta.2" \
    --package-store "$PACKAGE_STORE" \
    --current-package "$CURRENT_PACKAGE" \
    --apply
else
  "$VENV/bin/iot-ai" --home "$HOME_DIR" package clean --current-version "6.5.0-beta.2" --apply
fi

"$VENV/bin/iot-ai" --home "$HOME_DIR" status --logs
cat > "$TX_ROOT/SHELL_INSTALL_RECEIPT.json" <<JSON
{
  "schema": "iot-ai.shell-install-receipt.v1",
  "transaction_id": "$TX_ID",
  "version": "6.5.0-beta.2",
  "home": "$HOME_DIR",
  "runtime": "$RUNTIME_ROOT",
  "previous_runtime_archive": "$PREVIOUS",
  "clean_install": true,
  "logs_root": "$LOG_ROOT",
  "decision": "pass"
}
JSON
trap - EXIT HUP INT TERM
printf '%s\n' "install complete; logs: $LOG_ROOT; receipt: $TX_ROOT/SHELL_INSTALL_RECEIPT.json"
