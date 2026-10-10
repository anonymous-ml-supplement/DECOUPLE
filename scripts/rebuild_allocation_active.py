#!/usr/bin/env python3
import csv, json, math, random, sys
from collections import defaultdict
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
work = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else repo / 'reproduced/work'
root = work / '10_PILOT/STEP4_V2_CLEAN_REBUILD'
logical_path = root / '04_OUTPUTS/STEP4V2_D11_FINAL_RANDOM_AWARE_ANALYSIS/D11_FINAL_ALL_LOGICAL_RESULTS.tsv'
outdir = repo / 'reproduced/paper'
outdir.mkdir(parents=True, exist_ok=True)
summary_path = outdir / 'allocation_active_summary.tsv'
budget_path = outdir / 'allocation_active_by_budget.tsv'

D11=[0.05,0.10,0.20,0.30,0.40,0.50,0.60,0.70,0.80,0.90,1.00]
BOOTSTRAP_REPLICATES=10000
BOOTSTRAP_SEED=20260829

def read_tsv(p):
    with p.open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f,delimiter='\t'))
def parse_steps(x): return tuple(json.loads(x))
def percentile(values,q):
    xs=sorted(values); pos=(len(xs)-1)*q; lo=math.floor(pos); hi=math.ceil(pos)
    if lo==hi: return xs[lo]
    frac=pos-lo; return xs[lo]*(1-frac)+xs[hi]*frac
def fmt(x): return '' if x is None else f'{float(x):.9f}'
def trapz_area(vals):
    # normalized over 0.05..1.00
    s=0.0
    for i in range(len(D11)-1):
        s += 0.5*(vals[i]+vals[i+1])*(D11[i+1]-D11[i])
    return s/(D11[-1]-D11[0])

def write_tsv(p,rows):
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()),delimiter='\t'); w.writeheader(); w.writerows(rows)

logical=read_tsv(logical_path)
rows_by_method=defaultdict(list)
for r in logical:
    x=dict(r); x['budget_f']=round(float(r['budget']),8); x['terminal_Z_i']=int(r['terminal_Z']); x['steps_t']=parse_steps(r['selected_steps'])
    rows_by_method[(r['benchmark'],r['method'])].append(x)

de_index={}
for (bench,method),rows in rows_by_method.items():
    if method!='DECOUPLE': continue
    for r in rows:
        k=(bench,r['instance_id'],r['budget_f'])
        if k in de_index: raise RuntimeError(f'duplicate DECOUPLE key {k}')
        de_index[k]=r

allowed={'H-only','p-only','Random','Step-PRM','PRM@BoK','ToolPRM-GRPO'}
pairs=sorted((b,m) for (b,m) in rows_by_method if m in allowed)
if len(pairs)!=17: raise RuntimeError(f'expected 17 pairs, got {len(pairs)}: {pairs}')

budget_rows=[]; pooled_units=defaultdict(list); uncond_by_pair_budget={}
for bench,baseline in pairs:
    base_rows=rows_by_method[(bench,baseline)]
    by_budget=defaultdict(list)
    for r in base_rows: by_budget[r['budget_f']].append(r)
    for budget in D11:
        b=round(budget,8); raw=by_budget[b]; units=[]; is_random=baseline=='Random'
        if is_random:
            by_inst=defaultdict(list)
            for br in raw: by_inst[br['instance_id']].append(br)
            for iid,reps in sorted(by_inst.items()):
                if len(reps)!=10: raise RuntimeError(f'Random reps != 10: {bench} {iid} {b}')
                de=de_index[(bench,iid,b)]
                for br in reps:
                    units.append({'instance_id':iid,'replicate':int(br['random_replicate']), 'active':int(de['steps_t']!=br['steps_t']), 'delta_z':de['terminal_Z_i']-br['terminal_Z_i']})
        else:
            seen=set()
            for br in raw:
                iid=br['instance_id']
                if iid in seen: raise RuntimeError(f'duplicate deterministic {bench} {baseline} {iid} {b}')
                seen.add(iid); de=de_index[(bench,iid,b)]
                units.append({'instance_id':iid,'replicate':None,'active':int(de['steps_t']!=br['steps_t']), 'delta_z':de['terminal_Z_i']-br['terminal_Z_i']})
        active=[u for u in units if u['active']]
        rho=len(active)/len(units); active_delta=(sum(u['delta_z'] for u in active)/len(active)) if active else None
        uncond=sum(u['delta_z'] for u in units)/len(units)
        recon=0.0 if not active else rho*active_delta
        if not math.isclose(uncond,recon,abs_tol=5e-12): raise RuntimeError('decomposition mismatch')
        uncond_by_pair_budget[(bench,baseline,b)]=uncond
        budget_rows.append({
            'benchmark':bench,'baseline':baseline,'budget':f'{b:.2f}',
            'unit_definition':'instance_budget_replicate' if is_random else 'instance_budget',
            'comparison_units':len(units),'active_units':len(active),'selection_disagreement_rate':fmt(rho),
            'active_wins':sum(u['delta_z']>0 for u in active),'active_ties':sum(u['delta_z']==0 for u in active),'active_losses':sum(u['delta_z']<0 for u in active),
            'active_terminal_advantage':fmt(active_delta),'unconditional_terminal_delta':fmt(uncond),
            'exact_decomposition_reconstructed_delta':fmt(recon),'active_identification_status':'IDENTIFIED' if active else 'NO_ACTIVE_UNITS'})
        for u in units: pooled_units[(bench,baseline)].append({**u,'budget':b})

