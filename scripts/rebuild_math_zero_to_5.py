#!/usr/bin/env python3
import csv, json, sys
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
work = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else repo/'reproduced/work'
base = work/'10_PILOT/STEP3/04_OUTPUTS/STEP3F_POST_LABELS_AND_SINGLETON_GAINS/STEP3F_BASE_OUTCOMES.jsonl'
d11 = work/'10_PILOT/STEP4_V2_CLEAN_REBUILD/04_OUTPUTS/STEP4V2_D11_FINAL_RANDOM_AWARE_ANALYSIS/D11_FINAL_ALL_LOGICAL_RESULTS.tsv'
outdir = repo/'reproduced/paper'; outdir.mkdir(parents=True,exist_ok=True)
out = outdir/'math_zero_to_5_accounting.tsv'
base_z={}
with base.open() as f:
    for line in f:
        if not line.strip(): continue
        r=json.loads(line)
        if r['benchmark'] in {'Math-Shepherd','MATH_SHEPHERD'} and r['base_outcome_status']=='IDENTIFIED':
            base_z[r['instance_id']]=int(r['base_outcome_Z0'])
post={}
with d11.open() as f:
    for r in csv.DictReader(f,delimiter='\t'):
        if r['benchmark']=='Math-Shepherd' and r['method']=='DECOUPLE' and abs(float(r['budget'])-0.05)<1e-12:
            post[r['instance_id']]=int(r['terminal_Z'])
if len(base_z)!=50 or len(post)!=50 or set(base_z)!=set(post):
    raise RuntimeError(f'panel mismatch base={len(base_z)} post={len(post)}')
counts={'base_success':0,'base_failure':0,'success_preserved':0,'success_harmed':0,'failure_rescued':0,'failure_unrescued':0}
for iid,z0 in base_z.items():
    z=post[iid]
    if z0==1:
        counts['base_success']+=1
        counts['success_preserved']+=int(z==1)
        counts['success_harmed']+=int(z==0)
    else:
        counts['base_failure']+=1
        counts['failure_rescued']+=int(z==1)
        counts['failure_unrescued']+=int(z==0)
u0=sum(base_z.values())/50
u5=sum(post.values())/50
row={**counts,'n':50,'U0':f'{u0:.2f}','U5':f'{u5:.2f}','delta_U':f'{u5-u0:.2f}','identity_delta':f'{(counts["failure_rescued"]-counts["success_harmed"])/50:.2f}'}
with out.open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=row.keys(),delimiter='\t'); w.writeheader(); w.writerow(row)
expected={'base_success':20,'base_failure':30,'success_preserved':7,'success_harmed':13,'failure_rescued':0,'failure_unrescued':30}
if any(row[k]!=v for k,v in expected.items()) or abs(u0-.40)>1e-12 or abs(u5-.14)>1e-12:
    raise RuntimeError(f'paper accounting mismatch: {row}')
print('PASS math_zero_to_5 20 base successes; 13 harmed; 0/30 failures rescued; U0=.40 U5=.14')
print(f'OUTPUT={out}')
