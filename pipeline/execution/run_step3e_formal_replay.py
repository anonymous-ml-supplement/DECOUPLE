#!/usr/bin/env python3

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path
from string import Template


ROOT = Path("__DECOUPLE_ROOT__")
STEP1 = ROOT / "10_PILOT/STEP1"
STEP3 = ROOT / "10_PILOT/STEP3"

THIS_FILE = Path(__file__).resolve()

DEFAULT_INPUT = (
    STEP3
    / "03_WORK/STEP3E_EXACT_CHECKPOINT_REPLAY/"
      "STEP3E_FORMAL_CORE_METHOD_COVERAGE_SHARD.jsonl"
)

DESCRIPTORS = (
    STEP3
    / "04_OUTPUTS/STEP3D_PRACTICAL_REFINE/"
      "STEP3D_PRACTICAL_REFINE_REQUEST_DESCRIPTORS.jsonl"
)

REFINE_CONTRACT = (
    STEP3
    / "00_CONFIG/STEP3_INTERVENTION/"
      "STEP3D_PRACTICAL_REFINE_CONTRACT.json"
)

REFINE_AMENDMENT = (
    STEP3
    / "00_CONFIG/STEP3_INTERVENTION/"
      "STEP3D_PRACTICAL_REFINE_PROMPT_AMENDMENT.json"
)

TERMINAL_CONTRACT = (
    STEP3
    / "00_CONFIG/STEP3_INTERVENTION/"
      "STEP3_BENCHMARK_TERMINAL_UTILITY_CONTRACT.json"
)

BFCL_RUNTIME = (
    STEP1
    / "01_CODE/STEP1B_TRAJECTORY/"
      "generate_bfcl_pilot25_base_trajectories.py"
)

BFCL_WORKER = (
    STEP1
    / "01_CODE/STEP1B_TRAJECTORY/"
      "bfcl_docker_trajectory_worker.py"
)


BFCL_ROOT = (
    STEP1
    / "02_INPUTS/RAW_AUTHORITY/BFCL/gorilla/"
      "berkeley-function-call-leaderboard"
)

TOOL_RUNTIME = (
    STEP1
    / "01_CODE/STEP1B_TRAJECTORY/"
      "generate_toolalpaca_pilot25_base_trajectories.py"
)

TOOL_AUTH = (
    STEP1
    / "02_INPUTS/RAW_AUTHORITY/TOOLALPACA/"
      "ToolAlpaca/data/eval_simulated.json"
)

RESULT_DIR = (
    OUT_DIR
    if False
    else STEP3
    / "04_OUTPUTS/STEP3E_EXACT_CHECKPOINT_REPLAY/"
      "FORMAL_BRANCH_RESULTS"
)

COMPUTE_LEDGER = (
    STEP3
    / "04_OUTPUTS/STEP3E_EXACT_CHECKPOINT_REPLAY/"
      "STEP3E_FORMAL_COMPUTE_LEDGER.jsonl"
)

COMPUTE_JOURNAL = (
    STEP3
    / "04_OUTPUTS/STEP3E_EXACT_CHECKPOINT_REPLAY/"
      "STEP3E_FORMAL_COMPUTE_JOURNAL.jsonl"
)

FAILED_ATTEMPT_DIR = (
    STEP3
    / "06_AUDIT/STEP3E_EXACT_CHECKPOINT_REPLAY/"
      "FAILED_ATTEMPTS/FORMAL_BRANCH_RESULTS"
)

ACTIVE_EXECUTION_ID = None

DRYRUN_AUDIT = (
    STEP3
    / "06_AUDIT/STEP3E_EXACT_CHECKPOINT_REPLAY/"
      "STEP3E_FORMAL_RUNNER_NO_API_DRY_RUN.json"
)

EXECUTION_AUDIT = (
    STEP3
    / "06_AUDIT/STEP3E_EXACT_CHECKPOINT_REPLAY/"
      "STEP3E_FORMAL_EXECUTION_AUDIT.json"
)

REPRESENTATIVE_FINAL_AUDIT = (
    STEP3
    / "06_AUDIT/STEP3E_EXACT_CHECKPOINT_REPLAY/"
      "STEP3E_SIX_REPRESENTATIVE_RESULTS_FINAL_AUDIT.json"
)

REPRESENTATIVE_SHARD = (
    STEP3
    / "04_OUTPUTS/STEP3E_EXACT_CHECKPOINT_REPLAY/"
      "STEP3E_NEW_PATH_REPRESENTATIVE_SHARD.jsonl"
)

EXPECTED_REPRESENTATIVE_FINAL_AUDIT_SHA256 = (
    "1251d3aa4e54c0ff0c9f097f49d6c808"
    "2959b0c071b3ba9c75ff7906ff2272e5"
)

EXPECTED_REPRESENTATIVE_SHARD_SHA256 = (
    "ae188ac1def06f3a56ccd21e8ac1b782"
    "4e578bd9aeef79d466055fc251a32ba1"
)

EXPECTED_REPRESENTATIVE_RUNNER_SHA256 = (
    "72e57262990da309da81f5812e60b034"
    "d82340f058add0dc776c3de40ef19093"
)

MODEL = "gpt-5.6-terra"
REASONING_EFFORT = "medium"
MAX_OUTPUT_TOKENS = 2048

EXPECTED_HASHES = {
    DESCRIPTORS:
        "d7564ecb3c431b3c1640ddbf7de6fcb"
        "f7fc6d0cf458372a909e4a06c3c66042a",

    REFINE_CONTRACT:
        "939c37a82531f9875c11fe7328b086423"
        "daec9929267c8babbe0096a949d9229",

    REFINE_AMENDMENT:
        "bffe872d04b9140e40d4b261648082d"
        "248d6d43d3c03cc7a6b7ee172b750933e",

    BFCL_RUNTIME:
        "4f362df60fa5412b436c65e20027b210"
        "580108c259bdfd8cb06fc1b8056cf343",

    BFCL_WORKER:
        "993b60e6cd116b1f1ebe59cd79d3d284"
        "57338bc96309309b887d112320a7c7c0",

    TOOL_RUNTIME:
        "fb07cc373896efd885bc3fc26d2fa4eee"
        "9cd46998d0bdfa3c599fe29fd8ff1cf",

    TOOL_AUTH:
        "17085ffefae0a0e15c1d2d5642630639"
        "32d692011edf27ce8ae3d3803432ba08",
}

BFCL_AUTHORITIES = {
    "base": {
        "task": (
            STEP1
            / "02_INPUTS/RAW_AUTHORITY/BFCL/gorilla/"
              "berkeley-function-call-leaderboard/bfcl_eval/"
              "data/BFCL_v4_multi_turn_base.json"
        ),
        "task_sha256":
            "1a21a995d06fd6f20ba55de7bced30ef"
            "953ec35e998f502ec2ecf4d66ef1c43a",
        "gt": (
            STEP1
            / "02_INPUTS/RAW_AUTHORITY/BFCL/gorilla/"
              "berkeley-function-call-leaderboard/bfcl_eval/"
              "data/possible_answer/"
              "BFCL_v4_multi_turn_base.json"
        ),
        "gt_sha256":
            "1fee67823b317571649177dd89d63969f"
            "eaae4e810cc7448ee55ba797fb7c8fc",
    },
    "long_context": {
        "task": (
            STEP1
            / "02_INPUTS/RAW_AUTHORITY/BFCL/gorilla/"
              "berkeley-function-call-leaderboard/bfcl_eval/"
              "data/BFCL_v4_multi_turn_long_context.json"
        ),
        "task_sha256":
            "78c3268c5cc8e97c0f4ec6c811b3b9a"
            "2bba14323b1830b7a874b06d822749324",
        "gt": (
            STEP1
            / "02_INPUTS/RAW_AUTHORITY/BFCL/gorilla/"
              "berkeley-function-call-leaderboard/bfcl_eval/"
              "data/possible_answer/"
              "BFCL_v4_multi_turn_long_context.json"
        ),
        "gt_sha256":
            "e82aa0e839c39d23c64a05834f7ae024"
            "d7c9738ec21738ecee78dc876e3d0d18",
    },
    "miss_func": {
        "task": (
            STEP1
            / "02_INPUTS/RAW_AUTHORITY/BFCL/gorilla/"
              "berkeley-function-call-leaderboard/bfcl_eval/"
              "data/BFCL_v4_multi_turn_miss_func.json"
        ),
        "task_sha256":
            "87d28ce10e37d864b72de85d5732eef2"
            "a867b241d6c1c99b4ae682c9e3ea921c",
        "gt": (
            STEP1
            / "02_INPUTS/RAW_AUTHORITY/BFCL/gorilla/"
              "berkeley-function-call-leaderboard/bfcl_eval/"
              "data/possible_answer/"
              "BFCL_v4_multi_turn_miss_func.json"
        ),
        "gt_sha256":
            "69e679b806d1c871b05393a4b95583bb"
            "973248e5b8d96c2d7f4ca05e29fc32e6",
    },
    "miss_param": {
        "task": (
            STEP1
            / "02_INPUTS/RAW_AUTHORITY/BFCL/gorilla/"
              "berkeley-function-call-leaderboard/bfcl_eval/"
              "data/BFCL_v4_multi_turn_miss_param.json"
        ),
        "task_sha256":
            "f0c66dda3795f5f53e3e1c0cc8ba0246"
            "b6761c8f58bdba8317203bf451ab8838",
        "gt": (
            STEP1
            / "02_INPUTS/RAW_AUTHORITY/BFCL/gorilla/"
              "berkeley-function-call-leaderboard/bfcl_eval/"
              "data/possible_answer/"
              "BFCL_v4_multi_turn_miss_param.json"
        ),
        "gt_sha256":
            "59c442901779e2c31c33abcd566d032e"
            "03736e5ad8069de2fe05489873046ecf",
    },
}


def sha256_file(path):
    h = hashlib.sha256()

    with Path(path).open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def load_jsonl(path):
    rows = []

    with Path(path).open(
        encoding="utf-8"
    ) as f:
        for line in f:
            if line.strip():
                rows.append(
                    json.loads(line)
                )

    return rows


def load_json_flexible(path):
    text = Path(path).read_text(
        encoding="utf-8"
    ).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return [
            json.loads(line)
            for line in text.splitlines()
            if line.strip()
        ]


def write_json(path, obj):
    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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


def append_jsonl(path, obj):
    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "a",
        encoding="utf-8",
    ) as f:
        f.write(
            json.dumps(
                obj,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n"
        )


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(
        name,
        str(path),
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "MODULE_SPEC_FAILED="
            + str(path)
        )

    mod = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        mod
    )

    return mod


def verify_hashes():
    for path, expected in EXPECTED_HASHES.items():
        if not path.is_file():
            raise RuntimeError(
                "FROZEN_FILE_MISSING="
                + str(path)
            )

        actual = sha256_file(
            path
        )

        if actual != expected:
            raise RuntimeError(
                "FROZEN_HASH_MISMATCH="
                f"{path}:{actual}:{expected}"
            )

    for spec in BFCL_AUTHORITIES.values():
        for field in ("task", "gt"):
            path = spec[field]
            expected = spec[
                field + "_sha256"
            ]

            actual = sha256_file(
                path
            )

            if actual != expected:
                raise RuntimeError(
                    "BFCL_AUTHORITY_HASH_MISMATCH="
                    f"{path}:{actual}:{expected}"
                )


def descriptor_index():
    out = {}

    for row in load_jsonl(
        DESCRIPTORS
    ):
        key = (
            row["benchmark"],
            row["instance_id"],
            int(row["step_index"]),
        )

        if key in out:
            raise RuntimeError(
                "DUPLICATE_DESCRIPTOR="
                + repr(key)
            )

        out[key] = row

    return out


def get_singleton_descriptor(
    branch,
    descriptors,
):
    if (
        branch.get(
            "intervention_operator"
        )
        != "V_refine"
    ):
        raise RuntimeError(
            "COVERAGE_EXECUTOR_ONLY_SUPPORTS_V_REFINE="
            + branch["execution_id"]
        )

    steps = branch[
        "selected_steps_chronological"
    ]

    if len(steps) != 1:
        raise RuntimeError(
            "COVERAGE_EXECUTOR_ONLY_SUPPORTS_SINGLETON="
            + branch["execution_id"]
        )

    key = (
        branch["benchmark"],
        branch["instance_id"],
        int(steps[0]),
    )

    if key not in descriptors:
        raise RuntimeError(
            "DESCRIPTOR_NOT_FOUND="
            + repr(key)
        )

    return descriptors[key]


def load_runtime_rows(path):
    return load_jsonl(
        path
    )


def find_row(rows, instance_id):
    matches = [
        row
        for row in rows
        if row.get("instance_id")
        == instance_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            "RUNTIME_ROW_MATCH_COUNT="
            f"{instance_id}:{len(matches)}"
        )

    return matches[0]


def response_usage(response):
    usage = getattr(
        response,
        "usage",
        None,
    )

    if usage is None:
        return {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }

    return {
        "input_tokens":
            getattr(
                usage,
                "input_tokens",
                None,
            ),
        "output_tokens":
            getattr(
                usage,
                "output_tokens",
                None,
            ),
        "total_tokens":
            getattr(
                usage,
                "total_tokens",
                None,
            ),
    }


def record_compute_row(
    compute_rows,
    row,
):
    compute_rows.append(
        row
    )

    if ACTIVE_EXECUTION_ID is not None:
        durable = dict(
            row
        )

        durable[
            "execution_id"
        ] = ACTIVE_EXECUTION_ID

        append_jsonl(
            COMPUTE_JOURNAL,
            durable,
        )


def preserve_existing_nonpass_result(
    result_path,
    execution_id,
):
    result_path = Path(
        result_path
    )

    if not result_path.is_file():
        return None

    old = json.loads(
        result_path.read_text(
            encoding="utf-8"
        )
    )

    if old.get("status") == "PASS":
        return None

    FAILED_ATTEMPT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = time.strftime(
        "%Y%m%d_%H%M%S"
    )

    archive_path = (
        FAILED_ATTEMPT_DIR
        / (
            execution_id
            + "__"
            + stamp
            + "__"
            + str(time.time_ns())
            + ".json"
        )
    )

    write_json(
        archive_path,
        old,
    )

    return archive_path


def persist_empty_math_response_forensic(
    *,
    execution_id,
    instance_id,
    step_index,
    response,
    input_items=None,
    failure_status="EMPTY_MATH_REFINED_STEP_FORENSIC",
    call_site="frozen_refiner",
):
    forensic_dir = Path(
        "__DECOUPLE_ROOT__/"
        "10_PILOT/STEP3/04_OUTPUTS/"
        "STEP3E_EXACT_CHECKPOINT_REPLAY/"
        "MATH_EMPTY_RESPONSE_FORENSICS"
    )

    forensic_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    usage = getattr(
        response,
        "usage",
        None,
    )

    output_details = getattr(
        usage,
        "output_tokens_details",
        None,
    )

    outputs = []

    for item in (
        getattr(
            response,
            "output",
            None,
        )
        or []
    ):
        contents = []

        for part in (
            getattr(
                item,
                "content",
                None,
            )
            or []
        ):
            contents.append(
                {
                    "type":
                        getattr(
                            part,
                            "type",
                            None,
                        ),

                    "text":
                        getattr(
                            part,
                            "text",
                            None,
                        ),

                    "refusal":
                        getattr(
                            part,
                            "refusal",
                            None,
                        ),
                }
            )

        outputs.append(
            {
                "type":
                    getattr(
                        item,
                        "type",
                        None,
                    ),

                "id":
                    getattr(
                        item,
                        "id",
                        None,
                    ),

                "status":
                    getattr(
                        item,
                        "status",
                        None,
                    ),

                "role":
                    getattr(
                        item,
                        "role",
                        None,
                    ),

                "content":
                    contents,
            }
        )

    incomplete = getattr(
        response,
        "incomplete_details",
        None,
    )

    request_serialized = json.dumps(
        input_items,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )

    request_sha256 = hashlib.sha256(
        request_serialized.encode("utf-8")
    ).hexdigest()

    payload = {
        "status":
            failure_status,

        "call_site":
            call_site,

        "request_input_sha256":
            request_sha256,

        "request_serialized_chars":
            len(request_serialized),

        "request_item_count":
            (
                len(input_items)
                if isinstance(input_items, list)
                else None
            ),

        "request_model":
            MODEL,

        "request_reasoning_effort":
            REASONING_EFFORT,

        "request_max_output_tokens":
            MAX_OUTPUT_TOKENS,

        "scientific_result_valid":
            False,

        "Z":
            None,

        "execution_id":
            execution_id,

        "instance_id":
            instance_id,

        "step_index":
            step_index,

        "response_id":
            getattr(
                response,
                "id",
                None,
            ),

        "response_status":
            getattr(
                response,
                "status",
                None,
            ),

        "response_error":
            str(
                getattr(
                    response,
                    "error",
                    None,
                )
            ),

        "incomplete_details":
            (
                incomplete.model_dump()
                if hasattr(
                    incomplete,
                    "model_dump",
                )
                else (
                    str(incomplete)
                    if incomplete
                    is not None
                    else None
                )
            ),

        "output_text_repr":
            repr(
                getattr(
                    response,
                    "output_text",
                    None,
                )
            ),

        "usage_input_tokens":
            getattr(
                usage,
                "input_tokens",
                None,
            ),

        "usage_output_tokens":
            getattr(
                usage,
                "output_tokens",
                None,
            ),

        "usage_total_tokens":
            getattr(
                usage,
                "total_tokens",
                None,
            ),

        "reasoning_tokens":
            getattr(
                output_details,
                "reasoning_tokens",
                None,
            ),

        "output_item_count":
            len(outputs),

        "output_items":
            outputs,

        "scientific_semantics_changed":
            False,

        "retry_added":
            False,

        "failure_behavior_preserved":
            True,
    }

    path = (
        forensic_dir
        / (
            execution_id
            + "__step_"
            + str(step_index)
            + "__"
            + str(time.time_ns())
            + ".json"
        )
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "EMPTY_MATH_RESPONSE_FORENSIC="
        + str(path)
    )

    return path



def record_response_call(
    compute_rows,
    role,
    benchmark,
    instance_id,
    step_index,
    response,
    started,
    requested_temperature,
    effective_temperature_status,
    retry_count,
):
    usage = response_usage(
        response
    )

    record_compute_row(
        compute_rows,
        {
            "call_id":
                hashlib.sha256(
                    (
                        role
                        + "|"
                        + benchmark
                        + "|"
                        + instance_id
                        + "|"
                        + str(step_index)
                        + "|"
                        + str(
                            len(
                                compute_rows
                            )
                        )
                    ).encode()
                ).hexdigest(),

            "call_role":
                role,

            "benchmark":
                benchmark,

            "instance_id":
                instance_id,

            "step_index":
                step_index,

            "model_id":
                getattr(
                    response,
                    "model",
                    MODEL,
                ),

            "reasoning_effort":
                REASONING_EFFORT,

            "requested_temperature":
                requested_temperature,

            "effective_temperature_status":
                effective_temperature_status,

            "input_tokens":
                usage[
                    "input_tokens"
                ],

            "output_tokens":
                usage[
                    "output_tokens"
                ],

            "total_tokens":
                usage[
                    "total_tokens"
                ],

            "latency":
                time.perf_counter()
                - started,

            "retry_count":
                retry_count,

            "response_id":
                getattr(
                    response,
                    "id",
                    None,
                ),

            "wall_clock_seconds":
                time.time(),
        }
    )


