<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Document version: 1.1.0 | Suite source baseline: 6.8.0-beta.1 | Date: 2026-08-31 -->

# Local Claude, Codex, Grok and Gemini seat qualification

Official `iot-ai multi-coder` must use the CLIs that actually work for the Suite Unix user. It must not require `GROK_API_KEY` for the Grok Build subscription TUI, inherit an open stdin pipe, or treat `decision: blocked` as exit code zero.

## Failures corrected in the integrated source

| Seat | Failure | Corrected cause |
|---|---|---|
| grok | `GROK_API_KEY missing` despite an authenticated subscription CLI | Restricted PATH preferred a different system executable over the user-local Grok Build binary. |
| claude | `provider-binding-mismatch` | The model was present in `modelUsage`; the harness did not populate `model_served`. |
| codex | Long timeout with an empty body | `codex exec` waited on inherited stdin. |

Exit code zero with `decision: blocked` is not a pass.

## Current integrated behavior

- Pin user-local binaries first: `~/.local/bin`, then `~/.grok/bin`, then approved system locations.
- Close stdin with an empty EOF unless the prompt was intentionally moved to stdin.
- Parse Claude `modelUsage.canonicalModel`, the Codex `model:` banner, and Grok JSON `text` plus `modelUsage`.
- Invoke Grok Build as `grok -p "<prompt>" --output-format json`; `-p` consumes the following value.
- Run official `iot-ai` commands as the Suite Unix user. A root-only provider login is not a qualified seat for another user.
- Treat `GROK_API_KEY` or `API key required` as an authentication failure only for the Grok seat.
- Return exit code one when the Multi-Coder decision is blocked.
- Use `--quorum` as the plan-stage minimum; unavailable seats remain visible and never become implicit consensus.

## Exact live proof captured for the 2026-08-31 source snapshot

```yaml
claude_subscription_route: bound
codex_model_served: gpt-5.6-sol
grok_model_served: grok-4.6-build
gemini_exact_local_seat: not_proven_by_this_snapshot
suite_source_baseline: 6.8.0-beta.1
mc_gpt_source_baseline: 0.8.0-alpha.7
production_claim: false
```

The Claude route is operationally bound, but this document does not publish an exact Claude model identity. Gemini remains a supported provider family, not a locally qualified seat in this evidence slice. Every material run must still record `model_requested`, provider-emitted `model_served`, authentication outcome, substantive contribution, and the exact qualification receipt.
