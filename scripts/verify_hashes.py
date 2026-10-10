#!/usr/bin/env python3
import hashlib, sys
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
mode = sys.argv[1] if len(sys.argv) > 1 else 'all'

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def verify(label: str, base: Path, manifest: Path, verbose: bool) -> int:
    failures = 0
    for raw in manifest.read_text(encoding='utf-8').splitlines():
        if not raw.strip():
            continue
        digest, rel = raw.split(None, 1)
        rel = rel.strip()
        path = base / rel
        if not path.is_file():
            print(f'FAIL {label} missing {rel}')
            failures += 1
            continue
        got = sha256(path)
        if got != digest:
            print(f'FAIL {label} hash {rel}')
            failures += 1
        elif verbose:
            print(f'PASS {rel}')
    print(f'FINAL_{label.upper()}_HASH_STATUS=' + ('PASS' if failures == 0 else 'FAIL'))
    return failures

failures = 0
if mode in {'all', 'frozen'}:
    failures += verify(
        'frozen',
        repo / 'artifacts/frozen_inputs',
        repo / 'artifacts/FROZEN_INPUT_SHA256SUMS.txt',
        True,
    )
if mode in {'all', 'expected'}:
    failures += verify(
        'expected',
        repo / 'artifacts/expected',
        repo / 'artifacts/EXPECTED_SHA256SUMS.txt',
        False,
    )
raise SystemExit(0 if failures == 0 else 1)
