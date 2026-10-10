#!/usr/bin/env python3

import csv
import hashlib
import json
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
    / "04_OUTPUTS/STEP4V2_VEF_MANUSCRIPT"
)

AUDIT = (
    ROOT
    / "06_AUDIT/STEP4V2_VEF_MANUSCRIPT"
)

OUT.mkdir(parents=True, exist_ok=True)
AUDIT.mkdir(parents=True, exist_ok=True)

EXPECTED_SOURCE_SHA = (
    "32d160166c3546f62b579f30e2e007e6213fb64596fca9b9ecb52f3b1bb83c53"
)

GRID = [
    5, 10, 20, 30, 40, 50,
    60, 70, 80, 90, 100,
]

CORE_METHODS = [
    "DECOUPLE",
    "H-only",
    "p-only",
    "Random",
    "Step-PRM",
    "PRM@BoK",
]

SPECIALIZED = "ToolPRM-GRPO"

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


def fail(msg):
    print(f"FAIL={msg}")
    raise RuntimeError(msg)


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


def normalized_full_auc(frontier):
    x = [
        b / 100.0
        for b in GRID
    ]

    area = 0.0

    for j in range(1, len(x)):
        area += (
            0.5
            * (
                frontier[j - 1]
                + frontier[j]
            )
            * (
                x[j]
                - x[j - 1]
            )
        )

    return (
        area
        / (
            x[-1]
            - x[0]
        )
    )


def build_curve(
    collapsed,
    benchmark,
    method,
    panel,
):
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

    return exact, frontier


print("CURRENT=ABSOLUTE_VEF_MANUSCRIPT_TABLES")
print(
    "D11_GRID="
    + ",".join(str(x) for x in GRID)
)
print("CELL_VALUE=ABSOLUTE_VERIFICATION_EFFICIENCY_FRONTIER")
print("SUMMARY_VALUE=FULL_VEF_AUBC_5_TO_100")
print("API_CALLS=0")
print("MODEL_RUNS=0")
print("PHYSICAL_REPLAY=0")
print()

if not SOURCE.exists():
    fail(
        f"MISSING_SOURCE={SOURCE}"
    )

source_sha = sha256(
    SOURCE
)

print(f"SOURCE={SOURCE}")
print(f"SOURCE_SHA256={source_sha}")

if source_sha != EXPECTED_SOURCE_SHA:
    fail(
        "FROZEN_D11_SOURCE_SHA_MISMATCH"
    )

print("PASS=SOURCE_AUTHORITY")

# ------------------------------------------------------------
# Collapse Random replicates within original
# benchmark-instance-budget.
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

        method = (
            row["method"]
            .strip()
        )

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

print(
    "COLLAPSED_INSTANCE_METHOD_BUDGET_ROWS="
    f"{len(collapsed)}"
)

# ============================================================
# CORE TABLES
# One joint matched panel per benchmark across all
# six core methods and all eleven budgets.
# ============================================================

core_rows = []
core_audit_rows = []

for benchmark in [
    "BFCL",
    "Math-Shepherd",
    "ToolAlpaca",
]:

    required_sets = []

    for method in CORE_METHODS:
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

    if not panel:
        fail(
            f"EMPTY_CORE_JOINT_PANEL={benchmark}"
        )

    frontiers = {}

    for method in CORE_METHODS:

        exact, frontier = build_curve(
            collapsed,
            benchmark,
            method,
            panel,
        )

        frontiers[
            method
        ] = frontier

        row = {
            "benchmark":
                benchmark,
            "method":
                method,
            "joint_panel_n":
                len(panel),
        }

        for j, budget in enumerate(
            GRID
        ):
            row[
                f"VEF_{budget}"
            ] = (
                f"{frontier[j]:.9f}"
            )

        row[
            "full_VEF_AUBC"
        ] = (
            f"{normalized_full_auc(frontier):.9f}"
        )

        core_rows.append(
            row
        )

    # Internal sign audit only.
    for baseline in CORE_METHODS:

        if baseline == "DECOUPLE":
            continue

        pos = 0
        tie = 0
        neg = 0

        for j in range(
            len(GRID)
        ):
            delta = (
                frontiers[
                    "DECOUPLE"
                ][j]
                -
                frontiers[
                    baseline
                ][j]
            )

            if delta > EPS:
                pos += 1
            elif delta < -EPS:
                neg += 1
            else:
                tie += 1

        core_audit_rows.append({
            "benchmark":
                benchmark,
            "baseline":
                baseline,
            "positive_caps":
                pos,
            "tie_caps":
                tie,
            "negative_caps":
                neg,
        })


# ============================================================
# SPECIALIZED TOOLPRM-GRPO TABLES
# Pair-specific matched panel because compatibility differs.
# ============================================================

special_rows = []
special_audit_rows = []

for benchmark in [
    "BFCL",
    "ToolAlpaca",
]:

    required_sets = []

    for method in [
        "DECOUPLE",
        SPECIALIZED,
    ]:
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

    if not panel:
        fail(
            f"EMPTY_SPECIALIZED_PANEL={benchmark}"
        )

    pair_frontiers = {}

    for method in [
        "DECOUPLE",
        SPECIALIZED,
    ]:

        exact, frontier = build_curve(
            collapsed,
            benchmark,
            method,
            panel,
        )

        pair_frontiers[
            method
        ] = frontier

        row = {
            "benchmark":
                benchmark,
            "method":
                method,
            "pair_panel_n":
                len(panel),
        }

        for j, budget in enumerate(
            GRID
        ):
            row[
                f"VEF_{budget}"
            ] = (
                f"{frontier[j]:.9f}"
            )

        row[
            "full_VEF_AUBC"
        ] = (
            f"{normalized_full_auc(frontier):.9f}"
        )

        special_rows.append(
            row
        )

    pos = 0
    tie = 0
    neg = 0

    for j in range(
        len(GRID)
    ):
        delta = (
            pair_frontiers[
                "DECOUPLE"
            ][j]
            -
            pair_frontiers[
                SPECIALIZED
            ][j]
        )

        if delta > EPS:
            pos += 1
        elif delta < -EPS:
            neg += 1
        else:
            tie += 1

    special_audit_rows.append({
        "benchmark":
            benchmark,
        "baseline":
            SPECIALIZED,
        "positive_caps":
            pos,
        "tie_caps":
            tie,
        "negative_caps":
            neg,
    })


# ============================================================
# Write persistent tables.
# ============================================================

core_path = (
    OUT
    / "MANUSCRIPT_CORE_ABSOLUTE_VEF.tsv"
)

special_path = (
    OUT
    / "MANUSCRIPT_SPECIALIZED_TOOLPRM_ABSOLUTE_VEF.tsv"
)

core_audit_path = (
    AUDIT
    / "MANUSCRIPT_CORE_ABSOLUTE_VEF_SIGN_AUDIT.tsv"
)

special_audit_path = (
    AUDIT
    / "MANUSCRIPT_SPECIALIZED_TOOLPRM_SIGN_AUDIT.tsv"
)

for path in [
    core_path,
    special_path,
    core_audit_path,
    special_audit_path,
]:
    if path.exists():
        fail(
            f"REFUSE_OVERWRITE={path}"
        )


with open(
    core_path,
    "w",
    encoding="utf-8",
    newline="",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=list(
            core_rows[0].keys()
        ),
        delimiter="\t",
    )

    writer.writeheader()
    writer.writerows(
        core_rows
    )


with open(
    special_path,
    "w",
    encoding="utf-8",
    newline="",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=list(
            special_rows[0].keys()
        ),
        delimiter="\t",
    )

    writer.writeheader()
    writer.writerows(
        special_rows
    )


with open(
    core_audit_path,
    "w",
    encoding="utf-8",
    newline="",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=list(
            core_audit_rows[0].keys()
        ),
        delimiter="\t",
    )

    writer.writeheader()
    writer.writerows(
        core_audit_rows
    )


with open(
    special_audit_path,
    "w",
    encoding="utf-8",
    newline="",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=list(
            special_audit_rows[0].keys()
        ),
        delimiter="\t",
    )

    writer.writeheader()
    writer.writerows(
        special_audit_rows
    )


# ============================================================
# Manuscript-style preview.
# ============================================================

for benchmark in [
    "BFCL",
    "Math-Shepherd",
    "ToolAlpaca",
]:

    rows = [
        r
        for r in core_rows
        if r["benchmark"]
        == benchmark
    ]

    print()
    print("=" * 135)
    print(
        f"{benchmark}: "
        "ABSOLUTE VERIFICATION EFFICIENCY FRONTIER"
    )
    print("=" * 135)

    header = (
        ["Method"]
        + [
            f"{b}%"
            for b in GRID
        ]
        + [
            "Full VEF-AUBC"
        ]
    )

    print(
        "\t".join(
            header
        )
    )

    for r in rows:

        vals = [
            f"{float(r[f'VEF_{b}']):.3f}"
            for b in GRID
        ]

        aubc = (
            f"{float(r['full_VEF_AUBC']):.3f}"
        )

        print(
            "\t".join(
                [r["method"]]
                + vals
                + [aubc]
            )
        )

    print(
        "JOINT_PANEL_N="
        f"{rows[0]['joint_panel_n']}"
    )


