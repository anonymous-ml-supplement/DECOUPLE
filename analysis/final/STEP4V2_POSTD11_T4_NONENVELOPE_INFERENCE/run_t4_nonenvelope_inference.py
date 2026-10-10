#!/usr/bin/env python3

import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path("__DECOUPLE_ROOT__")
BASE = ROOT / "10_PILOT/STEP4_V2_CLEAN_REBUILD"

INPUT = (
    BASE
    / "04_OUTPUTS/STEP4V2_D11_FINAL_RANDOM_AWARE_ANALYSIS"
    / "D11_FINAL_ALL_LOGICAL_RESULTS.tsv"
)

OUTDIR = (
    BASE
    / "04_OUTPUTS/STEP4V2_POSTD11_T4_NONENVELOPE_INFERENCE"
)

AUDITDIR = (
    BASE
    / "06_AUDIT/STEP4V2_POSTD11_T4_NONENVELOPE_INFERENCE"
)

EXPECTED_INPUT_SHA256 = (
    "32d160166c3546f62b579f30e2e007e6213fb64596fca9b9ecb52f3b1bb83c53"
)

D11 = [
    0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
    0.60, 0.70, 0.80, 0.90, 1.00,
]

LOW = [0.05, 0.10, 0.20]

BENCHMARKS = [
    "BFCL",
    "Math-Shepherd",
    "ToolAlpaca",
]

BASELINES = [
    "H-only",
    "p-only",
    "Random",
    "Step-PRM",
    "PRM@BoK",
]

CORE_METHODS = [
    "DECOUPLE",
    *BASELINES,
]

EXPECTED_N = {
    "BFCL": 25,
    "Math-Shepherd": 50,
    "ToolAlpaca": 25,
}

BOOTSTRAP_REPLICATES = 10000
PERMUTATION_REPLICATES = 10000
BOOTSTRAP_SEED = 20260829
PERMUTATION_SEED = 20260830

