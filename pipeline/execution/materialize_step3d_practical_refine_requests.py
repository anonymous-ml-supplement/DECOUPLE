#!/usr/bin/env python3

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path("__DECOUPLE_ROOT__")
STEP1 = ROOT / "10_PILOT/STEP1"
STEP3 = ROOT / "10_PILOT/STEP3"

PREFIX_ROOT = (
    STEP1
    / "04_OUTPUTS/STEP1C_PREFIX/CAUSAL_PREFIXES"
)

CONTRACT = (
    STEP3
    / "00_CONFIG/STEP3_INTERVENTION/"
      "STEP3D_PRACTICAL_REFINE_CONTRACT.json"
)

OUT = (
    STEP3
    / "04_OUTPUTS/STEP3D_PRACTICAL_REFINE"
)

AUD = (
    STEP3
    / "06_AUDIT/STEP3D_PRACTICAL_REFINE"
)

REQUESTS = (
    OUT
    / "STEP3D_PRACTICAL_REFINE_REQUEST_DESCRIPTORS.jsonl"
)

MANIFEST = (
    OUT
    / "STEP3D_PRACTICAL_REFINE_REQUEST_MANIFEST.json"
)

AUDIT = (
    AUD
    / "STEP3D_PRACTICAL_REFINE_REQUEST_AUDIT.json"
)

STATUS = (
    AUD
    / "STEP3D_CLOSURE_STATUS.txt"
)

LEDGER = (
    AUD
    / "STEP3D_SHA256SUMS.txt"
)

EXPECTED_CONTRACT_SHA256 = (
    "939c37a82531f9875c11fe7328b086423"
    "daec9929267c8babbe0096a949d9229"
)

EXPECTED_COUNTS = {
    "BFCL": 228,
    "Math-Shepherd": 343,
    "ToolAlpaca": 60,
}

