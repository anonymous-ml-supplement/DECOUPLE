#!/usr/bin/env python3
import ast, csv, json, math, sys
from collections import defaultdict
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
work = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else repo / 'reproduced/work'
step4 = work / '10_PILOT/STEP4_V2_CLEAN_REBUILD'
paperdir = repo / 'reproduced/paper'
paperdir.mkdir(parents=True, exist_ok=True)

static = step4 / '04_OUTPUTS/STEP4V2_04D_FULL_20PT_SELECTION_MATERIALIZATION/STEP2A/static_baseline_scores.jsonl'
d11 = step4 / '04_OUTPUTS/STEP4V2_D11_FINAL_RANDOM_AWARE_ANALYSIS/D11_FINAL_ALL_LOGICAL_RESULTS.tsv'
singleton = work / '10_PILOT/STEP3/04_OUTPUTS/STEP3F_POST_LABELS_AND_SINGLETON_GAINS/STEP3F_PRACTICAL_SINGLETON_GAINS.jsonl'
out = paperdir / 'earliest_step_executed_coverage.tsv'

BUDGETS = [5,10,20,30,40,50,60,70,80,90,100]
BFRAC = [x/100 for x in BUDGETS]
BENCHES = ['BFCL','Math-Shepherd','ToolAlpaca']

steps = defaultdict(set)
with static.open(encoding='utf-8') as f:
    for line in f:
        if not line.strip():
            continue
        r = json.loads(line)
        if r['method'] == 'DECOUPLE':
            steps[(r['benchmark'], r['instance_id'])].add(int(r['step_index']))

branch = defaultdict(set)
with d11.open(encoding='utf-8', newline='') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        ss = tuple(ast.literal_eval(r['selected_steps']))
        branch[(r['benchmark'], r['instance_id'], float(r['budget']), ss)].add(float(r['terminal_Z']))
if any(len(v) > 1 for v in branch.values()):
    raise RuntimeError('conflicting terminal outcomes for an identical frozen physical branch')

single = {}
with singleton.open(encoding='utf-8') as f:
    for line in f:
        if not line.strip():
            continue
        r = json.loads(line)
        single[(r['benchmark'], r['instance_id'], int(r['step_index']))] = float(r['singleton_outcome_Z'])

panel_n = {b: sum(1 for k in steps if k[0] == b) for b in BENCHES}
vals = defaultdict(list)
missing = []
for (bench, iid), cand in sorted(steps.items()):
    cand = sorted(cand)
    T = len(cand)
    for beta in BFRAC:
        B = min(T, max(1, math.floor(beta*T + 0.5)))
        sel = tuple(cand[:B])
        key = (bench, iid, beta, sel)
        if key in branch:
            vals[(bench, beta)].append(next(iter(branch[key])))
        elif B == 1 and (bench, iid, sel[0]) in single:
            vals[(bench, beta)].append(single[(bench, iid, sel[0])])
        else:
            missing.append((bench, iid, beta, sel))

if len(missing) != 172:
    raise RuntimeError(f'earliest-step missing selected-set count mismatch: {len(missing)} != 172')

coverage_rows = []
for bench in BENCHES:
    for b, beta in zip(BUDGETS, BFRAC):
        ys = vals[(bench, beta)]
        coverage_rows.append({
            'benchmark': bench,
            'budget_percent': b,
            'covered_instances': len(ys),
            'panel_instances': panel_n[bench],
            'fully_observed': 'YES' if len(ys) == panel_n[bench] else 'NO',
            'earliest_step_utility': f'{sum(ys)/len(ys):.6f}' if len(ys) == panel_n[bench] else '',
        })

with out.open('w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=coverage_rows[0].keys(), delimiter='\t')
    w.writeheader()
    w.writerows(coverage_rows)

print('PASS earliest_step_coverage')
print('PASS earliest_step_missing_sets=172/1100')
print(f'OUTPUT={out}')
