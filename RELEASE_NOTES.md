# IOT-AI Suite 6.8.0-beta.1 / MC-GPT 0.8.0-alpha.7 — Source Preview Notes

`main` is a source snapshot ahead of the latest downloadable Community Preview.

```text
latest tagged download: IOT-AI Suite 6.7.0-beta.6 / MC-GPT 0.8.0-alpha.6
current main source:    IOT-AI Suite 6.8.0-beta.1 / MC-GPT 0.8.0-alpha.7
production_claim:       false
```

## Discoverability and evaluation improvements

- Proof-first README with one product name, one value proposition and one five-minute evaluation path.
- Exact distinction between the tagged download and unreleased `main` source.
- Disposable standard-library authentication fixture with an acceptance-driven rate-limiting task.
- Plan-first SHA-256-verifying community installer for the published Linux evaluation wheel.
- New demo-feedback issue form focused on activation friction and evidence trust.
- Rewritten GitHub Pages landing with corrected SoftwareApplication metadata, a Linux-only public qualification claim, exact release links and UTM-tagged calls to action.
- Search metadata and topics retargeted toward coding-agent orchestration, Git worktrees, parallel coding and review automation.

## Merged onto `main` on 2026-08-31 (still 6.8.0-beta.1)

These branches were merged locally, tested, documented and landed on `main`. This is not a new tagged download.

### GitHub Packages
- `ghcr.io/iotaitech/mc-gpt` and `@iotaitech/mc-gpt` publish on every annotated `v*` tag and GitHub Release.
- Python wheels remain on the Releases tab. GitHub Packages does not host wheels.
- First GHCR/npm publish is private until an org owner sets visibility to public once.

### Minimum Necessary Change Gate
- Planning must pick the first sufficient rung: no change, reuse, stdlib, native platform, approved dependency, smallest local edit, then new code.
- Public schemas, skill `iot-ai-minimum-change`, runtime `src/iot_ai/minimum_change.py`, and operator guide `docs/minimum-necessary-change-gate.md`.

### Local Claude, Codex and Grok seats
- Official `iot-ai multi-coder` pins user-local CLIs (`~/.local/bin`, then `~/.grok/bin`).
- Codex `exec` receives empty stdin unless the prompt was moved to stdin.
- Served-model parsing: Claude `modelUsage.canonicalModel`, Codex `model:` banner, Grok JSON `text` plus `modelUsage`.
- `decision: blocked` returns exit 1. Plan-stage floor is `--quorum` (default 2).
- `GROK_API_KEY` is an auth failure only on the grok seat.

### New and notable CLI options
- `iot-ai multi-coder run --quorum N --plan --providers claude,codex,grok`
- `iot-ai github-analyze <owner/name|url>… [--offline-json PATH] [--no-network]`
- Grok Build: `grok -p "<prompt>" --output-format json`

### Benchmarks and research
- `benchmarks/minimum-change/` and `benchmarks/minimum-change-v2/`
- `benchmarks/deep-mncg-openwiki/`
- OpenWiki assessment and pinned upstream audit workflow

See [CHANGELOG.md](CHANGELOG.md) `[Unreleased]`.

## Current source-candidate evidence

`FINAL_TEST_SUMMARY.json` is a checked-in historical summary (220 pytest / 220 unittest at that revision). The 2026-08-31 merge tree measured **335 pytest passed, 1 skipped**, unittest discover green, `pytest -W error` green, and the public-boundary / license-header / static-security / brand / no-Arabic / EU AI Act preview gates green. Those later counts apply only to the merge HEAD they were run against.

## Claim boundary

Community Developer Preview. `production_claim: false`.

This is not a production qualification, legal certification, customer PMD acceptance, Windows/macOS on-device qualification or blanket provider-account claim. Commercial and company-internal operational use requires written IoT-AI.Tech terms.
