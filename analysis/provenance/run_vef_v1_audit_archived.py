#!/usr/bin/env python3

import csv
import hashlib
import json
import statistics
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path("__DECOUPLE_ROOT__/10_PILOT/STEP4_V2_CLEAN_REBUILD")

SOURCE = (
    ROOT
    / "04_OUTPUTS/STEP4V2_D11_FINAL_RANDOM_AWARE_ANALYSIS"
    / "D11_FINAL_ALL_LOGICAL_RESULTS.tsv"
)

FREEZE = (
    ROOT
    / "08_TECHNICAL_DOCS/STEP4V2_VEF_AUDIT"
    / "VEF_V1_PREANALYSIS_FREEZE_20260928.md"
)

OUT = ROOT / "04_OUTPUTS/STEP4V2_VEF_AUDIT"
AUDIT = ROOT / "06_AUDIT/STEP4V2_VEF_AUDIT"

OUT.mkdir(parents=True, exist_ok=True)
AUDIT.mkdir(parents=True, exist_ok=True)

EXPECTED_SOURCE_SHA = (
    "32d160166c3546f62b579f30e2e007e6213fb64596fca9b9ecb52f3b1bb83c53"
)

GRID = [5,10,20,30,40,50,60,70,80,90,100]

BASELINES = {
    "H-only",
    "p-only",
    "Random",
    "Step-PRM",
    "PRM@BoK",
    "ToolPRM-GRPO",
}

EPS = 1e-12


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def fail(msg):
    print(f"FAIL={msg}")
    raise RuntimeError(msg)


def norm_benchmark(x):
    y = str(x).strip().upper().replace("-", "_").replace(" ", "_")
    if y == "MATH_SHEPHERD":
        return "Math-Shepherd"
    if y == "TOOLALPACA":
        return "ToolAlpaca"
    if y == "BFCL":
        return "BFCL"
    return str(x).strip()


def budget_pct(x):
    v = float(x)
    if v <= 1.0 + EPS:
        v *= 100.0
    return int(round(v))


def mean(xs):
    return sum(xs) / len(xs)


def direction(x):
    if x > EPS:
        return "POSITIVE"
    if x < -EPS:
        return "NEGATIVE"
    return "TIE"


def cumulative_max(xs):
    out = []
    cur = None
    for x in xs:
        if cur is None or x > cur:
            cur = x
        out.append(cur)
    return out


def linear_auc(ys):
    xs = [x / 100.0 for x in GRID]
    area = 0.0
    for i in range(1, len(xs)):
        area += (
            0.5
            * (ys[i-1] + ys[i])
            * (xs[i] - xs[i-1])
        )
    return area / (xs[-1] - xs[0])


def choose_budget(collapsed, benchmark, method, train_ids, cap):
    candidates = [b for b in GRID if b <= cap]

    scored = []

    for b in candidates:
        vals = [
            collapsed[(benchmark, method, b, iid)]
            for iid in train_ids
        ]
        scored.append((mean(vals), b))

    best_score = max(x[0] for x in scored)

    best_budgets = [
        b
        for score, b in scored
        if abs(score - best_score) <= EPS
    ]

    return min(best_budgets)


print("CURRENT=VEF_V1_FULL_D11_AUDIT")
print("D11_GRID=" + ",".join(str(x) for x in GRID))
print("API_CALLS=0")
print("MODEL_RUNS=0")
print("PHYSICAL_REPLAY=0")
print("METHOD_RETUNING=NO")
print("CONFIRMATORY_STATUS=NO")
print()

for p in (SOURCE, FREEZE):
    if not p.exists():
        fail(f"MISSING_SOURCE={p}")
    print(f"SOURCE={p}")
    print(f"SOURCE_SHA256={sha256(p)}")

if sha256(SOURCE) != EXPECTED_SOURCE_SHA:
    fail("FROZEN_D11_SOURCE_SHA_MISMATCH")

