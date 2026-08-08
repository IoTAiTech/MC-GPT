<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.7.0-beta.5 | Date: 2026-08-08 -->
# Autonomous run reporting

Every terminal or bounded-blocked run creates:

```text
AUTONOMOUS_RUN_REPORT.json
AUTONOMOUS_RUN_REPORT.md
TASKS.csv
PROVIDERS.csv
ITERATIONS.csv
AUTONOMOUS_RUN_REPORT.xlsx
MANIFEST.json
```

The Task table includes backend authority, initial/final state, acceptance score, Meeting, Multi-Coder, tests, repairs, blocker/next actor and evidence. Provider rows preserve exact requested/served model identity and failure class. Iterations show every plan/repair loop and failure fingerprint.
