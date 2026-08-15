# Inbound GitHub analysis

Community Developer Preview. `production_claim: false`.

When someone sends GitHub repositories to MC-GPT, the Suite judges them. It does not install them.

## Four axes

1. Technical — what it does and whether it fits our architecture.
2. Commercial — SaaS vs source-available, dual-license, and our PolyForm / commercial split.
3. License — SPDX from the real license record. MIT is never inferred.
4. Relevance — whether the idea helps this product without harming it.

## If relevant

Rewrite the useful pattern, model, or idea in our files under our license. Do not copy their source or their license text onto ours.

## Hard line

- No dependency: no pip, npm, vendor tree, submodule, or skill install of their repository.
- No illegal licensing: no unlicensed code, no vendored copyleft, no relicensing Community away from PolyForm Noncommercial 1.0.0.

## Command

```bash
iot-ai github-analyze https://github.com/example/tool
iot-ai github-analyze --offline-json records.json --no-network
```

Policy: [`LICENSE_POLICY.json`](../LICENSE_POLICY.json) · fleet rule `GITHUB_ANALYSIS_NO_DEPENDENCY_v1`.