# ------------------------------------------------------------
# Collapse Random replicate rows within original instance-budget.
# ------------------------------------------------------------
raw = defaultdict(list)

with open(SOURCE, "r", encoding="utf-8", newline="") as f:
    r = csv.DictReader(f, delimiter="\t")

    for row in r:
        benchmark = norm_benchmark(row["benchmark"])
        method = row["method"].strip()
        budget = budget_pct(row["budget"])

        if budget not in GRID:
            continue

        iid = row["instance_id"]
        z = float(row["terminal_Z"])

        raw[(benchmark, method, budget, iid)].append(z)

collapsed = {
    key: mean(vals)
    for key, vals in raw.items()
}

methods_by_benchmark = defaultdict(set)

for benchmark, method, budget, iid in collapsed:
    methods_by_benchmark[benchmark].add(method)

pairs = []

for benchmark in sorted(methods_by_benchmark):
    for baseline in sorted(methods_by_benchmark[benchmark]):
        if baseline in BASELINES:
            pairs.append((benchmark, baseline))

if len(pairs) != 17:
    fail(f"EXPECTED_17_PAIRS_GOT={len(pairs)}")

# ------------------------------------------------------------
# VEF + savings + cross-fitting.
# ------------------------------------------------------------
summary_rows = []
curve_rows = []
saving_rows = []

