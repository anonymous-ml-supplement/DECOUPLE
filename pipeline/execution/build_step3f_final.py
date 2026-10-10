#!/usr/bin/env python3
import copy
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path('__DECOUPLE_ROOT__')
STEP1 = ROOT / '10_PILOT/STEP1'
STEP3 = ROOT / '10_PILOT/STEP3'
EOUT = STEP3 / '04_OUTPUTS/STEP3E_EXACT_CHECKPOINT_REPLAY'
EAUD = STEP3 / '06_AUDIT/STEP3E_EXACT_CHECKPOINT_REPLAY'
OUT = STEP3 / '04_OUTPUTS/STEP3F_POST_LABELS_AND_SINGLETON_GAINS'
AUD = STEP3 / '06_AUDIT/STEP3F_POST_LABELS_AND_SINGLETON_GAINS'
OUT.mkdir(parents=True, exist_ok=True)
AUD.mkdir(parents=True, exist_ok=True)

LEDGER = EOUT / 'STEP3E_FORMAL_EXECUTION_LEDGER.jsonl'
FANOUT = EOUT / 'STEP3E_EXECUTION_FANOUT.jsonl'
JOINT = EOUT / 'STEP3E_JOINT_REPLAY_EXECUTION_MANIFEST.jsonl'
RESULT_DIR = EOUT / 'FORMAL_BRANCH_RESULTS'
HANDOFF = EAUD / 'STEP3E_FINAL_FREEZE_HANDOFF.json'

BFCL_ROOT = STEP1 / '02_INPUTS/RAW_AUTHORITY/BFCL/gorilla/berkeley-function-call-leaderboard'
BFCL_ARCHIVE = STEP1 / '04_OUTPUTS/STEP1B_TRAJECTORY/ARCHIVED_BASE/BFCL'
BFCL_CHECKER = BFCL_ROOT / 'bfcl_eval/eval_checker/multi_turn_eval/multi_turn_checker.py'
MATH_SOURCE = STEP1 / '02_INPUTS/RAW_AUTHORITY/MATH_SHEPHERD/math-shepherd.jsonl'
MATH_ARCHIVE = STEP1 / '04_OUTPUTS/STEP1B_TRAJECTORY/ARCHIVED_BASE/MATH_SHEPHERD'
TOOL_ARCHIVE = STEP1 / '04_OUTPUTS/STEP1B_TRAJECTORY/ARCHIVED_BASE/TOOLALPACA'

BASE_OUT = OUT / 'STEP3F_BASE_OUTCOMES.jsonl'
BRANCH_OUT = OUT / 'STEP3F_PHYSICAL_BRANCH_LABELS.jsonl'
SINGLETON_OUT = OUT / 'STEP3F_PRACTICAL_SINGLETON_GAINS.jsonl'
YT_OUT = OUT / 'STEP3F_YT_LABELS.jsonl'
RT_OUT = OUT / 'STEP3F_RT_LABELS.jsonl'
SUMMARY_OUT = OUT / 'STEP3F_CORE_REBUILD_SUMMARY.json'
MANIFEST_OUT = AUD / 'STEP3F_FINAL_MANIFEST.json'
STATUS_OUT = AUD / 'STATUS.txt'
SHA_OUT = AUD / 'SHA256SUMS'

