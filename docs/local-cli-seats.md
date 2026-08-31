<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.8.0-beta.2 | Date: 2026-08-21 -->

# Local Claude, Codex and Grok seats

Official `iot-ai multi-coder` must use the CLIs that already work on this
host for user `iot`. It must not require `GROK_API_KEY` for the Grok
Build TUI, inherit an open stdin pipe, or treat `decision: blocked` as
exit 0.

## What was wrong

| Seat | Failure | Cause |
|---|---|---|
| grok | `GROK_API_KEY missing for user iot` | Restricted PATH preferred system vibe-kit `grok` over the user-local Grok Build TUI (`~/.local/bin/grok`) |
| claude | `provider-binding-mismatch` | Advisory JSON had the model only in `modelUsage`; harness left `model_served` empty |
| codex | timeout ~900s, empty body | `codex exec` waited forever on inherited stdin |

Exit 0 with `decision: blocked` is not a pass.

## What now

- Pin user-local binaries first (`~/.local/bin`, `~/.grok/bin`).
- Close stdin (empty EOF) unless the prompt was moved to stdin.
- Parse Claude `modelUsage.canonicalModel`, Codex `model:` banner, and Grok JSON `text` + `modelUsage`.
- Grok Build flag order is `grok -p "<prompt>" --output-format json` (`-p` consumes the next token).
- Official `iot-ai` runs as the Suite Unix user. Claude Code login must exist for that same user (`claudeAiOauth` in `~/.claude/.credentials.json`); a root-only login is not a seat.
- Treat `GROK_API_KEY` / "API key required" as auth failure only on the grok seat. A Claude or Codex plan that *cites* that defect is not an auth fail.
- `iot-ai multi-coder run` returns exit 1 when the decision is blocked.

Live proof as the Suite Unix user against this source snapshot: Claude subscription bound, Codex `gpt-5.6-sol`, Grok `grok-4.6-build`. Package lockstep on this tree remains `6.8.0-beta.1`.
