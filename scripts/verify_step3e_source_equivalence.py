#!/usr/bin/env python3
"""Read-only comparison of a private STEP3E source pair to publication copies.

No private paths are embedded here. The user supplies the original source path.
We assert exact *text* equality after solely normalizing the original root
literal, rather than claiming a vague high-level AST similarity. This is
source comparison, not proof of historical runtime/checkpoint equivalence.
"""
import argparse
import ast
import hashlib
import re
from pathlib import Path

PUB = Path(__file__).resolve().parents[1] / 'pipeline/execution'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def compare(priv_path,pub_path):
    private = priv_path.read_text(encoding='utf-8')
    public = pub_path.read_text(encoding='utf-8')
    ast.parse(private);ast.parse(public)
    private_root_match = re.search(r'^ROOT\s*=\s*Path\([\x27\"]([^\x27\"]+)[\x27\"]\)',private,re.M)
    public_root_match = re.search(r'^ROOT\s*=\s*Path\([\x27\"]([^\x27\"]+)[\x27\"]\)',public,re.M)
    if not private_root_match or not public_root_match:
        return 'OPEN:cannot_identify_both_roots'
    old, new = private_root_match.group(1),public_root_match.group(1)
    if not Path(old).is_absolute() or new != '__DECOUPLE_ROOT__':
        return 'OPEN:unexpected_root_mapping'
    return 'PASS:exact_source_modulo_root_prefix' if private.replace(old,new)==public else 'OPEN:non_path_logic_diff'


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--private-runner',required=True,type=Path)
    p.add_argument('--private-state-machine',required=True,type=Path)
    args=p.parse_args()
    pub_runner=PUB/'run_step3e_formal_replay.py'
    pub_sm=PUB/'step3e_execution_state_machine.py'
    rc=0
    verdict=compare(args.private_runner,pub_runner)
    print('STEP3E_RUNNER='+verdict)
    if not verdict.startswith('PASS'): rc=1
    exact=(args.private_state_machine.read_bytes()==pub_sm.read_bytes())
    print('STEP3E_STATE_MACHINE='+('PASS:byte_identical' if exact else 'OPEN:byte_difference'))
    if not exact:rc=1
    print('PRIVATE_RUNNER_SHA256='+sha(args.private_runner))
    print('RELEASE_RUNNER_SHA256='+sha(pub_runner))
    print('PRIVATE_STATE_SHA256='+sha(args.private_state_machine))
    print('RELEASE_STATE_SHA256='+sha(pub_sm))
    print('HISTORICAL_RUNTIME_EQUIVALENCE=NOT_ASSESSED')
    print('DO_NOT_TOUCH=FROZEN_EXPERIMENTS')
    return rc

if __name__=='__main__':
    raise SystemExit(main())
