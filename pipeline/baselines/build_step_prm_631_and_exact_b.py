#!/usr/bin/env python3

import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path("__DECOUPLE_ROOT__")

TOOL = ROOT / (
    "10_PILOT/STEP2/04_OUTPUTS/STEP2B_PRM_SCORING/"
    "TOOL_PRM/tool_step_prm_scores.jsonl"
)

MATH = ROOT / (
    "10_PILOT/STEP2/04_OUTPUTS/STEP2B_PRM_SCORING/"
    "GENPRM_MATH/math_genprm_scores.jsonl"
)

OUTDIR = ROOT / (
    "10_PILOT/STEP2/04_OUTPUTS/"
    "STEP2B_STEP_PRM_631"
)

AUDITDIR = ROOT / (
    "10_PILOT/STEP2/06_AUDIT/"
    "STEP2B_STEP_PRM_631"
)

MERGED = OUTDIR / "step_prm_631_scores.jsonl"
SELECTIONS = OUTDIR / "step_prm_exact_b_selections.jsonl"
AUDIT = AUDITDIR / "step_prm_631_audit.json"
MANIFEST = AUDITDIR / "step_prm_631_manifest.json"

EXPECTED_TOOL = 288
EXPECTED_MATH = 343
EXPECTED_TOTAL = 631

MASTER_SEED = 20260829
BUDGETS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.50]

FORBIDDEN_KEYS = {
    "possible_answer",
    "ground_truth",
    "path",
    "missed_function",
    "excluded_function",
    "correctness",
    "outcome",
    "oracle",
    "intervention_gain",
}


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            row["_source_line"] = line_number
            rows.append(row)
    return rows


def scan_forbidden(obj, location):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise RuntimeError(
                    f"Forbidden retrospective field at "
                    f"{location}: {key}"
                )
            scan_forbidden(
                value,
                f"{location}.{key}",
            )
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            scan_forbidden(
                value,
                f"{location}[{i}]",
            )


def tie_key(instance_id, step_index):
    payload = (
        f"{instance_id}\t"
        f"{step_index}\t"
        f"{MASTER_SEED}"
    ).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()


def budget_size(T, beta):
    return min(
        T,
        max(
            1,
            math.floor(beta * T + 0.5),
        ),
    )


def normalize_tool(row):
    scan_forbidden(row, "tool")

    score = float(
        row["process_correctness_score"]
    )
    risk = float(
        row["risk_score"]
    )

    if not math.isfinite(score):
        raise RuntimeError(
            "Non-finite Tool correctness score."
        )

    if not math.isfinite(risk):
        raise RuntimeError(
            "Non-finite Tool risk score."
        )

    expected_risk = 1.0 - score

    if abs(risk - expected_risk) > 1e-12:
        raise RuntimeError(
            "Tool risk transform mismatch."
        )

    if row.get("posthoc_access") is not False:
        raise RuntimeError(
            "Tool posthoc_access is not false."
        )

    return {
        "project": "DECOUPLE",
        "stage": "STEP2B_STEP_PRM_631",
        "baseline": "Step-PRM",
        "domain_verifier": "Tool-Step-PRM",
        "benchmark": row["benchmark"],
        "instance_id": row["instance_id"],
        "step_index": int(row["step_index"]),
        "candidate_kind": row["candidate_kind"],
        "prefix_hash": row["prefix_hash"],
        "model_id": row["model_id"],
        "correctness_score": score,
        "risk_score": risk,
        "posthoc_access": False,
        "tie_key": tie_key(
            row["instance_id"],
            int(row["step_index"]),
        ),
    }


