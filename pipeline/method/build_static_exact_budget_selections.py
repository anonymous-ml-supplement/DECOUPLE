#!/usr/bin/env python3

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


ROOT = Path("__DECOUPLE_ROOT__")

PRE_SCORES = (
    ROOT
    / "10_PILOT/STEP1/04_OUTPUTS/"
      "STEP1F_PRE_SCORE/DECOUPLE_PRE/"
      "decouple_pre_scores.jsonl"
)

STEP1_FINAL = (
    ROOT
    / "10_PILOT/STEP1/07_MANIFESTS/"
      "STEP1G_CLOSURE/"
      "STEP1_FINAL_MANIFEST.json"
)

OUT = (
    ROOT
    / "10_PILOT/STEP2/04_OUTPUTS/"
      "STEP2A_STATIC_SELECTIONS"
)

AUDIT_DIR = (
    ROOT
    / "10_PILOT/STEP2/06_AUDIT/"
      "STEP2A_STATIC_SELECTIONS"
)

OUT_SCORES = OUT / "static_baseline_scores.jsonl"
OUT_SELECTIONS = OUT / "exact_budget_selections.jsonl"
OUT_MANIFEST = OUT / "static_selection_manifest.json"
OUT_AUDIT = AUDIT_DIR / "static_selection_audit.json"

MASTER_SEED = 20260829

BUDGETS = [
    0.05,
    0.10,
    0.15,
    0.20,
    0.25,
    0.50,
]

RANDOM_REPLICATES = 10


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(block)

    return h.hexdigest()


def load_jsonl(path):
    rows = []

    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    return rows


def budget_half_up(T, beta):
    return min(
        T,
        max(
            1,
            math.floor(
                beta * T + 0.5
            ),
        ),
    )


def hash_key(*parts):
    payload = "\t".join(
        str(x)
        for x in parts
    ).encode("utf-8")

    return hashlib.sha256(
        payload
    ).hexdigest()


