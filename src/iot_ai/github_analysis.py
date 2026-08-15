# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.6 | Date: 2026-08-15
"""Inbound GitHub analysis: technical, commercial, license, relevance.

Reuse only our own rewrite of a pattern, model, or idea. Never add the
analyzed repository as a dependency and never take an illegal license.
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

POLICY_ID = "GITHUB_ANALYSIS_NO_DEPENDENCY_v1"
OUR_COMMUNITY_SPDX = "LicenseRef-PolyForm-Noncommercial-1.0.0"

COPYLEFT = frozenset({
    "GPL-2.0",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "AGPL-3.0",
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
    "OSL-3.0",
    "EUPL-1.2",
    "SSPL-1.0",
})
PERMISSIVE_OK_FOR_IDEAS = frozenset({
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "0BSD",
    "Unlicense",
})
MARK_STRIP_NEEDLES = (
    "watermark remover",
    "watermarks-remover",
    "remove-ai-marks",
    "strip c2pa",
    "strip provenance",
    "synthid removal",
    "unmark ai",
)

_REPO_RE = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$")


def parse_repo_ref(value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError("empty repository reference")
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"} and parsed.netloc.lower() in {"github.com", "www.github.com"}:
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 2:
            raise ValueError(f"not a GitHub repository URL: {value}")
        return f"{parts[0]}/{parts[1].removesuffix('.git')}"
    match = _REPO_RE.match(text)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    raise ValueError(f"not a GitHub owner/name or URL: {value}")


def _contradicts_marking(name: str, description: str) -> bool:
    blob = f"{name} {description}".casefold()
    return any(needle in blob for needle in MARK_STRIP_NEEDLES)


def classify(
    *,
    repo: str,
    spdx: str | None,
    description: str = "",
    commercial_notes: str = "",
) -> dict[str, Any]:
    """Classify one inbound repository. Never recommends a dependency."""
    desc = description or ""
    license_id = (spdx or "").strip() or None
    if license_id in {"NOASSERTION", "OTHER", "NONE"}:
        license_id = None

    if _contradicts_marking(repo, desc):
        use = "NO"
        relevance = "contradicts_product"
        idea = "None. MC-GPT marks AI output (Art. 50 / C2PA-style). Do not unmark."
        do_not = "Do not ship a watermark or provenance remover."
    elif license_id is None:
        use = "NO"
        relevance = "no_license_grant"
        idea = "None until the owner publishes a license grant."
        do_not = "Do not copy or vendor unlicensed code."
    elif license_id in COPYLEFT:
        use = "NO_VENDOR"
        relevance = "copyleft_separate_process_only"
        idea = "Study the architecture. Run a separate process only after an explicit Founder pick."
        do_not = f"Do not vendor {license_id} into the Suite tree."
    elif license_id in PERMISSIVE_OK_FOR_IDEAS:
        use = "PATTERNS_ONLY"
        relevance = "ideas_only"
        idea = "Rewrite useful patterns, models, or UX ideas in our files under our license."
        do_not = "Do not add this repository as a dependency or copy its license onto ours."
    else:
        use = "BLOCK"
        relevance = "unresolved_license"
        idea = "None until LICENSE_POLICY resolves this SPDX."
        do_not = "Default BLOCK: do not infer MIT and do not vendor."

    record = {
        "repo": repo,
        "spdx": license_id,
        "technical": desc or "not_provided",
        "commercial": commercial_notes or "keep_our_polyform_community_and_written_commercial",
        "license": license_id or "missing",
        "relevance": relevance,
        "use": use,
        "idea_we_may_rewrite": idea,
        "do_not": do_not,
        "adds_dependency": False,
        "relicense_us": False,
        "policy_id": POLICY_ID,
        "our_community_spdx": OUR_COMMUNITY_SPDX,
    }
    if record["adds_dependency"] or record["relicense_us"]:
        raise RuntimeError("github analysis must never recommend a dependency or relicensing")
    return record


def analyze_records(items: list[dict[str, Any]]) -> dict[str, Any]:
    repos = []
    for item in items:
        repos.append(
            classify(
                repo=parse_repo_ref(str(item.get("repo") or item.get("url") or "")),
                spdx=item.get("spdx") or item.get("license"),
                description=str(item.get("description") or item.get("technical") or ""),
                commercial_notes=str(item.get("commercial") or ""),
            )
        )
    return {
        "decision": "pass",
        "policy_id": POLICY_ID,
        "adds_dependency": False,
        "relicense_us": False,
        "production_claim": False,
        "repos": repos,
    }


def fetch_github_repo(repo: str, *, timeout: float = 12.0) -> dict[str, Any]:
    """Read public GitHub metadata. Does not clone or install the repository."""
    url = f"https://api.github.com/repos/{repo}"
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "iot-ai-mc-gpt-github-analysis",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - https GitHub API only
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"GitHub API HTTP {exc.code} for {repo}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API unreachable for {repo}: {exc.reason}") from exc
    license_block = payload.get("license") or {}
    return {
        "repo": payload.get("full_name") or repo,
        "spdx": license_block.get("spdx_id"),
        "description": payload.get("description") or "",
        "stars": payload.get("stargazers_count"),
        "archived": bool(payload.get("archived")),
        "html_url": payload.get("html_url"),
    }


def analyze_refs(refs: list[str], *, fetch: bool = False, offline: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if offline is not None:
        return analyze_records(offline)
    items: list[dict[str, Any]] = []
    for ref in refs:
        repo = parse_repo_ref(ref)
        if fetch:
            items.append(fetch_github_repo(repo))
        else:
            items.append({"repo": repo, "spdx": None, "description": ""})
    return analyze_records(items)
