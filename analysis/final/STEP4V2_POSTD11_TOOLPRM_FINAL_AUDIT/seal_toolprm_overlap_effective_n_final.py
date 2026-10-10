#!/usr/bin/env python3

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(
    "__DECOUPLE_ROOT__/10_PILOT/STEP4_V2_CLEAN_REBUILD"
)

TABLE = (
    ROOT
    / "04_OUTPUTS/STEP4V2_VEF_MANUSCRIPT/"
      "MANUSCRIPT_SPECIALIZED_TOOLPRM_ABSOLUTE_VEF.tsv"
)

SIGN = (
    ROOT
    / "06_AUDIT/STEP4V2_VEF_MANUSCRIPT/"
      "MANUSCRIPT_SPECIALIZED_TOOLPRM_SIGN_AUDIT.tsv"
)

CF = (
    ROOT
    / "04_OUTPUTS/STEP4V2_POSTD11_CROSSFIT_AUBC/"
      "CROSSFIT_A_PLUS_SPECIALIZED_TOOLPRM.tsv"
)

REPORT = (
    ROOT
    / "06_AUDIT/STEP4V2_POSTD11_TOOLPRM_FINAL_AUDIT/"
      "01_TOOLPRM_OVERLAP_EFFECTIVE_N_FINAL.json"
)

EXPECTED = {
    "BFCL": {
        "n": 12,
        "de_aubc": 1.0 / 6.0,
        "tool_aubc": 0.25,
        "delta": -1.0 / 12.0,
        "positive_caps": 0,
        "tie_caps": 0,
        "negative_caps": 11,
        "direction": "NEGATIVE",
    },
    "ToolAlpaca": {
        "n": 25,
        "de_aubc": 0.52,
        "tool_aubc": 0.48,
        "delta": 0.04,
        "positive_caps": 11,
        "tie_caps": 0,
        "negative_caps": 0,
        "direction": "POSITIVE",
    },
}

VEF_COLS = [
    "VEF_5",
    "VEF_10",
    "VEF_20",
    "VEF_30",
    "VEF_40",
    "VEF_50",
    "VEF_60",
    "VEF_70",
    "VEF_80",
    "VEF_90",
    "VEF_100",
]

TOL = 2e-8


def fail(msg):
    print(f"FAIL={msg}")
    raise SystemExit(1)


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_tsv(path):
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as f:
        return list(
            csv.DictReader(f, delimiter="\t")
        )


for path in (TABLE, SIGN, CF):
    if not path.exists():
        fail(f"MISSING_AUTHORITY={path}")


table_rows = read_tsv(TABLE)
sign_rows = read_tsv(SIGN)
cf_rows = read_tsv(CF)

if len(table_rows) != 4:
    fail(f"ABSOLUTE_TABLE_ROWS={len(table_rows)}_EXPECTED=4")

if len(sign_rows) != 2:
    fail(f"SIGN_ROWS={len(sign_rows)}_EXPECTED=2")

if len(cf_rows) != 2:
    fail(f"CROSSFIT_ROWS={len(cf_rows)}_EXPECTED=2")


results = {}

for benchmark, expected in EXPECTED.items():

    rows = [
        r for r in table_rows
        if r["benchmark"] == benchmark
    ]

    if len(rows) != 2:
        fail(
            f"{benchmark}_ABSOLUTE_ROWS="
            f"{len(rows)}_EXPECTED=2"
        )

    methods = {
        r["method"]
        for r in rows
    }

    if methods != {
        "DECOUPLE",
        "ToolPRM-GRPO",
    }:
        fail(
            f"{benchmark}_METHOD_SET="
            f"{sorted(methods)}"
        )

    ns = {
        int(r["pair_panel_n"])
        for r in rows
    }

    if ns != {expected["n"]}:
        fail(
            f"{benchmark}_PAIR_PANEL_N="
            f"{sorted(ns)}_EXPECTED={expected['n']}"
        )

    de = next(
        r for r in rows
        if r["method"] == "DECOUPLE"
    )

    tool = next(
        r for r in rows
        if r["method"] == "ToolPRM-GRPO"
    )

    de_a = float(de["full_VEF_AUBC"])
    tool_a = float(tool["full_VEF_AUBC"])
    delta = de_a - tool_a

    if abs(de_a - expected["de_aubc"]) > TOL:
        fail(
            f"{benchmark}_DE_AUBC={de_a}"
        )

    if abs(tool_a - expected["tool_aubc"]) > TOL:
        fail(
            f"{benchmark}_TOOLPRM_AUBC={tool_a}"
        )

    if abs(delta - expected["delta"]) > TOL:
        fail(
            f"{benchmark}_DELTA={delta}"
        )

    # Full 11-budget panel must be present and finite.
    for row in rows:
        for col in VEF_COLS:
            float(row[col])

    sr = [
        r for r in sign_rows
        if r["benchmark"] == benchmark
        and r["baseline"] == "ToolPRM-GRPO"
    ]

    if len(sr) != 1:
        fail(
            f"{benchmark}_SIGN_ROW_COUNT={len(sr)}"
        )

    sr = sr[0]

    p = int(sr["positive_caps"])
    t = int(sr["tie_caps"])
    n = int(sr["negative_caps"])

    if (
        p != expected["positive_caps"]
        or t != expected["tie_caps"]
        or n != expected["negative_caps"]
    ):
        fail(
            f"{benchmark}_SIGN_COUNTS="
            f"P{p}_T{t}_N{n}"
        )

    cfr = [
        r for r in cf_rows
        if r["benchmark"] == benchmark
        and r["baseline"] == "ToolPRM-GRPO"
    ]

    if len(cfr) != 1:
        fail(
            f"{benchmark}_CROSSFIT_ROW_COUNT={len(cfr)}"
        )

    cfr = cfr[0]

    cf_n = int(cfr["matched_instance_n"])

    if cf_n != expected["n"]:
        fail(
            f"{benchmark}_CF_N="
            f"{cf_n}_EXPECTED={expected['n']}"
        )

    empirical_dir = cfr[
        "empirical_pair_direction"
    ]
    crossfit_dir = cfr[
        "crossfit_pair_direction"
    ]

    if empirical_dir != expected["direction"]:
        fail(
            f"{benchmark}_EMP_DIR={empirical_dir}"
        )

    if crossfit_dir != expected["direction"]:
        fail(
            f"{benchmark}_CF_DIR={crossfit_dir}"
        )

    results[benchmark] = {
        "pair_panel_n":
            expected["n"],

        "core_panel_reference_n":
            25,

        "support_fraction_vs_core25":
            expected["n"] / 25.0,

        "DECOUPLE_full_VEF_AUBC":
            de_a,

        "ToolPRM_GRPO_full_VEF_AUBC":
            tool_a,

        "DECOUPLE_minus_ToolPRM":
            delta,

        "positive_caps":
            p,

        "tie_caps":
            t,

        "negative_caps":
            n,

        "empirical_direction":
            empirical_dir,

        "crossfit_direction":
            crossfit_dir,

        "crossfit_pair_delta_A_plus":
            float(
                cfr["crossfit_pair_delta_A_plus"]
            ),

        "CF_nonloss_all_11":
            int(cfr["CF_nonloss_all_11"]),
    }


report = {
    "audit":
        "TOOLPRM_OVERLAP_EFFECTIVE_N_FINAL",

    "authority_scope":
        "Spec5.5.5_ChecklistV27",

    "scientific_role":
        "SPECIALIZED_COMPARATOR_FAIRNESS_AND_SUPPORT",

    "api_calls":
        0,

    "new_model_execution":
        0,

    "new_baseline":
        False,

    "toolprm_in_core15":
        False,

    "panel_rule":
        "PAIR_SPECIFIC_COMPATIBLE_MATCHED_PANEL",

    "results":
        results,

    "interpretation_lock": {
        "BFCL":
            "ADVERSE_RESULT_MUST_REMAIN_VISIBLE_AND_IS_SUPPORTED_ON_PAIR_SPECIFIC_N12",

        "ToolAlpaca":
            "FAVORABLE_RESULT_SUPPORTED_ON_PAIR_SPECIFIC_N25",

        "do_not_pool_with_core15":
            True,

        "do_not_claim_uniform_superiority_over_ToolPRM":
            True,

        "do_not_suppress_BFCL_adverse_result":
            True,
    },

    "source_hashes": {
        "specialized_absolute_vef":
            sha256_file(TABLE),

        "specialized_sign_audit":
            sha256_file(SIGN),

        "specialized_crossfit":
            sha256_file(CF),
    },

    "gate6_status":
        "PASS_WITH_BENCHMARK_SPECIFIC_MIXED_DIRECTION",

    "next":
        "CONTEMPORARY_LITERATURE_COMPARISON_DECISION_MATRIX",
}

REPORT.write_text(
    json.dumps(
        report,
        indent=2,
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)


print("CURRENT=TOOLPRM_OVERLAP_EFFECTIVE_N_FINAL_AUDIT")
print()

for benchmark in (
    "BFCL",
    "ToolAlpaca",
):
    r = results[benchmark]

    print(
        f"{benchmark}|"
        f"PAIR_N={r['pair_panel_n']}|"
        f"SUPPORT_VS_CORE25="
        f"{r['support_fraction_vs_core25']:.3f}|"
        f"DE_A_PLUS="
        f"{r['DECOUPLE_full_VEF_AUBC']:.9f}|"
        f"TOOLPRM_A_PLUS="
        f"{r['ToolPRM_GRPO_full_VEF_AUBC']:.9f}|"
        f"DELTA="
        f"{r['DECOUPLE_minus_ToolPRM']:.9f}|"
        f"P={r['positive_caps']}|"
        f"T={r['tie_caps']}|"
        f"N={r['negative_caps']}|"
        f"CF_DIR={r['crossfit_direction']}"
    )

print()
print("PASS=PAIR_SPECIFIC_EFFECTIVE_N_BOUND")
print("PASS=11_BUDGET_SIGN_PATTERN_BOUND")
print("PASS=CROSSFIT_DIRECTION_CONSISTENCY_BOUND")

print("BFCL_TOOLPRM_RESULT=ADVERSE_N12")
print("TOOLALPACA_TOOLPRM_RESULT=FAVORABLE_N25")

print("TOOLPRM_CORE15_MEMBER=NO")
print("UNIFORM_TOOLPRM_SUPERIORITY_CLAIM_AUTHORIZED=NO")
print("BFCL_ADVERSE_RESULT_MUST_REMAIN_VISIBLE=YES")

print("API_CALLS=NO")
print("NEW_MODEL_EXECUTION=NO")
print(f"REPORT={REPORT}")

print("DONE=TOOLPRM_OVERLAP_EFFECTIVE_N_FINAL_AUDIT")
print("NEXT=CONTEMPORARY_LITERATURE_COMPARISON_DECISION_MATRIX")
print("DO_NOT_TOUCH=H1_H2_H3_H4_H5_H6_D11_PHYSICAL_RESULTS")
