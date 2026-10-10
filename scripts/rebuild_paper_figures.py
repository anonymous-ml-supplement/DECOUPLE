#!/usr/bin/env python3
import ast, csv, json, math, sys
from collections import defaultdict
from pathlib import Path

repo=Path(__file__).resolve().parents[1]
work=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else repo/'reproduced/work'
step4=work/'10_PILOT/STEP4_V2_CLEAN_REBUILD'
outdir=repo/'reproduced/figures'; outdir.mkdir(parents=True,exist_ok=True)
paperdir=repo/'reproduced/paper'; paperdir.mkdir(parents=True,exist_ok=True)

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
except Exception as e:
    raise SystemExit(f'matplotlib is required for figure reproduction: {e}')

exact=step4/'04_OUTPUTS/STEP4V2_POSTD11_EXACT_BUDGET_MAIN_TABLE/D11_EXACT_BUDGET_TERMINAL_UTILITY_WIDE.tsv'
vef=step4/'04_OUTPUTS/STEP4V2_POSTD11_EXACT_BUDGET_MAIN_TABLE/D11_VEF_CAPACITY_CURVE_WIDE.tsv'
d11=step4/'04_OUTPUTS/STEP4V2_D11_FINAL_RANDOM_AWARE_ANALYSIS/D11_FINAL_ALL_LOGICAL_RESULTS.tsv'
static=step4/'04_OUTPUTS/STEP4V2_04D_FULL_20PT_SELECTION_MATERIALIZATION/STEP2A/static_baseline_scores.jsonl'
singleton=work/'10_PILOT/STEP3/04_OUTPUTS/STEP3F_POST_LABELS_AND_SINGLETON_GAINS/STEP3F_PRACTICAL_SINGLETON_GAINS.jsonl'

BUDGETS=[5,10,20,30,40,50,60,70,80,90,100]
BFRAC=[x/100 for x in BUDGETS]
METHODS=['DECOUPLE','H-only','p-only','Random','Step-PRM','PRM@BoK']
BENCHES=['BFCL','Math-Shepherd','ToolAlpaca']
LABELS={'DECOUPLE':'DECOUPLE (Ours)','H-only':'H-only','p-only':'p-only','Random':'Random','Step-PRM':'Step-PRM','PRM@BoK':'PRM@BoK'}


def rows_by_key(path):
    with path.open(encoding='utf-8',newline='') as f:
        rows=list(csv.DictReader(f,delimiter='\t'))
    return {(r['benchmark'],r['method']):r for r in rows}

E=rows_by_key(exact); V=rows_by_key(vef)
# Main paper Figure 1: exact forced quota and retrospective envelope.
fig,axes=plt.subplots(1,3,figsize=(11.0,3.35),sharex=True)
for ax,bench in zip(axes,BENCHES):
    for m in METHODS:
        y=[float(E[(bench,m)][f'{b}%']) for b in BUDGETS]
        yf=[float(V[(bench,m)][f'{b}%']) for b in BUDGETS]
        lw=2.2 if m=='DECOUPLE' else 1.1
        line,=ax.plot(BUDGETS,y,marker='o' if m=='DECOUPLE' else None,markersize=3.2,lw=lw,label=LABELS[m])
        ax.plot(BUDGETS,yf,ls='--',lw=0.9,alpha=.60,color=line.get_color())
    ax.set_title(bench,fontsize=10)
    ax.set_xlabel('Verification capacity (%)')
    ax.grid(alpha=.18,linewidth=.5)
axes[0].set_ylabel('Executed terminal utility')
handles,labels=axes[0].get_legend_handles_labels()
fig.legend(handles,labels,loc='upper center',ncol=6,frameon=False,fontsize=8,bbox_to_anchor=(0.5,1.04))
fig.text(.5,.005,'Solid: exact forced quota    Dashed: retrospective positive-capacity envelope',ha='center',fontsize=8)
fig.tight_layout(rect=(0,.04,1,.90))
for ext in ('pdf','png'):
    fig.savefig(outdir/f'main_figure_budget_dynamics.{ext}',dpi=220,bbox_inches='tight')
plt.close(fig)

# Supplement Figure 1: earliest-step partial executed-utility diagnostic.
# Frozen execution coverage is the union of the final D11 logical branches and
# practical singleton interventions. This exactly recovers the paper's 172/1100
# missing earliest-step selected sets.
steps=defaultdict(set)
with static.open(encoding='utf-8') as f:
    for line in f:
        if not line.strip(): continue
        r=json.loads(line)
        if r['method']=='DECOUPLE': steps[(r['benchmark'],r['instance_id'])].add(int(r['step_index']))

