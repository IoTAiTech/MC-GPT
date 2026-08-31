#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-29
set -euo pipefail
umask 077

REPO="${1:-IoTAiTech/MC-GPT}"
EXPECTED_CONFIRM="FOUNDER_APPLY_GITHUB_METADATA"
if [[ "${IOT_AI_FOUNDER_CONFIRM:-}" != "$EXPECTED_CONFIRM" ]]; then
  echo "blocked: set IOT_AI_FOUNDER_CONFIRM=$EXPECTED_CONFIRM" >&2
  exit 3
fi

command -v gh >/dev/null 2>&1 || {
  echo "blocked: gh CLI is required" >&2
  exit 4
}
command -v python3 >/dev/null 2>&1 || {
  echo "blocked: python3 is required" >&2
  exit 4
}
gh auth status >/dev/null

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
METADATA="$REPO_ROOT/GITHUB_REPOSITORY_METADATA.json"
[[ -f "$METADATA" ]] || {
  echo "blocked: metadata file is missing: $METADATA" >&2
  exit 5
}

EXPECTED_REPO="$(python3 - "$METADATA" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(data["repository"])
PY
)"
[[ "$REPO" == "$EXPECTED_REPO" ]] || {
  echo "blocked: target repository does not match metadata: $REPO != $EXPECTED_REPO" >&2
  exit 6
}

DESCRIPTION="$(python3 - "$METADATA" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
value = str(data["description"]).strip()
if not value or len(value) > 350 or "\n" in value:
    raise SystemExit("invalid repository description")
print(value)
PY
)"

HOMEPAGE="$(python3 - "$METADATA" <<'PY'
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
value = str(data["homepage"]).strip()
parsed = urlparse(value)
if parsed.scheme != "https" or not parsed.netloc:
    raise SystemExit("homepage must be an absolute HTTPS URL")
print(value)
PY
)"

TOPICS_CSV="$(python3 - "$METADATA" <<'PY'
import json
import re
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
topics = data["topics"]
if not isinstance(topics, list) or not 1 <= len(topics) <= 20:
    raise SystemExit("topics must contain between 1 and 20 entries")
if len(set(topics)) != len(topics):
    raise SystemExit("topics must be unique")
if any(not isinstance(topic, str) or not re.fullmatch(r"[a-z0-9-]{1,50}", topic) for topic in topics):
    raise SystemExit("invalid topic")
print(",".join(topics))
PY
)"

while IFS= read -r topic; do
  [[ -n "$topic" ]] || continue
  case ",$TOPICS_CSV," in
    *",$topic,"*) ;;
    *) gh repo edit "$REPO" --remove-topic "$topic" ;;
  esac
done < <(gh api "repos/$REPO" --jq '.topics[]')

gh repo edit "$REPO" \
  --description "$DESCRIPTION" \
  --homepage "$HOMEPAGE" \
  --add-topic "$TOPICS_CSV"

echo "pass: metadata applied from $METADATA to $REPO"
echo "note: upload the approved social preview through repository Settings when required."
