#!/usr/bin/env python3

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


ROOT = Path("__DECOUPLE_ROOT__")
STEP2 = ROOT / "10_PILOT/STEP2"

SOURCE = (
    STEP2
    / "09_HANDOFF/"
      "DECOUPLE_STEP2B5_TOOLPRM_SPEC4_PASS_FROZEN_JOB3734246_20260908/"
      "toolprm_spec4_step_scores.jsonl"
)

OUT = (
    STEP2
    / "04_OUTPUTS/STEP2C_CORE_PRE_CLOSURE/TOOLPRM/"
      "toolprm_exact_b_selections.jsonl"
)

AUDIT = (
    STEP2
    / "06_AUDIT/STEP2C_CORE_PRE_CLOSURE/"
      "toolprm_exact_b_audit.json"
)

MANIFEST = (
    STEP2
    / "06_AUDIT/STEP2C_CORE_PRE_CLOSURE/"
      "toolprm_exact_b_manifest.json"
)

SHA_LEDGER = (
    STEP2
    / "06_AUDIT/STEP2C_CORE_PRE_CLOSURE/"
      "toolprm_exact_b_SHA256SUMS.txt"
)

EXPECTED_SOURCE_SHA256 = (
    "7220802f7f5e749599d38a0dbd7e8c6"
    "e9b5014fabd516e1c6fbb385dfb5c9553"
)

EXPECTED_SOURCE_ROWS = 169
EXPECTED_INSTANCES = 37
EXPECTED_SELECTION_ROWS = 311

MASTER_SEED = 20260829

