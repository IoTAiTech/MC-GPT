<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 1.0.1 | Date: 2026-08-29 -->

# MC-GPT quickstart demo fixture

This disposable, standard-library-only repository fragment evaluates the MC-GPT workflow without exposing customer code.

## Baseline

```bash
cd examples/quickstart-demo
python3 -m unittest discover -s tests -v
```

Expected baseline: three tests pass.

## Plan-only evaluation

```bash
iot-ai \
  "Read TASK.md. Inspect the fixture, preserve all nine acceptance criteria, produce a complete implementation and test plan, name the writer and independent review roles, and do not execute."
```

## Governed implementation

Run only after at least one supported provider is configured:

```bash
iot-ai \
  "Implement TASK.md. Use one authorised writer and independent review, test the post-change tree, repair bounded failures and return one complete evidence table."
```

The fixture includes `pyproject.toml`, allowing the runtime to detect this deterministic post-change test:

```bash
python3 -m pytest -q
```

## Review

The implementation is performed in an isolated writer worktree. Read `workers[].path` from the generated worktree record, then inspect and test that path—not the untouched checkout used to start the command.

Check:

- all nine acceptance criteria;
- separate writer and reviewer authority;
- deterministic post-change tests;
- requested and actually served models recorded separately;
- complete remaining-work and blocker disclosure;
- absence of private paths or credentials in public evidence.

Send results through the repository's `Demo feedback` issue template. Never attach unrestricted logs or secrets.
