# Host-selected test execution for the agentic graph

Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Version: 1.0.0 | Date: 2026-09-05

## What changed

The `run_goal(..., execute=True)` Python API requires a `HostTestRunner`.
Planning calls (`execute=False`) do not require it. A missing runner returns
`host-test-runner-required` before provider dispatch or task creation. The
existing CLI task pipeline and its separate multi-coder runner are not silently
rerouted to this API. This document does not claim all execution surfaces share
one implementation or that live PMD integration has been qualified.

The graph no longer treats a model-generated `tests: [{decision: pass}]` list
as executed verification. A trusted host adapter selects the commands and the
source inventory. The runner observes actual child-process exit codes, writes
private receipts, and persists command results in the existing Suite test table.
Final audit and completion reread the evidence and current task/source binding.
Failed execution keeps the task in `needs-work` and the meeting in `needs-review`;
a successful planning discussion alone cannot produce technical completion.

## Host integration example

Use an already approved isolated checkout with the product and test dependencies
installed. The following is host-owned adapter code, not a model-callable tool
for choosing arbitrary commands or silently trusting repository configuration:

```python
from pathlib import Path
import sys

from iot_ai.agentic import run_goal
from iot_ai.test_execution_evidence import CheckCommand, HostTestRunner, source_digest

checkout = Path.cwd()
reviewed_inputs = ["src/example.py", "tests/test_example.py", "pyproject.toml"]
runner = HostTestRunner(
    cwd=checkout,
    commands=[CheckCommand((sys.executable, "-I", "-m", "pytest", "-q"), 120)],
    current_source_digest=lambda: source_digest(checkout, reviewed_inputs),
)
result = run_goal(
    Path.home(),
    "Implement the approved example change and verify its acceptance criteria",
    execute=True,
    test_runner=runner,
)
```

The example paths and goal must correspond to an actual reviewed project and
scope. Include every relevant source, test, fixture, configuration and lockfile
in the inventory; an omitted input is not covered by its digest. Use the existing
authenticated adapter and revision-bound assignment for ProductX/PMD work. Do not
substitute the standalone Suite ledger for another product's task authority.

## Evidence and trust limits

- The metrics count executed host commands, not individual framework test cases.
  A command printing a success count cannot override its nonzero process exit.
- The configured checks must actually cover the acceptance criteria. A trivial
  command that exits zero is not proof of product quality.
- Source, profile, task revision, acceptance and run are bound to the receipt.
  Changing source after a successful check invalidates completion evidence.
- Executables are pinned; commands run without a shell and without inherited
  provider credentials or PYTHONPATH. Output and execution time are bounded.
- These precautions are not a filesystem or network sandbox. Run untrusted tests
  in a separately managed container/VM/OS sandbox that cannot access credentials,
  the host, or the authoritative ledger. A compromised host process/database is
  outside this in-process trust boundary.
- Ordinary POSIX children in the runner-created process group are cleaned up.
  Cross-platform descendant containment requires the external sandbox. Detached
  descendants are not proven contained by this primitive.
- An evidence handle is issued in-process and is not a signing key, a lease, or
  a remotely verifiable attestation. After restart, recapture or use a separately
  reviewed external-verifier integration; do not deserialize a dictionary into
  trusted evidence.
- Raw commands and output logs remain private. Public summaries contain digests,
  typed results and counts, not local paths, credentials or raw tracebacks.

This correction closes the model-assertion boundary for this graph. It is not a
production readiness certificate, a provider benchmark or an Enterprise release.
