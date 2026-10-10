#!/usr/bin/env python3

import csv
import hashlib
import json
import re
from pathlib import Path

PROJECT = Path("__DECOUPLE_ROOT__")
ROOT = PROJECT / "10_PILOT/STEP4_V2_CLEAN_REBUILD"

AUDIT_DIR = (
    ROOT
    / "06_AUDIT/STEP4V2_POSTD11_ALL_IN_COST_GATE"
)

REPORT = AUDIT_DIR / "01_EXISTING_ALL_IN_COST_AUTHORITY.json"

D11_LOGICAL = (
    ROOT
    / "04_OUTPUTS/STEP4V2_D11_FINAL_RANDOM_AWARE_ANALYSIS/"
      "D11_FINAL_ALL_LOGICAL_RESULTS.tsv"
)

D11_UTILITY = (
    ROOT
    / "04_OUTPUTS/STEP4V2_D11_FINAL_RANDOM_AWARE_ANALYSIS/"
      "D11_FINAL_TERMINAL_UTILITY.tsv"
)

STEP3_LEDGER = (
    PROJECT
    / "10_PILOT/STEP3/04_OUTPUTS/"
      "STEP3E_EXACT_CHECKPOINT_REPLAY/"
      "STEP3E_JOINT_REPLAY_EXECUTION_MANIFEST.jsonl"
)

STEP3_LEDGER_MANIFEST = (
    PROJECT
    / "10_PILOT/STEP3/04_OUTPUTS/"
      "STEP3E_EXACT_CHECKPOINT_REPLAY/"
      "STEP3E_FORMAL_EXECUTION_LEDGER_MANIFEST.json"
)

SEARCH_ROOTS = [
    ROOT / "04_OUTPUTS",
    ROOT / "06_AUDIT",
    PROJECT / "10_PILOT/STEP3/04_OUTPUTS/STEP3E_EXACT_CHECKPOINT_REPLAY",
]

CORE_ID_FIELDS = {
    "benchmark",
    "method",
    "budget",
}

COST_PATTERNS = {
    "calls": re.compile(
        r"(api_?calls?|model_?calls?|request_?count|attempts?)",
        re.I,
    ),
    "tokens": re.compile(
        r"(token|prompt_tokens|completion_tokens|input_tokens|output_tokens)",
        re.I,
    ),
    "latency": re.compile(
        r"(latency|wall_?clock|elapsed|runtime|duration)",
        re.I,
    ),
    "money": re.compile(
        r"(usd|dollar|price|monetary|cost_usd)",
        re.I,
    ),
    "compute": re.compile(
        r"(gpu|cpu|memory|throughput)",
        re.I,
    ),
    "verification": re.compile(
        r"(verification|verified|selected_steps|verify_calls?)",
        re.I,
    ),
}


def fail(msg):
    print(f"FAIL={msg}")
    raise SystemExit(1)


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def get_tsv_header(path):
    with path.open(
        "r",
        encoding="utf-8",
        errors="replace",
        newline="",
    ) as f:
        reader = csv.reader(f, delimiter="\t")
        return next(reader)


def get_csv_header(path):
    with path.open(
        "r",
        encoding="utf-8",
        errors="replace",
        newline="",
    ) as f:
        reader = csv.reader(f)
        return next(reader)


def get_jsonl_keys(path):
    with path.open(
        "r",
        encoding="utf-8",
        errors="replace",
    ) as f:
        for line in f:
            line = line.strip()
            if line:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    return sorted(obj.keys())
    return []


def classify_fields(fields):
    hits = {}

    for category, pattern in COST_PATTERNS.items():
        matched = [
            x for x in fields
            if pattern.search(str(x))
        ]
        hits[category] = sorted(matched)

    return hits


for path in (
    D11_LOGICAL,
    D11_UTILITY,
    STEP3_LEDGER,
    STEP3_LEDGER_MANIFEST,
):
    if not path.exists():
        fail(f"MISSING_EXPECTED_AUTHORITY={path}")