EXPECTED = {
    'ledger': '831ebab2cfb3091ac4f0ced26e9e4c49b4a9aeecdb04e36a11c27836e2a4ca59',
    'fanout': '9285e77c9ab62c0e0a12d652ddb9d3f7ffc74688d4438cb4315dcc36a4954dc6',
    'joint': '1d659f7678cf4fff555988224e5ba13fd56a700f9eb1a3ee8dbde9e372da2387',
    'bfcl_checker': 'b3b787515eda3bf0e365e39634a8fc7f831763f010f716d35d86f96fd5aab1b5',
    'math_source': 'bbe67ca2e1d551734e100297349779b597ddfa9fd7655364ea1f99cc23beb4b6',
}
BFCL_AUTH = {
    'multi_turn_base': {
        'task': '1a21a995d06fd6f20ba55de7bced30ef953ec35e998f502ec2ecf4d66ef1c43a',
        'gt': '1fee67823b317571649177dd89d63969feaae4e810cc7448ee55ba797fb7c8fc',
    },
    'multi_turn_long_context': {
        'task': '78c3268c5cc8e97c0f4ec6c811b3b9a2bba14323b1830b7a874b06d822749324',
        'gt': 'e82aa0e839c39d23c64a05834f7ae024d7c9738ec21738ecee78dc876e3d0d18',
    },
    'multi_turn_miss_func': {
        'task': '87d28ce10e37d864b72de85d5732eef2a867b241d6c1c99b4ae682c9e3ea921c',
        'gt': '69e679b806d1c871b05393a4b95583bb973248e5b8d96c2d7f4ca05e29fc32e6',
    },
    'multi_turn_miss_param': {
        'task': 'f0c66dda3795f5f53e3e1c0cc8ba0246b6761c8f58bdba8317203bf451ab8838',
        'gt': '59c442901779e2c31c33abcd566d032e03736e5ad8069de2fe05489873046ecf',
    },
}
DIRECT_ERROR_TYPES = {
    'multi_turn:empty_turn_model_response',
    'multi_turn:irrelevance_error:decoder_success',
}
UNAVAILABLE_IDS = {
    '10efdfa462cd12871335418a8c0b3d16c24b9b3dc2f163f632ec83c283975267',
    'a479b91becc2676330ac458c24484465bf8074e575a510b3ace5781d9c472457',
    '65451867357ffa28390872a290bbb36772be7e4bf9d1bd1b6948422d3bf0f625',
    'cbedbbe448cd303cb58eeff86d88cdfa94ddcdb07bf45ad3b615d3140bea1682',
}

def sha256_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))

def load_jsonl(path):
    rows = []
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows

def load_json_or_jsonl(path):
    text = path.read_text(encoding='utf-8').strip()
    if not text:
        return []
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, list) else [obj]
    except json.JSONDecodeError:
        return [json.loads(x) for x in text.splitlines() if x.strip()]

def write_jsonl(path, rows):
    with path.open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')

def normalize_benchmark(x):
    if x == 'BFCL': return 'BFCL'
    if x in {'Math-Shepherd', 'MATH_SHEPHERD'}: return 'MATH_SHEPHERD'
    if x in {'ToolAlpaca', 'TOOLALPACA'}: return 'TOOLALPACA'
    return str(x)

def parse_math_labels(text):
    out = []
    for line in text.splitlines():
        m = re.search(r'\s([+-])\s*$', line)
        if m: out.append(m.group(1))
    return out

def archive_objects(directory):
    result = {}
    for p in sorted(directory.glob('*.json')):
        try: x = load_json(p)
        except Exception: continue
        iid = x.get('instance_id') if isinstance(x, dict) else None
        if iid:
            if iid in result: raise RuntimeError(f'DUPLICATE_ARCHIVE_INSTANCE={iid}')
            result[iid] = (p, x)
    return result

def fail(msg):
    raise RuntimeError(msg)

# ------------------------------------------------------------------
# Gate 0: final STEP3E authority and immutable inputs.
# ------------------------------------------------------------------
required = [LEDGER, FANOUT, JOINT, RESULT_DIR, HANDOFF, BFCL_CHECKER, MATH_SOURCE, BFCL_ARCHIVE, MATH_ARCHIVE, TOOL_ARCHIVE]
missing = [str(p) for p in required if not p.exists()]
if missing: fail('MISSING_REQUIRED_INPUTS=' + json.dumps(missing))
for key, p in [('ledger', LEDGER), ('fanout', FANOUT), ('joint', JOINT), ('bfcl_checker', BFCL_CHECKER), ('math_source', MATH_SOURCE)]:
    got = sha256_file(p)
    if got != EXPECTED[key]: fail(f'{key.upper()}_SHA_MISMATCH={got}')

handoff = load_json(HANDOFF)
if handoff.get('status') != 'PASS_FROZEN': fail('STEP3E_HANDOFF_NOT_PASS_FROZEN')
if handoff.get('formal_universe', {}).get('ledger_rows') != 2518: fail('HANDOFF_LEDGER_ROWS_NOT_2518')
if handoff.get('formal_universe', {}).get('executable_results') != 2514: fail('HANDOFF_EXECUTABLE_NOT_2514')
if set(handoff.get('corrected_unavailable_execution_ids', [])) != UNAVAILABLE_IDS: fail('UNAVAILABLE_ID_SET_MISMATCH')

