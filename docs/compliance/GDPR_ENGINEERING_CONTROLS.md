<!--
Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Version: 6.7.0-beta.3 | Date: 2026-08-06
SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
-->
# GDPR engineering controls

## Purpose

This is a data-protection-by-design engineering map. It does not choose a lawful basis or replace a controller/processor assessment, ROPA, DPIA, DPA or legal advice.

## Defaults

- raw prompts and outputs are not retained by default;
- secrets and D3/customer-restricted content block cloud egress;
- public diagnostics redact credentials, tokens, private network identifiers, internal hostnames, personal paths and customer identifiers;
- public, internal, customer and Enterprise roots are physically separate;
- telemetry stores minimal operational metadata and evidence hashes;
- provider/model calls are receipt-bound without logging raw credentials;
- retention and deletion are adapter/policy controlled rather than hard-coded into the core.

## Customer obligations

Before production, document controller/processor roles, purposes, lawful bases, categories, recipients, transfers, retention, data-subject rights, TOMs, subprocessors, deletion/return, breach handling and DPIA applicability. Special-category data and employee monitoring are blocked until separately authorised and assessed.
