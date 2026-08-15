# Usage

Community Developer Preview. `production_claim: false`.  
Licence: [PolyForm Noncommercial 1.0.0](https://github.com/IoTAiTech/MC-GPT/blob/main/LICENSE). Commercial use needs a [written IoT-AI.Tech licence](https://github.com/IoTAiTech/MC-GPT/blob/main/COMMERCIAL.md).

Canonical copy: [USAGE.md](https://github.com/IoTAiTech/MC-GPT/blob/main/USAGE.md) in the repository root.

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
iot-ai github-analyze https://github.com/example/tool
```

`--plan` is preview only. A run without `--plan` executes.

`github-analyze` judges technical fit, commercial terms, license, and relevance. If a repo is relevant, MC-GPT may reuse only the **pattern, model, or idea** as our own rewrite. It never adds that repository as a dependency and never takes an illegal license.

## What you may do under Community

| Allowed without a commercial licence | Needs a written commercial licence |
|---|---|
| Personal use, study, hobby and testing | Company-internal operational or production use |
| Noncommercial academic or independent research | Paid consulting, integration or support |
| Modify the source and keep a private fork | Managed hosting or Software-as-a-Service |
| Share noncommercial copies with the licence and notices | Resale, bundling or commercial redistribution |
| Publish research with attribution | Commercial forks, customer deployments, Enterprise / PMD connector |

GitHub's Fork button is a platform feature. It does not grant commercial rights.

Full terms: [LICENSE](https://github.com/IoTAiTech/MC-GPT/blob/main/LICENSE) · [NOTICE](https://github.com/IoTAiTech/MC-GPT/blob/main/NOTICE) · [licensing and forks](licensing-and-forks.md) · contact `info@iot-ai.tech`.