ledger = load_jsonl(LEDGER)
fanout = load_jsonl(FANOUT)
joint = load_jsonl(JOINT)
if len(ledger) != 2518: fail(f'LEDGER_ROWS={len(ledger)}')
if len(fanout) != 9919: fail(f'FANOUT_ROWS={len(fanout)}')
if len(joint) != 9222: fail(f'JOINT_ROWS={len(joint)}')
ledger_ids = [r['execution_id'] for r in ledger]
if len(set(ledger_ids)) != 2518: fail('DUPLICATE_LEDGER_EXECUTION_ID')

# Load exact final result universe.
results = {}
for eid in ledger_ids:
    p = RESULT_DIR / f'{eid}.json'
    if not p.is_file(): fail(f'FINAL_RESULT_MISSING={eid}')
    obj = load_json(p)
    if obj.get('execution_id') != eid: fail(f'RESULT_EXECUTION_ID_MISMATCH={eid}')
    results[eid] = obj
unexpected = sorted(p.stem for p in RESULT_DIR.glob('*.json') if p.stem not in set(ledger_ids))
if unexpected: fail('UNEXPECTED_RESULT_FILES=' + json.dumps(unexpected[:20]))

status_counts = Counter(r.get('status') for r in results.values())
if status_counts != Counter({'PASS': 2514, 'UNAVAILABLE': 4}): fail('RESULT_STATUS_COUNTS=' + repr(status_counts))
for eid, r in results.items():
    if eid in UNAVAILABLE_IDS:
        if not (r.get('status') == 'UNAVAILABLE' and r.get('terminal_outcome_Z') is None and r.get('scientific_result_valid') is False):
            fail(f'BAD_UNAVAILABLE_RESULT={eid}')
    else:
        if r.get('status') != 'PASS' or r.get('terminal_outcome_Z') not in (0,1):
            fail(f'BAD_EXECUTABLE_RESULT={eid}')

# ------------------------------------------------------------------
# Gate 1: singleton practical fanout authority = all 631 opportunities.
# ------------------------------------------------------------------
practical = []
oracle_singletons = []
for row in fanout:
    src = row.get('source_identity')
    if row.get('branch_type') == 'singleton_practical':
        if not isinstance(src, dict) or src.get('branch_type') != 'PRACTICAL_REFINE': fail('BAD_SINGLETON_PRACTICAL_SOURCE_IDENTITY')
        practical.append((row['execution_id'], src))
    elif row.get('branch_type') == 'singleton_oracle':
        if not isinstance(src, dict) or src.get('branch_type') != 'DIAGNOSTIC_ORACLE': fail('BAD_SINGLETON_ORACLE_SOURCE_IDENTITY')
        oracle_singletons.append((row['execution_id'], src))
if len(practical) != 631: fail(f'PRACTICAL_SINGLETON_ROWS={len(practical)}')
if len(oracle_singletons) != 66: fail(f'ORACLE_SINGLETON_ROWS={len(oracle_singletons)}')

seen_opp = set()
for eid, src in practical:
    key = (normalize_benchmark(src['benchmark']), src['instance_id'], int(src['step_index']))
    if key in seen_opp: fail(f'DUPLICATE_PRACTICAL_OPPORTUNITY={key}')
    seen_opp.add(key)
    result = results[eid]
    if result.get('status') != 'PASS': fail(f'PRACTICAL_SINGLETON_NOT_PASS={eid}')
    if result.get('selected_steps_chronological') != [int(src['step_index'])]: fail(f'PRACTICAL_SINGLETON_SELECTED_STEP_MISMATCH={eid}')
    if result.get('intervention_operator') != 'V_refine': fail(f'PRACTICAL_SINGLETON_OPERATOR_MISMATCH={eid}')

# ------------------------------------------------------------------
# Benchmark authorities and base outcomes. Reuses proven V2 logic,
# but executes fresh against final frozen authorities.
# ------------------------------------------------------------------
sys.path.insert(0, str(BFCL_ROOT))
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import multi_turn_checker  # noqa

bfcl_archives = archive_objects(BFCL_ARCHIVE)
math_archives = archive_objects(MATH_ARCHIVE)
tool_archives = archive_objects(TOOL_ARCHIVE)
if (len(bfcl_archives),len(math_archives),len(tool_archives)) != (25,50,25):
    fail(f'ARCHIVE_COUNTS={len(bfcl_archives)},{len(math_archives)},{len(tool_archives)}')

