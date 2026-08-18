#!/usr/bin/env sh
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-18
set -eu
VERSION="6.8.0-beta.1"
PY_VERSION="6.8.0b1"

APPLY=false
HOME_DIR="${HOME}"
HOSTS="all"
PACKAGE_STORE=""
PACKAGE_ARCHIVE=""
CURRENT_PACKAGE=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --apply) APPLY=true ;;
    --home) shift; HOME_DIR="$1" ;;
    --hosts) shift; HOSTS="$1" ;;
    --package-store) shift; PACKAGE_STORE="$1" ;;
    --package-archive) shift; PACKAGE_ARCHIVE="$1" ;;
    --current-package) shift; CURRENT_PACKAGE="$1" ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DATA_HOME="${XDG_DATA_HOME:-$HOME_DIR/.local/share}"
STATE_HOME="${XDG_STATE_HOME:-$HOME_DIR/.local/state}"
SUITE_BASE="$DATA_HOME/iot-ai-tech/iot-ai-suite/v1/suite"
RUNTIME_ROOT="$SUITE_BASE/$VERSION"
TX_ID="shell-install-$(date -u +%Y%m%dT%H%M%SZ)-$$"
TX_ROOT="$DATA_HOME/iot-ai-tech/iot-ai-suite/v1/update-transactions/$TX_ID"
LOG_ROOT="$STATE_HOME/iot-ai-tech/iot-ai-suite/v1/logs"
VENV="$RUNTIME_ROOT/venv"
WHEEL_ROOT="$ROOT/wheels"
[ -d "$WHEEL_ROOT" ] || WHEEL_ROOT="$ROOT/installers/wheels"

_json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}
printf '%s\n' '{"schema":"iot-ai.install-plan.v3","version":"'"$VERSION"'","home":"'"$(_json_escape "$HOME_DIR")"'","runtime":"'"$(_json_escape "$RUNTIME_ROOT")"'","apply":'"$APPLY"',"clean_install":true,"pep668_safe":true,"logs_root":"'"$(_json_escape "$LOG_ROOT")"'"}'
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
if ls "$WHEEL_ROOT"/iot_ai_coder_suite-${PY_VERSION}*.whl >/dev/null 2>&1; then
  "$VENV/bin/python" -m pip install --no-index --disable-pip-version-check --no-input --find-links "$WHEEL_ROOT" "iot-ai-coder-suite==$PY_VERSION"
else
  "$VENV/bin/python" -m pip install --disable-pip-version-check --no-input "setuptools>=75" "wheel>=0.45"
  "$VENV/bin/python" -m pip install --no-build-isolation --no-index --disable-pip-version-check --no-input --find-links "$WHEEL_ROOT" "$ROOT"
fi
"$VENV/bin/iot-ai" --home "$HOME_DIR" package install --hosts "$HOSTS" --apply
ADAPTER_MUTATED=true
"$VENV/bin/iot-ai" --home "$HOME_DIR" package verify

if [ -n "$PACKAGE_STORE" ]; then
  if [ -z "$CURRENT_PACKAGE" ]; then
    CURRENT_PACKAGE="$PACKAGE_STORE/IoT-AI-Tech-iot-ai-Coder-Suite-v$VERSION-ALL-IN-ONE.zip"
  fi
  [ -f "$CURRENT_PACKAGE" ] || { echo "current package not found: $CURRENT_PACKAGE" >&2; exit 2; }
  set -- --current-version "$VERSION" --package-store "$PACKAGE_STORE" --current-package "$CURRENT_PACKAGE"
  if [ -n "$PACKAGE_ARCHIVE" ]; then set -- "$@" --package-archive "$PACKAGE_ARCHIVE"; fi
  "$VENV/bin/iot-ai" --home "$HOME_DIR" package clean "$@" --apply
else
  [ -z "$PACKAGE_ARCHIVE" ] || { echo "--package-archive requires --package-store" >&2; exit 2; }
  "$VENV/bin/iot-ai" --home "$HOME_DIR" package clean --current-version "$VERSION" --apply
fi

"$VENV/bin/iot-ai" --home "$HOME_DIR" status --logs
cat > "$TX_ROOT/SHELL_INSTALL_RECEIPT.json" <<JSON
{
  "schema": "iot-ai.shell-install-receipt.v1",
  "transaction_id": "$TX_ID",
  "version": "$VERSION",
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