def call_responses(
    client,
    *,
    role,
    benchmark,
    instance_id,
    step_index,
    input_items,
    compute_rows,
    tools=None,
    requested_temperature=None,
):
    kwargs = {
        "model": MODEL,
        "input": input_items,
        "reasoning": {
            "effort":
                REASONING_EFFORT,
        },
        "max_output_tokens":
            MAX_OUTPUT_TOKENS,
        "store":
            False,
    }

    if tools is not None:
        kwargs[
            "tools"
        ] = tools
        kwargs[
            "tool_choice"
        ] = "auto"
        kwargs[
            "parallel_tool_calls"
        ] = False

    retry_count = 0

    if requested_temperature is not None:
        kwargs[
            "temperature"
        ] = requested_temperature

    started = time.perf_counter()

    try:
        response = (
            client.responses.create(
                **kwargs
            )
        )

        effective = (
            "EXPLICIT_REQUEST_ACCEPTED"
            if requested_temperature
            is not None
            else "PROVIDER_DEFAULT"
        )

    except Exception as exc:
        if (
            requested_temperature
            is None
            or "temperature"
            not in str(exc).lower()
        ):
            raise

        record_compute_row(
            compute_rows,
            {
                "call_id":
                    hashlib.sha256(
                        (
                            "temperature_rejection|"
                            + benchmark
                            + "|"
                            + instance_id
                            + "|"
                            + str(step_index)
                            + "|"
                            + role
                        ).encode()
                    ).hexdigest(),

                "call_role":
                    role
                    + "_provider_parameter_rejection",

                "benchmark":
                    benchmark,

                "instance_id":
                    instance_id,

                "step_index":
                    step_index,

                "model_id":
                    MODEL,

                "reasoning_effort":
                    REASONING_EFFORT,

                "requested_temperature":
                    requested_temperature,

                "effective_temperature_status":
                    "REJECTED_BEFORE_MODEL_OUTPUT",

                "input_tokens":
                    0,

                "output_tokens":
                    0,

                "total_tokens":
                    0,

                "latency":
                    time.perf_counter()
                    - started,

                "retry_count":
                    0,

                "response_id":
                    None,

                "wall_clock_seconds":
                    time.time(),

                "provider_error":
                    str(exc),
            }
        )

        kwargs.pop(
            "temperature",
            None,
        )

        retry_count = 1
        started = time.perf_counter()

        response = (
            client.responses.create(
                **kwargs
            )
        )

        effective = (
            "PROVIDER_DEFAULT_AFTER_EXPLICIT_REJECTION"
        )

    if (
        getattr(
            response,
            "model",
            MODEL,
        )
        != MODEL
    ):
        raise RuntimeError(
            "RETURNED_MODEL_MISMATCH="
            + str(
                getattr(
                    response,
                    "model",
                    None,
                )
            )
        )

    record_response_call(
        compute_rows,
        role,
        benchmark,
        instance_id,
        step_index,
        response,
        started,
        requested_temperature,
        effective,
        retry_count,
    )

    return response


def make_component_input(
    frozen_prompt,
    *,
    current_history,
    archived_candidate_step,
    critique=None,
    tool_metadata=None,
):
    payload = {
        "current_pre_step_branch_history":
            current_history,

        "archived_selected_step":
            archived_candidate_step,
    }

    if critique is not None:
        payload[
            "frozen_critique"
        ] = critique

    if tool_metadata is not None:
        payload[
            "tool_metadata"
        ] = tool_metadata

    return [
        {
            "role":
                "developer",
            "content":
                frozen_prompt,
        },
        {
            "role":
                "user",
            "content":
                json.dumps(
                    payload,
                    sort_keys=True,
                    ensure_ascii=False,
                ),
        },
    ]


def extract_function_calls(
    response,
):
    return [
        item
        for item in response.output
        if getattr(
            item,
            "type",
            None,
        )
        == "function_call"
    ]


def bfcl_authority_key(
    instance_id,
):
    prefixes = (
        (
            "multi_turn_long_context_",
            "long_context",
        ),
        (
            "multi_turn_miss_func_",
            "miss_func",
        ),
        (
            "multi_turn_miss_param_",
            "miss_param",
        ),
        (
            "multi_turn_base_",
            "base",
        ),
    )

    for prefix, key in prefixes:
        if instance_id.startswith(prefix):
            return key

    raise RuntimeError(
        "BFCL_UNKNOWN_AUTHORITY_FAMILY="
        + instance_id
    )


def bfcl_grounded_prefix_restore(
    branch,
    desc,
    bfcl_mod,
    descriptors,
):
    archive = (
        ROOT
        / desc[
            "source_archive_path"
        ]
    )

    if (
        sha256_file(archive)
        != desc[
            "source_archive_sha256"
        ]
    ):
        raise RuntimeError(
            "BFCL_ARCHIVE_HASH_MISMATCH="
            + branch[
                "execution_id"
            ]
        )

    archive_obj = json.loads(
        archive.read_text(
            encoding="utf-8"
        )
    )

    pre_rows = load_jsonl(
        bfcl_mod.PRE
    )

    row = find_row(
        pre_rows,
        branch[
            "instance_id"
        ],
    )

    namespace = (
        "decouple_step3e_"
        + branch[
            "execution_id"
        ][:16]
    )

    worker = (
        bfcl_mod.BFCLDockerWorker(
            row,
            namespace,
        )
    )

    (
        GORILLA_TO_OPENAPI,
        ModelStyle,
        convert_to_tool,
    ) = bfcl_mod.load_tool_conversion()

    (
        convert_to_function_call,
        _,
    ) = (
        bfcl_mod
        .load_official_convert_to_function_call()
    )

    tools = convert_to_tool(
        worker.functions,
        GORILLA_TO_OPENAPI,
        ModelStyle.OPENAI_RESPONSES,
    )

    selected_step = int(
        branch[
            "selected_steps_chronological"
        ][0]
    )

    global_step = 0
    messages = []
    trace_turns = []

    for round_index, turn in enumerate(
        archive_obj["turns"]
    ):
        user_turn = [
            dict(x)
            for x in worker.question[
                round_index
            ]
        ]

        for message in user_turn:
            if (
                message.get("role")
                == "system"
            ):
                message[
                    "role"
                ] = "developer"

        messages.extend(
            user_turn
        )

        branch_turn = {
            "round_index":
                round_index,
            "user_messages":
                user_turn,
            "model_steps":
                [],
        }

        for model_step in turn[
            "model_steps"
        ]:
            calls = (
                model_step.get(
                    "function_calls",
                    [],
                )
                or []
            )

            terminal_text = (
                model_step.get(
                    "terminal_text"
                )
            )

            emitted_kinds = []

            if calls:
                emitted_kinds.append(
                    (
                        "joint_tool_call"
                        if len(calls) > 1
                        else "tool_call"
                    )
                )

            if (
                terminal_text is not None
                and terminal_text != ""
            ):
                emitted_kinds.append(
                    "assistant_text"
                )

            if len(emitted_kinds) > 1:
                raise RuntimeError(
                    "BFCL_RESTORE_DUAL_EMISSION_RAW_STEP="
                    + branch["execution_id"]
                    + ":round="
                    + str(round_index)
                )

            if not emitted_kinds:
                continue

            global_step += 1

            if global_step >= selected_step:
                trace_turns.append(
                    branch_turn
                )

                return {
                    "worker":
                        worker,
                    "row":
                        row,
                    "tools":
                        tools,
                    "convert_to_function_call":
                        convert_to_function_call,
                    "messages":
                        messages,
                    "trace_turns":
                        trace_turns,
                    "current_round_index":
                        round_index,
                    "selected_step":
                        selected_step,
                    "archive":
                        archive_obj,
                }

            prior_desc = descriptors[
                (
                    "BFCL",
                    branch[
                        "instance_id"
                    ],
                    global_step,
                )
            ]

            kind = prior_desc[
                "candidate_kind"
            ]

            if kind in {
                "tool_call",
                "joint_tool_call",
            }:
                expected_calls = (
                    model_step.get(
                        "function_calls",
                        []
                    )
                )

                execution_results = (
                    worker.execute(
                        expected_calls
                    )
                )

                expected_results = (
                    model_step.get(
                        "execution_results",
                        []
                    )
                )

                if (
                    execution_results
                    != expected_results
                ):
                    worker.close()

                    raise RuntimeError(
                        "BFCL_EXACT_PREFIX_OBSERVATION_MISMATCH="
                        f"{branch['instance_id']}:"
                        f"step={global_step}"
                    )

                normalized = (
                    prior_desc[
                        "archived_candidate_step"
                    ][
                        "function_calls"
                    ]
                )

                archived_outputs = (
                    model_step.get(
                        "function_call_outputs",
                        []
                    )
                )

                if (
                    len(normalized)
                    != len(
                        archived_outputs
                    )
                ):
                    worker.close()

                    raise RuntimeError(
                        "BFCL_PREFIX_CALL_ID_BINDING_MISMATCH="
                        f"{branch['instance_id']}:"
                        f"step={global_step}"
                    )

                for call, output in zip(
                    normalized,
                    archived_outputs,
                ):
                    messages.append(
                        {
                            "type":
                                "function_call",

                            "call_id":
                                output[
                                    "call_id"
                                ],

                            "name":
                                call[
                                    "function_name"
                                ],

                            "arguments":
                                json.dumps(
                                    call[
                                        "arguments"
                                    ],
                                    separators=(
                                        ",",
                                        ":",
                                    ),
                                    ensure_ascii=False,
                                ),
                        }
                    )

                    messages.append(
                        dict(output)
                    )

                branch_turn[
                    "model_steps"
                ].append(
                    {
                        "step_index":
                            global_step,

                        "function_calls":
                            expected_calls,

                        "execution_results":
                            execution_results,
                    }
                )

            elif kind == "assistant_text":
                text = (
                    prior_desc[
                        "archived_candidate_step"
                    ][
                        "text"
                    ]
                )

                messages.append(
                    {
                        "role":
                            "assistant",
                        "content":
                            text,
                    }
                )

                branch_turn[
                    "model_steps"
                ].append(
                    {
                        "step_index":
                            global_step,

                        "terminal_text":
                            text,

                        "function_calls":
                            [],
                    }
                )

            else:
                worker.close()

                raise RuntimeError(
                    "BFCL_UNKNOWN_PREFIX_KIND="
                    + str(kind)
                )

        trace_turns.append(
            branch_turn
        )

    worker.close()

    raise RuntimeError(
        "BFCL_SELECTED_STEP_NOT_REACHED="
        + branch[
            "execution_id"
        ]
    )


def bfcl_dry_run_branch(
    branch,
    desc,
    bfcl_mod,
    descriptors,
):
    state = (
        bfcl_grounded_prefix_restore(
            branch,
            desc,
            bfcl_mod,
            descriptors,
        )
    )

    state[
        "worker"
    ].close()

    return {
        "execution_id":
            branch[
                "execution_id"
            ],

        "benchmark":
            "BFCL",

        "instance_id":
            branch[
                "instance_id"
            ],

        "selected_step":
            state[
                "selected_step"
            ],

        "prefix_restoration":
            "PASS",

        "source_archive_sha256":
            desc[
                "source_archive_sha256"
            ],
    }


def toolalpaca_authority_binding(
    desc,
):
    archive = (
        ROOT
        / desc[
            "source_archive_path"
        ]
    )

    if (
        sha256_file(archive)
        != desc[
            "source_archive_sha256"
        ]
    ):
        raise RuntimeError(
            "TOOLALPACA_ARCHIVE_HASH_MISMATCH"
        )

    trajectory = json.loads(
        archive.read_text(
            encoding="utf-8"
        )
    )

    group_index = int(
        trajectory[
            "source_group_index"
        ]
    )

    instruction_index = int(
        trajectory[
            "source_instruction_index"
        ]
    )

    authority = json.loads(
        TOOL_AUTH.read_text(
            encoding="utf-8"
        )
    )

    api_info = authority[
        group_index
    ]

    instruction = (
        api_info[
            "Instructions"
        ][
            instruction_index
        ]
    )

    if (
        instruction
        != trajectory[
            "instruction"
        ]
    ):
        raise RuntimeError(
            "TOOLALPACA_INSTRUCTION_BINDING_MISMATCH"
        )

    golden = (
        api_info[
            "Golden_Answers"
        ][
            instruction_index
        ]
    )

    if not golden:
        raise RuntimeError(
            "TOOLALPACA_EMPTY_GOLDEN_ANSWER"
        )

    return {
        "trajectory":
            trajectory,

        "api_info":
            api_info,

        "instruction":
            instruction,

        "golden_answers":
            golden,

        "group_index":
            group_index,

        "instruction_index":
            instruction_index,
    }


def tool_dry_run_branch(
    branch,
    desc,
):
    binding = (
        toolalpaca_authority_binding(
            desc
        )
    )

    return {
        "execution_id":
            branch[
                "execution_id"
            ],

        "benchmark":
            "ToolAlpaca",

        "instance_id":
            branch[
                "instance_id"
            ],

        "selected_step":
            branch[
                "selected_steps_chronological"
            ][0],

        "source_group_index":
            binding[
                "group_index"
            ],

        "source_instruction_index":
            binding[
                "instruction_index"
            ],

        "instruction_exact_match":
            True,

        "golden_answer_count":
            len(
                binding[
                    "golden_answers"
                ]
            ),

        "authority_binding":
            "PASS",
    }


def normalize_bfcl_evaluator_diagnostic(
    value,
    _active=None,
):
    import datetime

    if _active is None:
        _active = set()

    if (
        value is None
        or isinstance(
            value,
            (str, int, float, bool),
        )
    ):
        return value

    if isinstance(
        value,
        (datetime.datetime, datetime.date, datetime.time),
    ):
        return {
            "__python_type__":
                type(value).__name__,
            "isoformat":
                value.isoformat(),
        }

    if isinstance(value, dict):
        normalized = {}

        for key, item in value.items():
            if not isinstance(
                key,
                (str, int, float, bool),
            ) and key is not None:
                raise TypeError(
                    "BFCL_DIAGNOSTIC_UNSUPPORTED_DICT_KEY_TYPE="
                    + type(key).__module__
                    + "."
                    + type(key).__name__
                )

            normalized[key] = (
                normalize_bfcl_evaluator_diagnostic(
                    item,
                    _active,
                )
            )

        return normalized

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            normalize_bfcl_evaluator_diagnostic(
                item,
                _active,
            )
            for item in value
        ]

    if isinstance(
        value,
        (set, frozenset),
    ):
        normalized_items = [
            normalize_bfcl_evaluator_diagnostic(
                item,
                _active,
            )
            for item in value
        ]

        return sorted(
            normalized_items,
            key=lambda item: json.dumps(
                item,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )

    cls = type(value)
    module_name = cls.__module__
    class_name = cls.__name__

    if (
        module_name.endswith(
            ".gorilla_file_system"
        )
        and class_name == "File"
    ):
        return {
            "__bfcl_type__":
                "File",
            "name":
                normalize_bfcl_evaluator_diagnostic(
                    value.name,
                    _active,
                ),
            "content":
                normalize_bfcl_evaluator_diagnostic(
                    value.content,
                    _active,
                ),
        }

    if (
        module_name.endswith(
            ".gorilla_file_system"
        )
        and class_name == "Directory"
    ):
        object_id = id(value)

        if object_id in _active:
            return {
                "__bfcl_cycle_ref__":
                    "Directory",
                "name":
                    getattr(
                        value,
                        "name",
                        None,
                    ),
            }

        _active.add(
            object_id
        )

        try:
            contents = {
                key:
                    normalize_bfcl_evaluator_diagnostic(
                        value.contents[key],
                        _active,
                    )
                for key in sorted(
                    value.contents.keys()
                )
            }

            return {
                "__bfcl_type__":
                    "Directory",
                "name":
                    value.name,
                "contents":
                    contents,
            }
        finally:
            _active.remove(
                object_id
            )

    bfcl_runtime_prefix = (
        "bfcl_eval.eval_checker.multi_turn_eval."
        "func_source_code."
    )

    if module_name.startswith(
        bfcl_runtime_prefix
    ):
        object_id = id(value)

        if object_id in _active:
            reference = {
                "__bfcl_cycle_ref__":
                    module_name
                    + "."
                    + class_name,
            }

            name = getattr(
                value,
                "name",
                None,
            )

            if isinstance(
                name,
                (str, int, float, bool),
            ) or name is None:
                reference["name"] = name

            return reference

        _active.add(
            object_id
        )

        try:
            public_state = {
                key:
                    normalize_bfcl_evaluator_diagnostic(
                        item,
                        _active,
                    )
                for key, item in vars(value).items()
                if not key.startswith("_")
            }

            return {
                "__bfcl_type__":
                    module_name
                    + "."
                    + class_name,
                "public_state":
                    public_state,
            }
        finally:
            _active.remove(
                object_id
            )

    raise TypeError(
        "BFCL_DIAGNOSTIC_UNSUPPORTED_TYPE="
        + module_name
        + "."
        + class_name
    )

def bfcl_terminal_utility(
    branch,
    state,
):
    bfcl_mod = state[
        "bfcl_mod"
    ]

    authority_key = (
        bfcl_authority_key(
            branch[
                "instance_id"
            ]
        )
    )

    authority = (
        BFCL_AUTHORITIES[
            authority_key
        ]
    )

    task_rows = (
        load_json_flexible(
            authority[
                "task"
            ]
        )
    )

    gt_rows = (
        load_json_flexible(
            authority[
                "gt"
            ]
        )
    )

    tasks = {
        x["id"]:
            x
        for x in task_rows
    }

    gt = {
        x["id"]:
            x[
                "ground_truth"
            ]
        for x in gt_rows
    }

    iid = branch[
        "instance_id"
    ]

    if iid not in tasks:
        raise RuntimeError(
            "BFCL_TASK_NOT_FOUND="
            + iid
        )

    if iid not in gt:
        raise RuntimeError(
            "BFCL_GT_NOT_FOUND="
            + iid
        )

    sys.path.insert(
        0,
        str(BFCL_ROOT),
    )

    from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import (
        multi_turn_checker,
    )

    decoded_turns = []

    for turn in state[
        "trace_turns"
    ]:
        decoded = []

        for step in turn[
            "model_steps"
        ]:
            calls = step.get(
                "function_calls",
                [],
            )

            if calls:
                decoded.append(
                    list(calls)
                )

        decoded_turns.append(
            decoded
        )

    if (
        len(decoded_turns)
        != len(
            gt[iid]
        )
    ):
        raise RuntimeError(
            "BFCL_TURN_COUNT_MISMATCH="
            f"{iid}:"
            f"{len(decoded_turns)}:"
            f"{len(gt[iid])}"
        )

    result = multi_turn_checker(
        decoded_turns,
        gt[iid],
        tasks[iid],
        state[
            "row"
        ][
            "category"
        ],
        MODEL,
    )

    terminal_outcome = (
        1
        if result.get(
            "valid"
        ) is True
        else 0
    )

    persisted_result = (
        normalize_bfcl_evaluator_diagnostic(
            result
        )
    )

    return (
        terminal_outcome,
        persisted_result,
    )


def math_runtime_history_from_descriptor(desc):
    history = []

    for item in desc[
        "frozen_base_history_reference"
    ]:
        history.append(
            dict(item)
        )

    return history


def render_math_causal_history(history):
    rendered = []

    for item in history:
        item_type = item.get(
            "type"
        )

        if item_type == "problem":
            rendered.append(
                "USER_OR_PROBLEM:\n"
                + item[
                    "content"
                ]
            )

        elif (
            item_type
            == "math_reasoning_step"
        ):
            rendered.append(
                "PRIOR_REASONING_STEP:\n"
                + item[
                    "content"
                ]
            )

        else:
            raise RuntimeError(
                "UNKNOWN_MATH_HISTORY_TYPE="
                + str(item_type)
            )

    return "\n\n".join(
        rendered
    )


def make_math_local_continuation_input(history):
    rendered = (
        render_math_causal_history(
            history
        )
    )

    instruction = (
        "Generate exactly one possible next local "
        "reasoning step from the causal history. "
        "Do not solve or continue beyond that one step."
    )

    prompt = (
        "You are sampling one local continuation "
        "from a frozen decision-time causal history "
        "for a research experiment.\n\n"
        + instruction
        + "\n\n"
        + "The sampled local decision must contain "
        + "no more than 256 non-reasoning output tokens."
        + "\n\nCAUSAL_HISTORY_BEGIN\n"
        + rendered
        + "\nCAUSAL_HISTORY_END"
    )

    return [
        {
            "role": "user",
            "content": prompt,
        }
    ]


def normalize_math_terminal_answer(text):
    value = str(
        text
        if text is not None
        else ""
    ).strip()

    boxed_marker = "\\boxed{"
    position = value.rfind(
        boxed_marker
    )

    if position >= 0:
        start = (
            position
            + len(boxed_marker)
        )

        depth = 1
        cursor = start

        while (
            cursor < len(value)
            and depth > 0
        ):
            char = value[cursor]

            if char == "{":
                depth += 1

            elif char == "}":
                depth -= 1

            cursor += 1

        if depth == 0:
            value = value[
                start:
                cursor - 1
            ]

    lower = value.lower()
    marker = "answer is"
    position = lower.rfind(
        marker
    )

    if position >= 0:
        value = value[
            position
            + len(marker):
        ].lstrip()

        if value.startswith(":"):
            value = value[1:].lstrip()

    else:
        heading_matches = list(
            re.finditer(
                r"(?im)^\s*#+\s*answer\s*:?\s*$",
                value,
            )
        )

        if heading_matches:
            value = value[
                heading_matches[-1].end():
            ]

    value = value.strip()

    trailing_marker = "\u043a\u0438"

    if value.endswith(
        trailing_marker
    ):
        value = value[
            :-len(trailing_marker)
        ].rstrip()

    while (
        value
        and value[-1]
        in ".,;:!?"
    ):
        value = value[:-1].rstrip()

    if (
        len(value) >= 2
        and value[0] == "$"
        and value[-1] == "$"
    ):
        value = value[1:-1].strip()

    value = value.replace(
        ",",
        "",
    )

    return value.strip()


def get_math_frozen_trajectory_horizon(desc):
    archive = (
        ROOT
        / desc[
            "source_archive_path"
        ]
    )

    if (
        sha256_file(archive)
        != desc[
            "source_archive_sha256"
        ]
    ):
        raise RuntimeError(
            "MATH_ARCHIVE_HASH_MISMATCH"
        )

    obj = json.loads(
        archive.read_text(
            encoding="utf-8"
        )
    )

    if (
        obj.get("artifact_type")
        != "archived_base_reasoning_sequence"
    ):
        raise RuntimeError(
            "MATH_ARCHIVE_ARTIFACT_TYPE_MISMATCH"
        )

    if (
        obj.get("benchmark")
        != "Math-Shepherd"
    ):
        raise RuntimeError(
            "MATH_ARCHIVE_BENCHMARK_MISMATCH"
        )

    steps = obj.get(
        "steps"
    )

    if not isinstance(
        steps,
        list,
    ):
        raise RuntimeError(
            "MATH_ARCHIVE_STEPS_NOT_LIST"
        )

    if not steps:
        raise RuntimeError(
            "MATH_ARCHIVE_STEPS_EMPTY"
        )

    frozen_horizon = int(
        obj.get(
            "step_count",
            len(steps),
        )
    )

    if frozen_horizon <= 0:
        raise RuntimeError(
            "MATH_FROZEN_TRAJECTORY_HORIZON_INVALID="
            + str(frozen_horizon)
        )

    if frozen_horizon != len(steps):
        raise RuntimeError(
            "MATH_ARCHIVE_STEP_COUNT_MISMATCH="
            + str(frozen_horizon)
            + ":"
            + str(len(steps))
        )

    return frozen_horizon


def extract_math_gold_from_archive(desc):
    archive = (
        ROOT
        / desc[
            "source_archive_path"
        ]
    )

    if (
        sha256_file(archive)
        != desc[
            "source_archive_sha256"
        ]
    ):
        raise RuntimeError(
            "MATH_ARCHIVE_HASH_MISMATCH"
        )

    obj = json.loads(
        archive.read_text(
            encoding="utf-8"
        )
    )

    if (
        obj.get("artifact_type")
        != "archived_base_reasoning_sequence"
    ):
        raise RuntimeError(
            "MATH_ARCHIVE_ARTIFACT_TYPE_MISMATCH"
        )

    if (
        obj.get("benchmark")
        != "Math-Shepherd"
    ):
        raise RuntimeError(
            "MATH_ARCHIVE_BENCHMARK_MISMATCH"
        )

    steps = obj.get(
        "steps"
    )

    if not isinstance(
        steps,
        list,
    ):
        raise RuntimeError(
            "MATH_ARCHIVE_STEPS_NOT_LIST"
        )

    if not steps:
        raise RuntimeError(
            "MATH_ARCHIVE_STEPS_EMPTY"
        )

    final_step = steps[-1]

    if not isinstance(
        final_step,
        dict,
    ):
        raise RuntimeError(
            "MATH_ARCHIVE_FINAL_STEP_NOT_OBJECT"
        )

    final_text = final_step.get(
        "step_text_raw"
    )

    if not isinstance(
        final_text,
        str,
    ):
        raise RuntimeError(
            "MATH_ARCHIVE_FINAL_STEP_TEXT_MISSING"
        )

    final_text = final_text.strip()

    answer_match = re.search(
        r"(?i)answer\s+is\s*:?\s*(.+?)\s*(?:\u043a\u0438)?\s*$",
        final_text,
    )

    if answer_match:
        answer = (
            answer_match.group(1)
            .strip()
        )

        if answer:
            return answer

    boxed_marker = "\\boxed{"
    position = final_text.rfind(
        boxed_marker
    )

    if position >= 0:
        start = (
            position
            + len(boxed_marker)
        )

        depth = 1
        cursor = start

        while (
            cursor < len(final_text)
            and depth > 0
        ):
            char = final_text[cursor]

            if char == "{":
                depth += 1

            elif char == "}":
                depth -= 1

            cursor += 1

        if depth == 0:
            boxed = final_text[
                start:
                cursor - 1
            ].strip()

            if boxed:
                return boxed

    heading_matches = list(
        re.finditer(
            r"(?im)^\s*#+\s*answer\s*:?\s*$",
            final_text,
        )
    )

    if heading_matches:
        answer = final_text[
            heading_matches[-1].end():
        ].strip()

        trailing_marker = "\u043a\u0438"

        if answer.endswith(
            trailing_marker
        ):
            answer = answer[
                :-len(trailing_marker)
            ].rstrip()

        if answer:
            return answer

    raise RuntimeError(
        "MATH_RELEASED_FINAL_ANSWER_NOT_EXTRACTABLE="
        + desc["instance_id"]
    )


def math_step_is_terminal(text):
    value = (
        text
        or ""
    )

    lower = value.lower()

    return (
        "answer is" in lower
        or "\\boxed{" in value
        or re.search(
            r"(?im)^\s*#+\s*answer\s*:?\s*$",
            value,
        )
        is not None
    )


def persist_math_failure_forensic(
    *,
    branch,
    generated_steps,
    intervention_records,
    compute_rows,
    current_step,
    watchdog_limit,
):
    forensic_dir = (
        STEP3
        / "04_OUTPUTS/STEP3E_EXACT_CHECKPOINT_REPLAY/"
          "MATH_FAILURE_FORENSICS"
    )

    forensic_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        forensic_dir
        / (
            branch["execution_id"]
            + ".json"
        )
    )

    payload = {
        "execution_id":
            branch["execution_id"],

        "benchmark":
            branch["benchmark"],

        "instance_id":
            branch["instance_id"],

        "status":
            "INFRASTRUCTURE_ABORT_FORENSIC",

        "scientific_result_valid":
            False,

        "terminal_outcome_Z":
            None,

        "current_step":
            int(current_step),

        "watchdog_limit":
            int(watchdog_limit),

        "generated_steps":
            generated_steps,

        "intervention_records":
            intervention_records,

        "compute_rows":
            compute_rows,
    }

    write_json(
        path,
        payload,
    )



