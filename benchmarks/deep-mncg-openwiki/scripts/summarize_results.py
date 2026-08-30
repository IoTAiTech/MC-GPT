#!/usr/bin/env python3
"""Summarize immutable trial receipts with paired descriptive statistics."""
from __future__ import annotations
import argparse,json,math,random,statistics
from collections import defaultdict
from pathlib import Path
METRICS=('source_lines_added','input_tokens','output_tokens','provider_cost_usd','total_duration_seconds')
def med(v): return statistics.median(v) if v else None
def iqr(v): return None if len(v)<4 else (lambda q:q[2]-q[0])(statistics.quantiles(sorted(v),n=4,method='inclusive'))
def wilson(s,n,z=1.959963984540054):
 if not n:return [None,None]
 p=s/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; h=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d; return [max(0,c-h),min(1,c+h)]
def boot(v,seed=20260830,it=10000):
 if not v:return [None,None]
 r=random.Random(seed); samples=sorted(statistics.median([v[r.randrange(len(v))] for _ in v]) for _ in range(it)); return [samples[int(.025*it)],samples[int(.975*it)]]
def hard(row):
 g=row.get('hard_gates') or {}; return row.get('status')=='pass' and all(g.get(k) is True for k in ('security_privacy_passed','data_loss_rollback_passed','accessibility_passed','model_identity_passed','contamination_absent','clean_patch_boundary_passed'))
def main()->int:
 p=argparse.ArgumentParser(); p.add_argument('--results',required=True); p.add_argument('--output',required=True); a=p.parse_args(); rows=[json.loads(x.read_text()) for x in sorted(Path(a.results).glob('*.json'))]; by=defaultdict(list)
 for row in rows:by[row['arm_id']].append(row)
 arms={}
 for arm,items in sorted(by.items()):
  passed=[x for x in items if hard(x)]; arms[arm]={'attempted':len(items),'hard_gate_passed':len(passed),'success_rate':len(passed)/len(items) if items else None,'success_wilson_95':wilson(len(passed),len(items)),'metrics_on_success':{m:{'median':med([x['metrics'][m] for x in passed if x['metrics'].get(m) is not None]),'iqr':iqr([x['metrics'][m] for x in passed if x['metrics'].get(m) is not None])} for m in METRICS}}
 blocks=defaultdict(dict)
 for row in rows:blocks[(row['task_id'],row['provider_slot'],row['model_served'],row['repetition'],row['seed'])][row['arm_id']]=row
 comparisons=[]
 for treatment in ('B_SIMPLE_YAGNI','C_PONYTAIL_PINNED','D_MNCG','E_OPENWIKI','F_MNCG_OPENWIKI'):
  pairs=[(b['A_BASELINE'],b[treatment]) for b in blocks.values() if 'A_BASELINE' in b and treatment in b and hard(b['A_BASELINE']) and hard(b[treatment])]; stats={}
  for m in METRICS:
   diffs=[other['metrics'][m]-base['metrics'][m] for base,other in pairs if base['metrics'].get(m) is not None and other['metrics'].get(m) is not None]; stats[m]={'pairs':len(diffs),'median_difference':med(diffs),'iqr_difference':iqr(diffs),'paired_bootstrap_95':boot(diffs)}
  comparisons.append({'comparison':f'{treatment}-A_BASELINE','successful_pairs':len(pairs),'metrics':stats})
 minpairs=min((m['pairs'] for c in comparisons for m in c['metrics'].values()),default=0); out={'schema':'iot-ai.deep-benchmark-summary.v1','benchmark_id':'mcgpt-mncg-openwiki-2026-01','trial_count':len(rows),'valid_trial_count':sum(isinstance(x.get('receipt_sha256'),str) for x in rows),'arms':arms,'comparisons':comparisons,'claim_decision':'eligible_for_internal_review' if minpairs>=10 else 'insufficient_evidence','production_claim':False}; Path(a.output).parent.mkdir(parents=True,exist_ok=True); Path(a.output).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n'); print(json.dumps(out,indent=2,sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
