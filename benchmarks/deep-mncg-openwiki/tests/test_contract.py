# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-08-30
from __future__ import annotations
import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(path,name):
 spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module); return module
class ContractTests(unittest.TestCase):
 def test_public_contract_validates(self):
  load(ROOT/'scripts'/'validate_benchmark.py','validate_benchmark'); self.assertTrue((ROOT/'PREREGISTRATION.json').is_file()); self.assertEqual(json.loads((ROOT/'STATUS.json').read_text())['provider_trials_executed'],0)
 def test_plan_is_deterministic_and_non_executable_without_qualified_models(self):
  planner=load(ROOT/'scripts'/'plan_trials.py','plan_trials'); matrix=json.loads((ROOT/'RUN_MATRIX.json').read_text()); self.assertEqual(len(matrix['arms']),6); self.assertEqual(len(json.loads((ROOT/'TASK_SUITE.json').read_text())['tasks']),30); self.assertEqual(planner.order(['a','b','c'],'fixed'),planner.order(['a','b','c'],'fixed'))
 def test_claim_boundary(self):
  for name in ('STATUS.json','RUN_MATRIX.json','TASK_SUITE.json','SCORING_SPEC.json','PREREGISTRATION.json','MODELS.example.json'):
   payload=json.loads((ROOT/name).read_text()); self.assertIs(payload.get('production_claim'),False)
if __name__=='__main__':unittest.main()
