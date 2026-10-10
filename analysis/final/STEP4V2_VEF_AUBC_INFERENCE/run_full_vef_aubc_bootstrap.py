#!/usr/bin/env python3

import csv
import gzip
import hashlib
import json
import math
import random
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

CORE_TABLE = (
    ROOT
    / "04_OUTPUTS/STEP4V2_VEF_MANUSCRIPT"
    / "MANUSCRIPT_CORE_ABSOLUTE_VEF.tsv"
)

SPECIAL_TABLE = (
    ROOT
    / "04_OUTPUTS/STEP4V2_VEF_MANUSCRIPT"
    / "MANUSCRIPT_SPECIALIZED_TOOLPRM_ABSOLUTE_VEF.tsv"
)

OUT = (
    ROOT
    / "04_OUTPUTS/STEP4V2_VEF_AUBC_INFERENCE"
)

AUDIT = (
    ROOT
    / "06_AUDIT/STEP4V2_VEF_AUBC_INFERENCE"
)

OUT.mkdir(parents=True, exist_ok=True)
AUDIT.mkdir(parents=True, exist_ok=True)

EXPECTED_SOURCE_SHA = (
    "32d160166c3546f62b579f30e2e007e6213fb64596fca9b9ecb52f3b1bb83c53"
)

EXPECTED_CORE_TABLE_SHA = (
    "69d50c0e1fce8184701babc68634b101cfb51acb4ebbd9952e2c851452e78b44"
)

EXPECTED_SPECIAL_TABLE_SHA = (
    "ed8756b9d5b08b647c8a8d1a1423ffd074d4865cd2bc3322ea24fd029ef58e71"
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

CORE_BASELINES = [
    "H-only",
    "p-only",
    "Random",
    "Step-PRM",
    "PRM@BoK",
]

SPECIALIZED = "ToolPRM-GRPO"

BOOTSTRAP_REPLICATES = 10000
BOOTSTRAP_SEED = 20260929

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


def full_normalized_vef_aubc(frontier):
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


def percentile(values, q):
    vals = sorted(values)

    if not vals:
        fail("EMPTY_PERCENTILE_INPUT")

    if len(vals) == 1:
        return vals[0]

    pos = (
        (len(vals) - 1)
        * q
    )

    lo = int(
        math.floor(pos)
    )

    hi = int(
        math.ceil(pos)
    )

    if lo == hi:
        return vals[lo]

    frac = (
        pos - lo
    )

    return (
        vals[lo]
        * (1.0 - frac)
        +
        vals[hi]
        * frac
    )


def build_utility_curve(
    collapsed,
    benchmark,
    method,
    sampled_ids,
):
    curve = []

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
            for iid in sampled_ids
        ]

        curve.append(
            mean(vals)
        )

    return curve


def compute_vef_aubc(
    collapsed,
    benchmark,
    method,
    sampled_ids,
):
    utility = build_utility_curve(
        collapsed,
        benchmark,
        method,
        sampled_ids,
    )

    frontier = cumulative_max(
        utility
    )

    return full_normalized_vef_aubc(
        frontier
    )


print("CURRENT=FULL_VEF_AUBC_PAIRED_BOOTSTRAP")
print(
    "D11_GRID="
    + ",".join(str(x) for x in GRID)
)
print(
    f"BOOTSTRAP_REPLICATES="
    f"{BOOTSTRAP_REPLICATES}"
)
print(
    f"BOOTSTRAP_SEED="
    f"{BOOTSTRAP_SEED}"
)
print(
    "BOOTSTRAP_CLUSTER="
    "original_benchmark_instance"
)
print("API_CALLS=0")
print("MODEL_RUNS=0")
print("PHYSICAL_REPLAY=0")
print("METHOD_RETUNING=NO")
print()

# ------------------------------------------------------------
# Authority checks.
# ------------------------------------------------------------