branch=defaultdict(set)
with d11.open(encoding='utf-8',newline='') as f:
    for r in csv.DictReader(f,delimiter='\t'):
        ss=tuple(ast.literal_eval(r['selected_steps']))
        branch[(r['benchmark'],r['instance_id'],float(r['budget']),ss)].add(float(r['terminal_Z']))
if any(len(v)>1 for v in branch.values()): raise RuntimeError('conflicting terminal outcomes for an identical frozen physical branch')

single={}
with singleton.open(encoding='utf-8') as f:
    for line in f:
        if not line.strip(): continue
        r=json.loads(line)
        single[(r['benchmark'],r['instance_id'],int(r['step_index']))]=float(r['singleton_outcome_Z'])

panel_n={b:sum(1 for k in steps if k[0]==b) for b in BENCHES}
vals=defaultdict(list); missing=[]
for (bench,iid),cand in sorted(steps.items()):
    cand=sorted(cand); T=len(cand)
    for beta in BFRAC:
        B=min(T,max(1,math.floor(beta*T+0.5)))
        sel=tuple(cand[:B])
        key=(bench,iid,beta,sel)
        if key in branch:
            vals[(bench,beta)].append(next(iter(branch[key])))
        elif B==1 and (bench,iid,sel[0]) in single:
            vals[(bench,beta)].append(single[(bench,iid,sel[0])])
        else:
            missing.append((bench,iid,beta,sel))
if len(missing)!=172:
    raise RuntimeError(f'earliest-step missing selected-set count mismatch: {len(missing)} != 172')

coverage_rows=[]
for bench in BENCHES:
    for b,beta in zip(BUDGETS,BFRAC):
        ys=vals[(bench,beta)]
        coverage_rows.append({'benchmark':bench,'budget_percent':b,'covered_instances':len(ys),'panel_instances':panel_n[bench],
                              'fully_observed':'YES' if len(ys)==panel_n[bench] else 'NO',
                              'earliest_step_utility':f'{sum(ys)/len(ys):.6f}' if len(ys)==panel_n[bench] else ''})
with (paperdir/'earliest_step_executed_coverage.tsv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=coverage_rows[0].keys(),delimiter='\t'); w.writeheader(); w.writerows(coverage_rows)

fig,axes=plt.subplots(1,3,figsize=(11.0,3.35),sharex=True)
for ax,bench in zip(axes,BENCHES):
    for m in METHODS:
        y=[float(E[(bench,m)][f'{b}%']) for b in BUDGETS]
        lw=2.0 if m=='DECOUPLE' else 1.0
        ax.plot(BUDGETS,y,lw=lw,label=LABELS[m])
    xs=[]; ys=[]
    for b,beta in zip(BUDGETS,BFRAC):
        vv=vals[(bench,beta)]
        if len(vv)==panel_n[bench]:
            xs.append(b); ys.append(sum(vv)/len(vv))
    ax.plot(xs,ys,linestyle='none',marker='D',markersize=5.0,markerfacecolor='white',markeredgecolor='black',label='Earliest-step (fully observed only)')
    ax.set_title(bench,fontsize=10); ax.set_xlabel('Verification capacity (%)'); ax.grid(alpha=.18,linewidth=.5)
axes[0].set_ylabel('Executed terminal utility')
handles,labels=axes[0].get_legend_handles_labels()
# de-duplicate labels
seen={};
for h,l in zip(handles,labels): seen.setdefault(l,h)
fig.legend(list(seen.values()),list(seen.keys()),loc='upper center',ncol=4,frameon=False,fontsize=8,bbox_to_anchor=(0.5,1.06))
fig.text(.5,.005,'No interpolation or imputation; incomplete earliest-step quotas are omitted. Missing frozen branches: 172 / 1,100.',ha='center',fontsize=8)
fig.tight_layout(rect=(0,.04,1,.88))
for ext in ('pdf','png'):
    fig.savefig(outdir/f'supplement_figure_earliest_step_overlay.{ext}',dpi=220,bbox_inches='tight')
plt.close(fig)

print('PASS paper_figures main + supplement')
print('PASS earliest_step_missing_sets=172/1100')
print(f'OUTPUT_DIR={outdir}')