bfcl_authorities = {}
for category, hashes in BFCL_AUTH.items():
    name = f'BFCL_v4_{category}.json'
    task_path = BFCL_ROOT / 'bfcl_eval/data' / name
    gt_path = BFCL_ROOT / 'bfcl_eval/data/possible_answer' / name
    if sha256_file(task_path) != hashes['task']: fail(f'BFCL_TASK_SHA_MISMATCH={category}')
    if sha256_file(gt_path) != hashes['gt']: fail(f'BFCL_GT_SHA_MISMATCH={category}')
    tasks = {r['id']: r for r in load_json_or_jsonl(task_path)}
    gts = {r['id']: r['ground_truth'] for r in load_json_or_jsonl(gt_path)}
    bfcl_authorities[category] = (task_path, gt_path, tasks, gts)
math_raw = load_jsonl(MATH_SOURCE)

base_rows=[]; base_lookup={}; bfcl_checker_info={}; bfcl_slot_maps={}; bfcl_turn_slot_counts={}
for iid,(archive_path,x) in sorted(bfcl_archives.items()):
    category=x['category']; task_path,gt_path,tasks,gts=bfcl_authorities[category]
    if iid not in tasks or iid not in gts: fail(f'BFCL_AUTHORITY_INSTANCE_MISSING={iid}')
    decoded_turns=[]; global_step=0; by_global={}; by_turn=defaultdict(list)
    for turn_index,turn in enumerate(x['turns']):
        decoded=[]; local_step_index=0
        for model_step in turn['model_steps']:
            calls=model_step.get('function_calls',[]) or []; terminal_text=model_step.get('terminal_text')
            if calls: decoded.append(list(calls))
            emitted=[]
            if calls: emitted.append('joint_tool_call' if len(calls)>1 else 'tool_call')
            if terminal_text is not None and terminal_text!='': emitted.append('assistant_text')
            for candidate_kind in emitted:
                global_step+=1; local_step_index+=1
                slot={'step_index':global_step,'turn_index':turn_index,'local_step_index':local_step_index,'candidate_kind':candidate_kind}
                by_global[global_step]=slot; by_turn[turn_index].append(slot)
        decoded_turns.append(decoded)
    result=multi_turn_checker(copy.deepcopy(decoded_turns),gts[iid],tasks[iid],category,x['model_id'])
    z0=int(result.get('valid') is True)
    row={'benchmark':'BFCL','instance_id':iid,'base_outcome_status':'IDENTIFIED','base_outcome_Z0':z0,
         'outcome_semantics':'official_BFCL_multi_turn_checker.valid','archive_path':str(archive_path),'archive_sha256':sha256_file(archive_path),
         'task_authority_path':str(task_path),'task_authority_sha256':sha256_file(task_path),'ground_truth_authority_path':str(gt_path),
         'ground_truth_authority_sha256':sha256_file(gt_path),'checker_sha256':EXPECTED['bfcl_checker'],'api_calls':0}
    base_rows.append(row); base_lookup[('BFCL',iid)]=row
    bfcl_checker_info[iid]={'archive':x,'decoded_turns':decoded_turns,'result':result,'task':tasks[iid],'ground_truth':gts[iid]}
    bfcl_slot_maps[iid]=by_global; bfcl_turn_slot_counts[iid]={k:len(v) for k,v in by_turn.items()}

for iid,(archive_path,x) in sorted(math_archives.items()):
    row_id=int(x['source_row_id']); authority=math_raw[row_id]; signs=parse_math_labels(authority['label'])
    if len(signs)!=int(x['step_count']): fail(f'MATH_STEP_COUNT_MISMATCH={iid}')
    z0=int(signs[-1]=='+')
    row={'benchmark':'MATH_SHEPHERD','instance_id':iid,'base_outcome_status':'IDENTIFIED','base_outcome_Z0':z0,
         'outcome_semantics':'released_final_step_correctness_annotation','source_row_id':row_id,'released_step_count':len(signs),
         'archive_path':str(archive_path),'archive_sha256':sha256_file(archive_path),'authority_path':str(MATH_SOURCE),
         'authority_sha256':EXPECTED['math_source'],'api_calls':0}
    base_rows.append(row); base_lookup[('MATH_SHEPHERD',iid)]=row

