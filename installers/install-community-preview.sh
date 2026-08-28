#!/bin/sh
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-08-28
# Purpose: Plan-first, SHA-256-verified installation of the latest tagged
# MC-GPT Community Developer Preview into a versioned user environment.

set -eu
umask 077

VERSION="6.7.0-beta.6"
WHEEL="iot_ai_coder_suite-6.7.0b6-py3-none-any.whl"
WHEEL_URL="https://github.com/IoTAiTech/MC-GPT/releases/download/v${VERSION}/${WHEEL}"
EXPECTED_SHA256="18a752eddcfa9336152cfe72e8ab320372e021121f89e68dbe086474f8ab2807"

BASE="${IOT_AI_COMMUNITY_HOME:-$HOME/.local/share/iot-ai-tech/mc-gpt-community}"
BIN_DIR="${IOT_AI_BIN_DIR:-$HOME/.local/bin}"
STATE_DIR="${IOT_AI_STATE_DIR:-$HOME/.local/state/iot-ai-tech/mc-gpt-community}"
APPLY=false
REINSTALL=false
ROLLBACK=false

usage() {
  cat <<'USAGE'
Usage:
  install-community-preview.sh [--apply] [--reinstall]
  install-community-preview.sh --rollback

Options:
  --apply       Perform the displayed installation transaction.
  --reinstall   Replace an already installed copy of the same managed version.
  --rollback    Restore the previous managed version, when available.
  --help        Show this help.

Environment overrides:
  IOT_AI_COMMUNITY_HOME   Managed version/archive root.
  IOT_AI_BIN_DIR          User wrapper directory.
  IOT_AI_STATE_DIR        Install log/receipt root.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --apply) APPLY=true ;;
    --reinstall) REINSTALL=true ;;
    --rollback) ROLLBACK=true ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

VERSIONS="$BASE/versions"
ARCHIVE="$BASE/archive"
CURRENT="$BASE/current"
PREVIOUS="$BASE/previous"
TARGET="$VERSIONS/$VERSION"
LOG_DIR="$STATE_DIR/install"
UTC="$(date -u '+%Y%m%dT%H%M%SZ')"
LOG="$LOG_DIR/install-${UTC}.log"
RECEIPT="$LOG_DIR/install-${UTC}.receipt"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "required command not found: $1" >&2
    exit 4
  }
}

python_check() {
  python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required")
print(f"python={sys.version.split()[0]}")
PY
}

link_wrappers() {
  root="$1"
  mkdir -p "$BIN_DIR"
  for name in \
    iot-ai \
    iot-ai-help \
    iot-ai-status \
    iot-ai-settings \
    iot-ai-update \
    iot-ai-meeting \
    iot-ai-tasks \
    iot-ai-multi-coder
  do
    src="$root/venv/bin/$name"
    [ -x "$src" ] || {
      echo "installed wrapper missing: $src" >&2
      exit 8
    }
    ln -sfn "$src" "$BIN_DIR/$name"
  done
}

resolve_link() {
  path="$1"
  [ -L "$path" ] || return 1
  readlink "$path"
}

if [ "$ROLLBACK" = true ]; then
  [ "$APPLY" = false ] || {
    echo "--rollback and --apply are mutually exclusive" >&2
    exit 2
  }
  previous_target="$(resolve_link "$PREVIOUS" || true)"
  current_target="$(resolve_link "$CURRENT" || true)"
  [ -n "$previous_target" ] && [ -d "$previous_target" ] || {
    echo "no managed previous version is available" >&2
    exit 5
  }
  mkdir -p "$LOG_DIR"
  printf '%s\n' \
    "MC-GPT managed rollback plan" \
    "current=$current_target" \
    "restore=$previous_target" \
    "bin_dir=$BIN_DIR" \
    "log=$LOG"
  ln -sfn "$previous_target" "$CURRENT"
  [ -n "$current_target" ] && ln -sfn "$current_target" "$PREVIOUS"
  link_wrappers "$previous_target"
  {
    printf 'action=rollback\n'
    printf 'restored=%s\n' "$previous_target"
    printf 'previous=%s\n' "$current_target"
    printf 'production_claim=false\n'
  } > "$RECEIPT"
  printf 'rollback complete\nreceipt=%s\n' "$RECEIPT"
  exit 0
