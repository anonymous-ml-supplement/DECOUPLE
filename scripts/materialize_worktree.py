#!/usr/bin/env python3
from pathlib import Path
import shutil, sys

repo = Path(__file__).resolve().parents[1]
work = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else repo / 'reproduced/work'
source = repo / 'artifacts/frozen_inputs/10_PILOT'
analysis = repo / 'analysis/final'

if work.exists():
    shutil.rmtree(work)
work.mkdir(parents=True, exist_ok=True)
shutil.copytree(source, work / '10_PILOT', dirs_exist_ok=True)
code_dst = work / '10_PILOT/STEP4_V2_CLEAN_REBUILD/01_CODE'
code_dst.mkdir(parents=True, exist_ok=True)
shutil.copytree(analysis, code_dst, dirs_exist_ok=True)

for path in code_dst.rglob('*.py'):
    text = path.read_text(encoding='utf-8')
    text = text.replace('__DECOUPLE_ROOT__', str(work))
    path.write_text(text, encoding='utf-8')

for directory in code_dst.iterdir():
    if not directory.is_dir():
        continue
    name = directory.name
    (work / f'10_PILOT/STEP4_V2_CLEAN_REBUILD/04_OUTPUTS/{name}').mkdir(parents=True, exist_ok=True)
    (work / f'10_PILOT/STEP4_V2_CLEAN_REBUILD/06_AUDIT/{name}').mkdir(parents=True, exist_ok=True)

print(f'PASS worktree_materialized={work}')
