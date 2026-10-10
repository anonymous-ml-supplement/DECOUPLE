#!/usr/bin/env python3
"""Zero-API reconstruction of archived 11-cap leave-one-instance-out budget choice.

Algorithm is transcribed from the retained upstream run_vef_v1_audit.py,
including per-instance Random replicate collapsing, matched panel intersection,
training-fold argmax, and smallest-budget tie-breaking. It never reads held-out
outcomes to choose that held-out case's budget. This replayer writes no inputs.
"""
import argparse
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

GRID = (5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
BASELINES = {'H-only', 'p-only', 'Random', 'Step-PRM', 'PRM@BoK', 'ToolPRM-GRPO'}
EPS = 1e-12
D11_SHA = '32d160166c3546f62b579f30e2e007e6213fb64596fca9b9ecb52f3b1bb83c53'
ROOT = Path(__file__).resolve().parents[1]
D11_REL = '10_PILOT/STEP4_V2_CLEAN_REBUILD/04_OUTPUTS/STEP4V2_D11_FINAL_RANDOM_AWARE_ANALYSIS/D11_FINAL_ALL_LOGICAL_RESULTS.tsv'
CF_REL = '10_PILOT/STEP4_V2_CLEAN_REBUILD/04_OUTPUTS/STEP4V2_VEF_AUDIT/VEF_V1_FULL_11_CAP_CURVES_187.tsv'
COLUMNS = ('DE_exact_utility','baseline_exact_utility','DE_VEF','baseline_VEF','VEF_delta',
           'CF_DE_utility','CF_baseline_utility','CF_delta',
           'CF_DE_mean_selected_budget_pct','CF_baseline_mean_selected_budget_pct')


def benchmark(x):
    k = str(x).strip().upper().replace('-', '_').replace(' ', '_')
    return {'MATH_SHEPHERD': 'Math-Shepherd', 'TOOLALPACA': 'ToolAlpaca', 'BFCL': 'BFCL'}.get(k, str(x).strip())


def budget_pct(x):
    v = float(x)
    if v <= 1.0 + EPS:
        v *= 100
    return int(round(v))


def mean(xs):
    return sum(xs) / len(xs)


def prefix_max(xs):
    out, cur = [], None
    for v in xs:
        if cur is None or v > cur:
            cur = v
        out.append(cur)
    return out


def choose_budget(collapsed, bench, method, train_ids, cap):
    scores = [(mean([collapsed[(bench,method,b,iid)] for iid in train_ids]), b)
              for b in GRID if b <= cap]
    high = max(x[0] for x in scores)
    # Historical code's exact tie semantics. Do not use Python tuple max,
    # which would favor the largest cap rather than the smallest one.
    return min(b for score,b in scores if abs(score-high) <= EPS)


def run(d11, authority):
    digest = hashlib.sha256(d11.read_bytes()).hexdigest()
    if digest != D11_SHA:
        raise ValueError('Frozen D11 SHA mismatch: refusing to reconstruct LOO')
    raw = defaultdict(list)
    with d11.open(newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            b = budget_pct(row['budget'])
            if b not in GRID: continue
            raw[(benchmark(row['benchmark']), row['method'].strip(), b, row['instance_id'])].append(float(row['terminal_Z']))
    collapsed = {k:mean(v) for k,v in raw.items()}
    methods = defaultdict(set)
    for ben,method,b,iid in collapsed:
        methods[ben].add(method)
    pairs = [(ben,method) for ben in sorted(methods) for method in sorted(methods[ben]) if method in BASELINES]
    if len(pairs) != 17:
        raise ValueError(f'Expected 17 frozen pairs; got {len(pairs)}')
    calculated = {}
    for ben,baseline in pairs:
        common = []
        for b in GRID:
            de = {iid for bb,m,quota,iid in collapsed if bb == ben and m == 'DECOUPLE' and quota == b}
            bl = {iid for bb,m,quota,iid in collapsed if bb == ben and m == baseline and quota == b}
            common.append(de & bl)
        panel = sorted(set.intersection(*common))
        if len(panel) < 2:
            raise ValueError(f'Insufficient matched panel: {ben}, {baseline}')
        de_u = [mean([collapsed[(ben,'DECOUPLE',b,iid)] for iid in panel]) for b in GRID]
        bl_u = [mean([collapsed[(ben,baseline,b,iid)] for iid in panel]) for b in GRID]
        de_f, bl_f = prefix_max(de_u),prefix_max(bl_u)
        for j,cap in enumerate(GRID):
            held_de,held_bl,chosen_de,chosen_bl = [],[],[],[]
            for heldout in panel:
                train = [iid for iid in panel if iid != heldout]
                bd = choose_budget(collapsed,ben,'DECOUPLE',train,cap)
                bb = choose_budget(collapsed,ben,baseline,train,cap)
                held_de.append(collapsed[(ben,'DECOUPLE',bd,heldout)])
                held_bl.append(collapsed[(ben,baseline,bb,heldout)])
                chosen_de.append(bd);chosen_bl.append(bb)
            cf_de,cf_bl = mean(held_de),mean(held_bl)
            vals = {'DE_exact_utility':f'{de_u[j]:.9f}',
                    'baseline_exact_utility':f'{bl_u[j]:.9f}',
                    'DE_VEF':f'{de_f[j]:.9f}',
                    'baseline_VEF':f'{bl_f[j]:.9f}',
                    'VEF_delta':f'{de_f[j]-bl_f[j]:.9f}',
                    'CF_DE_utility':f'{cf_de:.9f}',
                    'CF_baseline_utility':f'{cf_bl:.9f}',
                    'CF_delta':f'{cf_de-cf_bl:.9f}',
                    'CF_DE_mean_selected_budget_pct':f'{mean(chosen_de):.6f}',
                    'CF_baseline_mean_selected_budget_pct':f'{mean(chosen_bl):.6f}'}
            calculated[(ben,baseline,cap)] = (len(panel),vals)
    with authority.open(newline='',encoding='utf-8') as f:
        expected = list(csv.DictReader(f, delimiter='\t'))
    if len(expected) != 187 or len(calculated) != 187:
        raise ValueError(f'Expected 187 rows, got {len(expected)} expected / {len(calculated)} rederived')
    comparisons, errors = 0, []
    for row in expected:
        key = (row['benchmark'],row['baseline'],int(row['budget_cap_pct']))
        if key not in calculated:
            errors.append((key,'missing row'));continue
        n, vals = calculated[key]
        if n != int(row['matched_instance_n']):
            errors.append((key,'matched instance count',n,row['matched_instance_n']))
        for col in COLUMNS:
            comparisons += 1
            if vals[col] != row[col]:
                errors.append((key,col,vals[col],row[col]))
    print(f'LOO_UPSTREAM_REBUILT_ROWS={len(calculated)}')
    print(f'LOO_UPSTREAM_NUMERIC_CELLS={comparisons}')
    print(f'LOO_UPSTREAM_ERRORS={len(errors)}')
    if errors:
        for x in errors[:25]: print('FAIL',x)
        print('FINAL_LOO_UPSTREAM_REPLAY_STATUS=FAIL')
        return 1
    print('PASS original-instance fold selection and smallest-cap tie policy')
    print('PASS Random instance-budget replicate aggregation')
    print('PASS frozen D11 digest')
    print('FINAL_LOO_UPSTREAM_REPLAY_STATUS=PASS')
    return 0


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--d11',type=Path,default=ROOT/'artifacts/frozen_inputs'/D11_REL)
    p.add_argument('--authority',type=Path,default=ROOT/'artifacts/frozen_inputs'/CF_REL)
    args=p.parse_args()
    raise SystemExit(run(args.d11,args.authority))