for path, expected in [
    (
        SOURCE,
        EXPECTED_SOURCE_SHA,
    ),
    (
        CORE_TABLE,
        EXPECTED_CORE_TABLE_SHA,
    ),
    (
        SPECIAL_TABLE,
        EXPECTED_SPECIAL_TABLE_SHA,
    ),
]:

    if not path.exists():
        fail(
            f"MISSING_AUTHORITY={path}"
        )

    actual = sha256(
        path
    )

    print(
        f"AUTHORITY={path}"
    )

    print(
        f"SHA256={actual}"
    )

    if actual != expected:
        fail(
            "AUTHORITY_SHA_MISMATCH="
            f"{path}|"
            f"EXPECTED={expected}|"
            f"ACTUAL={actual}"
        )

print(
    "PASS=ALL_AUTHORITY_HASHES"
)

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

# ------------------------------------------------------------
# Load manuscript table values for exact reconstruction.
# ------------------------------------------------------------

core_observed_authority = {}

with open(
    CORE_TABLE,
    "r",
    encoding="utf-8",
    newline="",
) as f:

    reader = csv.DictReader(
        f,
        delimiter="\t",
    )

    for row in reader:

        core_observed_authority[
            (
                row["benchmark"],
                row["method"],
            )
        ] = float(
            row[
                "full_VEF_AUBC"
            ]
        )


special_observed_authority = {}

with open(
    SPECIAL_TABLE,
    "r",
    encoding="utf-8",
    newline="",
) as f:

    reader = csv.DictReader(
        f,
        delimiter="\t",
    )

    for row in reader:

        special_observed_authority[
            (
                row["benchmark"],
                row["method"],
            )
        ] = float(
            row[
                "full_VEF_AUBC"
            ]
        )


core_summary = []
special_summary = []
draw_rows = []

# ============================================================
# CORE ANALYSIS
# Same joint panel per benchmark across all six core methods.
# Same bootstrap resample is used for every method inside a
# benchmark on a given draw.
# ============================================================

for benchmark_index, benchmark in enumerate(
    [
        "BFCL",
        "Math-Shepherd",
        "ToolAlpaca",
    ]
):

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

    if len(panel) < 2:
        fail(
            f"INSUFFICIENT_CORE_PANEL={benchmark}"
        )

    # --------------------------------------------------------
    # Reconstruct observed values.
    # --------------------------------------------------------

    observed = {}

    for method in CORE_METHODS:

        observed[
            method
        ] = compute_vef_aubc(
            collapsed,
            benchmark,
            method,
            panel,
        )

        authority = (
            core_observed_authority[
                (
                    benchmark,
                    method,
                )
            ]
        )

        if abs(
            observed[method]
            - authority
        ) > 1e-8:

            fail(
                "CORE_OBSERVED_RECON_MISMATCH="
                f"{benchmark}|{method}|"
                f"RECON={observed[method]}|"
                f"AUTHORITY={authority}"
            )

    print()
    print(
        f"BENCHMARK={benchmark}|"
        f"JOINT_PANEL_N={len(panel)}"
    )

    # --------------------------------------------------------
    # Draw bootstrap samples once per benchmark.
    # --------------------------------------------------------

    rng = random.Random(
        BOOTSTRAP_SEED
        + benchmark_index
    )

    pair_draws = {
        baseline: []
        for baseline in CORE_BASELINES
    }

    for draw in range(
        1,
        BOOTSTRAP_REPLICATES + 1,
    ):

        sampled_ids = [
            panel[
                rng.randrange(
                    len(panel)
                )
            ]
            for _ in range(
                len(panel)
            )
        ]

        boot_values = {}

        for method in CORE_METHODS:

            boot_values[
                method
            ] = compute_vef_aubc(
                collapsed,
                benchmark,
                method,
                sampled_ids,
            )

        for baseline in CORE_BASELINES:

            delta = (
                boot_values[
                    "DECOUPLE"
                ]
                -
                boot_values[
                    baseline
                ]
            )

            pair_draws[
                baseline
            ].append(
                delta
            )

            draw_rows.append({
                "comparator_class":
                    "CROSS_DOMAIN_CORE",

                "benchmark":
                    benchmark,

                "baseline":
                    baseline,

                "bootstrap_draw":
                    draw,

                "matched_instance_n":
                    len(panel),

                "VEF_AUBC_delta":
                    f"{delta:.9f}",
            })

    # --------------------------------------------------------
    # Pair summaries.
    # --------------------------------------------------------

    for baseline in CORE_BASELINES:

        observed_delta = (
            observed[
                "DECOUPLE"
            ]
            -
            observed[
                baseline
            ]
        )

        vals = pair_draws[
            baseline
        ]

        ci_low = percentile(
            vals,
            0.025,
        )

        ci_high = percentile(
            vals,
            0.975,
        )

        lower_one_sided = percentile(
            vals,
            0.05,
        )

        p_ge_zero = (
            sum(
                x >= -EPS
                for x in vals
            )
            / len(vals)
        )

        p_gt_zero = (
            sum(
                x > EPS
                for x in vals
            )
            / len(vals)
        )

        core_summary.append({
            "benchmark":
                benchmark,

            "baseline":
                baseline,

            "joint_panel_n":
                len(panel),

            "DE_full_VEF_AUBC":
                f"{observed['DECOUPLE']:.9f}",

            "baseline_full_VEF_AUBC":
                f"{observed[baseline]:.9f}",

            "observed_delta":
                f"{observed_delta:.9f}",

            "bootstrap_ci95_low":
                f"{ci_low:.9f}",

            "bootstrap_ci95_high":
                f"{ci_high:.9f}",

            "bootstrap_lower95_one_sided":
                f"{lower_one_sided:.9f}",

            "bootstrap_prob_delta_ge_0":
                f"{p_ge_zero:.9f}",

            "bootstrap_prob_delta_gt_0":
                f"{p_gt_zero:.9f}",

            "bootstrap_replicates":
                BOOTSTRAP_REPLICATES,

            "bootstrap_seed":
                BOOTSTRAP_SEED
                + benchmark_index,
        })