for benchmark, baseline in pairs:

    complete_sets = []

    for budget in GRID:
        de_ids = {
            iid
            for (b, m, bb, iid) in collapsed
            if b == benchmark
            and m == "DECOUPLE"
            and bb == budget
        }

        bl_ids = {
            iid
            for (b, m, bb, iid) in collapsed
            if b == benchmark
            and m == baseline
            and bb == budget
        }

        complete_sets.append(de_ids & bl_ids)

    panel = sorted(set.intersection(*complete_sets))

    if len(panel) < 2:
        fail(f"INSUFFICIENT_PANEL={benchmark}|{baseline}")

    # Aggregate ordinary curves.
    de_u = []
    bl_u = []

    for budget in GRID:
        de_u.append(mean([
            collapsed[(benchmark, "DECOUPLE", budget, iid)]
            for iid in panel
        ]))

        bl_u.append(mean([
            collapsed[(benchmark, baseline, budget, iid)]
            for iid in panel
        ]))

    de_f = cumulative_max(de_u)
    bl_f = cumulative_max(bl_u)

    frontier_delta = [
        d - b
        for d, b in zip(de_f, bl_f)
    ]

    strict_caps = sum(x > EPS for x in frontier_delta)
    tie_caps = sum(abs(x) <= EPS for x in frontier_delta)
    neg_caps = sum(x < -EPS for x in frontier_delta)

    worst_margin = min(frontier_delta)
    nonloss11 = int(neg_caps == 0)

    # --------------------------------------------------------
    # Verification savings.
    # Distinct baseline VEF utility targets.
    # --------------------------------------------------------
    targets = []

    for x in bl_f:
        xr = round(x, 12)
        if xr not in targets:
            targets.append(xr)

    savings = []
    attainable = 0

    for target in targets:

        bl_candidates = [
            GRID[j]
            for j, u in enumerate(bl_u)
            if u >= target - EPS
        ]

        de_candidates = [
            GRID[j]
            for j, u in enumerate(de_u)
            if u >= target - EPS
        ]

        if not bl_candidates:
            fail("BASELINE_TARGET_SELF_UNATTAINABLE")

        bl_cost = min(bl_candidates)

        if de_candidates:
            de_cost = min(de_candidates)
            saving = bl_cost - de_cost
            attainable += 1
            savings.append(saving)
            status = "ATTAINABLE"
        else:
            de_cost = ""
            saving = ""
            status = "DE_NOT_ATTAINABLE"

        saving_rows.append({
            "benchmark": benchmark,
            "baseline": baseline,
            "matched_instance_n": len(panel),
            "target_utility": f"{target:.12f}",
            "baseline_min_budget_pct": bl_cost,
            "DE_min_budget_pct": de_cost,
            "budget_saving_pct_points": saving,
            "status": status,
        })

    target_coverage = attainable / len(targets)

    mean_saving = (
        mean(savings)
        if savings
        else float("nan")
    )

    median_saving = (
        statistics.median(savings)
        if savings
        else float("nan")
    )

    min_saving = (
        min(savings)
        if savings
        else float("nan")
    )

    # --------------------------------------------------------
    # Leave-one-instance-out cross-fitted VEF.
    # --------------------------------------------------------
    cf_de = []
    cf_bl = []
    cf_de_budget_mean = []
    cf_bl_budget_mean = []

    for cap in GRID:

        held_de = []
        held_bl = []
        chosen_de = []
        chosen_bl = []

        for heldout in panel:
            train = [
                iid
                for iid in panel
                if iid != heldout
            ]

            de_budget = choose_budget(
                collapsed,
                benchmark,
                "DECOUPLE",
                train,
                cap,
            )

            bl_budget = choose_budget(
                collapsed,
                benchmark,
                baseline,
                train,
                cap,
            )

            held_de.append(
                collapsed[
                    (
                        benchmark,
                        "DECOUPLE",
                        de_budget,
                        heldout,
                    )
                ]
            )

            held_bl.append(
                collapsed[
                    (
                        benchmark,
                        baseline,
                        bl_budget,
                        heldout,
                    )
                ]
            )

            chosen_de.append(de_budget)
            chosen_bl.append(bl_budget)

        cf_de.append(mean(held_de))
        cf_bl.append(mean(held_bl))
        cf_de_budget_mean.append(mean(chosen_de))
        cf_bl_budget_mean.append(mean(chosen_bl))

    cf_delta = [
        d - b
        for d, b in zip(cf_de, cf_bl)
    ]

    cf_strict = sum(x > EPS for x in cf_delta)
    cf_tie = sum(abs(x) <= EPS for x in cf_delta)
    cf_neg = sum(x < -EPS for x in cf_delta)

    cf_nonloss11 = int(cf_neg == 0)
    cf_worst = min(cf_delta)
    cf_auc = linear_auc(cf_delta)

    for j, budget in enumerate(GRID):
        curve_rows.append({
            "benchmark": benchmark,
            "baseline": baseline,
            "matched_instance_n": len(panel),
            "budget_cap_pct": budget,

            "DE_exact_utility":
                f"{de_u[j]:.9f}",
            "baseline_exact_utility":
                f"{bl_u[j]:.9f}",

            "DE_VEF":
                f"{de_f[j]:.9f}",
            "baseline_VEF":
                f"{bl_f[j]:.9f}",
            "VEF_delta":
                f"{frontier_delta[j]:.9f}",

            "CF_DE_utility":
                f"{cf_de[j]:.9f}",
            "CF_baseline_utility":
                f"{cf_bl[j]:.9f}",
            "CF_delta":
                f"{cf_delta[j]:.9f}",

            "CF_DE_mean_selected_budget_pct":
                f"{cf_de_budget_mean[j]:.6f}",
            "CF_baseline_mean_selected_budget_pct":
                f"{cf_bl_budget_mean[j]:.6f}",
        })

    summary_rows.append({
        "benchmark": benchmark,
        "baseline": baseline,
        "matched_instance_n": len(panel),

        "VEF_nonloss_all_11":
            nonloss11,
        "VEF_worst_cap_margin":
            f"{worst_margin:.9f}",
        "VEF_strict_better_caps":
            strict_caps,
        "VEF_tie_caps":
            tie_caps,
        "VEF_negative_caps":
            neg_caps,

        "saving_target_count":
            len(targets),
        "saving_attainable_count":
            attainable,
        "saving_target_coverage":
            f"{target_coverage:.9f}",
        "mean_budget_saving_pct_points":
            f"{mean_saving:.9f}",
        "median_budget_saving_pct_points":
            f"{median_saving:.9f}",
        "min_budget_saving_pct_points":
            f"{min_saving:.9f}",

        "CF_nonloss_all_11":
            cf_nonloss11,
        "CF_worst_cap_margin":
            f"{cf_worst:.9f}",
        "CF_strict_better_caps":
            cf_strict,
        "CF_tie_caps":
            cf_tie,
        "CF_negative_caps":
            cf_neg,
        "CF_linear_aubc_delta":
            f"{cf_auc:.9f}",
    })

