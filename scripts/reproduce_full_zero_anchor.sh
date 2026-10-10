#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/reproduced/work"
CODE="$WORK/10_PILOT/STEP4_V2_CLEAN_REBUILD/01_CODE/STEP4V2_POSTD11_ZERO_ANCHOR_PROVENANCE/run_zero_anchored_vef_inference.py"
OUT="$WORK/10_PILOT/STEP4_V2_CLEAN_REBUILD/04_OUTPUTS/STEP4V2_POSTD11_ZERO_ANCHOR_PROVENANCE"
AUD="$WORK/10_PILOT/STEP4_V2_CLEAN_REBUILD/06_AUDIT/STEP4V2_POSTD11_ZERO_ANCHOR_PROVENANCE"

if [ ! -f "$CODE" ]; then
  echo "FAIL: disposable worktree missing. Run bash scripts/reproduce_all.sh first."
  exit 2
fi
mkdir -p "$OUT" "$AUD"
rm -f "$OUT/ZERO_ANCHORED_VEF_CORE10.tsv" "$OUT/ZERO_ANCHOR_METHOD_SUMMARY.tsv"

echo "CURRENT: full zero-anchor inferential rerun"
echo "PERMUTATIONS=100000"
echo "BOOTSTRAPS=10000"
echo "API_CALLS=0"
python3 "$CODE"
RC=$?
if [ "$RC" -ne 0 ]; then
  echo "FINAL_FULL_ZERO_ANCHOR_STATUS=FAIL"
  exit "$RC"
fi

python3 - "$ROOT" "$WORK" <<'PY'
import csv, math, sys
from pathlib import Path
repo=Path(sys.argv[1]); work=Path(sys.argv[2])
e=repo/'artifacts/expected/STEP4V2_POSTD11_ZERO_ANCHOR_PROVENANCE'
g=work/'10_PILOT/STEP4_V2_CLEAN_REBUILD/04_OUTPUTS/STEP4V2_POSTD11_ZERO_ANCHOR_PROVENANCE'
for name in ['ZERO_ANCHORED_VEF_CORE10.tsv','ZERO_ANCHOR_METHOD_SUMMARY.tsv']:
    er=list(csv.reader((e/name).open(),delimiter='\t')); gr=list(csv.reader((g/name).open(),delimiter='\t'))
    if len(er)!=len(gr): raise SystemExit(f'FAIL {name}: row count')
    for i,(a,b) in enumerate(zip(er,gr),1):
        if len(a)!=len(b): raise SystemExit(f'FAIL {name}: col count row {i}')
        for j,(x,y) in enumerate(zip(a,b),1):
            if x==y: continue
            try:
                if math.isclose(float(x),float(y),rel_tol=1e-12,abs_tol=2e-12): continue
            except Exception: pass
            raise SystemExit(f'FAIL {name} cell {i},{j}: {x!r}!={y!r}')
    print('PASS',name)
print('FINAL_FULL_ZERO_ANCHOR_STATUS=PASS')
PY