# ============================================================
# SPECIALIZED TOOLPRM-GRPO
# Pair-specific panel.
# ============================================================

for benchmark_index, benchmark in enumerate(
    [
        "BFCL",
        "ToolAlpaca",
    ]
):

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

    if len(panel) < 2:
        fail(
            f"INSUFFICIENT_SPECIALIZED_PANEL={benchmark}"
        )

    observed_de = compute_vef_aubc(
        collapsed,
        benchmark,
        "DECOUPLE",
        panel,
    )

    observed_bl = compute_vef_aubc(
        collapsed,
        benchmark,
        SPECIALIZED,
        panel,
    )

    for method, value in [
        (
            "DECOUPLE",
            observed_de,
        ),
        (
            SPECIALIZED,
            observed_bl,
        ),
    ]:

        authority = (
            special_observed_authority[
                (
                    benchmark,
                    method,
                )
            ]
        )

        if abs(
            value
            - authority
        ) > 1e-8:

            fail(
                "SPECIAL_OBSERVED_RECON_MISMATCH="
                f"{benchmark}|{method}|"
                f"RECON={value}|"
                f"AUTHORITY={authority}"
            )

    rng = random.Random(
        BOOTSTRAP_SEED
        + 100
        + benchmark_index
    )

    vals = []

    for draw in range(
        1,
        BOOTSTRAP_REPLICATES + 1,
    ):

        sampled_ids = [
            panel[
                rng.randrange(
                    len(panel)
                )
            ]
            for _ in range(
                len(panel)
            )
        ]

        de = compute_vef_aubc(
            collapsed,
            benchmark,
            "DECOUPLE",
            sampled_ids,
        )

        bl = compute_vef_aubc(
            collapsed,
            benchmark,
            SPECIALIZED,
            sampled_ids,
        )

        delta = (
            de - bl
        )

        vals.append(
            delta
        )

        draw_rows.append({
            "comparator_class":
                "TOOL_SPECIALIZED",

            "benchmark":
                benchmark,

            "baseline":
                SPECIALIZED,

            "bootstrap_draw":
                draw,

            "matched_instance_n":
                len(panel),

            "VEF_AUBC_delta":
                f"{delta:.9f}",
        })

    observed_delta = (
        observed_de
        - observed_bl
    )

    ci_low = percentile(
        vals,
        0.025,
    )

    ci_high = percentile(
        vals,
        0.975,
    )

    lower_one_sided = percentile(
        vals,
        0.05,
    )

    p_ge_zero = (
        sum(
            x >= -EPS
            for x in vals
        )
        / len(vals)
    )

    p_gt_zero = (
        sum(
            x > EPS
            for x in vals
        )
        / len(vals)
    )

    special_summary.append({
        "benchmark":
            benchmark,

        "baseline":
            SPECIALIZED,

        "pair_panel_n":
            len(panel),

        "DE_full_VEF_AUBC":
            f"{observed_de:.9f}",

        "baseline_full_VEF_AUBC":
            f"{observed_bl:.9f}",

        "observed_delta":
            f"{observed_delta:.9f}",

        "bootstrap_ci95_low":
            f"{ci_low:.9f}",

        "bootstrap_ci95_high":
            f"{ci_high:.9f}",

        "bootstrap_lower95_one_sided":
            f"{lower_one_sided:.9f}",

        "bootstrap_prob_delta_ge_0":
            f"{p_ge_zero:.9f}",

        "bootstrap_prob_delta_gt_0":
            f"{p_gt_zero:.9f}",

        "bootstrap_replicates":
            BOOTSTRAP_REPLICATES,

        "bootstrap_seed":
            BOOTSTRAP_SEED
            + 100
            + benchmark_index,
    })


