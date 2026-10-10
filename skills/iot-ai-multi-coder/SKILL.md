---
name: iot-ai-multi-coder
description: Coordinate one writer with a sandboxed Codex seat, tool-less Grok, and a cloud Ollama panel. Use for every multi-seat unit on Linux or Windows.
id: iot-ai-multi-coder
version: 1.2.0
category: general
license: LicenseRef-PolyForm-Noncommercial-1.0.0
---
# iot-ai-multi-coder

Author: Dr. Babak Sorkhpour with AI assistance  
Version: 1.2.0 | Date: 2026-10-10

One coordinator uses three helper seats. An executing seat produces measurements. A read-only seat produces candidates. A candidate becomes a fact only after an executing seat or the coordinator runs its trigger.

`iot-ai multi-coder` remains the receipted suite control surface. There is no `--task-file`. Seat commands and prompt templates live in the seat skills. Read each tool's `--help` on the host before the first run.

| Skill | Owns |
|---|---|
| `iot-ai-seat-codex` | Sandbox command, build, review, fix, find-check, draft |
| `iot-ai-seat-grok` | Tool-less prompt and the diff walk |
| `iot-ai-seat-panel` | Sanitised cloud-model critique |

## Seats

| Seat | Does | Receives | Never receives |
|---|---|---|---|
| Coordinator | Short orders, launch, read compact results, decide, integrate | The unit | — |
| Codex | Build, test, execute a finding, draft text from code | A copied work folder and one order file | Write access to the shared tree, credentials |
| Grok | Read a design or a diff and judge it | One self-contained prompt file | Tools, paths it must open, anything it must fetch |
| Ollama panel | Critique a sanitised description from cloud models | The description and today's date | Code, paths, line numbers, identifiers, customer data, secrets |

Defaults:

- Suite seats when `--providers` is omitted: `claude,codex,grok`. Gemini stays disabled.
- Ollama is cloud-only, on the configured gateway port `11500`. Never host port `11434` and never `ollama run`.
- The suite's single Ollama seat is the largest cloud model (`120b` before `20b`). The design panel may ask the other served cloud models the same sanitised text. Local models are not seats.
- Suite tasks stay in the local task store. A `PMD-REQ-` id does not bind PMD permissions. Only explicit `backend=pmd-api` uses that adapter.
- A seat counts only with a requested model, a served model, and real work. `--plan` and exit 124 with an empty receipt are unsatisfied.

## Launch and wait

Long jobs are detached. The job writes a done-file as its last act. The launcher is its own command, never chained behind `&&`. The Codex line itself is in `iot-ai-seat-codex`.

```sh
#!/usr/bin/env bash
# seat_job.sh WORKDIR ORDERFILE LOG
set -u
W=$1; ORDER=$2; LOG=$3
test -s "$ORDER" || { echo "order missing or empty"; exit 2; }
export TMPDIR="$W/tmp.$$"; mkdir -p "$TMPDIR"
timeout 5400 codex exec --sandbox workspace-write -m "$CODEX_MODEL" -c model_reasoning_effort=xhigh \
  -C "$W" - < "$ORDER" > "$LOG" 2>&1
rc=$?
rm -rf "$TMPDIR"
echo "rc=$rc" > "$W/codex.done"
```

```sh
setsid nohup bash seat_job.sh "$WORKDIR" "$WORKDIR/ORDER.txt" "$WORKDIR/codex.log" \
  > "$WORKDIR/launch.out" 2>&1 < /dev/null &
```

Confirm a launch by the job's own first output, read in a later command. Wait on the done-file or the numeric process id. Never wait on text that the watched output can itself contain. Take the exit status into a variable on the next line. Do not put a heredoc inside an ssh argument: upload a script and run that file. Stop a job by numeric process id after listing its tree, children first. A pattern kill matches your own shell.

Windows: `Start-Process` with redirected stdout, and write `codex.done` from the script. Read `%ERRORLEVEL%` on the next line. A panel lock is a named mutex. Grok uses the same flags as on Linux.

## Capacity and order

Measure one client's memory before multiplying it. Start a seat only when a slot is free and the host is calm (load, disk, free memory, production service health). Test rounds in one stream run one after another. Reads and the panel may run beside them. Check free disk before a build. Use a per-run temporary folder and remove it with the run. Do not copy a whole tree per mutant.

Order for one unit:

1. Inventory what already exists. Read the first screen of every hit.
2. One page of numbered rules. The panel critiques a sanitised copy. Grok walks every rule. At most three design rounds.
3. Codex builds from an order file.
4. Checks on a fresh copy: tests, lint, mutants, secret scan.
5. Grok reads the diff. A Codex read-only seat executes every finding Grok raised.
6. Fix rounds of 15 minutes, at most three findings per job, at most three rounds.
7. One final review. The coordinator integrates. No seat writes the shared tree.

Stop after the second rejected round on the same mechanism and write a smaller unit. A unit above three quarters of the review size limit is split before the next round.

## Reading results

Read a review from the top. A tail is closing remarks only. An incomplete answer is "no result" for what it did not reach. A verdict covers only the subject the prompt named. Execute a finding of the form "the base did X" or "input Y raises Z" before it becomes a rule or a fix. "Description says X, code does Y" is answered first by correcting the description. A count, digest, time, or version enters a message only from a command output of the same turn.

Codex build returns `ANSWER.md` of at most 40 lines. Codex review line 1 is `approve` or `reject`. Grok without a walk line per rule is not a review. The panel answers in at most 200 words and ends with `approve` or `needs-changes`.

## Decision

| Condition | Required |
|---|---|
| Tests and mutants | Green on a fresh copy of the base plus the unit |
| Codex reviewers | A majority approves |
| Panel | Two thirds of the models that answered approve |
| Grok findings | Each fixed, refuted by execution, or recorded as an accepted limit with its reason |
| Deterministic checks | Outrank any model agreement |

The coordinator writes the decision: seats, verdicts, each finding and its disposition, and the digest of the bytes reviewed. A defect inside the unit is fixed, never recorded as a limit. An absent seat is recorded with what covered it. No quota: probe, record the probe, use another model or host, then more rounds plus one reviewer who did not write the order.

## Before every seat call

- The order is final, with facts quoted from code or an executed call.
- It names files, limits, verify commands, and the return format.
- A tool-less prompt is self-contained. A panel prompt is sanitised.
- Model, effort, sandbox, and time limit are on the command line.
- A slot is free, the host is calm, and disk is free.
- The job is detached, with a done-file. The first output is read in a later command.
- After the run: orphans swept, temporary folder gone, result read from the top, findings executed before use.

No credential, key, or personal data in a prompt, log, or answer file. Word review orders as verification of your own code. No seat acts on a live system unless the owner named that action.

## Suite receipt

Linux, as the suite owner, never as root against another user's home:

```sh
PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin" \
  $HOME/.local/bin/iot-ai multi-coder run \
  --task "<secret-free task>" \
  --providers claude,codex,grok \
  --quorum 2 \
  --cwd "<lane-root>"
rc=$?
```

Windows: `where iot-ai`, then `iot-ai multi-coder run --help`. Quote `--cwd`. Persist `%ERRORLEVEL%` on the next line.

Install each skill under `.claude/skills`, `.codex/skills`, `.grok/skills`, and `.agents/skills` in the user home (`%USERPROFILE%` on Windows).
