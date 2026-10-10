#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/reproduced/work"
SCRIPT="$WORK/10_PILOT/STEP4_V2_CLEAN_REBUILD/01_CODE/STEP4V2_VEF_AUBC_FINAL_INFERENCE/run_vef_aubc_permutation_holm.py"

if [ ! -f "$SCRIPT" ]; then
    echo "FAIL=DEFAULT_WORKTREE_NOT_FOUND"
    echo "NEXT=bash scripts/reproduce_all.sh"
    exit 2
fi

# Remove the frozen input copy so the final 100k-permutation script can write
# its fresh output in the disposable worktree.
OUTDIR="$WORK/10_PILOT/STEP4_V2_CLEAN_REBUILD/04_OUTPUTS/STEP4V2_VEF_AUBC_FINAL_INFERENCE"
FROZEN="$OUTDIR/VEF_AUBC_FINAL_PERMUTATION_HOLM_CORE15.tsv"
if [ -f "$FROZEN" ]; then
    mkdir -p "$ROOT/reproduced/full_permutation_frozen_backup"
    cp -f "$FROZEN" "$ROOT/reproduced/full_permutation_frozen_backup/"
    rm -f "$FROZEN"
fi
mkdir -p "$OUTDIR"

python3 "$SCRIPT" | tee "$ROOT/reproduced/logs/full_100k_permutation.log"
RC=${PIPESTATUS[0]}
if [ "$RC" -ne 0 ]; then
    echo "FINAL_FULL_PERMUTATION_STATUS=FAIL"
    exit "$RC"
fi

python3 - "$ROOT" "$WORK" <<'PY'
import csv, math, sys
from pathlib import Path
root=Path(sys.argv[1]); work=Path(sys.argv[2])
a=root/'artifacts/frozen_inputs/10_PILOT/STEP4_V2_CLEAN_REBUILD/04_OUTPUTS/STEP4V2_VEF_AUBC_FINAL_INFERENCE/VEF_AUBC_FINAL_PERMUTATION_HOLM_CORE15.tsv'
b=work/'10_PILOT/STEP4_V2_CLEAN_REBUILD/04_OUTPUTS/STEP4V2_VEF_AUBC_FINAL_INFERENCE/VEF_AUBC_FINAL_PERMUTATION_HOLM_CORE15.tsv'
with a.open() as fa,b.open() as fb:
    ra=list(csv.reader(fa,delimiter='\t')); rb=list(csv.reader(fb,delimiter='\t'))
ok=len(ra)==len(rb)
if ok:
    for xa,xb in zip(ra,rb):
        if len(xa)!=len(xb): ok=False; break
        for sa,sb in zip(xa,xb):
            if sa==sb: continue
            try:
                if math.isclose(float(sa),float(sb),rel_tol=1e-12,abs_tol=2e-12): continue
            except: pass
            ok=False; break
        if not ok: break
print('FINAL_FULL_PERMUTATION_STATUS=' + ('PASS' if ok else 'FAIL'))
raise SystemExit(0 if ok else 1)
PY
