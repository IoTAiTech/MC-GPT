# ADR: one runtime settings authority and one skill router

Status: Accepted
Date: 2026-09-03
Author: Dr.-Ing. Babak Sorkhpour, with AI assistance

## Decision

Extend `settings.py`. Do not create a second settings store. Discover skills
through one registry and one router for every engine.

Garden skills from ConardLi/garden-skills@aaf9a82 (MIT) are derived, data-only,
reference-only adapters. No submodule, no package dependency, no automatic
network pull, no automatic JS execution. MC-GPT remains PolyForm Noncommercial
1.0.0.
