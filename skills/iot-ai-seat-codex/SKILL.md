---
name: iot-ai-seat-codex
description: Launch a sandboxed Codex seat that builds, tests, executes a finding, or drafts from code. Use for a Codex build, read-only review, fix round, find-check, or draft.
id: iot-ai-seat-codex
version: 1.0.0
category: general
license: LicenseRef-PolyForm-Noncommercial-1.0.0
---
# iot-ai-seat-codex

Author: Dr. Babak Sorkhpour with AI assistance  
Version: 1.0.0 | Date: 2026-10-10

Codex executes. Its output is a measurement. A candidate from Grok or the panel becomes a fact only after this seat, or the coordinator, runs the trigger.

The coordinator owns launch, done-files, and the decision. This skill owns the Codex command and the order text. Read `codex exec --help` on the host before the first run. `$CODEX_MODEL` is the model that host lists. Do not pin an example name.

## Command

One input only. Stdin (`- < file`) or one argument with `< /dev/null`. Never both. Pass model, effort, and sandbox on every call. A resumed session uses the config-file defaults.

```sh
# Build. Writes only inside the work folder.
codex exec --sandbox workspace-write -m "$CODEX_MODEL" -c model_reasoning_effort=xhigh \
  -C "$WORKDIR" - < "$WORKDIR/ORDER.txt" > "$WORKDIR/codex.log" 2>&1

# Read-only review or find-check.
codex exec --sandbox read-only -m "$CODEX_MODEL" -c model_reasoning_effort=xhigh \
  -C "$WORKDIR" - < "$WORKDIR/REVIEW.txt" > "$WORKDIR/review.log" 2>&1

# Fix round. Lower effort. Hard limit 900 seconds.
timeout 900 codex exec --sandbox workspace-write -m "$CODEX_MODEL" -c model_reasoning_effort=high \
  -C "$WORKDIR" - < "$WORKDIR/FIX.txt" > "$WORKDIR/fix.log" 2>&1
```

Sandbox values are `read-only` and `workspace-write`. Do not use `danger-full-access`. Tests that open sockets need `-c sandbox_workspace_write.network_access=true`.

The work folder is a copy (`git archive HEAD | tar -x -C "$WORKDIR/tree"`). The shared tree is never that run's writable folder. Write `ANSWER.md` as soon as the edits exist and update it after every check. Read the log header before calling the run started. The answer is the text after the last line that is exactly `codex`, or `ANSWER.md` if the run was cut.

On Windows, `codex.exe` uses the same flags. Quote `-C`. There is no `timeout`: use a job limit or `Start-Process`, and stop by numeric process id.

## Build order

```
TASK <id>. Time limit: 60 minutes. Write ANSWER.md as soon as the edits exist and update it after every check.
BASE: commit <sha>; your tree is ./tree (a copy; the shared repository is out of bounds).
MAY EDIT: <exact files>. Tool caches and files a check generates are not unit files: delete them and name them.
FORBIDDEN: any git write outside ./tree fixtures, any other file, network, deleting, formatting unrelated lines.
GOAL: <one paragraph: user, visible result>.
RULES (numbered, each testable):
 R1 ...
FACTS YOU NEED (quoted from code or an executed call, with file and line): ...
ORDER OF WORK: 1 build; 2 verify the whole tree (tests, lint, mutants); 3 measure the size; 4 if over the
ceiling, make the cut named below and re-run only what the move touches. A size overrun never ends the round
before step 2.
VERIFY: <exact commands with interpreter path and environment>. A run that does not start is repeated once
the invocation is corrected.
TESTS: prove behaviour by executing it. A repository test reads nothing outside the repository. Credential-
shaped test data is written the way the existing tests write it. Tests that start a child process pass a
memory limit and a timeout.
MUTANTS: at most <N>, derived from the diff: for each comparison its neighbours, one per dropped condition,
one per removed reset.
SIZE: ESTIMATE: <current bytes> + <growth per item> = <sum> against <ceiling>.
Above the ceiling: <named moves, in order>.
STOP ONLY IF: <exhaustive list>. Otherwise build every other rule and report the one you could not.
RETURN (ANSWER.md, at most 40 lines): files changed with bytes, each rule -> the test that proves it,
commands run with results, anything not executed and why, assumptions (each one is a finding for the coordinator).
```

## Read-only review

```
REVIEW of <unit>. You may read and execute inside this folder. You change nothing.
Line 1 of your answer: one word, approve or reject.
Then one table, at most 40 lines: finding | the input that triggers it | what you executed | result | in scope?
Tasks (answer each by number; an unanswered task means "not reviewed"):
 1 For which inputs does each rule NOT hold? Execute the three most likely.
 2 Numbers arriving as text: the smallest decimal step beyond each bound, 1e400, NaN, a very long number.
 3 Every "never fails" sentence: a deeply nested input, an oversized input, a lone surrogate.
 4 What does this change break for callers of the functions it touches? List the callers first.
 5 Which sentence of the description is wider than the code?
Scope: <who calls this, which data can reach it>. A finding outside the scope is listed and marked so.
```

## Fix round

```
FIX ROUND <n> of <unit>. 15 minutes. At most these three findings, nothing else:
 F1 <finding> - reproduce first with: <command>. If it does not reproduce, say so and change nothing for it.
A test that asserts the old behaviour of a fixed item moves with the item, exactly there. No other test body
changes. Run the mutant tool's anchor check over the whole spec afterwards.
RETURN: per finding - reproduced yes/no, lines changed, the new test, the commands and results.
```

## Find-check

```
A reader that cannot execute raised the findings below. Your only task: run each trigger on this tree.
Table: finding | exact command | output | reproduces? | survives the validator in front of this function?
No opinion on design. No new findings.
```

## Draft

```
From the code and test results in this folder write: (a) a description of the change for a reader who has
nothing else, (b) a commit message, (c) release notes in plain English. Every sentence must be provable by a
named test or line; list that proof beside it in a separate table. State the former behaviour in words.
Keep accepted limits in one paragraph with the reason each is not a defect. No draft wording, no open
questions inside the texts; open questions go into your summary.
```

Search a draft for the words draft, pending, proposed, unverified, and placeholder before use.
