<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.8.0-beta.1 | Date: 2026-08-28 -->

# MC-GPT five-minute evaluation

This guide separates the **latest downloadable preview** from the newer source snapshot on `main`:

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
- at least one configured provider CLI only when you move from plan mode to execution.

## Install the tagged wheel

### Option A — pipx

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install \
  https://github.com/IoTAiTech/MC-GPT/releases/download/v6.7.0-beta.6/iot_ai_coder_suite-6.7.0b6-py3-none-any.whl
```

### Option B — verified curl installer

Inspect the script first, then apply it:

```bash
curl -fsSLo /tmp/install-mc-gpt.sh \
  https://raw.githubusercontent.com/IoTAiTech/MC-GPT/main/installers/install-community-preview.sh
less /tmp/install-mc-gpt.sh
sh /tmp/install-mc-gpt.sh
sh /tmp/install-mc-gpt.sh --apply
```

The installer verifies this published wheel SHA-256 before creating a versioned virtual environment:

```text
18a752eddcfa9336152cfe72e8ab320372e021121f89e68dbe086474f8ab2807
```

### Option C — ordinary virtual environment

```bash
python3 -m venv .mc-gpt-venv
.mc-gpt-venv/bin/python -m pip install --upgrade pip
.mc-gpt-venv/bin/python -m pip install \
  https://github.com/IoTAiTech/MC-GPT/releases/download/v6.7.0-beta.6/iot_ai_coder_suite-6.7.0b6-py3-none-any.whl
```

## Verify the installation

```bash
iot-ai --version
iot-ai help
iot-ai status
```

A status report may show provider routes as unavailable. That is an honest readiness result, not an installation failure.

## Run the disposable fixture

```bash
git clone --depth 1 https://github.com/IoTAiTech/MC-GPT.git
cd MC-GPT/examples/quickstart-demo
python3 -m unittest discover -s tests -v
```

The baseline tests must pass before any agent modifies the fixture.

Read the task:

```bash
cat TASK.md
```

Compile a plan without writes or provider spending:

```bash
iot-ai \
  "Read TASK.md. Inspect this disposable fixture, resolve the acceptance criteria, show the exact specialist and provider seats, identify the tests that must run after the change, and do not execute." \
  --plan
```

The plan should identify:

- the current authentication behaviour;
- the requested rate-limit semantics;
- deterministic clock injection;
- post-change tests;
- one writer and independent review roles;
- explicit non-goals and rollback scope.

## Run the governed implementation loop

Only after at least one supported provider route is configured:

```bash
iot-ai \
  "Implement TASK.md in this disposable fixture. Preserve existing behaviour, use one authorised writer and independent review, run all tests on the post-change tree, repair failures within the bounded loop, and return one complete evidence table."
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

## Review the result

Inspect at least:

```bash
git status --short
git diff --stat
git diff
python3 -m unittest discover -s tests -v
iot-ai status --logs
```

The final report should identify the task, acceptance criteria, requested and served models, changed files, post-change test results, repairs, final state, remaining work and evidence locations.

## Send useful feedback

Use the repository's [demo feedback issue form](https://github.com/IoTAiTech/MC-GPT/issues/new?template=demo_feedback.yml). Report:

1. time to first meaningful result;
2. the first unclear setup step;
3. the first point where trust decreased;
4. whether the final report helped review the change;
5. sanitised errors only.

Never paste provider tokens, private hostnames, customer data, personal filesystem paths or unrestricted logs into a public issue.

## Licensing and claim boundary

The Community Developer Preview is source-available under PolyForm Noncommercial 1.0.0. Personal and noncommercial evaluation is permitted under the licence. Company-internal operational use, production, paid services, hosting, resale and customer deployment require written commercial terms.

This evaluation is not a production qualification, security certification, EU AI Act conformity assessment or customer PMD acceptance.
