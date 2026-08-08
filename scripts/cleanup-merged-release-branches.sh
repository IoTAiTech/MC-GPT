#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
set -euo pipefail

REPO="${1:-IoTAiTech/MC-GPT}"
TAG="${2:-}"
EXPECTED_MAIN_SHA="${3:-}"
EXPECTED_CONFIRM="FOUNDER_CLEAN_MERGED_RELEASE_BRANCHES"

if [[ "${IOT_AI_FOUNDER_CONFIRM:-}" != "$EXPECTED_CONFIRM" ]]; then
  echo "blocked: set IOT_AI_FOUNDER_CONFIRM=$EXPECTED_CONFIRM" >&2
  exit 3
fi
if [[ -z "$TAG" || -z "$EXPECTED_MAIN_SHA" ]]; then
  echo "usage: $0 <owner/repo> <published-tag> <expected-main-sha>" >&2
  exit 4
fi
command -v gh >/dev/null 2>&1 || { echo "blocked: gh CLI is required" >&2; exit 5; }
command -v git >/dev/null 2>&1 || { echo "blocked: git is required" >&2; exit 5; }
gh auth status >/dev/null

main_sha="$(gh api "repos/$REPO/commits/main" --jq .sha)"
[[ "$main_sha" == "$EXPECTED_MAIN_SHA" ]] || {
  echo "blocked: main SHA mismatch ($main_sha != $EXPECTED_MAIN_SHA)" >&2
  exit 6
}
gh release view "$TAG" --repo "$REPO" >/dev/null || {
  echo "blocked: GitHub Release $TAG is not visible" >&2
  exit 7
}
tag_sha="$(gh api "repos/$REPO/git/ref/tags/$TAG" --jq .object.sha)"
# Annotated tags point to a tag object; peel it when needed.
object_type="$(gh api "repos/$REPO/git/ref/tags/$TAG" --jq .object.type)"
if [[ "$object_type" == "tag" ]]; then
  tag_sha="$(gh api "repos/$REPO/git/tags/$tag_sha" --jq .object.sha)"
fi
[[ "$tag_sha" == "$main_sha" ]] || {
  echo "blocked: release tag does not point to current main ($tag_sha != $main_sha)" >&2
  exit 8
}

mapfile -t open_heads < <(gh pr list --repo "$REPO" --state open --json headRefName --jq '.[].headRefName')
mapfile -t branches < <(gh api --paginate "repos/$REPO/branches?per_page=100" --jq '.[].name')

deleted=0
skipped=0
for branch in "${branches[@]}"; do
  case "$branch" in
    main|master|develop) ((skipped+=1)); continue ;;
  esac
  case "$branch" in
    release/*|fix/*|security/*|hotfix/*|chore/*) ;;
    *) ((skipped+=1)); continue ;;
  esac
  if printf '%s\n' "${open_heads[@]:-}" | grep -Fxq "$branch"; then
    echo "skip open PR branch: $branch"
    ((skipped+=1)); continue
  fi
  branch_sha="$(gh api "repos/$REPO/branches/$branch" --jq .commit.sha)"
  compare="$(gh api "repos/$REPO/compare/$branch_sha...$main_sha" --jq .status)"
  if [[ "$compare" != "ahead" && "$compare" != "identical" ]]; then
    echo "skip unmerged branch: $branch ($compare)"
    ((skipped+=1)); continue
  fi
  gh api -X DELETE "repos/$REPO/git/refs/heads/$branch"
  echo "deleted merged release branch: $branch"
  ((deleted+=1))
done

printf 'pass: deleted=%d skipped=%d repo=%s tag=%s main=%s\n' "$deleted" "$skipped" "$REPO" "$TAG" "$main_sha"
