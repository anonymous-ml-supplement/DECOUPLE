#!/usr/bin/env python3

from pathlib import Path
import csv
import hashlib
import math
import sys
from collections import defaultdict

ROOT = Path(
    "__DECOUPLE_ROOT__/10_PILOT/STEP4_V2_CLEAN_REBUILD"
)

SRC = (
    ROOT
    / "04_OUTPUTS"
    / "STEP4V2_D11_FINAL_RANDOM_AWARE_ANALYSIS"
    / "D11_FINAL_ALL_LOGICAL_RESULTS.tsv"
)

OUT = (
    ROOT
    / "04_OUTPUTS"
    / "STEP4V2_POSTD11_EXACT_BUDGET_MAIN_TABLE"
)

AUDIT = (
    ROOT
    / "06_AUDIT"
    / "STEP4V2_POSTD11_EXACT_BUDGET_MAIN_TABLE"
)

EXPECTED_SOURCE_SHA = (
    "32d160166c3546f62b579f30e2e007e6213fb64596fca9b9ecb52f3b1bb83c53"
)

BUDGETS = [5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

BENCHMARK_ORDER = [
    "BFCL",
    "Math-Shepherd",
    "ToolAlpaca",
]

METHOD_ORDER = [
    "DECOUPLE",
    "H-only",
    "p-only",
    "Random",
    "Step-PRM",
    "PRM@BoK",
]

BASELINES = [
    "H-only",
    "p-only",
    "Random",
    "Step-PRM",
    "PRM@BoK",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def normalize_budget(x: str) -> int:
    v = float(x)

    if v <= 1.0000001:
        v *= 100.0

    b = int(round(v))

    if b not in BUDGETS:
        raise ValueError(
            f"Unexpected D11 budget {x!r} -> {b}; expected {BUDGETS}"
        )

    return b


def canonical_benchmark(x: str) -> str:
    s = x.strip()
    lo = s.lower().replace("_", "-")

    if "bfcl" in lo:
        return "BFCL"

    if "math" in lo and "shepherd" in lo:
        return "Math-Shepherd"

    if "toolalpaca" in lo or "tool-alpaca" in lo:
        return "ToolAlpaca"

    raise ValueError(f"Unknown benchmark label: {x!r}")


def canonical_method(x: str) -> str:
    s = x.strip()
    lo = (
        s.lower()
        .replace("_", "-")
        .replace(" ", "")
    )

    if lo == "decouple":
        return "DECOUPLE"

    if lo in {"h-only", "honly"}:
        return "H-only"

    if lo in {"p-only", "ponly"}:
        return "p-only"

    if lo in {"random"}:
        return "Random"

    if lo in {
        "step-prm",
        "stepprm",
    }:
        return "Step-PRM"

    if lo in {
        "prm@bok",
        "prm-at-bok",
        "prmatbok",
        "prm-bok",
    }:
        return "PRM@BoK"

    raise ValueError(f"Unknown core method label: {x!r}")


def trapezoid_aubc(values):
    """
    Normalized area over the physical capacity interval [5,100].
    This does NOT replace the detailed 11-capacity curve.
    """
    area = 0.0

    for i in range(len(BUDGETS) - 1):
        x0 = BUDGETS[i]
        x1 = BUDGETS[i + 1]
        y0 = values[x0]
        y1 = values[x1]

        area += (x1 - x0) * (y0 + y1) / 2.0

    return area / (BUDGETS[-1] - BUDGETS[0])


def direction(delta, eps=1e-12):
    if delta > eps:
        return "POSITIVE"
    if delta < -eps:
        return "NEGATIVE"
    return "TIE"


if not SRC.is_file():
    raise SystemExit(f"FAIL=MISSING_CANONICAL_SOURCE\nSOURCE={SRC}")

src_sha = sha256_file(SRC)

if src_sha != EXPECTED_SOURCE_SHA:
    raise SystemExit(
        "FAIL=CANONICAL_SOURCE_SHA_MISMATCH\n"
        f"EXPECTED={EXPECTED_SOURCE_SHA}\n"
        f"ACTUAL={src_sha}\n"
        f"SOURCE={SRC}"
    )

OUT.mkdir(parents=True, exist_ok=True)
AUDIT.mkdir(parents=True, exist_ok=True)

targets = [
    OUT / "D11_EXACT_BUDGET_TERMINAL_UTILITY_LONG.tsv",
    OUT / "D11_EXACT_BUDGET_TERMINAL_UTILITY_WIDE.tsv",
    OUT / "D11_VEF_CAPACITY_CURVE_LONG.tsv",
    OUT / "D11_VEF_CAPACITY_CURVE_WIDE.tsv",
    OUT / "D11_VEF_CORE15_PAIRWISE_BY_CAP.tsv",
    OUT / "D11_VEF_CORE15_PAIR_SUMMARY.tsv",
    OUT / "D11_VEF_MANUSCRIPT_MAIN_TABLE.tsv",
    AUDIT / "01_D11_DETAILED_PRIMARY_TABLE_AUDIT.txt",
]

for path in targets:
    if path.exists():
        raise SystemExit(
            "FAIL=OUTPUT_TARGET_EXISTS\n"
            f"TARGET={path}\n"
            "DONE=NO_OVERWRITE"
        )

rows = []

with SRC.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")

    required = {
        "benchmark",
        "method",
        "budget",
        "instance_id",
        "random_replicate",
        "terminal_Z",
    }

    missing = required - set(reader.fieldnames or [])

    if missing:
        raise SystemExit(
            f"FAIL=SOURCE_SCHEMA_MISSING_FIELDS\nMISSING={sorted(missing)}"
        )

    raw_methods = set()
    raw_benchmarks = set()

    for r in reader:
        raw_methods.add(r["method"])
        raw_benchmarks.add(r["benchmark"])

        try:
            benchmark = canonical_benchmark(r["benchmark"])
            method = canonical_method(r["method"])
        except ValueError:
            # Canonical D11 source can contain methods outside this core table.
            # They are intentionally excluded here rather than relabeled.
            continue

        budget = normalize_budget(r["budget"])

        z = float(r["terminal_Z"])

        if not math.isfinite(z):
            raise SystemExit(
                "FAIL=NONFINITE_TERMINAL_Z\n"
                f"ROW={r}"
            )

        rows.append(
            {
                "benchmark": benchmark,
                "method": method,
                "budget": budget,
                "instance_id": r["instance_id"],
                "random_replicate": r["random_replicate"],
                "terminal_Z": z,
            }
        )

print("SOURCE_ROWS_CORE=", len(rows))
print("RAW_BENCHMARK_LABELS=", sorted(raw_benchmarks))
print("RAW_METHOD_LABELS=", sorted(raw_methods))


# ----------------------------------------------------------------------
# 1. Collapse logical rows to instance x method x budget.
#
# Random:
#   average frozen random replicates within original instance-budget first.
#
# Deterministic:
#   require duplicated logical rows, if any, to agree in terminal_Z.
# ----------------------------------------------------------------------

grouped = defaultdict(list)

for r in rows:
    key = (
        r["benchmark"],
        r["method"],
        r["budget"],
        r["instance_id"],
    )
    grouped[key].append(r["terminal_Z"])


instance_value = {}

for key, vals in grouped.items():
    benchmark, method, budget, instance_id = key

    if method != "Random":
        lo = min(vals)
        hi = max(vals)

        if abs(hi - lo) > 1e-12:
            raise SystemExit(
                "FAIL=DETERMINISTIC_DUPLICATE_DISAGREEMENT\n"
                f"KEY={key}\n"
                f"VALUES={vals}"
            )

    instance_value[key] = sum(vals) / len(vals)


# ----------------------------------------------------------------------
# 2. Exact-budget physical terminal utility.
# ----------------------------------------------------------------------

exact = defaultdict(dict)
panel_n = defaultdict(dict)

for benchmark in BENCHMARK_ORDER:
    for method in METHOD_ORDER:
        for budget in BUDGETS:

            vals = [
                v
                for (b, m, beta, instance_id), v
                in instance_value.items()
                if b == benchmark
                and m == method
                and beta == budget
            ]

            if not vals:
                raise SystemExit(
                    "FAIL=MISSING_CORE_CELL\n"
                    f"BENCHMARK={benchmark}\n"
                    f"METHOD={method}\n"
                    f"BUDGET={budget}"
                )

            exact[(benchmark, method)][budget] = (
                sum(vals) / len(vals)
            )

            panel_n[(benchmark, method)][budget] = len(vals)


# Expected main-panel support.
expected_n = {
    "BFCL": 25,
    "Math-Shepherd": 50,
    "ToolAlpaca": 25,
}

for benchmark in BENCHMARK_ORDER:
    for method in METHOD_ORDER:
        for budget in BUDGETS:
            n = panel_n[(benchmark, method)][budget]

            if n != expected_n[benchmark]:
                raise SystemExit(
                    "FAIL=CORE_PANEL_N_MISMATCH\n"
                    f"BENCHMARK={benchmark}\n"
                    f"METHOD={method}\n"
                    f"BUDGET={budget}\n"
                    f"EXPECTED_N={expected_n[benchmark]}\n"
                    f"ACTUAL_N={n}"
                )


# ----------------------------------------------------------------------
# 3. VEF capacity curve.
#
# Frozen empirical frontier:
#
# U_VEF(B) = max_{b <= B} U_exact(b)
#
# This produces an 11-capacity curve.
# It does NOT replace or erase the exact-budget physical table.
# ----------------------------------------------------------------------

vef = defaultdict(dict)
vef_source_budget = defaultdict(dict)

for benchmark in BENCHMARK_ORDER:
    for method in METHOD_ORDER:

        best_value = None
        best_budget = None

        for cap in BUDGETS:

            candidate = exact[(benchmark, method)][cap]

            if (
                best_value is None
                or candidate > best_value + 1e-12
            ):
                best_value = candidate
                best_budget = cap

            # smallest-budget argmax is retained automatically:
            # equal later values do not replace the earlier budget.
            vef[(benchmark, method)][cap] = best_value
            vef_source_budget[(benchmark, method)][cap] = best_budget


# ----------------------------------------------------------------------
# 4. AUBC over full VEF curve.
# ----------------------------------------------------------------------

aubc = {}

for benchmark in BENCHMARK_ORDER:
    for method in METHOD_ORDER:
        aubc[(benchmark, method)] = trapezoid_aubc(
            vef[(benchmark, method)]
        )


# ----------------------------------------------------------------------
# 5. Pairwise VEF cap-level directions.
# ----------------------------------------------------------------------

pair_rows = []
pair_summary = []

point_pos = 0
point_tie = 0
point_neg = 0

pair_pos = 0
pair_tie = 0
pair_neg = 0

for benchmark in BENCHMARK_ORDER:
    de_aubc = aubc[(benchmark, "DECOUPLE")]

    for baseline in BASELINES:

        p = 0
        t = 0
        n = 0

        for cap in BUDGETS:
            de = vef[(benchmark, "DECOUPLE")][cap]
            bl = vef[(benchmark, baseline)][cap]

            delta = de - bl
            d = direction(delta)

            if d == "POSITIVE":
                p += 1
                point_pos += 1
            elif d == "TIE":
                t += 1
                point_tie += 1
            else:
                n += 1
                point_neg += 1

            pair_rows.append(
                {
                    "benchmark": benchmark,
                    "baseline": baseline,
                    "capacity_pct": cap,
                    "DECOUPLE_VEF": de,
                    "baseline_VEF": bl,
                    "delta": delta,
                    "direction": d,
                    "DECOUPLE_source_budget": (
                        vef_source_budget[
                            (benchmark, "DECOUPLE")
                        ][cap]
                    ),
                    "baseline_source_budget": (
                        vef_source_budget[
                            (benchmark, baseline)
                        ][cap]
                    ),
                }
            )

        bl_aubc = aubc[(benchmark, baseline)]
        delta_aubc = de_aubc - bl_aubc
        adir = direction(delta_aubc)

        if adir == "POSITIVE":
            pair_pos += 1
        elif adir == "TIE":
            pair_tie += 1
        else:
            pair_neg += 1

        pair_summary.append(
            {
                "benchmark": benchmark,
                "baseline": baseline,
                "DECOUPLE_VEF_AUBC": de_aubc,
                "baseline_VEF_AUBC": bl_aubc,
                "delta_VEF_AUBC": delta_aubc,
                "AUBC_direction": adir,
                "capacity_positive": p,
                "capacity_tie": t,
                "capacity_negative": n,
            }
        )


# ----------------------------------------------------------------------
# 6. HARD SCIENTIFIC ASSERTIONS AGAINST FROZEN RESULT.
# ----------------------------------------------------------------------

if (point_pos, point_tie, point_neg) != (96, 69, 0):
    raise SystemExit(
        "FAIL=FROZEN_POINTWISE_PATTERN_NOT_REPRODUCED\n"
        f"EXPECTED=96_POSITIVE_69_TIE_0_NEGATIVE\n"
        f"ACTUAL={point_pos}_POSITIVE_{point_tie}_TIE_{point_neg}_NEGATIVE\n"
        "INTERPRETATION=DO_NOT_USE_GENERATED_TABLE_AS_MANUSCRIPT_AUTHORITY"
    )

if (pair_pos, pair_tie, pair_neg) != (10, 5, 0):
    raise SystemExit(
        "FAIL=FROZEN_CORE15_PATTERN_NOT_REPRODUCED\n"
        f"EXPECTED=10_POSITIVE_5_TIE_0_NEGATIVE\n"
        f"ACTUAL={pair_pos}_POSITIVE_{pair_tie}_TIE_{pair_neg}_NEGATIVE\n"
        "INTERPRETATION=DO_NOT_USE_GENERATED_TABLE_AS_MANUSCRIPT_AUTHORITY"
    )


# ----------------------------------------------------------------------
# 7. Write exact-budget LONG.
# ----------------------------------------------------------------------

exact_long = targets[0]

with exact_long.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t")

    w.writerow(
        [
            "benchmark",
            "method",
            "budget_pct",
            "terminal_utility",
            "panel_n",
        ]
    )

    for benchmark in BENCHMARK_ORDER:
        for method in METHOD_ORDER:
            for budget in BUDGETS:
                w.writerow(
                    [
                        benchmark,
                        method,
                        budget,
                        f"{exact[(benchmark, method)][budget]:.9f}",
                        panel_n[(benchmark, method)][budget],
                    ]
                )


# ----------------------------------------------------------------------
# 8. Write exact-budget WIDE.
# ----------------------------------------------------------------------

exact_wide = targets[1]

with exact_wide.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t")

    w.writerow(
        ["benchmark", "method", "N"]
        + [f"{b}%" for b in BUDGETS]
    )

    for benchmark in BENCHMARK_ORDER:
        for method in METHOD_ORDER:
            w.writerow(
                [
                    benchmark,
                    method,
                    expected_n[benchmark],
                ]
                + [
                    f"{exact[(benchmark, method)][b]:.3f}"
                    for b in BUDGETS
                ]
            )


# ----------------------------------------------------------------------
# 9. Write VEF LONG.
# ----------------------------------------------------------------------

vef_long = targets[2]

with vef_long.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t")

    w.writerow(
        [
            "benchmark",
            "method",
            "capacity_pct",
            "VEF_utility",
            "attaining_exact_budget_pct",
        ]
    )

    for benchmark in BENCHMARK_ORDER:
        for method in METHOD_ORDER:
            for cap in BUDGETS:
                w.writerow(
                    [
                        benchmark,
                        method,
                        cap,
                        f"{vef[(benchmark, method)][cap]:.9f}",
                        vef_source_budget[(benchmark, method)][cap],
                    ]
                )


# ----------------------------------------------------------------------
# 10. Write VEF WIDE.
# ----------------------------------------------------------------------

vef_wide = targets[3]

with vef_wide.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t")

    w.writerow(
        ["benchmark", "method", "N"]
        + [f"{b}%" for b in BUDGETS]
        + ["VEF_AUBC_5_100"]
    )

    for benchmark in BENCHMARK_ORDER:
        for method in METHOD_ORDER:
            w.writerow(
                [
                    benchmark,
                    method,
                    expected_n[benchmark],
                ]
                + [
                    f"{vef[(benchmark, method)][b]:.3f}"
                    for b in BUDGETS
                ]
                + [
                    f"{aubc[(benchmark, method)]:.6f}"
                ]
            )


# ----------------------------------------------------------------------
# 11. Pairwise by-cap table.
# ----------------------------------------------------------------------

pairwise_path = targets[4]

with pairwise_path.open("w", encoding="utf-8", newline="") as f:
    fields = [
        "benchmark",
        "baseline",
        "capacity_pct",
        "DECOUPLE_VEF",
        "baseline_VEF",
        "delta",
        "direction",
        "DECOUPLE_source_budget",
        "baseline_source_budget",
    ]

    w = csv.DictWriter(
        f,
        fieldnames=fields,
        delimiter="\t",
    )
    w.writeheader()

    for r in pair_rows:
        rr = dict(r)

        for k in [
            "DECOUPLE_VEF",
            "baseline_VEF",
            "delta",
        ]:
            rr[k] = f"{rr[k]:.9f}"

        w.writerow(rr)


# ----------------------------------------------------------------------
# 12. Pair summary.
# ----------------------------------------------------------------------

pair_summary_path = targets[5]

with pair_summary_path.open(
    "w",
    encoding="utf-8",
    newline="",
) as f:
    fields = [
        "benchmark",
        "baseline",
        "DECOUPLE_VEF_AUBC",
        "baseline_VEF_AUBC",
        "delta_VEF_AUBC",
        "AUBC_direction",
        "capacity_positive",
        "capacity_tie",
        "capacity_negative",
    ]

    w = csv.DictWriter(
        f,
        fieldnames=fields,
        delimiter="\t",
    )
    w.writeheader()

    for r in pair_summary:
        rr = dict(r)

        for k in [
            "DECOUPLE_VEF_AUBC",
            "baseline_VEF_AUBC",
            "delta_VEF_AUBC",
        ]:
            rr[k] = f"{rr[k]:.9f}"

        w.writerow(rr)


# ----------------------------------------------------------------------
# 13. Manuscript-facing main table.
#
# This is the requested NON-COLLAPSED primary table:
# 11 capacity columns + AUBC.
# ----------------------------------------------------------------------

main_table = targets[6]

with main_table.open(
    "w",
    encoding="utf-8",
    newline="",
) as f:
    w = csv.writer(f, delimiter="\t")

    w.writerow(
        [
            "benchmark",
            "method",
            "N",
        ]
        + [f"VEF@{b}%" for b in BUDGETS]
        + ["VEF_AUBC_5_100"]
    )

    for benchmark in BENCHMARK_ORDER:
        for method in METHOD_ORDER:

            w.writerow(
                [
                    benchmark,
                    method,
                    expected_n[benchmark],
                ]
                + [
                    f"{vef[(benchmark, method)][b]:.3f}"
                    for b in BUDGETS
                ]
                + [
                    f"{aubc[(benchmark, method)]:.3f}"
                ]
            )


# ----------------------------------------------------------------------
# 14. Audit.
# ----------------------------------------------------------------------

audit_path = targets[7]

with audit_path.open("w", encoding="utf-8") as f:

    f.write("CURRENT=D11_DETAILED_PRIMARY_TABLE\n")
    f.write(f"SOURCE={SRC}\n")
    f.write(f"SOURCE_SHA256={src_sha}\n")
    f.write("SOURCE_ROWS=16908_EXPECTED_WITH_HEADER\n")
    f.write("\n")

    f.write(
        "PRIMARY_MANUSCRIPT_DISPLAY="
        "11_CAPACITY_VEF_CURVE_PLUS_AUBC\n"
    )

    f.write(
        "COMPANION_PHYSICAL_DISPLAY="
        "11_EXACT_BUDGET_TERMINAL_UTILITY\n"
    )

    f.write("VEF_REDEFINITION=NO\n")
    f.write("RAW_EXACT_RESULT_MUTATION=NO\n")
    f.write("SMOOTHING=NO\n")
    f.write("INTERPOLATION=NO\n")
    f.write(
        "VEF_OPERATION=FROZEN_CUMULATIVE_ATTAINABLE_MAX_WITH_SMALLEST_BUDGET_ARGMAX\n"
    )

    f.write("\n")

    f.write(
        f"POINTWISE_PATTERN="
        f"{point_pos}_POSITIVE_"
        f"{point_tie}_TIE_"
        f"{point_neg}_NEGATIVE\n"
    )

    f.write(
        f"CORE15_AUBC_PATTERN="
        f"{pair_pos}_POSITIVE_"
        f"{pair_tie}_TIE_"
        f"{pair_neg}_NEGATIVE\n"
    )

    f.write("\n")

    f.write("PASS=FROZEN_POINTWISE_96_69_0_REPRODUCED\n")
    f.write("PASS=FROZEN_CORE15_10_5_0_REPRODUCED\n")
    f.write("PASS=DETAILED_11_CAPACITY_TABLE_MATERIALIZED\n")
    f.write("PASS=RAW_EXACT_BUDGET_TABLE_RETAINED_SEPARATELY\n")

    f.write("\n")

    f.write(
        "DONE=D11_DETAILED_PRIMARY_TABLE\n"
    )

    f.write(
        "NEXT=INSPECT_NUMERIC_TABLE_AND_BIND_INTO_PAPER_BEFORE_AUTHORITY\n"
    )

    f.write(
        "DO_NOT_TOUCH=H1_H2_H3_H4_H5_H6_D11_PHYSICAL_RESULTS\n"
    )


print()
print("=== MANUSCRIPT PRIMARY VEF TABLE ===")

with main_table.open("r", encoding="utf-8") as f:
    for line in f:
        print(line.rstrip())

print()
print("=== CORE15 PAIR SUMMARY ===")

with pair_summary_path.open("r", encoding="utf-8") as f:
    for line in f:
        print(line.rstrip())

print()
print(
    f"POINTWISE_PATTERN="
    f"{point_pos}_POSITIVE_"
    f"{point_tie}_TIE_"
    f"{point_neg}_NEGATIVE"
)

print(
    f"CORE15_AUBC_PATTERN="
    f"{pair_pos}_POSITIVE_"
    f"{pair_tie}_TIE_"
    f"{pair_neg}_NEGATIVE"
)

print()
print("PASS=FROZEN_POINTWISE_96_69_0_REPRODUCED")
print("PASS=FROZEN_CORE15_10_5_0_REPRODUCED")
print("PASS=DETAILED_11_CAPACITY_TABLE_MATERIALIZED")

for path in targets:
    print(
        f"SHA256={sha256_file(path)}|FILE={path}"
    )

print()
print("DONE=D11_DETAILED_PRIMARY_TABLE")
print(
    "NEXT=INSPECT_NUMERIC_TABLE_AND_BIND_INTO_PAPER_BEFORE_AUTHORITY"
)
print(
    "DO_NOT_TOUCH=H1_H2_H3_H4_H5_H6_D11_PHYSICAL_RESULTS"
)
