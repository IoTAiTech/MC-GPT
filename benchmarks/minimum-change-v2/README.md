# MC-GPT Minimum Necessary Change Paired Benchmark v1

**Author:** Dr.-Ing. Babak Sorkhpour, with AI assistance  
**Status:** protocol and deterministic analysis harness implemented; live provider runs not started  
**Production claim:** false

## Objective

Measure whether MC-GPT's structured Minimum Necessary Change Gate reduces change surface, dependencies, tokens, cost, time, and rework **without reducing correctness or safety**.

The benchmark does not copy Ponytail runtime or prompt files. The optional Ponytail arm is disabled until exact upstream provenance, licence notice, integration method, and isolation controls are recorded.

## Arms

1. `baseline` — MC-GPT without an explicit minimum-change instruction.
2. `simple-yagni` — the same workflow plus one sentence requesting the simplest sufficient change.
3. `mcgpt-minimum-change` — the native structured, evidence-bound gate.
4. `ponytail-experimental` — disabled optional external arm.

## Corpus

`task-corpus.json` defines 24 public-data tasks across all seven decision rungs:

```text
necessity
existing capability
standard library
native platform
existing approved dependency
minimal local change
minimum new code
```

The corpus includes security, privacy, recovery, database, UI, IAM, Meeting, release, provider, and observability cases. Each task has explicit acceptance criteria, an expected rung, a risk class, and a public-data-only flag.

Task identifiers are opaque strings. Scheduling, synthetic self-tests, receipts, and analysis never derive semantics or ordering from an identifier's spelling.

The current corpus is a protocol corpus. Runnable fixture repositories must be frozen and hashed before live provider execution.

## Experimental design

- fresh isolated workspace for every run;
- no cross-arm context reuse;
- deterministic balanced arm order;
- five repetitions per task, arm, and provider;
- requested and served model identities recorded separately;
- failures, timeouts, blocks, and budget exhaustion included in intention-to-treat reporting;
- exact source and fixture revisions required;
- one immutable result receipt per scheduled run.

Planned provider surfaces:

```text
OpenAI Codex CLI
Anthropic Claude Code
Google Gemini CLI
xAI Grok CLI
Ollama exact-model seat
```

A provider is not qualified merely because its CLI is installed. Live readiness, authentication outcome, requested model, served model, and substantive contribution must be recorded.

## Hard gates

Efficiency is evaluated only after all of these pass:

- complete acceptance criteria;
- post-change tests;
- security and privacy controls;
- independent review;
- post-tree and diff binding;
- no secret/private-data disclosure;
- no unapproved runtime dependency;
- verified rollback or no-change rationale.

One failed hard gate blocks a savings claim for the affected comparison.

## Metrics

Primary:

- hard-gate pass rate;
- source lines added;
- new runtime dependencies.

Secondary:

- files added, modified, and deleted;
- input, output, and reasoning tokens;
- provider cost;
- wall-clock time;
- repair iterations;
- tests and review findings;
- timeout and blocked rates;
- change-budget variance.

## Statistical rules

- pair by task, provider, served model, and repetition;
- minimum 20 complete pairs per comparison;
- 10,000 deterministic bootstrap iterations;
- median paired percentage delta and IQR;
- two-sided sign test;
- failures reported separately, never silently dropped;
- no public savings claim when hard-gate performance is inferior;
- no public savings claim when model identity is unverified;
- synthetic data never authorizes a public claim.

## Commands

Validate the protocol and corpus:

```bash
python benchmarks/minimum-change-v2/benchmark.py validate
```

Generate the full deterministic schedule:

```bash
python benchmarks/minimum-change-v2/benchmark.py schedule \
  --output benchmark-output/schedule.json
```

Generate one-provider schedule:

```bash
python benchmarks/minimum-change-v2/benchmark.py schedule \
  --providers openai-codex \
  --output benchmark-output/codex-schedule.json
```

Run the deterministic synthetic self-test:

```bash
python benchmarks/minimum-change-v2/benchmark.py selftest \
  --output-dir benchmark-output/selftest
```

Validate real JSONL receipts:

```bash
python benchmarks/minimum-change-v2/benchmark.py validate-results \
  --schedule benchmark-output/schedule.json \
  --results benchmark-output/results.jsonl
```

Analyse real results:

```bash
python benchmarks/minimum-change-v2/benchmark.py analyse \
  --schedule benchmark-output/schedule.json \
  --results benchmark-output/results.jsonl \
  --output benchmark-output/analysis.json
```

## Current claim boundary

```yaml
protocol_validated: true
synthetic_selftest: true
live_provider_runs: not-started
mcgpt_loc_savings: not-measured
mcgpt_token_savings: not-measured
mcgpt_cost_savings: not-measured
mcgpt_time_savings: not-measured
production_claim: false
```
