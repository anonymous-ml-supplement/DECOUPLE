#!/usr/bin/env python3

from pathlib import Path
from collections import defaultdict, Counter
import csv
import json
import math
import hashlib
import statistics
import random

ROOT = Path("__DECOUPLE_ROOT__")
STEP4 = ROOT / "10_PILOT/STEP4_V2_CLEAN_REBUILD"

GAIN = (
    ROOT
    / "10_PILOT/STEP3/04_OUTPUTS/STEP3F_POST_LABELS_AND_SINGLETON_GAINS/"
      "STEP3F_PRACTICAL_SINGLETON_GAINS.jsonl"
)

STATIC_SCORES = (
    STEP4
    / "04_OUTPUTS/STEP4V2_04D_FULL_20PT_SELECTION_MATERIALIZATION/"
      "STEP2A/static_baseline_scores.jsonl"
)

STATIC_SEL = (
    STEP4
    / "04_OUTPUTS/STEP4V2_04D_FULL_20PT_SELECTION_MATERIALIZATION/"
      "STEP2A/exact_budget_selections.jsonl"
)

PRM_SCORES = (
    STEP4
    / "04_OUTPUTS/STEP4V2_04D_FULL_20PT_SELECTION_MATERIALIZATION/"
      "STEP_PRM/step_prm_631_scores.jsonl"
)

PRM_SEL = (
    STEP4
    / "04_OUTPUTS/STEP4V2_04D_FULL_20PT_SELECTION_MATERIALIZATION/"
      "STEP_PRM/step_prm_exact_b_selections.jsonl"
)

OUT = (
    STEP4
    / "04_OUTPUTS/STEP4V2_POSTD11_REALIZED_DISPLACEMENT_REGRET"
)
AUDIT = (
    STEP4
    / "06_AUDIT/STEP4V2_POSTD11_REALIZED_DISPLACEMENT_REGRET"
)

OUT.mkdir(parents=True, exist_ok=True)
AUDIT.mkdir(parents=True, exist_ok=True)

BUDGETS = [0.05, 0.10, 0.15, 0.20, 0.25]
IDENTIFIABLE_BENCHMARKS = {"BFCL", "MATH_SHEPHERD"}
MASTER_SEED = 20260829
BOOTSTRAP_REPLICATES = 10000


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_benchmark(x):
    if x == "Math-Shepherd":
        return "MATH_SHEPHERD"
    return x


def rankdata(vals):
    """
    Average ranks for ties, 1-based.
    """
    n = len(vals)
    order = sorted(range(n), key=lambda i: vals[i])
    ranks = [0.0] * n

    i = 0
    while i < n:
        j = i + 1
        while j < n and vals[order[j]] == vals[order[i]]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[order[k]] = avg_rank
        i = j

    return ranks


def pearson(x, y):
    n = len(x)
    if n < 2:
        return None

    mx = sum(x) / n
    my = sum(y) / n

    dx = [v - mx for v in x]
    dy = [v - my for v in y]

    sx = sum(v * v for v in dx)
    sy = sum(v * v for v in dy)

    if sx == 0 or sy == 0:
        return None

    return sum(a * b for a, b in zip(dx, dy)) / math.sqrt(sx * sy)


def spearman(x, y):
    if len(x) != len(y) or len(x) < 2:
        return None
    return pearson(rankdata(x), rankdata(y))


def deterministic_uniform_steps(all_steps, B):
    """
    Retrospective structural baseline.
    Choose B unique step positions nearest equally spaced midpoint quantiles.

    Targets in 0-based positional space:
        (j + 0.5) * T / B - 0.5

    Ties resolved toward earlier step position.

    This rule is frozen here before inspecting resulting utilities.
    """
    steps = sorted(all_steps)
    T = len(steps)

    if B >= T:
        return steps[:]

    targets = [((j + 0.5) * T / B) - 0.5 for j in range(B)]

    chosen_positions = []
    available = set(range(T))

    for target in targets:
        pos = min(
            available,
            key=lambda k: (abs(k - target), k)
        )
        chosen_positions.append(pos)
        available.remove(pos)

    return sorted(steps[k] for k in chosen_positions)


print("=== SOURCE HASHES ===")
for p in [GAIN, STATIC_SCORES, STATIC_SEL, PRM_SCORES, PRM_SEL]:
    assert p.exists(), p
    print(f"{p}  {sha256(p)}")


