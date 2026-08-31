# MC-GPT Deep MNCG and OpenWiki Benchmark

Status: `STARTED_PRE_REGISTERED`  
Benchmark ID: `mcgpt-mncg-openwiki-2026-01`  
Provider trials executed: `0`  
Performance claim allowed: `false`  
Production claim: `false`

This benchmark evaluates the MC-GPT Minimum Necessary Change Gate, a short YAGNI control, a pinned Ponytail treatment, and a pinned OpenWiki knowledge treatment under paired, exact-model, isolated conditions.

## Frozen revisions

| Component | Revision |
|---|---|
| MC-GPT public main baseline | `62fc203aa931a8abce2e6163881bd014f6f84159` |
| MC-GPT PR #14 MNCG treatment | `117d0489047b434a2710c57a83c4a7fe53eb7c5d` |
| OpenWiki | `58a1358e1f7d5b883db7405f56dcbdac3c4d7fe5` |
| Ponytail | `2ed6c52c9d7e5e56942508591085fd45dea277d3` |
| DeepSWE task definitions | `6db64a40f3318d8659238ff34a8cc4b491c49205` |

PR #14 is an open draft at this freeze. The benchmark branch is stacked on that exact head and must not be described as merged into `main`.

## Experimental arms

- `A_BASELINE`
- `B_SIMPLE_YAGNI`
- `C_PONYTAIL_PINNED`
- `D_MNCG`
- `E_OPENWIKI`
- `F_MNCG_OPENWIKI`

## Local validation

```bash
python3 benchmarks/deep-mncg-openwiki/scripts/validate_benchmark.py benchmarks/deep-mncg-openwiki
python3 -m unittest discover -s benchmarks/deep-mncg-openwiki/tests -p 'test_*.py'
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

The repository workflow validates contracts only. It does not call providers, consume paid quota, expose credentials, or publish performance claims.
