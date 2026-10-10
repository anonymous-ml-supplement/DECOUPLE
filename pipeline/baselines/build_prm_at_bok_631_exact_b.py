#!/usr/bin/env python3

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path("__EXTERNAL_PRM_WORKSPACE__")
BASE = ROOT / "10_PILOT/STEP2"

TOOL_ROOT = BASE / "04_OUTPUTS/STEP2B3_PRM_AT_BOK/TOOL"
MATH_ROOT = BASE / "04_OUTPUTS/STEP2B3_PRM_AT_BOK/MATH"

OUTDIR = BASE / "04_OUTPUTS/STEP2B3_PRM_AT_BOK/FINAL"
AUDITDIR = BASE / "06_AUDIT/STEP2B3_PRM_AT_BOK/FINAL"
DOCDIR = ROOT / "03_TECHNICAL_DOCS/02_STEP2"

SCORES_OUT = OUTDIR / "prm_at_bok_631_scores.jsonl"
SELECT_OUT = OUTDIR / "prm_at_bok_exact_b_selections.jsonl"
AUDIT_OUT = AUDITDIR / "prm_at_bok_631_audit.json"
MANIFEST_OUT = AUDITDIR / "prm_at_bok_631_manifest.json"
CLOSURE_OUT = DOCDIR / "STEP2B3_PRM_AT_BOK_CLOSURE_20260906.md"

MASTER_SEED = 20260829
BETAS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.50]

EXPECTED_TOOL = 288
EXPECTED_MATH = 343
EXPECTED_TOTAL = 631
EXPECTED_TOOL_PROPOSALS = 2304
EXPECTED_MATH_PROPOSALS = 2744
EXPECTED_PROPOSALS = 5048


