# Third-Party Notices

- `openpyxl` 3.1.5 — MIT License.
- `et_xmlfile` 2.0.0 — MIT License.
- Optional Enterprise `cryptography` 50.x — Apache-2.0 OR BSD-3-Clause.

The architecture borrows open design ideas such as progressive disclosure and file-based knowledge artifacts; no third-party private code, credentials or model output is bundled as product source.

## Garden Skills (derived adapters)

- Upstream: `https://github.com/ConardLi/garden-skills`
- Reviewed commit: `aaf9a82f5efd73e87cc0998edc398e75bfc35901`
- Upstream license: MIT
- Integration: MC-GPT-owned rewrite of permitted patterns only. Not a submodule,
  not a package dependency, and not an automatic network pull.
- Bundled Garden JavaScript/Node scripts are not included and must not execute.
- Lock file: `governance/garden-skills.lock.json`
- MC-GPT top-level license remains LicenseRef-PolyForm-Noncommercial-1.0.0.