# ------------------------------------------------------------
# Print the old 1/17 negative AFTER the definitions were frozen.
# ------------------------------------------------------------
print()
print("=== ORACLE VEF RESULT ===")

oracle_pos = 0
oracle_tie = 0
oracle_fail = 0

for r in summary_rows:
    margin = float(r["VEF_worst_cap_margin"])

    if int(r["VEF_nonloss_all_11"]) == 0:
        oracle_fail += 1
        label = "FAIL"
    elif margin > EPS:
        oracle_pos += 1
        label = "STRICT_ALL_CAP_WIN"
    else:
        oracle_tie += 1
        label = "NONLOSS_WITH_TIE"

    print(
        f"{r['benchmark']}|{r['baseline']}|"
        f"STATUS={label}|"
        f"WORST={r['VEF_worst_cap_margin']}|"
        f"WIN_CAPS={r['VEF_strict_better_caps']}|"
        f"TIE_CAPS={r['VEF_tie_caps']}|"
        f"NEG_CAPS={r['VEF_negative_caps']}"
    )

print()
print(
    f"ORACLE_VEF_PAIR_STATUS="
    f"STRICT={oracle_pos}|"
    f"NONLOSS_TIE={oracle_tie}|"
    f"FAIL={oracle_fail}"
)

print()
print("=== PREVIOUS 1/17 FAIL DETAIL ===")

for r in summary_rows:
    if int(r["VEF_nonloss_all_11"]) == 0:
        print(
            f"VEF_FAIL_PAIR="
            f"{r['benchmark']}|{r['baseline']}|"
            f"WORST_MARGIN={r['VEF_worst_cap_margin']}"
        )

        for x in curve_rows:
            if (
                x["benchmark"] == r["benchmark"]
                and x["baseline"] == r["baseline"]
            ):
                print(
                    f"BUDGET={x['budget_cap_pct']}|"
                    f"DE_VEF={x['DE_VEF']}|"
                    f"BASE_VEF={x['baseline_VEF']}|"
                    f"DELTA={x['VEF_delta']}"
                )

# ------------------------------------------------------------
# Cross-fitted result.
# ------------------------------------------------------------
print()
print("=== CROSS-FITTED VEF RESULT ===")

cf_nonloss = 0
cf_fail = 0

for r in summary_rows:
    if int(r["CF_nonloss_all_11"]) == 1:
        cf_nonloss += 1
        status = "NONLOSS_ALL_11"
    else:
        cf_fail += 1
        status = "FAIL"

    print(
        f"{r['benchmark']}|{r['baseline']}|"
        f"STATUS={status}|"
        f"WORST={r['CF_worst_cap_margin']}|"
        f"WIN_CAPS={r['CF_strict_better_caps']}|"
        f"TIE_CAPS={r['CF_tie_caps']}|"
        f"NEG_CAPS={r['CF_negative_caps']}|"
        f"AUBC={r['CF_linear_aubc_delta']}"
    )

print()
print(
    f"CROSSFIT_VEF_NONLOSS_ALL_11_PAIRS="
    f"{cf_nonloss}/17"
)
print(
    f"CROSSFIT_VEF_FAIL_PAIRS="
    f"{cf_fail}/17"
)