for iid,(archive_path,x) in sorted(tool_archives.items()):
    row={'benchmark':'TOOLALPACA','instance_id':iid,'base_outcome_status':'NOT_IDENTIFIABLE_ZERO_API','base_outcome_Z0':None,
         'outcome_semantics':'no_separately_frozen_base_judge_record_rebound_by_proven_v2_contract','archive_path':str(archive_path),
         'archive_sha256':sha256_file(archive_path),'api_calls':0}
    base_rows.append(row); base_lookup[('TOOLALPACA',iid)]=row
if len(base_rows)!=100: fail(f'BASE_ROWS={len(base_rows)}')

# ------------------------------------------------------------------
# Physical branch labels over complete final result universe.
# Unavailable rows stay explicitly undefined.
# ------------------------------------------------------------------
branch_rows=[]
for eid in sorted(ledger_ids):
    result=results[eid]; benchmark=normalize_benchmark(result['benchmark']); iid=result['instance_id']; base=base_lookup[(benchmark,iid)]
    if result.get('status')=='UNAVAILABLE':
        branch_rows.append({'execution_id':eid,'benchmark':benchmark,'instance_id':iid,'selected_steps_chronological':result.get('selected_steps_chronological',[]),
            'intervention_operator':result.get('intervention_operator'),'intervention_outcome_status':'UNAVAILABLE','intervention_outcome_Z':None,
            'base_outcome_status':base['base_outcome_status'],'base_outcome_Z0':base['base_outcome_Z0'],'rescue_status':'UNAVAILABLE',
            'rescue_indicator':None,'harmful_intervention_status':'UNAVAILABLE','harmful_intervention_indicator':None,
            'unavailable_reason':result.get('unavailable_reason'),'api_calls':0})
        continue
    z=result['terminal_outcome_Z']; ident=base['base_outcome_status']=='IDENTIFIED'; z0=base['base_outcome_Z0'] if ident else None
    branch_rows.append({'execution_id':eid,'benchmark':benchmark,'instance_id':iid,'selected_steps_chronological':result.get('selected_steps_chronological',[]),
        'intervention_operator':result.get('intervention_operator'),'intervention_outcome_status':'IDENTIFIED','intervention_outcome_Z':z,
        'base_outcome_status':base['base_outcome_status'],'base_outcome_Z0':z0,'rescue_status':'IDENTIFIED' if ident else 'NOT_IDENTIFIABLE',
        'rescue_indicator':int(z0==0 and z==1) if ident else None,'harmful_intervention_status':'IDENTIFIED' if ident else 'NOT_IDENTIFIABLE',
        'harmful_intervention_indicator':int(z0==1 and z==0) if ident else None,'api_calls':0})

# ------------------------------------------------------------------
# Practical singleton gains over all 631 frozen opportunities.
# ------------------------------------------------------------------
singleton_rows=[]
for eid,src in sorted(practical,key=lambda x:(normalize_benchmark(x[1]['benchmark']),x[1]['instance_id'],int(x[1]['step_index']),x[0])):
    result=results[eid]; benchmark=normalize_benchmark(src['benchmark']); iid=src['instance_id']; step=int(src['step_index']); base=base_lookup[(benchmark,iid)]
    ident=base['base_outcome_status']=='IDENTIFIED'; z_single=result['terminal_outcome_Z']; gain=int(z_single-base['base_outcome_Z0']) if ident else None
    singleton_rows.append({'execution_id':eid,'benchmark':benchmark,'instance_id':iid,'step_index':step,'branch_type':'singleton_practical',
        'singleton_outcome_Z':z_single,'base_outcome_status':base['base_outcome_status'],'base_outcome_Z0':base['base_outcome_Z0'] if ident else None,
        'singleton_gain_status':'IDENTIFIED' if ident else 'NOT_IDENTIFIABLE','singleton_empirical_gain':gain,'source_archive_path':src.get('source_archive_path'),
        'source_archive_sha256':src.get('source_archive_sha256'),'prefix_hash':src.get('prefix_hash'),'exact_restoration_certified':bool(result.get('exact_restoration_certified')),
        'approximate_restoration':bool(result.get('approximate_restoration')),'api_calls':0})

# ------------------------------------------------------------------
# y_t over the complete 631 practical-singleton candidate universe.
# ------------------------------------------------------------------
math_label_lookup={}
for iid,(_,x) in math_archives.items():
    signs=parse_math_labels(math_raw[int(x['source_row_id'])]['label'])
    for step,sign in enumerate(signs,1): math_label_lookup[(iid,step)]=int(sign=='+')

