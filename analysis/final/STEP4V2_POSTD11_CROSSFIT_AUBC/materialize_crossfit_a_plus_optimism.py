#!/usr/bin/env python3

import csv
import hashlib
import json
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(
    "__DECOUPLE_ROOT__/10_PILOT/STEP4_V2_CLEAN_REBUILD"
)

SOURCE = (
    ROOT
    / "04_OUTPUTS/STEP4V2_VEF_AUDIT/"
      "VEF_V1_FULL_11_CAP_CURVES_187.tsv"
)

OUT_DIR = ROOT / "04_OUTPUTS/STEP4V2_POSTD11_CROSSFIT_AUBC"
AUDIT_DIR = ROOT / "06_AUDIT/STEP4V2_POSTD11_CROSSFIT_AUBC"

PAIR_OUT = OUT_DIR / "CROSSFIT_A_PLUS_PAIR_OPTIMISM_17.tsv"
CORE_OUT = OUT_DIR / "CROSSFIT_A_PLUS_CORE15.tsv"
SPECIAL_OUT = OUT_DIR / "CROSSFIT_A_PLUS_SPECIALIZED_TOOLPRM.tsv"
AUDIT = AUDIT_DIR / "01_CROSSFIT_A_PLUS_OPTIMISM_AUDIT.json"

GRID = [5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
CORE_BASELINES = {
    "H-only",
    "p-only",
    "Random",
    "Step-PRM",
    "PRM@BoK",
}

SPECIALIZED = "ToolPRM-GRPO"

EPS = 1e-12


def fail(msg):
    print(f"FAIL={msg}")
    raise SystemExit(1)


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def linear_aubc(values):
    if len(values) != len(GRID):
        fail(f"AUBC_GRID_LENGTH={len(values)}")

    xs = [b / 100.0 for b in GRID]

    area = 0.0
    for i in range(len(xs) - 1):
        dx = xs[i + 1] - xs[i]
        area += dx * (values[i] + values[i + 1]) / 2.0

    width = xs[-1] - xs[0]

    if width <= 0:
        fail("INVALID_AUBC_WIDTH")

    return area / width


def direction(x):
    if x > EPS:
        return "POSITIVE"
    if x < -EPS:
        return "NEGATIVE"
    return "TIE"


if not SOURCE.exists():
    fail(f"MISSING_SOURCE={SOURCE}")


# ------------------------------------------------------------
# Load frozen 187-row authority.
# ------------------------------------------------------------
with SOURCE.open("r", encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f, delimiter="\t"))

if len(rows) != 187:
    fail(f"SOURCE_ROW_COUNT={len(rows)}_EXPECTED=187")

required = {
    "benchmark",
    "baseline",
    "matched_instance_n",
    "budget_cap_pct",
    "DE_VEF",
    "baseline_VEF",
    "VEF_delta",
    "CF_DE_utility",
    "CF_baseline_utility",
    "CF_delta",
    "CF_DE_mean_selected_budget_pct",
    "CF_baseline_mean_selected_budget_pct",
}

if not required.issubset(set(rows[0].keys())):
    fail("SOURCE_SCHEMA_MISMATCH")


grouped = defaultdict(list)

for row in rows:
    key = (row["benchmark"], row["baseline"])
    grouped[key].append(row)

if len(grouped) != 17:
    fail(f"PAIR_COUNT={len(grouped)}_EXPECTED=17")


# ------------------------------------------------------------
# Materialize pair-level A+ values.
# ------------------------------------------------------------
pair_rows = []

