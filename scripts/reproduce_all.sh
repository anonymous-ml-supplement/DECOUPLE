#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export MPLBACKEND=Agg
WORK="$ROOT/reproduced/work"
LOG="$ROOT/reproduced/logs"
STATUS=0

# The audit scripts run on standard-library Python, but numerical reproduction
# must use an environment with NumPy and Matplotlib. Select it automatically.
if ! source "$ROOT/scripts/select_offline_python.sh"; then
    echo "FINAL_REPRODUCTION_STATUS=FAIL"
    exit 2
fi

run_py () {
    NAME="$1"
    REL="$2"
    echo
    echo "===== RUN $NAME ====="
    python3 "$WORK/10_PILOT/STEP4_V2_CLEAN_REBUILD/01_CODE/$REL" > "$LOG/$NAME.log" 2>&1
    RC=$?
    if [ "$RC" -eq 0 ]; then
        echo "PASS $NAME"
        tail -5 "$LOG/$NAME.log"
    else
        echo "FAIL $NAME rc=$RC"
        tail -30 "$LOG/$NAME.log"
        STATUS=1
    fi
}

echo "============================================================"
echo "CURRENT: DECOUPLE zero-API paper reproduction"
echo "ROOT=$ROOT"
echo "API_CALLS=0"
echo "MODEL_EXECUTION=0"
echo "PHYSICAL_EXECUTION=0"
echo "============================================================"

python3 "$ROOT/scripts/check_environment.py"
if [ "$?" -ne 0 ]; then
    echo "FINAL_REPRODUCTION_STATUS=FAIL"
    echo "NEXT=consult docs/ENVIRONMENT.md"
    exit 2
fi

python3 - <<'PY'
try:
    import numpy
    print('PASS numpy', numpy.__version__)
except Exception as e:
    print('FAIL numpy unavailable:', e)
    raise SystemExit(2)
PY
if [ "$?" -ne 0 ]; then
    echo "FINAL_REPRODUCTION_STATUS=FAIL"
    echo "NEXT=use Python 3.10 and install the pinned requirements.txt in a separate environment"
    exit 2
fi

python3 "$ROOT/scripts/audit_source_tree.py"
if [ "$?" -ne 0 ]; then
    echo "FINAL_REPRODUCTION_STATUS=FAIL"
    exit 2
fi

python3 "$ROOT/scripts/verify_hashes.py" frozen
if [ "$?" -ne 0 ]; then
    echo "FINAL_REPRODUCTION_STATUS=FAIL"
    exit 2
fi

python3 "$ROOT/scripts/verify_hashes.py" expected
if [ "$?" -ne 0 ]; then
    echo "FINAL_REPRODUCTION_STATUS=FAIL"
    exit 2
fi

rm -rf "$WORK" "$LOG"
mkdir -p "$LOG"
python3 "$ROOT/scripts/materialize_worktree.py" "$WORK"
if [ "$?" -ne 0 ]; then
    echo "FINAL_REPRODUCTION_STATUS=FAIL"
    exit 2
fi

run_py exact_budget_tables \
  STEP4V2_POSTD11_EXACT_BUDGET_MAIN_TABLE/build_d11_detailed_primary_tables.py

run_py vef_manuscript_tables \
  STEP4V2_VEF_MANUSCRIPT/build_absolute_vef_manuscript_tables.py

run_py nonenvelope_t4 \
  STEP4V2_POSTD11_T4_NONENVELOPE_INFERENCE/run_t4_nonenvelope_inference.py

run_py grid_stability \
  STEP4V2_POSTD11_GRID_STABILITY/run_positive_vef_grid_stability.py

run_py crossfit_aubc \
  STEP4V2_POSTD11_CROSSFIT_AUBC/materialize_crossfit_a_plus_optimism.py

echo
echo "===== RUN original_LOO_fold_choice_reconstruction ====="
python3 "$ROOT/scripts/rebuild_loo_from_d11.py" > "$LOG/loo_upstream_replay.log" 2>&1
if [ "$?" -eq 0 ]; then
    echo "PASS original_LOO_fold_choice_reconstruction"
    tail -7 "$LOG/loo_upstream_replay.log"
else
    echo "FAIL original_LOO_fold_choice_reconstruction"
    tail -30 "$LOG/loo_upstream_replay.log"
    STATUS=1
fi

echo
echo "===== RUN zero_anchor_fast ====="
python3 "$ROOT/scripts/rebuild_zero_anchor_fast.py" "$WORK" > "$LOG/zero_anchor_fast.log" 2>&1
if [ "$?" -eq 0 ]; then
    echo "PASS zero_anchor_fast"
    tail -5 "$LOG/zero_anchor_fast.log"
