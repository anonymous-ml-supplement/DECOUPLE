#!/usr/bin/env python3
import csv, json, math, sys
from pathlib import Path

repo=Path(__file__).resolve().parents[1]
work=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else repo/'reproduced/work'
out=work/'10_PILOT/STEP4_V2_CLEAN_REBUILD/04_OUTPUTS'
expected=repo/'artifacts/expected'
errors=[]

def read_tsv(p):
    with p.open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f,delimiter='\t'))
def check(cond,label,detail=''):
    if cond: print(f'PASS {label}' + (f' | {detail}' if detail else ''))
    else:
        print(f'FAIL {label}' + (f' | {detail}' if detail else '')); errors.append(label)
def close(a,b,tol=1e-8): return math.isclose(float(a),float(b),rel_tol=0,abs_tol=tol)

# Primary 15 pair direction pattern.
rows=read_tsv(out/'STEP4V2_POSTD11_EXACT_BUDGET_MAIN_TABLE/D11_VEF_CORE15_PAIR_SUMMARY.tsv')
dirs=[r['AUBC_direction'] for r in rows]
check(len(rows)==15,'core15_count',str(len(rows)))
check(dirs.count('POSITIVE')==10 and dirs.count('TIE')==5 and dirs.count('NEGATIVE')==0,'primary_vef_pattern','10P/5T/0N')

# Primary Holm-5 frozen final permutation authority; default rerun does not repeat 100k permutations.
perm=read_tsv(work/'10_PILOT/STEP4_V2_CLEAN_REBUILD/04_OUTPUTS/STEP4V2_VEF_AUBC_FINAL_INFERENCE/VEF_AUBC_FINAL_PERMUTATION_HOLM_CORE15.tsv')
sig={(r['benchmark'],r['baseline']) for r in perm if float(r['holm5_p_two_sided'])<0.05}
check(sig=={('Math-Shepherd','Random'),('Math-Shepherd','PRM@BoK')},'holm5_survivors',str(sorted(sig)))

# Global Holm-15.
gh=read_tsv(out/'STEP4V2_POSTD11_GLOBAL_HOLM15/VEF_AUBC_GLOBAL_HOLM15_CORE15.tsv')
gsig={(r['benchmark'],r['baseline']) for r in gh if r['global_holm15_two_sig_005']=='True'}
check(gsig=={('Math-Shepherd','Random')},'global_holm15_survivor',str(sorted(gsig)))

# Grid robustness 24/24.
gr=read_tsv(out/'STEP4V2_POSTD11_GRID_STABILITY/GRID_STABILITY_SUMMARY.tsv')
check(len(gr)==24 and all(r['positive']=='10' and r['tie']=='5' and r['negative']=='0' and r['direction_changes_vs_primary']=='0' and r['new_negative_vs_primary_nonnegative']=='0' for r in gr),'grid_stability','24/24 unchanged')

# Cross-fitting 6/5/4 and 12/17 nonloss sanity target.
cf=read_tsv(out/'STEP4V2_POSTD11_CROSSFIT_AUBC/CROSSFIT_A_PLUS_CORE15.tsv')
cd=[r['crossfit_pair_direction'] for r in cf]
check(cd.count('POSITIVE')==6 and cd.count('TIE')==5 and cd.count('NEGATIVE')==4,'crossfit_pattern','6P/5T/4N')
check(sum(int(r['CF_nonloss_all_11']) for r in cf)==11,'crossfit_nonloss_core15','11/15 core rows')
# Historical registry target is 12/17 including specialized pairs; verify pair table if present.
pair=read_tsv(out/'STEP4V2_POSTD11_CROSSFIT_AUBC/CROSSFIT_A_PLUS_PAIR_OPTIMISM_17.tsv')
check(sum(int(r['CF_nonloss_all_11']) for r in pair)==12,'crossfit_nonloss_all17','12/17')

# Zero anchor.
za=read_tsv(out/'STEP4V2_POSTD11_ZERO_ANCHOR_FAST/ZERO_ANCHOR_FAST_SUMMARY.tsv')
de={r['benchmark']:r for r in za if r['method']=='DECOUPLE'}
check(close(de['BFCL']['U0'],0.32) and close(de['Math-Shepherd']['U0'],0.40),'zero_anchor','BFCL=.32 Math=.40')
check(all(float(r['positive_budget_max_exact_utility']) < float(r['U0']) for r in za),'zero_anchor_dominates_positive','BFCL/Math all methods')

# K=4 sensitivity.
k4=read_tsv(out/'STEP4V2_K4_K8_ZERO_API_SENSITIVITY/K4_VS_K8_SUMMARY.tsv')
kall=next(r for r in k4 if r['benchmark']=='ALL')
check(int(kall['n'])==631 and close(kall['spearman'],0.9198425254056379,1e-12),'k4_k8_spearman',kall['spearman'])

