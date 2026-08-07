<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.7.0-beta.3 | Date: 2026-08-06 -->

# Meeting Engine

A meeting is a governed execution-graph template, not a free-form chat room. Required phases are knowledge coverage, specialist role binding, independent opinions, blind challenge, layered fan-in, one frozen plan digest and exact-digest acceptance.

A successful meeting must include a direct answer, 5W1H, architecture/plan, KPI/SLA, ten use cases, ten test cases, ten failure cases, risks, disagreements, missing evidence and a substantive acceptance matrix.

## Seat selectors

| Selector | Meaning |
|---|---|
| `auto` | Bounded policy selection; reserves one Ollama Cloud seat when configured |
| `all-coders` | All enabled coder CLI families |
| `ollama-clouds` | Every discovered model-specific Ollama Cloud seat |
| `all-coders+ollama-clouds` | All enabled coders plus all discovered Ollama Cloud models |
| comma list | Exact requested seats; first-class Ollama omission is blocked unless explicitly excluded |

```bash
iot-ai meeting seat-plan --seats all-coders+ollama-clouds

iot-ai meeting start \
  --topic "Review the dashboard architecture" \
  --seats all-coders+ollama-clouds \
  --quorum 3 --depth ultra --effort xhigh --execute
```

Compatibility syntax:

```bash
iot-ai-meeting --max-parallel ask all coder and ollama clouds only review the dashboard architecture
```

The phrase resolves to `all-coders+ollama-clouds`; it is not interpreted as the old four-coder list.

## Ollama inclusion rule

When cloud access and first-class Ollama are enabled:

- `auto` reserves at least one Ollama Cloud seat within the edition limit;
- `all-coders+ollama-clouds` requests every configured coder and exact discovered cloud model;
- a literal `claude,codex,gemini,grok` list is blocked because it would reproduce the silent omission defect;
- intentional omission requires `--exclude-ollama` and remains in the seat-plan receipt;
- if `all-coders+ollama-clouds` is requested but no Ollama Cloud seat can be discovered, the meeting blocks unless `--allow-missing-ollama` is explicitly supplied.

The seat plan is generated before provider dispatch and reports candidate readiness without treating static installation as live readiness.

## Acceptance semantics

```text
command_execution_status = pass
≠ meeting_status = accepted
≠ founder_approval
≠ task execution authority
```

Required gates include:

- all requested seats are accounted for;
- empty, failed, meta-only and model-unverified outputs are unsatisfied;
- every substantive seat performs final review;
- required reviewers accept the exact same plan digest;
- requested and served model receipts are present;
- 10/10/10 cases and KPI/SLA artifacts exist.

`iot-ai meeting show <meeting-id>` includes:

```yaml
seat_plan:
seat_coverage:
  requested:
  attempted:
  substantive:
  unsatisfied:
  ollama_requested:
  ollama_attempted:
  ollama_substantive:
  ollama_omitted:
```

## Privacy and cost

Meeting prompts pass the privacy gate before cloud egress. The seat plan itself does not spend provider quota. Live calls occur only when the meeting is run. Local Ollama is not included by the `ollama-clouds` selector.
