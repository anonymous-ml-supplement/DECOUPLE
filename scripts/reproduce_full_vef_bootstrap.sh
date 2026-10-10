#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/reproduced/work"
SCRIPT="$WORK/10_PILOT/STEP4_V2_CLEAN_REBUILD/01_CODE/STEP4V2_VEF_AUBC_INFERENCE/run_full_vef_aubc_bootstrap.py"
OUTDIR="$WORK/10_PILOT/STEP4_V2_CLEAN_REBUILD/04_OUTPUTS/STEP4V2_VEF_AUBC_INFERENCE"
AUDDIR="$WORK/10_PILOT/STEP4_V2_CLEAN_REBUILD/06_AUDIT/STEP4V2_VEF_AUBC_INFERENCE"
if [ ! -f "$SCRIPT" ]; then
  echo "FAIL: disposable worktree missing. Run bash scripts/reproduce_all.sh first."
  exit 2
fi
mkdir -p "$OUTDIR" "$AUDDIR" "$ROOT/reproduced/logs"
echo "CURRENT: full 10,000-cluster-bootstrap VEF-AUBC rerun"
echo "API_CALLS=0"
python3 "$SCRIPT" > "$ROOT/reproduced/logs/full_vef_bootstrap.log" 2>&1
RC=$?
cat "$ROOT/reproduced/logs/full_vef_bootstrap.log"
if [ "$RC" -ne 0 ]; then
  echo "FINAL_FULL_VEF_BOOTSTRAP_STATUS=FAIL"
  exit "$RC"
fi
python3 - "$ROOT" "$WORK" <<'PY'
import csv, math, sys
from pathlib import Path
root=Path(sys.argv[1]); work=Path(sys.argv[2])
e=root/'artifacts/expected/STEP4V2_VEF_AUBC_INFERENCE'
g=work/'10_PILOT/STEP4_V2_CLEAN_REBUILD/04_OUTPUTS/STEP4V2_VEF_AUBC_INFERENCE'
for name in ['FULL_VEF_AUBC_BOOTSTRAP_CORE_15.tsv','FULL_VEF_AUBC_BOOTSTRAP_SPECIALIZED_2.tsv']:
    with (e/name).open() as fa,(g/name).open() as fb:
        ra=list(csv.reader(fa,delimiter='\t')); rb=list(csv.reader(fb,delimiter='\t'))
    if len(ra)!=len(rb): raise SystemExit(f'FAIL {name}: row count')
    for i,(a,b) in enumerate(zip(ra,rb),1):
        if len(a)!=len(b): raise SystemExit(f'FAIL {name}: column count row {i}')
        for j,(x,y) in enumerate(zip(a,b),1):
            if x==y: continue
            try:
                if math.isclose(float(x),float(y),rel_tol=1e-12,abs_tol=2e-12): continue
            except Exception: pass
            raise SystemExit(f'FAIL {name} cell {i},{j}: {x!r}!={y!r}')
    print('PASS',name)
print('FINAL_FULL_VEF_BOOTSTRAP_STATUS=PASS')
PY
