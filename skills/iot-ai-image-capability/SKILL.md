---
name: iot-ai-image-capability
id: iot-ai-image-capability
description: Host-native image generation/editing capability status. Never claim an image was generated without an authorized host tool.
version: 1.0.0
category: visual
compatibility: [mc-gpt]
source: packaged
license: LicenseRef-PolyForm-Noncommercial-1.0.0
execution_mode: host-native
derived_from: ConardLi/garden-skills gpt-image-2 (MIT, commit aaf9a82f5efd73e87cc0998edc398e75bfc35901)
---
# iot-ai-image-capability

Bounded guidance only. Do not execute third-party JavaScript. Do not print API
keys. Use a host-native image tool only when the operator requested image
generation or editing and MC-GPT policy permits the tool.

If no authorized host-native image tool is available, return capability status
`unavailable` and do not claim that an image was generated.

Prompt-writing pattern reused as an idea: specify subject, composition, medium,
lighting, negative space and text-in-image constraints. Rewrite is original to
MC-GPT.
