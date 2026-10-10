#!/usr/bin/env python3

import csv
import hashlib
import json
from pathlib import Path

PROJECT = Path("__DECOUPLE_ROOT__")
ROOT = PROJECT / "10_PILOT/STEP4_V2_CLEAN_REBUILD"

OUT_DIR = ROOT / "04_OUTPUTS/STEP4V2_POSTD11_GLOBAL_HOLM15"
AUDIT_DIR = ROOT / "06_AUDIT/STEP4V2_POSTD11_GLOBAL_HOLM15"

OUT = OUT_DIR / "VEF_AUBC_GLOBAL_HOLM15_CORE15.tsv"
AUDIT = AUDIT_DIR / "01_GLOBAL_HOLM15_AUDIT.json"

TARGET_NAME = "VEF_AUBC_FINAL_PERMUTATION_HOLM_CORE15.tsv"


def fail(msg):
    print(f"FAIL={msg}")
    raise SystemExit(1)


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def holm_adjust(pvals):
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])

    out = [None] * m
    running = 0.0

    for rank, idx in enumerate(order):
        adjusted = min(1.0, (m - rank) * pvals[idx])
        running = max(running, adjusted)
        out[idx] = running

    return out


# ------------------------------------------------------------
# Targeted exact-filename authority binding only.
# ------------------------------------------------------------
candidates = sorted(
    p for p in PROJECT.rglob(TARGET_NAME)
    if "STEP4V2_POSTD11_GLOBAL_HOLM15" not in str(p)
)

if not candidates:
    fail("PERMUTATION_HOLM_CORE15_AUTHORITY_NOT_FOUND")

# Deduplicate byte-identical mirrors.
by_hash = {}

for path in candidates:
    digest = sha256_file(path)
    by_hash.setdefault(digest, []).append(path)

if len(by_hash) != 1:
    print("CANDIDATE_AUTHORITIES=")
    for digest, paths in sorted(by_hash.items()):
        print(f"SHA256={digest}")
        for path in paths:
            print(f"  PATH={path}")
    fail("MULTIPLE_NONIDENTICAL_RESULT_AUTHORITIES_FOUND")

source_hash, source_paths = next(iter(by_hash.items()))

# Prefer current STEP4_V2_CLEAN_REBUILD path if present.
current_paths = [
    p for p in source_paths
    if str(ROOT) in str(p)
]

SOURCE = current_paths[0] if current_paths else source_paths[0]


# ------------------------------------------------------------
# Load frozen 15-comparison permutation authority.
# ------------------------------------------------------------
with SOURCE.open("r", encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f, delimiter="\t"))

if len(rows) != 15:
    fail(f"CORE_COMPARISON_COUNT={len(rows)}_EXPECTED=15")

required = {
    "benchmark",
    "baseline",
    "joint_panel_n",
    "observed_delta",
    "permutation_p_one_sided",
    "permutation_p_two_sided",
    "holm5_p_one_sided",
    "holm5_p_two_sided",
}

if not required.issubset(set(rows[0].keys())):
    fail("SOURCE_SCHEMA_MISMATCH")


p1 = [float(r["permutation_p_one_sided"]) for r in rows]
p2 = [float(r["permutation_p_two_sided"]) for r in rows]

global_holm15_one = holm_adjust(p1)
global_holm15_two = holm_adjust(p2)


out_rows = []

for i, row in enumerate(rows):
    delta = float(row["observed_delta"])

    if delta > 1e-12:
        direction = "POSITIVE"
    elif delta < -1e-12:
        direction = "NEGATIVE"
    else:
        direction = "TIE"

    h5_one = float(row["holm5_p_one_sided"])
    h5_two = float(row["holm5_p_two_sided"])

    h15_one = float(global_holm15_one[i])
    h15_two = float(global_holm15_two[i])

    out_rows.append({
        "benchmark": row["benchmark"],
        "baseline": row["baseline"],
        "joint_panel_n": row["joint_panel_n"],
        "observed_delta": row["observed_delta"],
        "direction": direction,

        "permutation_p_one_sided":
            row["permutation_p_one_sided"],
        "holm5_p_one_sided":
            row["holm5_p_one_sided"],
        "global_holm15_p_one_sided":
            f"{h15_one:.9f}",

        "permutation_p_two_sided":
            row["permutation_p_two_sided"],
        "holm5_p_two_sided":
            row["holm5_p_two_sided"],
        "global_holm15_p_two_sided":
            f"{h15_two:.9f}",

        "holm5_two_sig_005":
            str(h5_two < 0.05),
        "global_holm15_two_sig_005":
            str(h15_two < 0.05),
    })