# ============================================================
# 1. Load realized singleton gains
# ============================================================

gain_rows = []
gain_by_inst = defaultdict(dict)

with GAIN.open() as f:
    for line in f:
        r = json.loads(line)
        b = norm_benchmark(r["benchmark"])
        iid = r["instance_id"]
        t = int(r["step_index"])

        gain_rows.append(r)

        if b not in IDENTIFIABLE_BENCHMARKS:
            continue

        assert r["singleton_gain_status"] == "IDENTIFIED", r
        assert bool(r["exact_restoration_certified"]) is True, r
        assert r["singleton_empirical_gain"] is not None, r

        gain_by_inst[(b, iid)][t] = float(r["singleton_empirical_gain"])


print()
print("=== REALIZED GAIN COVERAGE ===")
for b in sorted(IDENTIFIABLE_BENCHMARKS):
    insts = [k for k in gain_by_inst if k[0] == b]
    nsteps = sum(len(gain_by_inst[k]) for k in insts)
    print(f"{b}: INSTANCES={len(insts)} STEPS={nsteps}")


# ============================================================
# 2. Load frozen DECOUPLE decision-time scores
# ============================================================

decouple_score = {}

with STATIC_SCORES.open() as f:
    for line in f:
        r = json.loads(line)
        if r["method"] != "DECOUPLE":
            continue

        b = norm_benchmark(r["benchmark"])
        if b not in IDENTIFIABLE_BENCHMARKS:
            continue

        key = (b, r["instance_id"], int(r["step_index"]))
        assert r["posthoc_access"] is False
        decouple_score[key] = float(r["score"])


# ============================================================
# 3. Load frozen DECOUPLE exact-budget selected sets
# ============================================================

decouple_sel = defaultdict(list)

with STATIC_SEL.open() as f:
    for line in f:
        r = json.loads(line)

        if r["method"] != "DECOUPLE":
            continue

        b = norm_benchmark(r["benchmark"])
        budget = float(r["budget_fraction"])

        if b not in IDENTIFIABLE_BENCHMARKS:
            continue
        if budget not in BUDGETS:
            continue

        assert r["posthoc_access"] is False

        key = (b, r["instance_id"], budget)
        decouple_sel[key].append(
            (
                int(r["selection_rank"]),
                int(r["step_index"])
            )
        )

decouple_sel = {
    k: [t for _, t in sorted(v)]
    for k, v in decouple_sel.items()
}


# ============================================================
# 4. Load frozen Step-PRM exact-budget selected sets
# ============================================================

prm_sel = defaultdict(list)

with PRM_SEL.open() as f:
    for line in f:
        r = json.loads(line)

        b = norm_benchmark(r["benchmark"])
        budget = float(r["budget_fraction"])

        if b not in IDENTIFIABLE_BENCHMARKS:
            continue
        if budget not in BUDGETS:
            continue

        assert r["baseline"] == "Step-PRM"
        assert r["posthoc_access"] is False

        key = (b, r["instance_id"], budget)
        prm_sel[key].append(
            (
                int(r["selection_rank"]),
                int(r["step_index"])
            )
        )

prm_sel = {
    k: [t for _, t in sorted(v)]
    for k, v in prm_sel.items()
}


# ============================================================
# 5. Verify lowest correctness == highest risk
# ============================================================

prm_score_rows = defaultdict(list)

with PRM_SCORES.open() as f:
    for line in f:
        r = json.loads(line)

        b = norm_benchmark(r["benchmark"])
        if b not in IDENTIFIABLE_BENCHMARKS:
            continue

        assert r["posthoc_access"] is False

        prm_score_rows[(b, r["instance_id"])].append(r)

order_mismatches = []

for key, rows in prm_score_rows.items():

    low_correct = sorted(
        rows,
        key=lambda r: (
            float(r["correctness_score"]),
            r["tie_key"]
        )
    )

    high_risk = sorted(
        rows,
        key=lambda r: (
            -float(r["risk_score"]),
            r["tie_key"]
        )
    )

    a = [int(r["step_index"]) for r in low_correct]
    b = [int(r["step_index"]) for r in high_risk]

    if a != b:
        order_mismatches.append(key)

assert not order_mismatches, order_mismatches


# ============================================================
# 6. Instance-level realized displacement regret
# ============================================================

instance_rows = []

