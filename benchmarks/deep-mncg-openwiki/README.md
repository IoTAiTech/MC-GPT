# MC-GPT Deep MNCG and OpenWiki Benchmark

Status: `STARTED_PRE_REGISTERED_AMENDED_BEFORE_PROVIDER_CALLS`  
Benchmark ID: `mcgpt-mncg-openwiki-2026-02`  
Provider trials executed: `0`  
Performance claim allowed: `false`  
Production claim: `false`

This benchmark evaluates the MC-GPT Minimum Necessary Change Gate, a short YAGNI control, a pinned Ponytail treatment, and pinned OpenWiki repository knowledge under paired, exact-model, isolated conditions.

## Pre-execution amendment

The first preregistration froze the former public `main` and PR 14 treatment as different source commits. PR 17 later integrated MNCG and the benchmark work into protected `main` before any provider trial was executed. Keeping the split-source comparison would confound the treatment with unrelated source drift.

`AMENDMENT_2026-08-31.json` therefore re-baselines every arm on one exact source commit and tree:

```text
commit: 51cb72e27d013d14ef2e3435ed84a3514b33c170
tree:   81e3b88bb0005cad19b58e016ac3b50b5e8443cd
```

Only the registered treatment bundle may differ within a paired block. Git history preserves the original preregistration and run matrix. No result was excluded or rewritten because provider execution had not started.

## Frozen upstream revisions

| Component | Revision |
|---|---|
| MC-GPT common source | `51cb72e27d013d14ef2e3435ed84a3514b33c170` |
| MC-GPT common tree | `81e3b88bb0005cad19b58e016ac3b50b5e8443cd` |
| OpenWiki sparse claim reconciliation | `58a1358e1f7d5b883db7405f56dcbdac3c4d7fe5` |
| Ponytail | `2ed6c52c9d7e5e56942508591085fd45dea277d3` |
| DeepSWE task definitions | `6db64a40f3318d8659238ff34a8cc4b491c49205` |

## Experimental arms

- `A_BASELINE`
- `B_SIMPLE_YAGNI`
- `C_PONYTAIL_PINNED`
- `D_MNCG`
- `E_OPENWIKI`
- `F_MNCG_OPENWIKI`

## Contract validation

```bash
python3 benchmarks/deep-mncg-openwiki/scripts/validate_benchmark.py \
  benchmarks/deep-mncg-openwiki
python3 -m unittest discover \
  -s benchmarks/deep-mncg-openwiki/tests \
  -p 'test_*.py'
```

## Trial planning

Create a private, untracked `MODELS.local.json` from `MODELS.example.json`. Enable only routes that provide exact `model_requested`, provider-emitted `model_served`, and a qualification receipt digest.

```bash
python3 benchmarks/deep-mncg-openwiki/scripts/plan_trials.py \
  --root benchmarks/deep-mncg-openwiki \
  --stage smoke \
  --models /secure/path/MODELS.local.json \
  --output /secure/results/smoke-plan
```

The repository workflows validate contracts and the pinned OpenWiki source only. They do not call providers, consume paid quota, expose credentials, or publish performance claims. The next execution gate remains a maximum 72-trial smoke stage after at least two exact provider routes have immutable qualification receipts.