fi

require_command python3
require_command curl
python_check

current_target="$(resolve_link "$CURRENT" || true)"

cat <<PLAN
MC-GPT Community Developer Preview installation plan
version=$VERSION
wheel=$WHEEL
source=$WHEEL_URL
expected_sha256=$EXPECTED_SHA256
target=$TARGET
current=${current_target:-none}
archive=$ARCHIVE
bin_dir=$BIN_DIR
log=$LOG
apply=$APPLY
production_claim=false
PLAN

[ "$APPLY" = true ] || {
  echo "plan only; rerun with --apply after reviewing the paths and licence"
  exit 0
}

mkdir -p "$VERSIONS" "$ARCHIVE" "$LOG_DIR" "$BIN_DIR"

if [ -e "$TARGET" ] && [ "$REINSTALL" != true ]; then
  echo "managed version already exists: $TARGET" >&2
  echo "use --reinstall only when an explicit replacement is intended" >&2
  exit 6
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/mc-gpt-community.XXXXXX")"
STAGE="$VERSIONS/.${VERSION}.stage.$$"
cleanup() {
  rm -rf "$TMP" "$STAGE"
}
trap cleanup EXIT HUP INT TERM

{
  echo "download_start=$UTC"
  echo "url=$WHEEL_URL"
  curl --fail --silent --show-error --location "$WHEEL_URL" --output "$TMP/$WHEEL"

  python3 - "$TMP/$WHEEL" "$EXPECTED_SHA256" <<'PY'
from pathlib import Path
import hashlib
import sys

path = Path(sys.argv[1])
expected = sys.argv[2].lower()
actual = hashlib.sha256(path.read_bytes()).hexdigest()
print(f"wheel_sha256={actual}")
if actual != expected:
    raise SystemExit("wheel SHA-256 mismatch")
PY

  python3 -m venv "$STAGE/venv"
  "$STAGE/venv/bin/python" -m pip install --disable-pip-version-check --upgrade pip
  "$STAGE/venv/bin/python" -m pip install --disable-pip-version-check "$TMP/$WHEEL"
  "$STAGE/venv/bin/iot-ai" --version

  if [ -e "$TARGET" ]; then
    same_archive="$ARCHIVE/${VERSION}-replaced-${UTC}"
    mv "$TARGET" "$same_archive"
    echo "same_version_archived=$same_archive"
  fi

  mv "$STAGE" "$TARGET"

  archived_previous=""
  if [ -n "$current_target" ] && [ "$current_target" != "$TARGET" ] && [ -d "$current_target" ]; then
    case "$current_target" in
      "$VERSIONS"/*)
        archived_previous="$ARCHIVE/$(basename "$current_target")-${UTC}"
        mv "$current_target" "$archived_previous"
        ln -sfn "$archived_previous" "$PREVIOUS"
        ;;
      *)
        echo "previous target is outside the managed versions root; it was preserved: $current_target"
        ;;
    esac
  fi

  ln -sfn "$TARGET" "$CURRENT"
  link_wrappers "$TARGET"

  "$TARGET/venv/bin/iot-ai" --version
  "$TARGET/venv/bin/iot-ai" help >/dev/null

  {
    printf 'action=install\n'
    printf 'version=%s\n' "$VERSION"
    printf 'wheel_sha256=%s\n' "$EXPECTED_SHA256"
    printf 'target=%s\n' "$TARGET"
    printf 'current=%s\n' "$CURRENT"
    printf 'previous=%s\n' "${archived_previous:-none}"
    printf 'bin_dir=%s\n' "$BIN_DIR"
    printf 'production_claim=false\n'
  } > "$RECEIPT"

  echo "install complete"
  echo "receipt=$RECEIPT"
  echo "runtime_logs: run 'iot-ai status --logs'"
} 2>&1 | tee "$LOG"
