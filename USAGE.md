# Usage

Community Developer Preview. `production_claim: false`.  
Licence: [PolyForm Noncommercial 1.0.0](LICENSE). Commercial use needs a [written IoT-AI.Tech licence](COMMERCIAL.md).

## After install

```bash
iot-ai status
iot-ai "Finish the selected work, use every eligible coder, meet on failures, repair, retest and report."
iot-ai "Review the remaining work and show one brief report; do not execute."
```

Read-only review language stays read-only. Words such as *finish*, *repair* or *complete* request a bounded run to a terminal state. Public release, production deploy and Founder Accept stay human gates.

## Expert overrides (optional)

```bash
iot-ai meeting seat-plan --seats all-coders+ollama-clouds
iot-ai tasks run --all --mode hybrid --plan
iot-ai multi-coder run --task-id <task-id> --plan
```

`--plan` is preview only. A run without `--plan` executes.

## What you may do under Community

| Allowed without a commercial licence | Needs a written commercial licence |
|---|---|
| Personal use, study, hobby and testing | Company-internal operational or production use |
| Noncommercial academic or independent research | Paid consulting, integration or support |
| Modify the source and keep a private fork | Managed hosting or Software-as-a-Service |
| Share noncommercial copies with the licence and notices | Resale, bundling or commercial redistribution |
| Publish research with attribution | Commercial forks, customer deployments, Enterprise / PMD connector |

GitHub's Fork button is a platform feature. It does not grant commercial rights.

Full terms: [LICENSE](LICENSE) · [NOTICE](NOTICE) · [licensing and forks](docs/licensing-and-forks.md) · contact `info@iot-ai.tech`.