yt_rows=[]
for benchmark,iid,step in sorted(seen_opp):
    status='NOT_IDENTIFIABLE'; y=None; reason=None; turn_index=None
    if benchmark=='MATH_SHEPHERD':
        if (iid,step) not in math_label_lookup: fail(f'MATH_YT_STEP_MISSING={iid}:{step}')
        status='IDENTIFIED'; y=math_label_lookup[(iid,step)]; reason='RELEASED_MATH_SHEPHERD_STEP_CORRECTNESS'
    elif benchmark=='BFCL':
        slot=bfcl_slot_maps.get(iid,{}).get(step)
        if slot is None: fail(f'BFCL_FORMAL_SLOT_MISSING={iid}:{step}')
        turn_index=slot['turn_index']; r=bfcl_checker_info[iid]['result']; error_type=r.get('error_type'); error_message=r.get('error_message','') or ''
        m=re.search(r'\bturn\s+(\d+)\b',error_message); failing_turn=int(m.group(1)) if m else None
        if error_type in DIRECT_ERROR_TYPES and failing_turn is not None and failing_turn==slot['turn_index'] and bfcl_turn_slot_counts[iid].get(failing_turn,0)==1:
            status='IDENTIFIED'; y=0; reason='OFFICIAL_BFCL_DIRECT_CURRENT_TURN_FAILURE_UNIQUE_CANONICAL_SLOT'
        elif r.get('valid') is True: reason='TRAJECTORY_VALID_NOT_SLOT_LEVEL_YT'
        elif error_type in {'multi_turn:instance_state_mismatch','multi_turn:execution_response_mismatch'}: reason='CUMULATIVE_TURN_FAILURE_NOT_SINGLE_SLOT_ATTRIBUTABLE'
        elif error_type in DIRECT_ERROR_TYPES and failing_turn==slot['turn_index']: reason='DIRECT_TURN_FAILURE_MULTIPLE_CANONICAL_SLOTS'
        elif error_type in DIRECT_ERROR_TYPES and failing_turn is not None and failing_turn!=slot['turn_index']: reason='DIRECT_FAILURE_OCCURS_AT_DIFFERENT_TURN'
        elif slot['candidate_kind']=='assistant_text': reason='ASSISTANT_TEXT_NOT_DIRECTLY_EVALUATED_BY_BFCL_CHECKER'
        else: reason='NO_OFFICIAL_SLOT_LEVEL_CORRECTNESS_AUTHORITY'
    elif benchmark=='TOOLALPACA': reason='NO_FROZEN_ZERO_API_SLOT_LEVEL_CORRECTNESS_AUTHORITY'
    else: fail(f'UNKNOWN_BENCHMARK={benchmark}')
    yt_rows.append({'benchmark':benchmark,'instance_id':iid,'step_index':step,'step_correctness_status':status,'y_t':y,'reason':reason,'turn_index':turn_index,'api_calls':0})

# ------------------------------------------------------------------
# Causal R_t only where the proven exact zero-API BFCL contract identifies y_t=0.
# Final success is never used as an R_t proxy.
# ------------------------------------------------------------------
rt_rows=[]
for yrow in yt_rows:
    if yrow['benchmark']!='BFCL' or yrow['step_correctness_status']!='IDENTIFIED' or yrow['y_t']!=0: continue
    iid=yrow['instance_id']; step=yrow['step_index']; slot=bfcl_slot_maps[iid][step]; turn_index=slot['turn_index']; info=bfcl_checker_info[iid]
    archive=info['archive']; base_decoded=copy.deepcopy(info['decoded_turns']); gt_turn=info['ground_truth'][turn_index]
    if base_decoded[turn_index]: fail(f'RT_TARGET_TURN_BASE_CALLS_NOT_EMPTY={iid}:{step}')
    base_result=multi_turn_checker(copy.deepcopy(base_decoded),info['ground_truth'],info['task'],archive['category'],archive['model_id'])
    base_z=int(bool(base_result.get('valid'))); expected=base_lookup[('BFCL',iid)]['base_outcome_Z0']
    if base_z!=expected: fail(f'RT_BASE_Z0_MISMATCH={iid}:{base_z}:{expected}')
    cf=copy.deepcopy(base_decoded); cf[turn_index]=[list(gt_turn)]
    changed=[i for i,(a,b) in enumerate(zip(base_decoded,cf)) if a!=b]
    if changed!=[turn_index]: fail(f'RT_SINGLE_PERTURBATION_GATE={iid}:{step}:{changed}')
    if any(base_decoded[i]!=cf[i] for i in range(turn_index)): fail(f'RT_PREFIX_CHANGED={iid}:{step}')
    if any(base_decoded[i]!=cf[i] for i in range(turn_index+1,len(base_decoded))): fail(f'RT_SUFFIX_CHANGED={iid}:{step}')
    cf_result=multi_turn_checker(copy.deepcopy(cf),info['ground_truth'],info['task'],archive['category'],archive['model_id'])
    cf_z=int(bool(cf_result.get('valid'))); O_t=0; N_t=int(cf_z==base_z); R_t=int(O_t==1 or N_t==1)
    rt_rows.append({'benchmark':'BFCL','instance_id':iid,'step_index':step,'precondition_y_t':0,'causal_self_repair_status':'IDENTIFIED',
        'causal_self_repair_R_t':R_t,'O_t':O_t,'N_t':N_t,'base_terminal_outcome_Z':base_z,'counterfactual_terminal_outcome_Z':cf_z,
        'changed_turn_indices':changed,'prefix_fixed':True,'suffix_fixed':True,'single_perturbation_certified':True,'exact_restoration_certified':True,
        'target_neutralization':'OFFICIAL_BFCL_CURRENT_TURN_GROUND_TRUTH_CALLS','api_calls':0})

