#!/usr/bin/env python3

import hashlib
import json
import sys
import time
from pathlib import Path

from openai import OpenAI
import tiktoken


ROOT = Path("__DECOUPLE_ROOT__")

PREFIX_ROOT = (
    ROOT
    / "10_PILOT/STEP1/04_OUTPUTS/"
      "STEP1C_PREFIX/CAUSAL_PREFIXES"
)

PREFIX_INDEX = (
    PREFIX_ROOT
    / "PILOT_CAUSAL_PREFIX_INDEX.json"
)

BFCL_TOOLS_PRE = (
    ROOT
    / "10_PILOT/STEP1/02_INPUTS/PRE_ONLY/"
      "BFCL_PILOT25_TOOLS_PRE.json"
)

TOOLALPACA_EXEC_PRE = (
    ROOT
    / "10_PILOT/STEP1/02_INPUTS/PRE_ONLY/"
      "TOOLALPACA_PILOT25_EXECUTION_PRE.jsonl"
)

_BUNDLED_DATA_GENERATION = Path(__file__).resolve().parent
TOOLALPACA_CODE = (
    _BUNDLED_DATA_GENERATION
    if (_BUNDLED_DATA_GENERATION / "generate_toolalpaca_pilot25_base_trajectories.py").is_file()
    else ROOT / "10_PILOT/STEP1/01_CODE/STEP1B_TRAJECTORY"
)

sys.path.insert(
    0,
    str(TOOLALPACA_CODE),
)

from generate_toolalpaca_pilot25_base_trajectories import (
    build_tools as build_toolalpaca_tools,
)


OUT_DIR = (
    ROOT
    / "10_PILOT/STEP1/04_OUTPUTS/"
      "STEP1D_SEMANTIC/K8_CONTINUATIONS"
)

AUDIT_DIR = (
    ROOT
    / "10_PILOT/STEP1/06_AUDIT/"
      "STEP1D_SEMANTIC"
)

FAILURE_DIR = (
    ROOT
    / "10_PILOT/STEP1/06_AUDIT/"
      "STEP1D_SEMANTIC/RAW_PROVIDER_FAILURES"
)

MODEL = "gpt-5.6-terra"
REASONING_EFFORT = "medium"

K = 8

REQUESTED_TEMPERATURE = 0.7
REQUESTED_TOP_P = 0.95
EFFECTIVE_SAMPLING = "provider_default"

API_MAX_OUTPUT_TOKENS = 8192
SCIENTIFIC_MAX_DECISION_TOKENS = 256
TOKENIZER_MODEL = "gpt-5.6-terra"
TOKENIZER_ENCODING = "o200k_base"

MASTER_SEED = 20260829

MAX_INVALID_CONTINUATION_RETRIES = 3

EXPECTED_PREFIX_INDEX_SHA256 = (
    "7b0aaff15f7b26349cac43cf3b7bbe367e37075c86a021d7b0c1a3278c88a8b8"
)

FORBIDDEN = {
    "possible_answer",
    "ground_truth",
    "golden_answers",
    "golden_answer",
    "correctness",
    "reward",
    "outcome",
    "oracle",
    "intervention_gain",
    "process_correctness",
    "final_response_correctness",
}


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(block)

    return h.hexdigest()


def canonical_hash(obj):
    payload = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(
        payload
    ).hexdigest()


def find_forbidden(obj):
    found = []

    def walk(value, path="root"):
        if isinstance(value, dict):
            for key, child in value.items():
                p = f"{path}.{key}"

                if str(key).lower() in FORBIDDEN:
                    found.append(p)

                walk(child, p)

        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(
                    child,
                    f"{path}[{i}]",
                )

    walk(obj)

    return found


