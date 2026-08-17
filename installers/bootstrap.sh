#!/usr/bin/env sh
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.6 | Date: 2026-08-17
set -eu
VERSION="6.7.0-beta.6"
URL="${IOT_AI_RELEASE_URL:-https://github.com/IoTAiTech/MC-GPT/releases/download/v$VERSION/IoT-AI-Tech-iot-ai-Coder-Suite-v$VERSION-ALL-IN-ONE.zip}"
EXPECTED="${IOT_AI_RELEASE_SHA256:-}"
HOME_DIR="$HOME"
PACKAGE_STORE="${IOT_AI_PACKAGE_STORE:-$HOME/ai-iot/Install/MC-GPT}"
PACKAGE_ARCHIVE="${IOT_AI_PACKAGE_ARCHIVE:-$HOME/ai-iot/Archive/MC-GPT}"
APPLY=false
LOCAL_PACKAGE=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --url) shift; URL="$1" ;;
    --package) shift; LOCAL_PACKAGE="$1" ;;
    --sha256) shift; EXPECTED="$1" ;;
    --home) shift; HOME_DIR="$1" ;;
    --package-store) shift; PACKAGE_STORE="$1" ;;
    --package-archive) shift; PACKAGE_ARCHIVE="$1" ;;
    --apply) APPLY=true ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
[ -n "$EXPECTED" ] || { echo "expected SHA-256 is required" >&2; exit 2; }
TMP=$(mktemp -d "${TMPDIR:-/tmp}/iot-ai-bootstrap.XXXXXX")
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
PKG="$TMP/IoT-AI-Tech-iot-ai-Coder-Suite-v$VERSION-ALL-IN-ONE.zip"
if [ -n "$LOCAL_PACKAGE" ]; then cp "$LOCAL_PACKAGE" "$PKG"; else curl --fail --silent --show-error --location "$URL" --output "$PKG"; fi
ACTUAL=$(sha256sum "$PKG" | awk '{print $1}')
[ "$ACTUAL" = "$EXPECTED" ] || { echo "SHA-256 mismatch" >&2; exit 3; }
mkdir -p "$PACKAGE_STORE" "$PACKAGE_ARCHIVE"
CANONICAL="$PACKAGE_STORE/$(basename "$PKG")"
cp "$PKG" "$CANONICAL"
unzip -q "$CANONICAL" -d "$TMP/stage"
INSTALLER="$TMP/stage/installers/install.sh"
[ -f "$INSTALLER" ] || INSTALLER="$TMP/stage/install.sh"
[ -f "$INSTALLER" ] || { echo "canonical installer missing" >&2; exit 4; }
set -- --home "$HOME_DIR" --package-store "$PACKAGE_STORE" --package-archive "$PACKAGE_ARCHIVE" --current-package "$CANONICAL"
[ "$APPLY" = true ] && set -- "$@" --apply
sh "$INSTALLER" "$@"