for (benchmark, baseline), grows in sorted(grouped.items()):
    grows = sorted(
        grows,
        key=lambda r: float(r["budget_cap_pct"]),
    )

    budgets = [
        int(round(float(r["budget_cap_pct"])))
        for r in grows
    ]

    if budgets != GRID:
        fail(
            f"GRID_MISMATCH:{benchmark}:{baseline}:"
            f"{budgets}"
        )

    n_values = {
        int(r["matched_instance_n"])
        for r in grows
    }

    if len(n_values) != 1:
        fail(
            f"MATCHED_N_NOT_CONSTANT:"
            f"{benchmark}:{baseline}"
        )

    matched_n = next(iter(n_values))

    de_emp_curve = [
        float(r["DE_VEF"])
        for r in grows
    ]
    bl_emp_curve = [
        float(r["baseline_VEF"])
        for r in grows
    ]

    de_cf_curve = [
        float(r["CF_DE_utility"])
        for r in grows
    ]
    bl_cf_curve = [
        float(r["CF_baseline_utility"])
        for r in grows
    ]

    emp_delta_curve = [
        float(r["VEF_delta"])
        for r in grows
    ]
    cf_delta_curve = [
        float(r["CF_delta"])
        for r in grows
    ]

    # Sanity: stored deltas must equal stored utility differences.
    for j in range(len(GRID)):
        if abs(
            (de_emp_curve[j] - bl_emp_curve[j])
            - emp_delta_curve[j]
        ) > 2e-9:
            fail(
                f"EMP_DELTA_MISMATCH:"
                f"{benchmark}:{baseline}:{GRID[j]}"
            )

        if abs(
            (de_cf_curve[j] - bl_cf_curve[j])
            - cf_delta_curve[j]
        ) > 2e-9:
            fail(
                f"CF_DELTA_MISMATCH:"
                f"{benchmark}:{baseline}:{GRID[j]}"
            )

    de_emp_a = linear_aubc(de_emp_curve)
    bl_emp_a = linear_aubc(bl_emp_curve)

    de_cf_a = linear_aubc(de_cf_curve)
    bl_cf_a = linear_aubc(bl_cf_curve)

    emp_delta_a = de_emp_a - bl_emp_a
    cf_delta_a = de_cf_a - bl_cf_a

    # Equivalent direct integration check.
    emp_delta_direct = linear_aubc(emp_delta_curve)
    cf_delta_direct = linear_aubc(cf_delta_curve)

    if abs(emp_delta_a - emp_delta_direct) > 2e-9:
        fail(
            f"EMP_AUBC_LINEARITY_FAIL:"
            f"{benchmark}:{baseline}"
        )

    if abs(cf_delta_a - cf_delta_direct) > 2e-9:
        fail(
            f"CF_AUBC_LINEARITY_FAIL:"
            f"{benchmark}:{baseline}"
        )

    de_optimism = de_emp_a - de_cf_a
    bl_optimism = bl_emp_a - bl_cf_a

    # How much of pairwise apparent advantage is reduced/increased
    # when moving from empirical envelope to cross-fitted selector.
    delta_optimism = emp_delta_a - cf_delta_a

    cf_neg_caps = sum(
        x < -EPS
        for x in cf_delta_curve
    )

    cf_tie_caps = sum(
        abs(x) <= EPS
        for x in cf_delta_curve
    )

    cf_pos_caps = sum(
        x > EPS
        for x in cf_delta_curve
    )

    cf_nonloss11 = int(cf_neg_caps == 0)

    family = (
        "CORE15"
        if baseline in CORE_BASELINES
        else "SPECIALIZED_TOOLPRM"
        if baseline == SPECIALIZED
        else "UNKNOWN"
    )

    if family == "UNKNOWN":
        fail(f"UNKNOWN_BASELINE_FAMILY={baseline}")

    pair_rows.append({
        "benchmark": benchmark,
        "baseline": baseline,
        "family": family,
        "matched_instance_n": matched_n,

        "empirical_DE_A_plus": de_emp_a,
        "crossfit_DE_A_plus": de_cf_a,
        "DE_empirical_minus_crossfit": de_optimism,

        "empirical_baseline_A_plus": bl_emp_a,
        "crossfit_baseline_A_plus": bl_cf_a,
        "baseline_empirical_minus_crossfit": bl_optimism,

        "empirical_pair_delta_A_plus": emp_delta_a,
        "crossfit_pair_delta_A_plus": cf_delta_a,
        "pair_delta_empirical_minus_crossfit":
            delta_optimism,

        "empirical_pair_direction":
            direction(emp_delta_a),
        "crossfit_pair_direction":
            direction(cf_delta_a),

        "CF_nonloss_all_11": cf_nonloss11,
        "CF_positive_caps": cf_pos_caps,
        "CF_tie_caps": cf_tie_caps,
        "CF_negative_caps": cf_neg_caps,
        "CF_worst_cap_margin": min(cf_delta_curve),
    })


# ------------------------------------------------------------
# Frozen cross-fit sanity target: 12 / 17 nonloss-all-11.
# ------------------------------------------------------------
cf_nonloss_17 = sum(
    int(r["CF_nonloss_all_11"])
    for r in pair_rows
)

if cf_nonloss_17 != 12:
    fail(
        f"FROZEN_CROSSFIT_SANITY_MISMATCH="
        f"{cf_nonloss_17}_OF_17_EXPECTED_12_OF_17"
    )


core_rows = [
    r for r in pair_rows
    if r["family"] == "CORE15"
]

special_rows = [
    r for r in pair_rows
    if r["family"] == "SPECIALIZED_TOOLPRM"
]

if len(core_rows) != 15:
    fail(f"CORE_ROW_COUNT={len(core_rows)}_EXPECTED=15")

if len(special_rows) != 2:
    fail(
        f"SPECIALIZED_ROW_COUNT={len(special_rows)}_EXPECTED=2"
    )


# ------------------------------------------------------------
# Summaries.
# ------------------------------------------------------------
emp_core_dirs = Counter(
    r["empirical_pair_direction"]
    for r in core_rows
)

cf_core_dirs = Counter(
    r["crossfit_pair_direction"]
    for r in core_rows
)

core_direction_changes = sum(
    r["empirical_pair_direction"]
    != r["crossfit_pair_direction"]
    for r in core_rows
)

core_cf_negative_pairs = [
    f"{r['benchmark']}|{r['baseline']}"
    for r in core_rows
    if r["crossfit_pair_direction"] == "NEGATIVE"
]

core_cf_nonloss11 = sum(
    int(r["CF_nonloss_all_11"])
    for r in core_rows
)


# ------------------------------------------------------------
# Write outputs.
# ------------------------------------------------------------
fields = [
    "benchmark",
    "baseline",
    "family",
    "matched_instance_n",
    "empirical_DE_A_plus",
    "crossfit_DE_A_plus",
    "DE_empirical_minus_crossfit",
    "empirical_baseline_A_plus",
    "crossfit_baseline_A_plus",
    "baseline_empirical_minus_crossfit",
    "empirical_pair_delta_A_plus",
    "crossfit_pair_delta_A_plus",
    "pair_delta_empirical_minus_crossfit",
    "empirical_pair_direction",
    "crossfit_pair_direction",
    "CF_nonloss_all_11",
    "CF_positive_caps",
    "CF_tie_caps",
    "CF_negative_caps",
    "CF_worst_cap_margin",
]

for path, selected in [
    (PAIR_OUT, pair_rows),
    (CORE_OUT, core_rows),
    (SPECIAL_OUT, special_rows),
]:
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(selected)


audit = {
    "audit":
        "CROSSFITTED_VEF_AUBC_OPTIMISM",

    "authority_scope":
        "Spec5.5.5_ChecklistV27",

    "scientific_role":
        "RETROSPECTIVE_EMPIRICAL_ENVELOPE_OPTIMISM_SENSITIVITY",

    "primary_frontier_redefined":
        False,

    "selector_retuned":
        False,

    "new_metric":
        False,

    "api_calls":
        0,

    "new_model_execution":
        0,

    "new_selector_execution":
        0,

    "source":
        str(SOURCE),

    "source_sha256":
        sha256_file(SOURCE),

    "source_rows":
        len(rows),

    "pair_count":
        len(pair_rows),

    "core_pair_count":
        len(core_rows),

    "specialized_pair_count":
        len(special_rows),

    "frozen_crossfit_sanity":
        {
            "CF_NONLOSS_ALL_11":
                f"{cf_nonloss_17}/17",
            "expected":
                "12/17",
            "status":
                "PASS",
        },

    "core_empirical_direction_pattern":
        {
            "positive":
                emp_core_dirs["POSITIVE"],
            "tie":
                emp_core_dirs["TIE"],
            "negative":
                emp_core_dirs["NEGATIVE"],
        },

    "core_crossfit_A_plus_direction_pattern":
        {
            "positive":
                cf_core_dirs["POSITIVE"],
            "tie":
                cf_core_dirs["TIE"],
            "negative":
                cf_core_dirs["NEGATIVE"],
        },

    "core_direction_changes":
        core_direction_changes,

    "core_crossfit_negative_pairs":
        core_cf_negative_pairs,

    "core_CF_nonloss_all_11_count":
        core_cf_nonloss11,

    "outputs":
        {
            "all_17":
                str(PAIR_OUT),
            "core15":
                str(CORE_OUT),
            "specialized_toolprm":
                str(SPECIAL_OUT),
        },

    "next":
        "ALL_IN_COST_CLAIM_GATE",
}

AUDIT.write_text(
    json.dumps(
        audit,
        indent=2,
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)


# ------------------------------------------------------------
# Compact terminal output.
# ------------------------------------------------------------
print("CURRENT=CROSSFITTED_VEF_AUBC_OPTIMISM_AUDIT")
print("PASS=FROZEN_187_ROW_CURVE_BOUND")
print("PASS=FROZEN_CROSSFIT_SANITY_12_OF_17_REPRODUCED")
print()

print("=== CORE15 CROSSFIT A+ ===")

for r in core_rows:
    print(
        f"{r['benchmark']}|{r['baseline']}|"
        f"EMP_DELTA={float(r['empirical_pair_delta_A_plus']):.9f}|"
        f"CF_DELTA={float(r['crossfit_pair_delta_A_plus']):.9f}|"
        f"OPTIMISM={float(r['pair_delta_empirical_minus_crossfit']):.9f}|"
        f"EMP_DIR={r['empirical_pair_direction']}|"
        f"CF_DIR={r['crossfit_pair_direction']}|"
        f"CF_NONLOSS11={r['CF_nonloss_all_11']}"
    )

print()
print(
    "EMPIRICAL_CORE_PATTERN="
    f"{emp_core_dirs['POSITIVE']}_POSITIVE_"
    f"{emp_core_dirs['TIE']}_TIE_"
    f"{emp_core_dirs['NEGATIVE']}_NEGATIVE"
)

print(
    "CROSSFIT_CORE_PATTERN="
    f"{cf_core_dirs['POSITIVE']}_POSITIVE_"
    f"{cf_core_dirs['TIE']}_TIE_"
    f"{cf_core_dirs['NEGATIVE']}_NEGATIVE"
)

print(
    f"CORE_DIRECTION_CHANGES={core_direction_changes}"
)

print(
    "CORE_CROSSFIT_NEGATIVE_PAIRS="
    + (
        ",".join(core_cf_negative_pairs)
        if core_cf_negative_pairs
        else "NONE"
    )
)

print(
    f"CORE_CF_NONLOSS_ALL_11="
    f"{core_cf_nonloss11}/15"
)

print()
print("=== SPECIALIZED TOOLPRM ===")

for r in special_rows:
    print(
        f"{r['benchmark']}|{r['baseline']}|"
        f"EMP_DELTA={float(r['empirical_pair_delta_A_plus']):.9f}|"
        f"CF_DELTA={float(r['crossfit_pair_delta_A_plus']):.9f}|"
        f"OPTIMISM={float(r['pair_delta_empirical_minus_crossfit']):.9f}|"
        f"CF_DIR={r['crossfit_pair_direction']}|"
        f"CF_NONLOSS11={r['CF_nonloss_all_11']}"
    )

print()
print("PRIMARY_EMPIRICAL_VEF_REDEFINED=NO")
print("CROSSFIT_ROLE=RETROSPECTIVE_OPTIMISM_SENSITIVITY")
print("SELECTOR_RETUNED=NO")
print("NEW_METRIC=NO")
print("API_CALLS=NO")

print(f"PAIR_OUT={PAIR_OUT}")
print(f"CORE_OUT={CORE_OUT}")
print(f"SPECIAL_OUT={SPECIAL_OUT}")
print(f"AUDIT={AUDIT}")

print("DONE=CROSSFITTED_VEF_AUBC_OPTIMISM_AUDIT")
print("NEXT=ALL_IN_COST_CLAIM_GATE")
print("DO_NOT_TOUCH=H1_H2_H3_H4_H5_H6_D11_PHYSICAL_RESULTS")