else
    echo "FAIL zero_anchor_fast"
    tail -30 "$LOG/zero_anchor_fast.log"
    STATUS=1
fi

run_py realized_displacement_regret \
  STEP4V2_POSTD11_REALIZED_DISPLACEMENT_REGRET/build_realized_displacement_regret.py

run_py vef_saturation \
  STEP4V2_VEF_SATURATION_AUDIT/audit_exact_vs_vef_saturation.py

run_py vef_flattening \
  STEP4V2_POSTD11_VEF_FLATTENING_AUDIT/audit_vef_flattening_and_exact_budget_reversals.py

# The 100k-permutation authority is included frozen by default. Recompute the
# global Holm-15 sensitivity from that frozen table without API/model calls.
run_py global_holm15 \
  STEP4V2_POSTD11_GLOBAL_HOLM15/run_global_holm15_sensitivity.py

run_py specialized_toolprm_audit \
  STEP4V2_POSTD11_TOOLPRM_FINAL_AUDIT/seal_toolprm_overlap_effective_n_final.py

run_py all_in_cost_claim_gate \
  STEP4V2_POSTD11_ALL_IN_COST_GATE/audit_existing_all_in_cost_authority.py

echo
echo "===== RUN k4_zero_api_sensitivity ====="
python3 "$ROOT/scripts/rebuild_k4_sensitivity.py" "$WORK" > "$LOG/k4_zero_api_sensitivity.log" 2>&1
if [ "$?" -eq 0 ]; then
    echo "PASS k4_zero_api_sensitivity"
    tail -5 "$LOG/k4_zero_api_sensitivity.log"
else
    echo "FAIL k4_zero_api_sensitivity"
    tail -30 "$LOG/k4_zero_api_sensitivity.log"
    STATUS=1
fi


echo
echo "===== RUN math_zero_to_5_accounting ====="
python3 "$ROOT/scripts/rebuild_math_zero_to_5.py" "$WORK" > "$LOG/math_zero_to_5_accounting.log" 2>&1
if [ "$?" -eq 0 ]; then
    echo "PASS math_zero_to_5_accounting"
    tail -5 "$LOG/math_zero_to_5_accounting.log"
else
    echo "FAIL math_zero_to_5_accounting"
    tail -30 "$LOG/math_zero_to_5_accounting.log"
    STATUS=1
fi

echo
echo "===== RUN allocation_active ====="
python3 "$ROOT/scripts/rebuild_allocation_active.py" "$WORK" > "$LOG/allocation_active.log" 2>&1
if [ "$?" -eq 0 ]; then
    echo "PASS allocation_active"
    tail -5 "$LOG/allocation_active.log"
else
    echo "FAIL allocation_active"
    tail -30 "$LOG/allocation_active.log"
    STATUS=1
fi

echo
echo "===== RUN earliest_step_coverage ====="
python3 "$ROOT/scripts/rebuild_earliest_step_coverage.py" "$WORK" > "$LOG/earliest_step_coverage.log" 2>&1
if [ "$?" -eq 0 ]; then
    echo "PASS earliest_step_coverage"
    tail -5 "$LOG/earliest_step_coverage.log"
else
    echo "FAIL earliest_step_coverage"
    tail -30 "$LOG/earliest_step_coverage.log"
    STATUS=1
fi

echo
echo "===== COMPARE AGAINST FROZEN EXPECTED OUTPUTS ====="
python3 "$ROOT/scripts/compare_outputs.py" "$WORK"
if [ "$?" -ne 0 ]; then STATUS=1; fi

echo
echo "===== VALIDATE PAPER CLAIM NUMBERS ====="
python3 "$ROOT/scripts/validate_claims.py" "$WORK"
if [ "$?" -ne 0 ]; then STATUS=1; fi

echo
echo "===== ANONYMITY SCAN ====="
python3 "$ROOT/scripts/check_anonymity.py"
if [ "$?" -ne 0 ]; then STATUS=1; fi

echo
if [ "$STATUS" -eq 0 ]; then
    echo "============================================================"
    echo "FINAL_REPRODUCTION_STATUS=PASS"
    echo "DONE=ZERO_API_PAPER_REPRODUCTION"
    echo "NEXT=OPTIONAL_FULL_INFERENCE_RERUNS"
    echo "============================================================"
else
    echo "============================================================"
    echo "FINAL_REPRODUCTION_STATUS=FAIL"
    echo "NEXT=INSPECT_reproduced/logs"
    echo "============================================================"
fi
exit "$STATUS"