def call_math_responses_with_completed_empty_replay_once(
    client,
    *,
    execution_id,
    role,
    benchmark,
    instance_id,
    step_index,
    input_items,
    compute_rows,
    failure_status,
    tools=None,
    requested_temperature=None,
):
    """
    Infrastructure-only recovery for the confirmed
    Math-Shepherd provider-completed empty-text class.

    Scientific semantics are unchanged.

    The first completed-empty response is preserved
    as forensic evidence and produces no scientific
    result. The exact effective provider request is
    replayed once. If the replay is also empty, the
    caller retains the pre-existing fail-closed path.
    """

    response = call_responses(
        client,
        role=role,
        benchmark=benchmark,
        instance_id=instance_id,
        step_index=step_index,
        input_items=input_items,
        compute_rows=compute_rows,
        tools=tools,
        requested_temperature=requested_temperature,
    )

    text = (
        getattr(
            response,
            "output_text",
            None,
        )
        or ""
    ).strip()

    if text:
        return response

    if (
        getattr(
            response,
            "status",
            None,
        )
        != "completed"
    ):
        return response

    if (
        getattr(
            response,
            "incomplete_details",
            None,
        )
        is not None
    ):
        return response

    persist_empty_math_response_forensic(
        execution_id=execution_id,
        instance_id=instance_id,
        step_index=step_index,
        response=response,
        input_items=input_items,
        failure_status=failure_status,
        call_site=role,
    )

    replay_temperature = (
        requested_temperature
    )

    if compute_rows:
        effective = (
            compute_rows[-1].get(
                "effective_temperature_status"
            )
        )

        if (
            effective
            == "PROVIDER_DEFAULT_AFTER_EXPLICIT_REJECTION"
        ):
            replay_temperature = None

    print(
        "MATH_COMPLETED_EMPTY_SAME_CALL_REPLAY="
        + execution_id
        + ":"
        + role
        + ":step="
        + str(step_index)
    )

    replay = call_responses(
        client,
        role=role,
        benchmark=benchmark,
        instance_id=instance_id,
        step_index=step_index,
        input_items=input_items,
        compute_rows=compute_rows,
        tools=tools,
        requested_temperature=replay_temperature,
    )

    if compute_rows:
        latest = compute_rows[-1]

        prior_retry_count = (
            latest.get(
                "retry_count",
                0,
            )
            or 0
        )

        latest[
            "retry_count"
        ] = max(
            int(prior_retry_count),
            1,
        )

    return replay

def execute_math_branch(
    branch,
    descriptors,
    client,
):
    if (
        branch[
            "intervention_operator"
        ]
        != "V_refine"
    ):
        raise RuntimeError(
            "MATH_ONLY_SUPPORTS_V_REFINE"
        )

    selected_steps = [
        int(x)
        for x in branch[
            "selected_steps_chronological"
        ]
    ]

    selected = set(
        selected_steps
    )

    first_key = (
        "Math-Shepherd",
        branch[
            "instance_id"
        ],
        selected_steps[0],
    )

    if first_key not in descriptors:
        raise RuntimeError(
            "MATH_FIRST_DESCRIPTOR_MISSING="
            + repr(first_key)
        )

    first_desc = descriptors[
        first_key
    ]

    math_frozen_trajectory_horizon = (
        get_math_frozen_trajectory_horizon(
            first_desc
        )
    )

    for selected_step in selected_steps:
        if (
            selected_step
            > math_frozen_trajectory_horizon
        ):
            raise RuntimeError(
                "MATH_SELECTED_STEP_EXCEEDS_"
                "FROZEN_TRAJECTORY_HORIZON="
                + str(selected_step)
                + ":"
                + str(
                    math_frozen_trajectory_horizon
                )
            )

    history = (
        math_runtime_history_from_descriptor(
            first_desc
        )
    )

    contract = json.loads(
        REFINE_CONTRACT.read_text(
            encoding="utf-8"
        )
    )

    amendment = json.loads(
        REFINE_AMENDMENT.read_text(
            encoding="utf-8"
        )
    )

    critic_prompt = contract[
        "critic"
    ][
        "prompt"
    ]

    refiner_prompt = amendment[
        "refiner"
    ][
        "prompt"
    ]

    compute_rows = []
    generated_steps = []
    intervention_records = []
    current_step = selected_steps[0]
    terminal_text = ""

    math_watchdog_path = (
        ROOT
        / "10_PILOT/STEP3/00_CONFIG/"
          "STEP3_INTERVENTION/"
          "STEP3E_MATH_GENERALIZED_TERMINATION_"
          "RUNTIME_SAFETY_AMENDMENT.json"
    )

    math_watchdog = json.loads(
        math_watchdog_path.read_text(
            encoding="utf-8"
        )
    )

    if (
        math_watchdog.get("status")
        !=
        "PASS_FROZEN_RUNTIME_REPAIR_AUTHORITY"
    ):
        raise RuntimeError(
            "MATH_RUNTIME_SAFETY_AUTHORITY_NOT_PASS"
        )

    if (
        math_watchdog.get(
            "watchdog_assigns_terminal_outcome_Z"
        )
        is not False
    ):
        raise RuntimeError(
            "MATH_RUNTIME_SAFETY_Z_POLICY_INVALID"
        )

    math_watchdog_step_limit = int(
        math_watchdog[
            "watchdog_max_step_index"
        ]
    )

    if (
        math_frozen_trajectory_horizon
        > math_watchdog_step_limit
    ):
        raise RuntimeError(
            "MATH_FROZEN_TRAJECTORY_HORIZON_"
            "EXCEEDS_RUNTIME_WATCHDOG="
            + str(
                math_frozen_trajectory_horizon
            )
            + ":"
            + str(
                math_watchdog_step_limit
            )
        )

    if (
        current_step
        > math_frozen_trajectory_horizon
    ):
        raise RuntimeError(
            "MATH_FIRST_SELECTED_STEP_EXCEEDS_"
            "FROZEN_TRAJECTORY_HORIZON="
            + str(current_step)
            + ":"
            + str(
                math_frozen_trajectory_horizon
            )
        )

    if current_step > math_watchdog_step_limit:
        raise RuntimeError(
            "MATH_FIRST_SELECTED_STEP_EXCEEDS_"
            "RUNTIME_WATCHDOG="
            + str(current_step)
        )

    while (
        current_step
        <= math_frozen_trajectory_horizon
    ):
        if current_step in selected:
            key = (
                "Math-Shepherd",
                branch[
                    "instance_id"
                ],
                current_step,
            )

            if key not in descriptors:
                raise RuntimeError(
                    "MATH_SELECTED_DESCRIPTOR_MISSING="
                    + repr(key)
                )

            desc = descriptors[key]

            critic_input = make_component_input(
                critic_prompt,
                current_history=
                    history,
                archived_candidate_step=
                    desc[
                        "archived_candidate_step"
                    ],
            )

            critic = call_responses(
                client,
                role="frozen_critic",
                benchmark="Math-Shepherd",
                instance_id=
                    branch[
                        "instance_id"
                    ],
                step_index=
                    current_step,
                input_items=
                    critic_input,
                compute_rows=
                    compute_rows,
            )

            critique = (
                critic.output_text
                or ""
            )

            if not critique.strip():
                raise RuntimeError(
                    "EMPTY_MATH_CRITIQUE"
                )

            refiner_input = make_component_input(
                refiner_prompt,
                current_history=
                    history,
                archived_candidate_step=
                    desc[
                        "archived_candidate_step"
                    ],
                critique=
                    critique,
            )

            refined = call_math_responses_with_completed_empty_replay_once(
                client,
                execution_id=
                    branch[
                        "execution_id"
                    ],
                role="frozen_refiner",
                benchmark="Math-Shepherd",
                instance_id=
                    branch[
                        "instance_id"
                    ],
                step_index=
                    current_step,
                input_items=
                    refiner_input,
                compute_rows=
                    compute_rows,
                failure_status=
                    "EMPTY_MATH_REFINED_STEP_FORENSIC",
                requested_temperature=
                    0.2,
            )

            text_step = (
                refined.output_text
                or ""
            ).strip()

            if not text_step:
                persist_empty_math_response_forensic(
                    execution_id=
                        branch[
                            "execution_id"
                        ],
                    instance_id=
                        branch[
                            "instance_id"
                        ],
                    step_index=
                        current_step,
                    response=
                        refined,
                    input_items=
                        refiner_input,
                    failure_status=
                        "EMPTY_MATH_REFINED_STEP_FORENSIC",
                    call_site=
                        "frozen_refiner",
                )

                raise RuntimeError(
                    "EMPTY_MATH_REFINED_STEP"
                )

            intervention_records.append(
                {
                    "step_index":
                        current_step,
                    "critic_output":
                        critique,
                    "refined_step":
                        text_step,
                }
            )

        else:
            continuation_input = (
                make_math_local_continuation_input(
                    history
                )
            )

            continuation = call_math_responses_with_completed_empty_replay_once(
                client,
                execution_id=
                    branch[
                        "execution_id"
                    ],
                role=
                    "branch_continuation_generator",
                benchmark=
                    "Math-Shepherd",
                instance_id=
                    branch[
                        "instance_id"
                    ],
                step_index=
                    current_step,
                input_items=
                    continuation_input,
                compute_rows=
                    compute_rows,
                failure_status=
                    "EMPTY_MATH_CONTINUATION_STEP_FORENSIC",
            )

            text_step = (
                continuation.output_text
                or ""
            ).strip()

            if not text_step:
                persist_empty_math_response_forensic(
                    execution_id=
                        branch[
                            "execution_id"
                        ],
                    instance_id=
                        branch[
                            "instance_id"
                        ],
                    step_index=
                        current_step,
                    response=
                        continuation,
                    input_items=
                        continuation_input,
                    failure_status=
                        "EMPTY_MATH_CONTINUATION_STEP_FORENSIC",
                    call_site=
                        "branch_continuation_generator",
                )

                raise RuntimeError(
                    "EMPTY_MATH_CONTINUATION_STEP"
                )

        generated_steps.append(
            {
                "step_index":
                    current_step,
                "text":
                    text_step,
                "source":
                    (
                        "refined_intervention"
                        if current_step
                        in selected
                        else
                        "branch_continuation"
                    ),
            }
        )

        history.append(
            {
                "type":
                    "math_reasoning_step",
                "step_index":
                    current_step,
                "content":
                    text_step,
                "observation":
                    "",
            }
        )

        if math_step_is_terminal(
            text_step
        ):
            terminal_text = text_step
            break

        if (
            current_step
            == math_frozen_trajectory_horizon
        ):
            terminal_text = text_step
            break

        current_step += 1

    if not terminal_text:
        persist_math_failure_forensic(
            branch=branch,
            generated_steps=generated_steps,
            intervention_records=intervention_records,
            compute_rows=compute_rows,
            current_step=current_step,
            watchdog_limit=math_watchdog_step_limit,
        )

        raise RuntimeError(
            "MATH_INFRASTRUCTURE_WATCHDOG_ABORT="
            + branch["execution_id"]
            + ":limit="
            + str(math_watchdog_step_limit)
            + ":next_step="
            + str(current_step)
        )

    gold_raw = (
        extract_math_gold_from_archive(
            first_desc
        )
    )

    candidate_normalized = (
        normalize_math_terminal_answer(
            terminal_text
        )
    )

    gold_normalized = (
        normalize_math_terminal_answer(
            gold_raw
        )
    )

    z = (
        1
        if (
            candidate_normalized
            == gold_normalized
        )
        else 0
    )

    return {
        "execution_id":
            branch[
                "execution_id"
            ],
        "benchmark":
            "Math-Shepherd",
        "instance_id":
            branch[
                "instance_id"
            ],
        "intervention_operator":
            "V_refine",
        "selected_steps_chronological":
            selected_steps,
        "exact_restoration_certified":
            True,
        "approximate_restoration":
            False,
        "generated_steps":
            generated_steps,
        "intervention_records":
            intervention_records,
        "terminal_answer_raw":
            terminal_text,
        "terminal_answer_normalized":
            candidate_normalized,
        "gold_answer_normalized":
            gold_normalized,
        "terminal_outcome_Z":
            z,
        "compute_rows":
            compute_rows,
        "status":
            "PASS",
    }