def main():
    print("===== STEP2A STATIC PRE-INTERVENTION SELECTIONS =====")
    print("POSTHOC_ACCESS=NO")
    print("TERRA_CALLS=0")
    print("MASTER_SEED=20260829")

    final = json.loads(
        STEP1_FINAL.read_text(
            encoding="utf-8"
        )
    )

    if final["status"] != "PASS_FROZEN":
        raise RuntimeError(
            "STEP1 is not PASS_FROZEN."
        )

    if not final["ready_for_posthoc_evaluation"]:
        raise RuntimeError(
            "STEP1 freeze does not permit progression."
        )

    rows = load_jsonl(
        PRE_SCORES
    )

    if len(rows) != 631:
        raise RuntimeError(
            f"Expected 631 PRE scores, got {len(rows)}"
        )

    trajectories = defaultdict(list)

    for row in rows:
        key = (
            row["benchmark"],
            row["instance_id"],
        )

        trajectories[key].append(row)

    if len(trajectories) != 100:
        raise RuntimeError(
            f"Expected 100 trajectories, got {len(trajectories)}"
        )

    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    AUDIT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    score_rows = []
    selection_rows = []

    expected_selection_count = 0

    for (
        benchmark,
        instance_id,
    ), traj in sorted(
        trajectories.items()
    ):
        traj.sort(
            key=lambda r: int(
                r["step_index"]
            )
        )

        T = len(traj)

        for row in traj:
            t = int(
                row["step_index"]
            )

            score_rows.append({
                "benchmark":
                    benchmark,
                "instance_id":
                    instance_id,
                "step_index":
                    t,
                "prefix_hash":
                    row["prefix_hash"],
                "method":
                    "DECOUPLE",
                "score":
                    float(
                        row["s_DECOUPLE"]
                    ),
                "tie_key_sha256":
                    row[
                        "tie_key_sha256"
                    ],
                "posthoc_access":
                    False,
            })

            score_rows.append({
                "benchmark":
                    benchmark,
                "instance_id":
                    instance_id,
                "step_index":
                    t,
                "prefix_hash":
                    row["prefix_hash"],
                "method":
                    "p-only",
                "score":
                    float(
                        row["p_t_raw"]
                    ),
                "tie_key_sha256":
                    row[
                        "tie_key_sha256"
                    ],
                "posthoc_access":
                    False,
            })

            score_rows.append({
                "benchmark":
                    benchmark,
                "instance_id":
                    instance_id,
                "step_index":
                    t,
                "prefix_hash":
                    row["prefix_hash"],
                "method":
                    "H-only",
                "score":
                    float(
                        row["H_hat_raw"]
                    ),
                "tie_key_sha256":
                    row[
                        "tie_key_sha256"
                    ],
                "posthoc_access":
                    False,
            })

        deterministic_methods = {
            "DECOUPLE":
                "s_DECOUPLE",
            "p-only":
                "p_t_raw",
            "H-only":
                "H_hat_raw",
        }

        for beta in BUDGETS:
            B = budget_half_up(
                T,
                beta,
            )

            for method, field in deterministic_methods.items():
                ranked = sorted(
                    traj,
                    key=lambda r: (
                        -float(
                            r[field]
                        ),
                        r[
                            "tie_key_sha256"
                        ],
                    ),
                )

                selected = ranked[:B]

                expected_selection_count += B

                for rank, row in enumerate(
                    selected,
                    start=1,
                ):
                    selection_rows.append({
                        "benchmark":
                            benchmark,
                        "instance_id":
                            instance_id,
                        "method":
                            method,
                        "random_replicate":
                            None,
                        "budget_fraction":
                            beta,
                        "T":
                            T,
                        "B":
                            B,
                        "selection_rank":
                            rank,
                        "step_index":
                            int(
                                row[
                                    "step_index"
                                ]
                            ),
                        "score":
                            float(
                                row[
                                    field
                                ]
                            ),
                        "tie_key_sha256":
                            row[
                                "tie_key_sha256"
                            ],
                        "prefix_hash":
                            row[
                                "prefix_hash"
                            ],
                        "posthoc_access":
                            False,
                    })

            for replicate in range(
                1,
                RANDOM_REPLICATES + 1,
            ):
                ranked = sorted(
                    traj,
                    key=lambda r: hash_key(
                        benchmark,
                        instance_id,
                        int(
                            r["step_index"]
                        ),
                        replicate,
                        MASTER_SEED,
                    ),
                )

                selected = ranked[:B]

                expected_selection_count += B

                for rank, row in enumerate(
                    selected,
                    start=1,
                ):
                    random_key = hash_key(
                        benchmark,
                        instance_id,
                        int(
                            row[
                                "step_index"
                            ]
                        ),
                        replicate,
                        MASTER_SEED,
                    )

                    selection_rows.append({
                        "benchmark":
                            benchmark,
                        "instance_id":
                            instance_id,
                        "method":
                            "Random",
                        "random_replicate":
                            replicate,
                        "budget_fraction":
                            beta,
                        "T":
                            T,
                        "B":
                            B,
                        "selection_rank":
                            rank,
                        "step_index":
                            int(
                                row[
                                    "step_index"
                                ]
                            ),
                        "score":
                            None,
                        "tie_key_sha256":
                            random_key,
                        "prefix_hash":
                            row[
                                "prefix_hash"
                            ],
                        "posthoc_access":
                            False,
                    })

    score_rows.sort(
        key=lambda r: (
            r["benchmark"],
            r["instance_id"],
            r["method"],
            r["step_index"],
        )
    )

    selection_rows.sort(
        key=lambda r: (
            r["benchmark"],
            r["instance_id"],
            r["method"],
            (
                r["random_replicate"]
                if r["random_replicate"] is not None
                else 0
            ),
            r["budget_fraction"],
            r["selection_rank"],
        )
    )

    with OUT_SCORES.open(
        "w",
        encoding="utf-8",
    ) as f:
        for row in score_rows:
            f.write(
                json.dumps(
                    row,
                    sort_keys=True,
                    ensure_ascii=False,
                )
                + "\n"
            )

    with OUT_SELECTIONS.open(
        "w",
        encoding="utf-8",
    ) as f:
        for row in selection_rows:
            f.write(
                json.dumps(
                    row,
                    sort_keys=True,
                    ensure_ascii=False,
                )
                + "\n"
            )

    audit = {
        "status":
            "PASS",
        "trajectory_count":
            len(
                trajectories
            ),
        "candidate_count":
            len(rows),
        "score_record_count":
            len(score_rows),
        "selection_record_count":
            len(selection_rows),
        "expected_selection_record_count":
            expected_selection_count,
        "budgets":
            BUDGETS,
        "budget_rule":
            "half_up_min1_capT",
        "random_replicates":
            RANDOM_REPLICATES,
        "master_seed":
            MASTER_SEED,
        "methods_frozen": [
            "DECOUPLE",
            "p-only",
            "H-only",
            "Random",
        ],
        "posthoc_access":
            False,
        "terra_calls":
            0,
    }

    if (
        len(selection_rows)
        != expected_selection_count
    ):
        raise RuntimeError(
            "Selection count mismatch."
        )

    OUT_AUDIT.write_text(
        json.dumps(
            audit,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "status":
            "FROZEN",
        "stage":
            "STEP2A_STATIC_PRE_INTERVENTION_SELECTIONS",
        "step1_final_manifest": {
            "path":
                str(
                    STEP1_FINAL.relative_to(
                        ROOT
                    )
                ),
            "sha256":
                sha256_file(
                    STEP1_FINAL
                ),
        },
        "pre_score_input": {
            "path":
                str(
                    PRE_SCORES.relative_to(
                        ROOT
                    )
                ),
            "sha256":
                sha256_file(
                    PRE_SCORES
                ),
        },
        "budget_fractions":
            BUDGETS,
        "methods": [
            "DECOUPLE",
            "p-only",
            "H-only",
            "Random",
        ],
        "random_replicates":
            RANDOM_REPLICATES,
        "outputs": {
            "scores_sha256":
                sha256_file(
                    OUT_SCORES
                ),
            "selections_sha256":
                sha256_file(
                    OUT_SELECTIONS
                ),
            "audit_sha256":
                sha256_file(
                    OUT_AUDIT
                ),
        },
        "implementation_sha256":
            sha256_file(
                Path(
                    __file__
                ).resolve()
            ),
        "posthoc_access":
            False,
        "next":
            "COMPATIBLE_PRM_AND_OUTCOME_BASELINE_SCORING",
    }

    OUT_MANIFEST.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("===== FINAL =====")
    print("TRAJECTORIES=100")
    print("CANDIDATES=631")
    print("METHODS=4")
    print("RANDOM_REPLICATES=10")
    print(
        "BUDGETS="
        + ",".join(
            str(x)
            for x in BUDGETS
        )
    )
    print(
        "SCORE_RECORDS="
        + str(
            len(
                score_rows
            )
        )
    )
    print(
        "SELECTION_RECORDS="
        + str(
            len(
                selection_rows
            )
        )
    )
    print("POSTHOC_ACCESS=NO")
    print("TERRA_CALLS=0")
    print("STATUS=PASS")
    print(
        "NEXT=COMPATIBLE_PRM_AND_OUTCOME_BASELINE_SCORING"
    )


if __name__ == "__main__":
    main()