# ============================================================
# Persist.
# ============================================================

core_path = (
    OUT
    / "FULL_VEF_AUBC_BOOTSTRAP_CORE_15.tsv"
)

special_path = (
    OUT
    / "FULL_VEF_AUBC_BOOTSTRAP_SPECIALIZED_2.tsv"
)

draws_path = (
    OUT
    / "FULL_VEF_AUBC_BOOTSTRAP_DRAWS.tsv.gz"
)

for path in [
    core_path,
    special_path,
    draws_path,
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
            core_summary[0].keys()
        ),
        delimiter="\t",
    )

    writer.writeheader()
    writer.writerows(
        core_summary
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
            special_summary[0].keys()
        ),
        delimiter="\t",
    )

    writer.writeheader()
    writer.writerows(
        special_summary
    )


with gzip.open(
    draws_path,
    "wt",
    encoding="utf-8",
    newline="",
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=list(
            draw_rows[0].keys()
        ),
        delimiter="\t",
    )

    writer.writeheader()
    writer.writerows(
        draw_rows
    )


# ============================================================
# Compact terminal output.
# ============================================================

print()
print(
    "=== CORE FULL VEF-AUBC BOOTSTRAP ==="
)

for r in core_summary:

    print(
        f"{r['benchmark']}|"
        f"{r['baseline']}|"
        f"DE={r['DE_full_VEF_AUBC']}|"
        f"BASE={r['baseline_full_VEF_AUBC']}|"
        f"DELTA={r['observed_delta']}|"
        f"CI95=["
        f"{r['bootstrap_ci95_low']},"
        f"{r['bootstrap_ci95_high']}]|"
        f"P_BOOT_GE0="
        f"{r['bootstrap_prob_delta_ge_0']}"
    )


print()
print(
    "=== SPECIALIZED FULL VEF-AUBC BOOTSTRAP ==="
)

for r in special_summary:

    print(
        f"{r['benchmark']}|"
        f"{r['baseline']}|"
        f"DE={r['DE_full_VEF_AUBC']}|"
        f"BASE={r['baseline_full_VEF_AUBC']}|"
        f"DELTA={r['observed_delta']}|"
        f"CI95=["
        f"{r['bootstrap_ci95_low']},"
        f"{r['bootstrap_ci95_high']}]|"
        f"P_BOOT_GE0="
        f"{r['bootstrap_prob_delta_ge_0']}"
    )