for (bench, iid), gains in sorted(gain_by_inst.items()):

    all_steps = sorted(gains)
    T = len(all_steps)

    for budget in BUDGETS:

        ek = (bench, iid, budget)

        assert ek in decouple_sel, ("MISSING_DECOUPLE_SELECTION", ek)
        assert ek in prm_sel, ("MISSING_PRM_SELECTION", ek)

        de_steps = decouple_sel[ek]
        lr_steps = prm_sel[ek]

        B = len(de_steps)

        assert len(lr_steps) == B, (
            "BUDGET_MISMATCH",
            ek,
            len(de_steps),
            len(lr_steps),
        )

        assert set(de_steps).issubset(gains), ("DECOUPLE_STEP_MISSING_GAIN", ek)
        assert set(lr_steps).issubset(gains), ("PRM_STEP_MISSING_GAIN", ek)

        # Post-hoc oracle:
        # higher singleton empirical gain first,
        # deterministic lower step index tie break
        oracle_steps = [
            t for t, _ in sorted(
                gains.items(),
                key=lambda kv: (-kv[1], kv[0])
            )[:B]
        ]

        earliest_steps = all_steps[:B]
        latest_steps = all_steps[-B:]
        uniform_steps = deterministic_uniform_steps(all_steps, B)

        selectors = {
            "DECOUPLE": de_steps,
            "LOCAL_RISK_STEP_PRM": lr_steps,
            "LOWEST_PRM_SCORE": lr_steps,
            "EARLIEST_STEP": earliest_steps,
            "LATEST_STEP": latest_steps,
            "UNIFORM_SPACING": uniform_steps,
        }

        oracle_F = sum(gains[t] for t in oracle_steps)

        for method, selected in selectors.items():
            selected_F = sum(gains[t] for t in selected)
            regret = oracle_F - selected_F

            # numerical tolerance only
            if regret < -1e-12:
                raise AssertionError(
                    ("NEGATIVE_DISPLACEMENT_REGRET", bench, iid, budget,
                     method, oracle_F, selected_F, regret)
                )

            if abs(regret) < 1e-12:
                regret = 0.0

            instance_rows.append({
                "benchmark": bench,
                "instance_id": iid,
                "budget": budget,
                "T": T,
                "B": B,
                "method": method,
                "oracle_steps": json.dumps(oracle_steps),
                "selected_steps": json.dumps(selected),
                "oracle_F": oracle_F,
                "selected_F": selected_F,
                "displacement_regret": regret,
            })


# ============================================================
# 7. Aggregate point metrics
# ============================================================

groups = defaultdict(list)

for r in instance_rows:
    groups[(r["benchmark"], r["method"], r["budget"])].append(r)

point_rows = []

for (bench, method, budget), rows in sorted(groups.items()):

    vals = [r["displacement_regret"] for r in rows]
    oracle_vals = [r["oracle_F"] for r in rows]
    selected_vals = [r["selected_F"] for r in rows]

    point_rows.append({
        "benchmark": bench,
        "method": method,
        "budget": budget,
        "instance_n": len(rows),
        "mean_oracle_F": sum(oracle_vals) / len(rows),
        "mean_selected_F": sum(selected_vals) / len(rows),
        "mean_displacement_regret": sum(vals) / len(vals),
        "median_displacement_regret": statistics.median(vals),
        "zero_regret_instances": sum(v == 0 for v in vals),
        "positive_regret_instances": sum(v > 0 for v in vals),
    })


# ============================================================
# 8. Cluster bootstrap by original instance
# ============================================================

rng = random.Random(MASTER_SEED)

bootstrap_rows = []

for bench in sorted(IDENTIFIABLE_BENCHMARKS):

    instance_ids = sorted({
        r["instance_id"]
        for r in instance_rows
        if r["benchmark"] == bench
    })

    n = len(instance_ids)

    by_lookup = defaultdict(dict)
    for r in instance_rows:
        if r["benchmark"] != bench:
            continue
        by_lookup[(r["method"], r["budget"])][r["instance_id"]] = \
            r["displacement_regret"]

    keys = sorted(by_lookup)

    reps = {k: [] for k in keys}

    for rep in range(BOOTSTRAP_REPLICATES):
        sampled = [
            instance_ids[rng.randrange(n)]
            for _ in range(n)
        ]

        for k in keys:
            vals = [by_lookup[k][iid] for iid in sampled]
            reps[k].append(sum(vals) / len(vals))

    for (method, budget), vals in sorted(reps.items()):
        s = sorted(vals)

        lo = s[int(0.025 * (len(s) - 1))]
        hi = s[int(0.975 * (len(s) - 1))]

        observed = next(
            r["mean_displacement_regret"]
            for r in point_rows
            if r["benchmark"] == bench
            and r["method"] == method
            and r["budget"] == budget
        )

        bootstrap_rows.append({
            "benchmark": bench,
            "method": method,
            "budget": budget,
            "cluster_n": n,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "mean_displacement_regret": observed,
            "ci95_low": lo,
            "ci95_high": hi,
        })


