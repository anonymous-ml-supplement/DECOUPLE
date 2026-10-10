#!/usr/bin/env python3

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

PROJECT = Path("__DECOUPLE_ROOT__")
ROOT = PROJECT / "10_PILOT/STEP4_V2_CLEAN_REBUILD"

BASE = (
    PROJECT
    / "10_PILOT/STEP3/04_OUTPUTS/"
      "STEP3F_POST_LABELS_AND_SINGLETON_GAINS/"
      "STEP3F_BASE_OUTCOMES.jsonl"
)

AGG = (
    ROOT
    / "04_OUTPUTS/STEP4V2_D11_FINAL_RANDOM_AWARE_ANALYSIS/"
      "D11_FINAL_TERMINAL_UTILITY.tsv"
)

LOGICAL = (
    ROOT
    / "04_OUTPUTS/STEP4V2_D11_FINAL_RANDOM_AWARE_ANALYSIS/"
      "D11_FINAL_ALL_LOGICAL_RESULTS.tsv"
)

OUT_DIR = ROOT / "04_OUTPUTS/STEP4V2_POSTD11_ZERO_ANCHOR_PROVENANCE"
AUDIT_DIR = ROOT / "06_AUDIT/STEP4V2_POSTD11_ZERO_ANCHOR_PROVENANCE"

PAIR_OUT = OUT_DIR / "ZERO_ANCHORED_VEF_CORE10.tsv"
METHOD_OUT = OUT_DIR / "ZERO_ANCHOR_METHOD_SUMMARY.tsv"
AUDIT_OUT = AUDIT_DIR / "07_ZERO_ANCHORED_VEF_INFERENCE_AUDIT.json"

