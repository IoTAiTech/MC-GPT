<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.6.0-beta.3 | Date: 2026-08-06 -->

# Diagnostics

```bash
iot-ai diagnostics collect --correlation-id <id> --output diagnostics.zip
iot-ai diagnostics validate --bundle diagnostics.zip
iot-ai diagnostics explain --bundle diagnostics.zip
```

Bundles include graph, node, command, model, token/latency, task, test, audit and timeline evidence. Export is sanitized; protected raw evidence remains local.
