# Work with ChatGPT and Codex through GitHub

Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Version: 1.0.0 | Date: 2026-09-05

## Shared context

The current starting point is `docs/coordination/CURRENT_HANDOFF.md` on the
live head of PR23. Until integration, the default branch may not contain the
current handoff. Fetch the PR rather than assuming main has the fixes.

Codex does not automatically receive this ChatGPT conversation. Repository
files, pull request comments and reviewed evidence are the shared context.
ChatGPT can read Codex's posted results through the GitHub connector during an
active session. This does not create background monitoring after a chat ends.

## Local Codex: one starting instruction

Give Codex this instruction once, with access to the repository:

```text
Work with ChatGPT on IoTAiTech/MC-GPT PR23. Read its live head, applicable
AGENTS.md and docs/coordination/CURRENT_HANDOFF.md from that head. Start as
an independent read-only reviewer in a fresh detached checkout. Reproduce the
listed checks; inspect the real command-execution and completion paths, not
only reported test totals. Post your exact-head findings and evidence summary
to PR23. Do not modify the writer's branch, self-approve, merge, release,
spend on provider benchmarks, or access PMD/customer data. If the head changed,
refresh only affected evidence. Ask for a scoped implementation handoff before
changing source. Keep all repository text in English and keep private data out.
```

With authenticated GitHub CLI access, Codex can read the shared conversation:

```sh
gh pr view 23 --repo IoTAiTech/MC-GPT --json headRefOid,headRefName,baseRefName,body,comments,reviews,statusCheckRollup
```

The GitHub connector is an alternative to this command. Use the existing
approved login; never copy access tokens into a prompt, repo or report.

## GitHub Codex integration

When Codex cloud/code review is enabled for this repository, a PR comment
containing `@codex review` requests a review. A reaction or request is not a
completed review. Read the actual result and the commit it covers. Availability
and usage are controlled by the connected account and workspace. No automatic
paid API fallback is configured here.

The implementation and review actors can exchange subsequent work through the
same PR. Only the active authorized writer changes shared files. A normal
GitHub approval still has to satisfy the repository's protection rules.

## Programmatic option, not deployed here

Codex App Server supports controlled thread/turn interactions. It can underpin
a future authenticated MC-GPT adapter, but is not an API for reading arbitrary
ChatGPT private history and does not attach a terminal automatically to this
chat. Reuse the existing MC-GPT transport/identity boundaries rather than adding
a second orchestration system. No new network service is installed by this doc.

## Official references checked 2026-09-05

- https://developers.openai.com/codex/integrations/github/
- https://developers.openai.com/codex/guides/agents-md/
- https://developers.openai.com/codex/app-server/
- https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex
