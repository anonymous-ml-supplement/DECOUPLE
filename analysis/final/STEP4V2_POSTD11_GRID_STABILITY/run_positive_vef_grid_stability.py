#!/usr/bin/env python3

import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(
    "__DECOUPLE_ROOT__/10_PILOT/STEP4_V2_CLEAN_REBUILD"
)

SOURCE = (
    ROOT
    / "04_OUTPUTS/STEP4V2_D11_FINAL_RANDOM_AWARE_ANALYSIS/"
      "D11_FINAL_TERMINAL_UTILITY.tsv"
)

OUT_DIR = ROOT / "04_OUTPUTS/STEP4V2_POSTD11_GRID_STABILITY"
AUDIT_DIR = ROOT / "06_AUDIT/STEP4V2_POSTD11_GRID_STABILITY"

DETAIL = OUT_DIR / "GRID_STABILITY_CORE15_DETAIL.tsv"
SUMMARY = OUT_DIR / "GRID_STABILITY_SUMMARY.tsv"
ROBUST = OUT_DIR / "GRID_STABILITY_COMPARISON_ROBUSTNESS.tsv"
AUDIT = AUDIT_DIR / "01_GRID_STABILITY_AUDIT.json"

FULL_GRID = [5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
INTERIOR = [10, 20, 30, 40, 50, 60, 70, 80, 90]

GRID_A = [5, 20, 40, 60, 80, 100]
GRID_B = [5, 10, 30, 50, 70, 90, 100]

BASELINES = [
    "H-only",
    "p-only",
    "Random",
    "Step-PRM",
    "PRM@BoK",
]

CANONICAL_BENCHMARKS = [
    "BFCL",
    "Math-Shepherd",
    "ToolAlpaca",
]

CANONICAL_METHODS = ["DECOUPLE"] + BASELINES

TOL = 1e-12


def fail(msg):
    print(f"FAIL={msg}")
    raise SystemExit(1)


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def norm_token(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


BENCH_MAP = {
    "bfcl": "BFCL",
    "mathshepherd": "Math-Shepherd",
    "toolalpaca": "ToolAlpaca",
}

METHOD_MAP = {
    "decouple": "DECOUPLE",
    "honly": "H-only",
    "ponly": "p-only",
    "random": "Random",
    "stepprm": "Step-PRM",
    "prmbok": "PRM@BoK",
}


def canon_benchmark(raw):
    key = norm_token(raw)
    return BENCH_MAP.get(key)


def canon_method(raw):
    key = norm_token(raw)
    return METHOD_MAP.get(key)


def parse_budget(raw):
    s = str(raw).strip().replace("%", "")
    x = float(s)

    if 0 < x <= 1:
        x *= 100.0

    x = int(round(x))

    if x not in FULL_GRID:
        fail(f"UNEXPECTED_BUDGET={raw}")

    return x


def frontier(values):
    out = []
    best = None

    for v in values:
        best = v if best is None else max(best, v)
        out.append(best)

    return out


def trapz_normalized(xs, ys):
    if len(xs) != len(ys):
        fail("TRAPZ_LENGTH_MISMATCH")

    if len(xs) < 2:
        fail("TRAPZ_TOO_FEW_POINTS")

    width = xs[-1] - xs[0]

    if abs(width) <= 0:
        fail("TRAPZ_ZERO_WIDTH")

    area = 0.0

    for i in range(len(xs) - 1):
        dx = xs[i + 1] - xs[i]
        area += dx * (ys[i] + ys[i + 1]) / 2.0

    return area / width


def aubc(values_by_budget, grid, weighting):
    ys = frontier([values_by_budget[b] for b in grid])

    if weighting == "linear":
        xs = [b / 100.0 for b in grid]

    elif weighting == "log":
        # Frozen prior definition from metric-space authority:
        # log_x = [math.log(x / 100.0) for x in GRID]
        xs = [math.log(b / 100.0) for b in grid]

    else:
        fail(f"UNKNOWN_WEIGHTING={weighting}")

    return trapz_normalized(xs, ys)


def direction(delta):
    if delta > TOL:
        return "POSITIVE"
    if delta < -TOL:
        return "NEGATIVE"
    return "TIE"


if not SOURCE.exists():
    fail(f"MISSING_SOURCE={SOURCE}")


# ------------------------------------------------------------
# Read and canonicalize frozen final random-aware utility table.
# Ignore non-core specialized methods here by design.
# ------------------------------------------------------------
utility = {}
raw_benchmarks = set()
raw_methods = set()

with SOURCE.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")

    required = {
        "benchmark",
        "method",
        "budget",
        "terminal_utility",
    }

    if not required.issubset(set(reader.fieldnames or [])):
        fail(
            "SOURCE_SCHEMA_MISMATCH="
            + repr(reader.fieldnames)
        )

    for row in reader:
        raw_benchmarks.add(row["benchmark"])
        raw_methods.add(row["method"])

        benchmark = canon_benchmark(row["benchmark"])
        method = canon_method(row["method"])

        # Specialized/non-core comparator remains outside core15.
        if benchmark is None or method is None:
            continue

        budget = parse_budget(row["budget"])
        key = (benchmark, method, budget)

        if key in utility:
            fail(f"DUPLICATE_AGGREGATE_CELL={key}")

        utility[key] = float(row["terminal_utility"])


# ------------------------------------------------------------
# Strict completeness gate: 3 x 6 x 11 exact-budget cells.
# ------------------------------------------------------------
expected_cells = (
    len(CANONICAL_BENCHMARKS)
    * len(CANONICAL_METHODS)
    * len(FULL_GRID)
)

if len(utility) != expected_cells:
    missing = []

    for benchmark in CANONICAL_BENCHMARKS:
        for method in CANONICAL_METHODS:
            for budget in FULL_GRID:
                if (benchmark, method, budget) not in utility:
                    missing.append(
                        f"{benchmark}|{method}|{budget}"
                    )

    fail(
        f"CORE_EXACT_BUDGET_CELL_COUNT={len(utility)}"
        f"_EXPECTED={expected_cells}"
        f"_MISSING={missing[:30]}"
    )


series = {}

for benchmark in CANONICAL_BENCHMARKS:
    for method in CANONICAL_METHODS:
        series[(benchmark, method)] = {
            budget: utility[(benchmark, method, budget)]
            for budget in FULL_GRID
        }


# ------------------------------------------------------------
# Mechanically frozen sensitivity scenarios.
# ------------------------------------------------------------
scenarios = [("FULL", FULL_GRID)]

for removed in INTERIOR:
    grid = [b for b in FULL_GRID if b != removed]
    scenarios.append((f"LOO_{removed}", grid))

scenarios.extend([
    ("GRID_A", GRID_A),
    ("GRID_B", GRID_B),
])

weightings = ["linear", "log"]


# ------------------------------------------------------------
# Establish immutable reference direction from FULL + linear.
# This must reproduce 10 positive / 5 tie / 0 negative.
# ------------------------------------------------------------
primary_direction = {}
primary_delta = {}

for benchmark in CANONICAL_BENCHMARKS:
    de = aubc(
        series[(benchmark, "DECOUPLE")],
        FULL_GRID,
        "linear",
    )

    for baseline in BASELINES:
        bl = aubc(
            series[(benchmark, baseline)],
            FULL_GRID,
            "linear",
        )

        delta = de - bl

        primary_direction[(benchmark, baseline)] = direction(delta)
        primary_delta[(benchmark, baseline)] = delta


primary_counts = Counter(primary_direction.values())

if (
    primary_counts["POSITIVE"] != 10
    or primary_counts["TIE"] != 5
    or primary_counts["NEGATIVE"] != 0
):
    fail(
        "PRIMARY_10_5_0_RECONSTRUCTION_FAILED:"
        + repr(dict(primary_counts))
    )


# ------------------------------------------------------------
# Run every mechanically pre-specified sensitivity.
# ------------------------------------------------------------
detail_rows = []
summary_rows = []

for scenario_name, grid in scenarios:
    for weighting in weightings:
        counts = Counter()
        flips_from_primary = 0
        negative_vs_primary_nonnegative = 0

        for benchmark in CANONICAL_BENCHMARKS:
            de_aubc = aubc(
                series[(benchmark, "DECOUPLE")],
                grid,
                weighting,
            )

            for baseline in BASELINES:
                baseline_aubc = aubc(
                    series[(benchmark, baseline)],
                    grid,
                    weighting,
                )

                delta = de_aubc - baseline_aubc
                d = direction(delta)
                primary_d = primary_direction[
                    (benchmark, baseline)
                ]

                counts[d] += 1

                if d != primary_d:
                    flips_from_primary += 1

                if (
                    primary_d in {"POSITIVE", "TIE"}
                    and d == "NEGATIVE"
                ):
                    negative_vs_primary_nonnegative += 1

                detail_rows.append({
                    "scenario": scenario_name,
                    "weighting": weighting,
                    "grid": ",".join(map(str, grid)),
                    "benchmark": benchmark,
                    "baseline": baseline,
                    "de_aubc": de_aubc,
                    "baseline_aubc": baseline_aubc,
                    "delta": delta,
                    "direction": d,
                    "primary_full_linear_delta":
                        primary_delta[(benchmark, baseline)],
                    "primary_full_linear_direction":
                        primary_d,
                    "matches_primary_direction":
                        d == primary_d,
                })

        summary_rows.append({
            "scenario": scenario_name,
            "weighting": weighting,
            "grid": ",".join(map(str, grid)),
            "positive": counts["POSITIVE"],
            "tie": counts["TIE"],
            "negative": counts["NEGATIVE"],
            "direction_changes_vs_primary":
                flips_from_primary,
            "new_negative_vs_primary_nonnegative":
                negative_vs_primary_nonnegative,
        })


# ------------------------------------------------------------
# Per-comparison robustness envelope across all frozen
# sensitivities, including linear and log.
# ------------------------------------------------------------
grouped = defaultdict(list)

for row in detail_rows:
    grouped[
        (row["benchmark"], row["baseline"])
    ].append(row)

robust_rows = []

for benchmark in CANONICAL_BENCHMARKS:
    for baseline in BASELINES:
        rows = grouped[(benchmark, baseline)]
        deltas = [float(r["delta"]) for r in rows]
        dirs = Counter(r["direction"] for r in rows)

        robust_rows.append({
            "benchmark": benchmark,
            "baseline": baseline,
            "primary_direction":
                primary_direction[(benchmark, baseline)],
            "primary_delta":
                primary_delta[(benchmark, baseline)],
            "sensitivity_cells": len(rows),
            "positive_cells": dirs["POSITIVE"],
            "tie_cells": dirs["TIE"],
            "negative_cells": dirs["NEGATIVE"],
            "min_delta": min(deltas),
            "max_delta": max(deltas),
            "any_negative":
                dirs["NEGATIVE"] > 0,
            "all_nonnegative":
                dirs["NEGATIVE"] == 0,
            "all_same_as_primary":
                all(
                    r["direction"]
                    == primary_direction[(benchmark, baseline)]
                    for r in rows
                ),
        })


# ------------------------------------------------------------
# Persist.
# ------------------------------------------------------------
detail_fields = [
    "scenario",
    "weighting",
    "grid",
    "benchmark",
    "baseline",
    "de_aubc",
    "baseline_aubc",
    "delta",
    "direction",
    "primary_full_linear_delta",
    "primary_full_linear_direction",
    "matches_primary_direction",
]

with DETAIL.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=detail_fields,
        delimiter="\t",
    )
    writer.writeheader()
    writer.writerows(detail_rows)


summary_fields = [
    "scenario",
    "weighting",
    "grid",
    "positive",
    "tie",
    "negative",
    "direction_changes_vs_primary",
    "new_negative_vs_primary_nonnegative",
]

with SUMMARY.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=summary_fields,
        delimiter="\t",
    )
    writer.writeheader()
    writer.writerows(summary_rows)


