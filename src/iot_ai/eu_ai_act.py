# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.4 | Date: 2026-08-08
"""Evidence-bound EU AI Act controls for the IOT-AI Suite.

This module implements technical controls and evidence contracts.  It does not
issue a legal certification or a global compliance score.  Decisions are bound
to an exact system version, intended purpose, deployment context and evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from .paths import (
    article5_screens_path,
    compliance_root,
    compliance_state_path,
    disclosure_receipts_path,
    incidents_path,
    literacy_receipts_path,
    model_dossiers_path,
)
from .privacy import sanitize
from .suite_version import MC_GPT_VERSION, SUITE_VERSION
from .util import atomic_json, atomic_text, exclusive_lock, load_json, sha256_bytes, utc_now

LEGAL_BASELINE: dict[str, Any] = {
    "schema": "iot-ai.eu-ai-act-legal-baseline.v1",
    "assessment_date": "2026-08-06",
    "primary_regulation": "Regulation (EU) 2024/1689",
    "amendment": "Regulation (EU) 2026/1744",
    "current_milestones": {
        "article_4_and_article_5": "2025-02-02",
        "gpai_provider_obligations": "2025-08-02",
        "article_50_and_enforcement": "2026-08-02",
        "article_50_2_limited_transition_for_preexisting_systems": "2026-12-02",
        "annex_iii_high_risk": "2027-12-02",
        "annex_i_product_high_risk": "2028-08-02",
    },
    "official_sources": [
        "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng",
        "https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=oj:L_202601744",
        "https://ai-act-service-desk.ec.europa.eu/en/ai-act/eu-ai-act-implementation-timeline",
        "https://digital-strategy.ec.europa.eu/en/policies/guidelines-transparency-ai-generated-content",
        "https://digital-strategy.ec.europa.eu/en/policies/contents-code-gpai",
        "https://digital-strategy.ec.europa.eu/en/policies/guidelines-gpai-providers",
        "https://digital-strategy.ec.europa.eu/en/library/commission-publishes-guidelines-prohibited-artificial-intelligence-ai-practices-defined-ai-act",
    ],
    "claim_boundary": "technical-compliance-enabling-controls-not-legal-certification",
}

CONTROL_STATES = {
    "not_assessed",
    "not_applicable",
    "applicable_missing",
    "implemented_unverified",
    "verified",
    "expired",
    "blocked",
}

CURRENT_OBLIGATION_CONTROLS = (
    "operator_role_and_intended_purpose",
    "article_4_ai_literacy",
    "article_5_prohibited_practices",
    "article_50_first_interaction_disclosure",
    "article_50_machine_readable_marking",
    "article_50_visible_labelling_and_editorial_control",
    "human_oversight",
    "upstream_model_and_gpai_dossier",
    "public_private_data_boundary",
    "post_market_and_incident_process",
    "claim_evidence_control",
)

PROHIBITED_PRACTICES: dict[str, dict[str, Any]] = {
    "harmful_manipulation_or_deception": {
        "article": "5(1)(a)",
        "effective_from": "2025-02-02",
        "patterns": (
            r"\b(?:covert|subliminal)\s+(?:manipulation|persuasion)\b",
            r"\bdeceive\s+(?:users|people|customers)\s+into\b",
            r"\bmanipulat(?:e|ion)\b.{0,80}\b(?:significant|material)\s+harm\b",
        ),
    },
    "vulnerability_exploitation": {
        "article": "5(1)(b)",
        "effective_from": "2025-02-02",
        "patterns": (
            r"\bexploit\b.{0,60}\b(?:children|elderly|disabled|vulnerable persons?|socioeconomic vulnerability)\b",
            r"\btarget\s+(?:children|elderly|disabled|vulnerable people)\s+to\s+manipulate\b",
        ),
    },
    "social_scoring": {
        "article": "5(1)(c)",
        "effective_from": "2025-02-02",
        "patterns": (
            r"\bsocial\s+scor(?:e|ing)\b",
            r"\bscore\s+(?:citizens|people|employees)\s+across\s+contexts\b",
            r"\b(?:soziale?s?\s+scoring|sozialkredit|soziale\s+bewertung)\b",
            r"(?:امتیازدهی|رتبه[‌ ]?بندی)\s+اجتماعی",
        ),
    },
    "profiling_only_criminal_risk": {
        "article": "5(1)(d)",
        "effective_from": "2025-02-02",
        "patterns": (
            r"\bpredict(?:ive)?\s+polic(?:e|ing)\b.{0,80}\bprofil(?:e|ing)\b",
            r"\bcriminal\s+(?:risk|offence)\s+(?:score|prediction)\b.{0,80}\bpersonality\b",
        ),
    },
    "untargeted_facial_scraping": {
        "article": "5(1)(e)",
        "effective_from": "2025-02-02",
        "patterns": (
            r"\buntargeted\s+(?:facial|face)\s+(?:image\s+)?scrap(?:e|ing)\b",
            r"\bscrape\s+(?:the\s+)?(?:web|cctv)\s+for\s+faces\b",
        ),
    },
    "workplace_or_education_emotion_recognition": {
        "article": "5(1)(f)",
        "effective_from": "2025-02-02",
        "patterns": (
            r"\bemotion\s+recognition\b.{0,60}\b(?:workplace|employee|school|education|student)\b",
            r"\binfer\s+(?:worker|employee|student)\s+emotion\b",
            r"\bemotionserkennung\b.{0,60}\b(?:arbeitsplatz|beschäftigte|schule|bildung|studierende)\b",
            r"(?:تشخیص|استنتاج)\s+احساسات.{0,50}(?:محل\s+کار|کارمند|مدرسه|آموزش|دانشجو)",
        ),
    },
    "sensitive_biometric_categorisation": {
        "article": "5(1)(g)",
        "effective_from": "2025-02-02",
        "patterns": (
            r"\bbiometric\s+categori[sz]ation\b.{0,100}\b(?:race|ethnic|political|religious|sexual|union|belief)\b",
            r"\binfer\s+(?:race|ethnicity|religion|sexual orientation|political opinion)\s+from\s+(?:face|biometric)\b",
            r"\bbiometrische\s+kategorisierung\b.{0,100}\b(?:rasse|ethnisch|politisch|religiös|sexuell|gewerkschaft)\b",
            r"دسته[‌ ]?بندی\s+بیومتریک.{0,100}(?:نژاد|قومیت|مذهب|گرایش\s+جنسی|نظر\s+سیاسی)",
        ),
    },
    "real_time_remote_biometric_identification": {
        "article": "5(1)(h)",
        "effective_from": "2025-02-02",
        "patterns": (
            r"\breal[- ]time\s+remote\s+biometric\s+identification\b",
            r"\breal[- ]time\s+facial\s+identification\b.{0,80}\bpublic\s+space\b",
        ),
    },
    "non_consensual_intimate_or_sexual_content": {
        "article": "5-amended-2026",
        "effective_from": "2026-12-02",
        "patterns": (
            r"\bnon[- ]consensual\s+(?:intimate|sexual)\s+(?:image|video|deepfake|content)\b",
            r"\bsexual\s+deepfake\b.{0,50}\bwithout\s+consent\b",
        ),
    },
    "child_sexual_abuse_material": {
        "article": "5-amended-2026",
        "effective_from": "2026-12-02",
        "patterns": (
            r"\bchild\s+sexual\s+abuse\s+material\b",
            r"\bcsam\b",
        ),
    },
}

REVIEW_CONTEXT_PATTERNS = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"\b(?:audit|review|assess|detect|prevent|block|prohibit|policy|compliance|research|test|red[- ]team|monitor)\b",
        r"\b(?:prüf(?:e|en|ung)|audit|begutacht(?:e|en|ung)|untersuch(?:e|en|ung)|verhinder(?:n|ung)|sperr(?:e|en)|compliance|richtlinie|forschung|test)\b",
        r"(?:ممیزی|بازبینی|ارزیابی|شناسایی|پیشگیری|مسدود|ممنوع|انطباق|پژوهش|آزمون)",
        r"\bhow\s+(?:do|can)\s+we\s+(?:prevent|detect|block)\b",
        r"\bdo\s+not\s+(?:use|build|allow|enable)\b",
    )
)

OPERATIONAL_INTENT_PATTERNS = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"\b(?:build|deploy|implement|enable|operate|launch|sell|commerciali[sz]e|put\s+into\s+service)\b",
        r"\b(?:bau(?:e|en)|entwickel(?:n|t)|bereitstell(?:en|ung)|implementier(?:en|ung)|aktivier(?:en|ung)|betreib(?:en|en)|vermarkt(?:en|ung))\b",
        r"(?:بساز|پیاده[‌ ]?سازی|مستقر|فعال|راه[‌ ]?اندازی|بفروش|تجاری[‌ ]?سازی)",
        r"\b(?:rank|score|profile|scrape|infer)\s+(?:citizens|people|employees|workers|students|applicants)\b",
        r"(?:امتیازدهی|رتبه[‌ ]?بندی|پروفایل|جمع[‌ ]?آوری|استنتاج).{0,40}(?:شهروند|کارمند|دانشجو|متقاضی)",
    )
)

HIGH_RISK_TRIGGERS: dict[str, tuple[re.Pattern[str], ...]] = {
    "annex_i_safety_component": (
        re.compile(r"\bsafety\s+component\b", re.I),
        re.compile(r"\bmedical\s+device\b", re.I),
        re.compile(r"\bmachinery\s+safety\b", re.I),
    ),
    "critical_infrastructure": (
        re.compile(r"\bcritical\s+infrastructure\b", re.I),
        re.compile(r"\b(?:electricity|water|gas|heating|traffic|digital infrastructure)\b.{0,80}\b(?:control|safety|dispatch)\b", re.I),
    ),
    "employment": (
        re.compile(
            r"\b(?:recruit(?:ment)?|hir(?:e|ing)|employment|employees?|workers?|staff|applicants?|candidates?)\b"
            r".{0,120}\b(?:score|scoring|rank|ranking|select|selection|monitor|monitoring|evaluate|evaluation|allocate|allocation)\b",
            re.I,
        ),
        re.compile(
            r"\b(?:score|scoring|rank|ranking|select|selection|monitor|monitoring|evaluate|evaluation|allocate|allocation)\b"
            r".{0,120}\b(?:employees?|workers?|staff|applicants?|candidates?)\b",
            re.I,
        ),
    ),
    "education": (
        re.compile(r"\b(?:student|education|school|university)\b.{0,80}\b(?:admission|assessment|grading|access|monitor)\b", re.I),
    ),
    "essential_services": (
        re.compile(r"\b(?:credit|insurance|benefit|essential service|emergency triage)\b.{0,80}\b(?:eligibility|score|decision|access)\b", re.I),
    ),
    "law_enforcement_migration_justice": (
        re.compile(r"\b(?:law enforcement|police|migration|asylum|border|court|justice)\b.{0,80}\b(?:risk|decision|assess|identify)\b", re.I),
    ),
    "biometrics": (
        re.compile(r"\bbiometric\b.{0,80}\b(?:identification|verification|categorisation|classification)\b", re.I),
    ),
    "health": (
        re.compile(
            r"\b(?:medical|clinical|patient|healthcare|health care)\b.{0,100}"
            r"\b(?:diagnosis|diagnose|treatment|triage|decision support)\b",
            re.I,
        ),
        re.compile(
            r"\b(?:diagnosis|diagnose|treatment|triage|medical decision)\b.{0,100}"
            r"\b(?:patient|medical|clinical|healthcare|health care)\b",
            re.I,
        ),
        re.compile(r"\bemergency\s+triage\b", re.I),
    ),
}


@dataclass(frozen=True, slots=True)
class ProhibitedPracticeFinding:
    category: str
    article: str
    effective_from: str
    matched: str


@dataclass(frozen=True, slots=True)
class ProhibitedPracticeDecision:
    decision: str
    review_context: bool
    text_sha256: str
    findings: tuple[ProhibitedPracticeFinding, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "iot-ai.article-5-screen.v1",
            "decision": self.decision,
            "review_context": self.review_context,
            "text_sha256": self.text_sha256,
            "findings": [asdict(item) for item in self.findings],
            "claim": "screening-result-not-legal-opinion",
        }


def default_system_card() -> dict[str, Any]:
    """Return the exact public developer-preview system card."""
    return {
        "schema": "iot-ai.ai-system-card.v1",
        "system_id": "iot-ai-tech.iot-ai-coder-suite",
        "name": "IOT-AI Suite",
        "version": SUITE_VERSION,
        "component_versions": {"iot-ai-mc-gpt": MC_GPT_VERSION},
        "provider": "IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour",
        "operator_roles": ["ai_system_provider", "deployer", "downstream_provider"],
        "intended_purpose": (
            "Developer-controlled multi-agent planning, code and architecture review, "
            "evidence-bound decision support, deterministic verification and diagnostics."
        ),
        "declared_context": "personal and professional software-development assistance under human control",
        "excluded_purposes": [
            "employment or worker scoring/monitoring decisions",
            "medical diagnosis, treatment or emergency triage",
            "law-enforcement, migration, asylum or judicial decision making",
            "credit, insurance, benefits or essential-service eligibility decisions",
            "biometric identification, categorisation or emotion recognition",
            "social scoring, manipulative persuasion or vulnerability exploitation",
            "autonomous safety-critical or critical-infrastructure control",
        ],
        "reasonably_foreseeable_misuse": [
            "over-reliance on unverified model output",
            "sending private source code or infrastructure data to cloud providers",
            "using generated code without human review and deterministic tests",
            "using the tool outside the declared intended purpose without reclassification",
        ],
        "interaction_profile": {
            "direct_human_interaction": True,
            "generative_text": True,
            "generative_image_audio_video": False,
            "article_50_disclosure_required": True,
            "machine_readable_marking_required_for_human_exposed_generated_content": True,
        },
        "risk_classification": {
            "status": "not-high-risk-for-declared-intended-purpose",
            "annex_i_route": False,
            "annex_iii_route": False,
            "deployment_specific_reassessment_required": True,
            "high_risk_mode_default": "blocked-until-classified",
        },
        "human_oversight": {
            "technical_completion_is_not_founder_acceptance": True,
            "writes_require_authorized_scope": True,
            "material_actions_require_human_approval": True,
            "stop_and_rollback_supported": True,
        },
        "public_claim": "Designed with compliance-enabling transparency, safety, audit and human-governance controls; not legally certified.",
        "assessment_date": LEGAL_BASELINE["assessment_date"],
    }


def default_model_register() -> dict[str, Any]:
    return {
        "schema": "iot-ai.upstream-model-register.v1",
        "generated_at": LEGAL_BASELINE["assessment_date"],
        "entries": [
            {
                "provider_family": "anthropic",
                "suite_route": "claude",
                "role": "upstream-model-provider",
                "exact_model_required_at_runtime": True,
                "documentation_status": "runtime-and-contract-verification-required",
                "code_of_practice_status": "verify-current-official-record",
            },
            {
                "provider_family": "openai",
                "suite_route": "codex",
                "role": "upstream-model-provider",
                "exact_model_required_at_runtime": True,
                "documentation_status": "runtime-and-contract-verification-required",
                "code_of_practice_status": "verify-current-official-record",
            },
            {
                "provider_family": "google",
                "suite_route": "gemini",
                "role": "upstream-model-provider",
                "exact_model_required_at_runtime": True,
                "documentation_status": "runtime-and-contract-verification-required",
                "code_of_practice_status": "verify-current-official-record",
            },
            {
                "provider_family": "xai",
                "suite_route": "grok",
                "role": "upstream-model-provider",
                "exact_model_required_at_runtime": True,
                "documentation_status": "runtime-and-contract-verification-required",
                "code_of_practice_status": "chapter-specific-verification-required",
            },
            {
                "provider_family": "ollama-model-supplier-dependent",
                "suite_route": "ollama",
                "role": "model-distribution-and-routing-layer",
                "exact_model_required_at_runtime": True,
                "underlying_model_provider_required": True,
                "license_and_model_card_required": True,
                "documentation_status": "per-model-dossier-required",
            },
        ],
        "policy": {
            "upstream_compliance_is_not_inherited": True,
            "requested_and_served_model_are_separate": True,
            "silent_fallback_forbidden": True,
            "unknown_model_blocks_required_role": True,
        },
    }


def screen_prohibited_practices(text: str) -> ProhibitedPracticeDecision:
    """Screen a request before provider dispatch.

    Research, compliance and defensive review contexts are allowed but retain
    the matched categories as review evidence.  Operational requests matching a
    prohibited practice fail closed before any model or tool is invoked.
    """
    normalized = " ".join(text.split())
    review_signal = any(pattern.search(normalized) for pattern in REVIEW_CONTEXT_PATTERNS)
    operational_signal = any(pattern.search(normalized) for pattern in OPERATIONAL_INTENT_PATTERNS)
    review_context = review_signal and not operational_signal
    findings: list[ProhibitedPracticeFinding] = []
    for category, spec in PROHIBITED_PRACTICES.items():
        for raw in spec["patterns"]:
            match = re.search(raw, normalized, re.I | re.S)
            if match:
                findings.append(
                    ProhibitedPracticeFinding(
                        category=category,
                        article=str(spec["article"]),
                        effective_from=str(spec["effective_from"]),
                        matched=hashlib.sha256(match.group(0).casefold().encode("utf-8")).hexdigest()[:16],
                    )
                )
                break
    decision = "pass"
    if findings:
        decision = "review-only" if review_context else "block"
    return ProhibitedPracticeDecision(
        decision=decision,
        review_context=review_context,
        text_sha256=sha256_bytes(normalized.encode("utf-8")),
        findings=tuple(findings),
    )


def classify_risk(intended_purpose: str, *, system_is_ai: bool = True) -> dict[str, Any]:
    """Return a conservative deployment-specific Article 6 triage."""
    if not system_is_ai:
        return {
            "schema": "iot-ai.article-6-triage.v1",
            "decision": "not_applicable",
            "reason": "not-an-ai-system",
            "claim": "triage-not-legal-opinion",
        }
    matches: list[str] = []
    for category, patterns in HIGH_RISK_TRIGGERS.items():
        if any(pattern.search(intended_purpose) for pattern in patterns):
            matches.append(category)
    if matches:
        return {
            "schema": "iot-ai.article-6-triage.v1",
            "decision": "high-risk-candidate",
            "matched_routes": matches,
            "deployment_eligible": False,
            "required_next": "documented Article 6/Annex I/Annex III assessment by an authorised legal-technical reviewer",
            "claim": "triage-not-legal-opinion",
        }
    return {
        "schema": "iot-ai.article-6-triage.v1",
        "decision": "not-high-risk-for-declared-purpose",
        "matched_routes": [],
        "deployment_eligible": True,
        "reassessment_triggers": [
            "intended-purpose change",
            "customer sector or deployment context change",
            "model, prompt, RAG source or tool-authority change",
            "rebranding or substantial modification",
        ],
        "claim": "triage-not-legal-opinion",
    }


def validate_system_card(card: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema",
        "system_id",
        "name",
        "version",
        "provider",
        "operator_roles",
        "intended_purpose",
        "excluded_purposes",
        "reasonably_foreseeable_misuse",
        "interaction_profile",
        "risk_classification",
        "human_oversight",
        "assessment_date",
    }
    missing = sorted(required - set(card))
    risk = classify_risk(str(card.get("intended_purpose", "")))
    article5 = screen_prohibited_practices(str(card.get("intended_purpose", ""))).to_dict()
    errors = [f"missing:{item}" for item in missing]
    if article5["decision"] == "block":
        errors.append("article-5-screen-blocked")
    if not card.get("excluded_purposes"):
        errors.append("excluded-purposes-empty")
    if not card.get("operator_roles"):
        errors.append("operator-roles-empty")
    interaction = card.get("interaction_profile") if isinstance(card.get("interaction_profile"), dict) else {}
    if interaction.get("direct_human_interaction") and interaction.get("article_50_disclosure_required") is not True:
        errors.append("article-50-disclosure-profile-missing")
    declared_risk = card.get("risk_classification") if isinstance(card.get("risk_classification"), dict) else {}
    if risk.get("decision") == "high-risk-candidate" and declared_risk.get("status") not in {"high-risk-candidate", "high-risk-classified"}:
        errors.append("risk-classification-contradicts-intended-purpose")
    return {
        "schema": "iot-ai.ai-system-card-validation.v1",
        "decision": "pass" if not errors else "block",
        "errors": errors,
        "article_5": article5,
        "article_6": risk,
    }


def _sanitized_mapping(value: dict[str, Any]) -> dict[str, Any]:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
    result = sanitize(encoded, "strict")
    if result.decision == "block":
        raise ValueError("compliance evidence contains secret-like material")
    try:
        cleaned = json.loads(result.text)
    except json.JSONDecodeError as exc:
        raise ValueError("sanitized compliance evidence is not valid JSON") from exc
    if not isinstance(cleaned, dict):
        raise ValueError("compliance evidence must be a JSON object")
    return cleaned


def verify_evidence_chain(path: Path) -> dict[str, Any]:
    """Verify an append-only local JSONL evidence hash chain."""
    previous = "0" * 64
    count = 0
    errors: list[str] = []
    if not path.exists():
        return {"decision": "pass", "records": 0, "errors": []}
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"line-{line_no}:invalid-json")
            continue
        if not isinstance(record, dict):
            errors.append(f"line-{line_no}:not-object")
            continue
        actual_hash = str(record.get("record_hash") or "")
        body_record = dict(record)
        body_record.pop("record_hash", None)
        if body_record.get("previous_hash") != previous:
            errors.append(f"line-{line_no}:previous-hash-mismatch")
        body = json.dumps(body_record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        expected_hash = sha256_bytes(body.encode("utf-8"))
        if actual_hash != expected_hash:
            errors.append(f"line-{line_no}:record-hash-mismatch")
        previous = actual_hash or previous
        count += 1
    return {"decision": "pass" if not errors else "block", "records": count, "errors": errors}


def _append_jsonl(path: Path, value: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    lock = path.with_name(path.name + ".lock")
    with exclusive_lock(lock):
        chain = verify_evidence_chain(path)
        if chain["decision"] != "pass":
            raise ValueError(f"existing compliance evidence chain is invalid: {chain['errors']}")
        clean = _sanitized_mapping(value)
        previous = "0" * 64
        if path.exists():
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if lines:
                previous = str(json.loads(lines[-1]).get("record_hash") or previous)
        payload = dict(clean)
        payload["previous_hash"] = previous
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload["record_hash"] = sha256_bytes(body.encode("utf-8"))
        descriptor = Path(path)
        with descriptor.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            import os
            os.fsync(handle.fileno())
        try:
            descriptor.chmod(0o600)
        except OSError:
            pass
        return payload


def record_prohibited_practice_screen(
    user_home: Path,
    text: str,
    *,
    context: str,
) -> dict[str, Any]:
    """Persist a privacy-minimised Article 5 screening receipt."""
    decision = screen_prohibited_practices(text)
    receipt = {
        "schema": "iot-ai.article-5-screen-receipt.v1",
        "screened_at": utc_now(),
        "context": context,
        **decision.to_dict(),
        "raw_text_stored": False,
    }
    return _append_jsonl(article5_screens_path(user_home), receipt)

def record_literacy_receipt(
    user_home: Path,
    *,
    subject_id: str,
    role: str,
    curriculum_version: str,
    assessment: str,
    refresher_due: str,
) -> dict[str, Any]:
    """Record a privacy-minimised Article 4 competence receipt."""
    if assessment not in {"pass", "needs-work", "expired"}:
        raise ValueError("invalid literacy assessment")
    receipt = {
        "schema": "iot-ai.ai-literacy-receipt.v1",
        "receipt_id": "lit-" + hashlib.sha256(f"{subject_id}:{role}:{utc_now()}".encode()).hexdigest()[:20],
        "subject_pseudonym": hashlib.sha256(subject_id.encode("utf-8")).hexdigest(),
        "role": role,
        "curriculum_version": curriculum_version,
        "assessment": assessment,
        "completed_at": utc_now(),
        "refresher_due": refresher_due,
        "raw_identity_stored": False,
    }
    return _append_jsonl(literacy_receipts_path(user_home), receipt)


def register_model_dossier(user_home: Path, dossier: dict[str, Any]) -> dict[str, Any]:
    required = {
        "provider",
        "model_id",
        "model_version",
        "license",
        "model_card_reference",
        "capabilities",
        "limitations",
        "data_egress_profile",
        "last_verified_at",
    }
    missing = sorted(required - set(dossier))
    if missing:
        raise ValueError(f"model dossier missing fields: {missing}")
    clean = _sanitized_mapping(dossier)
    entry = {
        **clean,
        "dossier_sha256": sha256_bytes(
            json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ),
    }
    path = model_dossiers_path(user_home)
    with exclusive_lock(path.with_name(path.name + ".lock")):
        store = load_json(path, {"schema": "iot-ai.model-dossiers.v1", "entries": []})
        if not isinstance(store, dict):
            raise ValueError("model dossier store is invalid")
        entries = [
            row
            for row in store.get("entries", [])
            if not (row.get("provider") == entry["provider"] and row.get("model_id") == entry["model_id"])
        ]
        entries.append(entry)
        store["entries"] = sorted(entries, key=lambda row: (str(row.get("provider")), str(row.get("model_id"))))
        store["updated_at"] = utc_now()
        atomic_json(path, store)
    return entry

def record_incident(user_home: Path, incident: dict[str, Any]) -> dict[str, Any]:
    required = {"system_id", "system_version", "severity", "discovered_at", "summary", "reportability"}
    missing = sorted(required - set(incident))
    if missing:
        raise ValueError(f"incident missing fields: {missing}")
    if incident.get("severity") not in {"info", "low", "medium", "high", "critical"}:
        raise ValueError("invalid incident severity")
    sanitized = sanitize(str(incident.get("summary", "")), "strict")
    if sanitized.decision == "block":
        raise ValueError("incident summary contains secret-like material")
    value = {
        "schema": "iot-ai.ai-incident.v1",
        "incident_id": incident.get("incident_id") or "inc-" + hashlib.sha256(f"{incident['system_id']}:{utc_now()}".encode()).hexdigest()[:20],
        **incident,
        "summary": sanitized.text,
        "evidence_frozen": bool(incident.get("evidence_frozen", False)),
        "recorded_at": utc_now(),
    }
    return _append_jsonl(incidents_path(user_home), value)


def change_reassessment(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "intended_purpose",
        "provider",
        "operator_roles",
        "interaction_profile",
        "risk_classification",
    )
    changes = [field for field in fields if previous.get(field) != current.get(field)]
    if previous.get("version") != current.get("version"):
        changes.append("version")
    return {
        "schema": "iot-ai.substantial-modification-review.v1",
        "decision": "reassessment-required" if changes else "no-material-change-detected",
        "changed_fields": sorted(set(changes)),
        "prior_version": previous.get("version"),
        "current_version": current.get("version"),
        "claim": "technical-change-trigger-not-legal-determination",
    }


def _parse_due(value: str) -> date | None:
    try:
        normalized = value.replace("Z", "+00:00")
        if "T" in normalized:
            return datetime.fromisoformat(normalized).date()
        return date.fromisoformat(normalized[:10])
    except (TypeError, ValueError):
        return None


def runtime_compliance_status(user_home: Path) -> dict[str, Any]:
    card = default_system_card()
    card_validation = validate_system_card(card)
    state = load_json(compliance_state_path(user_home), {}) or {}

    literacy_records: list[dict[str, Any]] = []
    literacy_path = literacy_receipts_path(user_home)
    if literacy_path.exists() and verify_evidence_chain(literacy_path)["decision"] == "pass":
        for line in literacy_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    literacy_records.append(value)
    latest_by_role: dict[str, dict[str, Any]] = {}
    for item in literacy_records:
        role = str(item.get("role") or "")
        if role and str(item.get("completed_at") or "") >= str(latest_by_role.get(role, {}).get("completed_at") or ""):
            latest_by_role[role] = item
    required_literacy_roles = {"developer", "operator", "administrator", "compliance"}
    current_roles = {
        role
        for role, item in latest_by_role.items()
        if item.get("assessment") == "pass"
        and (_parse_due(str(item.get("refresher_due") or "")) or date.min) >= date.today()
    }
    literacy_complete = required_literacy_roles.issubset(current_roles)

    disclosure_count = 0
    disclosures = disclosure_receipts_path(user_home)
    if disclosures.exists() and verify_evidence_chain(disclosures)["decision"] == "pass":
        disclosure_count = sum(1 for line in disclosures.read_text(encoding="utf-8").splitlines() if line.strip())
    model_store = load_json(model_dossiers_path(user_home), {"entries": []}) or {"entries": []}
    incidents = 0
    if incidents_path(user_home).exists() and verify_evidence_chain(incidents_path(user_home))["decision"] == "pass":
        incidents = sum(1 for line in incidents_path(user_home).read_text(encoding="utf-8").splitlines() if line.strip())

    controls = {
        "operator_role_and_intended_purpose": "verified" if card_validation["decision"] == "pass" else "blocked",
        "article_4_ai_literacy": "verified" if literacy_complete else "implemented_unverified",
        "article_5_prohibited_practices": "verified",
        "article_50_first_interaction_disclosure": (
            "verified" if disclosure_count and state.get("article_50_surface_coverage_verified") is True else "implemented_unverified"
        ),
        "article_50_machine_readable_marking": (
            "verified" if state.get("content_marking_export_coverage_verified") is True else "implemented_unverified"
        ),
        "article_50_visible_labelling_and_editorial_control": (
            "verified" if state.get("visible_label_workflow_verified") is True else "implemented_unverified"
        ),
        "human_oversight": "verified",
        "upstream_model_and_gpai_dossier": (
            "verified" if model_store.get("entries") and state.get("model_dossier_coverage_verified") is True else "implemented_unverified"
        ),
        "public_private_data_boundary": "verified",
        "post_market_and_incident_process": (
            "verified"
            if state.get("post_market_process_verified") is True and state.get("incident_process_verified") is True
            else "implemented_unverified"
        ),
        "claim_evidence_control": "verified",
    }
    hard_blockers = [name for name, control_state in controls.items() if control_state in {"blocked", "applicable_missing", "expired"}]
    return {
        "schema": "iot-ai.eu-ai-act-runtime-status.v2",
        "legal_baseline": LEGAL_BASELINE,
        "system_card": card,
        "controls": controls,
        "runtime_evidence": {
            "literacy_receipts": len(literacy_records),
            "literacy_roles_current": sorted(current_roles),
            "literacy_roles_required": sorted(required_literacy_roles),
            "article_50_disclosure_receipts": disclosure_count,
            "model_dossiers": len(model_store.get("entries", [])),
            "incident_records": incidents,
        },
        "developer_preview_decision": "pass" if not hard_blockers else "block",
        "production_decision": "block",
        "production_blockers": [
            "deployment-specific legal review",
            "live Article 50 surface verification",
            "exact runtime model supplier dossiers",
            "live provider and model receipts",
            "high-risk reassessment for every customer use case",
        ],
        "global_compliance_claim_allowed": False,
        "claim": "technical-control-status-not-legal-certification",
    }

def _load_json_required(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append(f"invalid-json:{path.name}")
        return {}
    return value if isinstance(value, dict) else {}


def release_gate(root: Path, *, profile: str = "developer-preview") -> dict[str, Any]:
    """Verify the repository's public EU AI Act evidence pack.

    The developer-preview profile checks currently applicable technical release
    controls for this exact declared purpose.  The production profile always
    requires external deployment and legal evidence not present in a public
    source release.
    """
    root = root.resolve()
    compliance = root / "docs" / "compliance"
    required_files = {
        "LEGAL_BASELINE.json",
        "AI_ACT_SYSTEM_CARD.json",
        "EU_AI_ACT_COMPLIANCE_MATRIX.json",
        "UPSTREAM_MODEL_REGISTER.json",
        "CLAIM_EVIDENCE_REGISTER.json",
        "AI_ACT_SYSTEM_CARD.md",
        "INTENDED_PURPOSE_AND_LIMITATIONS.md",
        "AI_ACT_CLASSIFICATION.md",
        "PROHIBITED_USES.md",
        "AI_INTERACTION_TRANSPARENCY.md",
        "AI_GENERATED_CONTENT_MARKING.md",
        "AI_LITERACY_PROGRAM.md",
        "HUMAN_OVERSIGHT.md",
        "POST_MARKET_MONITORING.md",
        "AI_INCIDENT_RESPONSE.md",
        "PUBLIC_PRIVATE_DATA_BOUNDARY.md",
    }
    errors = [f"missing:{name}" for name in sorted(required_files) if not (compliance / name).is_file()]
    card = _load_json_required(compliance / "AI_ACT_SYSTEM_CARD.json", errors) if (compliance / "AI_ACT_SYSTEM_CARD.json").exists() else {}
    matrix = _load_json_required(compliance / "EU_AI_ACT_COMPLIANCE_MATRIX.json", errors) if (compliance / "EU_AI_ACT_COMPLIANCE_MATRIX.json").exists() else {}
    models = _load_json_required(compliance / "UPSTREAM_MODEL_REGISTER.json", errors) if (compliance / "UPSTREAM_MODEL_REGISTER.json").exists() else {}
    claims = _load_json_required(compliance / "CLAIM_EVIDENCE_REGISTER.json", errors) if (compliance / "CLAIM_EVIDENCE_REGISTER.json").exists() else {}
    legal = _load_json_required(compliance / "LEGAL_BASELINE.json", errors) if (compliance / "LEGAL_BASELINE.json").exists() else {}

    if card:
        validation = validate_system_card(card)
        errors.extend(f"system-card:{error}" for error in validation["errors"])
        if card.get("version") != SUITE_VERSION:
            errors.append("system-card-version-mismatch")
    if legal and legal.get("primary_regulation") != LEGAL_BASELINE["primary_regulation"]:
        errors.append("legal-baseline-primary-regulation-mismatch")
    if legal and legal.get("amendment") != LEGAL_BASELINE["amendment"]:
        errors.append("legal-baseline-amendment-mismatch")
    controls = matrix.get("controls", {}) if isinstance(matrix.get("controls"), dict) else {}
    if matrix.get("system_version") != SUITE_VERSION:
        errors.append("compliance-matrix-version-mismatch")
    if matrix.get("global_compliance_claim_allowed") is not False:
        errors.append("compliance-matrix-global-claim-must-be-false")
    unverified_controls: list[str] = []
    for control in CURRENT_OBLIGATION_CONTROLS:
        state = controls.get(control)
        if state not in CONTROL_STATES:
            errors.append(f"control-state-invalid:{control}")
        elif state in {"blocked", "applicable_missing", "expired", "not_assessed"}:
            errors.append(f"control-not-releaseable:{control}:{state}")
        elif state == "implemented_unverified":
            unverified_controls.append(control)
    providers = {entry.get("suite_route") for entry in models.get("entries", []) if isinstance(entry, dict)}
    if not {"claude", "codex", "gemini", "grok", "ollama"}.issubset(providers):
        errors.append("upstream-model-register-incomplete")
    if claims.get("global_compliance_claim_allowed") is not False:
        errors.append("unsupported-global-compliance-claim")
    if profile == "production":
        errors.append("production-profile-requires-external-legal-and-live-deployment-evidence")
    decision = "pass" if not errors else "block"
    result = {
        "schema": "iot-ai.eu-ai-act-release-gate.v1",
        "profile": profile,
        "decision": decision,
        "errors": sorted(set(errors)),
        "system_version": SUITE_VERSION,
        "legal_baseline_sha256": sha256_bytes(json.dumps(LEGAL_BASELINE, sort_keys=True).encode("utf-8")),
        "global_compliance_claim_allowed": False,
        "unverified_runtime_or_organisational_controls": sorted(unverified_controls),
        "external_release_gates": [
            "live surface and export-path Article 50 verification",
            "role-based AI literacy completion evidence",
            "exact model supplier dossiers and contracts",
            "deployment-specific legal review and high-risk reassessment",
        ],
        "claim": "technical-current-obligations-gate-not-legal-certification",
    }
    return result


def initialize_runtime_state(user_home: Path) -> dict[str, Any]:
    root = compliance_root(user_home)
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    state = {
        "schema": "iot-ai.eu-ai-act-runtime-state.v1",
        "system_card": default_system_card(),
        "legal_baseline": LEGAL_BASELINE,
        "initialized_at": utc_now(),
        "global_compliance_claim_allowed": False,
    }
    atomic_json(compliance_state_path(user_home), state)
    atomic_text(root / "README.txt", "Private runtime compliance evidence. Do not publish this directory.\n")
    return state
