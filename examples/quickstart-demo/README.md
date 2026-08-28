<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 1.0.0 | Date: 2026-08-28 -->

# MC-GPT quickstart demo fixture

This is a disposable, standard-library-only repository fragment for evaluating the MC-GPT workflow without exposing customer code.

## Baseline

```bash
cd examples/quickstart-demo
python3 -m unittest discover -s tests -v
```

Expected baseline: `3` tests pass.

## Plan-only evaluation

```bash
iot-ai \
  "Read TASK.md. Inspect the fixture, produce a complete implementation and test plan, name the writer and review roles, but do not execute." \
  --plan
```

## Governed implementation

Run only after at least one supported provider is configured:

```bash
iot-ai \
  "Implement TASK.md. Use one authorised writer and independent review, test the post-change tree, repair bounded failures and return one complete evidence table."
```

## What to inspect

- Did the system preserve all eight acceptance criteria?
- Did it keep writer and reviewer authority separate?
- Did it run deterministic post-change tests?
- Did it identify requested and actually served models separately?
- Did the final report state exactly what remains?
- Did any prompt, log or report expose a private path or credential?

Send results through the repository's `Demo feedback` issue template. Never attach unrestricted logs or secrets.
