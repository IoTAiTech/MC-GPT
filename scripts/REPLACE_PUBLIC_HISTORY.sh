#!/usr/bin/env sh
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
set -eu
CANDIDATE=${1:?sanitized candidate path required}
EXPECTED_REMOTE_SHA=${2:?current remote main SHA required}
[ "${IOT_AI_FOUNDER_CONFIRM:-}" = "FOUNDER_REPLACE_SANITIZED_PUBLIC_HISTORY" ] || { echo "Founder confirmation missing" >&2; exit 2; }
python3 "$CANDIDATE/tools/public_boundary_check.py" "$CANDIDATE" --git-history
ACTUAL=$(git -C "$CANDIDATE" ls-remote origin refs/heads/main | awk '{print $1}')
[ "$ACTUAL" = "$EXPECTED_REMOTE_SHA" ] || { echo "remote main changed; aborting" >&2; exit 3; }
git -C "$CANDIDATE" push --force-with-lease=refs/heads/main:$EXPECTED_REMOTE_SHA origin main:main
git -C "$CANDIDATE" push origin "v6.7.0-beta.4-rc.1"
