---
name: iot-ai-seat-grok
description: Judge a design or a diff with tool-less Grok. Use when the prompt must contain every source and Grok must not open files or call tools.
id: iot-ai-seat-grok
version: 1.0.0
category: general
license: LicenseRef-PolyForm-Noncommercial-1.0.0
---
# iot-ai-seat-grok

Author: Dr. Babak Sorkhpour with AI assistance  
Version: 1.0.0 | Date: 2026-10-10

Grok reads. It produces candidates, not measurements. A finding becomes a fact only after the Codex find-check, or the coordinator, runs its trigger.

```sh
grok -m grok-4.7 --reasoning-effort xhigh --prompt-file "$WORKDIR/grok_prompt.txt" \
  --verbatim --no-subagents --no-plan --tools '' --max-turns 4 \
  > "$WORKDIR/grok.txt" 2> "$WORKDIR/grok.err"
```

Always name the model. The client default may be older. Open the prompt with `Answer now in this reply. No plan, no tools.` Inline every source. A prompt that says "read the file at this path" is narration, not a review. Allow up to an hour at `xhigh`. Record seconds and reasoning tokens. A reply after a few seconds, or a bare verdict word, is not reviewed.

Flags on this host's `grok --help`: `--model`, `--reasoning-effort`, `--prompt-file`, `--verbatim`, `--no-subagents`, `--no-plan`, `--tools`, `--max-turns`. Re-check `--help` after a client upgrade.

On Windows the same flags apply. Quote the prompt-file path.

## Diff read

```
Answer now in this reply. No plan, no tools. Today is <date>.
You review the diff below against the numbered rules. Facts outside the diff that you need are listed under
FACTS; treat them as true.
For EACH rule write one walk line: rule id | the input you walked | what the changed code does with it | holds?
A reply without the walk is not a review.
Then at most five findings, each as: the exact input -> the wrong result -> the line.
Last line: approve or reject.
RULES ...
FACTS (who validates what the new lines read; what callers can pass; what an exception does) ...
DIFF ...
```

Read the answer from the top. A reply that skips the walk is "not reviewed". The coordinator sends each finding to `iot-ai-seat-codex` find-check before it becomes a fix.
