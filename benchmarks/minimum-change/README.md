<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 1.0.0 | Date: 2026-08-29 -->

# Minimum Necessary Change Gate benchmark

This deterministic selftest checks gate semantics across twelve representative engineering tasks. It verifies that the first evidence-sufficient rung is selected and that an unknown earlier rung is never treated as rejection.

```bash
python3 benchmarks/minimum-change/evaluate.py
```

It performs zero provider calls and does **not** measure or claim code, token, cost, time, security, or production savings. Those claims require a comparable A/B run with the same task, model, provider route, environment, acceptance criteria, deterministic post-change tests, independent review, and a receipt bound to both revisions.