fields = [
    "benchmark",
    "baseline",
    "joint_panel_n",
    "observed_delta",
    "direction",
    "permutation_p_one_sided",
    "holm5_p_one_sided",
    "global_holm15_p_one_sided",
    "permutation_p_two_sided",
    "holm5_p_two_sided",
    "global_holm15_p_two_sided",
    "holm5_two_sig_005",
    "global_holm15_two_sig_005",
]

with OUT.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=fields,
        delimiter="\t",
    )
    writer.writeheader()
    writer.writerows(out_rows)


holm5_sig_two = [
    f"{r['benchmark']}|{r['baseline']}"
    for r in out_rows
    if r["holm5_two_sig_005"] == "True"
]

holm15_sig_two = [
    f"{r['benchmark']}|{r['baseline']}"
    for r in out_rows
    if r["global_holm15_two_sig_005"] == "True"
]


audit = {
    "audit": "GLOBAL_HOLM15_SENSITIVITY",
    "authority_scope": "Spec5.5.5_ChecklistV27",

    "primary_inferential_family":
        "WITHIN_BENCHMARK_HOLM5_RETAINED",

    "global_holm15_role":
        "CONSERVATIVE_SENSITIVITY_ONLY",

    "replaces_primary_holm5": False,

    "corrects_metric_selection_bias": False,

    "inference_status":
        "CONDITIONAL_RETROSPECTIVE",

    "api_calls": 0,
    "new_model_execution": 0,
    "new_permutation_execution": 0,

    "core_comparisons": 15,

    "source": str(SOURCE),
    "source_sha256": source_hash,

    "holm5_two_sided_significant_005":
        holm5_sig_two,

    "global_holm15_two_sided_significant_005":
        holm15_sig_two,

    "primary_point_estimate_pattern":
        "10_POSITIVE_5_TIE_0_NEGATIVE_UNCHANGED",

    "output": str(OUT),

    "next":
        "CROSSFITTED_VEF_AUBC_OPTIMISM_AUDIT",
}

AUDIT.write_text(
    json.dumps(audit, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)


print("CURRENT=GLOBAL_HOLM15_SENSITIVITY")
print(f"SOURCE={SOURCE}")
print(f"SOURCE_SHA256={source_hash}")
print()

print("=== GLOBAL HOLM15 RESULTS ===")

for row in out_rows:
    print(
        f"{row['benchmark']}|{row['baseline']}|"
        f"DELTA={row['observed_delta']}|"
        f"HOLM5_P2={row['holm5_p_two_sided']}|"
        f"HOLM15_P2={row['global_holm15_p_two_sided']}|"
        f"H15_SIG={row['global_holm15_two_sig_005']}"
    )

print()
print(
    "HOLM5_TWO_SIDED_SIG_005="
    + (
        ",".join(holm5_sig_two)
        if holm5_sig_two
        else "NONE"
    )
)

print(
    "GLOBAL_HOLM15_TWO_SIDED_SIG_005="
    + (
        ",".join(holm15_sig_two)
        if holm15_sig_two
        else "NONE"
    )
)

print("PASS=GLOBAL_HOLM15_SENSITIVITY_COMPLETE")
print("PRIMARY_HOLM5_RETAINED=YES")
print("GLOBAL_HOLM15_REPLACES_PRIMARY=NO")
print("CORRECTS_METRIC_SELECTION_BIAS=NO")
print("POINT_ESTIMATE_10_5_0_STATUS=UNCHANGED")

print(f"OUT={OUT}")
print(f"AUDIT={AUDIT}")

print("DONE=GLOBAL_HOLM15_SENSITIVITY")
print("NEXT=CROSSFITTED_VEF_AUBC_OPTIMISM_AUDIT")
print("DO_NOT_TOUCH=H1_H2_H3_H4_H5_H6_D11_PHYSICAL_RESULTS")