# Hard structural gates; do not hard-code outcome-direction counts beyond proven universe identities.
if len(base_rows)!=100: fail('BASE_ROWS_NOT_100')
if len(branch_rows)!=2518: fail('PHYSICAL_BRANCH_ROWS_NOT_2518')
if len(singleton_rows)!=631: fail('PRACTICAL_SINGLETON_ROWS_NOT_631')
if len(yt_rows)!=631: fail('YT_ROWS_NOT_631')
if Counter(r['benchmark'] for r in singleton_rows) != Counter({'MATH_SHEPHERD':343,'BFCL':228,'TOOLALPACA':60}):
    fail('SINGLETON_BENCHMARK_COUNTS=' + repr(Counter(r['benchmark'] for r in singleton_rows)))
if any(r['singleton_gain_status']!='IDENTIFIED' for r in singleton_rows if r['benchmark'] in {'BFCL','MATH_SHEPHERD'}):
    fail('BFCL_OR_MATH_SINGLETON_GAIN_NOT_IDENTIFIED')
if any(r['singleton_gain_status']=='IDENTIFIED' for r in singleton_rows if r['benchmark']=='TOOLALPACA'):
    fail('TOOLALPACA_SINGLETON_GAIN_SHOULD_REMAIN_NOT_IDENTIFIABLE_ZERO_API')

# Freeze outputs.
base_rows.sort(key=lambda r:(r['benchmark'],r['instance_id']))
branch_rows.sort(key=lambda r:r['execution_id'])
singleton_rows.sort(key=lambda r:(r['benchmark'],r['instance_id'],r['step_index'],r['execution_id']))
yt_rows.sort(key=lambda r:(r['benchmark'],r['instance_id'],r['step_index']))
rt_rows.sort(key=lambda r:(r['instance_id'],r['step_index']))
for p,rows in [(BASE_OUT,base_rows),(BRANCH_OUT,branch_rows),(SINGLETON_OUT,singleton_rows),(YT_OUT,yt_rows),(RT_OUT,rt_rows)]: write_jsonl(p,rows)

