#!/usr/bin/env python3
import csv, json, math, statistics, sys
from collections import defaultdict
from pathlib import Path

try:
    import numpy as np
except Exception as e:
    raise SystemExit('numpy is required for K=4 sensitivity reproduction') from e

repo = Path(__file__).resolve().parents[1]
work = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else repo / 'reproduced' / 'work'
base = work / '10_PILOT/STEP1/04_OUTPUTS/STEP1D_SEMANTIC/SEMANTIC_CLASSES_PT'
out = work / '10_PILOT/STEP4_V2_CLEAN_REBUILD/04_OUTPUTS/STEP4V2_K4_K8_ZERO_API_SENSITIVITY'
out.mkdir(parents=True, exist_ok=True)

class_rows = defaultdict(list)
with (base/'semantic_class_index.jsonl').open(encoding='utf-8') as f:
    for line in f:
        if line.strip():
            r=json.loads(line)
            class_rows[(r['benchmark'],r['instance_id'],int(r['step_index']))].append(r)

scores={}
with (base/'semantic_candidate_scores.jsonl').open(encoding='utf-8') as f:
    for line in f:
        if line.strip():
            r=json.loads(line)
            scores[(r['benchmark'],r['instance_id'],int(r['step_index']))]=r

if len(class_rows)!=631 or len(scores)!=631:
    raise SystemExit(f'FAIL=K4_INPUT_COUNT classes={len(class_rows)} scores={len(scores)}')

def normalized_entropy(rows, K):
    counts=[]
    for r in rows:
        c=sum(1 for i in r['continuation_indices'] if int(i) <= K)
        if c:
            counts.append(c)
    probs=[c/K for c in counts]
    h=-sum(p*math.log(p) for p in probs)
    return h/math.log(K), len(counts)

def rankdata(vals):
    idx=sorted(range(len(vals)), key=lambda i: vals[i])
    ranks=[0.0]*len(vals)
    i=0
    while i<len(idx):
        j=i+1
        while j<len(idx) and vals[idx[j]]==vals[idx[i]]:
            j+=1
        avg=((i+1)+j)/2.0
        for k in idx[i:j]: ranks[k]=avg
        i=j
    return ranks

def corr(a,b):
    return float(np.corrcoef(np.asarray(a,float),np.asarray(b,float))[0,1])

rows=[]
for key in sorted(class_rows):
    b,i,t=key
    p4,k4n=normalized_entropy(class_rows[key],4)
    p8_recon,k8n=normalized_entropy(class_rows[key],8)
    p8=float(scores[key]['p_t'])
    rows.append({
        'benchmark':b,'instance_id':i,'step_index':t,
        'p_k4_subsample':p4,'p_k8_reconstructed':p8_recon,'p_k8_frozen':p8,
        'k8_reconstruction_abs_diff':abs(p8_recon-p8),
        'k4_vs_k8_abs_diff':abs(p4-p8),
        'k4_unique_classes':k4n,'k8_unique_classes':k8n,
    })

cand=out/'K4_VS_K8_CANDIDATE_LEVEL.tsv'
cols=list(rows[0].keys())
with cand.open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=cols,delimiter='\t',lineterminator='\n'); w.writeheader(); w.writerows(rows)

def summarize(sub):
    a=[r['p_k4_subsample'] for r in sub]; b=[r['p_k8_frozen'] for r in sub]
    d=[abs(x-y) for x,y in zip(a,b)]
    return {
        'n':len(sub),
        'pearson':corr(a,b),
        'spearman':corr(rankdata(a),rankdata(b)),
        'mae':sum(d)/len(d),
        'median_abs_diff':statistics.median(d),
        'exact_equal_fraction':sum(x==y for x,y in zip(a,b))/len(a),
    }

summary=[]
for bench in ['BFCL','Math-Shepherd','ToolAlpaca']:
    s=summarize([r for r in rows if r['benchmark']==bench]); s={'benchmark':bench,**s}; summary.append(s)
summary.append({'benchmark':'ALL',**summarize(rows)})
sp=out/'K4_VS_K8_SUMMARY.tsv'
cols=['benchmark','n','pearson','spearman','mae','median_abs_diff','exact_equal_fraction']
with sp.open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=cols,delimiter='\t',lineterminator='\n'); w.writeheader(); w.writerows(summary)

max_recon=max(r['k8_reconstruction_abs_diff'] for r in rows)
print(f'PASS=K4_REBUILT_FROM_FROZEN_K8_CLASSES')
print(f'CANDIDATES={len(rows)}')
print(f'K8_RECON_MAX_ABS_DIFF={max_recon:.17g}')
print(f'POOLED_SPEARMAN={summary[-1]["spearman"]:.15f}')
print(f'OUTPUT={sp}')
