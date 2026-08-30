#!/usr/bin/env python3
"""Create a deterministic counterbalanced trial plan without provider calls."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path

def order(values,key): return sorted(values,key=lambda value:hashlib.sha256(f'{key}:{value}'.encode()).hexdigest())
def main()->int:
 p=argparse.ArgumentParser(); p.add_argument('--root',default='.'); p.add_argument('--stage',choices=('smoke','pilot','confirmatory'),required=True); p.add_argument('--models',required=True); p.add_argument('--output',required=True); a=p.parse_args()
 root=Path(a.root).resolve(); matrix=json.loads((root/'RUN_MATRIX.json').read_text()); tasks=json.loads((root/'TASK_SUITE.json').read_text())['tasks']; models=json.loads(Path(a.models).read_text())['models']; stage=matrix['stages'][a.stage]
 selected=[row for row in tasks if a.stage in row['enabled_stages']][:stage['tasks']]; enabled=[row for row in models if row.get('enabled') is True]; rows=[]
 for task in selected:
  for model in enabled:
   for rep in range(1,stage['repetitions']+1):
    block=f"{task['task_id']}:{model['slot_id']}:{rep}"
    for position,arm in enumerate(order(stage['arms'],block),1):
     exact=(model.get('model_requested') not in (None,'','REQUIRED_AT_RUNTIME') and model.get('model_requested')==model.get('model_served') and isinstance(model.get('qualification_receipt_sha256'),str) and len(model['qualification_receipt_sha256'])==64)
     trial_id=hashlib.sha256(f"{matrix['benchmark_id']}:{block}:{arm}".encode()).hexdigest()[:24]
     rows.append({'trial_id':trial_id,'task_id':task['task_id'],'upstream_task_name':task['upstream_task_name'],'arm_id':arm,'provider_slot':model['slot_id'],'model_requested':model.get('model_requested'),'model_served':model.get('model_served'),'repetition':rep,'order_in_block':position,'executable':exact})
 out=Path(a.output); out.mkdir(parents=True,exist_ok=True); payload={'schema':'iot-ai.deep-benchmark-trial-plan.v1','benchmark_id':matrix['benchmark_id'],'stage':a.stage,'qualified_provider_slots':len(enabled),'trial_count':len(rows),'executable_trial_count':sum(bool(r['executable']) for r in rows),'trials':rows,'production_claim':False}; (out/'trial-plan.json').write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
 fields=list(rows[0]) if rows else ['trial_id','task_id','upstream_task_name','arm_id','provider_slot','model_requested','model_served','repetition','order_in_block','executable']
 with (out/'trial-plan.csv').open('w',newline='',encoding='utf-8') as stream:
  writer=csv.DictWriter(stream,fieldnames=fields); writer.writeheader(); writer.writerows(rows)
 print(json.dumps({'decision':'pass','stage':a.stage,'trial_count':len(rows),'executable_trial_count':sum(bool(r['executable']) for r in rows),'output':str(out),'production_claim':False},indent=2,sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