print()
print("=" * 135)
print(
    "SPECIALIZED TOOLPRM-GRPO PANEL"
)
print("=" * 135)

for benchmark in [
    "BFCL",
    "ToolAlpaca",
]:

    rows = [
        r
        for r in special_rows
        if r["benchmark"]
        == benchmark
    ]

    print()
    print(
        f"{benchmark}: "
        "ABSOLUTE VERIFICATION EFFICIENCY FRONTIER"
    )

    header = (
        ["Method"]
        + [
            f"{b}%"
            for b in GRID
        ]
        + [
            "Full VEF-AUBC"
        ]
    )

    print(
        "\t".join(
            header
        )
    )

    for r in rows:

        vals = [
            f"{float(r[f'VEF_{b}']):.3f}"
            for b in GRID
        ]

        aubc = (
            f"{float(r['full_VEF_AUBC']):.3f}"
        )

        print(
            "\t".join(
                [r["method"]]
                + vals
                + [aubc]
            )
        )

    print(
        "PAIR_PANEL_N="
        f"{rows[0]['pair_panel_n']}"
    )


# ============================================================
# Internal-only sign audit.
# ============================================================

print()
print(
    "=== INTERNAL CORE SIGN AUDIT "
    "(NOT MANUSCRIPT CONTENT) ==="
)

total_pos = 0
total_tie = 0
total_neg = 0

for r in core_audit_rows:

    total_pos += int(
        r["positive_caps"]
    )

    total_tie += int(
        r["tie_caps"]
    )

    total_neg += int(
        r["negative_caps"]
    )

    print(
        f"{r['benchmark']}|"
        f"{r['baseline']}|"
        f"POS={r['positive_caps']}|"
        f"TIE={r['tie_caps']}|"
        f"NEG={r['negative_caps']}"
    )

print(
    f"CORE_POSITIVE_CELLS="
    f"{total_pos}"
)

print(
    f"CORE_TIE_CELLS="
    f"{total_tie}"
)

print(
    f"CORE_NEGATIVE_CELLS="
    f"{total_neg}"
)

print(
    f"CORE_TOTAL_CELLS="
    f"{total_pos + total_tie + total_neg}"
)


print()
print(
    "=== INTERNAL SPECIALIZED SIGN AUDIT "
    "(NOT MANUSCRIPT CONTENT) ==="
)

for r in special_audit_rows:

    print(
        f"{r['benchmark']}|"
        f"{r['baseline']}|"
        f"POS={r['positive_caps']}|"
        f"TIE={r['tie_caps']}|"
        f"NEG={r['negative_caps']}"
    )


audit_obj = {
    "status":
        "PASS",

    "source_sha256":
        source_sha,

    "d11_grid":
        GRID,

    "core_methods":
        CORE_METHODS,

    "core_negative_cells":
        total_neg,

    "core_positive_cells":
        total_pos,

    "core_tie_cells":
        total_tie,

    "core_total_cells":
        total_pos
        + total_tie
        + total_neg,

    "outputs": {
        str(core_path):
            sha256(core_path),

        str(special_path):
            sha256(special_path),

        str(core_audit_path):
            sha256(core_audit_path),

        str(special_audit_path):
            sha256(special_audit_path),
    },
}

audit_json = (
    AUDIT
    / "MANUSCRIPT_ABSOLUTE_VEF_AUDIT.json"
)

if audit_json.exists():
    fail(
        f"REFUSE_OVERWRITE={audit_json}"
    )

with open(
    audit_json,
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        audit_obj,
        f,
        indent=2,
        sort_keys=True,
    )

    f.write("\n")


print()
print(f"CORE_TABLE={core_path}")
print(
    f"CORE_TABLE_SHA256="
    f"{sha256(core_path)}"
)

print(
    f"SPECIALIZED_TABLE="
    f"{special_path}"
)

print(
    f"SPECIALIZED_TABLE_SHA256="
    f"{sha256(special_path)}"
)

print(
    f"AUDIT_JSON="
    f"{audit_json}"
)

print(
    f"AUDIT_JSON_SHA256="
    f"{sha256(audit_json)}"
)

print()
print(
    "PASS=ABSOLUTE_VEF_MANUSCRIPT_TABLES"
)
print(
    "DONE=MANUSCRIPT_VEF_TABLE_PREVIEW"
)
print(
    "NEXT=REVIEW_GENERATED_VEF_TABLES"
)
print(
    "DO_NOT_TOUCH=FROZEN_D11_PHYSICAL_RESULTS"
)
