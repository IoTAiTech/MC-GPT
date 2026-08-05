# AI-generated content marking

The Suite provides technical marking for the exact supported formats:

- Markdown front-matter provenance;
- HTML metadata and JSON-LD provenance;
- JSON provenance objects;
- PNG embedded compressed-text provenance;
- TXT structured provenance plus a visible label;
- a hash-bound sidecar for every marked file.

CSV, JPEG, SVG, PDF, audio and video remain `needs-work` in the built-in marker and require a format-appropriate interoperable mark (for example, a suitable Content Credentials/C2PA implementation), preservation tests and any required visible label before public release. A sidecar alone is not represented as universally robust marking.

The record binds the unmarked source SHA-256 and marked-file SHA-256, generator/version, model provider/model IDs, human-review status, editorial responsibility, public-interest/deepfake flags and visible-label state. Existing IOT-AI marks are replaced rather than accumulated, and verification detects file or embedded/sidecar tampering.

The built-in implementation is a technical fallback, not proof that metadata survives every copy, screenshot, transcode, platform upload or customer export path. Those paths must be tested for the actual deployment.
