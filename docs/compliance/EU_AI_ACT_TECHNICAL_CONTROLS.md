<!--
Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Version: 6.7.0-beta.4 | Date: 2026-08-08
SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
-->
# EU AI Act technical controls

## Scope and claim boundary

This document maps technical controls in IOT-AI Suite v6.7.0-beta.4 to the declared Community Developer Preview purpose: supervised software-engineering collaboration. It is not legal advice, certification, CE marking, a conformity assessment, or a blanket conclusion for customer deployments.

Legal baseline:

- Regulation (EU) 2024/1689 and the current consolidated legal baseline;
- Commission Guidelines on Transparency of AI-Generated Content, published 20 July 2026;
- Article 50 applies from 2 August 2026;
- Commission guidance on prohibited practices and GPAI obligations.

Official sources:

- https://digital-strategy.ec.europa.eu/en/policies/guidelines-transparency-ai-generated-content
- https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content
- https://digital-strategy.ec.europa.eu/en/library/commission-publishes-guidelines-prohibited-artificial-intelligence-ai-practices-defined-ai-act
- https://digital-strategy.ec.europa.eu/en/policies/contents-code-gpai
- https://digital-strategy.ec.europa.eu/en/policies/guidelines-gpai-providers

## Control map

| Area | Runtime control | Evidence | Release behaviour |
|---|---|---|---|
| Actor role and intended purpose | versioned AI system card and declared purpose | system-card digest | missing assessment blocks external deployment claim |
| Article 4 literacy | role-specific curriculum/receipt contract | pseudonymous receipt | missing receipt reported; no blanket compliance claim |
| Article 5 prohibited practices | pre-dispatch deny screen | hash-chained finding receipt | prohibited purpose blocks provider, tool and task dispatch |
| Article 50 interaction notice | first-interaction disclosure profile | disclosure receipt | missing human-facing disclosure blocks public interactive release |
| Article 50 content provenance | machine-readable sidecar/embedded metadata | output digest + provenance receipt | required publication/export is blocked if marking fails |
| Human oversight | L0–L3 authority, explicit approval, stop and rollback | task/lease/audit records | AI evidence cannot be rewritten by human override |
| Provider/model provenance | requested/served model and supplier dossier | provider receipt | unknown or drifted model cannot satisfy required seat |
| Post-market/incident | diagnostic, audit and incident record | immutable evidence digest | incident freezes source evidence and triggers human routing |
| High-risk use | deployment-specific classification gate | signed assessment record | high-risk mode defaults to blocked-until-classified |

## No false consensus

Command success, meeting completion, plan acceptance, founder approval and execution authorisation are separate machine-readable states. Empty, timed-out, quota-blocked, unauthenticated or meta-only seats never count as substantive acceptance. Required roles must accept the same plan digest.

## Customer deployment

Enterprise customers must complete a deployment-specific role, purpose, sector, data, model, tool and risk assessment. A Community test result cannot be reused as proof for a customer, industrial, employment, medical, critical-infrastructure or other high-risk use case.
