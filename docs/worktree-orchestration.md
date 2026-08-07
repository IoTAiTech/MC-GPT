# Governed Worktree Orchestration

IOT-AI uses standard Git worktrees to isolate parallel coder tasks. The pattern is inspired by modern worktree-native agent tools, while IOT-AI adds immutable role contracts, provider/model receipts, task authority, privacy gates and human-reviewed promotion.

## Plan

```bash
iot-ai worktree plan \
  --repo . \
  --goal "Review and harden authentication" \
  --agents codex,grok,claude \
  --max-parallel 3
```

Planning is read-only. The plan binds the repository root, exact base commit, branch names, paths and worker identities.

## Create

```bash
iot-ai worktree create \
  --repo . \
  --goal "Review and harden authentication" \
  --agents codex,grok,claude \
  --max-parallel 3 \
  --apply
```

Only tracked Git content enters a worker tree. Untracked files, local `.env` files and ad-hoc secrets are not copied.

## Inspect and review

```bash
iot-ai worktree list
iot-ai worktree show <run-id>
iot-ai worktree review <run-id>
iot-ai worktree review <run-id> --winner codex
```

`review` never merges. It produces a human promotion plan containing branches, commits, dirty state and diff statistics. The expected next steps are independent review, deterministic tests, winner selection, a draft PR and human merge.

## Cleanup

```bash
iot-ai worktree cleanup <run-id>
iot-ai worktree cleanup <run-id> --apply
```

Cleanup is blocked when a worker is dirty or has commits not present in the base. IOT-AI never deletes potentially valuable agent work just to make the workspace look clean.

## Limits in this release

- CLI only; no desktop worktree/terminal UI is claimed.
- No automatic winner selection or merge.
- No automatic copy of untracked configuration between worktrees.
- GitHub publication uses the separate, allowlist-driven release workflow in `docs/github-publishing-runbook.md`.