# ============================================================
# 9. Spearman: frozen DECOUPLE score vs realized gain
#    pooled step-level within benchmark
# ============================================================

corr_rows = []

for bench in sorted(IDENTIFIABLE_BENCHMARKS):

    xs = []
    ys = []
    cluster_rows = defaultdict(list)

    for (b, iid), gains in gain_by_inst.items():
        if b != bench:
            continue

        for t, gain in gains.items():
            key = (b, iid, t)
            assert key in decouple_score, ("MISSING_DECOUPLE_SCORE", key)

            score = decouple_score[key]
            xs.append(score)
            ys.append(gain)
            cluster_rows[iid].append((score, gain))

    rho = spearman(xs, ys)

    # cluster bootstrap correlation:
    # resample original instances, then pool their steps
    instance_ids = sorted(cluster_rows)
    n = len(instance_ids)

    rng_corr = random.Random(MASTER_SEED + 17)
    rho_reps = []

    for _ in range(BOOTSTRAP_REPLICATES):

        sampled = [
            instance_ids[rng_corr.randrange(n)]
            for _ in range(n)
        ]

        bx = []
        by = []

        for iid in sampled:
            for score, gain in cluster_rows[iid]:
                bx.append(score)
                by.append(gain)

        rr = spearman(bx, by)

        if rr is not None and math.isfinite(rr):
            rho_reps.append(rr)

    if rho_reps:
        s = sorted(rho_reps)
        lo = s[int(0.025 * (len(s) - 1))]
        hi = s[int(0.975 * (len(s) - 1))]
    else:
        lo = None
        hi = None

    corr_rows.append({
        "benchmark": bench,
        "step_n": len(xs),
        "instance_n": n,
        "spearman_rho": rho,
        "cluster_bootstrap_replicates_valid": len(rho_reps),
        "ci95_low": lo,
        "ci95_high": hi,
        "aggregation": "POOLED_STEP_LEVEL_WITHIN_BENCHMARK",
        "bootstrap_unit": "ORIGINAL_BENCHMARK_INSTANCE",
    })

# ToolAlpaca explicit unavailable row
corr_rows.append({
    "benchmark": "TOOLALPACA",
    "step_n": 60,
    "instance_n": 25,
    "spearman_rho": "",
    "cluster_bootstrap_replicates_valid": 0,
    "ci95_low": "",
    "ci95_high": "",
    "aggregation": "NOT_IDENTIFIABLE_SINGLETON_GAIN",
    "bootstrap_unit": "ORIGINAL_BENCHMARK_INSTANCE",
})


# ============================================================
# 10. Write outputs
# ============================================================

def write_tsv(path, rows, fields):
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        w.writeheader()
        w.writerows(rows)


instance_path = OUT / "REALIZED_DISPLACEMENT_INSTANCE_LEVEL.tsv"
point_path = OUT / "REALIZED_DISPLACEMENT_POINT_METRICS.tsv"
boot_path = OUT / "REALIZED_DISPLACEMENT_BOOTSTRAP.tsv"
corr_path = OUT / "DECOUPLE_SCORE_REALIZED_GAIN_SPEARMAN.tsv"
summary_path = OUT / "REALIZED_DISPLACEMENT_MANUSCRIPT_SUMMARY.tsv"

write_tsv(
    instance_path,
    instance_rows,
    [
        "benchmark",
        "instance_id",
        "budget",
        "T",
        "B",
        "method",
        "oracle_steps",
        "selected_steps",
        "oracle_F",
        "selected_F",
        "displacement_regret",
    ],
)

write_tsv(
    point_path,
    point_rows,
    [
        "benchmark",
        "method",
        "budget",
        "instance_n",
        "mean_oracle_F",
        "mean_selected_F",
        "mean_displacement_regret",
        "median_displacement_regret",
        "zero_regret_instances",
        "positive_regret_instances",
    ],
)

