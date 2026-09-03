---
name: garden-gpt-image-2
id: garden-gpt-image-2
description: Derived image-prompt checklist. Reference-only. Host-native execution is owned by iot-ai-image-capability.
version: 1.0.0
category: visual
compatibility: [mc-gpt]
source: third-party-derived
license: MIT
source_commit: aaf9a82f5efd73e87cc0998edc398e75bfc35901
execution_mode: reference-only
---
# garden-gpt-image-2

Derived from ConardLi/garden-skills gpt-image-2 (MIT, commit
aaf9a82f5efd73e87cc0998edc398e75bfc35901). Garden generate.js/edit.js are not
included and must never run automatically.

This adapter is reference-only. Image generation requires the host-native
iot-ai-image-capability path. If that tool is absent, report unavailable.