def execute_bfcl_branch(
    branch,
    desc,
    bfcl_mod,
    descriptors,
    client,
):
    state = (
        bfcl_grounded_prefix_restore(
            branch,
            desc,
            bfcl_mod,
            descriptors,
        )
    )

    worker = state[
        "worker"
    ]

    compute_rows = []

    try:
        contract = json.loads(
            REFINE_CONTRACT.read_text(
                encoding="utf-8"
            )
        )

        amendment = json.loads(
            REFINE_AMENDMENT.read_text(
                encoding="utf-8"
            )
        )

        critic_prompt = (
            contract[
                "critic"
            ][
                "prompt"
            ]
        )

        refiner_prompt = (
            amendment[
                "refiner"
            ][
                "prompt"
            ]
        )

        selected_step = (
            state[
                "selected_step"
            ]
        )

        current_history = desc[
            "frozen_base_history_reference"
        ]

        candidate = desc[
            "archived_candidate_step"
        ]

        critic_input = (
            make_component_input(
                critic_prompt,
                current_history=
                    current_history,
                archived_candidate_step=
                    candidate,
                tool_metadata=
                    state[
                        "worker"
                    ].functions,
            )
        )

        critic_response = (
            call_responses(
                client,
                role=
                    "frozen_critic",
                benchmark=
                    "BFCL",
                instance_id=
                    branch[
                        "instance_id"
                    ],
                step_index=
                    selected_step,
                input_items=
                    critic_input,
                compute_rows=
                    compute_rows,
            )
        )

        critique = (
            critic_response.output_text
            or ""
        )

        if not critique.strip():
            raise RuntimeError(
                "EMPTY_CRITIQUE"
            )

        refiner_input = (
            make_component_input(
                refiner_prompt,
                current_history=
                    current_history,
                archived_candidate_step=
                    candidate,
                critique=
                    critique,
                tool_metadata=
                    state[
                        "worker"
                    ].functions,
            )
        )

        candidate_kind = desc[
            "candidate_kind"
        ]

        refiner_response = (
            call_responses(
                client,
                role=
                    "frozen_refiner",
                benchmark=
                    "BFCL",
                instance_id=
                    branch[
                        "instance_id"
                    ],
                step_index=
                    selected_step,
                input_items=
                    refiner_input,
                compute_rows=
                    compute_rows,
                tools=(
                    state[
                        "tools"
                    ]
                    if candidate_kind
                    == "tool_call"
                    else None
                ),
                requested_temperature=
                    0.2,
            )
        )

        trace_turn = state[
            "trace_turns"
        ][-1]

        function_calls = (
            extract_function_calls(
                refiner_response
            )
        )

        state[
            "messages"
        ].extend(
            list(
                refiner_response.output
            )
        )

        if function_calls:
            model_responses = [
                {
                    call.name:
                        call.arguments
                }
                for call in function_calls
            ]

            executable_calls = (
                state[
                    "convert_to_function_call"
                ](
                    model_responses
                )
            )

            if (
                len(executable_calls)
                != len(
                    function_calls
                )
            ):
                raise RuntimeError(
                    "BFCL_REFINER_DECODE_COUNT_MISMATCH"
                )

            results = worker.execute(
                executable_calls
            )

            if (
                len(results)
                != len(
                    function_calls
                )
            ):
                raise RuntimeError(
                    "BFCL_REFINER_EXECUTION_COUNT_MISMATCH"
                )

            outputs = []

            for call, result in zip(
                function_calls,
                results,
            ):
                out = {
                    "type":
                        "function_call_output",
                    "call_id":
                        call.call_id,
                    "output":
                        result,
                }

                state[
                    "messages"
                ].append(
                    out
                )

                outputs.append(
                    out
                )

            trace_turn[
                "model_steps"
            ].append(
                {
                    "step_index":
                        selected_step,
                    "source":
                        "refined_intervention",
                    "function_calls":
                        executable_calls,
                    "execution_results":
                        results,
                    "function_call_outputs":
                        outputs,
                }
            )

            round_terminated = False

        else:
            text = (
                refiner_response.output_text
                or ""
            )

            if not text.strip():
                raise RuntimeError(
                    "BFCL_REFINER_EMPTY_STEP"
                )

            trace_turn[
                "model_steps"
            ].append(
                {
                    "step_index":
                        selected_step,
                    "source":
                        "refined_intervention",
                    "terminal_text":
                        text,
                    "function_calls":
                        [],
                }
            )

            round_terminated = True

        round_index = state[
            "current_round_index"
        ]

        next_step_index = (
            selected_step + 1
        )

        while True:
            if round_terminated:
                round_index += 1

                if (
                    round_index
                    >= len(
                        state[
                            "worker"
                        ].question
                    )
                ):
                    break

                user_turn = [
                    dict(x)
                    for x in state[
                        "worker"
                    ].question[
                        round_index
                    ]
                ]

                for message in user_turn:
                    if (
                        message.get(
                            "role"
                        )
                        == "system"
                    ):
                        message[
                            "role"
                        ] = "developer"

                state[
                    "messages"
                ].extend(
                    user_turn
                )

                trace_turn = {
                    "round_index":
                        round_index,
                    "user_messages":
                        user_turn,
                    "model_steps":
                        [],
                }

                state[
                    "trace_turns"
                ].append(
                    trace_turn
                )

                round_terminated = False

            started = (
                time.perf_counter()
            )

            response = (
                client.responses.create(
                    model=MODEL,
                    input=
                        state[
                            "messages"
                        ],
                    tools=
                        state[
                            "tools"
                        ],
                    reasoning={
                        "effort":
                            REASONING_EFFORT,
                    },
                    max_output_tokens=
                        MAX_OUTPUT_TOKENS,
                    store=False,
                )
            )

            record_response_call(
                compute_rows,
                "branch_continuation_generator",
                "BFCL",
                branch[
                    "instance_id"
                ],
                next_step_index,
                response,
                started,
                None,
                "PROVIDER_DEFAULT",
                0,
            )

            calls = (
                extract_function_calls(
                    response
                )
            )

            state[
                "messages"
            ].extend(
                list(
                    response.output
                )
            )

            if not calls:
                text = (
                    response.output_text
                    or ""
                )

                trace_turn[
                    "model_steps"
                ].append(
                    {
                        "step_index":
                            next_step_index,
                        "source":
                            "branch_continuation",
                        "terminal_text":
                            text,
                        "function_calls":
                            [],
                    }
                )

                round_terminated = True
                next_step_index += 1
                continue

            model_responses = [
                {
                    call.name:
                        call.arguments
                }
                for call in calls
            ]

            executable_calls = (
                state[
                    "convert_to_function_call"
                ](
                    model_responses
                )
            )

            results = worker.execute(
                executable_calls
            )

            outputs = []

            for call, result in zip(
                calls,
                results,
            ):
                out = {
                    "type":
                        "function_call_output",
                    "call_id":
                        call.call_id,
                    "output":
                        result,
                }

                state[
                    "messages"
                ].append(
                    out
                )

                outputs.append(
                    out
                )

            trace_turn[
                "model_steps"
            ].append(
                {
                    "step_index":
                        next_step_index,
                    "source":
                        "branch_continuation",
                    "function_calls":
                        executable_calls,
                    "execution_results":
                        results,
                    "function_call_outputs":
                        outputs,
                }
            )

            next_step_index += 1


        state[
            "bfcl_mod"
        ] = bfcl_mod

        z, evaluator_result = (
            bfcl_terminal_utility(
                branch,
                state,
            )
        )

        return {
            "execution_id":
                branch[
                    "execution_id"
                ],

            "benchmark":
                "BFCL",

            "instance_id":
                branch[
                    "instance_id"
                ],

            "intervention_operator":
                "V_refine",

            "selected_steps_chronological":
                branch[
                    "selected_steps_chronological"
                ],

            "exact_restoration_certified":
                True,

            "approximate_restoration":
                False,

            "critic_output":
                critique,

            "terminal_outcome_Z":
                z,

            "terminal_evaluator_result":
                evaluator_result,

            "trace_turns":
                state[
                    "trace_turns"
                ],

            "compute_rows":
                compute_rows,

            "status":
                "PASS",
        }

    finally:
        worker.close()


def execute_tool_branch(
    branch,
    desc,
    tool_mod,
    client,
):
    binding = (
        toolalpaca_authority_binding(
            desc
        )
    )

    trajectory = binding[
        "trajectory"
    ]

    pre_rows = load_jsonl(
        tool_mod.PRE_PATH
    )

    row = find_row(
        pre_rows,
        branch[
            "instance_id"
        ],
    )

    tools, op_lookup = (
        tool_mod.build_tools(
            row[
                "documentation"
            ]
        )
    )

    history = [
        {
            "role":
                "user",
            "content":
                row[
                    "instruction"
                ],
        }
    ]

    compute_rows = []

    contract = json.loads(
        REFINE_CONTRACT.read_text(
            encoding="utf-8"
        )
    )

    amendment = json.loads(
        REFINE_AMENDMENT.read_text(
            encoding="utf-8"
        )
    )

    critic_input = (
        make_component_input(
            contract[
                "critic"
            ][
                "prompt"
            ],
            current_history=
                desc[
                    "frozen_base_history_reference"
                ],
            archived_candidate_step=
                desc[
                    "archived_candidate_step"
                ],
            tool_metadata=
                row[
                    "documentation"
                ],
        )
    )

    critic = call_responses(
        client,
        role=
            "frozen_critic",
        benchmark=
            "ToolAlpaca",
        instance_id=
            branch[
                "instance_id"
            ],
        step_index=1,
        input_items=
            critic_input,
        compute_rows=
            compute_rows,
    )

    critique = (
        critic.output_text
        or ""
    )

    if not critique.strip():
        raise RuntimeError(
            "EMPTY_TOOLALPACA_CRITIQUE"
        )

    refiner_input = (
        make_component_input(
            amendment[
                "refiner"
            ][
                "prompt"
            ],
            current_history=
                desc[
                    "frozen_base_history_reference"
                ],
            archived_candidate_step=
                desc[
                    "archived_candidate_step"
                ],
            critique=
                critique,
            tool_metadata=
                row[
                    "documentation"
                ],
        )
    )

    refined = call_responses(
        client,
        role=
            "frozen_refiner",
        benchmark=
            "ToolAlpaca",
        instance_id=
            branch[
                "instance_id"
            ],
        step_index=1,
        input_items=
            refiner_input,
        compute_rows=
            compute_rows,
        tools=tools,
        requested_temperature=
            0.2,
    )

    history.extend(
        list(
            refined.output
        )
    )

    actions = []
    final_answer = ""

    simulator_freeze = json.loads(
        tool_mod.FREEZE_PATH.read_text(
            encoding="utf-8"
        )
    )

    simulator_template = Template(
        tool_mod.SIMULATOR_PROMPT_PATH.read_text(
            encoding="utf-8"
        )
    )

    current_response = refined
    turn_index = 1

    while True:
        function_calls = (
            extract_function_calls(
                current_response
            )
        )

        if not function_calls:
            final_answer = (
                current_response.output_text
                or ""
            )
            break

        for call in function_calls:
            name = call.name

            try:
                arguments = (
                    json.loads(
                        call.arguments
                    )
                )
            except Exception:
                arguments = {}

            if name not in op_lookup:
                observation = (
                    "Status Code: 404. "
                    "Response: "
                    '{"message":"Function not found."}'
                )

                status_code = 404

                simulator_record = {
                    "simulator_called":
                        False,
                    "reason":
                        "unknown_function",
                }

            else:
                request_text = (
                    tool_mod.build_request(
                        row[
                            "api_name"
                        ],
                        op_lookup[
                            name
                        ],
                        arguments,
                    )
                )

                simulator_prompt = (
                    simulator_template
                    .safe_substitute(
                        Name=
                            row[
                                "api_name"
                            ],
                        Documentation=
                            row[
                                "documentation"
                            ],
                        Request=
                            request_text,
                    )
                )

                started = (
                    time.perf_counter()
                )

                sim_response = (
                    client.chat.completions.create(
                        model=
                            simulator_freeze[
                                "model"
                            ],
                        messages=[
                            {
                                "role":
                                    "user",
                                "content":
                                    simulator_prompt,
                            }
                        ],
                        temperature=float(
                            simulator_freeze[
                                "temperature"
                            ]
                        ),
                        top_p=float(
                            simulator_freeze[
                                "top_p"
                            ]
                        ),
                        n=int(
                            simulator_freeze[
                                "n"
                            ]
                        ),
                        reasoning_effort=
                            simulator_freeze[
                                "reasoning_effort"
                            ],
                    )
                )

                sim_usage = (
                    tool_mod.chat_usage(
                        sim_response
                    )
                )

                raw = (
                    sim_response
                    .choices[0]
                    .message
                    .content
                    or ""
                )

                (
                    status_code,
                    response_body,
                ) = (
                    tool_mod
                    .parse_simulator_output(
                        raw
                    )
                )

                observation = (
                    "Status Code: "
                    f"{status_code}. "
                    "Response: "
                    + json.dumps(
                        response_body,
                        ensure_ascii=False,
                    )
                )

                compute_rows.append(
                    {
                        "call_id":
                            hashlib.sha256(
                                (
                                    "tool_simulator|"
                                    + branch[
                                        "execution_id"
                                    ]
                                    + "|"
                                    + str(
                                        len(
                                            actions
                                        )
                                    )
                                ).encode()
                            ).hexdigest(),

                        "call_role":
                            "environment_simulator",

                        "benchmark":
                            "ToolAlpaca",

                        "instance_id":
                            branch[
                                "instance_id"
                            ],

                        "step_index":
                            turn_index,

                        "model_id":
                            simulator_freeze[
                                "model"
                            ],

                        "reasoning_effort":
                            simulator_freeze[
                                "reasoning_effort"
                            ],

                        "requested_temperature":
                            simulator_freeze[
                                "temperature"
                            ],

                        "effective_temperature_status":
                            "FROZEN_SIMULATOR_PARAMETER",

                        "input_tokens":
                            sim_usage[
                                "input_tokens"
                            ],

                        "output_tokens":
                            sim_usage[
                                "output_tokens"
                            ],

                        "total_tokens":
                            sim_usage[
                                "total_tokens"
                            ],

                        "latency":
                            time.perf_counter()
                            - started,

                        "retry_count":
                            0,

                        "response_id":
                            None,

                        "wall_clock_seconds":
                            time.time(),
                    }
                )

                simulator_record = {
                    "simulator_called":
                        True,
                    "model":
                        simulator_freeze[
                            "model"
                        ],
                    "temperature":
                        simulator_freeze[
                            "temperature"
                        ],
                    "top_p":
                        simulator_freeze[
                            "top_p"
                        ],
                    "request":
                        request_text,
                    "raw_output":
                        raw,
                }

            history.append(
                {
                    "type":
                        "function_call_output",
                    "call_id":
                        call.call_id,
                    "output":
                        observation,
                }
            )

            actions.append(
                {
                    "action_index":
                        len(
                            actions
                        )
                        + 1,

                    "turn_index":
                        turn_index,

                    "function_name":
                        name,

                    "arguments":
                        arguments,

                    "call_id":
                        call.call_id,

                    "status_code":
                        status_code,

                    "observation":
                        observation,

                    "simulator":
                        simulator_record,
                }
            )

        turn_index += 1

        if turn_index > 12:
            raise RuntimeError(
                "TOOLALPACA_EXCEEDED_12_AGENT_TURNS"
            )

        current_response = (
            call_responses(
                client,
                role=
                    "branch_continuation_generator",
                benchmark=
                    "ToolAlpaca",
                instance_id=
                    branch[
                        "instance_id"
                    ],
                step_index=
                    turn_index,
                input_items=
                    history,
                compute_rows=
                    compute_rows,
                tools=
                    tools,
            )
        )

        history.extend(
            list(
                current_response.output
            )
        )

    standard_answer = ""

    for i, ans in enumerate(
        binding[
            "golden_answers"
        ]
    ):
        standard_answer += (
            f"{i + 1}. Function: "
            f"{ans['Action']}\n"
            "Parameters: "
            f"{ans['Action_Input']}\n"
        )

    solution = ""

    for i, action in enumerate(
        actions
    ):
        solution += (
            f"{i + 1}. Function: "
            f"{action['function_name']}\n"
            "Parameters: "
            + json.dumps(
                action[
                    "arguments"
                ],
                ensure_ascii=False,
            )
            + "\n"
            "Retruns: "
            + action[
                "observation"
            ]
            + "\n"
        )

    solution += (
        f"{len(actions) + 1}. "
        "Final Response: "
        + final_answer
    )

    terminal_contract = json.loads(
        TERMINAL_CONTRACT.read_text(
            encoding="utf-8"
        )
    )

    eval_prompt_path = Path(
        terminal_contract[
            "toolalpaca"
        ][
            "evaluation_prompt_path"
        ]
    )

    if (
        sha256_file(
            eval_prompt_path
        )
        != terminal_contract[
            "toolalpaca"
        ][
            "evaluation_prompt_sha256"
        ]
    ):
        raise RuntimeError(
            "TOOLALPACA_EVALUATION_PROMPT_HASH_MISMATCH"
        )

    eval_template = Template(
        eval_prompt_path.read_text(
            encoding="utf-8"
        )
    )

    judge_prompt = (
        eval_template.substitute(
            documentation=
                binding[
                    "api_info"
                ][
                    "NLDocumentation"
                ],
            instruction=
                binding[
                    "instruction"
                ],
            standard=
                standard_answer,
            solution=
                solution,
        )
    )

    judge = call_responses(
        client,
        role=
            "terminal_utility_evaluator",
        benchmark=
            "ToolAlpaca",
        instance_id=
            branch[
                "instance_id"
            ],
        step_index=None,
        input_items=[
            {
                "role":
                    "user",
                "content":
                    judge_prompt,
            }
        ],
        compute_rows=
            compute_rows,
    )

    judge_text = (
        judge.output_text
        or ""
    )

    results_text = (
        judge_text.split(
            "## Results",
            1,
        )[-1]
    )

    process_match = re.search(
        r"Process Correctness: (\w+)",
        results_text,
    )

    final_match = re.search(
        r"Final Response Correctness: (\w+)",
        results_text,
    )

    process_word = (
        process_match.group(1)
        if process_match
        else ""
    )

    final_word = (
        final_match.group(1)
        if final_match
        else ""
    )

    z = (
        1
        if (
            process_word == "Yes"
            and final_word == "Yes"
        )
        else 0
    )

    return {
        "execution_id":
            branch[
                "execution_id"
            ],

        "benchmark":
            "ToolAlpaca",

        "instance_id":
            branch[
                "instance_id"
            ],

        "intervention_operator":
            "V_refine",

        "selected_steps_chronological":
            branch[
                "selected_steps_chronological"
            ],

        "exact_restoration_certified":
            True,

        "approximate_restoration":
            False,

        "critic_output":
            critique,

        "actions":
            actions,

        "final_answer":
            final_answer,

        "terminal_judge_output":
            judge_text,

        "process_correctness":
            process_word,

        "final_response_correctness":
            final_word,

        "terminal_outcome_Z":
            z,

        "compute_rows":
            compute_rows,

        "status":
            "PASS",
    }




def runtime_history_json(items):
    result = []

    for item in items:
        if isinstance(item, dict):
            result.append(
                dict(item)
            )

        elif hasattr(
            item,
            "model_dump",
        ):
            result.append(
                item.model_dump(
                    exclude_none=True
                )
            )

        elif hasattr(
            item,
            "to_dict",
        ):
            result.append(
                item.to_dict()
            )

        else:
            result.append(
                {
                    "type":
                        type(item).__name__,
                    "repr":
                        repr(item),
                }
            )

    return result


def parse_bfcl_raw_function_call(text):
    import ast

    node = ast.parse(
        text,
        mode="eval",
    ).body

    if not isinstance(
        node,
        ast.Call,
    ):
        raise RuntimeError(
            "BFCL_ORACLE_CALL_NOT_AST_CALL="
            + text
        )

    if not isinstance(
        node.func,
        ast.Name,
    ):
        raise RuntimeError(
            "BFCL_ORACLE_CALL_NAME_INVALID="
            + text
        )

    if node.args:
        raise RuntimeError(
            "BFCL_ORACLE_POSITIONAL_ARGS_UNSUPPORTED="
            + text
        )

    arguments = {}

    for keyword in node.keywords:
        if keyword.arg is None:
            raise RuntimeError(
                "BFCL_ORACLE_KW_SPLAT_UNSUPPORTED="
                + text
            )

        arguments[
            keyword.arg
        ] = ast.literal_eval(
            keyword.value
        )

    return {
        "function_name":
            node.func.id,

        "arguments":
            arguments,
    }


def bfcl_apply_function_calls_v2(
    *,
    branch,
    state,
    trace_turn,
    step_index,
    function_calls,
    official_calls,
    source,
):
    worker = state[
        "worker"
    ]

    if (
        len(function_calls)
        != len(official_calls)
    ):
        raise RuntimeError(
            "BFCL_V2_CALL_COUNT_MISMATCH="
            + branch["execution_id"]
            + ":step="
            + str(step_index)
        )

    results = worker.execute(
        official_calls
    )

    if (
        len(results)
        != len(function_calls)
    ):
        raise RuntimeError(
            "BFCL_V2_EXECUTION_COUNT_MISMATCH="
            + branch["execution_id"]
            + ":step="
            + str(step_index)
        )

    outputs = []

    for call, result in zip(
        function_calls,
        results,
    ):
        out = {
            "type":
                "function_call_output",

            "call_id":
                call[
                    "call_id"
                ],

            "output":
                result,
        }

        state[
            "messages"
        ].append(
            out
        )

        outputs.append(
            out
        )

    trace_turn[
        "model_steps"
    ].append(
        {
            "step_index":
                step_index,

            "source":
                source,

            "function_calls":
                official_calls,

            "execution_results":
                results,

            "function_call_outputs":
                outputs,
        }
    )


def bfcl_archive_slot_maps(
    branch,
    state,
    descriptors,
):
    by_global = {}
    by_round_local = {}
    global_step = 0

    for round_index, turn in enumerate(
        state["archive"]["turns"]
    ):
        local_step_index = 0

        for model_step in turn[
            "model_steps"
        ]:
            calls = (
                model_step.get(
                    "function_calls",
                    [],
                )
                or []
            )

            terminal_text = (
                model_step.get(
                    "terminal_text"
                )
            )

            emitted_kinds = []

            if calls:
                emitted_kinds.append(
                    (
                        "joint_tool_call"
                        if len(calls) > 1
                        else "tool_call"
                    )
                )

            if (
                terminal_text is not None
                and terminal_text != ""
            ):
                emitted_kinds.append(
                    "assistant_text"
                )

            for expected_kind in emitted_kinds:
                global_step += 1
                local_step_index += 1

                key = (
                    "BFCL",
                    branch["instance_id"],
                    global_step,
                )

                if key not in descriptors:
                    raise RuntimeError(
                        "BFCL_ARCHIVED_SLOT_DESCRIPTOR_MISSING="
                        + repr(key)
                    )

                descriptor_kind = (
                    descriptors[key][
                        "candidate_kind"
                    ]
                )

                if descriptor_kind != expected_kind:
                    raise RuntimeError(
                        "BFCL_ARCHIVED_SLOT_KIND_MISMATCH="
                        + repr(key)
                        + ":archive="
                        + str(expected_kind)
                        + ":descriptor="
                        + str(descriptor_kind)
                    )

                slot = {
                    "global_step_index":
                        global_step,
                    "round_index":
                        round_index,
                    "local_step_index":
                        local_step_index,
                    "candidate_kind":
                        descriptor_kind,
                }

                by_global[
                    global_step
                ] = slot

                round_local_key = (
                    round_index,
                    local_step_index,
                )

                if round_local_key in by_round_local:
                    raise RuntimeError(
                        "BFCL_DUPLICATE_ROUND_LOCAL_SLOT="
                        + repr(round_local_key)
                    )

                by_round_local[
                    round_local_key
                ] = slot

    return (
        by_global,
        by_round_local,
    )

