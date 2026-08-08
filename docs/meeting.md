<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.7.0-beta.5 | Date: 2026-08-08 -->
# Meeting

Meeting is the governed decision layer used automatically for planning, disagreement, failure diagnosis, repair selection and final hard-judge review.

A successful command is not an accepted meeting. Acceptance requires substantive seats, exact served-model receipts, quorum, critique, synthesis, one frozen plan digest and required-role acceptance. One available model is reported as `single-engine-or-incomplete`, never Multi-Coder consensus.

Normal users do not need to start meetings manually:

```bash
iot-ai "Fix the task; hold a meeting on every failure and continue until terminal."
```

Expert inspection remains available:

```bash
iot-ai meeting show <meeting-id> --view brief
iot-ai meeting show <meeting-id> --view full
iot-ai meeting report --classification restricted --view full --format bundle --output meetings.zip
```