def fail(msg):
    raise RuntimeError(msg)


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path):
    rows = []
    with Path(path).open("r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception as exc:
                fail(f"JSON parse failure {path}:{ln}: {exc}")
    return rows


def step_key(row):
    return (
        str(row.get("benchmark")),
        str(row.get("instance_id")),
        int(row.get("step_index")),
    )


def tie_hash(instance_id, step_index):
    raw = f"{instance_id}\t{step_index}\t{MASTER_SEED}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def half_up_budget(beta, T):
    return min(T, max(1, math.floor(beta * T + 0.5)))


def validate_pre(row, where):
    forbidden = {
        "correct", "correctness", "label", "reward",
        "episode_reward", "final_reward", "outcome", "success",
        "ground_truth", "gold_answer", "self_repair", "repair_label",
        "oracle", "oracle_rank", "intervention_gain", "realized_gain",
        "future_observation", "next_observation", "post_state",
        "verified_outcome", "unchecked_outcome",
        "terminal_reward", "terminal_success",
        "possible_answer", "path", "missed_function",
        "excluded_function", "action_chosen", "action_rejected",
    }

    # Explicit scorer fields are permitted only when they are PRM predictions,
    # not retrospective benchmark outcomes.
    allowed_score_fields = {
        "official_genprm_reward",
        "step_rewards",
    }

    def walk(obj, loc):
        if isinstance(obj, dict):
            for k, v in obj.items():
                kl = str(k).lower()
                if kl in forbidden and kl not in allowed_score_fields:
                    fail(f"Forbidden POST field at {where}:{loc}.{k}")
                walk(v, f"{loc}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{loc}[{i}]")

    walk(row, "root")

    if row.get("posthoc_access") is not False:
        fail(f"posthoc_access != false at {where}")

    if "terra_calls" in row and int(row["terra_calls"]) != 0:
        fail(f"terra_calls != 0 at {where}")


def read_domain(files, score_field, expected_rows, domain_name):
    per_k = []
    input_hashes = {}

    for k_idx, path in enumerate(files, 1):
        if not path.exists():
            fail(f"Missing {domain_name} K{k_idx:02d}: {path}")

        rows = load_jsonl(path)

        if len(rows) != expected_rows:
            fail(
                f"{domain_name} K{k_idx:02d} rows "
                f"{len(rows)} != {expected_rows}"
            )

        keys = set()
        mapped = {}

        for row in rows:
            validate_pre(row, f"{domain_name}/K{k_idx:02d}")
            key = step_key(row)

            if key in keys:
                fail(f"Duplicate {domain_name} key K{k_idx:02d}: {key}")
            keys.add(key)

            score = float(row[score_field])
            if not math.isfinite(score):
                fail(f"Non-finite score {domain_name} K{k_idx:02d}: {key}")

            mapped[key] = {
                "score": score,
                "row": row,
            }

        per_k.append(mapped)
        input_hashes[str(path)] = sha256_file(path)

    base_keys = set(per_k[0])

    for k_idx, mapped in enumerate(per_k[1:], 2):
        if set(mapped) != base_keys:
            fail(f"{domain_name} key mismatch at K{k_idx:02d}")

    aggregated = []

    for key in sorted(base_keys):
        scores = [mapped[key]["score"] for mapped in per_k]
        best_score = max(scores)
        best_k = scores.index(best_score) + 1

        exemplar = per_k[0][key]["row"]
        benchmark, instance_id, step_index = key

        aggregated.append({
            "project": "DECOUPLE",
            "stage": "STEP2B3_PRM_AT_BOK",
            "baseline": "PRM@BoK",
            "benchmark": benchmark,
            "instance_id": instance_id,
            "step_index": step_index,
            "candidate_kind": exemplar.get("candidate_kind"),
            "proposal_count": 8,
            "proposal_scores": scores,
            "best_prm_score": best_score,
            "best_k": best_k,
            "prm_at_bok_risk": 1.0 - best_score,
            "tie_hash": tie_hash(instance_id, step_index),
            "model_id": exemplar.get("model_id"),
            "posthoc_access": False,
            "terra_calls": 0,
        })

    return aggregated, input_hashes


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    AUDITDIR.mkdir(parents=True, exist_ok=True)
    DOCDIR.mkdir(parents=True, exist_ok=True)

    tool_files = [
        TOOL_ROOT / f"k{k:02d}/tool_step_prm_scores.jsonl"
        for k in range(1, 9)
    ]

    math_files = [
        MATH_ROOT / f"math_prm_k{k:02d}_scores.jsonl"
        for k in range(1, 9)
    ]

    tool_rows, tool_hashes = read_domain(
        tool_files,
        "process_correctness_score",
        EXPECTED_TOOL,
        "TOOL",
    )

    math_rows, math_hashes = read_domain(
        math_files,
        "step_prm_score",
        EXPECTED_MATH,
        "MATH",
    )

    if len(tool_rows) != EXPECTED_TOOL:
        fail("Tool aggregate count mismatch")

    if len(math_rows) != EXPECTED_MATH:
        fail("Math aggregate count mismatch")

    all_rows = tool_rows + math_rows

    if len(all_rows) != EXPECTED_TOTAL:
        fail(f"Total aggregate count {len(all_rows)} != {EXPECTED_TOTAL}")

    all_keys = [step_key(x) for x in all_rows]

    if len(set(all_keys)) != EXPECTED_TOTAL:
        fail("631 aggregate keys are not unique")

    all_rows.sort(
        key=lambda x: (
            str(x["benchmark"]),
            str(x["instance_id"]),
            int(x["step_index"]),
        )
    )

    with SCORES_OUT.open("w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    by_instance = defaultdict(list)

    for row in all_rows:
        traj_key = (
            str(row["benchmark"]),
            str(row["instance_id"]),
        )
        by_instance[traj_key].append(row)

    selection_rows = []

    for (benchmark, instance_id), rows in sorted(by_instance.items()):
        T = len(rows)

        ranked = sorted(
            rows,
            key=lambda x: (
                -float(x["prm_at_bok_risk"]),
                str(x["tie_hash"]),
            ),
        )

        for beta in BETAS:
            B = half_up_budget(beta, T)
            selected = ranked[:B]

            for rank, row in enumerate(selected, 1):
                selection_rows.append({
                    "project": "DECOUPLE",
                    "stage": "STEP2B3_PRM_AT_BOK",
                    "baseline": "PRM@BoK",
                    "benchmark": benchmark,
                    "instance_id": instance_id,
                    "beta": beta,
                    "trajectory_candidate_count": T,
                    "budget_B": B,
                    "selection_rank": rank,
                    "step_index": int(row["step_index"]),
                    "best_prm_score": float(row["best_prm_score"]),
                    "prm_at_bok_risk": float(row["prm_at_bok_risk"]),
                    "tie_hash": row["tie_hash"],
                    "posthoc_access": False,
                })

    with SELECT_OUT.open("w", encoding="utf-8") as f:
        for row in selection_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    score_values = [float(x["best_prm_score"]) for x in all_rows]
    risk_values = [float(x["prm_at_bok_risk"]) for x in all_rows]

    if not all(math.isfinite(x) for x in score_values + risk_values):
        fail("Non-finite aggregate score detected")

    for row in all_rows:
        if abs(
            float(row["prm_at_bok_risk"])
            - (1.0 - float(row["best_prm_score"]))
        ) > 1e-12:
            fail("Risk transform mismatch")

    input_hashes = {}
    input_hashes.update(tool_hashes)
    input_hashes.update(math_hashes)

    audit = {
        "project": "DECOUPLE",
        "stage": "STEP2B3_PRM_AT_BOK",
        "status": "PASS",
        "method": "PRM@BoK",
        "tool_candidates": EXPECTED_TOOL,
        "math_candidates": EXPECTED_MATH,
        "total_candidates": EXPECTED_TOTAL,
        "tool_proposal_scores": EXPECTED_TOOL_PROPOSALS,
        "math_proposal_scores": EXPECTED_MATH_PROPOSALS,
        "total_proposal_scores": EXPECTED_PROPOSALS,
        "k": 8,
        "aggregation": "max_prm_correctness_score_over_k",
        "risk_transform": "1-best_prm_score",
        "master_seed": MASTER_SEED,
        "budget_rule": "min(T,max(1,floor(beta*T+0.5)))",
        "betas": BETAS,
        "tie_rule": "SHA256(instance_id<TAB>step_index<TAB>20260829), ascending",
        "trajectory_count": len(by_instance),
        "selection_record_count": len(selection_rows),
        "score_finite": True,
        "best_score_min": min(score_values),
        "best_score_max": max(score_values),
        "risk_min": min(risk_values),
        "risk_max": max(risk_values),
        "posthoc_access": False,
        "terra_calls": 0,
        "score_output_sha256": sha256_file(SCORES_OUT),
        "selection_output_sha256": sha256_file(SELECT_OUT),
    }

    AUDIT_OUT.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "project": "DECOUPLE",
        "stage": "STEP2B3_PRM_AT_BOK",
        "status": "PASS_FROZEN",
        "scientific_authority": "Spec3",
        "input_file_sha256": input_hashes,
        "outputs": {
            str(SCORES_OUT): sha256_file(SCORES_OUT),
            str(SELECT_OUT): sha256_file(SELECT_OUT),
            str(AUDIT_OUT): sha256_file(AUDIT_OUT),
        },
        "tool_model_revision":
            "b89a8956c8a39c75f8cc25064455c33f8f8831f2",
        "math_model_revision":
            "0ea3fa755896b5448a33458fd0b010501dbea21e",
        "tool_runtime":
            "__TOOL_PRM_ENV__/bin/python",
        "math_runtime":
            "__MATH_PRM_ENV__/bin/python",
        "tool_formal_job": "3733587",
        "math_timeout_job": "3733588",
        "math_resume_job": "3733778",
        "post_allowed": False,
    }

    MANIFEST_OUT.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    closure = f"""# STEP2B3 PRM@BoK Closure

STATUS=PASS_FROZEN

BIG_STEP=STEP2
SUBSTEP=STEP2B3_PRM_AT_BOK

Scientific authority: Spec3.

## Formal scorer coverage

Tool domain:
- BFCL candidates: 228
- ToolAlpaca candidates: 60
- Tool candidates: 288
- K: 8
- Proposal scores: 2304
- Formal job: 3733587
- Runtime: __TOOL_PRM_ENV__
- Model revision: b89a8956c8a39c75f8cc25064455c33f8f8831f2
- Status: PASS

Math domain:
- Math-Shepherd candidates: 343
- K: 8
- Proposal scores: 2744
- Original job: 3733588
- Original scheduler result: TIMEOUT
- Frozen partial K08 rows: 291
- Resume job: 3733778
- Final Math K01-K08: 2744/2744
- Runtime: __MATH_PRM_ENV__
- Model revision: 0ea3fa755896b5448a33458fd0b010501dbea21e
- Status: PASS

## PRM@BoK aggregation

Total archived candidate steps: 631.
Total frozen proposal scores: 5048.

For each archived step:

best_prm_score_t = max over the eight frozen PRM proposal scores.

prm_at_bok_risk_t = 1 - best_prm_score_t.

The archived base trajectory is not replaced by the sampled proposal.

## Exact budget

Budgets:
0.05, 0.10, 0.15, 0.20, 0.25, 0.50.

B_beta = min(T, max(1, floor(beta*T + 0.5))).

Ranking:
descending prm_at_bok_risk_t.

Tie rule:
SHA256(instance_id<TAB>step_index<TAB>20260829), ascending.

## PRE / POST

POSTHOC_ACCESS=NO
TERRA_CALLS=0
PRIMARY_K8_REGENERATED=NO
POST_ALLOWED=NO

## Final artifacts

Score rows: {len(all_rows)}
Selection rows: {len(selection_rows)}
Trajectories: {len(by_instance)}

SCORES_SHA256={sha256_file(SCORES_OUT)}
SELECTIONS_SHA256={sha256_file(SELECT_OUT)}
AUDIT_SHA256={sha256_file(AUDIT_OUT)}
MANIFEST_SHA256={sha256_file(MANIFEST_OUT)}

STEP2B3_PRM_AT_BOK=PASS_FROZEN

NEXT=STEP2B4_AGENTPRM_AUTHORITY_AND_COMPATIBILITY_CLOSURE
"""

    CLOSURE_OUT.write_text(closure, encoding="utf-8")

    print("===== STEP2B3 FINAL =====")
    print(f"TOOL_CANDIDATES={EXPECTED_TOOL}")
    print(f"MATH_CANDIDATES={EXPECTED_MATH}")
    print(f"TOTAL_CANDIDATES={len(all_rows)}")
    print(f"TOOL_PROPOSALS={EXPECTED_TOOL_PROPOSALS}")
    print(f"MATH_PROPOSALS={EXPECTED_MATH_PROPOSALS}")
    print(f"TOTAL_PROPOSALS={EXPECTED_PROPOSALS}")
    print(f"TRAJECTORIES={len(by_instance)}")
    print(f"SELECTION_RECORDS={len(selection_rows)}")
    print(f"BEST_SCORE_MIN={min(score_values)}")
    print(f"BEST_SCORE_MAX={max(score_values)}")
    print(f"RISK_MIN={min(risk_values)}")
    print(f"RISK_MAX={max(risk_values)}")
    print("POSTHOC_ACCESS=NO")
    print("TERRA_CALLS=0")
    print(f"SCORES_SHA256={sha256_file(SCORES_OUT)}")
    print(f"SELECTIONS_SHA256={sha256_file(SELECT_OUT)}")
    print(f"AUDIT_SHA256={sha256_file(AUDIT_OUT)}")
    print(f"MANIFEST_SHA256={sha256_file(MANIFEST_OUT)}")
    print(f"CLOSURE_SHA256={sha256_file(CLOSURE_OUT)}")
    print("STATUS=PASS")


if __name__ == "__main__":
    main()