def bfcl_allowed_tool_names(tools):
    names = set()

    for tool in tools:
        name = None

        if isinstance(tool, dict):
            name = tool.get("name")

            if (
                name is None
                and isinstance(
                    tool.get("function"),
                    dict,
                )
            ):
                name = tool[
                    "function"
                ].get("name")

        else:
            name = getattr(
                tool,
                "name",
                None,
            )

            if name is None:
                function = getattr(
                    tool,
                    "function",
                    None,
                )

                name = getattr(
                    function,
                    "name",
                    None,
                )

        if isinstance(name, str) and name:
            names.add(name)

    return names


def parse_strict_textual_tool_call(
    *,
    text,
    allowed_tool_names,
):
    value = text.strip()

    if not value:
        return None

    parsed_json = None

    try:
        parsed_json = json.loads(value)
    except (
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):
        parsed_json = None

    if isinstance(parsed_json, dict):
        if set(parsed_json) == {
            "name",
            "arguments",
        }:
            name = parsed_json.get(
                "name"
            )

            arguments = parsed_json.get(
                "arguments"
            )

            if isinstance(
                arguments,
                str,
            ):
                try:
                    arguments = json.loads(
                        arguments
                    )
                except (
                    json.JSONDecodeError,
                    TypeError,
                    ValueError,
                ):
                    return None

            if (
                isinstance(name, str)
                and name
                in allowed_tool_names
                and isinstance(
                    arguments,
                    dict,
                )
            ):
                return {
                    "name":
                        name,
                    "arguments":
                        arguments,
                }

        return None

    try:
        node = ast.parse(
            value,
            mode="eval",
        ).body
    except (
        SyntaxError,
        ValueError,
    ):
        return None

    if not isinstance(
        node,
        ast.Call,
    ):
        return None

    if not isinstance(
        node.func,
        ast.Name,
    ):
        return None

    if node.args:
        return None

    name = node.func.id

    if name not in allowed_tool_names:
        return None

    arguments = {}

    for keyword in node.keywords:
        if keyword.arg is None:
            return None

        try:
            argument_value = (
                ast.literal_eval(
                    keyword.value
                )
            )
        except (
            ValueError,
            TypeError,
            SyntaxError,
            MemoryError,
            RecursionError,
        ):
            return None

        arguments[
            keyword.arg
        ] = argument_value

    return {
        "name":
            name,
        "arguments":
            arguments,
    }


def persist_selected_refiner_raw_response(
    *,
    branch,
    step_index,
    candidate_kind,
    response,
):
    journal = (
        STEP3
        / "04_OUTPUTS/"
          "STEP3E_EXACT_CHECKPOINT_REPLAY/"
          "STEP3E_SELECTED_REFINER_RAW_RESPONSE_JOURNAL.jsonl"
    )

    output_items = []

    for item in response.output:
        if hasattr(
            item,
            "model_dump",
        ):
            output_items.append(
                item.model_dump(
                    mode="json"
                )
            )
        else:
            output_items.append(
                {
                    "type":
                        getattr(
                            item,
                            "type",
                            None,
                        ),
                    "repr":
                        repr(item),
                }
            )

    row = {
        "execution_id":
            branch["execution_id"],
        "benchmark":
            branch["benchmark"],
        "instance_id":
            branch["instance_id"],
        "step_index":
            int(step_index),
        "candidate_kind":
            candidate_kind,
        "response_id":
            getattr(
                response,
                "id",
                None,
            ),
        "output_text":
            response.output_text
            or "",
        "output":
            output_items,
    }

    journal.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with journal.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            json.dumps(
                row,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n"
        )


def deterministic_normalized_call_id(
    execution_id,
    step_index,
    text,
):
    digest = hashlib.sha256(
        (
            execution_id
            + "|"
            + str(step_index)
            + "|"
            + text
        ).encode()
    ).hexdigest()[:24]

    return (
        "call_norm_"
        + digest
    )


def validate_selected_refiner_response_kind(
    *,
    benchmark,
    execution_id,
    step_index,
    candidate_kind,
    response,
    allowed_tool_names=None,
):
    calls = extract_function_calls(
        response
    )

    text = (
        response.output_text
        or ""
    ).strip()

    if candidate_kind == "tool_call":
        if calls and not text:
            return {
                "mode": "STRUCTURED_FUNCTION_CALL",
                "calls": calls,
                "textual_call": None,
            }

        if (
            not calls
            and text
            and allowed_tool_names is not None
        ):
            textual_call = (
                parse_strict_textual_tool_call(
                    text=text,
                    allowed_tool_names=set(
                        allowed_tool_names
                    ),
                )
            )

            if textual_call is not None:
                return {
                    "mode": "STRICT_TEXTUAL_TOOL_CALL",
                    "calls": [],
                    "textual_call": textual_call,
                }

        return {
            "mode":
                "INVALID_SELECTED_TOOL_SLOT_TERMINAL_FAILURE",
            "calls": [],
            "textual_call": None,
            "terminal_failure": True,
        }

    elif candidate_kind == "joint_tool_call":
        if (
            len(calls) >= 2
            and not text
        ):
            return {
                "mode": "STRUCTURED_FUNCTION_CALL",
                "calls": calls,
                "textual_call": None,
                "joint_tool_call": True,
            }

        return {
            "mode":
                "INVALID_SELECTED_TOOL_SLOT_TERMINAL_FAILURE",
            "calls": [],
            "textual_call": None,
            "terminal_failure": True,
            "joint_tool_call": True,
        }

    elif candidate_kind in {
        "assistant_text",
        "math_reasoning_step",
    }:
        if calls:
            return {
                "mode":
                    "INVALID_SELECTED_SLOT_INTERFACE_TERMINAL_FAILURE",
                "calls":
                    calls,
                "textual_call":
                    None,
                "terminal_failure":
                    True,
                "expected_interface":
                    "text",
                "observed_interface":
                    "function_call",
            }

        if not text:
            raise RuntimeError(
                benchmark
                + "_SELECTED_TEXT_SLOT_EMPTY="
                + execution_id
                + ":step="
                + str(step_index)
            )

    else:
        raise RuntimeError(
            benchmark
            + "_UNKNOWN_SELECTED_CANDIDATE_KIND="
            + str(candidate_kind)
        )

    return {
        "mode": "TEXT_SLOT",
        "calls": calls,
        "textual_call": None,
    }


def execute_bfcl_branch_v2(
    branch,
    branch_descriptors,
    bfcl_mod,
    descriptors,
    oracle_index,
    client,
):
    selected_steps = [
        int(x)
        for x in branch[
            "selected_steps_chronological"
        ]
    ]

    selected_set = set(
        selected_steps
    )

    desc_by_step = {
        int(desc["step_index"]):
            desc
        for desc in branch_descriptors
    }

    first_desc = desc_by_step[
        selected_steps[0]
    ]

    state = bfcl_grounded_prefix_restore(
        branch,
        first_desc,
        bfcl_mod,
        descriptors,
    )

    worker = state["worker"]
    compute_rows = []
    interventions = []

    try:
        contract = json.loads(
            REFINE_CONTRACT.read_text(
                encoding="utf-8"
            )
        )

        amendment = json.loads(
            REFINE_AMENDMENT.read_text(
                encoding="utf-8"
            )
        )

        critic_prompt = contract[
            "critic"
        ]["prompt"]

        refiner_prompt = amendment[
            "refiner"
        ]["prompt"]

        (
            slot_by_global,
            slot_by_round_local,
        ) = bfcl_archive_slot_maps(
            branch,
            state,
            descriptors,
        )

        for selected_step in selected_steps:
            if selected_step not in slot_by_global:
                raise RuntimeError(
                    "BFCL_SELECTED_SLOT_NOT_IN_ARCHIVE="
                    + branch["execution_id"]
                    + ":step="
                    + str(selected_step)
                )

        first_slot = slot_by_global[
            selected_steps[0]
        ]

        round_index = state[
            "current_round_index"
        ]

        if round_index != first_slot[
            "round_index"
        ]:
            raise RuntimeError(
                "BFCL_RESTORE_ROUND_SLOT_MISMATCH="
                + branch["execution_id"]
            )

        local_step_index = first_slot[
            "local_step_index"
        ]

        trace_turn = state[
            "trace_turns"
        ][-1]

        round_terminated = False

        unreachable_selected_steps = []

        def pending_selected_in_round(
            current_round,
            after_local_step,
        ):
            pending = []

            for selected_step in selected_steps:
                slot = slot_by_global[
                    selected_step
                ]

                if (
                    slot["round_index"]
                    == current_round
                    and slot["local_step_index"]
                    > after_local_step
                    and selected_step
                    not in {
                        int(x["step_index"])
                        for x in interventions
                    }
                ):
                    pending.append(
                        selected_step
                    )

            return pending

        while True:
            if round_terminated:
                pending = pending_selected_in_round(
                    round_index,
                    local_step_index - 1,
                )

                if pending:
                    for unreachable_step in pending:
                        unreachable_slot = slot_by_global[
                            unreachable_step
                        ]

                        noop_record = {
                            "step_index":
                                unreachable_step,
                            "round_index":
                                round_index,
                            "local_step_index":
                                unreachable_slot[
                                    "local_step_index"
                                ],
                            "operator":
                                branch[
                                    "intervention_operator"
                                ],
                            "intervention_applied":
                                False,
                            "consumed_as_noop":
                                True,
                            "noop_reason":
                                "CURRENT_MODIFIED_BRANCH_"
                                "ROUND_TERMINATED_BEFORE_"
                                "FROZEN_SELECTED_SLOT",
                        }

                        interventions.append(
                            noop_record
                        )

                        unreachable_selected_steps.append(
                            unreachable_step
                        )

                round_index += 1

                if round_index >= len(
                    worker.question
                ):
                    break

                user_turn = [
                    dict(x)
                    for x in worker.question[
                        round_index
                    ]
                ]

                for message in user_turn:
                    if message.get("role") == "system":
                        message["role"] = "developer"

                state["messages"].extend(
                    user_turn
                )

                trace_turn = {
                    "round_index":
                        round_index,
                    "user_messages":
                        user_turn,
                    "model_steps":
                        [],
                }

                state[
                    "trace_turns"
                ].append(
                    trace_turn
                )

                local_step_index = 1
                round_terminated = False

            slot = slot_by_round_local.get(
                (
                    round_index,
                    local_step_index,
                )
            )

            canonical_step = (
                slot[
                    "global_step_index"
                ]
                if slot is not None
                else None
            )

            is_selected = (
                canonical_step
                in selected_set
            )

            operator = branch[
                "intervention_operator"
            ]

            if is_selected:
                desc = desc_by_step[
                    canonical_step
                ]

                candidate_kind = desc[
                    "candidate_kind"
                ]

                if operator == "V_refine":
                    current_history = runtime_history_json(
                        state["messages"]
                    )

                    critic_input = make_component_input(
                        critic_prompt,
                        current_history=current_history,
                        archived_candidate_step=
                            desc[
                                "archived_candidate_step"
                            ],
                        tool_metadata=
                            worker.functions,
                    )

                    critic = call_responses(
                        client,
                        role="frozen_critic",
                        benchmark="BFCL",
                        instance_id=
                            branch["instance_id"],
                        step_index=
                            canonical_step,
                        input_items=
                            critic_input,
                        compute_rows=
                            compute_rows,
                    )

                    critique = (
                        critic.output_text
                        or ""
                    )

                    if not critique.strip():
                        raise RuntimeError(
                            "EMPTY_BFCL_V2_CRITIQUE"
                        )

                    refiner_input = make_component_input(
                        refiner_prompt,
                        current_history=current_history,
                        archived_candidate_step=
                            desc[
                                "archived_candidate_step"
                            ],
                        critique=critique,
                        tool_metadata=
                            worker.functions,
                    )

                    response = call_responses(
                        client,
                        role="frozen_refiner",
                        benchmark="BFCL",
                        instance_id=
                            branch["instance_id"],
                        step_index=
                            canonical_step,
                        input_items=
                            refiner_input,
                        compute_rows=
                            compute_rows,
                        tools=(
                            state["tools"]
                            if candidate_kind
                            == "tool_call"
                            else None
                        ),
                        requested_temperature=0.2,
                    )

                    persist_selected_refiner_raw_response(
                        branch=branch,
                        step_index=
                            canonical_step,
                        candidate_kind=
                            candidate_kind,
                        response=response,
                    )

                    allowed_tool_names = (
                        bfcl_allowed_tool_names(
                            state["tools"]
                        )
                    )

                    if (
                        candidate_kind
                        == "tool_call"
                        and not allowed_tool_names
                    ):
                        raise RuntimeError(
                            "BFCL_EXPOSED_TOOL_NAME_SET_EMPTY="
                            + branch[
                                "execution_id"
                            ]
                            + ":step="
                            + str(
                                canonical_step
                            )
                        )

                    validation = (
                        validate_selected_refiner_response_kind(
                            benchmark="BFCL",
                            execution_id=
                                branch[
                                    "execution_id"
                                ],
                            step_index=
                                canonical_step,
                            candidate_kind=
                                candidate_kind,
                            response=response,
                            allowed_tool_names=
                                allowed_tool_names,
                        )
                    )

                    normalization_mode = (
                        validation["mode"]
                    )

                    if validation.get(
                        "terminal_failure"
                    ) is True:
                        interventions.append(
                            {
                                "step_index":
                                    canonical_step,
                                "round_index":
                                    round_index,
                                "local_step_index":
                                    local_step_index,
                                "operator":
                                    "V_refine",
                                "critic_output":
                                    critique,
                                "response_normalization_mode":
                                    normalization_mode,
                                "terminal_failure":
                                    True,
                            }
                        )

                        return {
                            "execution_id":
                                branch["execution_id"],
                            "benchmark":
                                "BFCL",
                            "instance_id":
                                branch["instance_id"],
                            "intervention_operator":
                                branch[
                                    "intervention_operator"
                                ],
                            "selected_steps_chronological":
                                selected_steps,
                            "exact_restoration_certified":
                                True,
                            "approximate_restoration":
                                False,
                            "bfcl_slot_semantics":
                                "FROZEN_BASE_ROUND_LOCAL_DECISION_SLOT",
                            "intervention_records":
                                interventions,
                            "unreachable_selected_steps":
                                unreachable_selected_steps,
                            "unreachable_selected_slot_policy":
                                "ALLOCATED_BUT_UNREACHABLE_"
                                "SELECTED_SLOT_CONSUMED_AS_NOOP",
                            "terminal_outcome_Z":
                                0,
                            "terminal_outcome_source":
                                "STEP3E_INVALID_SELECTED_TOOL_SLOT_"
                                "TERMINAL_FAILURE_AMENDMENT",
                            "terminal_evaluator_result":
                                {
                                    "valid": False,
                                    "error_type":
                                        "intervention_interface_failure",
                                    "failed_step_index":
                                        canonical_step,
                                    "candidate_kind":
                                        candidate_kind,
                                },
                            "trace_turns":
                                state["trace_turns"],
                            "compute_rows":
                                compute_rows,
                            "status":
                                "PASS",
                        }

                    interventions.append(
                        {
                            "step_index":
                                canonical_step,
                            "round_index":
                                round_index,
                            "local_step_index":
                                local_step_index,
                            "operator":
                                "V_refine",
                            "critic_output":
                                critique,
                            "response_normalization_mode":
                                normalization_mode,
                        }
                    )

                    if (
                        normalization_mode
                        == "STRUCTURED_FUNCTION_CALL"
                    ):
                        calls = validation[
                            "calls"
                        ]

                        state[
                            "messages"
                        ].extend(
                            list(
                                response.output
                            )
                        )

                        model_responses = [
                            {
                                call.name:
                                    call.arguments
                            }
                            for call in calls
                        ]

                        official_calls = state[
                            "convert_to_function_call"
                        ](
                            model_responses
                        )

                        normalized_calls = [
                            {
                                "call_id":
                                    call.call_id,
                                "name":
                                    call.name,
                                "arguments":
                                    call.arguments,
                            }
                            for call in calls
                        ]

                        bfcl_apply_function_calls_v2(
                            branch=branch,
                            state=state,
                            trace_turn=
                                trace_turn,
                            step_index=
                                canonical_step,
                            function_calls=
                                normalized_calls,
                            official_calls=
                                official_calls,
                            source=
                                "refined_intervention",
                        )

                        round_terminated = False

                    elif (
                        normalization_mode
                        == "STRICT_TEXTUAL_TOOL_CALL"
                    ):
                        textual_call = (
                            validation[
                                "textual_call"
                            ]
                        )

                        argument_json = (
                            json.dumps(
                                textual_call[
                                    "arguments"
                                ],
                                separators=(
                                    ",",
                                    ":",
                                ),
                                ensure_ascii=False,
                            )
                        )

                        normalized_call_id = (
                            deterministic_normalized_call_id(
                                branch[
                                    "execution_id"
                                ],
                                canonical_step,
                                response.output_text
                                or "",
                            )
                        )

                        normalized_function_item = {
                            "type":
                                "function_call",
                            "call_id":
                                normalized_call_id,
                            "name":
                                textual_call[
                                    "name"
                                ],
                            "arguments":
                                argument_json,
                        }

                        state[
                            "messages"
                        ].append(
                            normalized_function_item
                        )

                        official_calls = state[
                            "convert_to_function_call"
                        ](
                            [
                                {
                                    textual_call[
                                        "name"
                                    ]:
                                        argument_json
                                }
                            ]
                        )

                        normalized_calls = [
                            {
                                "call_id":
                                    normalized_call_id,
                                "name":
                                    textual_call[
                                        "name"
                                    ],
                                "arguments":
                                    argument_json,
                            }
                        ]

                        bfcl_apply_function_calls_v2(
                            branch=branch,
                            state=state,
                            trace_turn=
                                trace_turn,
                            step_index=
                                canonical_step,
                            function_calls=
                                normalized_calls,
                            official_calls=
                                official_calls,
                            source=
                                "refined_intervention_"
                                "strict_textual_"
                                "tool_normalization",
                        )

                        round_terminated = False

                    elif (
                        normalization_mode
                        == "TEXT_SLOT"
                    ):
                        state[
                            "messages"
                        ].extend(
                            list(
                                response.output
                            )
                        )

                        text_output = (
                            response.output_text
                            or ""
                        )

                        trace_turn[
                            "model_steps"
                        ].append(
                            {
                                "step_index":
                                    canonical_step,
                                "round_index":
                                    round_index,
                                "local_step_index":
                                    local_step_index,
                                "source":
                                    "refined_intervention",
                                "terminal_text":
                                    text_output,
                                "function_calls":
                                    [],
                            }
                        )

                        round_terminated = True

                    else:
                        raise RuntimeError(
                            "BFCL_UNKNOWN_REFINER_"
                            "NORMALIZATION_MODE="
                            + str(
                                normalization_mode
                            )
                        )

                elif operator == "V_oracle":
                    if candidate_kind != "tool_call":
                        raise RuntimeError(
                            "BFCL_ORACLE_NON_TOOL_SLOT="
                            + branch["execution_id"]
                            + ":step="
                            + str(canonical_step)
                        )

                    key = (
                        "BFCL",
                        branch["instance_id"],
                        canonical_step,
                    )

                    if key not in oracle_index:
                        raise RuntimeError(
                            "BFCL_ORACLE_ROW_MISSING="
                            + repr(key)
                        )

                    oracle_row = oracle_index[
                        key
                    ]

                    payload = oracle_row[
                        "patch_operation"
                    ]["replacement_payload"]

                    if not isinstance(
                        payload,
                        list,
                    ):
                        raise RuntimeError(
                            "BFCL_ORACLE_PAYLOAD_NOT_LIST="
                            + repr(key)
                        )

                    normalized_calls = []

                    for ordinal, raw_call in enumerate(
                        payload
                    ):
                        parsed = parse_bfcl_raw_function_call(
                            raw_call
                        )

                        call_id = (
                            "oracle_"
                            + hashlib.sha256(
                                (
                                    branch[
                                        "execution_id"
                                    ]
                                    + "|"
                                    + str(
                                        canonical_step
                                    )
                                    + "|"
                                    + str(ordinal)
                                ).encode()
                            ).hexdigest()[:24]
                        )

                        state["messages"].append(
                            {
                                "type":
                                    "function_call",
                                "call_id":
                                    call_id,
                                "name":
                                    parsed[
                                        "function_name"
                                    ],
                                "arguments":
                                    json.dumps(
                                        parsed[
                                            "arguments"
                                        ],
                                        separators=(
                                            ",",
                                            ":",
                                        ),
                                        ensure_ascii=False,
                                    ),
                            }
                        )

                        normalized_calls.append(
                            {
                                "call_id":
                                    call_id,
                                "name":
                                    parsed[
                                        "function_name"
                                    ],
                                "arguments":
                                    json.dumps(
                                        parsed[
                                            "arguments"
                                        ],
                                        separators=(
                                            ",",
                                            ":",
                                        ),
                                        ensure_ascii=False,
                                    ),
                            }
                        )

                    bfcl_apply_function_calls_v2(
                        branch=branch,
                        state=state,
                        trace_turn=trace_turn,
                        step_index=canonical_step,
                        function_calls=
                            normalized_calls,
                        official_calls=payload,
                        source=
                            "oracle_intervention",
                    )

                    interventions.append(
                        {
                            "step_index":
                                canonical_step,
                            "round_index":
                                round_index,
                            "local_step_index":
                                local_step_index,
                            "operator":
                                "V_oracle",
                            "oracle_target":
                                oracle_row[
                                    "oracle_target"
                                ],
                        }
                    )

                    round_terminated = False

                else:
                    raise RuntimeError(
                        "BFCL_V2_UNKNOWN_OPERATOR="
                        + operator
                    )

            else:
                started = time.perf_counter()

                response = client.responses.create(
                    model=MODEL,
                    input=state["messages"],
                    tools=state["tools"],
                    reasoning={
                        "effort":
                            REASONING_EFFORT,
                    },
                    max_output_tokens=
                        MAX_OUTPUT_TOKENS,
                    store=False,
                )

                record_response_call(
                    compute_rows,
                    "branch_continuation_generator",
                    "BFCL",
                    branch["instance_id"],
                    canonical_step,
                    response,
                    started,
                    None,
                    "PROVIDER_DEFAULT",
                    0,
                )

                state["messages"].extend(
                    list(response.output)
                )

                calls = extract_function_calls(
                    response
                )

                if calls:
                    model_responses = [
                        {
                            call.name:
                                call.arguments
                        }
                        for call in calls
                    ]

                    official_calls = state[
                        "convert_to_function_call"
                    ](
                        model_responses
                    )

                    normalized_calls = [
                        {
                            "call_id":
                                call.call_id,
                            "name":
                                call.name,
                            "arguments":
                                call.arguments,
                        }
                        for call in calls
                    ]

                    bfcl_apply_function_calls_v2(
                        branch=branch,
                        state=state,
                        trace_turn=trace_turn,
                        step_index=canonical_step,
                        function_calls=
                            normalized_calls,
                        official_calls=
                            official_calls,
                        source=
                            "branch_continuation",
                    )

                    round_terminated = False

                else:
                    text = (
                        response.output_text
                        or ""
                    )

                    trace_turn[
                        "model_steps"
                    ].append(
                        {
                            "step_index":
                                canonical_step,
                            "round_index":
                                round_index,
                            "local_step_index":
                                local_step_index,
                            "source":
                                "branch_continuation",
                            "terminal_text":
                                text,
                            "function_calls":
                                [],
                        }
                    )

                    round_terminated = True

            local_step_index += 1

        applied = [
            int(x["step_index"])
            for x in interventions
        ]

        if applied != selected_steps:
            raise RuntimeError(
                "BFCL_SELECTED_STEPS_NOT_ALL_APPLIED="
                + branch["execution_id"]
                + ":applied="
                + repr(applied)
                + ":expected="
                + repr(selected_steps)
            )

        state["bfcl_mod"] = bfcl_mod

        z, evaluator_result = bfcl_terminal_utility(
            branch,
            state,
        )

        return {
            "execution_id":
                branch["execution_id"],
            "benchmark":
                "BFCL",
            "instance_id":
                branch["instance_id"],
            "intervention_operator":
                branch[
                    "intervention_operator"
                ],
            "selected_steps_chronological":
                selected_steps,
            "exact_restoration_certified":
                True,
            "approximate_restoration":
                False,
            "bfcl_slot_semantics":
                "FROZEN_BASE_ROUND_LOCAL_DECISION_SLOT",
            "intervention_records":
                interventions,
            "unreachable_selected_steps":
                unreachable_selected_steps,
            "unreachable_selected_slot_policy":
                "ALLOCATED_BUT_UNREACHABLE_"
                "SELECTED_SLOT_CONSUMED_AS_NOOP",
            "terminal_outcome_Z":
                z,
            "terminal_evaluator_result":
                evaluator_result,
            "trace_turns":
                state["trace_turns"],
            "compute_rows":
                compute_rows,
            "status":
                "PASS",
        }

    finally:
        worker.close()