summary={
 'status':'PASS', 'scope':'FINAL_STEP3F_POST_LABELS_AND_SINGLETON_GAINS', 'paper_authoritative':True, 'api_calls':0,
 'scientific_authority':'DECOUPLE_NAACL_SPEC5_1_20260921', 'engineering_status_authority':'CHECKLIST_V16',
 'step3e_authority':{'ledger_rows':2518,'executable_pass':2514,'unavailable':4,'ledger_sha256':EXPECTED['ledger'],'fanout_sha256':EXPECTED['fanout'],'joint_sha256':EXPECTED['joint']},
 'base_status_counts':{str(k):v for k,v in sorted(Counter((r['benchmark'],r['base_outcome_status']) for r in base_rows).items())},
 'physical_branch_status_counts':dict(Counter(r['intervention_outcome_status'] for r in branch_rows)),
 'physical_rescue_identified_rows':sum(r['rescue_status']=='IDENTIFIED' for r in branch_rows),
 'physical_harm_identified_rows':sum(r['harmful_intervention_status']=='IDENTIFIED' for r in branch_rows),
 'practical_singleton_rows':len(singleton_rows),
 'practical_singleton_status_counts':{str(k):v for k,v in sorted(Counter((r['benchmark'],r['singleton_gain_status']) for r in singleton_rows).items())},
 'practical_singleton_gain_counts':dict(Counter(str(r['singleton_empirical_gain']) for r in singleton_rows)),
 'yt_rows':len(yt_rows), 'yt_status_counts':{str(k):v for k,v in sorted(Counter((r['benchmark'],r['step_correctness_status'],r['y_t']) for r in yt_rows).items())},
 'rt_rows':len(rt_rows), 'rt_status_counts':{str(k):v for k,v in sorted(Counter((r['causal_self_repair_status'],r['causal_self_repair_R_t']) for r in rt_rows).items())},
 'interpretation_lock':{'final_success_alone_used_for_R_t':False,'diagnostic_oracle_singletons_used_for_practical_gain':False,'old_1000_labels_imported':False,'new_API_calls':0,'toolalpaca_unidentified_base_imputed':False},
 'next':'STEP3B_RETROSPECTIVE_ORACLE_RANKING_CLOSURE', 'outputs':{}
}
for p in [BASE_OUT,BRANCH_OUT,SINGLETON_OUT,YT_OUT,RT_OUT]: summary['outputs'][p.name]={'path':str(p),'sha256':sha256_file(p)}
SUMMARY_OUT.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')

manifest={'status':'PASS','step':'STEP3F','builder_sha256':sha256_file(Path(__file__).resolve()),'summary_sha256':sha256_file(SUMMARY_OUT),'inputs':{
 'ledger':{'path':str(LEDGER),'sha256':sha256_file(LEDGER)},'fanout':{'path':str(FANOUT),'sha256':sha256_file(FANOUT)},'joint':{'path':str(JOINT),'sha256':sha256_file(JOINT)},'handoff':{'path':str(HANDOFF),'sha256':sha256_file(HANDOFF)}},
 'api_calls':0,'formal_step3e_mutation':False,'old_1000_authority_imported':False,'next':'STEP3B_RETROSPECTIVE_ORACLE_RANKING_CLOSURE'}
MANIFEST_OUT.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')

hash_paths=[BASE_OUT,BRANCH_OUT,SINGLETON_OUT,YT_OUT,RT_OUT,SUMMARY_OUT,MANIFEST_OUT]
SHA_OUT.write_text(''.join(f'{sha256_file(p)}  {p}\n' for p in hash_paths),encoding='utf-8')
STATUS_OUT.write_text('STATUS=PASS\nSTEP3F=PASS_FROZEN_CANDIDATE\nAPI_CALLS=0\nFORMAL_STEP3E_MUTATION=NO\nOLD_1000_AUTHORITY_IMPORTED=NO\nNEXT=STEP3B_RETROSPECTIVE_ORACLE_RANKING_CLOSURE\n',encoding='utf-8')

print('CURRENT=STEP3F_FINAL_MATERIALIZATION')
print('FORMAL_LEDGER_ROWS=2518')
print('EXECUTABLE_PASS=2514')
print('UNAVAILABLE=4')
print('BASE_ROWS=100')
print('PHYSICAL_BRANCH_ROWS='+str(len(branch_rows)))
print('PRACTICAL_SINGLETON_ROWS='+str(len(singleton_rows)))
print('PRACTICAL_SINGLETON_IDENTIFIED='+str(sum(r['singleton_gain_status']=='IDENTIFIED' for r in singleton_rows)))
print('PRACTICAL_SINGLETON_NOT_IDENTIFIABLE='+str(sum(r['singleton_gain_status']!='IDENTIFIED' for r in singleton_rows)))
print('YT_ROWS='+str(len(yt_rows)))
print('YT_IDENTIFIED='+str(sum(r['step_correctness_status']=='IDENTIFIED' for r in yt_rows)))
print('RT_ROWS='+str(len(rt_rows)))
print('API_CALLS=0')
print('FORMAL_RESULT_MUTATION=NO')
print('PASS=STEP3F_FINAL_MATERIALIZATION')
print('NEXT=STEP3B_RETROSPECTIVE_ORACLE_RANKING_CLOSURE')
