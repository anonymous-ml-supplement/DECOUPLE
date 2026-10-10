#!/usr/bin/env python3

import csv
import hashlib
from collections import defaultdict
from pathlib import Path

ROOT = Path(
    "__DECOUPLE_ROOT__/10_PILOT/STEP4_V2_CLEAN_REBUILD"
)

SOURCE = (
    ROOT
    / "04_OUTPUTS/STEP4V2_D11_FINAL_RANDOM_AWARE_ANALYSIS"
    / "D11_FINAL_ALL_LOGICAL_RESULTS.tsv"
)

OUT = (
    ROOT
    / "04_OUTPUTS/STEP4V2_VEF_SATURATION_AUDIT"
)

EXPECTED_SHA = (
    "32d160166c3546f62b579f30e2e007e6213fb64596fca9b9ecb52f3b1bb83c53"
)

GRID = [
    5, 10, 20, 30, 40, 50,
    60, 70, 80, 90, 100,
]

METHODS = [
    "DECOUPLE",
    "H-only",
    "p-only",
    "Random",
    "Step-PRM",
    "PRM@BoK",
]

EPS = 1e-12


def sha256(path):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def mean(xs):
    return sum(xs) / len(xs)


def pct(x):
    v = float(x)

    if v <= 1.0 + EPS:
        v *= 100.0

    return int(round(v))


def norm_benchmark(x):
    y = (
        str(x)
        .strip()
        .upper()
        .replace("-", "_")
        .replace(" ", "_")
    )

    if y == "BFCL":
        return "BFCL"

    if y == "MATH_SHEPHERD":
        return "Math-Shepherd"

    if y == "TOOLALPACA":
        return "ToolAlpaca"

    return str(x).strip()


def cumulative_max(xs):
    out = []
    cur = None

    for x in xs:
        if cur is None or x > cur:
            cur = x

        out.append(cur)

    return out


print("CURRENT=EXACT_VS_VEF_SATURATION_AUDIT")
print("API_CALLS=0")
print("MODEL_RUNS=0")
print("PHYSICAL_REPLAY=0")
print("D11_GRID=" + ",".join(str(x) for x in GRID))
print()

source_sha = sha256(SOURCE)

print(f"SOURCE={SOURCE}")
print(f"SOURCE_SHA256={source_sha}")

if source_sha != EXPECTED_SHA:
    raise RuntimeError("SOURCE_SHA_MISMATCH")

# ------------------------------------------------------------
# Collapse Random replicates.
# ------------------------------------------------------------

raw = defaultdict(list)

with open(
    SOURCE,
    "r",
    encoding="utf-8",
    newline="",
) as f:

    reader = csv.DictReader(
        f,
        delimiter="\t",
    )

    for row in reader:

        benchmark = norm_benchmark(
            row["benchmark"]
        )

        method = row[
            "method"
        ].strip()

        if method not in METHODS:
            continue

        budget = pct(
            row["budget"]
        )

        if budget not in GRID:
            continue

        iid = row[
            "instance_id"
        ]

        z = float(
            row["terminal_Z"]
        )

        raw[
            (
                benchmark,
                method,
                budget,
                iid,
            )
        ].append(z)


collapsed = {
    key: mean(vals)
    for key, vals in raw.items()
}


audit_rows = []

for benchmark in [
    "BFCL",
    "Math-Shepherd",
    "ToolAlpaca",
]:

    # Same joint core panel used by manuscript preview.
    required_sets = []

    for method in METHODS:
        for budget in GRID:

            ids = {
                iid
                for (
                    b,
                    m,
                    bb,
                    iid,
                ) in collapsed
                if b == benchmark
                and m == method
                and bb == budget
            }

            required_sets.append(
                ids
            )

    panel = sorted(
        set.intersection(
            *required_sets
        )
    )

    print()
    print("=" * 125)
    print(
        f"{benchmark}: EXACT UTILITY VS VEF"
    )
    print("=" * 125)

    print(
        "Method\t"
        + "\t".join(
            f"E{b}"
            for b in GRID
        )
    )

    method_curves = {}

    for method in METHODS:

        exact = []

        for budget in GRID:

            vals = [
                collapsed[
                    (
                        benchmark,
                        method,
                        budget,
                        iid,
                    )
                ]
                for iid in panel
            ]

            exact.append(
                mean(vals)
            )

        frontier = cumulative_max(
            exact
        )

        method_curves[
            method
        ] = (
            exact,
            frontier,
        )

        global_max = max(exact)

        first_max_index = next(
            i
            for i, x in enumerate(exact)
            if abs(
                x - global_max
            ) <= EPS
        )

        first_max_budget = GRID[
            first_max_index
        ]

        exact_unique = len(
            {
                round(x, 12)
                for x in exact
            }
        )

        vef_unique = len(
            {
                round(x, 12)
                for x in frontier
            }
        )

        print(
            method
            + "\t"
            + "\t".join(
                f"{x:.3f}"
                for x in exact
            )
        )

        print(
            "VEF"
            + "\t"
            + "\t".join(
                f"{x:.3f}"
                for x in frontier
            )
        )

        print(
            f"META\tMETHOD={method}|"
            f"GLOBAL_MAX={global_max:.3f}|"
            f"FIRST_MAX_BUDGET={first_max_budget}|"
            f"EXACT_UNIQUE={exact_unique}|"
            f"VEF_UNIQUE={vef_unique}"
        )

        audit_rows.append({
            "benchmark":
                benchmark,
            "method":
                method,
            "joint_panel_n":
                len(panel),
            "global_max":
                f"{global_max:.9f}",
            "first_max_budget_pct":
                first_max_budget,
            "exact_unique_values":
                exact_unique,
            "vef_unique_values":
                vef_unique,
            "vef_flat_from_5pct":
                int(
                    vef_unique == 1
                ),
        })


out_path = (
    OUT
    / "EXACT_VS_VEF_SATURATION_AUDIT.tsv"
)

if out_path.exists():
    raise RuntimeError(
        f"REFUSE_OVERWRITE={out_path}"
    )

with open(
    out_path,
    "w",
    encoding="utf-8",
    newline="",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=list(
            audit_rows[0].keys()
        ),
        delimiter="\t",
    )

    writer.writeheader()
    writer.writerows(
        audit_rows
    )


print()
print("=== SATURATION SUMMARY ===")

for benchmark in [
    "BFCL",
    "Math-Shepherd",
    "ToolAlpaca",
]:

    rows = [
        r
        for r in audit_rows
        if r["benchmark"]
        == benchmark
    ]

    flat = sum(
        int(
            r["vef_flat_from_5pct"]
        )
        for r in rows
    )

    first5 = sum(
        int(
            r["first_max_budget_pct"]
        ) == 5
        for r in rows
    )

    print(
        f"{benchmark}|"
        f"METHODS={len(rows)}|"
        f"FIRST_GLOBAL_MAX_AT_5={first5}|"
        f"VEF_FLAT_FROM_5={flat}"
    )


print()
print(f"OUTPUT={out_path}")
print(
    f"OUTPUT_SHA256="
    f"{sha256(out_path)}"
)

print()
print("PASS=EXACT_VS_VEF_SATURATION_AUDIT")
print("DONE=VEF_SATURATION_DIAGNOSIS")
print("NEXT=DECIDE_IF_VEF_IS_INFORMATIVE_ENOUGH_FOR_MAIN_RESULT")
print("DO_NOT_TOUCH=FROZEN_D11_PHYSICAL_RESULTS")