BUDGETS = np.array(
    [5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
    dtype=float,
)

X_POS = BUDGETS / 100.0
X_ZERO = np.concatenate(([0.0], X_POS))

BASELINES = ["H-only", "p-only", "Random", "Step-PRM", "PRM@BoK"]
METHODS = ["DECOUPLE"] + BASELINES

BOOTSTRAP_REPS = 10000
PERMUTATION_REPS = 100000
SEED = 20260929
TOL = 1e-9

BENCH_ALIAS = {
    "BFCL": "BFCL",
    "MATH_SHEPHERD": "Math-Shepherd",
}

# Current immutable positive-budget VEF authority values.
EXPECTED_APLUS = {
    ("BFCL", "DECOUPLE"): 0.200000000,
    ("BFCL", "H-only"): 0.200000000,
    ("BFCL", "p-only"): 0.200000000,
    ("BFCL", "Random"): 0.185052632,
    ("BFCL", "Step-PRM"): 0.160000000,
    ("BFCL", "PRM@BoK"): 0.191578947,

    ("Math-Shepherd", "DECOUPLE"): 0.171578947,
    ("Math-Shepherd", "H-only"): 0.149473684,
    ("Math-Shepherd", "p-only"): 0.147368421,
    ("Math-Shepherd", "Random"): 0.123210526,
    ("Math-Shepherd", "Step-PRM"): 0.117894737,
    ("Math-Shepherd", "PRM@BoK"): 0.100000000,
}


def fail(msg):
    print(f"FAIL={msg}")
    raise SystemExit(1)


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def norm_budget(value):
    s = str(value).strip().replace("%", "")
    x = float(s)

    if 0 < x <= 1.0:
        x *= 100.0

    for b in BUDGETS:
        if abs(x - b) < 1e-8:
            return int(b)

    raise ValueError(f"Unexpected budget={value!r}")


def positive_frontier(u):
    return np.maximum.accumulate(np.asarray(u, dtype=float))


def aplus(u):
    f = positive_frontier(u)
    return float(np.trapz(f, X_POS) / (X_POS[-1] - X_POS[0]))


def azero(u0, u):
    fpos = positive_frontier(u)
    fzero = np.maximum(float(u0), fpos)
    y = np.concatenate(([float(u0)], fzero))
    return float(np.trapz(y, X_ZERO))


def holm_adjust(pvals):
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adjusted = [None] * m
    running = 0.0

    for rank, idx in enumerate(order):
        val = min(1.0, (m - rank) * pvals[idx])
        running = max(running, val)
        adjusted[idx] = running

    return adjusted


for required in (BASE, AGG, LOGICAL):
    if not required.exists():
        fail(f"MISSING_REQUIRED_AUTHORITY:{required}")


# ------------------------------------------------------------
# Load authoritative per-instance zero outcomes.
# ------------------------------------------------------------
base_rows = []

with BASE.open("r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            base_rows.append(json.loads(line))

z0 = {}

for src_bench, d11_bench in BENCH_ALIAS.items():
    rows = [
        r for r in base_rows
        if r["benchmark"] == src_bench
    ]

    if not rows:
        fail(f"NO_BASE_ROWS:{src_bench}")

    for r in rows:
        if r["base_outcome_status"] != "IDENTIFIED":
            fail(
                f"NONIDENTIFIED_Z0_IN_ADMISSIBLE_BENCHMARK:"
                f"{src_bench}:{r['instance_id']}"
            )

        if r["base_outcome_Z0"] is None:
            fail(
                f"NULL_Z0_IN_ADMISSIBLE_BENCHMARK:"
                f"{src_bench}:{r['instance_id']}"
            )

    z0[d11_bench] = {
        str(r["instance_id"]): float(r["base_outcome_Z0"])
        for r in rows
    }


# Hard ToolAlpaca non-imputation gate.
tool_rows = [
    r for r in base_rows
    if r["benchmark"] == "TOOLALPACA"
]

if len(tool_rows) != 25:
    fail(f"TOOLALPACA_BASE_ROW_COUNT={len(tool_rows)}")

if any(
    r["base_outcome_status"] != "NOT_IDENTIFIABLE_ZERO_API"
    for r in tool_rows
):
    fail("TOOLALPACA_STATUS_CHANGED")

if any(r["base_outcome_Z0"] is not None for r in tool_rows):
    fail("TOOLALPACA_Z0_IMPUTED")


# ------------------------------------------------------------
# Load final random-aware aggregate table.
# ------------------------------------------------------------
agg = {}

with AGG.open("r", encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f, delimiter="\t"):
        benchmark = row["benchmark"]
        method = row["method"]
        budget = norm_budget(row["budget"])

        agg[(benchmark, method, budget)] = float(
            row["terminal_utility"]
        )


# ------------------------------------------------------------
# Load per-instance logical results.
# Average Random replicates within instance × budget first.
# ------------------------------------------------------------
raw = defaultdict(list)

with LOGICAL.open("r", encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f, delimiter="\t"):
        benchmark = row["benchmark"]

        if benchmark not in {"BFCL", "Math-Shepherd"}:
            continue

        method = row["method"]

        if method not in METHODS:
            continue

        budget = norm_budget(row["budget"])
        iid = str(row["instance_id"])
        terminal_z = float(row["terminal_Z"])

        raw[(benchmark, method, budget, iid)].append(
            terminal_z
        )


inst_value = {
    key: float(np.mean(values))
    for key, values in raw.items()
}


# ------------------------------------------------------------
# Build aligned instance × budget matrices and validate
# against final aggregate authority.
# ------------------------------------------------------------
matrices = {}
instance_ids = {}

for benchmark in ("BFCL", "Math-Shepherd"):
    ids = sorted(z0[benchmark].keys())
    instance_ids[benchmark] = ids

    n = len(ids)

    expected_n = 25 if benchmark == "BFCL" else 50

    if n != expected_n:
        fail(f"{benchmark}_Z0_N={n}")

    for method in METHODS:
        arr = np.empty((n, len(BUDGETS)), dtype=float)

        for i, iid in enumerate(ids):
            for j, budget in enumerate(BUDGETS.astype(int)):
                key = (benchmark, method, int(budget), iid)

                if key not in inst_value:
                    fail(
                        "MISSING_LOGICAL_UNIT:"
                        f"{benchmark}:{method}:{budget}:{iid}"
                    )

                arr[i, j] = inst_value[key]

        matrices[(benchmark, method)] = arr

        # Verify per-instance reconstruction matches aggregate table.
        means = arr.mean(axis=0)

        for j, budget in enumerate(BUDGETS.astype(int)):
            key = (benchmark, method, int(budget))

            if key not in agg:
                fail(f"MISSING_AGGREGATE_UNIT:{key}")

            if abs(means[j] - agg[key]) > TOL:
                fail(
                    "AGGREGATE_RECONSTRUCTION_MISMATCH:"
                    f"{benchmark}:{method}:{budget}:"
                    f"per_instance={means[j]:.12f}:"
                    f"aggregate={agg[key]:.12f}"
                )

        # Verify positive-budget A+ reconstructs immutable authority.
        observed_aplus = aplus(means)
        expected_aplus = EXPECTED_APLUS[(benchmark, method)]

        if abs(observed_aplus - expected_aplus) > 5e-9:
            fail(
                "POSITIVE_VEF_AUTHORITY_MISMATCH:"
                f"{benchmark}:{method}:"
                f"observed={observed_aplus:.12f}:"
                f"expected={expected_aplus:.12f}"
            )


# ------------------------------------------------------------
# Method-level zero-anchor summaries + bootstrap support.
# ------------------------------------------------------------
rng_method = np.random.default_rng(SEED)

method_rows = []

for benchmark in ("BFCL", "Math-Shepherd"):
    ids = instance_ids[benchmark]
    n = len(ids)

    zvec = np.array(
        [z0[benchmark][iid] for iid in ids],
        dtype=float,
    )

    u0 = float(zvec.mean())

    for method in METHODS:
        matrix = matrices[(benchmark, method)]
        exact_means = matrix.mean(axis=0)

        pos_max = float(exact_means.max())
        benefit = pos_max - u0

        observed_a0 = azero(u0, exact_means)
        observed_ap = aplus(exact_means)

        boot_benefit = np.empty(BOOTSTRAP_REPS, dtype=float)
        boot_a0 = np.empty(BOOTSTRAP_REPS, dtype=float)

        for r in range(BOOTSTRAP_REPS):
            idx = rng_method.integers(0, n, size=n)

            u0_r = float(zvec[idx].mean())
            u_r = matrix[idx, :].mean(axis=0)

            boot_benefit[r] = float(u_r.max() - u0_r)
            boot_a0[r] = azero(u0_r, u_r)

        benefit_lo, benefit_hi = np.quantile(
            boot_benefit,
            [0.025, 0.975],
        )

        a0_lo, a0_hi = np.quantile(
            boot_a0,
            [0.025, 0.975],
        )

        if benefit > TOL:
            benefit_direction = "POSITIVE"
        elif benefit < -TOL:
            benefit_direction = "NEGATIVE"
        else:
            benefit_direction = "TIE"

        method_rows.append({
            "benchmark": benchmark,
            "method": method,
            "joint_panel_n": n,
            "U0": u0,
            "positive_budget_max_exact_utility": pos_max,
            "max_verified_minus_U0": benefit,
            "max_verified_minus_U0_boot_ci95_low":
                float(benefit_lo),
            "max_verified_minus_U0_boot_ci95_high":
                float(benefit_hi),
            "no_verification_benefit_direction":
                benefit_direction,
            "positive_VEF_AUBC_5_100": observed_ap,
            "zero_anchored_VEF_AUBC_0_100": observed_a0,
            "zero_anchored_AUBC_boot_ci95_low":
                float(a0_lo),
            "zero_anchored_AUBC_boot_ci95_high":
                float(a0_hi),
        })


# ------------------------------------------------------------
# Core pair zero-anchored paired inference.
# Bootstrap same instance multiset.
# Permutation swaps complete 11-budget vectors within instance.
# Zero anchor stays common and allocator-independent.
# ------------------------------------------------------------
pair_rows = []

for benchmark in ("BFCL", "Math-Shepherd"):
    ids = instance_ids[benchmark]
    n = len(ids)

    zvec = np.array(
        [z0[benchmark][iid] for iid in ids],
        dtype=float,
    )

    de = matrices[(benchmark, "DECOUPLE")]

    raw_p_two = []
    benchmark_pair_rows = []

    for pair_index, baseline in enumerate(BASELINES):
        bl = matrices[(benchmark, baseline)]

        u0 = float(zvec.mean())
        de_obs = azero(u0, de.mean(axis=0))
        bl_obs = azero(u0, bl.mean(axis=0))
        delta_obs = de_obs - bl_obs

        # Pair-specific deterministic RNG stream.
        rng_boot = np.random.default_rng(
            SEED + 1000 * (
                1 if benchmark == "BFCL" else 2
            ) + pair_index
        )

        boot_delta = np.empty(
            BOOTSTRAP_REPS,
            dtype=float,
        )

        for r in range(BOOTSTRAP_REPS):
            idx = rng_boot.integers(0, n, size=n)

            u0_r = float(zvec[idx].mean())

            de_r = de[idx, :].mean(axis=0)
            bl_r = bl[idx, :].mean(axis=0)

            boot_delta[r] = (
                azero(u0_r, de_r)
                - azero(u0_r, bl_r)
            )

        ci_low, ci_high = np.quantile(
            boot_delta,
            [0.025, 0.975],
        )

        # Whole-vector paired sign-flip / exchange.
        rng_perm = np.random.default_rng(
            SEED + 100000 * (
                1 if benchmark == "BFCL" else 2
            ) + pair_index
        )

        midpoint = (de + bl) / 2.0
        halfdiff = (de - bl) / 2.0

        extreme_two = 0
        ge_obs = 0
        done = 0
        chunk = 2000

        while done < PERMUTATION_REPS:
            k = min(chunk, PERMUTATION_REPS - done)

            signs = rng_perm.choice(
                np.array([-1.0, 1.0]),
                size=(k, n),
            )

            # k × 11 budget means.
            signed = (
                signs[:, :, None]
                * halfdiff[None, :, :]
            ).mean(axis=1)

            midmean = midpoint.mean(axis=0)[None, :]

            de_perm_u = midmean + signed
            bl_perm_u = midmean - signed

            # Common U0 is unchanged by allocator exchange.
            u0_perm = u0

            de_front = np.maximum.accumulate(
                de_perm_u,
                axis=1,
            )
            bl_front = np.maximum.accumulate(
                bl_perm_u,
                axis=1,
            )

            de_front = np.maximum(
                de_front,
                u0_perm,
            )
            bl_front = np.maximum(
                bl_front,
                u0_perm,
            )

            de_y = np.concatenate(
                [
                    np.full((k, 1), u0_perm),
                    de_front,
                ],
                axis=1,
            )

            bl_y = np.concatenate(
                [
                    np.full((k, 1), u0_perm),
                    bl_front,
                ],
                axis=1,
            )

            de_a = np.trapz(
                de_y,
                X_ZERO,
                axis=1,
            )

            bl_a = np.trapz(
                bl_y,
                X_ZERO,
                axis=1,
            )

            perm_delta = de_a - bl_a

            extreme_two += int(
                np.sum(
                    np.abs(perm_delta)
                    >= abs(delta_obs) - 1e-15
                )
            )

            ge_obs += int(
                np.sum(
                    perm_delta
                    >= delta_obs - 1e-15
                )
            )

            done += k

        p_two = (
            extreme_two + 1
        ) / (
            PERMUTATION_REPS + 1
        )

        # Directional one-sided probability under exchange null.
        p_one = (
            int(np.sum([])) + 0
        )

        # Explicit one-sided test for DE > baseline:
        # null distribution tail at observed positive delta.
        # Re-run is unnecessary; symmetry gives:
        if delta_obs > 0:
            p_one_value = min(1.0, p_two / 2.0)
        elif delta_obs < 0:
            p_one_value = 1.0 - min(1.0, p_two / 2.0)
        else:
            p_one_value = 1.0

        raw_p_two.append(float(p_two))

        if delta_obs > TOL:
            direction = "POSITIVE"
        elif delta_obs < -TOL:
            direction = "NEGATIVE"
        else:
            direction = "TIE"

        benchmark_pair_rows.append({
            "benchmark": benchmark,
            "baseline": baseline,
            "joint_panel_n": n,
            "DE_zero_VEF_AUBC_0_100": de_obs,
            "baseline_zero_VEF_AUBC_0_100": bl_obs,
            "observed_delta": delta_obs,
            "direction": direction,
            "bootstrap_ci95_low": float(ci_low),
            "bootstrap_ci95_high": float(ci_high),
            "permutation_p_one_sided":
                float(p_one_value),
            "permutation_p_two_sided":
                float(p_two),
            "bootstrap_replicates":
                BOOTSTRAP_REPS,
            "permutation_replicates":
                PERMUTATION_REPS,
            "seed_base":
                SEED,
        })

        print(
            "PAIR_DONE="
            f"{benchmark}|{baseline}|"
            f"DELTA={delta_obs:.9f}|"
            f"P2={p_two:.9f}"
        )

    holm_two = holm_adjust(raw_p_two)

    for row, p_adj in zip(
        benchmark_pair_rows,
        holm_two,
    ):
        row["holm5_p_two_sided"] = float(p_adj)
        pair_rows.append(row)


# ------------------------------------------------------------
# Persist.
# ------------------------------------------------------------
method_fields = [
    "benchmark",
    "method",
    "joint_panel_n",
    "U0",
    "positive_budget_max_exact_utility",
    "max_verified_minus_U0",
    "max_verified_minus_U0_boot_ci95_low",
    "max_verified_minus_U0_boot_ci95_high",
    "no_verification_benefit_direction",
    "positive_VEF_AUBC_5_100",
    "zero_anchored_VEF_AUBC_0_100",
    "zero_anchored_AUBC_boot_ci95_low",
    "zero_anchored_AUBC_boot_ci95_high",
]

with METHOD_OUT.open(
    "w",
    encoding="utf-8",
    newline="",
) as f:
    writer = csv.DictWriter(
        f,
        fieldnames=method_fields,
        delimiter="\t",
    )
    writer.writeheader()

    for row in method_rows:
        writer.writerow(row)


pair_fields = [
    "benchmark",
    "baseline",
    "joint_panel_n",
    "DE_zero_VEF_AUBC_0_100",
    "baseline_zero_VEF_AUBC_0_100",
    "observed_delta",
    "direction",
    "bootstrap_ci95_low",
    "bootstrap_ci95_high",
    "permutation_p_one_sided",
    "permutation_p_two_sided",
    "holm5_p_two_sided",
    "bootstrap_replicates",
    "permutation_replicates",
    "seed_base",
]

with PAIR_OUT.open(
    "w",
    encoding="utf-8",
    newline="",
) as f:
    writer = csv.DictWriter(
        f,
        fieldnames=pair_fields,
        delimiter="\t",
    )
    writer.writeheader()

    for row in pair_rows:
        writer.writerow(row)


audit = {
    "audit":
        "ZERO_ANCHORED_VEF_AND_NO_VERIFICATION_BENEFIT",
    "authority_scope":
        "Spec5.5.5_ChecklistV27",
    "api_calls": 0,
    "new_model_execution": 0,
    "toolalpaca_z0_imputed": False,
    "benchmarks_zero_anchor_analyzed": [
        "BFCL",
        "Math-Shepherd",
    ],
    "toolalpaca_status":
        "NOT_IDENTIFIABLE_UNDER_FROZEN_ZERO_API_AUTHORITY",
    "budgets_positive": [
        int(x) for x in BUDGETS
    ],
    "bootstrap_replicates":
        BOOTSTRAP_REPS,
    "permutation_replicates":
        PERMUTATION_REPS,
    "seed_base":
        SEED,
    "source_hashes": {
        "STEP3F_BASE_OUTCOMES":
            sha256_file(BASE),
        "D11_FINAL_TERMINAL_UTILITY":
            sha256_file(AGG),
        "D11_FINAL_ALL_LOGICAL_RESULTS":
            sha256_file(LOGICAL),
    },
    "positive_VEF_authority_reconstruction":
        "PASS",
    "random_replicates":
        "AVERAGED_WITHIN_INSTANCE_AND_BUDGET_BEFORE_INFERENCE",
    "permutation_unit":
        "WHOLE_11_BUDGET_METHOD_VECTOR_WITHIN_ORIGINAL_INSTANCE",
    "zero_anchor_permutation_behavior":
        "COMMON_ALLOCATOR_INDEPENDENT_Z0_NOT_SWAPPED",
    "outputs": {
        "method_summary":
            str(METHOD_OUT),
        "core10_pair_inference":
            str(PAIR_OUT),
    },
    "next":
        "GRID_STABILITY_STRESS_TEST",
}

AUDIT_OUT.write_text(
    json.dumps(
        audit,
        indent=2,
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)


print()
print("PASS=ZERO_ANCHORED_VEF_INFERENCE_COMPLETE")
print("PASS=POSITIVE_VEF_AUTHORITY_RECONSTRUCTED")
print("PASS=PER_INSTANCE_Z0_RESAMPLING_USED")
print("PASS=WHOLE_VECTOR_PERMUTATION_USED")
print("PASS=RANDOM_REPLICATES_COLLAPSED_WITHIN_INSTANCE")
print("TOOLALPACA_Z0_IMPUTED=NO")
print(f"METHOD_OUT={METHOD_OUT}")
print(f"PAIR_OUT={PAIR_OUT}")
print(f"AUDIT_OUT={AUDIT_OUT}")
print("DONE=ZERO_ANCHORED_VEF_AND_NO_VERIFICATION_BENEFIT")
print("NEXT=GRID_STABILITY_STRESS_TEST")
print("DO_NOT_TOUCH=H1_H2_H3_H4_H5_H6_D11_PHYSICAL_RESULTS")