def execute_tool_branch_v2(
    branch,
    branch_descriptors,
    oracle_index,
    tool_mod,
    client,
):
    selected_steps = [
        int(x)
        for x in branch[
            "selected_steps_chronological"
        ]
    ]

    selected_set = set(
        selected_steps
    )

    desc_by_step = {
        int(desc["step_index"]):
            desc
        for desc in branch_descriptors
    }

    if not hasattr(
        tool_mod,
        "MAX_AGENT_TURNS",
    ):
        raise RuntimeError(
            "TOOLALPACA_FROZEN_MAX_AGENT_TURNS_MISSING"
        )

    max_agent_turns = int(
        tool_mod.MAX_AGENT_TURNS
    )

    if max_agent_turns <= 0:
        raise RuntimeError(
            "TOOLALPACA_FROZEN_MAX_AGENT_TURNS_INVALID="
            + str(max_agent_turns)
        )

    first_desc = desc_by_step[
        selected_steps[0]
    ]

    binding = (
        toolalpaca_authority_binding(
            first_desc
        )
    )

    pre_rows = load_jsonl(
        tool_mod.PRE_PATH
    )

    row = find_row(
        pre_rows,
        branch[
            "instance_id"
        ],
    )

    tools, op_lookup = (
        tool_mod.build_tools(
            row[
                "documentation"
            ]
        )
    )

    history = [
        {
            "role":
                "user",

            "content":
                row[
                    "instruction"
                ],
        }
    ]

    actions = []
    interventions = []
    compute_rows = []
    final_answer = ""

    contract = json.loads(
        REFINE_CONTRACT.read_text(
            encoding="utf-8"
        )
    )

    amendment = json.loads(
        REFINE_AMENDMENT.read_text(
            encoding="utf-8"
        )
    )

    critic_prompt = (
        contract[
            "critic"
        ][
            "prompt"
        ]
    )

    refiner_prompt = (
        amendment[
            "refiner"
        ][
            "prompt"
        ]
    )

    simulator_freeze = json.loads(
        tool_mod.FREEZE_PATH.read_text(
            encoding="utf-8"
        )
    )

    simulator_template = Template(
        tool_mod.SIMULATOR_PROMPT_PATH.read_text(
            encoding="utf-8"
        )
    )

    def apply_tool_calls(
        call_rows,
        step_index,
    ):
        for call_row in call_rows:
            name = call_row[
                "name"
            ]

            arguments = call_row[
                "arguments"
            ]

            call_id = call_row[
                "call_id"
            ]

            if name not in op_lookup:
                observation = (
                    "Status Code: 404. "
                    "Response: "
                    '{"message":"Function not found."}'
                )

                status_code = 404

                simulator_record = {
                    "simulator_called":
                        False,

                    "reason":
                        "unknown_function",
                }

            else:
                request_text = (
                    tool_mod.build_request(
                        row[
                            "api_name"
                        ],

                        op_lookup[
                            name
                        ],

                        arguments,
                    )
                )

                simulator_prompt = (
                    simulator_template
                    .safe_substitute(
                        Name=
                            row[
                                "api_name"
                            ],

                        Documentation=
                            row[
                                "documentation"
                            ],

                        Request=
                            request_text,
                    )
                )

                started = (
                    time.perf_counter()
                )

                sim_response = (
                    client.chat.completions.create(
                        model=
                            simulator_freeze[
                                "model"
                            ],

                        messages=[
                            {
                                "role":
                                    "user",

                                "content":
                                    simulator_prompt,
                            }
                        ],

                        temperature=float(
                            simulator_freeze[
                                "temperature"
                            ]
                        ),

                        top_p=float(
                            simulator_freeze[
                                "top_p"
                            ]
                        ),

                        n=int(
                            simulator_freeze[
                                "n"
                            ]
                        ),

                        reasoning_effort=
                            simulator_freeze[
                                "reasoning_effort"
                            ],
                    )
                )

                sim_usage = (
                    tool_mod.chat_usage(
                        sim_response
                    )
                )

                raw = (
                    sim_response
                    .choices[0]
                    .message
                    .content
                    or ""
                )

                (
                    status_code,
                    response_body,
                ) = (
                    tool_mod
                    .parse_simulator_output(
                        raw
                    )
                )

                observation = (
                    "Status Code: "
                    + str(
                        status_code
                    )
                    + ". Response: "
                    + json.dumps(
                        response_body,
                        ensure_ascii=False,
                    )
                )

                record_compute_row(
                    compute_rows,
                    {
                        "call_id":
                            hashlib.sha256(
                                (
                                    "tool_simulator|"
                                    + branch[
                                        "execution_id"
                                    ]
                                    + "|"
                                    + str(
                                        step_index
                                    )
                                    + "|"
                                    + str(
                                        len(
                                            actions
                                        )
                                    )
                                ).encode()
                            ).hexdigest(),

                        "call_role":
                            "environment_simulator",

                        "benchmark":
                            "ToolAlpaca",

                        "instance_id":
                            branch[
                                "instance_id"
                            ],

                        "step_index":
                            step_index,

                        "model_id":
                            simulator_freeze[
                                "model"
                            ],

                        "reasoning_effort":
                            simulator_freeze[
                                "reasoning_effort"
                            ],

                        "requested_temperature":
                            simulator_freeze[
                                "temperature"
                            ],

                        "effective_temperature_status":
                            "FROZEN_SIMULATOR_PARAMETER",

                        "input_tokens":
                            sim_usage[
                                "input_tokens"
                            ],

                        "output_tokens":
                            sim_usage[
                                "output_tokens"
                            ],

                        "total_tokens":
                            sim_usage[
                                "total_tokens"
                            ],

                        "latency":
                            time.perf_counter()
                            - started,

                        "retry_count":
                            0,

                        "response_id":
                            None,

                        "wall_clock_seconds":
                            time.time(),
                    }
                )

                simulator_record = {
                    "simulator_called":
                        True,

                    "model":
                        simulator_freeze[
                            "model"
                        ],

                    "temperature":
                        simulator_freeze[
                            "temperature"
                        ],

                    "top_p":
                        simulator_freeze[
                            "top_p"
                        ],

                    "request":
                        request_text,

                    "raw_output":
                        raw,
                }

            history.append(
                {
                    "type":
                        "function_call_output",

                    "call_id":
                        call_id,

                    "output":
                        observation,
                }
            )

            actions.append(
                {
                    "action_index":
                        len(actions)
                        + 1,

                    "turn_index":
                        step_index,

                    "function_name":
                        name,

                    "arguments":
                        arguments,

                    "call_id":
                        call_id,

                    "status_code":
                        status_code,

                    "observation":
                        observation,

                    "simulator":
                        simulator_record,
                }
            )

    step_index = 1

    while step_index <= max_agent_turns:
        is_selected = (
            step_index
            in selected_set
        )

        operator = branch[
            "intervention_operator"
        ]

        if is_selected:
            if operator == "V_refine":
                desc = desc_by_step[
                    step_index
                ]

                current_history = (
                    runtime_history_json(
                        history
                    )
                )

                critic_input = (
                    make_component_input(
                        critic_prompt,

                        current_history=
                            current_history,

                        archived_candidate_step=
                            desc[
                                "archived_candidate_step"
                            ],

                        tool_metadata=
                            row[
                                "documentation"
                            ],
                    )
                )

                critic = call_responses(
                    client,

                    role=
                        "frozen_critic",

                    benchmark=
                        "ToolAlpaca",

                    instance_id=
                        branch[
                            "instance_id"
                        ],

                    step_index=
                        step_index,

                    input_items=
                        critic_input,

                    compute_rows=
                        compute_rows,
                )

                critique = (
                    critic.output_text
                    or ""
                )

                if not critique.strip():
                    raise RuntimeError(
                        "EMPTY_TOOLALPACA_V2_CRITIQUE"
                    )

                refiner_input = (
                    make_component_input(
                        refiner_prompt,

                        current_history=
                            current_history,

                        archived_candidate_step=
                            desc[
                                "archived_candidate_step"
                            ],

                        critique=
                            critique,

                        tool_metadata=
                            row[
                                "documentation"
                            ],
                    )
                )

                response = call_responses(
                    client,

                    role=
                        "frozen_refiner",

                    benchmark=
                        "ToolAlpaca",

                    instance_id=
                        branch[
                            "instance_id"
                        ],

                    step_index=
                        step_index,

                    input_items=
                        refiner_input,

                    compute_rows=
                        compute_rows,

                    tools=
                        tools,

                    requested_temperature=
                        0.2,
                )

                history.extend(
                    list(
                        response.output
                    )
                )

                interventions.append(
                    {
                        "step_index":
                            step_index,

                        "operator":
                            "V_refine",

                        "critic_output":
                            critique,
                    }
                )

                validation = validate_selected_refiner_response_kind(
                    benchmark="ToolAlpaca",
                    execution_id=
                        branch["execution_id"],
                    step_index=
                        step_index,
                    candidate_kind=
                        desc["candidate_kind"],
                    response=
                        response,
                )

                validation_mode = (
                    validation[
                        "mode"
                    ]
                )

                calls = (
                    validation[
                        "calls"
                    ]
                )

                if validation_mode in {
                    "INVALID_SELECTED_TOOL_SLOT_TERMINAL_FAILURE",
                    "INVALID_SELECTED_SLOT_INTERFACE_TERMINAL_FAILURE",
                }:
                    if validation.get(
                        "terminal_failure"
                    ) is not True:
                        raise RuntimeError(
                            "TOOLALPACA_INVALID_SELECTED_TOOL_SLOT_"
                            "WITHOUT_TERMINAL_FAILURE_FLAG="
                            + branch["execution_id"]
                            + ":step="
                            + str(step_index)
                        )

                    if not interventions:
                        raise RuntimeError(
                            "TOOLALPACA_TERMINAL_FAILURE_"
                            "INTERVENTION_RECORD_MISSING="
                            + branch["execution_id"]
                        )

                    current_intervention = (
                        interventions[-1]
                    )

                    if (
                        int(
                            current_intervention[
                                "step_index"
                            ]
                        )
                        != int(step_index)
                    ):
                        raise RuntimeError(
                            "TOOLALPACA_TERMINAL_FAILURE_"
                            "INTERVENTION_STEP_MISMATCH="
                            + branch["execution_id"]
                        )

                    current_intervention[
                        "response_normalization_mode"
                    ] = validation_mode

                    current_intervention[
                        "terminal_failure"
                    ] = True

                    unreachable_selected_steps = [
                        int(selected_step)
                        for selected_step
                        in selected_steps
                        if int(selected_step)
                        > int(step_index)
                    ]

                    for unreachable_step in (
                        unreachable_selected_steps
                    ):
                        interventions.append(
                            {
                                "step_index":
                                    unreachable_step,

                                "operator":
                                    branch[
                                        "intervention_operator"
                                    ],

                                "consumed_as_noop":
                                    True,

                                "noop_reason":
                                    "CURRENT_MODIFIED_BRANCH_"
                                    "TERMINATED_BEFORE_"
                                    "FROZEN_SELECTED_SLOT",
                            }
                        )

                    return {
                        "execution_id":
                            branch[
                                "execution_id"
                            ],

                        "benchmark":
                            "ToolAlpaca",

                        "instance_id":
                            branch[
                                "instance_id"
                            ],

                        "intervention_operator":
                            branch[
                                "intervention_operator"
                            ],

                        "selected_steps_chronological":
                            selected_steps,

                        "exact_restoration_certified":
                            True,

                        "approximate_restoration":
                            False,

                        "toolalpaca_max_agent_turns_source":
                            "FROZEN_STEP1_RUNTIME",

                        "toolalpaca_max_agent_turns":
                            max_agent_turns,

                        "intervention_records":
                            interventions,

                        "unreachable_selected_steps":
                            unreachable_selected_steps,

                        "unreachable_selected_slot_policy":
                            "ALLOCATED_BUT_UNREACHABLE_"
                            "SELECTED_SLOT_CONSUMED_AS_NOOP",

                        "terminal_outcome_Z":
                            0,

                        "terminal_outcome_source":
                            "STEP3E_INVALID_SELECTED_TOOL_SLOT_"
                            "TERMINAL_FAILURE_AMENDMENT",

                        "terminal_evaluator_result":
                            {
                                "valid":
                                    False,

                                "error_type":
                                    "intervention_interface_failure",

                                "failed_step_index":
                                    step_index,

                                "candidate_kind":
                                    desc[
                                        "candidate_kind"
                                    ],
                            },

                        "actions":
                            actions,

                        "compute_rows":
                            compute_rows,

                        "status":
                            "PASS",
                    }

                if validation_mode == "TEXT_SLOT":
                    final_answer = (
                        response.output_text
                        or ""
                    )
                    break

                if validation_mode != "STRUCTURED_FUNCTION_CALL":
                    raise RuntimeError(
                        "TOOLALPACA_UNSUPPORTED_VALIDATED_RESPONSE_MODE="
                        + str(
                            validation_mode
                        )
                    )

                if not calls:
                    raise RuntimeError(
                        "TOOLALPACA_STRUCTURED_FUNCTION_CALL_WITHOUT_CALLS"
                    )

                call_rows = []

                for call in calls:
                    try:
                        arguments = json.loads(
                            call.arguments
                        )

                    except Exception:
                        arguments = {}

                    call_rows.append(
                        {
                            "name":
                                call.name,

                            "arguments":
                                arguments,

                            "call_id":
                                call.call_id,
                        }
                    )

                apply_tool_calls(
                    call_rows,
                    step_index,
                )

            elif operator == "V_oracle":
                key = (
                    "ToolAlpaca",
                    branch[
                        "instance_id"
                    ],
                    step_index,
                )

                if key not in oracle_index:
                    raise RuntimeError(
                        "TOOLALPACA_ORACLE_ROW_MISSING="
                        + repr(key)
                    )

                oracle_row = (
                    oracle_index[
                        key
                    ]
                )

                payload = (
                    oracle_row[
                        "patch_operation"
                    ][
                        "replacement_payload"
                    ]
                )

                name = payload[
                    "function_name"
                ]

                arguments_raw = payload[
                    "arguments"
                ]

                if isinstance(
                    arguments_raw,
                    str,
                ):
                    arguments = json.loads(
                        arguments_raw
                    )

                else:
                    arguments = dict(
                        arguments_raw
                    )

                call_id = (
                    "oracle_"
                    + hashlib.sha256(
                        (
                            branch[
                                "execution_id"
                            ]
                            + "|"
                            + str(
                                step_index
                            )
                        ).encode()
                    ).hexdigest()[:24]
                )

                history.append(
                    {
                        "type":
                            "function_call",

                        "call_id":
                            call_id,

                        "name":
                            name,

                        "arguments":
                            json.dumps(
                                arguments,
                                separators=(
                                    ",",
                                    ":",
                                ),
                                ensure_ascii=False,
                            ),
                    }
                )

                apply_tool_calls(
                    [
                        {
                            "name":
                                name,

                            "arguments":
                                arguments,

                            "call_id":
                                call_id,
                        }
                    ],
                    step_index,
                )

                interventions.append(
                    {
                        "step_index":
                            step_index,

                        "operator":
                            "V_oracle",

                        "oracle_target":
                            oracle_row[
                                "oracle_target"
                            ],
                    }
                )

            else:
                raise RuntimeError(
                    "TOOLALPACA_V2_UNKNOWN_OPERATOR="
                    + operator
                )

        else:
            response = call_responses(
                client,

                role=
                    "branch_continuation_generator",

                benchmark=
                    "ToolAlpaca",

                instance_id=
                    branch[
                        "instance_id"
                    ],

                step_index=
                    step_index,

                input_items=
                    history,

                compute_rows=
                    compute_rows,

                tools=
                    tools,
            )

            history.extend(
                list(
                    response.output
                )
            )

            calls = (
                extract_function_calls(
                    response
                )
            )

            if not calls:
                final_answer = (
                    response.output_text
                    or ""
                )

                break

            call_rows = []

            for call in calls:
                try:
                    arguments = json.loads(
                        call.arguments
                    )

                except Exception:
                    arguments = {}

                call_rows.append(
                    {
                        "name":
                            call.name,

                        "arguments":
                            arguments,

                        "call_id":
                            call.call_id,
                    }
                )

            apply_tool_calls(
                call_rows,
                step_index,
            )

        step_index += 1

    if not final_answer:
        if step_index > max_agent_turns:
            raise RuntimeError(
                "TOOLALPACA_V2_EXCEEDED_FROZEN_MAX_AGENT_TURNS="
                + str(max_agent_turns)
            )

    normal_termination_unreachable_selected_steps = []

    if final_answer:
        applied_before_unreachable_accounting = {
            int(x["step_index"])
            for x in interventions
        }

        normal_termination_unreachable_selected_steps = [
            int(selected_step)
            for selected_step in selected_steps
            if (
                int(selected_step) > int(step_index)
                and int(selected_step)
                not in applied_before_unreachable_accounting
            )
        ]

        for unreachable_step in (
            normal_termination_unreachable_selected_steps
        ):
            interventions.append(
                {
                    "step_index":
                        unreachable_step,

                    "operator":
                        branch[
                            "intervention_operator"
                        ],

                    "consumed_as_noop":
                        True,

                    "noop_reason":
                        "CURRENT_MODIFIED_BRANCH_"
                        "TERMINATED_BEFORE_"
                        "FROZEN_SELECTED_SLOT",
                }
            )

    applied = [
        int(x["step_index"])
        for x in interventions
    ]

    if applied != selected_steps:
        raise RuntimeError(
            "TOOLALPACA_SELECTED_STEPS_NOT_ALL_APPLIED="
            + branch[
                "execution_id"
            ]
            + ":applied="
            + repr(applied)
            + ":expected="
            + repr(
                selected_steps
            )
        )

    standard_answer = ""

    for i, ans in enumerate(
        binding[
            "golden_answers"
        ]
    ):
        standard_answer += (
            f"{i + 1}. Function: "
            f"{ans['Action']}\n"
            "Parameters: "
            f"{ans['Action_Input']}\n"
        )

    solution = ""

    for i, action in enumerate(
        actions
    ):
        solution += (
            f"{i + 1}. Function: "
            f"{action['function_name']}\n"
            "Parameters: "
            + json.dumps(
                action[
                    "arguments"
                ],
                ensure_ascii=False,
            )
            + "\n"
            "Retruns: "
            + action[
                "observation"
            ]
            + "\n"
        )

    solution += (
        f"{len(actions) + 1}. "
        "Final Response: "
        + final_answer
    )

    terminal_contract = json.loads(
        TERMINAL_CONTRACT.read_text(
            encoding="utf-8"
        )
    )

    eval_prompt_path = Path(
        terminal_contract[
            "toolalpaca"
        ][
            "evaluation_prompt_path"
        ]
    )

    if (
        sha256_file(
            eval_prompt_path
        )
        != terminal_contract[
            "toolalpaca"
        ][
            "evaluation_prompt_sha256"
        ]
    ):
        raise RuntimeError(
            "TOOLALPACA_EVALUATION_PROMPT_HASH_MISMATCH"
        )

    eval_template = Template(
        eval_prompt_path.read_text(
            encoding="utf-8"
        )
    )

    judge_prompt = (
        eval_template.substitute(
            documentation=
                binding[
                    "api_info"
                ][
                    "NLDocumentation"
                ],

            instruction=
                binding[
                    "instruction"
                ],

            standard=
                standard_answer,

            solution=
                solution,
        )
    )

    judge = call_responses(
        client,

        role=
            "terminal_utility_evaluator",

        benchmark=
            "ToolAlpaca",

        instance_id=
            branch[
                "instance_id"
            ],

        step_index=None,

        input_items=[
            {
                "role":
                    "user",

                "content":
                    judge_prompt,
            }
        ],

        compute_rows=
            compute_rows,
    )

    judge_text = (
        judge.output_text
        or ""
    )

    results_text = (
        judge_text.split(
            "## Results",
            1,
        )[-1]
    )

    process_match = re.search(
        r"Process Correctness: (\w+)",
        results_text,
    )

    final_match = re.search(
        r"Final Response Correctness: (\w+)",
        results_text,
    )

    process_word = (
        process_match.group(1)
        if process_match
        else ""
    )

    final_word = (
        final_match.group(1)
        if final_match
        else ""
    )

    z = (
        1
        if (
            process_word == "Yes"
            and final_word == "Yes"
        )
        else 0
    )

    return {
        "execution_id":
            branch[
                "execution_id"
            ],

        "benchmark":
            "ToolAlpaca",

        "instance_id":
            branch[
                "instance_id"
            ],

        "intervention_operator":
            branch[
                "intervention_operator"
            ],

        "selected_steps_chronological":
            selected_steps,

        "exact_restoration_certified":
            True,

        "approximate_restoration":
            False,

        "toolalpaca_max_agent_turns_source":
            "FROZEN_STEP1_RUNTIME",

        "toolalpaca_max_agent_turns":
            max_agent_turns,

        "intervention_records":
            interventions,

        "unreachable_selected_steps":
            normal_termination_unreachable_selected_steps,

        "unreachable_selected_slot_policy":
            (
                "ALLOCATED_BUT_UNREACHABLE_"
                "SELECTED_SLOT_CONSUMED_AS_NOOP"
                if normal_termination_unreachable_selected_steps
                else None
            ),

        "actions":
            actions,

        "final_answer":
            final_answer,

        "terminal_judge_output":
            judge_text,

        "process_correctness":
            process_word,

        "final_response_correctness":
            final_word,

        "terminal_outcome_Z":
            z,

        "compute_rows":
            compute_rows,

        "status":
            "PASS",
    }