# ============================================================
# Simple descriptive counts.
# ============================================================

pos = sum(
    float(
        r["observed_delta"]
    ) > EPS
    for r in core_summary
)

tie = sum(
    abs(
        float(
            r["observed_delta"]
        )
    ) <= EPS
    for r in core_summary
)

neg = sum(
    float(
        r["observed_delta"]
    ) < -EPS
    for r in core_summary
)

ci_positive = sum(
    float(
        r["bootstrap_ci95_low"]
    ) > EPS
    for r in core_summary
)

ci_nonnegative = sum(
    float(
        r["bootstrap_ci95_low"]
    ) >= -EPS
    for r in core_summary
)

print()
print(
    "=== CORE DESCRIPTIVE SUMMARY ==="
)

print(
    f"CORE_PAIR_COUNT="
    f"{len(core_summary)}"
)

print(
    f"OBSERVED_POSITIVE="
    f"{pos}"
)

print(
    f"OBSERVED_TIE="
    f"{tie}"
)

print(
    f"OBSERVED_NEGATIVE="
    f"{neg}"
)

print(
    f"CI95_STRICT_POSITIVE="
    f"{ci_positive}"
)

print(
    f"CI95_NONNEGATIVE="
    f"{ci_nonnegative}"
)


# ============================================================
# Audit JSON.
# ============================================================

audit_obj = {
    "status":
        "PASS",

    "analysis":
        "FULL_VEF_AUBC_PAIRED_CLUSTER_BOOTSTRAP",

    "metric":
        "NORMALIZED_LINEAR_AREA_UNDER_VERIFICATION_EFFICIENCY_FRONTIER_5_TO_100",

    "api_calls":
        0,

    "model_runs":
        0,

    "physical_replay":
        0,

    "method_retuning":
        False,

    "d11_grid":
        GRID,

    "bootstrap_replicates":
        BOOTSTRAP_REPLICATES,

    "bootstrap_seed":
        BOOTSTRAP_SEED,

    "bootstrap_cluster":
        "original_benchmark_instance",

    "bootstrap_probability_is_pvalue":
        False,

    "source_sha256":
        sha256(SOURCE),

    "core_table_sha256":
        sha256(CORE_TABLE),

    "special_table_sha256":
        sha256(SPECIAL_TABLE),

    "core_pair_count":
        len(core_summary),

    "core_observed_positive":
        pos,

    "core_observed_tie":
        tie,

    "core_observed_negative":
        neg,

    "core_ci95_strict_positive":
        ci_positive,

    "core_ci95_nonnegative":
        ci_nonnegative,

    "outputs": {
        str(core_path):
            sha256(core_path),

        str(special_path):
            sha256(special_path),

        str(draws_path):
            sha256(draws_path),
    },
}

audit_path = (
    AUDIT
    / "FULL_VEF_AUBC_BOOTSTRAP_AUDIT.json"
)

if audit_path.exists():
    fail(
        f"REFUSE_OVERWRITE={audit_path}"
    )


with open(
    audit_path,
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
print(
    f"CORE_OUTPUT={core_path}"
)

print(
    f"CORE_OUTPUT_SHA256="
    f"{sha256(core_path)}"
)

print(
    f"SPECIAL_OUTPUT={special_path}"
)

print(
    f"SPECIAL_OUTPUT_SHA256="
    f"{sha256(special_path)}"
)

print(
    f"DRAWS={draws_path}"
)

print(
    f"DRAWS_SHA256="
    f"{sha256(draws_path)}"
)

print(
    f"AUDIT={audit_path}"
)

print(
    f"AUDIT_SHA256="
    f"{sha256(audit_path)}"
)

print()
print(
    "PASS=FULL_VEF_AUBC_PAIRED_BOOTSTRAP"
)

print(
    "DONE=VEF_AUBC_STATISTICAL_VALIDATION"
)

print(
    "NEXT=REVIEW_GENERATED_BOOTSTRAP_TABLES"
)

print(
    "DO_NOT_TOUCH=FROZEN_D11_PHYSICAL_RESULTS"
)
