# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.6.0-beta.3 | Date: 2026-08-06
from __future__ import annotations

import base64
import hashlib
import io
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from iot_ai.agentic import run_goal
from iot_ai.cli import main
from iot_ai.eu_ai_act import (
    LEGAL_BASELINE,
    change_reassessment,
    classify_risk,
    default_model_register,
    default_system_card,
    record_incident,
    record_literacy_receipt,
    record_prohibited_practice_screen,
    register_model_dossier,
    release_gate,
    runtime_compliance_status,
    screen_prohibited_practices,
    validate_system_card,
    verify_evidence_chain,
)
from iot_ai.meeting import start as meeting_start
from iot_ai.paths import article5_screens_path, disclosure_receipts_path
from iot_ai.roles import select_roles
from iot_ai.transparency import DISCLOSURES, mark_file, record_disclosure, runtime_output_provenance, verify_file

from tests.common import IsolatedHomeTestCase

# 1x1 transparent PNG.
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class EuAiActTests(IsolatedHomeTestCase):
    def test_legal_baseline_is_current_and_claim_bounded(self) -> None:
        self.assertEqual(LEGAL_BASELINE["primary_regulation"], "Regulation (EU) 2024/1689")
        self.assertEqual(LEGAL_BASELINE["amendment"], "Regulation (EU) 2026/1744")
        self.assertEqual(LEGAL_BASELINE["current_milestones"]["article_50_and_enforcement"], "2026-08-02")
        self.assertIn("not-legal-certification", LEGAL_BASELINE["claim_boundary"])

    def test_system_card_is_versioned_and_valid(self) -> None:
        card = default_system_card()
        result = validate_system_card(card)
        self.assertEqual(result["decision"], "pass")
        self.assertFalse(card["risk_classification"]["annex_iii_route"])
        self.assertFalse(card["risk_classification"]["annex_i_route"])

    def test_system_card_rejects_risk_classification_contradiction(self) -> None:
        card = default_system_card()
        card["intended_purpose"] = "Rank employees and allocate work using performance scores"
        result = validate_system_card(card)
        self.assertEqual(result["decision"], "block")
        self.assertIn("risk-classification-contradicts-intended-purpose", result["errors"])

    def test_article_5_operational_social_scoring_blocks(self) -> None:
        result = screen_prohibited_practices("Build a social scoring engine that ranks citizens across contexts")
        self.assertEqual(result.decision, "block")
        self.assertTrue(result.findings)

    def test_article_5_defensive_audit_is_review_only(self) -> None:
        result = screen_prohibited_practices("Audit our policy to detect and block social scoring")
        self.assertEqual(result.decision, "review-only")
        self.assertTrue(result.review_context)

    def test_article_5_operational_intent_cannot_hide_behind_audit_word(self) -> None:
        result = screen_prohibited_practices("Audit the design and then deploy a social scoring service")
        self.assertEqual(result.decision, "block")
        self.assertFalse(result.review_context)

    def test_article_5_multilingual_social_scoring_blocks(self) -> None:
        self.assertEqual(screen_prohibited_practices("Baue ein System für soziale Bewertung").decision, "block")
        self.assertEqual(screen_prohibited_practices("یک سامانه امتیازدهی اجتماعی بساز").decision, "block")

    def test_article_5_receipt_has_no_raw_prompt(self) -> None:
        receipt = record_prohibited_practice_screen(
            self.home,
            "Audit social scoring controls for a private environment",
            context="unit-test",
        )
        self.assertFalse(receipt["raw_text_stored"])
        self.assertNotIn("private environment", json.dumps(receipt))
        self.assertEqual(verify_evidence_chain(article5_screens_path(self.home))["decision"], "pass")

    def test_article_5_benign_developer_request_passes(self) -> None:
        self.assertEqual(screen_prohibited_practices("Review this Python package for security defects").decision, "pass")

    def test_high_risk_triage_blocks_employment_scoring_candidate(self) -> None:
        result = classify_risk("Rank employees and allocate work using performance scores")
        self.assertEqual(result["decision"], "high-risk-candidate")
        self.assertFalse(result["deployment_eligible"])

    def test_declared_developer_purpose_not_high_risk(self) -> None:
        result = classify_risk("Review source code and run deterministic tests under human control")
        self.assertEqual(result["decision"], "not-high-risk-for-declared-purpose")

    def test_disclosure_payloads_exist_in_three_languages(self) -> None:
        self.assertEqual(set(DISCLOSURES), {"en", "de", "fa"})
        for language in DISCLOSURES:
            result = record_disclosure(self.home, surface="test", language=language)
            self.assertTrue(result["disclosure"]["ai_interaction"])
            self.assertFalse(result["receipt"]["personal_identity_stored"])

    def test_markdown_mark_and_verify(self) -> None:
        path = self.home / "post.md"
        path.write_text("# Launch\n", encoding="utf-8")
        result = mark_file(path, model_providers=["openai"], model_ids=["model-x"], human_reviewed=True, editorially_responsible_party="IoT-AI.Tech")
        self.assertEqual(result["decision"], "pass")
        self.assertEqual(verify_file(path)["decision"], "pass")
        self.assertTrue(path.read_text(encoding="utf-8").startswith("---\n"))

    def test_repeated_marking_replaces_stale_mark_instead_of_accumulating(self) -> None:
        path = self.home / "repeat.md"
        path.write_text("# Repeated\n", encoding="utf-8")
        mark_file(path, model_providers=["openai"], model_ids=["model-a"])
        mark_file(path, model_providers=["anthropic"], model_ids=["model-b"])
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count("iot_ai_provenance: "), 1)
        self.assertIn("model-b", text)
        self.assertNotIn("model-a", text)
        self.assertEqual(verify_file(path)["decision"], "pass")

    def test_json_mark_and_verify(self) -> None:
        path = self.home / "result.json"
        path.write_text('{"answer": "ok"}\n', encoding="utf-8")
        mark_file(path, model_providers=["ollama"], model_ids=["model:cloud"])
        self.assertEqual(verify_file(path)["decision"], "pass")
        self.assertIn("_iot_ai_provenance", json.loads(path.read_text(encoding="utf-8")))

    def test_html_mark_and_verify(self) -> None:
        path = self.home / "index.html"
        path.write_text("<html><head></head><body>AI</body></html>", encoding="utf-8")
        mark_file(path, human_reviewed=True, editorially_responsible_party="IoT-AI.Tech")
        self.assertEqual(verify_file(path)["decision"], "pass")
        self.assertIn("iot-ai-provenance", path.read_text(encoding="utf-8"))

    def test_png_mark_and_verify(self) -> None:
        path = self.home / "image.png"
        path.write_bytes(PNG_1X1)
        result = mark_file(path, visible_label_present=True)
        self.assertEqual(result["decision"], "pass")
        self.assertEqual(verify_file(path)["decision"], "pass")

    def test_repeated_png_marking_keeps_one_provenance_chunk(self) -> None:
        path = self.home / "repeat.png"
        path.write_bytes(PNG_1X1)
        mark_file(path, visible_label_present=True, model_ids=["model-a"])
        mark_file(path, visible_label_present=True, model_ids=["model-b"])
        self.assertEqual(path.read_bytes().count(b"IOT-AI-Provenance"), 1)
        self.assertEqual(verify_file(path)["decision"], "pass")

    def test_csv_requires_external_interoperable_mark(self) -> None:
        path = self.home / "report.csv"
        path.write_text("name,value\nitem,1\n", encoding="utf-8")
        result = mark_file(path, visible_label_present=True)
        self.assertEqual(result["decision"], "needs-work")
        self.assertTrue(result["receipt"]["external_interoperable_mark_required"])

    def test_text_mark_has_visible_label(self) -> None:
        path = self.home / "post.txt"
        path.write_text("Launch content", encoding="utf-8")
        mark_file(path, visible_label_present=True)
        self.assertTrue(path.read_text(encoding="utf-8").startswith("IOT-AI-PROVENANCE: "))
        self.assertEqual(verify_file(path)["decision"], "pass")

    def test_tamper_is_detected(self) -> None:
        path = self.home / "tamper.md"
        path.write_text("safe", encoding="utf-8")
        mark_file(path)
        path.write_text(path.read_text(encoding="utf-8") + "changed", encoding="utf-8")
        self.assertEqual(verify_file(path)["decision"], "block")

    def test_public_interest_requires_editorial_control_or_label(self) -> None:
        path = self.home / "policy.md"
        path.write_text("Public policy text", encoding="utf-8")
        with self.assertRaises(ValueError):
            mark_file(path, public_interest=True)

    def test_deepfake_requires_visible_label(self) -> None:
        path = self.home / "synthetic.png"
        path.write_bytes(PNG_1X1)
        with self.assertRaises(ValueError):
            mark_file(path, deepfake=True)

    def test_unsupported_media_requires_external_mark(self) -> None:
        path = self.home / "audio.wav"
        path.write_bytes(b"RIFF-demo")
        result = mark_file(path, visible_label_present=True)
        self.assertEqual(result["decision"], "needs-work")
        self.assertTrue(result["receipt"]["external_interoperable_mark_required"])

    def test_literacy_receipt_is_pseudonymous_and_chained(self) -> None:
        first = record_literacy_receipt(self.home, subject_id="person-1", role="developer", curriculum_version="1.0", assessment="pass", refresher_due="2027-08-05")
        second = record_literacy_receipt(self.home, subject_id="person-2", role="operator", curriculum_version="1.0", assessment="pass", refresher_due="2027-08-05")
        self.assertNotEqual(first["subject_pseudonym"], second["subject_pseudonym"])
        self.assertNotIn("person-1", json.dumps(first))

    def test_evidence_chain_redacts_private_metadata(self) -> None:
        result = record_incident(self.home, {
            "system_id": "suite",
            "system_version": "6.6.0-beta.3",
            "severity": "low",
            "discovered_at": "2026-08-06T00:00:00Z",
            "summary": "Observed on " + ".".join(("192", "168", "50", "40")) + " under /" + "/".join(("home", "iot", "private")),
            "reportability": "not-assessed",
        })
        encoded = json.dumps(result)
        self.assertNotIn(".".join(("192", "168", "50", "40")), encoded)
        self.assertNotIn("/" + "/".join(("home", "iot")), encoded)
        self.assertIn("[PRIVATE_IP]", encoded)

    def test_evidence_chain_rejects_tampered_history(self) -> None:
        record_disclosure(self.home, surface="one", language="en")
        path = disclosure_receipts_path(self.home)
        path.write_text(path.read_text(encoding="utf-8").replace('"surface": "one"', '"surface": "changed"'), encoding="utf-8")
        self.assertEqual(verify_evidence_chain(path)["decision"], "block")
        with self.assertRaisesRegex(ValueError, "chain is invalid"):
            record_disclosure(self.home, surface="two", language="en")

    def test_concurrent_disclosure_receipts_preserve_hash_chain(self) -> None:
        def issue(index: int) -> None:
            record_disclosure(self.home, surface=f"surface-{index}", language="en")
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(issue, range(24)))
        result = verify_evidence_chain(disclosure_receipts_path(self.home))
        self.assertEqual(result["decision"], "pass", result["errors"])
        self.assertEqual(result["records"], 24)

    def test_partial_literacy_or_single_model_dossier_does_not_false_green(self) -> None:
        record_literacy_receipt(self.home, subject_id="person-1", role="developer", curriculum_version="1.0", assessment="pass", refresher_due="2027-08-05")
        dossier = {
            "provider": "example-provider",
            "model_id": "model-a",
            "model_version": "1",
            "license": "documented",
            "model_card_reference": "https://example.invalid/model-card",
            "capabilities": ["text"],
            "limitations": ["may be inaccurate"],
            "data_egress_profile": "cloud-opt-in",
            "last_verified_at": "2026-08-06T00:00:00Z",
        }
        register_model_dossier(self.home, dossier)
        status = runtime_compliance_status(self.home)
        self.assertEqual(status["controls"]["article_4_ai_literacy"], "implemented_unverified")
        self.assertEqual(status["controls"]["upstream_model_and_gpai_dossier"], "implemented_unverified")

    def test_model_dossier_validates_and_rejects_secrets(self) -> None:
        dossier = {
            "provider": "example-provider",
            "model_id": "model-a",
            "model_version": "1",
            "license": "documented",
            "model_card_reference": "https://example.invalid/model-card",
            "capabilities": ["text"],
            "limitations": ["may be inaccurate"],
            "data_egress_profile": "cloud-opt-in",
            "last_verified_at": "2026-08-06T00:00:00Z",
        }
        entry = register_model_dossier(self.home, dossier)
        self.assertEqual(entry["provider"], "example-provider")
        bad = {**dossier, "model_id": "model-b", "limitations": ["api" + "_key=" + "A" * 26]}
        with self.assertRaises(ValueError):
            register_model_dossier(self.home, bad)

    def test_upstream_register_requires_underlying_ollama_supplier(self) -> None:
        register = default_model_register()
        ollama = next(item for item in register["entries"] if item["suite_route"] == "ollama")
        self.assertTrue(ollama["underlying_model_provider_required"])
        self.assertTrue(register["policy"]["upstream_compliance_is_not_inherited"])

    def test_incident_record_is_evidence_only(self) -> None:
        result = record_incident(self.home, {
            "system_id": "suite",
            "system_version": "6.6.0-beta.3",
            "severity": "high",
            "discovered_at": "2026-08-06T00:00:00Z",
            "summary": "Provider returned wrong model identity",
            "reportability": "legal-review-required",
        })
        self.assertEqual(result["reportability"], "legal-review-required")
        self.assertFalse(result["evidence_frozen"])

    def test_change_reassessment_detects_intended_purpose(self) -> None:
        previous = default_system_card()
        current = {**previous, "intended_purpose": "employee ranking"}
        result = change_reassessment(previous, current)
        self.assertEqual(result["decision"], "reassessment-required")
        self.assertIn("intended_purpose", result["changed_fields"])

    def test_runtime_status_has_no_compliance_percentage(self) -> None:
        status = runtime_compliance_status(self.home)
        self.assertFalse(status["global_compliance_claim_allowed"])
        self.assertNotIn("score", status)
        self.assertEqual(status["production_decision"], "block")

    def test_compliance_role_is_selected(self) -> None:
        roles = {role.role_id for role in select_roles("Review EU AI Act Article 50 and GPAI compliance")}
        self.assertIn("eu-ai-act-compliance-reviewer", roles)

    @patch("iot_ai.agentic.select_candidates")
    def test_agentic_article_5_blocks_before_provider_selection(self, candidates) -> None:
        result = run_goal(self.home, "Build a social scoring engine for citizens", execute=True)
        candidates.assert_not_called()
        self.assertEqual(result["provider_calls"], 0)
        self.assertEqual(result["decision"], "blocked")

    @patch("iot_ai.meeting.delegate")
    def test_meeting_article_5_blocks_before_provider_calls(self, delegate_mock) -> None:
        with self.assertRaisesRegex(PermissionError, "Article 5"):
            meeting_start(self.home, "Build social scoring for citizens", ["codex"], quorum=1)
        delegate_mock.assert_not_called()

    @patch("iot_ai.cli.mesh_delegate")
    def test_provider_doctor_surfaces_article_50_notice(self, delegate_mock) -> None:
        delegate_mock.return_value = {"status": "pass", "output": "OK"}
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = main([
                "--home", str(self.home), "provider", "doctor",
                "--provider", "ollama", "--prompt", "Return OK",
            ])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["article_50"]["disclosure"]["ai_interaction"])
        self.assertEqual(payload["content_provenance"]["transparency_profile"], "eu-ai-act-article-50-v1")
        self.assertFalse(payload["global_compliance_claim_allowed"])

    def test_cli_compliance_status_and_screen(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = main(["--home", str(self.home), "compliance", "status"])
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(stdout.getvalue())["global_compliance_claim_allowed"])
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = main(["--home", str(self.home), "compliance", "screen", "--text", "Audit social scoring controls"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["decision"], "review-only")

    def test_developer_preview_release_gate_passes(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = release_gate(root, profile="developer-preview")
        self.assertEqual(result["decision"], "pass", result["errors"])
        self.assertFalse(result["global_compliance_claim_allowed"])
        self.assertIn("article_4_ai_literacy", result["unverified_runtime_or_organisational_controls"])

    def test_production_release_gate_blocks(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = release_gate(root, profile="production")
        self.assertEqual(result["decision"], "block")
        self.assertIn("production-profile-requires-external-legal-and-live-deployment-evidence", result["errors"])

    def test_runtime_output_provenance_is_machine_readable_and_hash_bound(self) -> None:
        content = '{"answer":"evidence-bound"}'
        payload = runtime_output_provenance(
            content,
            content_type="application/json",
            model_providers=["provider-b", "provider-a", "provider-a"],
            model_ids=["model-2", "model-1"],
        )
        self.assertEqual(payload["content_sha256"], hashlib.sha256(content.encode()).hexdigest())
        self.assertEqual(payload["model_providers"], ["provider-a", "provider-b"])
        self.assertEqual(payload["transparency_profile"], "eu-ai-act-article-50-v1")
        self.assertIn("not-authenticity", payload["claim"])



if __name__ == "__main__":
    unittest.main()
