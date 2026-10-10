#!/usr/bin/env python3

import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path("__DECOUPLE_ROOT__/10_PILOT/STEP4_V2_CLEAN_REBUILD")

SOURCE = ROOT / "04_OUTPUTS/STEP4V2_D11_FINAL_RANDOM_AWARE_ANALYSIS/D11_FINAL_ALL_LOGICAL_RESULTS.tsv"
BOOT = ROOT / "04_OUTPUTS/STEP4V2_VEF_AUBC_INFERENCE/FULL_VEF_AUBC_BOOTSTRAP_CORE_15.tsv"

OUT = ROOT / "04_OUTPUTS/STEP4V2_VEF_AUBC_FINAL_INFERENCE"
AUDIT = ROOT / "06_AUDIT/STEP4V2_VEF_AUBC_FINAL_INFERENCE"

GRID = [5,10,20,30,40,50,60,70,80,90,100]
METHODS = ["DECOUPLE","H-only","p-only","Random","Step-PRM","PRM@BoK"]
BASELINES = ["H-only","p-only","Random","Step-PRM","PRM@BoK"]

EXPECTED_SOURCE_SHA = "32d160166c3546f62b579f30e2e007e6213fb64596fca9b9ecb52f3b1bb83c53"
EXPECTED_BOOT_SHA = "c62693a09ae7a67861e08700df2e13da3021f2edaa2bd6f895c7c742205ea8b4"

N_PERM = 100000
SEED = 20260929
EPS = 1e-12


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for x in iter(lambda: f.read(1024*1024), b""):
            h.update(x)
    return h.hexdigest()


def mean(xs):
    return sum(xs) / len(xs)


def pct(x):
    v = float(x)
    if v <= 1.0 + EPS:
        v *= 100
    return int(round(v))


def norm_benchmark(x):
    y = str(x).strip().upper().replace("-", "_").replace(" ", "_")
    return {
        "BFCL": "BFCL",
        "MATH_SHEPHERD": "Math-Shepherd",
        "TOOLALPACA": "ToolAlpaca",
    }.get(y, str(x).strip())


def vef_aubc(curve):
    frontier = []
    cur = None
    for x in curve:
        cur = x if cur is None else max(cur, x)
        frontier.append(cur)

    xs = [b / 100.0 for b in GRID]
    area = 0.0
    for j in range(1, len(xs)):
        area += 0.5 * (frontier[j-1] + frontier[j]) * (xs[j] - xs[j-1])

    return area / (xs[-1] - xs[0])


def holm(pairs):
    # pairs = [(index, p)]
    ordered = sorted(pairs, key=lambda x: x[1])
    m = len(ordered)
    adjusted = [None] * m
    running = 0.0

    for rank, (idx, p) in enumerate(ordered, start=1):
        value = min(1.0, (m - rank + 1) * p)
        running = max(running, value)
        adjusted[idx] = running

    return adjusted


print("CURRENT=VEF_AUBC_FINAL_PERMUTATION_HOLM")
print(f"PERMUTATIONS={N_PERM}")
print(f"SEED={SEED}")
print("PERMUTATION_UNIT=original_instance_whole_11_budget_vector")
print("API_CALLS=0")
print("MODEL_RUNS=0")
print("PHYSICAL_REPLAY=0")

if sha256(SOURCE) != EXPECTED_SOURCE_SHA:
    raise RuntimeError("SOURCE_SHA_MISMATCH")

if sha256(BOOT) != EXPECTED_BOOT_SHA:
    raise RuntimeError("BOOTSTRAP_AUTHORITY_SHA_MISMATCH")

raw = defaultdict(list)

with open(SOURCE, newline="", encoding="utf-8") as f:
    r = csv.DictReader(f, delimiter="\t")
    for row in r:
        b = norm_benchmark(row["benchmark"])
        m = row["method"].strip()
        if m not in METHODS:
            continue
        q = pct(row["budget"])
        if q not in GRID:
            continue
        raw[(b,m,q,row["instance_id"])].append(float(row["terminal_Z"]))

collapsed = {k: mean(v) for k,v in raw.items()}

boot = {}
with open(BOOT, newline="", encoding="utf-8") as f:
    r = csv.DictReader(f, delimiter="\t")
    for row in r:
        boot[(row["benchmark"], row["baseline"])] = row

results = []

