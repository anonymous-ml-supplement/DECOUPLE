#!/usr/bin/env python3

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path("__DECOUPLE_ROOT__")
STEP3 = ROOT / "10_PILOT/STEP3"

OUT = (
    STEP3
    / "04_OUTPUTS/STEP3E_EXACT_CHECKPOINT_REPLAY"
)

AUD = (
    STEP3
    / "06_AUDIT/STEP3E_EXACT_CHECKPOINT_REPLAY"
)

JOINT = (
    OUT
    / "STEP3E_JOINT_REPLAY_EXECUTION_MANIFEST.jsonl"
)

SINGLETON = (
    OUT
    / "STEP3E_FORMAL_REPLAY_PLAN.jsonl"
)

EXECUTION_LEDGER = (
    OUT
    / "STEP3E_FORMAL_EXECUTION_LEDGER.jsonl"
)

FANOUT = (
    OUT
    / "STEP3E_EXECUTION_FANOUT.jsonl"
)

MANIFEST = (
    OUT
    / "STEP3E_FORMAL_EXECUTION_LEDGER_MANIFEST.json"
)

AUDIT = (
    AUD
    / "STEP3E_FORMAL_EXECUTION_LEDGER_AUDIT.json"
)

STATUS = (
    AUD
    / "STEP3E_FORMAL_EXECUTION_LEDGER_STATUS.txt"
)

EXPECTED_JOINT_SHA256 = (
    "1d659f7678cf4fff555988224e5ba13fd"
    "56a700f9eb1a3ee8dbde9e372da2387"
)

