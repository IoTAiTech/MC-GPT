<!-- SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0 -->
# Codex / ChatGPT follow-on for PR 20

Author: Dr.-Ing. Babak Sorkhpour, with AI assistance

This file exists so Codex and ChatGPT can continue this work after a Grok
weekly-limit stop. **GitHub is authoritative.** Do not look for a `/tmp`
worktree.

- Repository: https://github.com/IoTAiTech/MC-GPT
- Branch: `feat/settings-skill-autodiscovery-v1`
- Pull request: https://github.com/IoTAiTech/MC-GPT/pull/20
- Do not modify, merge, close, undraft, rebase, reset, or force-push PR #19
- Merge method when gates pass: squash (linear history)
- Production claim: false
- provider_calls: 0

Recreate:

```text
git clone https://github.com/IoTAiTech/MC-GPT
git checkout feat/settings-skill-autodiscovery-v1
PYTHONPATH=src python3 -m pytest tests/test_runtime_settings_v2.py tests/test_skill_router.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 tools/public_boundary_check.py
python3 tools/verify_repository.py
```