def get_branch_descriptors(
    branch,
    descriptors,
):
    rows = []

    for step in branch[
        "selected_steps_chronological"
    ]:
        key = (
            branch["benchmark"],
            branch["instance_id"],
            int(step),
        )

        if key not in descriptors:
            raise RuntimeError(
                "BRANCH_DESCRIPTOR_MISSING="
                + repr(key)
            )

        rows.append(
            descriptors[key]
        )

    return rows


def load_oracle_patch_index():
    path = (
        ROOT
        / "10_PILOT/STEP3/04_OUTPUTS/"
          "STEP3C_DIAGNOSTIC_ORACLE_PATCH/"
          "oracle_patch_plan.jsonl"
    )

    rows = load_jsonl(path)
    index = {}

    for row in rows:
        key = (
            row["benchmark"],
            row["instance_id"],
            int(row["step_index"]),
        )

        if key in index:
            raise RuntimeError(
                "DUPLICATE_ORACLE_PATCH="
                + repr(key)
            )

        index[key] = row

    return index


def bfcl_validate_selected_slot_bindings_no_api(
    branch,
    descriptors,
):
    steps = [
        int(x)
        for x in branch[
            "selected_steps_chronological"
        ]
    ]

    rows = []

    for step in steps:
        key = (
            "BFCL",
            branch["instance_id"],
            step,
        )

        if key not in descriptors:
            raise RuntimeError(
                "BFCL_SELECTED_DESCRIPTOR_MISSING="
                + repr(key)
            )

        rows.append(
            descriptors[key]
        )

    archive_paths = {
        row["source_archive_path"]
        for row in rows
    }

    archive_hashes = {
        row["source_archive_sha256"]
        for row in rows
    }

    if len(archive_paths) != 1:
        raise RuntimeError(
            "BFCL_SELECTED_ARCHIVE_PATH_MISMATCH="
            + branch["execution_id"]
        )

    if len(archive_hashes) != 1:
        raise RuntimeError(
            "BFCL_SELECTED_ARCHIVE_HASH_MISMATCH="
            + branch["execution_id"]
        )

    archive = ROOT / next(
        iter(archive_paths)
    )

    expected_hash = next(
        iter(archive_hashes)
    )

    if sha256_file(archive) != expected_hash:
        raise RuntimeError(
            "BFCL_SELECTED_ARCHIVE_CONTENT_HASH_MISMATCH="
            + branch["execution_id"]
        )

    obj = json.loads(
        archive.read_text(
            encoding="utf-8"
        )
    )

    global_step = 0
    slot_map = {}

    for round_index, turn in enumerate(
        obj["turns"]
    ):
        for local_step_index, _ in enumerate(
            turn["model_steps"],
            start=1,
        ):
            global_step += 1
            slot_map[global_step] = {
                "round_index":
                    round_index,
                "local_step_index":
                    local_step_index,
            }

    bindings = []

    for step, row in zip(
        steps,
        rows,
    ):
        if step not in slot_map:
            raise RuntimeError(
                "BFCL_SELECTED_SLOT_NOT_IN_ARCHIVE="
                + branch["execution_id"]
                + ":step="
                + str(step)
            )

        bindings.append(
            {
                "step_index":
                    step,
                "round_index":
                    slot_map[step][
                        "round_index"
                    ],
                "local_step_index":
                    slot_map[step][
                        "local_step_index"
                    ],
                "candidate_kind":
                    row["candidate_kind"],
            }
        )

    return bindings


def full_dry_run_branch(
    branch,
    descriptors,
    oracle_index,
):
    benchmark = branch[
        "benchmark"
    ]

    operator = branch[
        "intervention_operator"
    ]

    steps = [
        int(x)
        for x in branch[
            "selected_steps_chronological"
        ]
    ]

    if benchmark not in {
        "BFCL",
        "Math-Shepherd",
        "ToolAlpaca",
    }:
        raise RuntimeError(
            "FULL_DRY_RUN_UNSUPPORTED_BENCHMARK="
            + benchmark
        )

    if not steps:
        raise RuntimeError(
            "EMPTY_SELECTED_STEPS="
            + branch["execution_id"]
        )

    if steps != sorted(steps):
        raise RuntimeError(
            "SELECTED_STEPS_NOT_CHRONOLOGICAL="
            + branch["execution_id"]
        )

    if len(steps) != len(set(steps)):
        raise RuntimeError(
            "DUPLICATE_SELECTED_STEPS="
            + branch["execution_id"]
        )

    if int(
        branch["first_modified_step"]
    ) != steps[0]:
        raise RuntimeError(
            "FIRST_MODIFIED_STEP_MISMATCH="
            + branch["execution_id"]
        )

    checks = []
    bfcl_slot_bindings = None

    if benchmark == "BFCL":
        bfcl_slot_bindings = (
            bfcl_validate_selected_slot_bindings_no_api(
                branch,
                descriptors,
            )
        )

    if operator == "V_refine":
        rows = get_branch_descriptors(
            branch,
            descriptors,
        )

        for step, row in zip(
            steps,
            rows,
        ):
            if (
                row.get(
                    "runtime_history_source"
                )
                !=
                "STEP3E_EXACT_CURRENT_PRE_STEP_BRANCH_STATE"
            ):
                raise RuntimeError(
                    "RUNTIME_HISTORY_SOURCE_MISMATCH="
                    + branch["execution_id"]
                    + ":"
                    + str(step)
                )

            if (
                row.get(
                    "archived_history_may_replace_runtime_branch_history"
                )
                is not False
            ):
                raise RuntimeError(
                    "ARCHIVED_HISTORY_REPLACEMENT_FORBIDDEN="
                    + branch["execution_id"]
                    + ":"
                    + str(step)
                )

            checks.append(
                {
                    "step_index": step,
                    "binding": "V_refine_descriptor",
                    "candidate_kind": row.get(
                        "candidate_kind"
                    ),
                    "prefix_hash": row.get(
                        "prefix_hash"
                    ),
                }
            )

    elif operator == "V_oracle":
        if benchmark == "Math-Shepherd":
            raise RuntimeError(
                "MATH_ORACLE_FORBIDDEN="
                + branch["execution_id"]
            )

        for step in steps:
            key = (
                benchmark,
                branch["instance_id"],
                step,
            )

            if key not in oracle_index:
                raise RuntimeError(
                    "ORACLE_PATCH_MISSING="
                    + repr(key)
                )

            row = oracle_index[key]

            if row.get(
                "patch_defined"
            ) is not True:
                raise RuntimeError(
                    "ORACLE_PATCH_NOT_DEFINED="
                    + repr(key)
                )

            if row.get(
                "diagnostic_only"
            ) is not True:
                raise RuntimeError(
                    "ORACLE_NOT_DIAGNOSTIC_ONLY="
                    + repr(key)
                )

            checks.append(
                {
                    "step_index": step,
                    "binding": "V_oracle_patch",
                    "prefix_hash": row.get(
                        "prefix_hash"
                    ),
                }
            )

    else:
        raise RuntimeError(
            "UNKNOWN_OPERATOR="
            + operator
        )

    return {
        "execution_id": branch[
            "execution_id"
        ],
        "benchmark": benchmark,
        "instance_id": branch[
            "instance_id"
        ],
        "intervention_operator": operator,
        "selected_steps_chronological": steps,
        "bindings": checks,
        "bfcl_slot_bindings":
            bfcl_slot_bindings,
        "status": "PASS",
    }


def dry_run(
    branches,
    descriptors,
):
    bfcl_mod = load_module(
        "decouple_bfcl_runtime",
        BFCL_RUNTIME,
    )

    tool_mod = load_module(
        "decouple_tool_runtime_dry_run",
        TOOL_RUNTIME,
    )

    if not hasattr(
        tool_mod,
        "MAX_AGENT_TURNS",
    ):
        raise RuntimeError(
            "TOOLALPACA_FROZEN_MAX_AGENT_TURNS_MISSING"
        )

    if int(tool_mod.MAX_AGENT_TURNS) <= 0:
        raise RuntimeError(
            "TOOLALPACA_FROZEN_MAX_AGENT_TURNS_INVALID"
        )

    print(
        "TOOLALPACA_FROZEN_MAX_AGENT_TURNS="
        + str(int(tool_mod.MAX_AGENT_TURNS))
    )

    checker_path = (
        BFCL_ROOT
        / "bfcl_eval/eval_checker/multi_turn_eval/"
          "multi_turn_checker.py"
    )

    if (
        sha256_file(checker_path)
        !=
        "b3b787515eda3bf0e365e39634a8fc7f"
        "831763f010f716d35d86f96fd5aab1b5"
    ):
        raise RuntimeError(
            "BFCL_TERMINAL_CHECKER_HASH_MISMATCH"
        )

    sys.path.insert(
        0,
        str(BFCL_ROOT),
    )

    from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import (
        multi_turn_checker as _bfcl_terminal_import_gate,
    )

    if _bfcl_terminal_import_gate is None:
        raise RuntimeError(
            "BFCL_TERMINAL_IMPORT_GATE_FAILED"
        )

    print("BFCL_TERMINAL_IMPORT_GATE=PASS")

    results = []

    oracle_index = (
        load_oracle_patch_index()
    )

    full_mode = (
        len(branches) == 2518
    )

    generalized_mode = (
        full_mode
        or any(
            branch["benchmark"] == "Math-Shepherd"
            or branch["intervention_operator"] == "V_oracle"
            or len(branch["selected_steps_chronological"]) > 1
            for branch in branches
        )
    )

    if generalized_mode:
        for branch in branches:
            results.append(
                full_dry_run_branch(
                    branch,
                    descriptors,
                    oracle_index,
                )
            )

        return results

    for branch in branches:
        desc = (
            get_singleton_descriptor(
                branch,
                descriptors,
            )
        )

        benchmark = branch[
            "benchmark"
        ]

        if benchmark == "BFCL":
            results.append(
                bfcl_dry_run_branch(
                    branch,
                    desc,
                    bfcl_mod,
                    descriptors,
                )
            )

        elif benchmark == "ToolAlpaca":
            results.append(
                tool_dry_run_branch(
                    branch,
                    desc,
                )
            )

        else:
            raise RuntimeError(
                "COVERAGE_DRY_RUN_UNSUPPORTED_BENCHMARK="
                + benchmark
            )

    return results

def verify_full_2518_execution_unlock():
    if not REPRESENTATIVE_FINAL_AUDIT.is_file():
        raise RuntimeError(
            "REPRESENTATIVE_FINAL_AUDIT_MISSING"
        )

    if (
        sha256_file(
            REPRESENTATIVE_FINAL_AUDIT
        )
        != EXPECTED_REPRESENTATIVE_FINAL_AUDIT_SHA256
    ):
        raise RuntimeError(
            "REPRESENTATIVE_FINAL_AUDIT_HASH_MISMATCH"
        )

    if not REPRESENTATIVE_SHARD.is_file():
        raise RuntimeError(
            "REPRESENTATIVE_SHARD_MISSING"
        )

    if (
        sha256_file(
            REPRESENTATIVE_SHARD
        )
        != EXPECTED_REPRESENTATIVE_SHARD_SHA256
    ):
        raise RuntimeError(
            "REPRESENTATIVE_SHARD_HASH_MISMATCH"
        )

    audit = json.loads(
        REPRESENTATIVE_FINAL_AUDIT.read_text(
            encoding="utf-8"
        )
    )

    if audit.get("status") != "PASS":
        raise RuntimeError(
            "REPRESENTATIVE_FINAL_AUDIT_NOT_PASS"
        )

    if audit.get("branch_count") != 6:
        raise RuntimeError(
            "REPRESENTATIVE_BRANCH_COUNT_NOT_SIX"
        )

    if audit.get("all_execution_valid") is not True:
        raise RuntimeError(
            "REPRESENTATIVE_EXECUTION_NOT_ALL_VALID"
        )

    if (
        audit.get("full_2518_api_execution_allowed")
        is not True
    ):
        raise RuntimeError(
            "REPRESENTATIVE_AUDIT_DID_NOT_UNLOCK_FULL_EXECUTION"
        )

    if (
        audit.get("runner_sha256")
        != EXPECTED_REPRESENTATIVE_RUNNER_SHA256
    ):
        raise RuntimeError(
            "REPRESENTATIVE_AUDIT_RUNNER_SHA_MISMATCH"
        )

    if (
        audit.get("source_shard_sha256")
        != EXPECTED_REPRESENTATIVE_SHARD_SHA256
    ):
        raise RuntimeError(
            "REPRESENTATIVE_AUDIT_SHARD_SHA_MISMATCH"
        )

    return True


TOOLALPACA_SYMBOLIC_ORACLE_UNAVAILABLE_AMENDMENT = Path(
    "__DECOUPLE_ROOT__/10_PILOT/STEP3/06_AUDIT/"
    "STEP3E_EXACT_CHECKPOINT_REPLAY/AMENDMENTS/"
    "TOOLALPACA_SYMBOLIC_ORACLE_UNAVAILABLE_AMENDMENT_V1.json"
)

EXPECTED_TOOLALPACA_SYMBOLIC_ORACLE_UNAVAILABLE_AMENDMENT_SHA256 = (
    "2338b657cc828835dfe77d3460e70db5c06359df3859556ae108b56d4f3866aa"
)

EXPECTED_TOOLALPACA_SYMBOLIC_ORACLE_UNAVAILABLE_EXECUTION_IDS = {
    "10efdfa462cd12871335418a8c0b3d16c24b9b3dc2f163f632ec83c283975267",
    "a479b91becc2676330ac458c24484465bf8074e575a510b3ace5781d9c472457",
    "65451867357ffa28390872a290bbb36772be7e4bf9d1bd1b6948422d3bf0f625",
    "cbedbbe448cd303cb58eeff86d88cdfa94ddcdb07bf45ad3b615d3140bea1682",
}


def load_toolalpaca_symbolic_oracle_unavailable_execution_ids():
    path = (
        TOOLALPACA_SYMBOLIC_ORACLE_UNAVAILABLE_AMENDMENT
    )

    if not path.is_file():
        raise RuntimeError(
            "TOOLALPACA_SYMBOLIC_ORACLE_AMENDMENT_MISSING="
            + str(path)
        )

    observed_sha = sha256_file(path)

    if (
        observed_sha
        != EXPECTED_TOOLALPACA_SYMBOLIC_ORACLE_UNAVAILABLE_AMENDMENT_SHA256
    ):
        raise RuntimeError(
            "TOOLALPACA_SYMBOLIC_ORACLE_AMENDMENT_SHA256_MISMATCH="
            + observed_sha
        )

    obj = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if obj.get("status") != "FROZEN":
        raise RuntimeError(
            "TOOLALPACA_SYMBOLIC_ORACLE_AMENDMENT_NOT_FROZEN"
        )

    if (
        obj.get("scope")
        != "FOUR_TOOLALPACA_V_ORACLE_BRANCHES_ONLY"
    ):
        raise RuntimeError(
            "TOOLALPACA_SYMBOLIC_ORACLE_AMENDMENT_SCOPE_MISMATCH"
        )

    scientific = obj.get(
        "scientific_interpretation",
        {},
    )

    if (
        scientific.get("oracle_target_status")
        != "UNAVAILABLE"
        or scientific.get(
            "scientific_result_valid"
        ) is not False
        or scientific.get("Z") is not None
        or scientific.get(
            "branch_replay_executed"
        ) is not False
    ):
        raise RuntimeError(
            "TOOLALPACA_SYMBOLIC_ORACLE_AMENDMENT_SEMANTICS_INVALID"
        )

    observed_ids = {
        row["execution_id"]
        for row in obj.get(
            "affected_branches",
            []
        )
    }

    if (
        observed_ids
        != EXPECTED_TOOLALPACA_SYMBOLIC_ORACLE_UNAVAILABLE_EXECUTION_IDS
    ):
        raise RuntimeError(
            "TOOLALPACA_SYMBOLIC_ORACLE_AMENDMENT_EXECUTION_IDS_MISMATCH"
        )

    return observed_ids


