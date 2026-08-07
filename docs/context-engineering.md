<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.6.0-beta.3 | Date: 2026-08-06 -->

# Context Engineering

Context is a typed, inspectable manifest—not an unbounded chat transcript.

## Block types

- goal contract;
- specialist role contract;
- execution-node contract;
- dependency result;
- validated knowledge artifact;
- evidence reference;
- previous failure summary;
- human decision or approval receipt.

Each block records source, privacy class, relevance, token estimate, SHA-256, inclusion reason, exclusion reason and whether the original payload was compacted.

## Privacy

| Class | Cloud egress |
|---|---|
| D0 public | allowed after secret scan |
| D1 internal | policy-controlled and sanitised |
| D2 confidential | protected-store hash reference only |
| D3 secret/customer-restricted | denied |

A D2/D3 goal itself blocks cloud dispatch. A separate, reviewed D0/D1 derivative must be created for any external consultation.

## Token and compaction policy

- reserve output capacity before selecting input blocks;
- include mandatory contracts first;
- rank optional blocks by relevance;
- never silently remove the middle of history;
- store full payload outside the context window;
- put hash, token count, available keys and protected location in the compacted block;
- expose selected and excluded blocks in diagnostics.

## Quality metrics

```yaml
context_relevance_precision:
evidence_coverage:
context_compaction_ratio:
silent_truncation_count: 0
private_egress_findings: 0
repeated_context_rate:
tokens_per_accepted_result:
```
