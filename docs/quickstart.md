<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.8.0-beta.1 | Date: 2026-08-29 -->

# MC-GPT five-minute evaluation

This guide separates the **latest downloadable preview** from the newer source snapshot:

```text
latest tagged download: IOT-AI Suite 6.7.0-beta.6 / MC-GPT 0.8.0-alpha.6
current main source:    IOT-AI Suite 6.8.0-beta.1 / MC-GPT 0.8.0-alpha.7
production_claim:       false
```

Use a disposable repository. Do not start with customer code, credentials, private infrastructure or production data.

## Requirements

- Python 3.11 or newer;
- Git;
- Linux for the currently documented public evaluation path;
- at least one configured provider route only when moving from plan-only inspection to execution.

## Install the tagged wheel

### Option A — pipx

```bash
python3 -m pip install --user pipx
python3 -m pipx install \
  https://github.com/IoTAiTech/MC-GPT/releases/download/v6.7.0-beta.6/iot_ai_coder_suite-6.7.0b6-py3-none-any.whl
```

Verify:

```bash
iot-ai --version
iot-ai help
iot-ai status
```

When the current shell cannot yet find `iot-ai`, inspect the executable location with:

```bash
python3 -m pipx environment
```

### Option B — ordinary virtual environment

```bash
python3 -m venv .mc-gpt-venv
.mc-gpt-venv/bin/python -m pip install --upgrade pip
.mc-gpt-venv/bin/python -m pip install \
  https://github.com/IoTAiTech/MC-GPT/releases/download/v6.7.0-beta.6/iot_ai_coder_suite-6.7.0b6-py3-none-any.whl

.mc-gpt-venv/bin/iot-ai --version
.mc-gpt-venv/bin/iot-ai help
.mc-gpt-venv/bin/iot-ai status
```

Published wheel SHA-256:

```text
18a752eddcfa9336152cfe72e8ab320372e021121f89e68dbe086474f8ab2807
```

For an independent digest check, download the wheel and run:

```bash
python3 - <<'PY'
from pathlib import Path
import hashlib

path = Path("iot_ai_coder_suite-6.7.0b6-py3-none-any.whl")
expected = "18a752eddcfa9336152cfe72e8ab320372e021121f89e68dbe086474f8ab2807"
actual = hashlib.sha256(path.read_bytes()).hexdigest()
print(actual)
raise SystemExit(0 if actual == expected else 1)
PY
```

## Run the disposable fixture

```bash
git clone --depth 1 https://github.com/IoTAiTech/MC-GPT.git
cd MC-GPT/examples/quickstart-demo
python3 -m unittest discover -s tests -v
```

Expected baseline: three tests pass.

Read the nine-criterion task contract:

```bash
cat TASK.md
```

Compile a plan without writes or provider spending:

```bash
iot-ai \
  "Read TASK.md. Inspect this disposable fixture, resolve all nine acceptance criteria, name the writer and independent review roles, identify the exact post-change test command, and do not execute."
```

The plan should identify:

- current authentication behaviour;
- rate-limit semantics;
- deterministic clock injection;
- post-change tests;
- one writer and independent review roles;
- explicit non-goals and rollback scope.

## Run the governed implementation loop

Only after at least one supported provider route is configured:

```bash
iot-ai \
  "Implement TASK.md in this disposable fixture. Preserve existing behaviour, use one authorised writer and independent review, run all tests on the post-change tree, repair bounded failures, and return one complete evidence table."
```

The fixture includes a minimal `pyproject.toml`, so MC-GPT can detect and run:

```bash
python3 -m pytest -q
```

A truthful terminal result is one of:

```text
technical complete / awaiting Founder decision
needs work with exact failed evidence
external or authority blocked with one next actor
cancelled
budget exhausted
```

MC-GPT must not call a zero-eligible run a pass, invent model identity, treat progress as implementation, or silently copy PMD tasks into a second task authority.

## Review the actual writer worktree

MC-GPT writes in an isolated worker path. Do not review the untouched checkout from which the command was launched.

Read the `workers[].path` value from the generated worktree record or final change-binding evidence, then use that exact local path:

```bash
WRITER_WORKTREE="/absolute/path/from-the-local-worktree-record"

git -C "$WRITER_WORKTREE" status --short
git -C "$WRITER_WORKTREE" diff --stat
git -C "$WRITER_WORKTREE" diff
(
  cd "$WRITER_WORKTREE"
  python3 -m pytest -q
)
```

Never publish the local path. A public feedback report should include only sanitised changed-file names, test results and evidence hashes.

The final report should identify the Task, all nine acceptance criteria, requested and served models, changed files, post-change tests, repairs, final state, remaining work and evidence references.

## Send useful feedback

Use the repository's [demo feedback form](https://github.com/IoTAiTech/MC-GPT/issues/new?template=demo_feedback.yml). Report:

1. time to first meaningful result;
2. the first unclear setup step;
3. the first point where trust decreased;
4. whether the final report helped review the change;
5. sanitised errors only.

Never paste provider tokens, private hostnames, customer data, personal filesystem paths or unrestricted logs into a public issue.

## Licensing and claim boundary

The Community Developer Preview is source-available under PolyForm Noncommercial 1.0.0. Personal and noncommercial evaluation is permitted under the licence. Company-internal operational use, production, paid services, hosting, resale and customer deployment require written commercial terms.

This evaluation is not a production qualification, security certification, EU AI Act conformity assessment or customer PMD acceptance.
