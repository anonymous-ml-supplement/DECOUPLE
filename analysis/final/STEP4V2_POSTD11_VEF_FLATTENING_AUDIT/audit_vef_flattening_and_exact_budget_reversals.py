#!/usr/bin/env python3

from pathlib import Path
import csv
from collections import defaultdict

ROOT = Path("__DECOUPLE_ROOT__/10_PILOT/STEP4_V2_CLEAN_REBUILD")

EXACT = (
    ROOT / "04_OUTPUTS"
    / "STEP4V2_POSTD11_EXACT_BUDGET_MAIN_TABLE"
    / "D11_EXACT_BUDGET_TERMINAL_UTILITY_LONG.tsv"
)

VEF = (
    ROOT / "04_OUTPUTS"
    / "STEP4V2_POSTD11_EXACT_BUDGET_MAIN_TABLE"
    / "D11_VEF_CAPACITY_CURVE_LONG.tsv"
)

OUT = (
    ROOT / "04_OUTPUTS"
    / "STEP4V2_POSTD11_VEF_FLATTENING_AUDIT"
)

AUDIT = (
    ROOT / "06_AUDIT"
    / "STEP4V2_POSTD11_VEF_FLATTENING_AUDIT"
)

OUT.mkdir(parents=True, exist_ok=True)
AUDIT.mkdir(parents=True, exist_ok=True)

BUDGETS = [5,10,20,30,40,50,60,70,80,90,100]
BENCHMARKS = ["BFCL","Math-Shepherd","ToolAlpaca"]
METHODS = ["DECOUPLE","H-only","p-only","Random","Step-PRM","PRM@BoK"]
BASELINES = ["H-only","p-only","Random","Step-PRM","PRM@BoK"]

targets = [
    OUT / "VEF_FLATTENING_BY_METHOD.tsv",
    OUT / "EXACT_VS_VEF_BY_CAP.tsv",
    OUT / "RAW_EXACT_PAIRWISE_DIRECTION.tsv",
    OUT / "VEF_PAIRWISE_DIRECTION.tsv",
    OUT / "ENVELOPE_DIRECTION_CHANGE_AUDIT.tsv",
    AUDIT / "01_VEF_FLATTENING_AUDIT.txt",
]

for p in targets:
    if p.exists():
        raise SystemExit(f"FAIL=OUTPUT_EXISTS\nTARGET={p}")

exact = {}
with EXACT.open("r", encoding="utf-8", newline="") as f:
    r = csv.DictReader(f, delimiter="\t")
    for row in r:
        key = (
            row["benchmark"],
            row["method"],
            int(row["budget_pct"]),
        )
        exact[key] = float(row["terminal_utility"])

vef = {}
source_budget = {}
with VEF.open("r", encoding="utf-8", newline="") as f:
    r = csv.DictReader(f, delimiter="\t")
    for row in r:
        key = (
            row["benchmark"],
            row["method"],
            int(row["capacity_pct"]),
        )
        vef[key] = float(row["VEF_utility"])
        source_budget[key] = int(row["attaining_exact_budget_pct"])


# -------------------------------------------------------------
# Method-level flattening diagnostics
# -------------------------------------------------------------

method_rows = []

for b in BENCHMARKS:
    for m in METHODS:
        vals = [exact[(b,m,beta)] for beta in BUDGETS]

        peak = max(vals)
        earliest_peak = BUDGETS[vals.index(peak)]

        unique_exact = len(set(round(x, 12) for x in vals))
        unique_vef = len(
            set(round(vef[(b,m,beta)], 12) for beta in BUDGETS)
        )

        carried = 0
        attained_at_current = 0
        post_peak_declines = 0
        envelope_lift_sum = 0.0
        envelope_lift_max = 0.0

        for beta in BUDGETS:
            sb = source_budget[(b,m,beta)]

            if sb < beta:
                carried += 1
            else:
                attained_at_current += 1

            lift = vef[(b,m,beta)] - exact[(b,m,beta)]
            envelope_lift_sum += lift
            envelope_lift_max = max(envelope_lift_max, lift)

            if beta > earliest_peak and exact[(b,m,beta)] < peak - 1e-12:
                post_peak_declines += 1

        method_rows.append({
            "benchmark": b,
            "method": m,
            "exact_unique_levels": unique_exact,
            "vef_unique_levels": unique_vef,
            "exact_peak": peak,
            "earliest_peak_budget": earliest_peak,
            "carried_forward_caps": carried,
            "attained_at_current_cap": attained_at_current,
            "post_peak_exact_declines": post_peak_declines,
            "mean_envelope_lift": envelope_lift_sum / len(BUDGETS),
            "max_envelope_lift": envelope_lift_max,
        })


# -------------------------------------------------------------
# Exact vs VEF by cap
# -------------------------------------------------------------

cap_rows = []

for b in BENCHMARKS:
    for m in METHODS:
        for beta in BUDGETS:
            raw = exact[(b,m,beta)]
            front = vef[(b,m,beta)]
            sb = source_budget[(b,m,beta)]

            cap_rows.append({
                "benchmark": b,
                "method": m,
                "capacity_pct": beta,
                "exact_budget_utility": raw,
                "VEF_utility": front,
                "VEF_source_budget": sb,
                "carried_forward": int(sb < beta),
                "envelope_lift": front - raw,
            })


def dsign(x, eps=1e-12):
    if x > eps:
        return "POSITIVE"
    if x < -eps:
        return "NEGATIVE"
    return "TIE"


# -------------------------------------------------------------
# Raw exact pairwise directions
# -------------------------------------------------------------