d11_logical_fields = get_tsv_header(D11_LOGICAL)
d11_utility_fields = get_tsv_header(D11_UTILITY)
step3_ledger_fields = get_jsonl_keys(STEP3_LEDGER)

with STEP3_LEDGER_MANIFEST.open(
    "r",
    encoding="utf-8",
) as f:
    manifest_obj = json.load(f)

manifest_fields = (
    sorted(manifest_obj.keys())
    if isinstance(manifest_obj, dict)
    else []
)


# ------------------------------------------------------------
# Look only for structured existing cost-ledger candidates.
# No outcome recomputation and no broad historical archaeology.
# ------------------------------------------------------------
structured_candidates = []

seen = set()

for root in SEARCH_ROOTS:
    if not root.exists():
        continue

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if path in seen:
            continue
        seen.add(path)

        suffix = path.suffix.lower()

        try:
            if suffix == ".tsv":
                fields = get_tsv_header(path)
            elif suffix == ".csv":
                fields = get_csv_header(path)
            elif suffix == ".jsonl":
                fields = get_jsonl_keys(path)
            else:
                continue
        except Exception:
            continue

        if not fields:
            continue

        cost_hits = classify_fields(fields)

        if any(cost_hits.values()):
            structured_candidates.append({
                "path": str(path),
                "sha256": sha256_file(path),
                "fields": fields,
                "cost_hits": cost_hits,
            })


# ------------------------------------------------------------
# Determine whether a unified method x budget all-in ledger
# already exists.
#
# Required for a strong "all-in efficiency" claim:
# - method-comparable identity
# - budget identity
# - call accounting
# - token accounting
# - latency/runtime accounting
#
# Monetary dollars are recorded separately because exact USD
# need not exist if complete resource accounting is available.
# ------------------------------------------------------------
unified_candidates = []

for item in structured_candidates:
    fields_lower = {
        str(x).lower()
        for x in item["fields"]
    }

    has_method = "method" in fields_lower
    has_budget = (
        "budget" in fields_lower
        or "budget_pct" in fields_lower
        or "budget_cap_pct" in fields_lower
    )
    has_benchmark = "benchmark" in fields_lower

    hits = item["cost_hits"]

    has_calls = bool(hits["calls"])
    has_tokens = bool(hits["tokens"])
    has_latency = bool(hits["latency"])

    if (
        has_method
        and has_budget
        and has_benchmark
        and has_calls
        and has_tokens
        and has_latency
    ):
        unified_candidates.append(item)


complete_all_in_ledger = len(unified_candidates) > 0

if complete_all_in_ledger:
    claim_gate = (
        "EXISTING_COMPLETE_LEDGER_CANDIDATE_FOUND_"
        "REQUIRES_METHOD_COVERAGE_VALIDATION"
    )
    next_step = (
        "VALIDATE_EXISTING_LEDGER_METHOD_AND_BUDGET_COVERAGE"
    )
else:
    claim_gate = (
        "NO_COMPLETE_EXISTING_ALL_IN_LEDGER_"
        "RESTRICT_CLAIM_TO_VERIFICATION_CAPACITY_FRONTIER"
    )
    next_step = "TOOLPRM_OVERLAP_EFFECTIVE_N_FINAL_AUDIT"