write_tsv(
    boot_path,
    bootstrap_rows,
    [
        "benchmark",
        "method",
        "budget",
        "cluster_n",
        "bootstrap_replicates",
        "mean_displacement_regret",
        "ci95_low",
        "ci95_high",
    ],
)

write_tsv(
    corr_path,
    corr_rows,
    [
        "benchmark",
        "step_n",
        "instance_n",
        "spearman_rho",
        "cluster_bootstrap_replicates_valid",
        "ci95_low",
        "ci95_high",
        "aggregation",
        "bootstrap_unit",
    ],
)


# manuscript summary:
# compare average regret over the five tight budgets
summary = []

for bench in sorted(IDENTIFIABLE_BENCHMARKS):
    for method in (
        "DECOUPLE",
        "LOCAL_RISK_STEP_PRM",
        "EARLIEST_STEP",
        "LATEST_STEP",
        "UNIFORM_SPACING",
        "LOWEST_PRM_SCORE",
    ):
        rows = [
            r for r in point_rows
            if r["benchmark"] == bench
            and r["method"] == method
        ]

        assert len(rows) == len(BUDGETS)

        summary.append({
            "benchmark": bench,
            "method": method,
            "mean_Rdisp_over_5_10_15_20_25": (
                sum(r["mean_displacement_regret"] for r in rows)
                / len(rows)
            ),
            "min_Rdisp": min(
                r["mean_displacement_regret"] for r in rows
            ),
            "max_Rdisp": max(
                r["mean_displacement_regret"] for r in rows
            ),
        })

summary.append({
    "benchmark": "TOOLALPACA",
    "method": "ALL",
    "mean_Rdisp_over_5_10_15_20_25": "",
    "min_Rdisp": "",
    "max_Rdisp": "",
})

write_tsv(
    summary_path,
    summary,
    [
        "benchmark",
        "method",
        "mean_Rdisp_over_5_10_15_20_25",
        "min_Rdisp",
        "max_Rdisp",
    ],
)


# ============================================================
# 11. Hard checks
# ============================================================

# lowest PRM must equal local risk exactly
for bench in IDENTIFIABLE_BENCHMARKS:
    for budget in BUDGETS:

        a = next(
            r["mean_displacement_regret"]
            for r in point_rows
            if r["benchmark"] == bench
            and r["method"] == "LOCAL_RISK_STEP_PRM"
            and r["budget"] == budget
        )

        b = next(
            r["mean_displacement_regret"]
            for r in point_rows
            if r["benchmark"] == bench
            and r["method"] == "LOWEST_PRM_SCORE"
            and r["budget"] == budget
        )

        assert abs(a - b) < 1e-12


print()
print("=== MANUSCRIPT SUMMARY ===")
for r in summary:
    print(
        f"{r['benchmark']}\t"
        f"{r['method']}\t"
        f"{r['mean_Rdisp_over_5_10_15_20_25']}\t"
        f"{r['min_Rdisp']}\t"
        f"{r['max_Rdisp']}"
    )

print()
print("=== SCORE vs REALIZED GAIN SPEARMAN ===")
for r in corr_rows:
    print(
        f"{r['benchmark']}\t"
        f"rho={r['spearman_rho']}\t"
        f"CI=[{r['ci95_low']},{r['ci95_high']}]\t"
        f"steps={r['step_n']}\t"
        f"instances={r['instance_n']}"
    )

print()
print("PASS=FROZEN_SINGLETON_GAIN_AUTHORITY_USED")
print("PASS=FROZEN_DECOUPLE_SELECTIONS_REUSED")
print("PASS=FROZEN_STEP_PRM_SELECTIONS_REUSED")
print("PASS=LOWEST_PRM_IDENTICAL_TO_STEP_PRM")
print("PASS=NO_STEP_LEVEL_BOOTSTRAP")
print("PASS=BFCL_AND_MATH_REALIZED_GAIN_IDENTIFIED")
print("PASS=TOOLALPACA_MARKED_NOT_IDENTIFIABLE")
print("DONE=REALIZED_DISPLACEMENT_REGRET_ANALYSIS")

print()
print(f"INSTANCE_TABLE={instance_path}")
print(f"POINT_TABLE={point_path}")
print(f"BOOTSTRAP_TABLE={boot_path}")
print(f"CORRELATION_TABLE={corr_path}")
print(f"SUMMARY_TABLE={summary_path}")