EXPECTED_TOTAL = 631


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def load_jsonl(path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
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


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(
                json.dumps(
                    row,
                    sort_keys=True,
                    ensure_ascii=False,
                )
                + "\n"
            )


if not CONTRACT.is_file():
    raise RuntimeError(
        f"STEP3D_CONTRACT_NOT_FOUND={CONTRACT}"
    )

actual_contract_sha = sha256_file(CONTRACT)

if actual_contract_sha != EXPECTED_CONTRACT_SHA256:
    raise RuntimeError(
        "STEP3D_CONTRACT_SHA256_MISMATCH="
        + actual_contract_sha
    )

contract = load_json(CONTRACT)

if contract.get("status") != "CONTRACT_PASS_FROZEN":
    raise RuntimeError(
        "STEP3D_CONTRACT_NOT_PASS_FROZEN"
    )


rows = []

domain_dirs = {
    "BFCL": "BFCL",
    "Math-Shepherd": "Math-Shepherd",
    "ToolAlpaca": "ToolAlpaca",
}

for benchmark, dirname in domain_dirs.items():
    root = PREFIX_ROOT / dirname

    if not root.is_dir():
        raise RuntimeError(
            f"PREFIX_ROOT_NOT_FOUND={root}"
        )

    domain_rows = []

    for path in sorted(root.glob("*.jsonl")):
        for x in load_jsonl(path):
            required = {
                "benchmark",
                "instance_id",
                "step_index",
                "prefix_hash",
                "candidate_kind",
                "candidate_step",
                "history_before_step",
                "source_archive_path",
                "source_archive_sha256",
            }

            missing = required - set(x)

            if missing:
                raise RuntimeError(
                    "PREFIX_REQUIRED_FIELDS_MISSING="
                    f"{path}:{sorted(missing)}"
                )

            if x["benchmark"] != benchmark:
                raise RuntimeError(
                    "BENCHMARK_IDENTITY_MISMATCH="
                    f"{path}:{x['benchmark']}:{benchmark}"
                )

            descriptor = {
                "scientific_authority":
                    "SPEC5",

                "scientific_substep":
                    "STEP3D_PRACTICAL_FROZEN_GENERATOR_CRITIC_REFINE",

                "operator":
                    "V_refine",

                "benchmark":
                    benchmark,

                "instance_id":
                    x["instance_id"],

                "step_index":
                    x["step_index"],

                "prefix_hash":
                    x["prefix_hash"],

                "candidate_kind":
                    x["candidate_kind"],

                "archived_candidate_step":
                    x["candidate_step"],

                "frozen_base_history_reference":
                    x["history_before_step"],

                "source_archive_path":
                    x["source_archive_path"],

                "source_archive_sha256":
                    x["source_archive_sha256"],

                "critic_model":
                    "gpt-5.6-terra",

                "refine_generator":
                    "gpt-5.6-terra",

                "generator_api":
                    "Responses",

                "reasoning_effort":
                    "medium",

                "requested_refine_temperature":
                    0.2,

                "toolalpaca_simulator_model":
                    (
                        "gpt-5.4-mini-2026-03-17"
                        if benchmark == "ToolAlpaca"
                        else None
                    ),

                "toolalpaca_simulator_role":
                    (
                        "environment_simulator_only"
                        if benchmark == "ToolAlpaca"
                        else None
                    ),

                # Critical replay rule:
                # archived history is provenance only.
                # At execution, critic/refiner must receive
                # the exact current pre-step branch state
                # produced by STEP3E restoration/replay.
                "runtime_history_source":
                    "STEP3E_EXACT_CURRENT_PRE_STEP_BRANCH_STATE",

                "archived_history_may_replace_runtime_branch_history":
                    False,

                "critic_execution_phase":
                    "STEP3E",

                "selected_step_regeneration_phase":
                    "STEP3E",

                "checkpoint_restore_phase":
                    "STEP3E",

                "terminal_evaluation_phase":
                    "STEP3E",

                "post_label_phase":
                    "STEP3F",

                "oracle_target_visible":
                    False,

                "future_trajectory_visible":
                    False,

                "posthoc_label_visible":
                    False,

                "critique_materialized":
                    False,

                "refined_step_materialized":
                    False,

                "replay_executed":
                    False,

                "descriptor_only":
                    True,
            }

            domain_rows.append(descriptor)

    if len(domain_rows) != EXPECTED_COUNTS[benchmark]:
        raise RuntimeError(
            "DOMAIN_COUNT_MISMATCH="
            f"{benchmark}:"
            f"{len(domain_rows)}:"
            f"{EXPECTED_COUNTS[benchmark]}"
        )

    rows.extend(domain_rows)


if len(rows) != EXPECTED_TOTAL:
    raise RuntimeError(
        f"TOTAL_REQUEST_DESCRIPTOR_ROWS={len(rows)}"
    )


keys = [
    (
        x["benchmark"],
        x["instance_id"],
        x["step_index"],
    )
    for x in rows
]

if len(keys) != len(set(keys)):
    raise RuntimeError(
        "DUPLICATE_STEP3D_REQUEST_KEY"
    )


rows.sort(
    key=lambda x: (
        x["benchmark"],
        x["instance_id"],
        x["step_index"],
    )
)

write_jsonl(
    REQUESTS,
    rows,
)

counts = Counter(
    x["benchmark"]
    for x in rows
)


manifest = {
    "scientific_authority":
        "SPEC5",

    "scientific_substep":
        "STEP3D_PRACTICAL_FROZEN_GENERATOR_CRITIC_REFINE",

    "status":
        "PASS_FROZEN",

    "artifact_role":
        "PRACTICAL_REFINE_RUNTIME_REQUEST_DESCRIPTORS",

    "descriptor_rows":
        len(rows),

    "counts":
        dict(counts),

    "critic_model":
        "gpt-5.6-terra",

    "refine_generator":
        "gpt-5.6-terra",

    "toolalpaca_simulator":
        "gpt-5.4-mini-2026-03-17",

    "toolalpaca_simulator_role":
        "environment_simulator_only",

    "requested_refine_temperature":
        0.2,

    "runtime_history_rule":
        "USE_EXACT_CURRENT_PRE_STEP_BRANCH_STATE_FROM_STEP3E",

    "precompute_concrete_refined_steps_from_base_history":
        False,

    "reason":
        "later_selected_steps_may_have_branch_specific_history_after_earlier_repairs",

    "model_calls":
        0,

    "api_calls":
        0,

    "replay_executed":
        False,

    "pre_mutation":
        False,

    "post_allowed":
        True,

    "requests_file":
        str(REQUESTS),

    "requests_sha256":
        sha256_file(REQUESTS),

    "step3d_contract_sha256":
        actual_contract_sha,

    "next":
        "STEP3E_EXACT_CHECKPOINT_RESTORE_REPLAY",
}

write_json(
    MANIFEST,
    manifest,
)


audit = {
    "status":
        "PASS",

    "expected_total":
        EXPECTED_TOTAL,

    "observed_total":
        len(rows),

    "benchmark_counts":
        dict(counts),

    "duplicate_keys":
        0,

    "all_runtime_history_bound_to_step3e_exact_state":
        all(
            x["runtime_history_source"]
            == "STEP3E_EXACT_CURRENT_PRE_STEP_BRANCH_STATE"
            for x in rows
        ),

    "oracle_target_access":
        False,

    "future_trajectory_access":
        False,

    "posthoc_label_access":
        False,

    "concrete_critique_precomputed":
        False,

    "concrete_refined_step_precomputed":
        False,

    "model_calls":
        0,

    "api_calls":
        0,

    "replay":
        False,

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
            "STEP3A=PASS_FROZEN",
            "STEP3B_CONTRACT=PASS_FROZEN",
            "STEP3B_RANKING=PENDING_SINGLETON_GAINS",
            "STEP3C=PASS_FROZEN",
            "STEP3D_CONTRACT=PASS_FROZEN",
            "STEP3D_REQUEST_DESCRIPTORS=PASS_FROZEN",
            "STEP3D=PASS_FROZEN",
            "STEP3D_DESCRIPTOR_ROWS=631",
            "STEP3D_MODEL_CALLS=0",
            "STEP3D_API_CALLS=0",
            "STEP3D_REPLAY_EXECUTED=NO",
            "CURRENT=STEP3D_CLOSED",
            "NEXT=STEP3E_EXACT_CHECKPOINT_RESTORE_REPLAY",
            "STEP3E_RUNTIME_CRITIC=gpt-5.6-terra",
            "STEP3E_RUNTIME_REFINER=gpt-5.6-terra",
            "TOOLALPACA_SIMULATOR=gpt-5.4-mini-2026-03-17",
            "TOOLALPACA_SIMULATOR_ROLE=environment_simulator_only",
            "RUNTIME_HISTORY=EXACT_CURRENT_BRANCH_STATE",
            "DO_NOT_PRECOMPUTE_REFINED_STEP_FROM_BASE_HISTORY=YES",
            "PRE_MUTATION=NO",
            "POST_ALLOWED=YES",
            "",
        ]
    ),
    encoding="utf-8",
)


