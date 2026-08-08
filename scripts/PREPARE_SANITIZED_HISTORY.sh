#!/usr/bin/env sh
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
set -eu
SOURCE=${1:-.}
TARGET=${2:-/tmp/mc-gpt-sanitized-history}
rm -rf "$TARGET"
mkdir -p "$TARGET"
( cd "$SOURCE" && tar --exclude=.git --exclude=.venv --exclude=__pycache__ --exclude=.pytest_cache --exclude=dist --exclude=build -cf - . ) | ( cd "$TARGET" && tar -xf - )
python3 "$TARGET/tools/public_boundary_check.py" "$TARGET"
git -C "$TARGET" init -q
git -C "$TARGET" checkout -q -b main
git -C "$TARGET" config user.name "IoT-AI.Tech Release"
git -C "$TARGET" config user.email "release@iot-ai.tech"
git -C "$TARGET" remote add origin https://github.com/IoTAiTech/MC-GPT.git
git -C "$TARGET" add -A
GIT_AUTHOR_NAME="IoT-AI.Tech Release" GIT_AUTHOR_EMAIL="release@iot-ai.tech" GIT_AUTHOR_DATE="2026-08-07T00:00:00Z" GIT_COMMITTER_NAME="IoT-AI.Tech Release" GIT_COMMITTER_EMAIL="release@iot-ai.tech" GIT_COMMITTER_DATE="2026-08-07T00:00:00Z" git -C "$TARGET" commit -q -m "release: sanitized IOT-AI Suite 6.7.0-beta.4 candidate"
git -C "$TARGET" tag -a "v6.7.0-beta.4-rc.1" -m "Sanitized local release candidate; production_claim=false"
python3 "$TARGET/tools/public_boundary_check.py" "$TARGET" --git-history
echo "$TARGET"