def render_history(prefix):
    parts = []

    for item in prefix[
        "history_before_step"
    ]:
        typ = item.get(
            "type",
            "unknown",
        )

        if typ in {
            "user_message",
            "problem",
        }:
            parts.append(
                "USER_OR_PROBLEM:\n"
                + str(
                    item.get(
                        "content",
                        "",
                    )
                )
            )

        elif typ == "math_reasoning_step":
            parts.append(
                "PRIOR_REASONING_STEP:\n"
                + str(
                    item.get(
                        "content",
                        "",
                    )
                )
            )

        elif typ in {
            "tool_action",
            "joint_tool_action",
        }:
            parts.append(
                "PRIOR_TOOL_ACTION:\n"
                + json.dumps(
                    item,
                    sort_keys=True,
                    ensure_ascii=False,
                )
            )

        elif typ in {
            "tool_observation",
            "joint_tool_observation",
        }:
            parts.append(
                "PRIOR_TOOL_OBSERVATION:\n"
                + json.dumps(
                    item,
                    sort_keys=True,
                    ensure_ascii=False,
                )
            )

        elif typ == "assistant_text":
            parts.append(
                "PRIOR_ASSISTANT_TEXT:\n"
                + str(
                    item.get(
                        "content",
                        "",
                    )
                )
            )

        else:
            parts.append(
                "PRIOR_CONTEXT:\n"
                + json.dumps(
                    item,
                    sort_keys=True,
                    ensure_ascii=False,
                )
            )

    return "\n\n".join(parts)


def build_prompt(prefix):
    history = render_history(
        prefix
    )

    benchmark = prefix[
        "benchmark"
    ]

    if benchmark == "Math-Shepherd":
        instruction = (
            "Generate exactly one possible next local reasoning step "
            "from the causal history. Do not solve or continue beyond "
            "that one step."
        )
    else:
        instruction = (
            "Generate exactly one possible next local agent decision "
            "from the causal history. You may call an available tool "
            "or produce a direct assistant response as appropriate. "
            "Stop immediately after that one local decision."
        )

    return (
        "You are sampling one local continuation from a frozen "
        "decision-time causal history for a research experiment.\n\n"
        + instruction
        + "\n\n"
        + "The sampled local decision must contain no more than "
          "256 non-reasoning output tokens.\n\n"
        + "CAUSAL_HISTORY_BEGIN\n"
        + history
        + "\nCAUSAL_HISTORY_END"
    )


def load_prefixes():
    if (
        sha256_file(
            PREFIX_INDEX
        )
        != EXPECTED_PREFIX_INDEX_SHA256
    ):
        raise RuntimeError(
            "Frozen causal-prefix index hash mismatch."
        )

    index = json.loads(
        PREFIX_INDEX.read_text(
            encoding="utf-8"
        )
    )

    prefixes = []

    for row in index:
        path = (
            ROOT
            / row["prefix_path"]
        )

        for line in path.read_text(
            encoding="utf-8"
        ).splitlines():
            if not line.strip():
                continue

            prefix = json.loads(
                line
            )

            forbidden = (
                find_forbidden(
                    prefix
                )
            )

            if forbidden:
                raise RuntimeError(
                    "Forbidden prefix fields: "
                    + repr(forbidden)
                )

            prefixes.append(
                prefix
            )

    if len(prefixes) != 631:
        raise RuntimeError(
            f"Expected 631 prefixes, got {len(prefixes)}"
        )

    return prefixes


def load_bfcl_tools():
    rows = json.loads(
        BFCL_TOOLS_PRE.read_text(
            encoding="utf-8"
        )
    )

    if len(rows) != 25:
        raise RuntimeError(
            "BFCL tool authority must contain 25 instances."
        )

    return {
        row["instance_id"]:
            row["tools"]
        for row in rows
    }