BETAS = (
    0.05,
    0.10,
    0.15,
    0.20,
    0.25,
    0.50,
)


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def tie_key(instance_id, step_index):
    payload = (
        f"{instance_id}\t"
        f"{step_index}\t"
        f"{MASTER_SEED}"
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def half_up_budget(beta, t):
    return min(
        t,
        max(
            1,
            math.floor(beta * t + 0.5),
        ),
    )


def load_jsonl(path):
    rows = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        for line_no, line in enumerate(
            f,
            start=1,
        ):
            if not line.strip():
                continue

            try:
                rows.append(json.loads(line))
            except Exception as e:
                raise RuntimeError(
                    f"JSONL_PARSE_FAIL="
                    f"{path}:{line_no}:{e}"
                )

    return rows


def main():
    if not SOURCE.is_file():
        raise RuntimeError(
            f"SOURCE_NOT_FOUND={SOURCE}"
        )

    source_sha = sha256_file(SOURCE)

    if source_sha != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(
            "SOURCE_SHA256_MISMATCH="
            + source_sha
        )

    rows = load_jsonl(SOURCE)

    if len(rows) != EXPECTED_SOURCE_ROWS:
        raise RuntimeError(
            "SOURCE_ROW_COUNT_MISMATCH="
            + str(len(rows))
        )

    grouped = defaultdict(list)
    seen = set()

    domain_steps = defaultdict(int)
    domain_instances = defaultdict(set)

    for row_no, row in enumerate(
        rows,
        start=1,
    ):
        required = {
            "benchmark",
            "instance_id",
            "step_index",
            "risk_score",
            "prefix_hash",
            "adapter_status",
            "posthoc_access",
        }

        missing = required - set(row)

        if missing:
            raise RuntimeError(
                f"MISSING_FIELDS_ROW_{row_no}="
                + ",".join(sorted(missing))
            )

        if row["adapter_status"] != "PASS":
            raise RuntimeError(
                f"NONPASS_ADAPTER_ROW={row_no}"
            )

        if row["posthoc_access"] is not False:
            raise RuntimeError(
                f"POSTHOC_ACCESS_ROW={row_no}"
            )

        risk = row["risk_score"]

        if not isinstance(
            risk,
            (int, float),
        ):
            raise RuntimeError(
                f"NONNUMERIC_RISK_ROW={row_no}"
            )

        if not math.isfinite(float(risk)):
            raise RuntimeError(
                f"NONFINITE_RISK_ROW={row_no}"
            )

        if not (0.0 <= float(risk) <= 1.0):
            raise RuntimeError(
                f"RISK_OUT_OF_RANGE_ROW={row_no}"
            )

        key = (
            str(row["instance_id"]),
            int(row["step_index"]),
        )

        if key in seen:
            raise RuntimeError(
                "DUPLICATE_INSTANCE_STEP="
                + repr(key)
            )

        seen.add(key)

        record = dict(row)
        record["risk_score"] = float(risk)
        record["tie_key"] = tie_key(
            str(row["instance_id"]),
            int(row["step_index"]),
        )

        grouped[
            str(row["instance_id"])
        ].append(record)

        benchmark = str(
            row["benchmark"]
        )

        domain_steps[benchmark] += 1
        domain_instances[
            benchmark
        ].add(
            str(row["instance_id"])
        )

    if len(grouped) != EXPECTED_INSTANCES:
        raise RuntimeError(
            "COMPATIBLE_INSTANCE_COUNT_MISMATCH="
            + str(len(grouped))
        )

    selections = []
    per_instance = []

    for instance_id in sorted(grouped):
        instance_rows = grouped[
            instance_id
        ]

        benchmarks = sorted(
            {
                str(x["benchmark"])
                for x in instance_rows
            }
        )

        if len(benchmarks) != 1:
            raise RuntimeError(
                "MULTI_BENCHMARK_INSTANCE="
                + instance_id
            )

        benchmark = benchmarks[0]

        ranked = sorted(
            instance_rows,
            key=lambda x: (
                -float(
                    x["risk_score"]
                ),
                x["tie_key"],
            ),
        )

        T = len(ranked)

        budget_summary = {}

        for beta in BETAS:
            B = half_up_budget(
                beta,
                T,
            )

            budget_summary[
                f"{beta:.2f}"
            ] = B

            chosen = ranked[:B]

            if len(chosen) != B:
                raise RuntimeError(
                    "EXACT_B_FAILURE="
                    f"{instance_id}:{beta}"
                )

            for rank, row in enumerate(
                chosen,
                start=1,
            ):
                selections.append(
                    {
                        "baseline":
                            "ToolPRM-GRPO-v4",
                        "benchmark":
                            benchmark,
                        "instance_id":
                            instance_id,
                        "step_index":
                            int(
                                row[
                                    "step_index"
                                ]
                            ),
                        "prefix_hash":
                            row[
                                "prefix_hash"
                            ],
                        "risk_score":
                            float(
                                row[
                                    "risk_score"
                                ]
                            ),
                        "tie_key":
                            row[
                                "tie_key"
                            ],
                        "budget_fraction":
                            beta,
                        "trajectory_candidate_count":
                            T,
                        "exact_B":
                            B,
                        "selection_rank":
                            rank,
                        "selected":
                            True,
                        "master_seed":
                            MASTER_SEED,
                        "score_rule":
                            "risk_score_descending",
                        "tie_rule":
                            "SHA256(instance_id<TAB>step_index<TAB>20260829)_ascending",
                        "budget_rule":
                            "min(T,max(1,floor(beta*T+0.5)))",
                        "source_score_sha256":
                            source_sha,
                        "posthoc_access":
                            False,
                    }
                )

        per_instance.append(
            {
                "benchmark":
                    benchmark,
                "instance_id":
                    instance_id,
                "eligible_steps_T":
                    T,
                "budgets":
                    budget_summary,
                "selection_rows":
                    sum(
                        budget_summary.values()
                    ),
            }
        )

    if (
        len(selections)
        != EXPECTED_SELECTION_ROWS
    ):
        raise RuntimeError(
            "SELECTION_ROW_COUNT_MISMATCH="
            + str(len(selections))
        )

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUT.open(
        "w",
        encoding="utf-8",
    ) as f:
        for row in selections:
            f.write(
                json.dumps(
                    row,
                    sort_keys=True,
                    ensure_ascii=False,
                )
                + "\n"
            )

    output_sha = sha256_file(
        OUT
    )

    audit = {
        "status":
            "PASS",
        "scientific_step":
            "STEP2C",
        "component":
            "TOOLPRM_EXACT_B",
        "baseline":
            "ToolPRM-GRPO-v4",
        "formal_scoring_job":
            3734246,
        "source_file":
            str(SOURCE),
        "source_sha256":
            source_sha,
        "source_rows":
            len(rows),
        "compatible_instances":
            len(grouped),
        "unique_instance_step_keys":
            len(seen),
        "selection_rows":
            len(selections),
        "expected_selection_rows":
            EXPECTED_SELECTION_ROWS,
        "betas":
            list(BETAS),
        "master_seed":
            MASTER_SEED,
        "ranking":
            "decreasing risk_score",
        "tie_key":
            "SHA256(instance_id<TAB>step_index<TAB>20260829), ascending",
        "budget_rule":
            "min(T,max(1,floor(beta*T+0.5)))",
        "domain_step_counts": {
            k: domain_steps[k]
            for k in sorted(
                domain_steps
            )
        },
        "domain_instance_counts": {
            k: len(
                domain_instances[k]
            )
            for k in sorted(
                domain_instances
            )
        },
        "per_instance":
            per_instance,
        "output_file":
            str(OUT),
        "output_sha256":
            output_sha,
        "model_rerun":
            False,
        "cluster_required":
            False,
        "posthoc_access":
            False,
    }

    AUDIT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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
        "status":
            "PASS_FROZEN_COMPONENT",
        "scientific_authority":
            "SPEC5",
        "scientific_step":
            "STEP2C",
        "component":
            "ToolPRM-GRPO-v4 exact-B selections",
        "source_frozen_score_file":
            str(SOURCE),
        "source_frozen_score_sha256":
            source_sha,
        "source_score_rows":
            len(rows),
        "compatible_instances":
            len(grouped),
        "selection_rows":
            len(selections),
        "output_file":
            str(OUT),
        "output_sha256":
            output_sha,
        "audit_file":
            str(AUDIT),
        "audit_sha256":
            sha256_file(
                AUDIT
            ),
        "post_allowed":
            False,
        "rerun_toolprm":
            False,
        "next":
            "STEP2C_CORE_CLOSURE",
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

    with SHA_LEDGER.open(
        "w",
        encoding="utf-8",
    ) as f:
        for path in (
            SOURCE,
            OUT,
            AUDIT,
            MANIFEST,
        ):
            f.write(
                f"{sha256_file(path)}  "
                f"{path}\n"
            )

    print(
        "STEP2C2_STATUS=PASS"
    )
    print(
        "SOURCE_SHA256_MATCH=YES"
    )
    print(
        "SOURCE_SCORE_ROWS="
        + str(len(rows))
    )
    print(
        "COMPATIBLE_INSTANCES="
        + str(len(grouped))
    )
    print(
        "UNIQUE_INSTANCE_STEP_KEYS="
        + str(len(seen))
    )

    for domain in sorted(
        domain_steps
    ):
        print(
            f"{domain}_STEPS="
            f"{domain_steps[domain]}"
        )
        print(
            f"{domain}_INSTANCES="
            f"{len(domain_instances[domain])}"
        )

    print(
        "EXACT_B_SELECTION_ROWS="
        + str(len(selections))
    )
    print(
        "EXACT_B_SELECTION_SHA256="
        + output_sha
    )
    print(
        "AUDIT_SHA256="
        + sha256_file(AUDIT)
    )
    print(
        "MANIFEST_SHA256="
        + sha256_file(MANIFEST)
    )
    print(
        "OUTPUT="
        + str(OUT)
    )
    print(
        "AUDIT="
        + str(AUDIT)
    )
    print(
        "MANIFEST="
        + str(MANIFEST)
    )
    print(
        "SHA_LEDGER="
        + str(SHA_LEDGER)
    )
    print(
        "TOOLPRM_EXACT_B="
        "PASS_FROZEN_COMPONENT"
    )
    print(
        "RERUN_TOOLPRM=NO"
    )
    print(
        "CLUSTER_REQUIRED=NO"
    )
    print(
        "POST_ALLOWED=NO"
    )
    print(
        "NEXT=STEP2C_CORE_CLOSURE"
    )


if __name__ == "__main__":
    main()