robust_fields = [
    "benchmark",
    "baseline",
    "primary_direction",
    "primary_delta",
    "sensitivity_cells",
    "positive_cells",
    "tie_cells",
    "negative_cells",
    "min_delta",
    "max_delta",
    "any_negative",
    "all_nonnegative",
    "all_same_as_primary",
]

with ROBUST.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=robust_fields,
        delimiter="\t",
    )
    writer.writeheader()
    writer.writerows(robust_rows)


all_summary_nonnegative = all(
    int(r["negative"]) == 0
    for r in summary_rows
)

all_comparisons_nonnegative = all(
    bool(r["all_nonnegative"])
    for r in robust_rows
)

audit = {
    "audit": "POSITIVE_BUDGET_VEF_GRID_STABILITY",
    "authority_scope": "Spec5.5.5_ChecklistV27",
    "estimand": "VEF_AUBC_5_TO_100",
    "zero_anchor_included": False,
    "api_calls": 0,
    "new_model_execution": 0,
    "metric_search": False,
    "source": str(SOURCE),
    "source_sha256": sha256_file(SOURCE),
    "full_grid": FULL_GRID,
    "leave_one_interior_out": INTERIOR,
    "grid_A": GRID_A,
    "grid_B": GRID_B,
    "weightings": {
        "linear": "x=b/100",
        "log": "x=log(b/100), frozen prior definition",
    },
    "primary_full_linear_counts": {
        "positive": primary_counts["POSITIVE"],
        "tie": primary_counts["TIE"],
        "negative": primary_counts["NEGATIVE"],
    },
    "scenario_count": len(scenarios),
    "scenario_weighting_cells":
        len(scenarios) * len(weightings),
    "core_comparisons": 15,
    "all_sensitivity_summaries_nonnegative":
        all_summary_nonnegative,
    "all_core_comparisons_nonnegative_across_all_sensitivities":
        all_comparisons_nonnegative,
    "specialized_ToolPRM_GRPO":
        "EXCLUDED_FROM_CORE15_AS_FROZEN_SPECIALIZED_COMPARATOR",
    "outputs": {
        "detail": str(DETAIL),
        "summary": str(SUMMARY),
        "comparison_robustness": str(ROBUST),
    },
    "next": "GLOBAL_HOLM15_SENSITIVITY",
}