def normalize_math(row):
    scan_forbidden(row, "math")

    score = float(
        row["step_prm_score"]
    )
    reward = float(
        row["official_genprm_reward"]
    )
    risk = float(
        row["risk_score"]
    )

    if not math.isfinite(score):
        raise RuntimeError(
            "Non-finite Math Step-PRM score."
        )

    if not math.isfinite(reward):
        raise RuntimeError(
            "Non-finite GenPRM official reward."
        )

    if not math.isfinite(risk):
        raise RuntimeError(
            "Non-finite Math risk score."
        )

    if abs(score - reward) > 1e-12:
        raise RuntimeError(
            "GenPRM reward/step score mismatch."
        )

    expected_risk = 1.0 - score

    if abs(risk - expected_risk) > 1e-12:
        raise RuntimeError(
            "Math risk transform mismatch."
        )

    if row.get("posthoc_access") is not False:
        raise RuntimeError(
            "Math posthoc_access is not false."
        )

    if int(row.get("terra_calls", 0)) != 0:
        raise RuntimeError(
            "Unexpected Terra calls in Math scores."
        )

    return {
        "project": "DECOUPLE",
        "stage": "STEP2B_STEP_PRM_631",
        "baseline": "Step-PRM",
        "domain_verifier": "Math-GenPRM",
        "benchmark": row["benchmark"],
        "instance_id": row["instance_id"],
        "step_index": int(row["step_index"]),
        "candidate_kind": row["candidate_kind"],
        "prefix_hash": row["prefix_hash"],
        "model_id": row["model_id"],
        "correctness_score": score,
        "risk_score": risk,
        "posthoc_access": False,
        "tie_key": tie_key(
            row["instance_id"],
            int(row["step_index"]),
        ),
    }