EXPECTED_POINT_ESTIMATES = {
    ("BFCL", "DECOUPLE"): ("0.135", "0.200"),
    ("BFCL", "H-only"): ("0.143", "0.200"),
    ("BFCL", "p-only"): ("0.135", "0.187"),
    ("BFCL", "Random"): ("0.144", "0.173"),
    ("BFCL", "Step-PRM"): ("0.122", "0.160"),
    ("BFCL", "PRM@BoK"): ("0.156", "0.160"),

    ("Math-Shepherd", "DECOUPLE"): ("0.109", "0.147"),
    ("Math-Shepherd", "H-only"): ("0.105", "0.113"),
    ("Math-Shepherd", "p-only"): ("0.091", "0.107"),
    ("Math-Shepherd", "Random"): ("0.100", "0.102"),
    ("Math-Shepherd", "Step-PRM"): ("0.088", "0.107"),
    ("Math-Shepherd", "PRM@BoK"): ("0.080", "0.100"),

    ("ToolAlpaca", "DECOUPLE"): ("0.465", "0.520"),
    ("ToolAlpaca", "H-only"): ("0.465", "0.520"),
    ("ToolAlpaca", "p-only"): ("0.465", "0.520"),
    ("ToolAlpaca", "Random"): ("0.450", "0.448"),
    ("ToolAlpaca", "Step-PRM"): ("0.482", "0.520"),
    ("ToolAlpaca", "PRM@BoK"): ("0.469", "0.480"),
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_tsv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def write_tsv(path, rows, fieldnames):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        w.writeheader()
        w.writerows(rows)


# Frozen helper implementation.
def percentile(xs, q):
    xs = sorted(xs)

    if not xs:
        raise RuntimeError("EMPTY_PERCENTILE_INPUT")

    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo

    return (
        xs[lo] * (1.0 - frac)
        + xs[hi] * frac
    )


# Frozen helper implementation.
def trapz_normalized(xs, ys):
    area = 0.0

    for i in range(1, len(xs)):
        dx = xs[i] - xs[i - 1]
        area += (
            dx
            * (ys[i - 1] + ys[i])
            / 2.0
        )

    return area / (xs[-1] - xs[0])


# Frozen helper implementation.
def holm_adjust(pvals):
    ordered = sorted(pvals, key=lambda x: x[1])
    m = len(ordered)

    adjusted = {}
    running = 0.0

    for i, (label, p) in enumerate(ordered):
        rank_mult = m - i
        val = min(1.0, p * rank_mult)
        running = max(running, val)
        adjusted[label] = min(1.0, running)

    return adjusted


def summary_from_budget_values(values, summary):
    if summary == "Area":
        ys = [values[b] for b in D11]
        return trapz_normalized(D11, ys)

    if summary == "Low":
        return sum(values[b] for b in LOW) / len(LOW)

    raise RuntimeError("UNKNOWN_SUMMARY=" + summary)


print("============================================================")
print("T4 NON-ENVELOPE INFERENCE")
print("============================================================")
print("CURRENT=DERIVED_STATISTICAL_CLOSURE")
print("NEW_API_CALLS=NO")
print("NEW_MODEL_EXECUTION=NO")
print("NEW_PHYSICAL_EXECUTION=NO")
print("SOURCE_MUTATION=NO")
print("PAIRING_CLUSTER=ORIGINAL_BENCHMARK_INSTANCE")
print("RANDOM_COLLAPSE=INSTANCE_BUDGET_MEAN_OF_10_FROZEN_REPLICATES")
print(f"BOOTSTRAP_REPLICATES={BOOTSTRAP_REPLICATES}")
print(f"PERMUTATION_REPLICATES={PERMUTATION_REPLICATES}")
print(f"BOOTSTRAP_SEED={BOOTSTRAP_SEED}")
print(f"PERMUTATION_SEED={PERMUTATION_SEED}")
print()

OUTDIR.mkdir(parents=True, exist_ok=True)
AUDITDIR.mkdir(parents=True, exist_ok=True)

if not INPUT.exists():
    raise RuntimeError("INPUT_MISSING=" + str(INPUT))

input_sha = sha256_file(INPUT)

print("SOURCE_INPUT=" + str(INPUT))
print("SOURCE_INPUT_SHA256=" + input_sha)

if input_sha != EXPECTED_INPUT_SHA256:
    raise RuntimeError(
        "SOURCE_INPUT_SHA256_MISMATCH="
        + input_sha
        + ":EXPECTED="
        + EXPECTED_INPUT_SHA256
    )

print("SOURCE_INPUT_SHA_GATE=PASS")
print()

rows = read_tsv(INPUT)

if not rows:
    raise RuntimeError("EMPTY_CANONICAL_LOGICAL_INPUT")

print("CANONICAL_ROWS=" + str(len(rows)))

# ------------------------------------------------------------
# Build one analysis value per
# benchmark x method x budget x original instance.
#
# Non-Random: exactly one binary terminal Z.
# Random: exactly ten frozen replicates, averaged first.
# ToolPRM-GRPO is deliberately outside T4.
# ------------------------------------------------------------

nonrandom = {}
random_reps = defaultdict(dict)

for row in rows:
    benchmark = row["benchmark"]
    method = row["method"]

    if benchmark not in BENCHMARKS:
        continue

    if method not in CORE_METHODS:
        continue

    budget = round(float(row["budget"]), 2)

    if budget not in D11:
        raise RuntimeError(
            "NON_D11_BUDGET="
            + repr((benchmark, method, budget))
        )

    instance_id = row["instance_id"]
    z = int(row["terminal_Z"])

    if z not in (0, 1):
        raise RuntimeError(
            "NONBINARY_TERMINAL_Z="
            + repr((benchmark, method, budget, instance_id, z))
        )

    key = (
        benchmark,
        method,
        budget,
        instance_id,
    )

    if method == "Random":
        rep = int(row["random_replicate"])

        if rep in random_reps[key]:
            raise RuntimeError(
                "DUPLICATE_RANDOM_REPLICATE="
                + repr((key, rep))
            )

        random_reps[key][rep] = z

    else:
        if key in nonrandom:
            raise RuntimeError(
                "DUPLICATE_NONRANDOM_KEY="
                + repr(key)
            )

        nonrandom[key] = float(z)


analysis_value = dict(nonrandom)

for key, rep_map in random_reps.items():
    if set(rep_map) != set(range(1, 11)):
        raise RuntimeError(
            "RANDOM_REPLICATE_SET_MISMATCH="
            + repr((key, sorted(rep_map)))
        )

    analysis_value[key] = (
        sum(rep_map.values()) / 10.0
    )

print("RANDOM_INSTANCE_BUDGET_CELLS=" + str(len(random_reps)))
print("CORE_ANALYSIS_INSTANCE_BUDGET_CELLS=" + str(len(analysis_value)))
print("RANDOM_COLLAPSE_GATE=PASS")
print()

# ------------------------------------------------------------
# Validate complete identical original-instance panels.
# ------------------------------------------------------------

benchmark_panels = {}

for benchmark in BENCHMARKS:
    reference = None

    for method in CORE_METHODS:
        method_common = None

        for budget in D11:
            here = {
                inst
                for (
                    bm,
                    m,
                    b,
                    inst,
                ) in analysis_value
                if bm == benchmark
                and m == method
                and b == budget
            }

            method_common = (
                here
                if method_common is None
                else method_common & here
            )

            if len(here) != EXPECTED_N[benchmark]:
                raise RuntimeError(
                    "INCOMPLETE_METHOD_BUDGET_PANEL="
                    + repr(
                        (
                            benchmark,
                            method,
                            budget,
                            len(here),
                            EXPECTED_N[benchmark],
                        )
                    )
                )

        method_common = set(method_common or [])

        if len(method_common) != EXPECTED_N[benchmark]:
            raise RuntimeError(
                "INCOMPLETE_METHOD_ALL_BUDGET_PANEL="
                + repr(
                    (
                        benchmark,
                        method,
                        len(method_common),
                    )
                )
            )

        if reference is None:
            reference = method_common
        elif method_common != reference:
            raise RuntimeError(
                "CORE_METHOD_INSTANCE_PANEL_MISMATCH="
                + repr((benchmark, method))
            )

    benchmark_panels[benchmark] = sorted(reference)

    print(
        "PANEL="
        + benchmark
        + ":N="
        + str(len(benchmark_panels[benchmark]))
    )

print("CORE_PAIRED_PANEL_GATE=PASS")
print()

# ------------------------------------------------------------
# Point estimates.
# ------------------------------------------------------------

point_rows = []
point_estimates = {}

for benchmark in BENCHMARKS:
    instances = benchmark_panels[benchmark]

    for method in CORE_METHODS:
        budget_values = {}

        for budget in D11:
            vals = [
                analysis_value[
                    (
                        benchmark,
                        method,
                        budget,
                        inst,
                    )
                ]
                for inst in instances
            ]

            budget_values[budget] = (
                sum(vals) / len(vals)
            )

        area = summary_from_budget_values(
            budget_values,
            "Area",
        )

        low = summary_from_budget_values(
            budget_values,
            "Low",
        )

        point_estimates[
            (benchmark, method, "Area")
        ] = area

        point_estimates[
            (benchmark, method, "Low")
        ] = low

        point_rows.append({
            "benchmark": benchmark,
            "method": method,
            "N": len(instances),
            "exact_curve_area": f"{area:.9f}",
            "low_quota_mean": f"{low:.9f}",
            "area_display_3dp": f"{area:.3f}",
            "low_display_3dp": f"{low:.3f}",
        })


# Manuscript point-estimate reproduction is a hard gate.
point_failures = []

for (benchmark, method), (
    expected_area,
    expected_low,
) in EXPECTED_POINT_ESTIMATES.items():

    got_area = (
        f"{point_estimates[(benchmark, method, 'Area')]:.3f}"
    )
    got_low = (
        f"{point_estimates[(benchmark, method, 'Low')]:.3f}"
    )

    if got_area != expected_area:
        point_failures.append(
            (
                benchmark,
                method,
                "Area",
                got_area,
                expected_area,
            )
        )

    if got_low != expected_low:
        point_failures.append(
            (
                benchmark,
                method,
                "Low",
                got_low,
                expected_low,
            )
        )

if point_failures:
    print("POINT_ESTIMATE_REPRODUCTION=FAIL")
    for x in point_failures:
        print("MISMATCH=" + repr(x))
    raise RuntimeError(
        "POINT_ESTIMATE_REPRODUCTION_FAILED"
    )

print("POINT_ESTIMATE_REPRODUCTION=PASS")
print()

point_path = (
    OUTDIR
    / "T4_NONENVELOPE_POINT_ESTIMATES.tsv"
)

write_tsv(
    point_path,
    point_rows,
    [
        "benchmark",
        "method",
        "N",
        "exact_curve_area",
        "low_quota_mean",
        "area_display_3dp",
        "low_display_3dp",
    ],
)

# ------------------------------------------------------------
# Instance-level paired DECOUPLE-minus-baseline differences.
# ------------------------------------------------------------

instance_budget_diff = {}

for benchmark in BENCHMARKS:
    instances = benchmark_panels[benchmark]

    for baseline in BASELINES:
        for budget in D11:
            for inst in instances:
                de = analysis_value[
                    (
                        benchmark,
                        "DECOUPLE",
                        budget,
                        inst,
                    )
                ]

                bl = analysis_value[
                    (
                        benchmark,
                        baseline,
                        budget,
                        inst,
                    )
                ]

                instance_budget_diff[
                    (
                        benchmark,
                        baseline,
                        budget,
                        inst,
                    )
                ] = de - bl


observed = {}

for benchmark in BENCHMARKS:
    instances = benchmark_panels[benchmark]

    for baseline in BASELINES:
        delta_by_budget = {}

        for budget in D11:
            diffs = [
                instance_budget_diff[
                    (
                        benchmark,
                        baseline,
                        budget,
                        inst,
                    )
                ]
                for inst in instances
            ]

            delta_by_budget[budget] = (
                sum(diffs) / len(diffs)
            )

        observed[
            (benchmark, baseline, "Area")
        ] = summary_from_budget_values(
            delta_by_budget,
            "Area",
        )

        observed[
            (benchmark, baseline, "Low")
        ] = summary_from_budget_values(
            delta_by_budget,
            "Low",
        )


# ------------------------------------------------------------
# Paired original-instance cluster bootstrap.
#
# One instance multiset is sampled per benchmark per replicate.
# The SAME sampled sequence is reused across:
#   - all 11 budgets
#   - all five T4 baseline contrasts
#
# This preserves the frozen original-instance clustering and
# gives a common resampling panel for the Holm-5 family.
# ------------------------------------------------------------

boot = defaultdict(list)
boot_rng = random.Random(BOOTSTRAP_SEED)

for rep in range(BOOTSTRAP_REPLICATES):
    for benchmark in BENCHMARKS:
        instances = benchmark_panels[benchmark]
        n = len(instances)

        sampled = [
            instances[boot_rng.randrange(n)]
            for _ in range(n)
        ]

        for baseline in BASELINES:
            delta_by_budget = {}

            for budget in D11:
                vals = [
                    instance_budget_diff[
                        (
                            benchmark,
                            baseline,
                            budget,
                            inst,
                        )
                    ]
                    for inst in sampled
                ]

                delta_by_budget[budget] = (
                    sum(vals) / n
                )

            for summary in ("Area", "Low"):
                boot[
                    (
                        benchmark,
                        baseline,
                        summary,
                    )
                ].append(
                    summary_from_budget_values(
                        delta_by_budget,
                        summary,
                    )
                )


print(
    "BOOTSTRAP_COMPLETED="
    + str(BOOTSTRAP_REPLICATES)
)
print("BOOTSTRAP_CLUSTER_GATE=PASS")
print()

# ------------------------------------------------------------
# Two-sided paired original-instance sign-flip permutation.
#
# One sign per original instance is reused across all 11 budgets.
# We also reuse that benchmark-level sign vector across the five
# contrasts inside the same descriptive family.
# ------------------------------------------------------------

perm_extreme = defaultdict(int)
perm_rng = random.Random(PERMUTATION_SEED)

for rep in range(PERMUTATION_REPLICATES):
    for benchmark in BENCHMARKS:
        instances = benchmark_panels[benchmark]

        signs = {
            inst: (
                1
                if perm_rng.randrange(2) == 1
                else -1
            )
            for inst in instances
        }

        for baseline in BASELINES:
            delta_by_budget = {}

            for budget in D11:
                vals = [
                    (
                        instance_budget_diff[
                            (
                                benchmark,
                                baseline,
                                budget,
                                inst,
                            )
                        ]
                        * signs[inst]
                    )
                    for inst in instances
                ]

                delta_by_budget[budget] = (
                    sum(vals) / len(vals)
                )

            for summary in ("Area", "Low"):
                perm_value = summary_from_budget_values(
                    delta_by_budget,
                    summary,
                )

                obs = observed[
                    (
                        benchmark,
                        baseline,
                        summary,
                    )
                ]

                if (
                    abs(perm_value)
                    >= abs(obs) - 1e-15
                ):
                    perm_extreme[
                        (
                            benchmark,
                            baseline,
                            summary,
                        )
                    ] += 1


raw_p = {}

for key in observed:
    raw_p[key] = (
        perm_extreme[key] + 1
    ) / (
        PERMUTATION_REPLICATES + 1
    )

print(
    "PERMUTATION_COMPLETED="
    + str(PERMUTATION_REPLICATES)
)
print("PERMUTATION_CLUSTER_GATE=PASS")
print()

# ------------------------------------------------------------
# Holm-5:
# separately within benchmark x summary.
# ------------------------------------------------------------

holm5 = {}

for benchmark in BENCHMARKS:
    for summary in ("Area", "Low"):
        family = [
            (
                baseline,
                raw_p[
                    (
                        benchmark,
                        baseline,
                        summary,
                    )
                ],
            )
            for baseline in BASELINES
        ]

        adjusted = holm_adjust(family)

        for baseline in BASELINES:
            holm5[
                (
                    benchmark,
                    baseline,
                    summary,
                )
            ] = adjusted[baseline]


# ------------------------------------------------------------
# Final 30-row inference artifact.
# ------------------------------------------------------------

inference_rows = []

for benchmark in BENCHMARKS:
    n = len(benchmark_panels[benchmark])

    for summary in ("Area", "Low"):
        for baseline in BASELINES:
            key = (
                benchmark,
                baseline,
                summary,
            )

            boots = boot[key]
            obs = observed[key]

            ci_low = percentile(
                boots,
                0.025,
            )

            ci_high = percentile(
                boots,
                0.975,
            )

            p = raw_p[key]
            p_holm = holm5[key]

            inference_rows.append({
                "benchmark": benchmark,
                "summary": summary,
                "baseline": baseline,
                "contrast": (
                    "DECOUPLE - "
                    + baseline
                ),
                "N_original_instances": n,
                "observed_delta": f"{obs:.9f}",
                "bootstrap_ci_low": f"{ci_low:.9f}",
                "bootstrap_ci_high": f"{ci_high:.9f}",
                "bootstrap_replicates":
                    BOOTSTRAP_REPLICATES,
                "permutation_p_raw":
                    f"{p:.9f}",
                "permutation_p_holm5":
                    f"{p_holm:.9f}",
                "permutation_replicates":
                    PERMUTATION_REPLICATES,
                "ci_excludes_zero":
                    int(
                        ci_low > 0.0
                        or ci_high < 0.0
                    ),
                "holm5_lt_0_05":
                    int(p_holm < 0.05),
            })


if len(inference_rows) != 30:
    raise RuntimeError(
        "T4_CONTRAST_ROW_COUNT="
        + str(len(inference_rows))
    )

inference_path = (
    OUTDIR
    / "T4_NONENVELOPE_CONTRAST_INFERENCE.tsv"
)

write_tsv(
    inference_path,
    inference_rows,
    [
        "benchmark",
        "summary",
        "baseline",
        "contrast",
        "N_original_instances",
        "observed_delta",
        "bootstrap_ci_low",
        "bootstrap_ci_high",
        "bootstrap_replicates",
        "permutation_p_raw",
        "permutation_p_holm5",
        "permutation_replicates",
        "ci_excludes_zero",
        "holm5_lt_0_05",
    ],
)


# Compact manuscript-facing summary.
print("=== T4 RESULTS ===")

for benchmark in BENCHMARKS:
    print()
    print("BENCHMARK=" + benchmark)

    for summary in ("Area", "Low"):
        print("SUMMARY=" + summary)

        for row in inference_rows:
            if (
                row["benchmark"] == benchmark
                and row["summary"] == summary
            ):
                print(
                    "  "
                    + row["baseline"]
                    + " delta="
                    + row["observed_delta"]
                    + " CI=["
                    + row["bootstrap_ci_low"]
                    + ","
                    + row["bootstrap_ci_high"]
                    + "]"
                    + " p="
                    + row["permutation_p_raw"]
                    + " Holm5="
                    + row["permutation_p_holm5"]
                )


ci_excluding = sum(
    int(r["ci_excludes_zero"])
    for r in inference_rows
)

holm_sig = sum(
    int(r["holm5_lt_0_05"])
    for r in inference_rows
)

script_sha = sha256_file(Path(__file__))

audit_lines = [
    "CURRENT=T4_NONENVELOPE_INFERENCE",
    "SOURCE_INPUT=" + str(INPUT),
    "SOURCE_INPUT_SHA256=" + input_sha,
    "SOURCE_INPUT_SHA_GATE=PASS",
    "SCRIPT_SHA256=" + script_sha,
    "POINT_ESTIMATE_REPRODUCTION=PASS",
    "PAIRING_CLUSTER=ORIGINAL_BENCHMARK_INSTANCE",
    "RANDOM_COLLAPSE_LEVEL=ORIGINAL_BENCHMARK_INSTANCE_BUDGET",
    "RANDOM_REPLICATES_REQUIRED=10",
    f"BOOTSTRAP_REPLICATES={BOOTSTRAP_REPLICATES}",
    f"BOOTSTRAP_SEED={BOOTSTRAP_SEED}",
    f"PERMUTATION_REPLICATES={PERMUTATION_REPLICATES}",
    f"PERMUTATION_SEED={PERMUTATION_SEED}",
    "SUMMARY_AREA=NORMALIZED_TRAPEZOID_0.05_TO_1.00",
    "SUMMARY_LOW=MEAN_0.05_0.10_0.20",
    "HOLM_FAMILY=WITHIN_BENCHMARK_X_SUMMARY_FIVE_CORE_BASELINES",
    "AREA_CONTRASTS=15",
    "LOW_CONTRASTS=15",
    "TOTAL_CONTRASTS=30",
    "CI_EXCLUDES_ZERO_COUNT=" + str(ci_excluding),
    "HOLM5_P_LT_0.05_COUNT=" + str(holm_sig),
    "NEW_API_CALLS=NO",
    "NEW_MODEL_EXECUTION=NO",
    "NEW_PHYSICAL_EXECUTION=NO",
    "SOURCE_MUTATION=NO",
    "TOOLPRM_GRPO_INCLUDED=NO",
    "DO_NOT_TOUCH=H1_H2_H3_H4_H5_H6_D11_PHYSICAL_RESULTS",
    "PASS=T4_DERIVED_INFERENCE_COMPLETE",
]

audit_path = (
    AUDITDIR
    / "T4_NONENVELOPE_INFERENCE_CLOSURE.txt"
)

audit_path.write_text(
    "\n".join(audit_lines) + "\n",
    encoding="utf-8",
)

print()
print("============================================================")
print("POINT_ESTIMATE_REPRODUCTION=PASS")
print("AREA_CONTRASTS=15")
print("LOW_CONTRASTS=15")
print("TOTAL_CONTRASTS=30")
print("CI_EXCLUDES_ZERO_COUNT=" + str(ci_excluding))
print("HOLM5_P_LT_0.05_COUNT=" + str(holm_sig))
print("NEW_API_CALLS=NO")
print("NEW_MODEL_EXECUTION=NO")
print("NEW_PHYSICAL_EXECUTION=NO")
print("SOURCE_MUTATION=NO")
print("T4=PASS")
print("============================================================")
print("OUTPUT=" + str(inference_path))
print("POINTS=" + str(point_path))
print("AUDIT=" + str(audit_path))
