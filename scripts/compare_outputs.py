#!/usr/bin/env python3
import csv, math, sys, hashlib
from pathlib import Path

repo=Path(__file__).resolve().parents[1]
work=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else repo/'reproduced/work'
step4=work/'10_PILOT/STEP4_V2_CLEAN_REBUILD/04_OUTPUTS'
expected=repo/'artifacts/expected'

DEFAULT_DIRS=[
 'STEP4V2_POSTD11_EXACT_BUDGET_MAIN_TABLE',
 'STEP4V2_VEF_MANUSCRIPT',
 'STEP4V2_POSTD11_T4_NONENVELOPE_INFERENCE',
 'STEP4V2_POSTD11_GRID_STABILITY',
 'STEP4V2_POSTD11_CROSSFIT_AUBC',
 'STEP4V2_POSTD11_GLOBAL_HOLM15',
 'STEP4V2_POSTD11_REALIZED_DISPLACEMENT_REGRET',
 'STEP4V2_VEF_SATURATION_AUDIT',
 'STEP4V2_POSTD11_VEF_FLATTENING_AUDIT',
 'STEP4V2_K4_K8_ZERO_API_SENSITIVITY',
]

def num(s):
    try: return float(s)
    except Exception: return None

def compare_tsv(a,b,tol=2e-12):
    with a.open(encoding='utf-8',newline='') as fa, b.open(encoding='utf-8',newline='') as fb:
        ra=list(csv.reader(fa,delimiter='\t')); rb=list(csv.reader(fb,delimiter='\t'))
    if len(ra)!=len(rb): return False,f'row_count {len(ra)} != {len(rb)}'
    for i,(xa,xb) in enumerate(zip(ra,rb),start=1):
        if len(xa)!=len(xb): return False,f'row {i} col_count {len(xa)} != {len(xb)}'
        for j,(sa,sb) in enumerate(zip(xa,xb),start=1):
            if sa==sb: continue
            na,nb=num(sa),num(sb)
            if na is not None and nb is not None and math.isclose(na,nb,rel_tol=1e-12,abs_tol=tol):
                continue
            return False,f'cell {i},{j}: {sa!r} != {sb!r}'
    return True,'numeric_or_exact_match'

fail=[]; passed=[]
for d in DEFAULT_DIRS:
    ep=expected/d
    gp=step4/d
    if not ep.exists(): continue
    if not gp.exists():
        fail.append((d,'missing reproduced directory')); continue
    for e in sorted(ep.iterdir()):
        if not e.is_file() or e.suffix.lower()!='.tsv': continue
        g=gp/e.name
        if not g.exists():
            fail.append((f'{d}/{e.name}','missing')); continue
        ok,msg=compare_tsv(e,g)
        if ok: passed.append(f'{d}/{e.name}')
        else: fail.append((f'{d}/{e.name}',msg))


# The default run reconstructs zero-anchor point estimates without the
# intentionally expensive 100k-permutation inferential loop. Compare those
# reconstructed point estimates against the corresponding frozen columns.
fast=step4/'STEP4V2_POSTD11_ZERO_ANCHOR_FAST/ZERO_ANCHOR_FAST_SUMMARY.tsv'
frozen_zero=expected/'STEP4V2_POSTD11_ZERO_ANCHOR_PROVENANCE/ZERO_ANCHOR_METHOD_SUMMARY.tsv'
if fast.exists() and frozen_zero.exists():
    with fast.open(encoding='utf-8',newline='') as f:
        fr=list(csv.DictReader(f,delimiter='\t'))
    with frozen_zero.open(encoding='utf-8',newline='') as f:
        zr=list(csv.DictReader(f,delimiter='\t'))
    zmap={(r['benchmark'],r['method']):r for r in zr}
    cols=['U0','positive_budget_max_exact_utility','max_verified_minus_U0','positive_VEF_AUBC_5_100','zero_anchored_VEF_AUBC_0_100']
    ok=True; msg=''
    for r in fr:
        key=(r['benchmark'],r['method'])
        if key not in zmap:
            ok=False; msg=f'missing frozen row {key}'; break
        z=zmap[key]
        for c in cols:
            if not math.isclose(float(r[c]),float(z[c]),rel_tol=1e-12,abs_tol=2e-12):
                ok=False; msg=f'{key} {c}: {r[c]} != {z[c]}'; break
        if not ok: break
    if ok:
        passed.append('STEP4V2_POSTD11_ZERO_ANCHOR_FAST/point_estimates')
    else:
        fail.append(('STEP4V2_POSTD11_ZERO_ANCHOR_FAST/point_estimates',msg))
else:
    fail.append(('STEP4V2_POSTD11_ZERO_ANCHOR_FAST/point_estimates','missing fast or frozen zero-anchor table'))

for p in passed: print(f'PASS {p}')
for p,msg in fail: print(f'FAIL {p}: {msg}')
print(f'PASS_COUNT={len(passed)}')
print(f'FAIL_COUNT={len(fail)}')
print('FINAL_OUTPUT_COMPARISON_STATUS=' + ('PASS' if not fail else 'FAIL'))
sys.exit(0 if not fail else 1)