for bi, benchmark in enumerate(["BFCL","Math-Shepherd","ToolAlpaca"]):

    req = []
    for method in METHODS:
        for budget in GRID:
            req.append({
                iid for (b,m,q,iid) in collapsed
                if b == benchmark and m == method and q == budget
            })

    panel = sorted(set.intersection(*req))

    for bj, baseline in enumerate(BASELINES):

        def curve(method):
            return [
                mean([
                    collapsed[(benchmark,method,q,iid)]
                    for iid in panel
                ])
                for q in GRID
            ]

        observed = vef_aubc(curve("DECOUPLE")) - vef_aubc(curve(baseline))

        expected = float(boot[(benchmark, baseline)]["observed_delta"])
        if abs(observed - expected) > 1e-8:
            raise RuntimeError(
                f"OBSERVED_RECON_MISMATCH={benchmark}|{baseline}|{observed}|{expected}"
            )

        # Keep the complete 11-budget vectors paired within instance.
        de_vectors = [
            [collapsed[(benchmark,"DECOUPLE",q,iid)] for q in GRID]
            for iid in panel
        ]
        bl_vectors = [
            [collapsed[(benchmark,baseline,q,iid)] for q in GRID]
            for iid in panel
        ]

        rng = random.Random(SEED + bi * 100 + bj)

        ge_one = 0
        ge_two = 0

        for _ in range(N_PERM):
            de_sums = [0.0] * len(GRID)
            bl_sums = [0.0] * len(GRID)

            for dv, bv in zip(de_vectors, bl_vectors):
                if rng.getrandbits(1):
                    a, c = dv, bv
                else:
                    a, c = bv, dv

                for j in range(len(GRID)):
                    de_sums[j] += a[j]
                    bl_sums[j] += c[j]

            n = len(panel)
            de_curve = [x/n for x in de_sums]
            bl_curve = [x/n for x in bl_sums]

            delta = vef_aubc(de_curve) - vef_aubc(bl_curve)

            if delta >= observed - EPS:
                ge_one += 1

            if abs(delta) >= abs(observed) - EPS:
                ge_two += 1

        p_one = (ge_one + 1) / (N_PERM + 1)
        p_two = (ge_two + 1) / (N_PERM + 1)

        results.append({
            "benchmark": benchmark,
            "baseline": baseline,
            "joint_panel_n": len(panel),
            "DE_full_VEF_AUBC": boot[(benchmark,baseline)]["DE_full_VEF_AUBC"],
            "baseline_full_VEF_AUBC": boot[(benchmark,baseline)]["baseline_full_VEF_AUBC"],
            "observed_delta": f"{observed:.9f}",
            "bootstrap_ci95_low": boot[(benchmark,baseline)]["bootstrap_ci95_low"],
            "bootstrap_ci95_high": boot[(benchmark,baseline)]["bootstrap_ci95_high"],
            "permutation_p_one_sided": f"{p_one:.9f}",
            "permutation_p_two_sided": f"{p_two:.9f}",
        })

# Holm separately within each benchmark, five prespecified core comparators.
for benchmark in ["BFCL","Math-Shepherd","ToolAlpaca"]:
    ids = [i for i,r in enumerate(results) if r["benchmark"] == benchmark]

    p1 = [(k, float(results[i]["permutation_p_one_sided"])) for k,i in enumerate(ids)]
    p2 = [(k, float(results[i]["permutation_p_two_sided"])) for k,i in enumerate(ids)]

    h1 = holm(p1)
    h2 = holm(p2)

    for k,i in enumerate(ids):
        results[i]["holm5_p_one_sided"] = f"{h1[k]:.9f}"
        results[i]["holm5_p_two_sided"] = f"{h2[k]:.9f}"

out = OUT / "VEF_AUBC_FINAL_PERMUTATION_HOLM_CORE15.tsv"

if out.exists():
    raise RuntimeError(f"REFUSE_OVERWRITE={out}")

with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()), delimiter="\t")
    w.writeheader()
    w.writerows(results)

print()
print("=== FINAL CORE VEF-AUBC INFERENCE ===")

for r in results:
    print(
        f"{r['benchmark']}|{r['baseline']}|"
        f"DE={r['DE_full_VEF_AUBC']}|"
        f"BASE={r['baseline_full_VEF_AUBC']}|"
        f"DELTA={r['observed_delta']}|"
        f"CI95=[{r['bootstrap_ci95_low']},{r['bootstrap_ci95_high']}]|"
        f"P2={r['permutation_p_two_sided']}|"
        f"HOLM5_P2={r['holm5_p_two_sided']}"
    )

raw_sig = sum(float(r["permutation_p_two_sided"]) < 0.05 for r in results)
holm_sig = sum(float(r["holm5_p_two_sided"]) < 0.05 for r in results)

print()
print("=== FINAL FAMILY SUMMARY ===")
print(f"CORE_PAIR_COUNT={len(results)}")
print(f"RAW_TWO_SIDED_P_LT_005={raw_sig}")
print(f"HOLM5_TWO_SIDED_P_LT_005={holm_sig}")

audit = {
    "status": "PASS",
    "metric": "FULL_VEF_AUBC_5_TO_100",
    "permutation_unit": "original_instance_whole_11_budget_vector",
    "permutations": N_PERM,
    "seed": SEED,
    "holm_family": "within_benchmark_5_core_comparators",
    "source_sha256": sha256(SOURCE),
    "bootstrap_authority_sha256": sha256(BOOT),
    "output_sha256": sha256(out),
}

audit_path = AUDIT / "VEF_AUBC_FINAL_PERMUTATION_HOLM_AUDIT.json"

if audit_path.exists():
    raise RuntimeError(f"REFUSE_OVERWRITE={audit_path}")

with open(audit_path, "w", encoding="utf-8") as f:
    json.dump(audit, f, indent=2, sort_keys=True)
    f.write("\n")

print()
print(f"OUTPUT={out}")
print(f"OUTPUT_SHA256={sha256(out)}")
print(f"AUDIT={audit_path}")
print(f"AUDIT_SHA256={sha256(audit_path)}")
print("PASS=VEF_AUBC_FINAL_PERMUTATION_HOLM")
print("DONE=VEF_AUBC_FINAL_INFERENCE")
print("NEXT=REVIEW_GENERATED_PERMUTATION_TABLE")
print("DO_NOT_TOUCH=FROZEN_D11_PHYSICAL_RESULTS")