EXPECTED_SINGLETON_SHA256 = (
    "cad48d06f581e6978cd43c5f69c6b923"
    "219e9a199df3a6bcbb9076eacbf8a295"
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


def stable_sha(obj):
    payload = json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(
        payload
    ).hexdigest()


def load_jsonl(path):
    rows = []

    with path.open(
        encoding="utf-8"
    ) as f:
        for line in f:
            if line.strip():
                rows.append(
                    json.loads(line)
                )

    return rows


def write_jsonl(path, rows):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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


def write_json(path, obj):
    path.write_text(
        json.dumps(
            obj,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


if not JOINT.is_file():
    raise RuntimeError(
        f"JOINT_MANIFEST_MISSING={JOINT}"
    )

if sha256_file(JOINT) != EXPECTED_JOINT_SHA256:
    raise RuntimeError(
        "JOINT_MANIFEST_SHA256_MISMATCH="
        + sha256_file(JOINT)
    )

if not SINGLETON.is_file():
    raise RuntimeError(
        f"SINGLETON_PLAN_MISSING={SINGLETON}"
    )

if (
    sha256_file(SINGLETON)
    != EXPECTED_SINGLETON_SHA256
):
    raise RuntimeError(
        "SINGLETON_PLAN_SHA256_MISMATCH="
        + sha256_file(SINGLETON)
    )


joint_rows = load_jsonl(
    JOINT
)

singleton_rows = load_jsonl(
    SINGLETON
)

if len(joint_rows) != 9222:
    raise RuntimeError(
        "JOINT_ROW_COUNT="
        + str(len(joint_rows))
    )

if len(singleton_rows) != 697:
    raise RuntimeError(
        "SINGLETON_ROW_COUNT="
        + str(len(singleton_rows))
    )


execution = {}
fanout = []


def register_branch(
    branch_type,
    benchmark,
    instance_id,
    selected_steps,
    intervention_operator,
    source_identity,
):
    selected_steps = [
        int(x)
        for x in selected_steps
    ]

    if not selected_steps:
        raise RuntimeError(
            "EMPTY_SELECTED_STEP_SET="
            + repr(source_identity)
        )

    if selected_steps != sorted(
        selected_steps
    ):
        raise RuntimeError(
            "SELECTED_STEPS_NOT_CHRONOLOGICAL="
            + repr(source_identity)
        )

    branch_spec = {
        "benchmark":
            benchmark,

        "instance_id":
            instance_id,

        "selected_steps_chronological":
            selected_steps,

        "intervention_operator":
            intervention_operator,
    }

    execution_id = stable_sha(
        branch_spec
    )

    if execution_id not in execution:
        execution[execution_id] = {
            "execution_id":
                execution_id,

            "scientific_authority":
                "SPEC5",

            "scientific_substep":
                "STEP3E_EXACT_CHECKPOINT_RESTORE_REPLAY",

            "benchmark":
                benchmark,

            "instance_id":
                instance_id,

            "selected_steps_chronological":
                selected_steps,

            "first_modified_step":
                selected_steps[0],

            "intervention_operator":
                intervention_operator,

            "restore_latest_exact_checkpoint":
                True,

            "process_selected_steps_chronologically":
                True,

            "model":
                "gpt-5.6-terra",

            "api":
                "Responses",

            "reasoning_effort":
                "medium",

            "status":
                "PENDING",

            "exact_restoration_certified":
                False,

            "approximate_restoration":
                False,

            "model_calls":
                0,

            "api_calls":
                0,

            "branch_replay_executed":
                False,

            "source_types":
                [],
        }

    if (
        branch_type
        not in execution[
            execution_id
        ]["source_types"]
    ):
        execution[
            execution_id
        ]["source_types"].append(
            branch_type
        )

    fanout.append(
        {
            "execution_id":
                execution_id,

            "branch_type":
                branch_type,

            "source_identity":
                source_identity,
        }
    )


# Joint practical branches.
for row in joint_rows:
    register_branch(
        branch_type=
            "joint_practical",

        benchmark=
            row["benchmark"],

        instance_id=
            row["instance_id"],

        selected_steps=
            row[
                "selected_steps_chronological"
            ],

        intervention_operator=
            "V_refine",

        source_identity={
            "method":
                row["method"],

            "budget":
                row["budget"],

            "random_replicate":
                row[
                    "random_replicate"
                ],
        },
    )


# Formal singleton/oracle plan.
for row in singleton_rows:
    benchmark = row.get(
        "benchmark"
    )

    instance_id = row.get(
        "instance_id"
    )

    step_index = row.get(
        "step_index"
    )

    if (
        benchmark is None
        or instance_id is None
        or step_index is None
    ):
        raise RuntimeError(
            "SINGLETON_SCHEMA_REQUIRED_FIELD_MISSING="
            + json.dumps(
                row,
                sort_keys=True,
            )
        )

    operator = (
        row.get(
            "intervention_operator"
        )
        or row.get(
            "operator"
        )
    )

    branch_type = (
        row.get(
            "branch_type"
        )
        or row.get(
            "replay_type"
        )
        or ""
    )

    text = (
        json.dumps(
            row,
            sort_keys=True,
        ).lower()
    )

    if operator is None:
        if (
            "oracle"
            in branch_type.lower()
            or "oracle"
            in text
        ):
            operator = "V_oracle"
        else:
            operator = "V_refine"

    if operator not in {
        "V_refine",
        "V_oracle",
    }:
        raise RuntimeError(
            f"UNKNOWN_SINGLETON_OPERATOR={operator}"
        )

    register_branch(
        branch_type=(
            "singleton_oracle"
            if operator == "V_oracle"
            else "singleton_practical"
        ),

        benchmark=
            benchmark,

        instance_id=
            instance_id,

        selected_steps=[
            int(step_index)
        ],

        intervention_operator=
            operator,

        source_identity=row,
    )


execution_rows = sorted(
    execution.values(),
    key=lambda r: (
        r["benchmark"],
        r["instance_id"],
        r["first_modified_step"],
        r["intervention_operator"],
        r["execution_id"],
    ),
)

for row in execution_rows:
    row["source_types"] = sorted(
        row["source_types"]
    )


write_jsonl(
    EXECUTION_LEDGER,
    execution_rows,
)

write_jsonl(
    FANOUT,
    fanout,
)


benchmark_counts = Counter(
    row["benchmark"]
    for row in execution_rows
)

operator_counts = Counter(
    row["intervention_operator"]
    for row in execution_rows
)

source_counts = Counter()

for row in fanout:
    source_counts[
        row["branch_type"]
    ] += 1


manifest = {
    "scientific_authority":
        "SPEC5",

    "scientific_substep":
        "STEP3E_EXACT_CHECKPOINT_RESTORE_REPLAY",

    "status":
        "PASS_FROZEN",

    "joint_source_rows":
        len(joint_rows),

    "singleton_source_rows":
        len(singleton_rows),

    "source_evaluation_rows_total":
        len(joint_rows)
        + len(singleton_rows),

    "unique_execution_branches":
        len(execution_rows),

    "deduplication_rule":
        (
            "execution identity is defined only by "
            "benchmark, instance_id, chronological "
            "selected-step set, and intervention operator"
        ),

    "evaluation_identity_rule":
        (
            "method, budget, and random replicate remain "
            "in the fanout ledger and are never pooled "
            "for statistical evaluation"
        ),

    "benchmark_counts":
        dict(
            sorted(
                benchmark_counts.items()
            )
        ),

    "operator_counts":
        dict(
            sorted(
                operator_counts.items()
            )
        ),

    "source_type_counts":
        dict(
            sorted(
                source_counts.items()
            )
        ),

    "execution_ledger":
        str(EXECUTION_LEDGER),

    "execution_ledger_sha256":
        sha256_file(
            EXECUTION_LEDGER
        ),

    "fanout_ledger":
        str(FANOUT),

    "fanout_ledger_sha256":
        sha256_file(
            FANOUT
        ),

    "model_calls":
        0,

    "api_calls":
        0,

    "branch_replay_executed":
        False,

    "pre_mutation":
        False,

    "next":
        "STEP3E_RUN_FORMAL_EXECUTION_LEDGER",
}


write_json(
    MANIFEST,
    manifest,
)


audit = {
    "status":
        "PASS",

    "joint_sha256_match":
        True,

    "singleton_sha256_match":
        True,

    "joint_rows":
        len(joint_rows),

    "singleton_rows":
        len(singleton_rows),

    "unique_execution_branches":
        len(execution_rows),

    "fanout_rows":
        len(fanout),

    "fanout_complete":
        (
            len(fanout)
            == len(joint_rows)
            + len(singleton_rows)
        ),

    "random_identity_preserved_in_fanout":
        True,

    "method_identity_preserved_in_fanout":
        True,

    "budget_identity_preserved_in_fanout":
        True,

    "joint_outcome_not_inferred_from_singleton":
        True,

    "model_calls":
        0,

    "api_calls":
        0,

    "pre_mutation":
        False,
}


write_json(
    AUDIT,
    audit,
)


STATUS.write_text(
    "\n".join(
        [
            "SCIENTIFIC_AUTHORITY=SPEC5",
            "CURRENT=STEP3E_EXACT_CHECKPOINT_RESTORE_REPLAY",
            "FORMAL_EXECUTION_LEDGER=PASS_FROZEN",
            f"JOINT_SOURCE_ROWS={len(joint_rows)}",
            f"SINGLETON_SOURCE_ROWS={len(singleton_rows)}",
            f"UNIQUE_EXECUTION_BRANCHES={len(execution_rows)}",
            f"FANOUT_ROWS={len(fanout)}",
            "MODEL_RUN=NO",
            "API_CALLS=0",
            "BRANCH_REPLAY_EXECUTED=NO",
            "PRE_MUTATION=NO",
            "POST_ALLOWED=YES",
            "NEXT=STEP3E_RUN_FORMAL_EXECUTION_LEDGER",
            "",
        ]
    ),
    encoding="utf-8",
)


print(
    "STEP3E_FORMAL_EXECUTION_LEDGER_STATUS="
    "PASS_FROZEN"
)

print(
    "JOINT_SOURCE_ROWS="
    + str(len(joint_rows))
)

print(
    "SINGLETON_SOURCE_ROWS="
    + str(len(singleton_rows))
)

print(
    "SOURCE_EVALUATION_ROWS_TOTAL="
    + str(
        len(joint_rows)
        + len(singleton_rows)
    )
)

print(
    "UNIQUE_EXECUTION_BRANCHES="
    + str(len(execution_rows))
)

print(
    "FANOUT_ROWS="
    + str(len(fanout))
)

for benchmark in sorted(
    benchmark_counts
):
    print(
        "BENCHMARK_"
        + benchmark.upper()
        .replace("-", "_")
        .replace(" ", "_")
        + "_EXECUTION_BRANCHES="
        + str(
            benchmark_counts[
                benchmark
            ]
        )
    )

for operator in sorted(
    operator_counts
):
    print(
        "OPERATOR_"
        + operator.upper()
        + "_EXECUTION_BRANCHES="
        + str(
            operator_counts[
                operator
            ]
        )
    )

print(
    "EXECUTION_LEDGER_SHA256="
    + sha256_file(
        EXECUTION_LEDGER
    )
)

print(
    "FANOUT_LEDGER_SHA256="
    + sha256_file(
        FANOUT
    )
)

print(
    "MANIFEST_SHA256="
    + sha256_file(
        MANIFEST
    )
)

print(
    "AUDIT_SHA256="
    + sha256_file(
        AUDIT
    )
)

print("MODEL_RUN=NO")
print("API_CALLS=0")
print("BRANCH_REPLAY_EXECUTED=NO")
print("PRE_MUTATION=NO")
print("POST_ALLOWED=YES")

print(
    "NEXT=STEP3E_RUN_FORMAL_EXECUTION_LEDGER"
)
