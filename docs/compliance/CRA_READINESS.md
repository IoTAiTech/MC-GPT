<!--
Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Version: 6.7.0-beta.4 | Date: 2026-08-08
SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
-->
# Cyber Resilience Act readiness

## Baseline

Regulation (EU) 2024/2847 applies generally from 11 December 2027. Article 14 reporting obligations for actively exploited vulnerabilities and severe incidents apply from 11 September 2026. This repository provides engineering readiness; applicability, product category and conformity route require release-specific qualified review.

Official source: https://eur-lex.europa.eu/eli/reg/2024/2847/2024-11-20/eng

## Implemented engineering controls

- secure-by-default cloud-off configuration;
- exact package hashes and sealed manifests;
- PEP 668-safe isolated environments;
- transaction-backed clean install and normal rollback;
- SBOM and third-party notices;
- vulnerability reporting policy in `SECURITY.md`;
- update and support documentation;
- static security, secret, archive traversal and symlink tests;
- incident evidence preservation and 24/72-hour deadline helper;
- no known-exploitable-vulnerability release claim without evidence.

## Required customer/release records

- manufacturer/economic-operator role;
- supported lifetime and security-update period;
- product cybersecurity risk assessment;
- vulnerability handling process and contact;
- actively exploited vulnerability/severe incident reportability decision;
- coordinated disclosure and corrective-action receipts;
- conformity assessment route where applicable.

The Suite does not claim CRA conformity solely because these controls exist.