def main():
    OUTDIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    AUDITDIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    tool_rows = load_jsonl(TOOL)
    math_rows = load_jsonl(MATH)

    if len(tool_rows) != EXPECTED_TOOL:
        raise RuntimeError(
            f"Tool count mismatch: "
            f"{len(tool_rows)}"
        )

    if len(math_rows) != EXPECTED_MATH:
        raise RuntimeError(
            f"Math count mismatch: "
            f"{len(math_rows)}"
        )

    rows = []

    for row in tool_rows:
        rows.append(
            normalize_tool(row)
        )

    for row in math_rows:
        rows.append(
            normalize_math(row)
        )

    if len(rows) != EXPECTED_TOTAL:
        raise RuntimeError(
            f"Total candidate mismatch: "
            f"{len(rows)}"
        )

    candidate_keys = [
        (
            row["benchmark"],
            row["instance_id"],
            row["step_index"],
        )
        for row in rows
    ]

    if len(set(candidate_keys)) != EXPECTED_TOTAL:
        counts = Counter(candidate_keys)

        duplicates = [
            key
            for key, count in counts.items()
            if count != 1
        ]

        raise RuntimeError(
            "Duplicate candidate keys: "
            + repr(duplicates[:10])
        )

    prefix_hashes = [
        row["prefix_hash"]
        for row in rows
    ]

    if len(set(prefix_hashes)) != EXPECTED_TOTAL:
        raise RuntimeError(
            "Expected 631 unique prefix hashes."
        )

    rows.sort(
        key=lambda r: (
            r["benchmark"],
            r["instance_id"],
            r["step_index"],
        )
    )

    with MERGED.open(
        "w",
        encoding="utf-8",
    ) as f:
        for row in rows:
            f.write(
                json.dumps(
                    row,
                    sort_keys=True,
                )
                + "\n"
            )

    trajectories = defaultdict(list)

    for row in rows:
        trajectory_key = (
            row["benchmark"],
            row["instance_id"],
        )

        trajectories[
            trajectory_key
        ].append(row)

    selection_records = 0

    with SELECTIONS.open(
        "w",
        encoding="utf-8",
    ) as f:

        for trajectory_key in sorted(
            trajectories
        ):
            benchmark, instance_id = (
                trajectory_key
            )

            candidates = trajectories[
                trajectory_key
            ]

            T = len(candidates)

            ranked = sorted(
                candidates,
                key=lambda r: (
                    -r["risk_score"],
                    r["tie_key"],
                ),
            )

            for beta in BUDGETS:
                B = budget_size(
                    T,
                    beta,
                )

                selected = ranked[:B]

                if len(selected) != B:
                    raise RuntimeError(
                        "Exact-B selection failure: "
                        f"{benchmark} "
                        f"{instance_id} "
                        f"beta={beta}"
                    )

                for rank, row in enumerate(
                    selected,
                    1,
                ):
                    record = {
                        "project": "DECOUPLE",
                        "stage": "STEP2B_STEP_PRM_631",
                        "baseline": "Step-PRM",
                        "benchmark": benchmark,
                        "instance_id": instance_id,
                        "budget_fraction": beta,
                        "trajectory_candidate_count": T,
                        "exact_budget_B": B,
                        "selection_rank": rank,
                        "step_index": row["step_index"],
                        "prefix_hash": row["prefix_hash"],
                        "domain_verifier": row["domain_verifier"],
                        "model_id": row["model_id"],
                        "risk_score": row["risk_score"],
                        "tie_key": row["tie_key"],
                        "posthoc_access": False,
                    }

                    f.write(
                        json.dumps(
                            record,
                            sort_keys=True,
                        )
                        + "\n"
                    )

                    selection_records += 1

    benchmark_counts = dict(
        sorted(
            Counter(
                row["benchmark"]
                for row in rows
            ).items()
        )
    )

    verifier_counts = dict(
        sorted(
            Counter(
                row["domain_verifier"]
                for row in rows
            ).items()
        )
    )

    audit = {
        "project": "DECOUPLE",
        "stage": "STEP2B_STEP_PRM_631",
        "status": "PASS",
        "tool_candidate_count": len(
            tool_rows
        ),
        "math_candidate_count": len(
            math_rows
        ),
        "total_candidate_count": len(
            rows
        ),
        "expected_total": EXPECTED_TOTAL,
        "unique_candidate_keys": len(
            set(candidate_keys)
        ),
        "unique_prefix_hashes": len(
            set(prefix_hashes)
        ),
        "trajectory_count": len(
            trajectories
        ),
        "benchmark_counts": benchmark_counts,
        "verifier_counts": verifier_counts,
        "budget_fractions": BUDGETS,
        "selection_record_count": (
            selection_records
        ),
        "risk_finite": all(
            math.isfinite(
                row["risk_score"]
            )
            for row in rows
        ),
        "posthoc_access": False,
        "terra_calls": 0,
        "tie_serialization": (
            "instance_id<TAB>"
            "step_index<TAB>20260829"
        ),
        "tie_hash": "sha256",
        "tie_direction": "ascending",
        "merged_score_sha256": (
            sha256_file(MERGED)
        ),
        "selection_sha256": (
            sha256_file(SELECTIONS)
        ),
    }

    AUDIT.write_text(
        json.dumps(
            audit,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "project": "DECOUPLE",
        "stage": "STEP2B_STEP_PRM_631",
        "status": "FROZEN_PRE_OUTCOME",
        "inputs": {
            str(
                TOOL.relative_to(ROOT)
            ): sha256_file(TOOL),
            str(
                MATH.relative_to(ROOT)
            ): sha256_file(MATH),
        },
        "outputs": {
            str(
                MERGED.relative_to(ROOT)
            ): sha256_file(MERGED),
            str(
                SELECTIONS.relative_to(ROOT)
            ): sha256_file(SELECTIONS),
            str(
                AUDIT.relative_to(ROOT)
            ): sha256_file(AUDIT),
        },
        "posthoc_access": False,
        "terra_calls": 0,
    }

    MANIFEST.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("STATUS=PASS")
    print(
        f"TOOL_CANDIDATES="
        f"{len(tool_rows)}"
    )
    print(
        f"MATH_CANDIDATES="
        f"{len(math_rows)}"
    )
    print(
        f"TOTAL_CANDIDATES="
        f"{len(rows)}"
    )
    print(
        f"TRAJECTORIES="
        f"{len(trajectories)}"
    )
    print(
        f"SELECTION_RECORDS="
        f"{selection_records}"
    )
    print("POSTHOC_ACCESS=NO")
    print("TERRA_CALLS=0")
    print(
        "MERGED_SHA256="
        + sha256_file(MERGED)
    )
    print(
        "SELECTION_SHA256="
        + sha256_file(SELECTIONS)
    )
    print(
        "AUDIT_SHA256="
        + sha256_file(AUDIT)
    )
    print(
        "MANIFEST_SHA256="
        + sha256_file(MANIFEST)
    )


if __name__ == "__main__":
    main()
