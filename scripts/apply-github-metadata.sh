#!/usr/bin/env bash
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
set -euo pipefail

REPO="${1:-IoTAiTech/MC-GPT}"
EXPECTED_CONFIRM="FOUNDER_APPLY_GITHUB_METADATA"
if [[ "${IOT_AI_FOUNDER_CONFIRM:-}" != "$EXPECTED_CONFIRM" ]]; then
  echo "blocked: set IOT_AI_FOUNDER_CONFIRM=$EXPECTED_CONFIRM" >&2
  exit 3
fi
command -v gh >/dev/null 2>&1 || { echo "blocked: gh CLI is required" >&2; exit 4; }
gh auth status >/dev/null

DESCRIPTION="Natural-language multi-agent AI coding control plane for Claude, Codex, Gemini, Grok and Ollama: autonomous Task-Meeting-Multi-Coder repair loops, tests, audit and rollback."
HOMEPAGE="https://iot-ai.tech"
TOPICS="multi-agent,ai-coding,coding-agent,agentic-ai,ai-orchestration,multi-coder,autonomous-coding,claude-code,openai-codex,gemini-cli,grok-cli,ollama,developer-tools,devsecops,ai-governance,human-in-the-loop,on-premises,data-sovereignty,eu-ai-act,python"

gh repo edit "$REPO" \
  --description "$DESCRIPTION" \
  --homepage "$HOMEPAGE" \
  --add-topic "$TOPICS"

echo "pass: metadata applied to $REPO"
echo "note: GitHub Social Preview image must still be uploaded through repository Settings if not already configured."