report = {
    "audit":
        "ALL_IN_COST_CLAIM_GATE",

    "authority_scope":
        "Spec5.5.5_ChecklistV27",

    "api_calls":
        0,

    "new_model_execution":
        0,

    "outcome_recomputation":
        False,

    "scientific_question":
        "DO_EXISTING_FROZEN_ARTIFACTS_SUPPORT_AN_ALL_IN_EFFICIENCY_CLAIM",

    "d11_logical": {
        "path": str(D11_LOGICAL),
        "sha256": sha256_file(D11_LOGICAL),
        "fields": d11_logical_fields,
        "cost_hits":
            classify_fields(d11_logical_fields),
    },

    "d11_utility": {
        "path": str(D11_UTILITY),
        "sha256": sha256_file(D11_UTILITY),
        "fields": d11_utility_fields,
        "cost_hits":
            classify_fields(d11_utility_fields),
    },

    "step3_execution_ledger": {
        "path": str(STEP3_LEDGER),
        "sha256": sha256_file(STEP3_LEDGER),
        "fields": step3_ledger_fields,
        "cost_hits":
            classify_fields(step3_ledger_fields),
    },

    "step3_execution_ledger_manifest": {
        "path": str(STEP3_LEDGER_MANIFEST),
        "sha256": sha256_file(STEP3_LEDGER_MANIFEST),
        "fields": manifest_fields,
        "cost_hits":
            classify_fields(manifest_fields),
    },

    "structured_cost_candidate_count":
        len(structured_candidates),

    "structured_cost_candidates":
        structured_candidates,

    "unified_method_budget_all_in_candidate_count":
        len(unified_candidates),

    "unified_method_budget_all_in_candidates":
        unified_candidates,

    "complete_existing_all_in_ledger_candidate":
        complete_all_in_ledger,

    "claim_gate":
        claim_gate,

    "claim_boundary_if_no_complete_ledger": {
        "allowed":
            "VERIFICATION_CAPACITY_FRONTIER",
        "not_supported":
            "ALL_IN_COMPUTE_OR_DEPLOYMENT_EFFICIENCY",
        "do_not_equate_verification_slots_with":
            [
                "TOTAL_TOKENS",
                "TOTAL_MODEL_CALLS",
                "END_TO_END_LATENCY",
                "MONETARY_COST",
            ],
    },

    "next":
        next_step,
}

REPORT.write_text(
    json.dumps(
        report,
        indent=2,
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)


print("CURRENT=ALL_IN_COST_CLAIM_GATE")
print()

print("=== D11 FINAL LOGICAL RESULT FIELDS ===")
print(",".join(d11_logical_fields))
print()

print("=== D11 COST FIELD HITS ===")
for category, hits in classify_fields(
    d11_logical_fields
).items():
    print(
        f"{category.upper()}="
        + (",".join(hits) if hits else "NONE")
    )

print()
print("=== STEP3 EXECUTION LEDGER COST FIELD HITS ===")
for category, hits in classify_fields(
    step3_ledger_fields
).items():
    print(
        f"{category.upper()}="
        + (",".join(hits) if hits else "NONE")
    )

print()
print(
    "STRUCTURED_COST_CANDIDATE_COUNT="
    f"{len(structured_candidates)}"
)

print(
    "UNIFIED_METHOD_BUDGET_ALL_IN_CANDIDATE_COUNT="
    f"{len(unified_candidates)}"
)

for item in unified_candidates:
    print(
        "UNIFIED_CANDIDATE="
        f"{item['path']}"
    )

print()
print(
    "COMPLETE_EXISTING_ALL_IN_LEDGER_CANDIDATE="
    + (
        "YES"
        if complete_all_in_ledger
        else "NO"
    )
)

print(f"CLAIM_GATE={claim_gate}")

if not complete_all_in_ledger:
    print(
        "PASS=CLAIM_RESTRICTED_TO_VERIFICATION_CAPACITY_FRONTIER"
    )
    print(
        "ALL_IN_EFFICIENCY_CLAIM_AUTHORIZED=NO"
    )
else:
    print(
        "CURRENT_STATUS=LEDGER_CANDIDATE_REQUIRES_COVERAGE_VALIDATION"
    )
    print(
        "ALL_IN_EFFICIENCY_CLAIM_AUTHORIZED=NOT_YET"
    )

print("API_CALLS=NO")
print("NEW_MODEL_EXECUTION=NO")
print(f"REPORT={REPORT}")
print("DONE=ALL_IN_COST_EXISTING_EVIDENCE_AUDIT")
print(f"NEXT={next_step}")
print(
    "DO_NOT_TOUCH="
    "H1_H2_H3_H4_H5_H6_D11_PHYSICAL_RESULTS"
)
