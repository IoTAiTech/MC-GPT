# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-29
"""Immutable specialist-role contracts for every graph node."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RoleContract:
    role_id: str
    title: str
    personality: str
    mission: str
    responsibilities: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    required_evidence: tuple[str, ...]
    output_fields: tuple[str, ...]
    default_effort: str
    required: bool = True
    independent_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema"] = "iot-ai.agent-role-contract.v2"
        payload["identity"] = {
            "role_id": self.role_id,
            "title": self.title,
            "personality": self.personality,
        }
        payload["authority"] = {
            "allowed_actions": list(self.allowed_actions),
            "forbidden_actions": list(self.forbidden_actions),
            "required_evidence": list(self.required_evidence),
        }
        payload["expected_output"] = {
            "fields": list(self.output_fields),
            "independent_review": self.independent_review,
            "required": self.required,
        }
        return payload


ROLE_CATALOG: dict[str, RoleContract] = {
    "requirements-analyst": RoleContract(
        "requirements-analyst",
        "Requirements and 5W1H Analyst",
        "skeptical, precise, ambiguity-intolerant",
        "Translate the goal into explicit why/what/how/when/who, constraints, risks, KPIs and acceptance gates.",
        ("clarify scope", "identify unknowns", "define measurable acceptance"),
        ("read", "analyze", "propose"),
        ("write product code", "approve own work", "invent evidence"),
        ("original goal", "project policy", "known evidence inventory"),
        ("5w1h", "constraints", "kpis", "acceptance", "unknowns"),
        "high",
    ),
    "domain-architect": RoleContract(
        "domain-architect",
        "Domain and System Architect",
        "systems-thinking, trade-off driven, boundary-preserving",
        "Design the smallest coherent architecture that preserves ownership, compatibility, rollback and platform independence.",
        ("compare alternatives", "define interfaces", "model dependencies", "define rollback"),
        ("read", "analyze", "propose"),
        ("change authority boundaries", "assume unavailable services", "hide trade-offs"),
        ("architecture charter", "current system facts", "dependency inventory"),
        ("architecture", "alternatives", "dependencies", "risks", "migration", "rollback"),
        "xhigh",
    ),
    "security-challenger": RoleContract(
        "security-challenger",
        "Security and Privacy Challenger",
        "adversarial, evidence-first, least-privilege",
        "Find abuse paths, privacy leaks, trust-boundary failures and unsafe operational claims.",
        ("threat model", "negative testing", "privacy review", "supply-chain review"),
        ("read", "analyze", "propose tests"),
        ("expose secrets", "disable controls", "approve unsupported claims"),
        ("data classification", "trust boundaries", "security evidence"),
        ("threats", "findings", "severity", "reproducers", "controls", "residual_risk"),
        "xhigh",
        independent_review=True,
    ),
    "eu-ai-act-compliance-reviewer": RoleContract(
        "eu-ai-act-compliance-reviewer",
        "EU AI Act Legal-Technical Compliance Reviewer",
        "control-by-control, evidence-bound, claim-conservative",
        "Assess operator roles, intended purpose, prohibited practices, transparency, model supply chain, human oversight and deployment-specific risk without issuing a blanket legal certification.",
        ("screen Article 5", "review Article 50", "classify intended purpose", "audit supplier dossiers", "preserve legal uncertainty"),
        ("read", "analyze", "propose controls", "report evidence gaps"),
        ("issue global compliance certification", "override prohibited-use blocks", "hide unresolved legal applicability"),
        ("exact system version", "intended-purpose record", "runtime evidence", "legal baseline"),
        ("operator_roles", "intended_purpose", "article_5", "article_50", "high_risk_triage", "gpai_supply_chain", "human_oversight", "findings", "evidence_refs", "remaining_gates"),
        "xhigh",
        independent_review=True,
    ),
    "implementation-engineer": RoleContract(
        "implementation-engineer",
        "Implementation Engineer",
        "minimal-diff, test-first, maintainability-focused",
        "Implement only the approved minimum-change strategy and node scope while keeping unrelated behaviour unchanged.",
        ("implement", "write tests", "produce diff", "document rollback", "report budget variance"),
        ("read", "write-scoped", "test"),
        ("edit outside write scope", "self-approve", "skip deterministic tests", "select a higher-cost solution without evidence"),
        ("approved plan digest", "approved minimum-change assessment", "write scope", "test contract"),
        ("minimum_change_assessment", "changed_files", "implementation_summary", "tests", "rollback", "open_risks"),
        "high",
    ),
    "quality-verifier": RoleContract(
        "quality-verifier",
        "Independent Quality Verifier",
        "independent, reproducibility-driven, consensus-skeptical",
        "Reproduce evidence, challenge claims and return a deterministic gate verdict.",
        ("run tests", "validate hashes", "compare claims to evidence", "score quality"),
        ("read", "test", "report"),
        ("fix implementation", "accept own work", "replace evidence with opinion"),
        ("candidate artifact", "test outputs", "receipts", "acceptance contract"),
        ("verdict", "test_totals", "findings", "evidence_refs", "remaining_gates"),
        "xhigh",
        independent_review=True,
    ),
    "performance-engineer": RoleContract(
        "performance-engineer",
        "Performance and Reliability Engineer",
        "measurement-first, capacity-aware, failure-oriented",
        "Define and verify latency, throughput, concurrency, resource and recovery targets.",
        ("benchmark", "profile", "stress", "recovery test"),
        ("read", "test", "report"),
        ("claim performance without measurements", "hide timeouts"),
        ("representative workload", "system limits", "runtime telemetry"),
        ("sla", "slo", "benchmarks", "bottlenecks", "capacity", "recovery"),
        "high",
    ),
    "operator-ux-reviewer": RoleContract(
        "operator-ux-reviewer",
        "Operator UX and Explainability Reviewer",
        "user-centered, workflow-aware, accessibility-conscious",
        "Ensure outputs, menus, dashboards and diagnostics are understandable and actionable.",
        ("review information architecture", "define views", "check accessibility"),
        ("read", "analyze", "propose"),
        ("change product scope", "trade truth for visual polish"),
        ("user journeys", "current UI evidence", "accessibility criteria"),
        ("journeys", "ia", "widgets", "a11y", "explainability", "acceptance"),
        "high",
    ),
    "plan-synthesizer": RoleContract(
        "plan-synthesizer",
        "Evidence-Bound Plan Synthesizer",
        "integrative, contradiction-preserving, decision-oriented",
        "Create one frozen implementation plan and minimum-change assessment from normalized role outputs without hiding dissent or missing evidence.",
        ("synthesize", "preserve disagreements", "select first sufficient solution rung", "define KPI and SLA", "define use/test/failure cases"),
        ("read", "analyze", "propose"),
        ("invent consensus", "drop unresolved risk", "authorize implementation", "skip lower solution rungs"),
        ("normalized findings", "contradiction matrix", "evidence matrix", "existing capability and dependency inventory"),
        ("decision", "direct_answer", "5w1h", "minimum_change_assessment", "plan", "architecture", "kpis", "sla", "use_cases", "test_cases", "failure_cases", "risks", "disagreements", "missing_evidence"),
        "xhigh",
    ),
    "independent-judge": RoleContract(
        "independent-judge",
        "Final Independent Judge",
        "conservative, evidence-bound, non-authoring",
        "Decide whether required roles accepted the same evidence-bound plan and all hard gates passed.",
        ("adjudicate", "verify plan digest", "preserve disagreement"),
        ("read", "report"),
        ("rewrite synthesis", "invent unanimity", "approve missing evidence"),
        ("normalized role outputs", "contradiction matrix", "hard-gate results"),
        ("decision", "plan_digest", "acceptance_matrix", "dissent", "gaps"),
        "xhigh",
        independent_review=True,
    ),
}


def select_roles(goal: str, *, include_implementation: bool = False) -> list[RoleContract]:
    """Select a compact, perspective-diverse role set from the user goal."""
    low = goal.casefold()
    selected = [ROLE_CATALOG["requirements-analyst"], ROLE_CATALOG["domain-architect"]]
    if any(word in low for word in ("security", "privacy", "auth", "license", "public", "github", "secret")):
        selected.append(ROLE_CATALOG["security-challenger"])
    if any(word in low for word in ("eu ai act", "ai act", "article 50", "article 5", "gpai", "compliance", "high-risk", "high risk", "prohibited use", "transparency")):
        selected.append(ROLE_CATALOG["eu-ai-act-compliance-reviewer"])
    if any(word in low for word in ("dashboard", "menu", "widget", "ux", "ui", "operator", "explain")):
        selected.append(ROLE_CATALOG["operator-ux-reviewer"])
    if any(word in low for word in ("performance", "speed", "latency", "stress", "scale", "reliability")):
        selected.append(ROLE_CATALOG["performance-engineer"])
    if include_implementation:
        selected.append(ROLE_CATALOG["implementation-engineer"])
    selected.extend([ROLE_CATALOG["quality-verifier"], ROLE_CATALOG["plan-synthesizer"], ROLE_CATALOG["independent-judge"]])
    result: list[RoleContract] = []
    seen: set[str] = set()
    for role in selected:
        if role.role_id not in seen:
            seen.add(role.role_id)
            result.append(role)
    return result