def validate_toolalpaca_unavailable_result(
    obj,
    execution_id,
):
    if obj.get("execution_id") != execution_id:
        raise RuntimeError(
            "UNAVAILABLE_RESULT_EXECUTION_ID_MISMATCH="
            + execution_id
        )

    if obj.get("status") != "UNAVAILABLE":
        raise RuntimeError(
            "UNAVAILABLE_RESULT_STATUS_INVALID="
            + execution_id
        )

    if (
        obj.get("oracle_target_status")
        != "UNAVAILABLE"
    ):
        raise RuntimeError(
            "UNAVAILABLE_RESULT_ORACLE_STATUS_INVALID="
            + execution_id
        )

    if (
        obj.get("scientific_result_valid")
        is not False
    ):
        raise RuntimeError(
            "UNAVAILABLE_RESULT_SCIENTIFIC_VALIDITY_INVALID="
            + execution_id
        )

    if obj.get("terminal_outcome_Z") is not None:
        raise RuntimeError(
            "UNAVAILABLE_RESULT_Z_NOT_NONE="
            + execution_id
        )

    if (
        obj.get("branch_replay_executed")
        is not False
    ):
        raise RuntimeError(
            "UNAVAILABLE_RESULT_REPLAY_FLAG_INVALID="
            + execution_id
        )

    return True


def execute(
    branches,
    descriptors,
    input_path,
):
    global ACTIVE_EXECUTION_ID

    if not os.environ.get(
        "OPENAI_API_KEY"
    ):
        raise RuntimeError(
            "OPENAI_API_KEY_NOT_SET"
        )

    if not DRYRUN_AUDIT.is_file():
        raise RuntimeError(
            "FORMAL_DRY_RUN_AUDIT_MISSING"
        )

    gate = json.loads(
        DRYRUN_AUDIT.read_text(
            encoding="utf-8"
        )
    )

    if gate.get(
        "status"
    ) != "PASS":
        raise RuntimeError(
            "FORMAL_DRY_RUN_NOT_PASS"
        )

    if (
        gate.get(
            "api_execution_allowed_for_same_runner_and_input"
        )
        is not True
    ):
        raise RuntimeError(
            "FORMAL_DRY_RUN_EXECUTION_PERMISSION_NOT_GRANTED"
        )

    if (
        gate.get(
            "runner_sha256"
        )
        != sha256_file(
            THIS_FILE
        )
    ):
        raise RuntimeError(
            "RUNNER_CHANGED_AFTER_DRY_RUN"
        )

    if (
        gate.get(
            "input_sha256"
        )
        != sha256_file(
            input_path
        )
    ):
        raise RuntimeError(
            "INPUT_CHANGED_AFTER_DRY_RUN"
        )

    from openai import OpenAI

    client = OpenAI()

    bfcl_mod = load_module(
        "decouple_bfcl_runtime",
        BFCL_RUNTIME,
    )

    tool_mod = load_module(
        "decouple_tool_runtime",
        TOOL_RUNTIME,
    )

    oracle_index = (
        load_oracle_patch_index()
    )

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    completed = 0
    skipped = 0
    unavailable_this_run = 0
    skipped_existing_unavailable = 0

    unavailable_execution_ids = (
        load_toolalpaca_symbolic_oracle_unavailable_execution_ids()
    )

    for branch in branches:
        result_path = (
            RESULT_DIR
            / (
                branch[
                    "execution_id"
                ]
                + ".json"
            )
        )

        execution_id = branch[
            "execution_id"
        ]

        amendment_unavailable = (
            execution_id
            in unavailable_execution_ids
        )

        if result_path.is_file():
            old = json.loads(
                result_path.read_text(
                    encoding="utf-8"
                )
            )

            if old.get(
                "status"
            ) == "PASS":
                if amendment_unavailable:
                    raise RuntimeError(
                        "AMENDMENT_UNAVAILABLE_HAS_EXISTING_PASS="
                        + execution_id
                    )

                print(
                    "BRANCH_SKIP_PASS="
                    + execution_id
                )

                skipped += 1
                continue

            if (
                amendment_unavailable
                and old.get("status")
                == "UNAVAILABLE"
            ):
                validate_toolalpaca_unavailable_result(
                    old,
                    execution_id,
                )

                print(
                    "BRANCH_SKIP_UNAVAILABLE="
                    + execution_id
                )

                skipped_existing_unavailable += 1
                continue

        if amendment_unavailable:
            preserved_failure = preserve_existing_nonpass_result(
                result_path,
                execution_id,
            )

            if preserved_failure is not None:
                print(
                    "PRIOR_FAILURE_PRESERVED="
                    + str(preserved_failure)
                )

            unavailable_result = {
                "execution_id":
                    execution_id,
                "benchmark":
                    branch["benchmark"],
                "instance_id":
                    branch["instance_id"],
                "intervention_operator":
                    branch[
                        "intervention_operator"
                    ],
                "selected_steps_chronological":
                    branch[
                        "selected_steps_chronological"
                    ],
                "status":
                    "UNAVAILABLE",
                "oracle_target_status":
                    "UNAVAILABLE",
                "unavailable_reason":
                    (
                        "TOOLALPACA_RELEASED_GOLDEN_"
                        "ACTION_INPUT_SYMBOLIC_NON_EXECUTABLE"
                    ),
                "scientific_result_valid":
                    False,
                "terminal_outcome_Z":
                    None,
                "branch_replay_executed":
                    False,
                "terminal_outcome_materialized":
                    False,
                "singleton_gain_materialized":
                    False,
                "model_calls":
                    0,
                "api_attempts":
                    0,
                "amendment_file":
                    str(
                        TOOLALPACA_SYMBOLIC_ORACLE_UNAVAILABLE_AMENDMENT
                    ),
                "amendment_sha256":
                    EXPECTED_TOOLALPACA_SYMBOLIC_ORACLE_UNAVAILABLE_AMENDMENT_SHA256,
            }

            validate_toolalpaca_unavailable_result(
                unavailable_result,
                execution_id,
            )

            write_json(
                result_path,
                unavailable_result,
            )

            print(
                "BRANCH_UNAVAILABLE="
                + execution_id
                + ":Z=None"
            )

            unavailable_this_run += 1
            continue

        preserved_failure = preserve_existing_nonpass_result(
            result_path,
            branch["execution_id"],
        )

        if preserved_failure is not None:
            print(
                "PRIOR_FAILURE_PRESERVED="
                + str(preserved_failure)
            )

        ACTIVE_EXECUTION_ID = branch[
            "execution_id"
        ]

        branch_descriptors = (
            get_branch_descriptors(
                branch,
                descriptors,
            )
        )

        print(
            "BRANCH_CURRENT="
            + branch[
                "execution_id"
            ]
            + ":"
            + branch[
                "benchmark"
            ]
            + ":"
            + branch[
                "instance_id"
            ]
        )

        started = time.time()

        try:
            benchmark = branch[
                "benchmark"
            ]

            if benchmark == "Math-Shepherd":
                result = execute_math_branch(
                    branch,
                    descriptors,
                    client,
                )

            elif benchmark == "BFCL":
                result = execute_bfcl_branch_v2(
                    branch,
                    branch_descriptors,
                    bfcl_mod,
                    descriptors,
                    oracle_index,
                    client,
                )

            elif benchmark == "ToolAlpaca":
                result = execute_tool_branch_v2(
                    branch,
                    branch_descriptors,
                    oracle_index,
                    tool_mod,
                    client,
                )

            else:
                raise RuntimeError(
                    "FORMAL_EXECUTION_UNSUPPORTED_BENCHMARK="
                    + benchmark
                )

            result[
                "wall_clock_seconds"
            ] = (
                time.time()
                - started
            )

            compute_rows = result.pop(
                "compute_rows"
            )

            for compute_row in compute_rows:
                compute_row[
                    "execution_id"
                ] = branch[
                    "execution_id"
                ]

                append_jsonl(
                    COMPUTE_LEDGER,
                    compute_row,
                )

            result[
                "model_calls"
            ] = sum(
                1
                for row in compute_rows
                if not row[
                    "call_role"
                ].endswith(
                    "_provider_parameter_rejection"
                )
            )

            result[
                "api_attempts"
            ] = len(
                compute_rows
            )

            write_json(
                result_path,
                result,
            )

            ACTIVE_EXECUTION_ID = None

            print(
                "BRANCH_PASS="
                + branch[
                    "execution_id"
                ]
                + ":Z="
                + str(
                    result[
                        "terminal_outcome_Z"
                    ]
                )
            )

            completed += 1

        except Exception as exc:
            failure = {
                "execution_id":
                    branch[
                        "execution_id"
                    ],

                "benchmark":
                    branch[
                        "benchmark"
                    ],

                "instance_id":
                    branch[
                        "instance_id"
                    ],

                "status":
                    "FAIL",

                "error_type":
                    type(
                        exc
                    ).__name__,

                "error":
                    str(exc),

                "wall_clock_seconds":
                    time.time()
                    - started,

                "scientific_result_valid":
                    False,

                "compute_journal":
                    str(COMPUTE_JOURNAL),
            }

            FAILED_ATTEMPT_DIR.mkdir(
                parents=True,
                exist_ok=True,
            )

            failure_attempt_path = (
                FAILED_ATTEMPT_DIR
                / (
                    branch["execution_id"]
                    + "__CURRENT__"
                    + str(time.time_ns())
                    + ".json"
                )
            )

            write_json(
                failure_attempt_path,
                failure,
            )

            write_json(
                result_path,
                failure,
            )

            ACTIVE_EXECUTION_ID = None

            print(
                "BRANCH_FAIL="
                + branch[
                    "execution_id"
                ]
                + ":"
                + type(
                    exc
                ).__name__
                + ":"
                + str(exc)
            )

            raise

    return {
        "completed_this_run":
            completed,

        "skipped_existing_pass":
            skipped,

        "unavailable_this_run":
            unavailable_this_run,

        "skipped_existing_unavailable":
            skipped_existing_unavailable,
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
    )

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--dry-run",
        action="store_true",
    )

    mode.add_argument(
        "--execute",
        action="store_true",
    )

    args = parser.parse_args()

    verify_hashes()

    if not args.input.is_file():
        raise RuntimeError(
            "INPUT_NOT_FOUND="
            + str(
                args.input
            )
        )

    branches = load_jsonl(
        args.input
    )

    if not branches:
        raise RuntimeError(
            "EMPTY_INPUT"
        )

    descriptors = (
        descriptor_index()
    )

    full_mode = (
        len(branches) == 2518
    )

    generalized_mode = (
        full_mode
        or any(
            branch["benchmark"] == "Math-Shepherd"
            or branch["intervention_operator"] == "V_oracle"
            or len(branch["selected_steps_chronological"]) > 1
            for branch in branches
        )
    )

    full_execution_unlock = False

    if full_mode:
        full_execution_unlock = (
            verify_full_2518_execution_unlock()
        )

    if generalized_mode:
        oracle_index = (
            load_oracle_patch_index()
        )

        for branch in branches:
            full_dry_run_branch(
                branch,
                descriptors,
                oracle_index,
            )

    else:
        for branch in branches:
            get_singleton_descriptor(
                branch,
                descriptors,
            )

            if (
                branch[
                    "benchmark"
                ]
                not in {
                    "BFCL",
                    "ToolAlpaca",
                }
            ):
                raise RuntimeError(
                    "FORMAL_COVERAGE_EXECUTOR_UNSUPPORTED_BENCHMARK="
                    + branch[
                        "benchmark"
                    ]
                )

    if args.dry_run:
        results = dry_run(
            branches,
            descriptors,
        )

        audit = {
            "scientific_authority":
                "SPEC5",

            "scientific_substep":
                "STEP3E_EXACT_CHECKPOINT_RESTORE_REPLAY",

            "status":
                "PASS",

            "mode":
                "CPU_NO_API_DRY_RUN",

            "formal_not_smoke":
                True,

            "scope":
                (
                    "FULL_2518_FORMAL_EXECUTION_LEDGER"
                    if full_mode
                    else
                    "GENERALIZED_SIX_PATH_REPRESENTATIVE_GATE"
                    if generalized_mode
                    else
                    "FROZEN_CORE_METHOD_COVERAGE_SINGLETON_BRANCHES"
                ),

            "input":
                str(
                    args.input
                ),

            "input_sha256":
                sha256_file(
                    args.input
                ),

            "runner":
                str(
                    THIS_FILE
                ),

            "runner_sha256":
                sha256_file(
                    THIS_FILE
                ),

            "branches_checked":
                len(
                    branches
                ),

            "branch_checks":
                results,

            "model_run":
                False,

            "api_calls":
                0,

            "branch_replay_executed":
                False,

            "api_execution_allowed_for_same_runner_and_input":
                (
                    full_execution_unlock
                    if full_mode
                    else True
                ),
        }

        write_json(
            DRYRUN_AUDIT,
            audit,
        )

        if full_mode:
            print(
                "STEP3E_FULL_2518_NO_API_DRY_RUN=PASS"
            )
        elif generalized_mode:
            print(
                "STEP3E_SIX_PATH_GENERALIZED_NO_API_DRY_RUN=PASS"
            )
        else:
            print(
                "STEP3E_FORMAL_SINGLETON_COVERAGE_DRY_RUN=PASS"
            )

        print(
            "BRANCHES_CHECKED="
            + str(
                len(
                    branches
                )
            )
        )

        print(
            "RUNNER_SHA256="
            + sha256_file(
                THIS_FILE
            )
        )

        print(
            "INPUT_SHA256="
            + sha256_file(
                args.input
            )
        )

        print(
            "DRYRUN_AUDIT_SHA256="
            + sha256_file(
                DRYRUN_AUDIT
            )
        )

        print("MODEL_RUN=NO")
        print("API_CALLS=0")
        if full_mode:
            print(
                "API_EXECUTION_ALLOWED="
                + (
                    "YES"
                    if full_execution_unlock
                    else "NO"
                )
            )
            print(
                "NEXT=RUN_SAME_RUNNER_EXECUTE"
                if full_execution_unlock
                else
                "NEXT=FULL_EXECUTION_UNLOCK_BLOCKED"
            )
        else:
            print(
                "API_EXECUTION_ALLOWED=YES"
            )
            print(
                "NEXT=RUN_SAME_RUNNER_EXECUTE"
            )

        return

    summary = execute(
        branches,
        descriptors,
        args.input,
    )

    result_files = list(
        RESULT_DIR.glob(
            "*.json"
        )
    )

    input_execution_ids = {
        branch["execution_id"]
        for branch in branches
    }

    frozen_unavailable_execution_ids = (
        load_toolalpaca_symbolic_oracle_unavailable_execution_ids()
    )

    input_unavailable_execution_ids = (
        input_execution_ids
        & frozen_unavailable_execution_ids
    )

    input_executable_execution_ids = (
        input_execution_ids
        - input_unavailable_execution_ids
    )

    all_pass_rows = []
    input_pass_rows = []
    input_unavailable_rows = []

    for path in result_files:
        obj = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        execution_id = obj.get(
            "execution_id"
        )

        if obj.get("status") == "PASS":
            all_pass_rows.append(
                obj
            )

            if (
                execution_id
                in input_unavailable_execution_ids
            ):
                raise RuntimeError(
                    "AMENDMENT_UNAVAILABLE_COUNTED_AS_PASS="
                    + str(execution_id)
                )

            if (
                execution_id
                in input_executable_execution_ids
            ):
                input_pass_rows.append(
                    obj
                )

        elif (
            obj.get("status")
            == "UNAVAILABLE"
            and execution_id
            in input_unavailable_execution_ids
        ):
            validate_toolalpaca_unavailable_result(
                obj,
                execution_id,
            )

            input_unavailable_rows.append(
                obj
            )

    input_pass_ids = {
        row["execution_id"]
        for row in input_pass_rows
    }

    input_unavailable_ids = {
        row["execution_id"]
        for row in input_unavailable_rows
    }

    if (
        input_pass_ids
        != input_executable_execution_ids
    ):
        missing = sorted(
            input_executable_execution_ids
            - input_pass_ids
        )

        extra = sorted(
            input_pass_ids
            - input_executable_execution_ids
        )

        raise RuntimeError(
            "FORMAL_EXECUTION_EXECUTABLE_PASS_SET_MISMATCH:"
            + "missing="
            + repr(missing)
            + ":extra="
            + repr(extra)
        )

    if (
        input_unavailable_ids
        != input_unavailable_execution_ids
    ):
        missing = sorted(
            input_unavailable_execution_ids
            - input_unavailable_ids
        )

        extra = sorted(
            input_unavailable_ids
            - input_unavailable_execution_ids
        )

        raise RuntimeError(
            "FORMAL_EXECUTION_UNAVAILABLE_SET_MISMATCH:"
            + "missing="
            + repr(missing)
            + ":extra="
            + repr(extra)
        )

    if (
        input_pass_ids
        & input_unavailable_ids
    ):
        raise RuntimeError(
            "FORMAL_EXECUTION_PASS_UNAVAILABLE_OVERLAP"
        )

    if (
        input_pass_ids
        | input_unavailable_ids
    ) != input_execution_ids:
        raise RuntimeError(
            "FORMAL_EXECUTION_INPUT_PARTITION_MISMATCH"
        )

    audit = {
        "scientific_authority":
            "SPEC5",

        "scientific_substep":
            "STEP3E_EXACT_CHECKPOINT_RESTORE_REPLAY",

        "status":
            "PASS",

        "formal_not_smoke":
            True,

        "scope":
            "INPUT_BOUND_FORMAL_EXECUTION",

        "input":
            str(args.input),

        "input_sha256":
            sha256_file(args.input),

        "runner_sha256":
            sha256_file(THIS_FILE),

        "completed_this_run":
            summary[
                "completed_this_run"
            ],

        "skipped_existing_pass":
            summary[
                "skipped_existing_pass"
            ],

        "input_branch_count":
            len(input_execution_ids),

        "input_executable_branch_count":
            len(
                input_executable_execution_ids
            ),

        "input_unavailable_branch_count":
            len(
                input_unavailable_execution_ids
            ),

        "input_pass_result_count":
            len(input_pass_rows),

        "input_unavailable_result_count":
            len(input_unavailable_rows),

        "unavailable_execution_ids":
            sorted(
                input_unavailable_execution_ids
            ),

        "symbolic_oracle_unavailable_amendment":
            str(
                TOOLALPACA_SYMBOLIC_ORACLE_UNAVAILABLE_AMENDMENT
            ),

        "symbolic_oracle_unavailable_amendment_sha256":
            EXPECTED_TOOLALPACA_SYMBOLIC_ORACLE_UNAVAILABLE_AMENDMENT_SHA256,

        "all_pass_result_files":
            len(all_pass_rows),

        "terminal_outcomes":
            {
                row["execution_id"]:
                    row["terminal_outcome_Z"]
                for row in input_pass_rows
            },

        "compute_ledger":
            str(COMPUTE_LEDGER),

        "compute_ledger_sha256":
            (
                sha256_file(
                    COMPUTE_LEDGER
                )
                if COMPUTE_LEDGER.is_file()
                else None
            ),

        "compute_journal":
            str(COMPUTE_JOURNAL),

        "compute_journal_sha256":
            (
                sha256_file(
                    COMPUTE_JOURNAL
                )
                if COMPUTE_JOURNAL.is_file()
                else None
            ),
    }

    write_json(
        EXECUTION_AUDIT,
        audit,
    )

    print(
        "STEP3E_FORMAL_EXECUTION=PASS"
    )

    print(
        "COMPLETED_THIS_RUN="
        + str(
            summary[
                "completed_this_run"
            ]
        )
    )

    print(
        "SKIPPED_EXISTING_PASS="
        + str(
            summary[
                "skipped_existing_pass"
            ]
        )
    )

    print(
        "INPUT_EXECUTABLE_BRANCHES="
        + str(
            len(
                input_executable_execution_ids
            )
        )
    )

    print(
        "INPUT_UNAVAILABLE_RESULTS="
        + str(
            len(
                input_unavailable_rows
            )
        )
    )

    print(
        "INPUT_PASS_RESULTS="
        + str(len(input_pass_rows))
    )

    print(
        "ALL_PASS_RESULT_FILES="
        + str(len(all_pass_rows))
    )

    print(
        "EXECUTION_AUDIT_SHA256="
        + sha256_file(
            EXECUTION_AUDIT
        )
    )

    print(
        "NEXT=REVIEW_INPUT_BOUND_FORMAL_RESULTS"
    )


if __name__ == "__main__":
    main()