with LEDGER.open(
    "w",
    encoding="utf-8",
) as f:
    for path in (
        CONTRACT,
        REQUESTS,
        MANIFEST,
        AUDIT,
        STATUS,
    ):
        f.write(
            f"{sha256_file(path)}  {path}\n"
        )


print("STEP3D_REQUEST_MATERIALIZATION_STATUS=PASS")
print("REQUEST_DESCRIPTOR_ROWS=631")
print(
    "BFCL_REQUEST_DESCRIPTORS="
    + str(counts["BFCL"])
)
print(
    "MATH_SHEPHERD_REQUEST_DESCRIPTORS="
    + str(counts["Math-Shepherd"])
)
print(
    "TOOLALPACA_REQUEST_DESCRIPTORS="
    + str(counts["ToolAlpaca"])
)
print(
    "REQUESTS_SHA256="
    + sha256_file(REQUESTS)
)
print(
    "MANIFEST_SHA256="
    + sha256_file(MANIFEST)
)
print(
    "AUDIT_SHA256="
    + sha256_file(AUDIT)
)
print("CRITIC_MODEL=gpt-5.6-terra")
print("REFINE_GENERATOR=gpt-5.6-terra")
print(
    "TOOLALPACA_SIMULATOR_MODEL="
    "gpt-5.4-mini-2026-03-17"
)
print(
    "RUNTIME_HISTORY_SOURCE="
    "STEP3E_EXACT_CURRENT_PRE_STEP_BRANCH_STATE"
)
print("CONCRETE_CRITIQUE_PRECOMPUTED=NO")
print("CONCRETE_REFINED_STEP_PRECOMPUTED=NO")
print("MODEL_RUN=NO")
print("API_CALLS=0")
print("REPLAY_EXECUTED=NO")
print("PRE_MUTATION=NO")
print("POST_ALLOWED=YES")
print("STEP3D=PASS_FROZEN")
print(
    "NEXT=STEP3E_EXACT_CHECKPOINT_RESTORE_REPLAY"
)