AUDIT.write_text(
    json.dumps(audit, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)


# ------------------------------------------------------------
# Compact terminal output.
# ------------------------------------------------------------
print("CURRENT=POSITIVE_BUDGET_VEF_GRID_STABILITY")
print(
    "PASS=PRIMARY_FULL_LINEAR_RECONSTRUCTED_"
    "10_POSITIVE_5_TIE_0_NEGATIVE"
)
print()

print("=== GRID STABILITY SUMMARY ===")

for row in summary_rows:
    print(
        f"{row['scenario']}|{row['weighting']}|"
        f"P={row['positive']}|"
        f"T={row['tie']}|"
        f"N={row['negative']}|"
        f"CHANGES={row['direction_changes_vs_primary']}|"
        f"NEW_NEG={row['new_negative_vs_primary_nonnegative']}"
    )

print()
print("=== PER-COMPARISON ROBUSTNESS ===")

for row in robust_rows:
    print(
        f"{row['benchmark']}|{row['baseline']}|"
        f"PRIMARY={row['primary_direction']}|"
        f"P={row['positive_cells']}|"
        f"T={row['tie_cells']}|"
        f"N={row['negative_cells']}|"
        f"MIN_DELTA={float(row['min_delta']):.9f}|"
        f"MAX_DELTA={float(row['max_delta']):.9f}"
    )

print()

if all_summary_nonnegative and all_comparisons_nonnegative:
    print("PASS=NO_NEGATIVE_CORE_COMPARISON_UNDER_FROZEN_GRID_SENSITIVITIES")
else:
    print("FAIL=NEGATIVE_CORE_COMPARISON_APPEARS_UNDER_FROZEN_GRID_SENSITIVITY")

print("API_CALLS=NO")
print("NEW_MODEL_EXECUTION=NO")
print("ZERO_ANCHOR_INCLUDED=NO")
print("METRIC_SEARCH=NO")

print(f"DETAIL={DETAIL}")
print(f"SUMMARY={SUMMARY}")
print(f"ROBUST={ROBUST}")
print(f"AUDIT={AUDIT}")

print("DONE=GRID_STABILITY_STRESS_TEST")
print("NEXT=GLOBAL_HOLM15_SENSITIVITY")
print("DO_NOT_TOUCH=H1_H2_H3_H4_H5_H6_D11_PHYSICAL_RESULTS")