raw_rows = []
vef_rows = []
change_rows = []

raw_total = defaultdict(int)
vef_total = defaultdict(int)

for b in BENCHMARKS:
    for base in BASELINES:
        rp = rt = rn = 0
        vp = vt = vn = 0
        neg_to_nonneg = 0

        for beta in BUDGETS:
            raw_delta = exact[(b,"DECOUPLE",beta)] - exact[(b,base,beta)]
            vef_delta = vef[(b,"DECOUPLE",beta)] - vef[(b,base,beta)]

            rs = dsign(raw_delta)
            vs = dsign(vef_delta)

            raw_total[rs] += 1
            vef_total[vs] += 1

            if rs == "POSITIVE":
                rp += 1
            elif rs == "TIE":
                rt += 1
            else:
                rn += 1

            if vs == "POSITIVE":
                vp += 1
            elif vs == "TIE":
                vt += 1
            else:
                vn += 1

            changed = int(rs != vs)
            if rs == "NEGATIVE" and vs != "NEGATIVE":
                neg_to_nonneg += 1

            change_rows.append({
                "benchmark": b,
                "baseline": base,
                "capacity_pct": beta,
                "raw_exact_delta": raw_delta,
                "raw_direction": rs,
                "VEF_delta": vef_delta,
                "VEF_direction": vs,
                "direction_changed": changed,
                "raw_negative_removed_by_envelope": int(
                    rs == "NEGATIVE" and vs != "NEGATIVE"
                ),
            })

        raw_rows.append({
            "benchmark": b,
            "baseline": base,
            "positive": rp,
            "tie": rt,
            "negative": rn,
        })

        vef_rows.append({
            "benchmark": b,
            "baseline": base,
            "positive": vp,
            "tie": vt,
            "negative": vn,
            "raw_negative_to_nonnegative": neg_to_nonneg,
        })


# -------------------------------------------------------------
# Write outputs
# -------------------------------------------------------------

def write_dicts(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=list(rows[0].keys()),
            delimiter="\t",
        )
        w.writeheader()
        for row in rows:
            out = {}
            for k,v in row.items():
                if isinstance(v, float):
                    out[k] = f"{v:.9f}"
                else:
                    out[k] = v
            w.writerow(out)

write_dicts(targets[0], method_rows)
write_dicts(targets[1], cap_rows)
write_dicts(targets[2], raw_rows)
write_dicts(targets[3], vef_rows)
write_dicts(targets[4], change_rows)

removed_neg = sum(
    r["raw_negative_removed_by_envelope"]
    for r in change_rows
)

changed_cells = sum(
    r["direction_changed"]
    for r in change_rows
)

with targets[5].open("w", encoding="utf-8") as f:
    f.write("CURRENT=VEF_FLATTENING_AND_EXACT_BUDGET_REVERSAL_AUDIT\n")
    f.write("\n")
    f.write(
        "RAW_EXACT_POINTWISE_PATTERN="
        f"{raw_total['POSITIVE']}_POSITIVE_"
        f"{raw_total['TIE']}_TIE_"
        f"{raw_total['NEGATIVE']}_NEGATIVE\n"
    )
    f.write(
        "VEF_POINTWISE_PATTERN="
        f"{vef_total['POSITIVE']}_POSITIVE_"
        f"{vef_total['TIE']}_TIE_"
        f"{vef_total['NEGATIVE']}_NEGATIVE\n"
    )
    f.write(
        f"DIRECTION_CHANGED_BY_ENVELOPE_CELLS={changed_cells}\n"
    )
    f.write(
        f"RAW_NEGATIVE_REMOVED_BY_ENVELOPE={removed_neg}\n"
    )
    f.write("\n")
    f.write("VEF_REDEFINITION=NO\n")
    f.write("RAW_RESULT_MUTATION=NO\n")
    f.write("NEW_MODEL_RUN=NO\n")
    f.write("NEW_API_CALL=NO\n")
    f.write("NEW_PHYSICAL_EXECUTION=NO\n")
    f.write("\n")
    f.write("DONE=VEF_FLATTENING_AUDIT\n")


print("=== FLATTENING BY METHOD ===")
with targets[0].open("r", encoding="utf-8") as f:
    for line in f:
        print(line.rstrip())

print()
print("=== RAW EXACT PAIRWISE DIRECTIONS ===")
with targets[2].open("r", encoding="utf-8") as f:
    for line in f:
        print(line.rstrip())

print()
print("=== VEF PAIRWISE DIRECTIONS ===")
with targets[3].open("r", encoding="utf-8") as f:
    for line in f:
        print(line.rstrip())

print()
print(
    "RAW_EXACT_POINTWISE_PATTERN="
    f"{raw_total['POSITIVE']}_POSITIVE_"
    f"{raw_total['TIE']}_TIE_"
    f"{raw_total['NEGATIVE']}_NEGATIVE"
)

print(
    "VEF_POINTWISE_PATTERN="
    f"{vef_total['POSITIVE']}_POSITIVE_"
    f"{vef_total['TIE']}_TIE_"
    f"{vef_total['NEGATIVE']}_NEGATIVE"
)

print(f"DIRECTION_CHANGED_BY_ENVELOPE_CELLS={changed_cells}")
print(f"RAW_NEGATIVE_REMOVED_BY_ENVELOPE={removed_neg}")

print()
print("DONE=VEF_FLATTENING_AUDIT")
print("NEXT=DECIDE_MANUSCRIPT_PRIMARY_DISPLAY_WITHOUT_REDEFINING_METRIC")
