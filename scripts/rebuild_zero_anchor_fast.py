#!/usr/bin/env python3
"""Zero-API reconstruction of the non-permutation zero-anchor point estimates.

This intentionally does not rerun the 100,000-draw zero-anchor permutation test.
It reconstructs U(0), positive-budget maxima, positive-budget VEF AUBC, and
zero-anchored VEF AUBC from frozen per-instance/base and D11 aggregate authority.
"""
import csv, json, math, sys
from collections import defaultdict
from pathlib import Path
import numpy as np

work = Path(sys.argv[1]).resolve()
root = work / '10_PILOT/STEP4_V2_CLEAN_REBUILD'
base = work / '10_PILOT/STEP3/04_OUTPUTS/STEP3F_POST_LABELS_AND_SINGLETON_GAINS/STEP3F_BASE_OUTCOMES.jsonl'
agg = root / '04_OUTPUTS/STEP4V2_D11_FINAL_RANDOM_AWARE_ANALYSIS/D11_FINAL_TERMINAL_UTILITY.tsv'
outdir = root / '04_OUTPUTS/STEP4V2_POSTD11_ZERO_ANCHOR_FAST'
outdir.mkdir(parents=True, exist_ok=True)
out = outdir / 'ZERO_ANCHOR_FAST_SUMMARY.tsv'

budgets = np.array([5,10,20,30,40,50,60,70,80,90,100], dtype=float)
xpos = budgets/100.0
xzero = np.concatenate(([0.0], xpos))
methods = ['DECOUPLE','H-only','p-only','Random','Step-PRM','PRM@BoK']
alias = {'BFCL':'BFCL','MATH_SHEPHERD':'Math-Shepherd'}

z=[]
with base.open(encoding='utf-8') as f:
    for line in f:
        if line.strip(): z.append(json.loads(line))
u0={}
for src,dst in alias.items():
    vals=[float(r['base_outcome_Z0']) for r in z if r['benchmark']==src and r['base_outcome_status']=='IDENTIFIED' and r['base_outcome_Z0'] is not None]
    exp=25 if dst=='BFCL' else 50
    if len(vals)!=exp: raise SystemExit(f'FAIL zero_anchor_n {dst}: {len(vals)} != {exp}')
    u0[dst]=float(np.mean(vals))

vals={}
with agg.open(encoding='utf-8', newline='') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        b=float(str(r['budget']).replace('%',''))
        if 0<b<=1: b*=100
        vals[(r['benchmark'],r['method'],int(round(b)))]=float(r['terminal_utility'])

rows=[]
for bench in ['BFCL','Math-Shepherd']:
    for method in methods:
        u=np.array([vals[(bench,method,int(b))] for b in budgets], dtype=float)
        frontier=np.maximum.accumulate(u)
        aplus=float(np.trapezoid(frontier,xpos)/(xpos[-1]-xpos[0]))
        fzero=np.maximum(u0[bench],frontier)
        azero=float(np.trapezoid(np.concatenate(([u0[bench]],fzero)),xzero))
        rows.append({
            'benchmark':bench,'method':method,'U0':u0[bench],
            'positive_budget_max_exact_utility':float(np.max(u)),
            'max_verified_minus_U0':float(np.max(u)-u0[bench]),
            'positive_VEF_AUBC_5_100':aplus,
            'zero_anchored_VEF_AUBC_0_100':azero,
        })

fields=list(rows[0])
with out.open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields,delimiter='\t'); w.writeheader(); w.writerows(rows)

print(f'PASS zero_anchor_fast rows={len(rows)}')
print(f'BFCL_U0={u0["BFCL"]:.12g}')
print(f'Math-Shepherd_U0={u0["Math-Shepherd"]:.12g}')
print(f'OUTPUT={out}')