def load_toolalpaca_tools():
    rows = [
        json.loads(line)
        for line in TOOLALPACA_EXEC_PRE.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    if len(rows) != 25:
        raise RuntimeError(
            "ToolAlpaca execution PRE must contain 25 instances."
        )

    mapping = {}

    for row in rows:
        tools, _ = (
            build_toolalpaca_tools(
                row["documentation"]
            )
        )

        mapping[
            row["instance_id"]
        ] = tools

    return mapping


def usage_dict(response):
    usage = getattr(
        response,
        "usage",
        None,
    )

    if usage is None:
        raise RuntimeError(
            "Missing Responses usage."
        )

    input_tokens = int(
        getattr(
            usage,
            "input_tokens",
            0,
        )
        or 0
    )

    output_tokens = int(
        getattr(
            usage,
            "output_tokens",
            0,
        )
        or 0
    )

    total_tokens = int(
        getattr(
            usage,
            "total_tokens",
            0,
        )
        or 0
    )

    details = getattr(
        usage,
        "output_tokens_details",
        None,
    )

    if details is None:
        raise RuntimeError(
            "Missing output_tokens_details."
        )

    reasoning_tokens = int(
        getattr(
            details,
            "reasoning_tokens",
            0,
        )
        or 0
    )

    decision_tokens = (
        output_tokens
        - reasoning_tokens
    )

    if decision_tokens < 0:
        raise RuntimeError(
            "Negative decision token count."
        )

    return {
        "input_tokens":
            input_tokens,
        "output_tokens":
            output_tokens,
        "reasoning_tokens":
            reasoning_tokens,
        "decision_tokens":
            decision_tokens,
        "total_tokens":
            total_tokens,
    }


def serialize_response(response):
    if hasattr(response, "model_dump"):
        return response.model_dump()

    raise RuntimeError(
        "Response object has no model_dump method."
    )


def extract_function_calls(response):
    calls = []

    for item in getattr(
        response,
        "output",
        [],
    ):
        if getattr(
            item,
            "type",
            None,
        ) != "function_call":
            continue

        raw_arguments = getattr(
            item,
            "arguments",
            None,
        )

        if raw_arguments is None:
            raise RuntimeError(
                "Function call missing arguments."
            )

        try:
            parsed_arguments = (
                json.loads(
                    raw_arguments
                )
            )
        except Exception as exc:
            raise RuntimeError(
                "Function call arguments "
                "are not valid JSON."
            ) from exc

        calls.append(
            {
                "call_id":
                    getattr(
                        item,
                        "call_id",
                        None,
                    ),
                "name":
                    getattr(
                        item,
                        "name",
                        None,
                    ),
                "arguments":
                    parsed_arguments,
                "arguments_raw":
                    raw_arguments,
            }
        )

    return calls


def add_usage(total, usage):
    for key in total:
        total[key] += usage[
            key
        ]


def zero_usage():
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "decision_tokens": 0,
        "total_tokens": 0,
    }