# Non-envelope summaries.
t4=read_tsv(out/'STEP4V2_POSTD11_T4_NONENVELOPE_INFERENCE/T4_NONENVELOPE_POINT_ESTIMATES.tsv')
def get(rows,b,m): return next(r for r in rows if r['benchmark']==b and r['method']==m)
check(close(get(t4,'BFCL','DECOUPLE')['exact_curve_area'],0.134736842) and close(get(t4,'ToolAlpaca','DECOUPLE')['exact_curve_area'],0.465263158),'exact_curve_area_de_values')
check(close(get(t4,'Math-Shepherd','DECOUPLE')['low_quota_mean'],0.146666667),'low_quota_math_de')

# Displacement-regret diagnostics.
rd=read_tsv(out/'STEP4V2_POSTD11_REALIZED_DISPLACEMENT_REGRET/REALIZED_DISPLACEMENT_MANUSCRIPT_SUMMARY.tsv')
sp=read_tsv(out/'STEP4V2_POSTD11_REALIZED_DISPLACEMENT_REGRET/DECOUPLE_SCORE_REALIZED_GAIN_SPEARMAN.tsv')
check(close(get(rd,'BFCL','DECOUPLE')['mean_Rdisp_over_5_10_15_20_25'],0.112) and close(get(rd,'MATH_SHEPHERD','DECOUPLE')['mean_Rdisp_over_5_10_15_20_25'],0.056),'displacement_regret_de')
# Correlation table uses benchmark labels; locate rho field dynamically.
if sp:
    rho_col=next((c for c in sp[0] if 'spearman' in c.lower()),None)
    if rho_col:
        sm={r['benchmark']:r for r in sp}
        check(close(sm['BFCL'][rho_col],0.137,0.0015) and close(sm['MATH_SHEPHERD'][rho_col],0.208,0.0015),'score_gain_spearman','BFCL~.137 Math~.208')

# Specialized ToolPRM result from generated VEF manuscript table.
tp=read_tsv(out/'STEP4V2_VEF_MANUSCRIPT/MANUSCRIPT_SPECIALIZED_TOOLPRM_ABSOLUTE_VEF.tsv')
# two rows per benchmark (DECOUPLE, ToolPRM-GRPO)
def aubc(bench,method):
    r=next(x for x in tp if x['benchmark']==bench and x['method']==method)
    col=next(c for c in r if 'AUBC' in c.upper())
    return float(r[col])
check(close(aubc('BFCL','DECOUPLE')-aubc('BFCL','ToolPRM-GRPO'),-1/12,2e-8) and close(aubc('ToolAlpaca','DECOUPLE')-aubc('ToolAlpaca','ToolPRM-GRPO'),0.04,2e-8),'specialized_toolprm_direction','BFCL adverse; ToolAlpaca favorable')

# Allocation-active frozen explanatory table (provided as frozen result; full upstream audit namespace is not in compact rerun).
aa=read_tsv(repo/'reproduced/paper/allocation_active_summary.tsv')
core=[r for r in aa if r['baseline'] in {'H-only','p-only','Random','Step-PRM','PRM@BoK'}]
strict=[(r['benchmark'],r['baseline']) for r in core if float(r['bootstrap_ci_low'])>0]
check(strict==[('Math-Shepherd','PRM@BoK')],'allocation_active_strict_positive_core',str(strict))


# Math zero-to-5 harm accounting from frozen base + 5% executed outcomes.
mz=read_tsv(repo/'reproduced/paper/math_zero_to_5_accounting.tsv')[0]
check(int(mz['base_success'])==20 and int(mz['success_harmed'])==13 and int(mz['failure_rescued'])==0 and close(mz['U0'],0.40) and close(mz['U5'],0.14),'math_zero_to_5_accounting','20 base-success; 13 harmed; 0 rescued; .40->.14')

# Partial earliest-step executed-utility coverage used by supplement figure.
ec=read_tsv(repo/'reproduced/paper/earliest_step_executed_coverage.tsv')
missing=sum(int(r['panel_instances'])-int(r['covered_instances']) for r in ec)
check(missing==172,'earliest_step_missing_physical_sets','172/1100')

# H2 / component closure frozen authority.
h2=json.loads((work/'10_PILOT/STEP4_V2_CLEAN_REBUILD/04_OUTPUTS/STEP4V2_H2_FINAL_CLOSURE/H2_FINAL_ACCOUNTING_CLOSURE.json').read_text())
check(h2['h2_status']=='NOT_IDENTIFIABLE_FROM_FROZEN_ACCOUNTING','all_in_cost_claim_gate',h2['h2_status'])
check(h2['recovered_accounting']['k8_calls']==5048,'k8_calls','5048')

print('FINAL_CLAIM_VALIDATION_STATUS=' + ('PASS' if not errors else 'FAIL'))
if errors: print('FAILED=' + ','.join(errors))
sys.exit(0 if not errors else 1)