rng=random.Random(BOOTSTRAP_SEED); summaries=[]
for bench,baseline in pairs:
    units=pooled_units[(bench,baseline)]; by_inst=defaultdict(list)
    for u in units: by_inst[u['instance_id']].append(u)
    iids=sorted(by_inst); active=[u for u in units if u['active']]; active_n=len(active); coverage=active_n/len(units)
    delta=(sum(u['delta_z'] for u in active)/active_n) if active_n else None
    # Collapse each original-instance cluster to its active numerator and denominator.
    # The bootstrap still draws the same clusters with the same Python RNG sequence as
    # the frozen implementation, but avoids repeatedly iterating over every budget/
    # replicate unit inside a sampled cluster.
    cluster_active = {
        iid: (
            sum(u['delta_z'] for u in by_inst[iid] if u['active']),
            sum(1 for u in by_inst[iid] if u['active']),
        )
        for iid in iids
    }
    boots=[]; undefined=0
    if active_n:
        for _ in range(BOOTSTRAP_REPLICATES):
            sample=[rng.choice(iids) for __ in range(len(iids))]
            num=0.0; den=0
            for iid in sample:
                n_i, d_i = cluster_active[iid]
                num += n_i
                den += d_i
            if den==0: undefined+=1
            else: boots.append(num/den)
        lo=percentile(boots,.025); hi=percentile(boots,.975)
    else: lo=hi=None
    uncond=sum(u['delta_z'] for u in units)/len(units)
    areas=[uncond_by_pair_budget[(bench,baseline,round(b,8))] for b in D11]
    area=trapz_area(areas)
    summaries.append({
        'benchmark':bench,'baseline':baseline,'unit_definition':'instance_budget_replicate' if baseline=='Random' else 'instance_budget',
        'original_instance_clusters':len(iids),'d11_comparison_units':len(units),'d11_active_units':active_n,'d11_disagreement_coverage':fmt(coverage),
        'pooled_active_terminal_advantage':fmt(delta),'bootstrap_ci_low':fmt(lo),'bootstrap_ci_high':fmt(hi),
        'bootstrap_draws_total':BOOTSTRAP_REPLICATES if active_n else 0,'bootstrap_draws_defined':len(boots) if active_n else 0,'bootstrap_draws_undefined':undefined if active_n else 0,
        'bootstrap_seed':BOOTSTRAP_SEED,'bootstrap_cluster':'original_benchmark_instance','pooled_unconditional_terminal_delta':fmt(uncond),
        'frozen_unconditional_d11_area_delta':fmt(area),'active_identification_status':'IDENTIFIED' if active_n else 'NO_ACTIVE_UNITS',
        'analysis_status':'RETROSPECTIVE_EXPLANATORY','confirmatory_pvalue':'NO'})
write_tsv(budget_path,budget_rows); write_tsv(summary_path,summaries)
print(f'PASS allocation_active pairs={len(summaries)} budget_rows={len(budget_rows)}')
print(f'OUTPUT={summary_path}')
