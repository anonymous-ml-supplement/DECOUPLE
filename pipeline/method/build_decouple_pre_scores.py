#!/usr/bin/env python3

import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path("__DECOUPLE_ROOT__")

PT_PATH = (
    ROOT
    / "10_PILOT/STEP1/04_OUTPUTS/"
      "STEP1D_SEMANTIC/SEMANTIC_CLASSES_PT/"
      "semantic_candidate_scores.jsonl"
)

HHAT_PATH = (
    ROOT
    / "10_PILOT/STEP1/04_OUTPUTS/"
      "STEP1E_GRAPH/HYBRID_GRAPH_HHAT/"
      "structural_harm_scores.jsonl"
)

OUT = (
    ROOT
    / "10_PILOT/STEP1/04_OUTPUTS/"
      "STEP1F_PRE_SCORE/DECOUPLE_PRE"
)

OUT_GATES = OUT / "trajectory_signal_gates.jsonl"
OUT_SCORES = OUT / "decouple_pre_scores.jsonl"
OUT_RANKINGS = OUT / "decouple_pre_rankings.jsonl"
OUT_AUDIT = OUT / "decouple_pre_audit.json"
OUT_COMPUTE = OUT / "compute_ledger.json"
OUT_MANIFEST = OUT / "decouple_pre_manifest.json"

MASTER_SEED = 20260829
FINITE_COVERAGE_THRESHOLD = 0.95
RANGE_THRESHOLD = 1e-8

EXPECTED_TRAJECTORIES = 100
EXPECTED_CANDIDATES = 631

EXPECTED_BENCHMARK_COUNTS = {
    "BFCL": 228,
    "Math-Shepherd": 343,
    "ToolAlpaca": 60,
}


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)

            if not b:
                break

            h.update(b)

    return h.hexdigest()


def load_jsonl(path):
    rows = []

    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(
                    json.loads(line)
                )

    return rows


def finite(x):
    return (
        isinstance(x, (int, float))
        and math.isfinite(float(x))
    )


def signal_gate(values):
    """
    Implements spec2 Eq. 37.

    A(z)=1 iff:
      finite coverage >= 0.95
      and
      max(finite z)-min(finite z) > 1e-8.

    Gate is decided before any imputation.

    If the signal is available and missing values exist,
    missing values are subsequently imputed by the
    within-trajectory median of finite values.
    """

    n = len(values)

    if n == 0:
        raise RuntimeError(
            "Cannot gate an empty trajectory."
        )

    finite_values = [
        float(x)
        for x in values
        if finite(x)
    ]

    coverage = (
        len(finite_values)
        / n
    )

    if finite_values:
        signal_min = min(
            finite_values
        )
        signal_max = max(
            finite_values
        )
        signal_range = (
            signal_max
            - signal_min
        )
    else:
        signal_min = None
        signal_max = None
        signal_range = None

    available = (
        coverage
        >= FINITE_COVERAGE_THRESHOLD
        and signal_range is not None
        and signal_range
        > RANGE_THRESHOLD
    )

    median = (
        statistics.median(
            finite_values
        )
        if finite_values
        else None
    )

    imputed = []

    for value in values:
        if finite(value):
            imputed.append(
                float(value)
            )
        elif available:
            if median is None:
                raise RuntimeError(
                    "Available signal has no median."
                )

            imputed.append(
                float(median)
            )
        else:
            imputed.append(None)

    return {
        "available":
            bool(available),
        "finite_count":
            len(finite_values),
        "total_count":
            n,
        "finite_coverage":
            coverage,
        "minimum":
            signal_min,
        "maximum":
            signal_max,
        "range":
            signal_range,
        "median":
            median,
        "missing_count":
            n - len(finite_values),
        "imputed_values":
            imputed,
    }


def tie_key(
    instance_id,
    step_index,
):
    """
    Deterministic operationalization of spec2 Eq. 41:

        Hash(instance_id, t, 20260829)

    Canonical byte serialization is:
        UTF-8(instance_id<TAB>t<TAB>master_seed)

    Smaller SHA256 hexadecimal value ranks first.
    """

    payload = (
        f"{instance_id}\t"
        f"{int(step_index)}\t"
        f"{MASTER_SEED}"
    ).encode("utf-8")

    return hashlib.sha256(
        payload
    ).hexdigest()


def main():
    print(
        "===== STEP1F SIGNAL GATES "
        "+ DECOUPLE PRE SCORE ====="
    )

    print(
        "FINITE_COVERAGE_THRESHOLD=0.95"
    )

    print(
        "RANGE_THRESHOLD=1e-8"
    )

    print(
        "MASTER_SEED=20260829"
    )

    print(
        "POSTHOC_ACCESS=NO"
    )

    print(
        "TERRA_CALLS=0"
    )

    pt_rows = load_jsonl(
        PT_PATH
    )

    hhat_rows = load_jsonl(
        HHAT_PATH
    )

    if (
        len(pt_rows)
        != EXPECTED_CANDIDATES
    ):
        raise RuntimeError(
            "p_t candidate count mismatch."
        )

    if (
        len(hhat_rows)
        != EXPECTED_CANDIDATES
    ):
        raise RuntimeError(
            "H_hat candidate count mismatch."
        )

    pt = {}

    for row in pt_rows:
        key = (
            row["benchmark"],
            row["instance_id"],
            int(row["step_index"]),
        )

        if key in pt:
            raise RuntimeError(
                "Duplicate p_t key: "
                + repr(key)
            )

        pt[key] = row

    hhat = {}

    for row in hhat_rows:
        key = (
            row["benchmark"],
            row["instance_id"],
            int(row["step_index"]),
        )

        if key in hhat:
            raise RuntimeError(
                "Duplicate H_hat key: "
                + repr(key)
            )

        hhat[key] = row

    if set(pt) != set(hhat):
        missing_h = sorted(
            set(pt) - set(hhat)
        )

        missing_p = sorted(
            set(hhat) - set(pt)
        )

        raise RuntimeError(
            "p_t/H_hat key mismatch. "
            f"missing_h={missing_h[:5]} "
            f"missing_p={missing_p[:5]}"
        )

    trajectories = defaultdict(
        list
    )

    benchmark_counts = Counter()

    for key in sorted(pt):
        benchmark, instance_id, step_index = key

        trajectories[
            (
                benchmark,
                instance_id,
            )
        ].append(
            step_index
        )

        benchmark_counts[
            benchmark
        ] += 1

    if (
        len(trajectories)
        != EXPECTED_TRAJECTORIES
    ):
        raise RuntimeError(
            "Trajectory count mismatch."
        )

    if (
        dict(benchmark_counts)
        != EXPECTED_BENCHMARK_COUNTS
    ):
        raise RuntimeError(
            "Benchmark candidate counts mismatch: "
            + repr(
                dict(
                    benchmark_counts
                )
            )
        )

    gate_outputs = []
    score_outputs = []
    ranking_outputs = []

    gate_regimes = Counter()

    p_available_count = 0
    h_available_count = 0
    both_available_count = 0
    fallback_trajectory_count = 0

    p_missing_total = 0
    h_missing_total = 0

    for (
        benchmark,
        instance_id,
    ), step_indices in sorted(
        trajectories.items()
    ):
        step_indices = sorted(
            step_indices
        )

        expected = list(
            range(
                1,
                len(step_indices) + 1,
            )
        )

        if step_indices != expected:
            raise RuntimeError(
                "Non-contiguous trajectory steps: "
                f"{benchmark}/{instance_id}"
            )

        p_values = [
            pt[
                (
                    benchmark,
                    instance_id,
                    t,
                )
            ]["p_t"]
            for t in step_indices
        ]

        h_values = [
            hhat[
                (
                    benchmark,
                    instance_id,
                    t,
                )
            ]["H_hat"]
            for t in step_indices
        ]

        p_gate = signal_gate(
            p_values
        )

        h_gate = signal_gate(
            h_values
        )

        Ap = int(
            p_gate[
                "available"
            ]
        )

        AH = int(
            h_gate[
                "available"
            ]
        )

        p_available_count += Ap
        h_available_count += AH

        if Ap == 1 and AH == 1:
            regime = "product"
            both_available_count += 1

        elif Ap == 1 and AH == 0:
            regime = "p_only_fallback"
            fallback_trajectory_count += 1

        elif Ap == 0 and AH == 1:
            regime = "H_only_fallback"
            fallback_trajectory_count += 1

        else:
            regime = "zero_fallback"
            fallback_trajectory_count += 1

        gate_regimes[
            regime
        ] += 1

        p_missing_total += (
            p_gate[
                "missing_count"
            ]
        )

        h_missing_total += (
            h_gate[
                "missing_count"
            ]
        )

        gate_outputs.append(
            {
                "benchmark":
                    benchmark,
                "instance_id":
                    instance_id,
                "T":
                    len(
                        step_indices
                    ),
                "A_p":
                    Ap,
                "A_H":
                    AH,
                "regime":
                    regime,
                "p_gate": {
                    k: v
                    for k, v
                    in p_gate.items()
                    if k
                    != "imputed_values"
                },
                "H_gate": {
                    k: v
                    for k, v
                    in h_gate.items()
                    if k
                    != "imputed_values"
                },
            }
        )

        trajectory_scores = []

        for pos, t in enumerate(
            step_indices
        ):
            raw_p = p_values[
                pos
            ]

            raw_h = h_values[
                pos
            ]

            p_value = (
                p_gate[
                    "imputed_values"
                ][pos]
            )

            h_value = (
                h_gate[
                    "imputed_values"
                ][pos]
            )

            if Ap == 1 and AH == 1:
                score = (
                    p_value
                    * h_value
                )
                score_rule = "p_times_H"

            elif Ap == 1 and AH == 0:
                score = p_value
                score_rule = "p_only"

            elif Ap == 0 and AH == 1:
                score = h_value
                score_rule = "H_only"

            else:
                score = 0.0
                score_rule = "zero"

            if not math.isfinite(
                float(score)
            ):
                raise RuntimeError(
                    "Non-finite DECOUPLE score."
                )

            key = tie_key(
                instance_id,
                t,
            )

            row = {
                "benchmark":
                    benchmark,
                "instance_id":
                    instance_id,
                "step_index":
                    t,
                "T":
                    len(
                        step_indices
                    ),
                "prefix_hash":
                    pt[
                        (
                            benchmark,
                            instance_id,
                            t,
                        )
                    ][
                        "prefix_hash"
                    ],
                "p_t_raw":
                    raw_p,
                "H_hat_raw":
                    raw_h,
                "p_t_used":
                    p_value
                    if Ap == 1
                    else None,
                "H_hat_used":
                    h_value
                    if AH == 1
                    else None,
                "A_p":
                    Ap,
                "A_H":
                    AH,
                "score_rule":
                    score_rule,
                "s_DECOUPLE":
                    float(score),
                "tie_key_sha256":
                    key,
                "tie_key_serialization":
                    (
                        f"{instance_id}\\t"
                        f"{t}\\t"
                        f"{MASTER_SEED}"
                    ),
                "master_seed":
                    MASTER_SEED,
            }

            score_outputs.append(
                row
            )

            trajectory_scores.append(
                row
            )

        ranked = sorted(
            trajectory_scores,
            key=lambda r: (
                -r[
                    "s_DECOUPLE"
                ],
                r[
                    "tie_key_sha256"
                ],
            ),
        )

        for rank, row in enumerate(
            ranked,
            start=1,
        ):
            ranking_outputs.append(
                {
                    "benchmark":
                        benchmark,
                    "instance_id":
                        instance_id,
                    "rank":
                        rank,
                    "step_index":
                        row[
                            "step_index"
                        ],
                    "s_DECOUPLE":
                        row[
                            "s_DECOUPLE"
                        ],
                    "tie_key_sha256":
                        row[
                            "tie_key_sha256"
                        ],
                    "A_p":
                        row[
                            "A_p"
                        ],
                    "A_H":
                        row[
                            "A_H"
                        ],
                    "score_rule":
                        row[
                            "score_rule"
                        ],
                }
            )

    if (
        len(score_outputs)
        != EXPECTED_CANDIDATES
    ):
        raise RuntimeError(
            "Score output count mismatch."
        )

    if (
        len(ranking_outputs)
        != EXPECTED_CANDIDATES
    ):
        raise RuntimeError(
            "Ranking output count mismatch."
        )

    score_outputs.sort(
        key=lambda r: (
            r["benchmark"],
            r["instance_id"],
            r["step_index"],
        )
    )

    gate_outputs.sort(
        key=lambda r: (
            r["benchmark"],
            r["instance_id"],
        )
    )

    ranking_outputs.sort(
        key=lambda r: (
            r["benchmark"],
            r["instance_id"],
            r["rank"],
        )
    )

    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    def write_jsonl(
        path,
        rows,
    ):
        with path.open(
            "w",
            encoding="utf-8",
        ) as f:
            for row in rows:
                f.write(
                    json.dumps(
                        row,
                        sort_keys=True,
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    write_jsonl(
        OUT_GATES,
        gate_outputs,
    )

    write_jsonl(
        OUT_SCORES,
        score_outputs,
    )

    write_jsonl(
        OUT_RANKINGS,
        ranking_outputs,
    )

    scores = [
        r["s_DECOUPLE"]
        for r in score_outputs
    ]

    audit = {
        "status":
            "PASS",
        "trajectory_count":
            len(
                trajectories
            ),
        "candidate_count":
            len(
                score_outputs
            ),
        "benchmark_candidate_counts":
            dict(
                sorted(
                    benchmark_counts.items()
                )
            ),
        "finite_coverage_threshold":
            FINITE_COVERAGE_THRESHOLD,
        "range_threshold":
            RANGE_THRESHOLD,
        "master_seed":
            MASTER_SEED,
        "tie_hash":
            "sha256",
        "tie_serialization":
            "instance_id<TAB>step_index<TAB>20260829",
        "p_available_trajectories":
            p_available_count,
        "H_available_trajectories":
            h_available_count,
        "both_available_trajectories":
            both_available_count,
        "fallback_trajectories":
            fallback_trajectory_count,
        "gate_regimes":
            dict(
                sorted(
                    gate_regimes.items()
                )
            ),
        "p_missing_values":
            p_missing_total,
        "H_missing_values":
            h_missing_total,
        "score_finite_rate":
            sum(
                math.isfinite(x)
                for x in scores
            )
            / len(scores),
        "score_min":
            min(scores),
        "score_max":
            max(scores),
        "posthoc_access":
            False,
        "terra_calls":
            0,
        "p_t_recomputed":
            False,
        "graph_recomputed":
            False,
        "alpha_retuned":
            False,
    }

    if (
        audit[
            "score_finite_rate"
        ]
        != 1.0
    ):
        raise RuntimeError(
            "Non-finite DECOUPLE score."
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

    compute = {
        "status":
            "PASS",
        "external_api_calls":
            0,
        "terra_calls":
            0,
        "operation":
            "deterministic_local_scoring",
        "candidate_count":
            EXPECTED_CANDIDATES,
        "trajectory_count":
            EXPECTED_TRAJECTORIES,
    }

    OUT_COMPUTE.write_text(
        json.dumps(
            compute,
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
            "STEP1F_DECOUPLE_PRE_SCORE",
        "spec_mapping": [
            "Eq37_signal_availability",
            "Eq38_Ap_AH",
            "Eq39_gated_DECOUPLE_score",
            "Eq41_deterministic_tie_key",
        ],
        "inputs": {
            "p_t_path":
                str(
                    PT_PATH.relative_to(
                        ROOT
                    )
                ),
            "p_t_sha256":
                sha256_file(
                    PT_PATH
                ),
            "H_hat_path":
                str(
                    HHAT_PATH.relative_to(
                        ROOT
                    )
                ),
            "H_hat_sha256":
                sha256_file(
                    HHAT_PATH
                ),
        },
        "gate_contract": {
            "finite_coverage_threshold":
                FINITE_COVERAGE_THRESHOLD,
            "range_threshold":
                RANGE_THRESHOLD,
            "median_imputation":
                "only_after_gate_decision_when_signal_available",
        },
        "tie_contract": {
            "hash":
                "sha256",
            "master_seed":
                MASTER_SEED,
            "serialization":
                "instance_id<TAB>step_index<TAB>master_seed",
            "ordering":
                "decreasing_score_then_increasing_hash",
            "spec_status":
                "deterministic_serialization_operationalization",
        },
        "outputs": {
            "gates_sha256":
                sha256_file(
                    OUT_GATES
                ),
            "scores_sha256":
                sha256_file(
                    OUT_SCORES
                ),
            "rankings_sha256":
                sha256_file(
                    OUT_RANKINGS
                ),
            "audit_sha256":
                sha256_file(
                    OUT_AUDIT
                ),
            "compute_sha256":
                sha256_file(
                    OUT_COMPUTE
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
        "terra_calls":
            0,
        "next":
            "STEP1_PRE_FREEZE_AND_ZERO_LEAKAGE_CLOSURE",
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
    print(
        "TRAJECTORIES="
        + str(
            len(
                trajectories
            )
        )
    )
    print(
        "CANDIDATES="
        + str(
            len(
                score_outputs
            )
        )
    )
    print(
        "P_AVAILABLE_TRAJECTORIES="
        + str(
            p_available_count
        )
    )
    print(
        "H_AVAILABLE_TRAJECTORIES="
        + str(
            h_available_count
        )
    )
    print(
        "BOTH_AVAILABLE_TRAJECTORIES="
        + str(
            both_available_count
        )
    )
    print(
        "FALLBACK_TRAJECTORIES="
        + str(
            fallback_trajectory_count
        )
    )
    print(
        "P_MISSING_VALUES="
        + str(
            p_missing_total
        )
    )
    print(
        "H_MISSING_VALUES="
        + str(
            h_missing_total
        )
    )
    print(
        "SCORE_FINITE_RATE="
        + str(
            audit[
                "score_finite_rate"
            ]
        )
    )
    print(
        "SCORE_MIN="
        + str(
            audit[
                "score_min"
            ]
        )
    )
    print(
        "SCORE_MAX="
        + str(
            audit[
                "score_max"
            ]
        )
    )
    print(
        "TIE_HASH=SHA256"
    )
    print(
        "POSTHOC_ACCESS=NO"
    )
    print(
        "TERRA_CALLS=0"
    )
    print(
        "P_T_RECOMPUTED=NO"
    )
    print(
        "GRAPH_RECOMPUTED=NO"
    )
    print(
        "ALPHA_RETUNED=NO"
    )
    print(
        "STATUS=PASS"
    )
    print(
        "NEXT=STEP1_PRE_FREEZE_AND_ZERO_LEAKAGE_CLOSURE"
    )


if __name__ == "__main__":
    main()
