#!/usr/bin/env python3
from pathlib import Path
import ast, sys

repo = Path(__file__).resolve().parents[1]
errors = []
files = [p for p in repo.rglob('*.py') if 'reproduced' not in p.parts and '__pycache__' not in p.parts]
for p in files:
    try:
        source = p.read_text(encoding='utf-8')
        compile(source, str(p), 'exec')
        ast.parse(source)
    except Exception as exc:
        errors.append((p.relative_to(repo), str(exc)))

required_first_party = [
    repo / 'pipeline/data_generation/bfcl_docker_trajectory_worker.py',
    repo / 'pipeline/vendor/bfcl_tool_conversion/bfcl_openai_responses_tool_conversion.py',
    repo / 'pipeline/data_generation/generate_toolalpaca_pilot25_base_trajectories.py',
    repo / 'pipeline/execution/step3e_bfcl_tool_v2_impl.py',
    repo / 'pipeline/execution/step3e_execution_state_machine.py',
]
for p in required_first_party:
    if not p.is_file():
        errors.append((p.relative_to(repo), 'missing first-party helper'))

print(f'PYTHON_SOURCE_FILES={len(files)}')
print('EXTERNAL_MODEL_INTERFACES=bfcl_eval,model_utils,prm_evaluation,openai,torch,transformers,tiktoken')
if errors:
    for p, msg in errors:
        print(f'FAIL source_tree {p}: {msg}')
    print('FINAL_SOURCE_TREE_STATUS=FAIL')
    raise SystemExit(1)
print('PASS python_syntax_all')
print('PASS bundled_first_party_helpers')
print('FINAL_SOURCE_TREE_STATUS=PASS')