def main():
    prefixes = load_prefixes()

    bfcl_tools = (
        load_bfcl_tools()
    )

    toolalpaca_tools = (
        load_toolalpaca_tools()
    )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    AUDIT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    FAILURE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    immutable_inputs_before = {
        "prefix_index":
            sha256_file(
                PREFIX_INDEX
            ),
        "bfcl_tools_pre":
            sha256_file(
                BFCL_TOOLS_PRE
            ),
        "toolalpaca_execution_pre":
            sha256_file(
                TOOLALPACA_EXEC_PRE
            ),
    }

    client = OpenAI()

    tokenizer = tiktoken.encoding_for_model(
        TOKENIZER_MODEL
    )

    if tokenizer.name != TOKENIZER_ENCODING:
        raise RuntimeError(
            "Tokenizer mismatch: "
            f"{tokenizer.name} != "
            f"{TOKENIZER_ENCODING}"
        )

    archive_index = []
    ledger_rows = []

    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "decision_tokens": 0,
        "total_tokens": 0,
    }

    total_api_calls = 0
    accepted_continuations = 0

    type_counts = {
        "assistant_text": 0,
        "tool_call": 0,
        "joint_tool_call": 0,
        "no_observable_output": 0,
    }

    for candidate_number, prefix in enumerate(
        prefixes,
        start=1,
    ):
        benchmark = prefix[
            "benchmark"
        ]

        instance_id = prefix[
            "instance_id"
        ]

        step_index = int(
            prefix["step_index"]
        )

        prompt = build_prompt(
            prefix
        )

        if benchmark == "BFCL":
            tools = bfcl_tools[
                instance_id
            ]
            parallel_tool_calls = True

        elif benchmark == "ToolAlpaca":
            tools = toolalpaca_tools[
                instance_id
            ]
            parallel_tool_calls = False

        elif benchmark == "Math-Shepherd":
            tools = None
            parallel_tool_calls = None

        else:
            raise RuntimeError(
                "Unexpected benchmark: "
                + benchmark
            )

        benchmark_dir = (
            OUT_DIR
            / benchmark.replace(
                "/",
                "_",
            )
        )

        benchmark_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        out_path = (
            benchmark_dir
            / (
                f"{instance_id}"
                f"__step_{step_index:04d}"
                f"__k8.jsonl"
            )
        )

        if out_path.exists():
            existing = [
                json.loads(line)
                for line in out_path.read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]

            if len(existing) != K:
                raise RuntimeError(
                    "Existing K8 candidate file is incomplete: "
                    + str(out_path)
                )

            if any(
                row.get("prefix_hash")
                != prefix["prefix_hash"]
                for row in existing
            ):
                raise RuntimeError(
                    "Existing K8 prefix hash mismatch: "
                    + str(out_path)
                )

            archive_index.append(
                {
                    "benchmark":
                        benchmark,
                    "instance_id":
                        instance_id,
                    "step_index":
                        step_index,
                    "prefix_hash":
                        prefix["prefix_hash"],
                    "continuation_count":
                        len(existing),
                    "path":
                        str(
                            out_path.relative_to(
                                ROOT
                            )
                        ),
                    "sha256":
                        sha256_file(
                            out_path
                        ),
                }
            )

            for sample in existing:
                sample_usage = sample.get(
                    "all_attempt_usage",
                    sample["usage"],
                )

                add_usage(
                    totals,
                    sample_usage,
                )

                retry_count = int(
                    sample.get(
                        "retry_count",
                        0,
                    )
                )

                total_api_calls += (
                    1 + retry_count
                )

                accepted_continuations += 1

                continuation_type = sample[
                    "continuation_type"
                ]

                type_counts[
                    continuation_type
                ] += 1

                ledger_rows.append(
                    {
                        "benchmark":
                            benchmark,
                        "instance_id":
                            instance_id,
                        "step_index":
                            step_index,
                        "continuation_index":
                            sample[
                                "continuation_index"
                            ],
                        "response_id":
                            sample[
                                "response_id"
                            ],
                        "continuation_type":
                            continuation_type,
                        "usage":
                            sample["usage"],
                        "all_attempt_usage":
                            sample_usage,
                        "retry_count":
                            retry_count,
                        "reused":
                            True,
                        "wall_clock_seconds":
                            sample.get(
                                "wall_clock_seconds",
                                0,
                            ),
                    }
                )

            print(
                f"REUSE {candidate_number}/631 "
                f"{benchmark} "
                f"{instance_id} "
                f"step={step_index} "
                f"K=8",
                flush=True,
            )

            continue

        samples = []

        for continuation_index in range(
            1,
            K + 1,
        ):
            sampling_key = {
                "instance_id":
                    instance_id,
                "step_index":
                    step_index,
                "continuation_index":
                    continuation_index,
                "master_seed":
                    MASTER_SEED,
            }

            request = {
                "model":
                    MODEL,
                "input":
                    prompt,
                "reasoning": {
                    "effort":
                        REASONING_EFFORT
                },
                "max_output_tokens":
                    API_MAX_OUTPUT_TOKENS,
                "store":
                    False,
            }

            if tools is not None:
                request["tools"] = (
                    tools
                )

                request["tool_choice"] = (
                    "auto"
                )

                request[
                    "parallel_tool_calls"
                ] = parallel_tool_calls

            retry_count = 0
            attempt_records = []
            all_attempt_usage = zero_usage()
            all_attempt_latency = 0.0

            while True:
                started = time.perf_counter()

                response = client.responses.create(
                    **request
                )

                elapsed_attempt = (
                    time.perf_counter()
                    - started
                )

                total_api_calls += 1
                all_attempt_latency += elapsed_attempt

                if (
                    getattr(
                        response,
                        "status",
                        None,
                    )
                    != "completed"
                ):
                    raise RuntimeError(
                        "Incomplete Terra response "
                        f"for {instance_id} "
                        f"step={step_index} "
                        f"k={continuation_index}"
                    )

                returned_model = getattr(
                    response,
                    "model",
                    None,
                )

                if returned_model != MODEL:
                    raise RuntimeError(
                        "Returned model mismatch: "
                        f"{returned_model} != {MODEL}"
                    )

                usage = usage_dict(
                    response
                )

                add_usage(
                    all_attempt_usage,
                    usage,
                )

                function_calls = (
                    extract_function_calls(
                        response
                    )
                )

                visible_text = (
                    response.output_text
                    or ""
                ).strip()

                observable = bool(
                    function_calls
                    or visible_text
                )

                within_decision_limit = (
                    usage["decision_tokens"]
                    <= SCIENTIFIC_MAX_DECISION_TOKENS
                )

                valid_continuation = True
                invalid_reason = None

                attempt_records.append(
                    {
                        "attempt_index":
                            retry_count,
                        "response_id":
                            response.id,
                        "usage":
                            usage,
                        "observable":
                            observable,
                        "within_decision_limit":
                            within_decision_limit,
                        "valid_continuation":
                            valid_continuation,
                        "invalid_reason":
                            invalid_reason,
                        "wall_clock_seconds":
                            elapsed_attempt,
                    }
                )

                if valid_continuation:
                    break

                failure_path = (
                    FAILURE_DIR
                    / (
                        f"{instance_id}"
                        f"__step_{step_index:04d}"
                        f"__k_{continuation_index:02d}"
                        f"__attempt_{retry_count:02d}"
                        f"__{invalid_reason}.json"
                    )
                )

                failure_path.write_text(
                    json.dumps(
                        {
                            "instance_id":
                                instance_id,
                            "benchmark":
                                benchmark,
                            "step_index":
                                step_index,
                            "continuation_index":
                                continuation_index,
                            "attempt_index":
                                retry_count,
                            "invalid_reason":
                                invalid_reason,
                            "response_id":
                                response.id,
                            "usage":
                                usage,
                            "observable":
                                observable,
                            "within_decision_limit":
                                within_decision_limit,
                            "output_text":
                                response.output_text,
                            "function_calls":
                                function_calls,
                            "raw_response":
                                serialize_response(
                                    response
                                ),
                            "posthoc_fields_used":
                                False,
                        },
                        indent=2,
                        sort_keys=True,
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n",
                    encoding="utf-8",
                )

                if (
                    retry_count
                    >= MAX_INVALID_CONTINUATION_RETRIES
                ):
                    raise RuntimeError(
                        "Terra exceeded bounded invalid "
                        "continuation retry limit: "
                        f"{instance_id} "
                        f"step={step_index} "
                        f"k={continuation_index} "
                        f"invalid_reason={invalid_reason} "
                        f"decision_tokens="
                        f"{usage['decision_tokens']} "
                        f"retry_count={retry_count}"
                    )

                retry_count += 1

            if function_calls:
                continuation_type = (
                    "joint_tool_call"
                    if len(
                        function_calls
                    ) > 1
                    else "tool_call"
                )

                canonical_payload = {
                    "type":
                        continuation_type,
                    "function_calls":
                        function_calls,
                }

            elif visible_text:
                continuation_type = (
                    "assistant_text"
                )

                full_visible_text = visible_text

                visible_token_ids = tokenizer.encode(
                    full_visible_text
                )

                continuation_token_ids = (
                    visible_token_ids[
                        :SCIENTIFIC_MAX_DECISION_TOKENS
                    ]
                )

                visible_text = tokenizer.decode(
                    continuation_token_ids
                )

                canonical_payload = {
                    "type":
                        "assistant_text",
                    "text":
                        visible_text,
                }

            else:
                continuation_type = (
                    "no_observable_output"
                )

                full_visible_text = ""

                canonical_payload = {
                    "type":
                        "no_observable_output"
                }

            elapsed = all_attempt_latency

            type_counts[
                continuation_type
            ] += 1

            add_usage(
                totals,
                all_attempt_usage,
            )

            accepted_continuations += 1

            record = {
                "project":
                    "DECOUPLE",
                "stage":
                    "10_PILOT",
                "step":
                    "STEP1",
                "artifact_type":
                    "local_continuation_sample",
                "benchmark":
                    benchmark,
                "instance_id":
                    instance_id,
                "step_index":
                    step_index,
                "prefix_hash":
                    prefix[
                        "prefix_hash"
                    ],
                "continuation_index":
                    continuation_index,
                "sampling_key":
                    sampling_key,
                "sampling_key_hash":
                    canonical_hash(
                        sampling_key
                    ),
                "provider_seed_parameter":
                    "unavailable",
                "model":
                    MODEL,
                "reasoning_effort":
                    REASONING_EFFORT,
                "requested_temperature":
                    REQUESTED_TEMPERATURE,
                "requested_top_p":
                    REQUESTED_TOP_P,
                "effective_sampling":
                    EFFECTIVE_SAMPLING,
                "api_max_output_tokens":
                    API_MAX_OUTPUT_TOKENS,
                "scientific_max_decision_tokens":
                    SCIENTIFIC_MAX_DECISION_TOKENS,
                "response_id":
                    response.id,
                "returned_model":
                    returned_model,
                "continuation_type":
                    continuation_type,
                "continuation":
                    canonical_payload,
                "visible_text":
                    visible_text,
                "function_calls":
                    function_calls,
                "usage":
                    usage,
                "local_window": {
                    "tokenizer_model":
                        TOKENIZER_MODEL,
                    "tokenizer_encoding":
                        TOKENIZER_ENCODING,
                    "max_generated_tokens":
                        SCIENTIFIC_MAX_DECISION_TOKENS,
                    "applied_to":
                        (
                            "assistant_text"
                            if continuation_type
                            == "assistant_text"
                            else "structured_action_atomic"
                        ),
                    "provider_decision_tokens":
                        usage["decision_tokens"],
                    "archived_text_tokens":
                        (
                            len(
                                tokenizer.encode(
                                    visible_text
                                )
                            )
                            if continuation_type
                            == "assistant_text"
                            else None
                        ),
                    "text_truncated":
                        (
                            len(
                                tokenizer.encode(
                                    full_visible_text
                                )
                            )
                            > SCIENTIFIC_MAX_DECISION_TOKENS
                            if continuation_type
                            == "assistant_text"
                            else False
                        ),
                },
                "full_visible_text":
                    (
                        full_visible_text
                        if continuation_type
                        == "assistant_text"
                        else ""
                    ),
                "all_attempt_usage":
                    all_attempt_usage,
                "retry_count":
                    retry_count,
                "attempts":
                    attempt_records,
                "wall_clock_seconds":
                    elapsed,
                "candidate_kind_used_as_model_input":
                    False,
                "candidate_step_used_as_model_input":
                    False,
                "posthoc_fields_used":
                    False,
            }

            samples.append(
                record
            )

            ledger_rows.append(
                {
                    "benchmark":
                        benchmark,
                    "instance_id":
                        instance_id,
                    "step_index":
                        step_index,
                    "continuation_index":
                        continuation_index,
                    "response_id":
                        response.id,
                    "continuation_type":
                        continuation_type,
                    "usage":
                        usage,
                    "all_attempt_usage":
                        all_attempt_usage,
                    "retry_count":
                        retry_count,
                    "reused":
                        False,
                    "wall_clock_seconds":
                        elapsed,
                }
            )

        out_path.write_text(
            "".join(
                json.dumps(
                    sample,
                    sort_keys=True,
                    ensure_ascii=False,
                )
                + "\n"
                for sample in samples
            ),
            encoding="utf-8",
        )

        archive_index.append(
            {
                "benchmark":
                    benchmark,
                "instance_id":
                    instance_id,
                "step_index":
                    step_index,
                "prefix_hash":
                    prefix[
                        "prefix_hash"
                    ],
                "continuation_count":
                    len(samples),
                "path":
                    str(
                        out_path.relative_to(
                            ROOT
                        )
                    ),
                "sha256":
                    sha256_file(
                        out_path
                    ),
            }
        )

        print(
            f"DONE {candidate_number}/631 "
            f"{benchmark} "
            f"{instance_id} "
            f"step={step_index} "
            f"K=8",
            flush=True,
        )

    if accepted_continuations != 5048:
        raise RuntimeError(
            "Expected 5048 accepted continuations, "
            f"got {accepted_continuations}"
        )

    immutable_inputs_after = {
        "prefix_index":
            sha256_file(
                PREFIX_INDEX
            ),
        "bfcl_tools_pre":
            sha256_file(
                BFCL_TOOLS_PRE
            ),
        "toolalpaca_execution_pre":
            sha256_file(
                TOOLALPACA_EXEC_PRE
            ),
    }

    if (
        immutable_inputs_before
        != immutable_inputs_after
    ):
        raise RuntimeError(
            "Frozen input changed during K8 run."
        )

    index_path = (
        OUT_DIR
        / "PILOT_K8_CONTINUATION_INDEX.json"
    )

    index_path.write_text(
        json.dumps(
            archive_index,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    ledger = {
        "status":
            "PASS",
        "model":
            MODEL,
        "reasoning_effort":
            REASONING_EFFORT,
        "K":
            K,
        "candidate_count":
            631,
        "continuation_count":
            accepted_continuations,
        "model_calls":
            total_api_calls,
        "invalid_continuation_retries":
            total_api_calls
            - accepted_continuations,
        "max_invalid_continuation_retries":
            MAX_INVALID_CONTINUATION_RETRIES,
        "invalid_continuation_policy":
            "retry_provider_completed_no_observable_only",
        "requested_temperature":
            REQUESTED_TEMPERATURE,
        "requested_top_p":
            REQUESTED_TOP_P,
        "effective_sampling":
            EFFECTIVE_SAMPLING,
        "provider_seed_parameter":
            "unavailable",
        "master_seed_key":
            MASTER_SEED,
        "api_max_output_tokens":
            API_MAX_OUTPUT_TOKENS,
        "scientific_max_decision_tokens":
            SCIENTIFIC_MAX_DECISION_TOKENS,
        "continuation_type_counts":
            type_counts,
        "usage":
            totals,
        "calls":
            ledger_rows,
    }

    ledger_path = (
        AUDIT_DIR
        / "PILOT_K8_COMPUTE_LEDGER.json"
    )

    ledger_path.write_text(
        json.dumps(
            ledger,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "status":
            "PASS",
        "candidate_count":
            631,
        "continuation_count":
            5048,
        "K":
            8,
        "model":
            MODEL,
        "reasoning_effort":
            REASONING_EFFORT,
        "requested_temperature":
            REQUESTED_TEMPERATURE,
        "requested_top_p":
            REQUESTED_TOP_P,
        "effective_sampling":
            EFFECTIVE_SAMPLING,
        "provider_temperature_compatibility_amendment":
            True,
        "provider_seed_parameter":
            "unavailable",
        "sampling_key_master_seed":
            MASTER_SEED,
        "api_max_output_tokens":
            API_MAX_OUTPUT_TOKENS,
        "scientific_max_decision_tokens":
            SCIENTIFIC_MAX_DECISION_TOKENS,
        "bfcl_native_tools":
            True,
        "toolalpaca_native_tools":
            True,
        "candidate_kind_used_as_model_input":
            False,
        "candidate_step_used_as_model_input":
            False,
        "posthoc_fields_used":
            False,
        "prefix_index_sha256":
            sha256_file(
                PREFIX_INDEX
            ),
        "bfcl_tools_pre_sha256":
            sha256_file(
                BFCL_TOOLS_PRE
            ),
        "toolalpaca_execution_pre_sha256":
            sha256_file(
                TOOLALPACA_EXEC_PRE
            ),
        "continuation_index_sha256":
            sha256_file(
                index_path
            ),
        "compute_ledger_sha256":
            sha256_file(
                ledger_path
            ),
        "semantic_clustering_performed":
            False,
    }

    manifest_path = (
        AUDIT_DIR
        / "PILOT_K8_ARCHIVE_MANIFEST.json"
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "===== PILOT K8 LOCAL CONTINUATIONS ====="
    )
    print("STATUS=PASS")
    print("CANDIDATE_COUNT=631")
    print("K=8")
    print("CONTINUATION_COUNT=5048")
    print(
        "MODEL_CALLS="
        + str(total_api_calls)
    )
    print(
        "INVALID_CONTINUATION_RETRIES="
        + str(
            total_api_calls
            - accepted_continuations
        )
    )
    print(
        "ASSISTANT_TEXT_COUNT="
        + str(
            type_counts[
                "assistant_text"
            ]
        )
    )
    print(
        "TOOL_CALL_COUNT="
        + str(
            type_counts[
                "tool_call"
            ]
        )
    )
    print(
        "JOINT_TOOL_CALL_COUNT="
        + str(
            type_counts[
                "joint_tool_call"
            ]
        )
    )
    print(
        "INPUT_TOKENS="
        + str(
            totals[
                "input_tokens"
            ]
        )
    )
    print(
        "OUTPUT_TOKENS="
        + str(
            totals[
                "output_tokens"
            ]
        )
    )
    print(
        "REASONING_TOKENS="
        + str(
            totals[
                "reasoning_tokens"
            ]
        )
    )
    print(
        "DECISION_TOKENS="
        + str(
            totals[
                "decision_tokens"
            ]
        )
    )
    print(
        "TOTAL_TOKENS="
        + str(
            totals[
                "total_tokens"
            ]
        )
    )
    print(
        "BFCL_NATIVE_TOOLS=YES"
    )
    print(
        "TOOLALPACA_NATIVE_TOOLS=YES"
    )
    print(
        "CANDIDATE_KIND_USED_AS_MODEL_INPUT=NO"
    )
    print(
        "CANDIDATE_STEP_USED_AS_MODEL_INPUT=NO"
    )
    print(
        "POSTHOC_FIELDS_USED=NO"
    )
    print(
        "SEMANTIC_CLUSTERING_PERFORMED=NO"
    )
    print(
        "INDEX_SHA256="
        + sha256_file(
            index_path
        )
    )
    print(
        "COMPUTE_LEDGER_SHA256="
        + sha256_file(
            ledger_path
        )
    )
    print(
        "MANIFEST_SHA256="
        + sha256_file(
            manifest_path
        )
    )


if __name__ == "__main__":
    main()
