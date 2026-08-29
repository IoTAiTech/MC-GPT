# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 4.0.0 | Date: 2026-08-30
"""Fourth-pass malformed-contract fail-closed hardening for PR 14."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def bootstrap() -> None:
    for name in (
        "tools/_pr14_deep_hardening_once_v3_20260830.py",
        "tools/_pr14_deep_hardening_once_v2_20260830.py",
        "tools/_pr14_deep_hardening_once_20260830.py",
    ):
        candidate = ROOT / name
        if candidate.is_file():
            subprocess.run([sys.executable, str(candidate)], cwd=ROOT, check=True)
            return
    required = [
        ROOT / "tests/test_minimum_change_deep.py",
        ROOT / "src/iot_ai/minimum_change.py",
    ]
    if not all(path.is_file() for path in required):
        raise RuntimeError("No prior hardening chain and no hardened persistent files found")


def harden_nested_contract_types() -> None:
    path = ROOT / "src/iot_ai/minimum_change.py"
    text = path.read_text(encoding="utf-8")

    old = '''    authority = contract.get("authority_precondition") or {}
    acceptance = bool(str(task.get("acceptance_criteria") or "").strip())
'''
    new = '''    authority = contract.get("authority_precondition") or {}
    if not isinstance(authority, Mapping):
        errors.append("authority-type")
        authority = {}
    acceptance = bool(str(task.get("acceptance_criteria") or "").strip())
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif "authority-type" not in text:
        raise RuntimeError("authority type hardening target not found")

    old = '''    rungs = list(contract.get("rungs") or [])
    expected_rungs = [
'''
    new = '''    raw_rungs = contract.get("rungs") or []
    if not isinstance(raw_rungs, list):
        errors.append("rungs-type")
        rungs = []
    else:
        rungs = list(raw_rungs)
    expected_rungs = [
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif "rungs-type" not in text:
        raise RuntimeError("rungs type hardening target not found")

    old = '''    if dict(contract.get("default_budgets") or {}) != ZERO_DEFAULT_BUDGETS:
        errors.append("default-budgets")
    if tuple(contract.get("non_negotiable_controls") or ()) != NON_NEGOTIABLE_CONTROLS:
        errors.append("non-negotiable-controls")
    if tuple(contract.get("required_assessment_fields") or ()) != _REQUIRED_ASSESSMENT_FIELDS:
        errors.append("assessment-fields")
    claim = contract.get("claim_boundary") or {}
    if claim.get("production_claim") is not False:
        errors.append("production-claim")
'''
    new = '''    raw_budgets = contract.get("default_budgets") or {}
    if not isinstance(raw_budgets, Mapping):
        errors.append("default-budgets-type")
        raw_budgets = {}
    if dict(raw_budgets) != ZERO_DEFAULT_BUDGETS:
        errors.append("default-budgets")

    raw_controls = contract.get("non_negotiable_controls") or ()
    if not isinstance(raw_controls, (list, tuple)):
        errors.append("non-negotiable-controls-type")
        raw_controls = ()
    if tuple(raw_controls) != NON_NEGOTIABLE_CONTROLS:
        errors.append("non-negotiable-controls")

    raw_assessment_fields = contract.get("required_assessment_fields") or ()
    if not isinstance(raw_assessment_fields, (list, tuple)):
        errors.append("assessment-fields-type")
        raw_assessment_fields = ()
    if tuple(raw_assessment_fields) != _REQUIRED_ASSESSMENT_FIELDS:
        errors.append("assessment-fields")

    claim = contract.get("claim_boundary") or {}
    if not isinstance(claim, Mapping):
        errors.append("claim-boundary-type")
        claim = {}
    if claim.get("production_claim") is not False:
        errors.append("production-claim")
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif "default-budgets-type" not in text:
        raise RuntimeError("nested contract type block target not found")

    path.write_text(text, encoding="utf-8")


def add_malformed_contract_fuzz_tests() -> None:
    path = ROOT / "tests/test_minimum_change_deep.py"
    text = path.read_text(encoding="utf-8")
    marker = "class ContractMalformedShapeFuzzTests(unittest.TestCase):"
    if marker in text:
        return
    insertion = r'''

class ContractMalformedShapeFuzzTests(unittest.TestCase):
    def test_nested_contract_type_matrix_fails_closed(self) -> None:
        fields = (
            "authority_precondition",
            "rungs",
            "default_budgets",
            "non_negotiable_controls",
            "required_assessment_fields",
            "claim_boundary",
        )
        malformed = (1, "invalid", b"invalid", math.nan)
        for field in fields:
            for value in malformed:
                with self.subTest(field=field, value=type(value).__name__):
                    contract = compile_contract(task(51))
                    contract[field] = value
                    contract["contract_sha256"] = "0" * 64
                    result = validate_contract(contract)
                    self.assertEqual(result["decision"], "block")
                    self.assertIsInstance(result["errors"], list)

    def test_seeded_random_contract_mutations_never_raise(self) -> None:
        rng = random.Random(2026083004)
        candidate_values = [
            None,
            0,
            1,
            -1,
            "",
            "invalid",
            b"bytes",
            [],
            {},
            math.nan,
            math.inf,
        ]
        canonical_contract = compile_contract(task(52))
        keys = list(canonical_contract)
        for _ in range(1000):
            contract = copy.deepcopy(canonical_contract)
            for _ in range(rng.randint(1, 4)):
                operation = rng.randrange(3)
                if operation == 0 and contract:
                    contract.pop(rng.choice(list(contract)), None)
                elif operation == 1:
                    contract[rng.choice(keys)] = rng.choice(candidate_values)
                else:
                    contract["unknown_" + str(rng.randrange(100))] = rng.choice(
                        candidate_values
                    )
            try:
                result = validate_contract(contract)
            except Exception as exc:  # pragma: no cover - assertion provides diagnostics
                self.fail(f"validate_contract raised {type(exc).__name__}: {exc}")
            self.assertIn(result["decision"], {"pass", "block"})
            self.assertIsInstance(result["errors"], list)
'''
    needle = "\n\nif __name__ == \"__main__\":\n    unittest.main()\n"
    if needle not in text:
        raise RuntimeError("deep test footer not found")
    path.write_text(text.replace(needle, insertion + needle, 1), encoding="utf-8")


def create_mutation_tool() -> None:
    source = ROOT / "tools/_pr14_curated_mutation_once_v3_20260830.py"
    target = ROOT / "tools/_pr14_curated_mutation_once_v4_20260830.py"
    if source.is_file():
        content = source.read_text(encoding="utf-8").replace(
            "# Version: 3.0.0 | Date: 2026-08-30",
            "# Version: 4.0.0 | Date: 2026-08-30",
            1,
        ).replace(
            "iot-ai.curated-mutation-report.v3",
            "iot-ai.curated-mutation-report.v4",
            1,
        )
        target.write_text(content, encoding="utf-8")
        return
    raise RuntimeError("v3 mutation tool was not produced by the bootstrap chain")


def main() -> int:
    bootstrap()
    harden_nested_contract_types()
    add_malformed_contract_fuzz_tests()
    create_mutation_tool()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