# ------------------------------------------------------------
# Savings summary.
# ------------------------------------------------------------
print()
print("=== VERIFICATION SAVINGS ===")

for r in summary_rows:
    print(
        f"{r['benchmark']}|{r['baseline']}|"
        f"TARGET_COVERAGE={r['saving_target_coverage']}|"
        f"MEAN_SAVE_PP={r['mean_budget_saving_pct_points']}|"
        f"MEDIAN_SAVE_PP={r['median_budget_saving_pct_points']}|"
        f"MIN_SAVE_PP={r['min_budget_saving_pct_points']}"
    )

# ------------------------------------------------------------
# Persist.
# ------------------------------------------------------------
summary_path = OUT / "VEF_V1_PAIR_SUMMARY_17.tsv"
curve_path = OUT / "VEF_V1_FULL_11_CAP_CURVES_187.tsv"
saving_path = OUT / "VEF_V1_VERIFICATION_SAVINGS.tsv"

for p in (summary_path, curve_path, saving_path):
    if p.exists():
        fail(f"REFUSE_OVERWRITE={p}")

with open(
    summary_path,
    "w",
    encoding="utf-8",
    newline="",
) as f:
    w = csv.DictWriter(
        f,
        fieldnames=list(summary_rows[0].keys()),
        delimiter="\t",
    )
    w.writeheader()
    w.writerows(summary_rows)

with open(
    curve_path,
    "w",
    encoding="utf-8",
    newline="",
) as f:
    w = csv.DictWriter(
        f,
        fieldnames=list(curve_rows[0].keys()),
        delimiter="\t",
    )
    w.writeheader()
    w.writerows(curve_rows)

with open(
    saving_path,
    "w",
    encoding="utf-8",
    newline="",
) as f:
    w = csv.DictWriter(
        f,
        fieldnames=list(saving_rows[0].keys()),
        delimiter="\t",
    )
    w.writeheader()
    w.writerows(saving_rows)

audit_obj = {
    "status": "PASS",
    "analysis_class":
        "RETROSPECTIVE_METRIC_DESIGN",
    "confirmatory_status": False,
    "api_calls": 0,
    "model_runs": 0,
    "physical_replay": 0,
    "d11_grid": GRID,
    "compatible_pairs": 17,
    "oracle_vef_nonloss_pairs":
        sum(
            int(r["VEF_nonloss_all_11"])
            for r in summary_rows
        ),
    "crossfit_vef_nonloss_pairs":
        cf_nonloss,
    "source_sha256":
        sha256(SOURCE),
    "freeze_sha256":
        sha256(FREEZE),
    "outputs": {
        str(summary_path): sha256(summary_path),
        str(curve_path): sha256(curve_path),
        str(saving_path): sha256(saving_path),
    },
}

audit_path = AUDIT / "VEF_V1_AUDIT.json"

if audit_path.exists():
    fail(f"REFUSE_OVERWRITE={audit_path}")

with open(audit_path, "w", encoding="utf-8") as f:
    json.dump(
        audit_obj,
        f,
        indent=2,
        sort_keys=True,
    )
    f.write("\n")

print()
print(f"SUMMARY={summary_path}")
print(f"SUMMARY_SHA256={sha256(summary_path)}")
print(f"CURVES={curve_path}")
print(f"CURVES_SHA256={sha256(curve_path)}")
print(f"SAVINGS={saving_path}")
print(f"SAVINGS_SHA256={sha256(saving_path)}")
print(f"AUDIT={audit_path}")
print(f"AUDIT_SHA256={sha256(audit_path)}")

print()
print("PASS=VEF_V1_FULL_D11_AUDIT")
print("DONE=ORACLE_AND_CROSSFIT_VEF")
print("NEXT=SCIENTIFIC_DECISION_ON_VEF_AS_MAIN_EVALUATION")
print("NEW_API_EXECUTION=NO")
print("DO_NOT_TOUCH=FROZEN_D11_PHYSICAL_RESULTS")
